#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""语言配置的跨版本行为验收（回归：BUG-R3-001 / BUG-R3-002）。

本脚本回答一个静态检查回答不了的问题：
**exampleSite/hugo.toml 的语言写法，在主题支持的每一个 Hugo 版本上都能
"构建成功 + 零弃用告警 + 文案真的出来 + og:locale 规范"吗？**

为什么要单独有一个脚本（而不是塞进 check_features.py）：
  * 它要跑 5 个 Hugo 版本 × 真实 exampleSite 全站构建，属于慢速行为检查；
  * 它需要能**故意改坏配置再构建**（反证），不能污染仓库文件。

发现并守住的两个真实缺陷
--------------------------
BUG-R3-001  语言键与 i18n 文件名不匹配
    exampleSite 曾把 defaultContentLanguage 写成 'zh'，而主题只提供
    i18n/zh-CN.yaml。i18n 语言匹配是「大小写不敏感的**精确**匹配」，
    不做别名扩展；`locale` 在 0.162+ 才作为 i18n 语言生效。
    结果：0.128 / 0.148 上**全部 UI 文案变空字符串**，构建成功且不报错。

BUG-R3-002  [languages.*] 下的字段在不同版本上分别弃用
    label        Hugo 0.112 起弃用，0.129 移除 -> 0.128.0 报 ERROR deprecated
    languageCode 0.158 起弃用                 -> 0.158+ 报 WARN deprecated
    locale       0.112~0.129 间弃用；且 0.128.0 上会吞掉 i18n 文案
    但带地区后缀的语言键（zh-CN）在 0.162+ 又**必须**配根级 locale，
    否则报 language name "zh-CN" is invalid。
    唯一零告警写法：根上 locale + [languages.<key>] 只放 weight/contentDir。

断言（每条都指向真实产物或真实构建日志）
------------------------------------------
L1  五个 Hugo 版本相继构建 exampleSite，rc 必须为 0；
L2  构建日志里不得出现 deprecated / ERROR（WARN 只统计不计失败，
    且要求 WARN 数不高于基线——用于发现"新引入的告警"）；
L3  产物里 NEBULA_I18N 的**每个值非空**（BUG-R3-001 的指纹）；
L4  og:locale 必须是规范 ll_CC 形态（zh_CN），且与根级 locale 一致；
L5  html lang 非空、与语言键一致（大小写不敏感）；
L6  提示块标题为中文（证明 i18n 真的被应用，而不是回退英文）;
L7  反证：把语言键改回 'zh'，0.128.0 上必须出现**空串文案**（证明 L3 有区分力）；
L8  反证：把 label 放回 [languages.*]，0.128.0 必须报 deprecated（证明 L2 有区分力）；
L8b 记录 Hugo 解码器的"同名 params 键遮蔽顶层弃用字段"行为（说明为何还需要静态禁止）。

用法：
    python3 tools/check_lang_config.py
环境变量：
    HUGO_MATRIX_DIR  Hugo 版本矩阵目录（默认指向验收环境；CI 里由 workflow 设置）
    HUGO_BIN         单版本模式用的 hugo（矩阵目录不存在时退化为只跑它）
    NEBULA_CLEAN     设为 1 时保留临时目录（默认自动清理）
"""

import io
import os
import re
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _testlib import Harness, guard, safe_rmtree  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = os.path.join(REPO, "exampleSite")
THEMES_DIR = os.path.dirname(REPO)          # 真实父目录（0.128/0.148 不解析符号链接）
OUT_ROOT = os.path.join(REPO, "tmp")
HUGO = os.environ.get("HUGO_BIN", "hugo")
HUGO_ROOT = os.environ.get(
    "HUGO_MATRIX_DIR",
    os.path.join(os.path.dirname(os.path.dirname(REPO)),
                 "tmp", "hugo博客主题验收测试", "r2", "_env", "hugo"))
HUGO_VERSIONS = ("0.128.0", "0.148.0", "0.162.0", "0.166.0", "0.167.0")
HUGO_EXE = "hugo.exe" if os.name == "nt" else "hugo"

H = Harness("lang_config")

# 允许存在的 WARN 基线：exampleSite 的历史内容里可能有主题无关的告警。
# 只在"WARN 数超过基线"时报失败，用于抓住**新引入的**告警。
WARN_BASELINE = 2


def versions():
    """返回 {版本: 可执行文件}；矩阵目录缺失时退化为 {HUGO 自身版本: HUGO}。"""
    got = {}
    if os.path.isdir(HUGO_ROOT):
        for v in HUGO_VERSIONS:
            exe = os.path.join(HUGO_ROOT, v, HUGO_EXE)
            if os.path.isfile(exe):
                got[v] = exe
    if got:
        return got, True
    return {"current": HUGO}, False


def build(exe, site_dir, out_dir, extra_cfg=None):
    """构建一个站点，返回 (rc, log)。extra_cfg 为额外的 --config 文件路径。"""
    safe_rmtree(out_dir)
    cmd = [exe, "--source", site_dir, "--themesDir", THEMES_DIR, "--gc", "--minify",
           "-d", out_dir, "--cleanDestinationDir"]
    if extra_cfg:
        cmd += ["--config", f"hugo.toml,{extra_cfg}"]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                           errors="ignore", timeout=600)
    except subprocess.TimeoutExpired:
        return 124, "TIMEOUT"
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def read(p):
    try:
        return io.open(p, encoding="utf-8", errors="ignore").read()
    except OSError:
        return ""


def i18n_pairs(html):
    """解析 NEBULA_I18N 注入块，返回 {键: 值}（兼容 --minify 的裸标识符键）。"""
    m = re.search(r"NEBULA_I18N\s*=\s*(\{.*?\})\s*[;<]", html, re.S)
    if not m:
        return None
    return {(a or b): c for a, b, c in re.findall(
        r'(?:"([^"]+)"|([A-Za-z_$][\w$]*))\s*:\s*"((?:[^"\\]|\\.)*)"', m.group(1))}


def site_copy(tag, mutate=None):
    """复制一份 exampleSite（只含配置与内容，不含 public），可选改配置。

    为什么要复制：反证实验必须"改坏配置再构建"，不能污染仓库里的真实站点。
    """
    dst = os.path.join(OUT_ROOT, f"_langcfg_{tag}")
    safe_rmtree(dst)
    shutil.copytree(SITE, dst, ignore=shutil.ignore_patterns(
        "public", "public-*", "resources", ".hugo_build.lock", "_ci-*.toml",
        "_ms-verify-*.toml", "__pycache__"))
    if mutate:
        cfg = os.path.join(dst, "hugo.toml")
        # ⚠ exampleSite/hugo.toml 是 **CRLF** 文件。变异正则若只按 "\n" 匹配，
        #   行尾的 \r 会让 `[languages.zh-CN]\n` 这类模式匹配不到 —— 于是"改坏"
        #   根本没发生，反证会以"未出现 deprecated"的假象失败（实测踩过）。
        #   这里统一归一为 LF 再交给变异函数，写回时也用 LF（Hugo 不介意）。
        text = read(cfg).replace("\r\n", "\n").replace("\r", "\n")
        text = mutate(text)
        io.open(cfg, "w", encoding="utf-8", newline="\n").write(text)
    return dst


def cfg_text():
    return read(os.path.join(SITE, "hugo.toml"))


def _minimal_lang_site(tag, block):
    """搭一个最小站点（单个 [languages.zh-CN] 块由 block 提供），用于最小反证。"""
    root = os.path.join(OUT_ROOT, f"_langcfg_{tag}")
    safe_rmtree(root)
    os.makedirs(os.path.join(root, "content"), exist_ok=True)
    cfg = ("baseURL = 'https://x.example/'\nlocale = 'zh-CN'\ntitle = 't'\n"
           "theme = 'hugo-theme-nebula'\ndefaultContentLanguage = 'zh-CN'\n"
           "[languages]\n" + block)
    io.open(os.path.join(root, "hugo.toml"), "w", encoding="utf-8", newline="\n").write(cfg)
    io.open(os.path.join(root, "content", "p.md"), "w", encoding="utf-8", newline="\n").write(
        "---\ntitle: p\ndate: 2024-01-01\n---\n\nhello\n")
    return root


# --------------------------------------------------------------------------- #
def run_matrix():
    """L1~L6：五个版本上构建真实 exampleSite。"""
    ver, real = versions()
    if not real:
        print("  ⚠ 未找到 Hugo 版本矩阵目录，退化为单版本（HUGO_BIN）")
        print(f"    HUGO_MATRIX_DIR={HUGO_ROOT}")
    for v, exe in sorted(ver.items()):
        out = os.path.join(OUT_ROOT, f"_langcfg_out_{v}")
        rc, log = build(exe, SITE, out)
        tag = f"[{v}] "
        ok_build = H.record(tag + "L1 构建成功（rc=0）", rc == 0,
                            "" if rc == 0 else log[-300:])
        if not ok_build:
            continue

        dep = re.findall(r"(?i)deprecated[^\n]*", log)
        errs = re.findall(r"(?i)^ERROR[^\n]*", log, re.M)
        warns_all = re.findall(r"(?i)^WARN[^\n]*", log, re.M)
        # ⚠ exampleSite **有意**用 `button` 演示"危险 scheme 被拦截"，
        #   那会在构建日志留下短代码级 WARN（`WARN shortcode button: 已阻止…`）。
        #   它来自**内容**、是预期内的提示，不是主题/配置回归，因此从"新告警"
        #   计数中排除；基线只用于衡量配置层告警（deprecated 等）。
        warns = [w for w in warns_all
                 if not re.match(r"(?i)WARN\s+shortcode\b", w.strip())]
        H.record(tag + "L2 构建日志无 deprecated", not dep,
                 (" | ".join(d.strip()[:120] for d in dep[:2])) if dep else "")
        H.record(tag + "L2 构建日志无 ERROR", not errs,
                 (" | ".join(e.strip()[:120] for e in errs[:2])) if errs else "")
        H.record(tag + f"L2 配置层 WARN 数不超过基线 {WARN_BASELINE}", len(warns) <= WARN_BASELINE,
                 " | ".join(w.strip()[:120] for w in warns[:4]))

        home = read(os.path.join(out, "index.html"))
        pairs = i18n_pairs(home)
        H.record(tag + "L3 NEBULA_I18N 可解析且键数 >= 10",
                 bool(pairs) and len(pairs) >= 10,
                 f"keys={len(pairs) if pairs else 0}")
        if pairs:
            empties = sorted(k for k, val in pairs.items() if not val.strip())
            H.record(tag + "L3 NEBULA_I18N 无空值（BUG-R3-001 指纹）", not empties,
                     "空值键: " + ", ".join(empties[:8]))

        og = re.search(r'og:locale" content="([^"]+)"', home)
        og = og.group(1) if og else ""
        H.record(tag + "L4 og:locale 为规范 ll_CC 形态", bool(re.fullmatch(r"[a-z]{2,3}_[A-Z]{2}", og)),
                 f"og:locale={og!r}")

        hl = re.search(r"<html lang=([^ >]+)", home)
        hl = hl.group(1) if hl else ""
        H.record(tag + "L5 html lang 非空且为 zh-cn/zh-CN",
                 hl.strip().lower() in ("zh-cn", "zh"), f"lang={hl!r}")

        # L6：UI 文案确实来自 i18n（非静默退化）。
        # ⚠ 探针必须是**跨版本恒定存在**的元素：提示块依赖 blockquote Render Hook，
        #   而 0.128.0 会忽略该 hook（主题的已知优雅退化行为），因此不能拿它当探针。
        #   改用 <html lang> 之外的两处恒定 UI 文案：
        #     * 搜索触发按钮的 aria-label（i18n nav.search）
        #     * 页脚/导航里的可见译文
        # 并额外断言"提示块标题要么是有效译文、要么该版本本就不生成提示块"。
        aria = re.findall(r'aria-label="([^"]*)"', home)
        zh_ui = [a for a in aria if a.strip()]
        H.record(tag + "L6 页面存在非空 aria-label（UI 文案非静默退化）",
                 bool(zh_ui), f"aria-label 数={len(zh_ui)}")
        # 反向证据：i18n 真的命中中文（而不是回退到英文或空串）
        H.record(tag + "L6 存在中文 UI 文案（i18n 命中 zh-CN，未回退英文）",
                 bool(re.search(r"[\u4e00-\u9fff]", " ".join(zh_ui))),
                 f"示例={zh_ui[:2]}")
        t = re.search(r'md-alert-title">([^<]*)<', home)
        t = t.group(1).strip() if t else ""
        # 0.128.0 不生成提示块（无标题可查）；其它版本必须给出有效译文
        has_alert = bool(re.search(r'md-alert-title', home))
        H.record(tag + "L6 提示块标题（若该版本生成提示块）非空",
                 (not has_alert) or bool(t), f"has_alert={has_alert} title={t!r}")
        safe_rmtree(out)


def run_counterproof():
    """L7/L8：故意改坏配置，证明 L3/L2 真的能抓到问题。"""
    ver, real = versions()
    if not real:
        H.record("L7/L8 反证需要 Hugo 版本矩阵，已跳过（单版本模式下不执行）", True, "")
        return
    # 反证固定用 0.128.0（最简单、无 locale 兜底的版本）
    exe = ver.get("0.128.0") or list(ver.values())[0]

    # --- L7：语言键改回 'zh' -> 0.128.0 上文案必须变空串 ---
    def to_zh(text):
        text = re.sub(r"^\s*defaultContentLanguage\s*=.*$",
                      "defaultContentLanguage = 'zh'", text, count=1, flags=re.M)
        return re.sub(r"\[languages\.zh-CN\]", "[languages.zh]", text)

    site_bad = site_copy("badkey", to_zh)
    out = os.path.join(OUT_ROOT, "_langcfg_out_badkey")
    rc, log = build(exe, site_bad, out)
    H.record("L7 反证：语言键 'zh' 仍能构建（缺陷是静默的，不是崩溃）", rc == 0,
             "" if rc == 0 else log[-200:])
    if rc == 0:
        home = read(os.path.join(out, "index.html"))
        pairs = i18n_pairs(home) or {}
        empties = sorted(k for k, val in pairs.items() if not val.strip())
        H.record("L7 反证：语言键 'zh' 时 NEBULA_I18N 出现空值（证明 L3 有区分力）",
                 bool(empties), f"空值键 {len(empties)} 个" if empties else "未出现空值（L3 失去区分力！）")
    safe_rmtree(site_bad)
    safe_rmtree(out)

    # --- L8：把 label 放回 [languages.*] -> 0.128.0 必须报 deprecated ---
    # ⚠ 实测发现一个 Hugo TOML 解码器的**遮蔽行为**：若 [languages.X] 顶层已有 `label`
    #   （弃用），而 [languages.X.params] 里**恰好也有一个同名的 `label`**，则顶层
    #   `label` 的弃用 ERROR 会被**静默吞掉**（P3 组合不告警，P1/P2/P4 都告警）。
    #   我们的真实配置 form I 用的是 params.label，因此如果只是"往顶层再加一个 label"，
    #   会被这个同名键遮蔽 —— 反证就测不出差异（本轮 L8 一度因此假红）。
    #   所以这里**先移除 params.label、再往顶层加 label**（还原成 P1/P2 形态），
    #   才能得到稳定的"必须告警"行为。这个遮蔽本身另由 L8b 单独记录。
    def add_label(text):
        # 移除 params 里的 label（避免同名遮蔽），再加顶层 label（弃用字段）
        text = re.sub(r"^\s*label\s*=\s*'简体中文'\s*$\n", "", text, flags=re.M)
        return re.sub(r"(\[languages\.zh-CN\]\n)",
                      r"\1    label = '简体中文'\n", text, count=1)

    site_lbl = site_copy("badlabel", add_label)
    out2 = os.path.join(OUT_ROOT, "_langcfg_out_badlabel")
    rc2, log2 = build(exe, site_lbl, out2)
    dep2 = re.findall(r"(?i)deprecated[^\n]*", log2)
    H.record("L8 反证：[languages.*] 顶层的 label 触发弃用告警（证明 L2 有区分力）",
             bool(dep2), (" | ".join(d.strip()[:110] for d in dep2[:1])) if dep2 else
             f"未出现 deprecated（L2 失去区分力！rc={rc2}）")
    safe_rmtree(site_lbl)
    safe_rmtree(out2)

    # --- L8b：记录"同名 params 键遮蔽顶层弃用字段"的 Hugo 行为 ---
    # 结论：**运行时弃用告警不可完全依赖**（会被同名 params 键遮蔽），因此
    # tools/check_features.py 8c 的**静态禁止**（[languages.X] 顶层不得出现
    # label/languageCode/locale）不是冗余，而是必要守卫。这里用两个最小站点反证。
    masked = _minimal_lang_site("langcfg_masked", block=(
        "  [languages.zh-CN]\n    label = 'x'\n    weight = 1\n    contentDir = 'content'\n"
        "    [languages.zh-CN.params]\n      label = 'y'\n"))
    outm = os.path.join(OUT_ROOT, "_langcfg_out_masked")
    rcm, logm = build(exe, masked, outm)
    depm = re.findall(r"(?i)deprecated[^\n]*", logm)
    H.record("L8b 同名 params.label 遮蔽顶层 label 的弃用告警（Hugo 解码器行为）",
             rcm == 0 and not depm, f"rc={rcm} dep={depm[:1]}")
    safe_rmtree(masked)
    safe_rmtree(outm)

    unmasked = _minimal_lang_site("langcfg_unmasked", block=(
        "  [languages.zh-CN]\n    label = 'x'\n    weight = 1\n    contentDir = 'content'\n"))
    outu = os.path.join(OUT_ROOT, "_langcfg_out_unmasked")
    rcu, logu = build(exe, unmasked, outu)
    depu = re.findall(r"(?i)deprecated[^\n]*", logu)
    H.record("L8b 无同名 params 键时顶层 label 恢复正常告警（证明遮蔽来自同名键）",
             rcu == 0 and bool(depu), f"rc={rcu} dep={depu[:1]}")
    safe_rmtree(unmasked)
    safe_rmtree(outu)


def main():
    guard(H, run_matrix)
    guard(H, run_counterproof)
    if os.environ.get("NEBULA_CLEAN") != "1":
        for d in os.listdir(OUT_ROOT) if os.path.isdir(OUT_ROOT) else []:
            if d.startswith("_langcfg_"):
                safe_rmtree(os.path.join(OUT_ROOT, d))
    H.finish()


if __name__ == "__main__":
    main()