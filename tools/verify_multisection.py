#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""多 Section 完整回归：确认首页 / 搜索 / 归档 / 相关文章 / Series / RSS / sitemap / 分页
都遵循 params.content.sections，而不是写死 posts。

用法（CI 与本地一致）：
    python tools/verify_multisection.py
环境变量：
    SITE_DIR   站点目录（默认仓库自带 `exampleSite`；兼容旧的 `myblog` 布局）
    HUGO_ARGS  传给 hugo 的额外参数（用 exampleSite 时自动补 `--source . --themesDir ../..`）
    HUGO_BIN   hugo 可执行文件（默认 PATH 中的 hugo）
    KEEP_TMP=1 保留本次临时目录以便排查（默认不保留）

退出码约定（见 tools/_testlib.py）：任一断言失败 / 构建失败 -> exit 1。

临时产物（TEST-DEFECT-R2-004）：
    旧实现在**成功路径末尾**才删 `exampleSite/ms-verify.toml` 与 `tmp/multisec`，
    异常/中断路径全部残留，`tmp/multisec` 还会持续累积 `multi-<runid>` 目录。
    现在：配置覆盖文件与输出目录都放进 TempWorkspace 的唯一目录，并用
    try/finally 保证成功、失败、异常、中断都清理。
"""
import json
import os
import re
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _testlib import Harness, guard, TempWorkspace, fresh_dir  # noqa: E402

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

# 站点目录解析（BUG：旧默认指向仓库内 `myblog`，该目录早已移出仓库 ->
# 本地直接运行必然 FileNotFoundError，而 CI 因显式传 SITE_DIR 侥幸通过，
# 属于"只在 CI 里能跑"的隐性缺陷）。
# 现在：显式 SITE_DIR 优先；否则用仓库自带的 exampleSite；都不存在才回退 myblog
# （兼容仍按旧结构组织站点的使用者）。
def _resolve_site():
    env = os.environ.get("SITE_DIR")
    if env:
        return os.path.abspath(env)
    for cand in (os.path.join(ROOT, "exampleSite"),
                 os.path.join(ROOT, "myblog")):
        if os.path.isdir(cand):
            return os.path.abspath(cand)
    return os.path.abspath(os.path.join(ROOT, "exampleSite"))


SITE = _resolve_site()
HUGO = os.environ.get("HUGO_BIN", "hugo")
HUGO_ARGS = os.environ.get("HUGO_ARGS", "").split() if os.environ.get("HUGO_ARGS") else []
# 用仓库自带 exampleSite 时必须显式给出主题目录（它不通过 themes/ 子目录引用主题），
# 否则 `hugo` 会找不到主题而构建失败 —— 这正是 CI 里写死 HUGO_ARGS 的原因。
if not HUGO_ARGS and os.path.basename(SITE) == "exampleSite":
    HUGO_ARGS = ["--source", ".", "--themesDir", "../.."]
CONFIG_NAME = "ms-verify.toml"

SECTIONS = ["posts", "tutorials", "notes", "projects"]
# 各 section 的测试文章标题与正文唯一标记（由 tools/gen_testdata.py 生成）
MARKERS = {
    "tutorials": ("多 Section 教程", "TUTORIALSSECTION1"),
    "notes": ("多 Section 笔记", "NOTESSECTION1"),
    "projects": ("多 Section 项目", "PROJECTSSECTION1"),
}

H = Harness("multisection")


def build(out_dir, extra_config=None):
    args = [HUGO] + HUGO_ARGS + ["--gc", "--minify", "-d", out_dir]
    if extra_config:
        # --config 会替换默认配置，因此必须显式合并站点主配置
        args += ["--config", f"hugo.toml,{extra_config}"]
    p = subprocess.run(args, cwd=SITE, capture_output=True, text=True,
                       encoding="utf-8", errors="ignore")
    errs = [l for l in (p.stderr + p.stdout).splitlines()
            if l.strip().upper().startswith("ERROR")]
    # 真实退出码优先（与 TEST-DEFECT-R2-008 同类）：非零即构建失败
    if p.returncode != 0:
        tail = (p.stderr or p.stdout or "").strip().splitlines()[-3:]
        errs = [f"hugo 退出码 {p.returncode}"] + errs + tail
    return errs


def read(base, rel):
    p = os.path.join(base, rel)
    if not os.path.exists(p):
        return None
    return open(p, encoding="utf-8", errors="ignore").read()


def index_blob(base):
    """把搜索索引转成一个大字符串（兼容单索引数组与分片 {items,chunks} 结构）。"""
    raw = read(base, "index.json")
    if raw is None:
        return ""
    try:
        doc = json.loads(raw)
    except Exception:
        return raw
    return json.dumps(doc, ensure_ascii=False)


def _remove_with_retry(path, tries=6):
    """删除临时覆盖配置；Windows 上偶发文件锁（杀软 / 索引器）会瞬时占用。

    实测清理逻辑本身正确，但并发/连续运行时 `os.remove` 偶发被占用而抛 OSError。
    旧实现 `except OSError: pass` 会**静默**吞掉它并留下残骸（正是 TEST-DEFECT-R2-004
    "失败路径残留"要消除的现象）。这里短重试+`os.chmod` 兜底，仍失败则**显式告警**
    （不静默），便于发现真实的环境问题。
    """
    last = None
    for i in range(tries):
        try:
            os.remove(path)
            return True
        except FileNotFoundError:
            return True
        except OSError as e:
            last = e
            try:
                os.chmod(path, 0o666)
            except OSError:
                pass
            time.sleep(0.15 * (i + 1))
    print(f"[WARN] 临时配置未能清理，可能残留 {path}: {last}")
    return False


def _run_all():
    # 唯一临时工作区：输出目录都在这里，成功/失败/异常/中断都清理。
    # 配置覆盖必须放在 SITE 内（--config 路径相对 --source），而且**扩展名必须是
    # .toml** —— Hugo 按扩展名推断配置格式，`x.toml.<id>` 会直接报
    # "not a valid configuration format"。因此这里用带唯一 id 的 `_ms-verify-<id>.toml`，
    # 并在 finally 中删除（`.gitignore` 只作兜底，运行期清理才是关键）。
    with TempWorkspace("multisec") as ws:
        ws_id = ws.path_root.rsplit(os.sep, 1)[-1]
        cfg_name = f"_ms-verify-{ws_id}.toml"
        cfg_path = os.path.join(SITE, cfg_name)
        try:
            with open(cfg_path, "w", encoding="utf-8") as f:
                f.write('[params.content]\n'
                        '  sections = ["posts", "tutorials", "notes", "projects"]\n')
            _checks(ws, cfg_name)
        finally:
            _remove_with_retry(cfg_path)


def _checks(ws, cfg_name):
    # 每次从空目录开始，绝不复用上一次的构建产物
    multi = fresh_dir(ws.path("multi"), boundary=ws.path_root)
    default = fresh_dir(ws.path("default"), boundary=ws.path_root)

    errs = build(multi, extra_config=cfg_name)
    if errs:
        H.fatal_error("多 section 构建失败", errs[0][:160]); return
    errs = build(default)
    if errs:
        H.fatal_error("默认（posts）构建失败", errs[0][:160]); return

    # ---------------- 1. 首页 ----------------
    home = read(multi, "index.html") or ""
    home_default = read(default, "index.html") or ""

    # 首页**按设计**只展示最新 homePostCount(8) 篇并按日期排序。因此"每个 section 都必须
    # 出现在首页"是一个**错误断言**：它会随夹具日期先后偶发射穿（实测：projects 夹具
    # date 2026-09-27/28 较新而入选，tutorials 09-24 与 notes 09-26 被挤出最新窗口）。
    #
    # 正确的可证伪断言是校验首页的**数据源**是否跟随 `params.content.sections`：
    #   * 默认（sections=posts）：首页卡片**不得**越出 posts；
    #   * 多 section：首页卡片**必须**出现 posts 之外的配置 section
    #     （若模板把 posts 写死，此项立即变红），且不得越出配置集合。
    # 判据与夹具日期先后无关，只要 sections 配置被遵守即恒成立。
    def card_hrefs(html):
        out = []
        for c in re.findall(r'<article class=["\']?post-card.*?</article>', html, re.S):
            m = re.search(r'href=["\']?([^"\'> ]+)', c)
            if m:
                out.append(m.group(1))
        return out

    def section_of(href):
        if href.startswith(("http://", "https://", "//")):
            return None            # 外链文章没有站内 section
        m = re.match(r'^/([^/]+)/', href)
        return m.group(1) if m else None

    configured = set(SECTIONS)

    d_secs = {s for s in (section_of(h) for h in card_hrefs(home_default)) if s}
    H.record("[默认配置] 首页卡片只来自 posts（不泄漏其它 section）",
             d_secs <= {"posts"}, f"实际出现: {sorted(d_secs)}")

    m_secs = {s for s in (section_of(h) for h in card_hrefs(home)) if s}
    H.record("[多section] 首页出现 posts 之外的配置 section（数据源非写死 posts）",
             bool(m_secs - {"posts"}), f"实际出现: {sorted(m_secs)}")
    H.record("[多section] 首页卡片不越出配置的 sections",
             m_secs <= configured, f"实际出现: {sorted(m_secs)}")

    # 首页本身不翻页（设计如此：固定展示 homePostCount 篇 + "浏览更多"），
    # 因此这里验证：首页卡片数量符合配置、存在进入全量列表的入口、区块列表页分页可用。
    cards = len(re.findall(r'class=["\']?post-card', home))
    H.record("首页卡片数量符合 homePostCount(8)", cards == 8, f"{cards} 张")
    # TEST-DEFECT-010：旧断言 `'class="btn"' in home or "btn" in home` 里
    # 第二个条件几乎恒真（页面随便一处出现 "btn" 子串即通过）。改为匹配按钮元素本身。
    more_btn = re.search(r'class=["\']?[^"\'>]*\bbtn\b', home) is not None
    H.record("首页有「浏览更多」入口（匹配按钮元素本身）", more_btn,
             "匹配 class 含 btn 的元素" if more_btn else "未找到 .btn 元素")
    H.record("区块列表页分页第 2 页存在",
             os.path.exists(os.path.join(multi, "posts", "page", "2", "index.html")))

    # ---------------- 2. 搜索索引 ----------------
    blob = index_blob(multi)
    for sec, (title, marker) in MARKERS.items():
        H.record(f"搜索索引包含 {sec} 内容", marker in blob, marker)
    H.record("搜索索引包含 posts 内容", "应急响应" in blob or "FOXTROT10000" in blob)

    # ---------------- 3. 归档 ----------------
    arch = read(multi, "archives/index.html") or ""
    for sec, (title, marker) in MARKERS.items():
        H.record(f"归档包含 {sec} 的文章", title in arch, title)

    # ---------------- 4. RSS ----------------
    rss = read(multi, "index.xml") or ""
    for sec in MARKERS:
        H.record(f"RSS 包含 /{sec}/ 文章链接", f"/{sec}/zz-" in rss)

    # ---------------- 5. sitemap ----------------
    sm = read(multi, "sitemap.xml") or ""
    for sec in MARKERS:
        H.record(f"sitemap 包含 /{sec}/ 页面", f"/{sec}/" in sm)

    # ---------------- 6. Series（跨 section） ----------------
    proj = read(multi, "projects/zz-projects-1/index.html") or ""
    if not proj:
        H.record("projects 文章页存在", False, "projects/zz-projects-1")
    else:
        H.record("projects 文章页存在", True)
        H.record("Series 卡片渲染（跨 section）", "series-card" in proj)
        H.record("Series 进度显示", bool(re.search(r"第\s*1\s*篇", proj)) and "共" in proj)
        H.record("Series 下一篇链接", "series-next" in proj or "series-prev" in proj)

    # ---------------- 7. 相关文章（必须落在配置的 sections 内） ----------------
    tut = read(multi, "tutorials/zz-tutorials-1/index.html") or ""
    if not tut:
        H.record("tutorials 文章页存在", False, "tutorials/zz-tutorials-1")
    else:
        H.record("tutorials 文章页存在", True)
        # TEST-DEFECT-010：旧实现在找不到 related 容器时把 rel_html 退化为**整页**，
        # 于是"相关文章链接都在配置的 sections 内"变成对全页链接的检查，失去意义。
        # 现在容器不存在直接判失败。
        rel = re.search(r'class=["\']?related["\']?[^>]*>(.*?)</div>\s*</div>', tut, re.S)
        if not rel:
            H.record("相关文章容器存在（.related）", False, "未找到 .related 容器，无法验证其链接范围")
        else:
            H.record("相关文章容器存在（.related）", True)
            rel_html = rel.group(1)
            hrefs = re.findall(r'href=["\']?(/[^"\'> ]+)', rel_html)
            internal = [h for h in hrefs if not h.startswith("/img")]
            H.record("相关文章有内容", len(internal) > 0, f"{len(internal)} 条")
            outside = [h for h in internal
                       if not any(h.startswith(f"/{s}/") for s in SECTIONS)]
            H.record("相关文章链接都在配置的 sections 内", not outside, f"越界 {outside[:3]}")

    # ---------------- 8. 默认配置必须排除其它 section ----------------
    dhome = read(default, "index.html") or ""
    for sec, (title, marker) in MARKERS.items():
        H.record(f"[默认配置] 首页不含 {sec}", title not in dhome)
    dblob = index_blob(default)
    for sec, (title, marker) in MARKERS.items():
        H.record(f"[默认配置] 搜索索引不含 {sec}", marker not in dblob)
    darch = read(default, "archives/index.html") or ""
    for sec, (title, marker) in MARKERS.items():
        H.record(f"[默认配置] 归档不含 {sec}", title not in darch)
    drss = read(default, "index.xml") or ""
    for sec in MARKERS:
        H.record(f"[默认配置] RSS 不含 /{sec}/", f"/{sec}/zz-" not in drss)

    # ---------------- 9. 源码不得硬编码 Section "posts" ----------------
    # TEST-DEFECT-005：旧实现的两个候选路径（SITE/themes/... 与 ROOT/hugo-theme-nebula/layouts）
    # 在仓库与 CI 里都不存在，os.walk 空转 -> hits 恒为空 -> 断言恒真。
    # 现在必须真的扫到布局文件，否则判致命错误（不允许空转）。
    candidates = [
        os.path.join(SITE, "themes", "hugo-theme-nebula", "layouts"),  # myblog 站点
        os.path.join(ROOT, "layouts"),                                # 主题仓库自身
        os.path.join(os.path.dirname(ROOT), "hugo-theme-nebula", "layouts"),  # exampleSite/themesDir
    ]
    theme_layouts = next((c for c in candidates if os.path.isdir(c)), None)
    if not theme_layouts:
        H.fatal_error("找不到主题 layouts 目录（源码扫描会空转，断言将恒真）",
                      "; ".join(candidates))
    else:
        hits = []
        scanned = 0
        for dirpath, _, files in os.walk(theme_layouts):
            for f in files:
                if not f.endswith((".html", ".xml", ".json")):
                    continue
                scanned += 1
                p = os.path.join(dirpath, f)
                for i, ln in enumerate(open(p, encoding="utf-8", errors="ignore").read().split("\n"), 1):
                    if re.search(r'\(\s*where[^\n]*"Section"\s+"posts"\s*\)', ln) or \
                       re.search(r'"Section"\s+"posts"', ln):
                        hits.append(f"{os.path.relpath(p, theme_layouts)}:{i}")
        if scanned == 0:
            H.fatal_error("layouts 目录下没有可扫描的模板文件", theme_layouts)
        else:
            H.record(f"模板中无硬编码 Section \"posts\"（仅允许 default 回退）",
                     not hits, f"{hits[:4]}" if hits else
                     f"扫描 {scanned} 个模板文件，无硬编码")


def main():
    guard(H, _run_all)
    H.finish()


if __name__ == "__main__":
    main()
