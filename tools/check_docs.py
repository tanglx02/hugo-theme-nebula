#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""文档一致性检查：README / CHANGELOG 中的关键表述不得回退。

本轮教训：README 曾用"零外部 CDN 请求""无 CDN"描述主题，容易让用户误解为
"任何配置下都没有第三方请求"。这里把关键表述固化成断言，防止再次回退。

检查项：
    1. README 不得出现"零外部 CDN 请求" / "无 CDN" / "完全没有 CDN"等绝对表述
    2. README 必须说明：默认无外部 CDN；启用可选评论/统计后可能加载第三方资源
    3. README 必须列出五个第三方服务：giscus / Waline / Twikoo / Disqus / busuanzi
    4. README 必须说明这些服务"默认关闭"
    5. CHANGELOG 必须存在且含当前版本条目

退出码约定（见 tools/_testlib.py）：任一断言失败 -> exit 1。

用法：python3 tools/check_docs.py [repo_root]
"""
import os
import re
import sys

from _testlib import Harness, guard

ROOT = sys.argv[1] if len(sys.argv) > 1 else os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

# Release 全站审计的**准确表述**（必须出现在 audit.py / CI / 文档中）
REQUIRED_TRUTH_WORDING = "以构建产物 HTML inventory 为真值"

# 禁止的过时表述：把 sitemap 当作全站真值
STALE_PHRASES = [
    "sitemap 中**全部可审计 HTML 页面**",
    "sitemap 中全部 HTML 页面",
    "sitemap 全部 HTML 页面",
    "覆盖 sitemap 全部 HTML 页面",
    "扫描 sitemap 中全部",
    "sitemap + pagination = 全站",
]

# 绝对化表述：出现即判失败
FORBIDDEN_PHRASES = [
    "零外部 CDN 请求",
    "零外部CDN请求",
    "无外部 CDN 请求。",       # 允许"默认…无外部 CDN 请求"这类限定表述
    "无 CDN\n",
    "完全没有 CDN",
    "任何配置下都没有外部",
    "不加载任何第三方",         # 除非紧邻"默认"限定（单独出现视为过度承诺）
]

REQUIRED_SERVICES = ["giscus", "Waline", "Twikoo", "Disqus", "busuanzi"]

# 必须出现的语义要点（任一命中即可）
REQUIRED_MEANINGS = [
    ("默认无外部 CDN", ["默认配置下无外部 CDN", "默认无外部 CDN",
                        "默认情况下主题无外部 CDN", "默认关闭可选第三方服务时无外部 CDN"]),
    ("启用后加载第三方", ["启用可选评论", "启用评论", "启用可选的评论",
                          "开启后会", "启用评论/统计"]),
]


def check_truth_wording(h):
    """Release 全站审计的表述一致性（准确表述必须在场，过时表述必须缺席）。"""
    targets = [
        ("tools/audit.py", os.path.join(ROOT, "tools", "audit.py")),
        (".github/workflows/ci.yml", os.path.join(ROOT, ".github", "workflows", "ci.yml")),
        ("README.md", os.path.join(ROOT, "README.md")),
    ]
    missing, stale = [], []
    for label, path in targets:
        if not os.path.isfile(path):
            missing.append(f"{label}(文件不存在)")
            continue
        text = open(path, encoding="utf-8").read()
        if REQUIRED_TRUTH_WORDING not in text:
            missing.append(f"{label} 缺少准确表述")
        for ph in STALE_PHRASES:
            if ph in text:
                line_no = text[: text.index(ph)].count("\n") + 1
                stale.append(f"{label}:{line_no} 仍写着「{ph}」")
    h.record("audit.py / CI / README 均声明「inventory 为全站真值」",
             not missing, "；".join(missing) if missing else "三处均已声明")
    h.record("无「sitemap = 全站」类过时表述",
             not stale, "；".join(stale[:3]) if stale else "无过时表述")


def run(h):
    readme_p = os.path.join(ROOT, "README.md")
    if not os.path.isfile(readme_p):
        h.fatal_error("README.md 不存在", readme_p)
        return
    readme = open(readme_p, encoding="utf-8").read()

    # ① 绝对化表述
    bad = []
    quoted = []          # 作为"被批评的示例"被引号包裹的引用，豁免但必须打印
    for ph in FORBIDDEN_PHRASES:
        for m in re.finditer(re.escape(ph), readme):
            line_no = readme[: m.start()].count("\n") + 1
            line_start = readme.rfind("\n", 0, m.start()) + 1
            line_end = readme.find("\n", m.end())
            line = readme[line_start: line_end if line_end > 0 else len(readme)]
            ctx = line.strip()[:80]
            # "默认配置下无外部 CDN 请求" 这类限定表述不算问题
            if "默认" in ctx:
                continue
            # 元语境：把该短语作为"被禁止/被回退的示例"引用时豁免（如更新日志、
            # 门禁说明），但必须打印，保证"引用"不会被误当成"声明"
            if re.search(r"[\"“”「」]|防止|回退|不再|这类表述|绝对化", line):
                quoted.append(f"第 {line_no} 行（作为示例引用，豁免）: {ctx}")
                continue
            bad.append(f"第 {line_no} 行: …{ctx}…")
    h.record("README 无绝对化的 CDN 表述", not bad, "；".join(bad[:3]) if bad else "干净")
    if quoted:
        print("\n被禁短语作为示例被引用（已豁免，请确认是批评性引用而非声明）:")
        for q in quoted:
            print("   ", q)

    # ② 必须说明默认无 CDN + 启用后有第三方
    missing = [name for name, pats in REQUIRED_MEANINGS
               if not any(p in readme for p in pats)]
    h.record("README 说明「默认无外部 CDN / 启用后可能加载第三方」",
             not missing, f"缺少: {missing}" if missing else "表述完整")

    # ③ 五个第三方服务必须列出
    absent = [s for s in REQUIRED_SERVICES if s not in readme]
    h.record("README 列出全部五个第三方服务（giscus/Waline/Twikoo/Disqus/busuanzi）",
             not absent, f"缺少: {absent}" if absent else "齐全")

    # ④ 默认关闭
    h.record("README 说明这些服务默认关闭",
             "默认关闭" in readme or "默认均为 false" in readme
             or "enable = false" in readme,
             "已说明默认关闭")

    # ⓹ Release 全站审计表述一致性
    check_truth_wording(h)

    # ⑤b README 引用的本地图片必须真实存在
    # 背景：截图本轮从 .png 改为 .jpg 并重命名（如 03-post-dark → 05-post-dark），
    # 若只改一处引用就会得到 GitHub 上的破图 —— 静态检查应能立刻发现。
    # 注意：必须先剥掉 ``` 围栏代码块 —— 里面的 `![x](photo.png)` 是**示例文本**，
    # 不是真实引用（否则会误判为破图）。
    readme_prose = re.sub(r'```.*?```', '', readme, flags=re.S)
    readme_prose = re.sub(r'`[^`\n]*`', '', readme_prose)      # 行内 code
    refs = re.findall(r'!\[[^\]]*\]\((?!https?://)([^)\s]+)\)', readme_prose)
    pic_missing = [r for r in refs if not os.path.isfile(os.path.join(ROOT, r))]
    h.record("README 引用的本地图片全部存在（防破图）",
             not pic_missing and bool(refs),
             f"缺失: {pic_missing[:5]}" if pic_missing
             else f"{len(refs)} 个本地图片引用均可解析")

    # ⑤c README 必须覆盖本轮五个新功能分组
    # 用**标题行**匹配而非子串："功能五"在正文里还会以注释、章节名出现，
    # 子串匹配会让"删掉标题"这类注入静默通过（实测过：假守卫）。
    FEATURE_HEADINGS = [f"### 功能{n}" for n in ("一", "二", "三", "四", "五")]
    absent_groups = [g for g in FEATURE_HEADINGS if g not in readme]
    h.record("README 特性含功能一~五的独立小标题",
             not absent_groups, f"缺少: {absent_groups}" if absent_groups
             else "五个分组标题齐全")

    # ⑤d 新功能的配置必须出现在配置参考里
    # 同样按 **TOML 表头**（行首 `[params.x]`）匹配 —— 正文里提到配置名不算文档化。
    # 且必须在"完整配置参考"的代码块区间内，避免正文散落提及就蒙混过关。
    cfg_block = re.search(r'## 完整配置参考\s*```toml(.*?)```', readme, re.S)
    if not cfg_block:
        h.record("README 配置参考含新功能配置项", False, "找不到「完整配置参考」的 toml 代码块")
    else:
        cfg_body = cfg_block.group(1)
        REQUIRED_CONFIG_TABLES = ["[params.home]", "[params.reading]", "[params.appearance]",
                                 "[params.editUrl]", "[params.mermaid]", "[params.math]"]
        absent_keys = [k for k in REQUIRED_CONFIG_TABLES
                       if not re.search(r'^\s*' + re.escape(k) + r'\s*$',
                                        cfg_body, re.M)]
        h.record("README 配置参考含新功能配置表（TOML 表头级匹配）",
                 not absent_keys, f"缺少: {absent_keys}" if absent_keys
                 else f"{len(REQUIRED_CONFIG_TABLES)} 组配置表均在配置参考代码块内")

    # ⑤ CHANGELOG 存在且有当前版本
    # TEST-DEFECT-011：旧实现把默认版本硬编码为 1.0.7，不设 DOC_VERSION 时
    # 校验的是"两个版本之前"的条目 -> 本地/其它调用方必然假绿。
    # 现在按 DOC_VERSION -> git tag -> CHANGELOG 首个版本 依次推断，
    # 并额外与 docs/稳定基线.md 交叉核对，防止"漏更新文档"。
    chg = os.path.join(ROOT, "CHANGELOG.md")
    version, source = _resolve_version(chg)
    if os.path.isfile(chg):
        text = open(chg, encoding="utf-8").read()
        h.record(f"CHANGELOG 存在且含 v{version} 条目（版本来源：{source}）",
                 version in text, f"CHANGELOG.md 中查找 {version}")
        baseline = os.path.join(ROOT, "docs", "稳定基线.md")
        if os.path.isfile(baseline):
            btxt = open(baseline, encoding="utf-8").read()
            h.record(f"稳定基线文档记录的版本与 CHANGELOG 一致（v{version}）",
                     version in btxt,
                     f"{os.path.relpath(baseline, ROOT)} 中查找 {version}")
    else:
        h.record("CHANGELOG.md 存在", False, chg)

    # ⑥ 作者档案页配置口径（DOC-R3-005）
    check_author_pages_wording(h)


# ---------------------------------------------------------------------------
# DOC-R3-005：作者档案页两个独立开关的口径
#   params.authors.pages   只控制**主题**是否渲染作者资料结构
#   [taxonomies] authors   决定 Hugo 是否生成 /authors/ taxonomy 页面
# 旧文档把二者混为一谈（"pages=false 时 URL 结构与历史一致"），会让用户误以为
# pages=false 能关掉 /authors/ 页面 —— 实测（交接报告 §8.1）：已注册 taxonomy +
# pages=false 时 Hugo 照常生成 /authors/（291 页），页面数的开关是 taxonomy 注册。
# ---------------------------------------------------------------------------
AUTHOR_SECTION_HEADING = "### 作者档案页"
# README 作者档案页章节内必须出现的语义锚（章节级结构匹配，防正文散落蒙混）
AUTHOR_SECTION_ANCHORS = [
    "Hugo 是否生成 `/authors/` 页面",       # 三场景表的列头（结构级锚点）
    "主题是否渲染作者资料结构",             # 三场景表的列头
    "不会阻止",                             # pages=false 不阻止 taxonomy 页面生成
    "唯一方法是不注册",                     # 完全去掉 /authors/ 页面的唯一途径
]
# 禁止回归的过时表述（旧版"URL 行为对照"表把 pages=false 写成"无任何 /authors/"）
AUTHOR_STALE_PHRASES = [
    "| 默认（`pages` 未设 / `false`） | 无任何 `/authors/...` |",
    "不配置 / pages = false 时，主题**不输出任何作者档案相关结构**",
]
# exampleSite/hugo.toml 与 稳定基线 也必须带准确语义
AUTHOR_TOML_ANCHOR = "不会阻止"
AUTHOR_BASELINE_ANCHOR = "唯一方法是不注册"


def _extract_section(text, heading):
    """取 markdown 中 heading（### 级）到下一个同级标题之间的正文。"""
    i = text.find(heading)
    if i < 0:
        return None
    j = text.find("\n### ", i + len(heading))
    return text[i: j if j > 0 else len(text)]


def check_author_pages_wording(h):
    readme_p = os.path.join(ROOT, "README.md")
    readme = open(readme_p, encoding="utf-8").read()
    sec = _extract_section(readme, AUTHOR_SECTION_HEADING)
    h.record("README 存在「作者档案页」独立章节（### 级标题）", sec is not None,
             AUTHOR_SECTION_HEADING)
    if sec is None:
        return
    missing = [a for a in AUTHOR_SECTION_ANCHORS if a not in sec]
    h.record("README 作者档案页章节说明「pages 只控制资料结构渲染 / taxonomy 注册决定页面生成」",
             not missing, f"章节内缺少语义锚: {missing}" if missing else "三场景口径完整")
    stale = [ph for ph in AUTHOR_STALE_PHRASES if ph in readme]
    h.record("README 无「pages=false ⇒ 无 /authors/ 页面」类过时表述",
             not stale, f"过时表述: {stale[:1]}" if stale else "无过时表述")

    toml_p = os.path.join(ROOT, "exampleSite", "hugo.toml")
    if os.path.isfile(toml_p):
        toml = open(toml_p, encoding="utf-8").read()
        toml_stale = [ph for ph in AUTHOR_STALE_PHRASES if ph in toml]
        h.record("exampleSite/hugo.toml 注释含准确口径且无过时表述",
                 AUTHOR_TOML_ANCHOR in toml and not toml_stale,
                 ("缺少语义锚" if AUTHOR_TOML_ANCHOR not in toml else "")
                 + ("；过时表述残留" if toml_stale else "") or "口径准确")

    baseline_p = os.path.join(ROOT, "docs", "稳定基线.md")
    if os.path.isfile(baseline_p):
        baseline = open(baseline_p, encoding="utf-8").read()
        h.record("稳定基线.md 记录「不产生 /authors/ 页面的唯一方法是不注册 taxonomy」",
                 AUTHOR_BASELINE_ANCHOR in baseline, AUTHOR_BASELINE_ANCHOR)


def _resolve_version(changelog_path):
    """推断"当前版本"：DOC_VERSION 环境变量 -> git tag -> CHANGELOG 首个版本号。

    返回 (version, source)。避免硬编码（TEST-DEFECT-011）。
    """
    env = os.environ.get("DOC_VERSION")
    if env:
        return env, "DOC_VERSION 环境变量"
    try:
        import subprocess
        r = subprocess.run(["git", "describe", "--tags", "--abbrev=0"],
                           cwd=ROOT, capture_output=True, text=True, timeout=10)
        tag = (r.stdout or "").strip().lstrip("v")
        if r.returncode == 0 and re.fullmatch(r"\d+\.\d+\.\d+", tag or ""):
            return tag, f"git tag v{tag}"
    except Exception:
        pass
    if os.path.isfile(changelog_path):
        text = open(changelog_path, encoding="utf-8").read()
        m = re.search(r"^##\s*\[?(\d+\.\d+\.\d+)", text, re.M)
        if m:
            return m.group(1), "CHANGELOG 首个版本条目"
    return "0.0.0", "无法推断（将判失败）"


if __name__ == "__main__":
    main_h = Harness("docs")
    guard(main_h, run, main_h)
    main_h.finish()
