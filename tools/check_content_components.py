#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""功能三验收：技术内容组件。

当前覆盖 **Markdown 提示块（GitHub Alerts 风格）**；标签页/步骤/文件树/徽标/
画廊/可选 Mermaid+KaTeX 会陆续并入本脚本的后续小节。

断言的都是**直接证明真实行为**的东西，不是"脚本没报错"：

A. 构建产物（真实 Hugo 构建 + 解析 HTML / CSS）
   A1 五种已知类型各自生成提示块，class 与类型一一对应；
   A2 五种图标**互不相同**（防"复制 note 图标"这类静默退化）；
   A3 默认标题走 i18n：中文站中文、英文站英文；
   A4 自定义标题（[!WARNING] 标题）优先于 i18n 默认；
   A5 未知类型（[!BOGUS]）**不**生成提示块，也不让构建失败；
   A6 **普通引用逐字节不变**：与"同一主题去掉本钩子"的构建产物做全站 diff=0；
   A7 CSS 提示块样式齐全，且复用设计变量（暗色模式无需第二套颜色）；
   A8 零 JS：产物中提示块不含 <script>；不引用任何第三方域名。

B. 多语言 / 版本矩阵
   B1 简体中文、繁體中文、English 三种站点语言的默认标题正确；
   B2 Hugo 0.128.0 优雅退化（无 md-alert、构建成功、marker 行可见）；
   B3 Hugo 0.148.0 / 0.162.0 / 0.166.0 / 0.167.0 均正常生成。

用法：
    python tools/check_content_components.py
环境变量：
    HUGO_BIN   Hugo 可执行文件（默认 hugo，用于"当前版本"相关断言）
"""

import difflib
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
THEMES_DIR = os.path.dirname(REPO)
HUGO = os.environ.get("HUGO_BIN", "hugo")
OUT_ROOT = os.path.join(REPO, "tmp")
# Hugo 版本矩阵目录：默认指向工作区内的验收环境（可用 HUGO_MATRIX_DIR 覆盖）。
# 找不到时**不是**致命错误，而是跳过 B2/B3 并在汇总里说明（CI 里由 compat_matrix 覆盖）。
HUGO_ROOT = os.environ.get(
    "HUGO_MATRIX_DIR",
    os.path.join(os.path.dirname(os.path.dirname(REPO)),
                 "tmp", "hugo博客主题验收测试", "r2", "_env", "hugo"))

ZERO_TMPL = """baseURL = 'https://z.example/'
title = 'cc probe'
theme = 'hugo-theme-nebula'
defaultContentLanguage = 'zh-cn'
disableKinds = ['taxonomy', 'term', 'RSS', 'sitemap', 'robotsTXT', '404', 'section']

[languages]
  [languages.zh-cn]
    weight = 1
    contentDir = 'content'
  [languages.en]
    weight = 2
    contentDir = 'content-en'
  [languages.zh-TW]
    weight = 3
    contentDir = 'content-zh-tw'
"""

# 探针正文：覆盖 5 种类型 + 自定义标题 + 未知类型 + 普通引用 + 嵌套
PROBE_MD = """---
title: "CC Probe"
date: 2024-05-06
draft: false
---

> 普通单段引用

尾随段落 A

> 普通多段一
>
> 普通多段二

> [!NOTE]
> 说明正文

> [!TIP]
> 提示正文

> [!IMPORTANT]
> 重要正文

> [!WARNING]
> 警告正文

> [!CAUTION]
> 注意正文

> [!WARNING] 自定义标题
> 自定义正文

> [!BOGUS]
> 未知类型正文

> 末尾引用
"""

HUGO_VERSIONS = ("0.128.0", "0.148.0", "0.162.0", "0.166.0", "0.167.0")
# 可执行文件名随平台变化：Windows 是 hugo.exe，CI（Linux）是 hugo。
HUGO_EXE = "hugo.exe" if os.name == "nt" else "hugo"


def hugo_matrix():
    """返回 {版本: 可执行文件路径}；目录不存在则返回空 dict（由调用方判为致命错误）。"""
    got = {}
    if not os.path.isdir(HUGO_ROOT):
        return got
    for v in HUGO_VERSIONS:
        exe = os.path.join(HUGO_ROOT, v, HUGO_EXE)
        if os.path.isfile(exe):
            got[v] = exe
    return got


KNOWN = ["note", "tip", "important", "warning", "caution"]
H = Harness("content_components")


# --------------------------------------------------------------------------- #
# 工具
# --------------------------------------------------------------------------- #
def build_probe(tag, lang=None, extra_toml="", hugo=HUGO):
    """在 tmp 下搭一个最小站点（不写 exampleSite），返回 (out_dir, log, rc)。

    为什么要最小站点而不是直接用 exampleSite：
      * 提示块的断言需要**可控的正文**（精确含 5 种类型 + 未知类型 + 普通引用）；
      * 最小站点只有 1 个页面，diff 的对象唯一，字节比较不会被无关差异干扰；
      * 不往 exampleSite 写任何探针文件（§11 要求临时文件必须清理）。
    """
    root = os.path.join(OUT_ROOT, f"_cc_{tag}")
    safe_rmtree(root)
    for d in ("content", "content-en", "content-zh-tw"):
        os.makedirs(os.path.join(root, d), exist_ok=True)
    with io.open(os.path.join(root, "hugo.toml"), "w", encoding="utf-8") as f:
        f.write(ZERO_TMPL + extra_toml)
    for d in ("content", "content-en", "content-zh-tw"):
        with io.open(os.path.join(root, d, "p1.md"), "w", encoding="utf-8") as f:
            f.write(PROBE_MD)
    out = os.path.join(root, "public")
    # themesDir 直接用**真实的主题父目录**（与 exampleSite 的 `--themesDir ../..` 等价）。
    # 不要用符号链接/junction 造 themes/ 目录：Hugo 0.128.0 / 0.148.0 不解析符号链接，
    # 会报 `module "hugo-theme-nebula" not found`（0.162+ 才跟随）。真实路径在五个
    # 版本上行为一致，也更贴近 exampleSite 的实际用法。
    cmd = [hugo, "--source", root, "--themesDir", THEMES_DIR, "--gc", "-d", out,
           "--cleanDestinationDir"]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                       errors="ignore", timeout=300)
    return out, (r.stdout or "") + (r.stderr or ""), r.returncode


def read(p):
    if not os.path.isfile(p):
        return None
    return io.open(p, encoding="utf-8").read()


def page(out, rel="p1/index.html"):
    return read(os.path.join(out, *rel.split("/")))


def alerts(html):
    """解析出 [(type, block_html)]，只匹配提示块。"""
    if not html:
        return []
    return re.findall(
        r'<blockquote class="md-alert md-alert-(\w+)">(.*?)</blockquote>', html, re.S)


def icons(html):
    """每种类型的 svg 内部路径（用于比对图标是否各不相同）。"""
    got = {}
    for t, body in alerts(html):
        m = re.search(r"<svg[^>]*>(.*?)</svg>", body, re.S)
        got.setdefault(t, []).append(m.group(1).strip() if m else "")
    return got


def title_of(body):
    m = re.search(r'class="md-alert-title">(.*?)</span>', body)
    return m.group(1).strip() if m else None


def css_text(out):
    d = os.path.join(out, "css")
    if not os.path.isdir(d):
        return ""
    for n in sorted(os.listdir(d)):
        if n.startswith("main") and n.endswith(".css"):
            return read(os.path.join(d, n)) or ""
    return ""


# --------------------------------------------------------------------------- #
# A. 构建产物断言
# --------------------------------------------------------------------------- #
def run_checks():
    out, log, rc = build_probe("main", hugo=HUGO)
    if rc != 0:
        H.fatal_error("探针站点构建失败", log[-800:])
        return None
    html = page(out)
    if html is None:
        H.fatal_error("探针页面未生成", out)
        return None

    blocks = alerts(html)
    got_types = [t for t, _ in blocks]

    # ---------- A1 五种类型 ----------
    # warning 在探针里出现两次：一次默认标题、一次自定义标题，二者都要验证。
    expect = {"note": 1, "tip": 1, "important": 1, "warning": 2, "caution": 1}
    for t in KNOWN:
        n = got_types.count(t)
        H.record(f"A1 [!{t.upper()}] 生成提示块且数量正确", n == expect[t],
                 f"count={n} expected={expect[t]}")
    H.record("A1 提示块总数 = 6（5 种类型 + 1 个自定义标题）",
             len(blocks) == 6, f"total={len(blocks)} types={got_types}")
    H.record("A1 class 命名空间为 md-alert md-alert-<type>（语义标记）",
             all(re.search(rf'<blockquote class="md-alert md-alert-{t}">', html) for t in KNOWN),
             "")

    # ---------- A2 图标互不相同（防静默退化成同一个图标） ----------
    ic = icons(html)
    first = {t: (ic.get(t) or [""])[0] for t in KNOWN}
    uniq = set(first.values())
    H.record("A2 五种类型的图标**互不相同**（不是复制同一个图标）",
             len(uniq) == 5 and all(first[t] for t in KNOWN),
             f"unique={len(uniq)} sizes={{{', '.join(f'{k}:{len(v)}' for k, v in first.items())}}}")
    H.record("A2 图标是内联 SVG（无外部图标字体/CDN 请求）",
             html.count("<svg viewBox=\"0 0 24 24\"") >= 5, "")
    H.record("A2 图标标记 aria-hidden（装饰性，不干扰读屏）",
             all('aria-hidden="true"' in body for _, body in blocks), "")

    # ---------- A3 默认标题走 i18n（中文站） ----------
    # 取"每种类型里**没有**自定义标题（即 .AlertTitle 为空）"的那一个块
    zh = {}
    for t, b in blocks:
        if t in KNOWN and title_of(b) in ("说明", "提示", "重要", "警告", "注意",
                                          "Note", "Tip", "Important", "Warning", "Caution"):
            zh[t] = title_of(b)
    H.record("A3 中文站默认标题为中文（说明/提示/重要/警告/注意）",
             zh == {"note": "说明", "tip": "提示", "important": "重要",
                    "warning": "警告", "caution": "注意"}, f"{zh}")

    # ---------- A4 自定义标题优先 ----------
    custom = [b for t, b in blocks if t == "warning"]
    titles = [title_of(b) for b in custom]
    H.record("A4 自定义标题（[!WARNING] 自定义标题）覆盖 i18n 默认",
             "自定义标题" in titles, f"{titles}")
    H.record("A4 自定义标题不改变类型与图标（仍是 warning）",
             any(title_of(b) == "自定义标题" and first["warning"] in b for _, b in blocks), "")

    # ---------- A5 未知类型不生成提示块 ----------
    H.record("A5 未知类型 [!BOGUS] **不**生成提示块",
             "md-alert-bogus" not in html and "bogus" not in got_types, f"{got_types}")
    H.record("A5 未知类型仍按普通引用渲染（正文保留）",
             "未知类型正文" in html, "")
    H.record("A5 构建成功（未知类型不让构建失败）", rc == 0, f"rc={rc}")

    # ---------- A6 普通引用逐字节不变 ----------
    # 方法：同一主题，唯一差异 = 是否存在 render-blockquote.html。
    # 用 git archive 取 HEAD 版本做"无钩子"对照组，并同步工作区的 CSS/i18n
    # （CSS/i18n 与钩子无关，必须一致，否则 diff 会因配色差异而误报）。
    nohook, log_nh, rc_nh = build_nohook_copy()
    H.record("A6 对照组（无钩子）构建成功", rc_nh == 0, f"rc={rc_nh}")
    if nohook:
        h2 = page(nohook)
        # 只比较正文块之前与之后的内容：
        #   * 正文块**内**必然不同（提示块取代了普通引用），这是本功能的定义；
        #   * 但正文块**外**必须逐字节一致（含阅读统计之外的全部外壳）。
        # 注意：阅读统计的"字数"会变（Hugo 的 .WordCount 连同 `[!NOTE]` 标记一起计数），
        # 这属于**预期差异**，因此把统计区一并排除，避免把正确行为误判为回归。
        def outside(s_html):
            if not s_html:
                return ""
            m = re.search(r'<div class="post-content[^"]*"[^>]*>(.*?)</div>\s*</article>',
                          s_html, re.S)
            core = m.group(1) if m else s_html
            stripped = s_html.replace(core, "\x00CORE\x00")
            stripped = re.sub(r'<span class="stat">.*?</span>', "", stripped, flags=re.S)
            return stripped
        a, b = outside(h2), outside(html)
        same = bool(a) and a == b
        if not same:
            d = list(difflib.unified_diff(a.splitlines(), b.splitlines(),
                                          "nohook", "withhook", lineterm=""))
            H.record("A6 正文块之外的内容逐字节不变（空壳/元信息/导航/页脚 diff=0）",
                     False, ("diff: " + " | ".join(d[2:14]))[:600])
        else:
            H.record("A6 正文块之外的内容逐字节不变（空壳/元信息/导航/页脚 diff=0）", True, "")
        # 再单独证明：**真正的普通引用**（正文里没有任何 `[!X]` 标记）的 HTML 片段一致。
        # 排除两类：
        #   * `[!NOTE]` 等已知类型 -> 本就被替换成提示块；
        #   * `[!BOGUS]` 未知类型   -> Hugo 内建的 alert 解析器仍会**吞掉 marker 行**
        #     （实测 0.148~0.167 一致，与模板无关），因此片段文本必然不同，属预期。
        def quotes(h):
            return re.findall(r"<blockquote>\n(.*?)</blockquote>", h or "", re.S)

        with_plain = quotes(html)                                    # 全部非 alert 块
        nohook_plain = [x for x in quotes(h2) if "[!" not in x]      # 对照组里真·普通引用
        # 对照组里带 marker 的块（[!NOTE] 等）在 withhook 里已被提示块取代，不参与比较。
        missing = [x for x in nohook_plain if x not in with_plain]
        H.record("A6 对照组中的真·普通引用全部原样保留（逐字节一致）",
                 bool(nohook_plain) and not missing,
                 f"nohook={len(nohook_plain)} missing={len(missing)}")
        # withhook 相对对照组"多出来"的普通引用块，只应是 [!BOGUS] 的正文：
        # Hugo 内建的 alert 解析器会吞掉未知类型的 marker 行（实测 0.148~0.167 一致，
        # 与模板无关；无钩子时该 marker 会被当普通文本保留，故两边必然差这一处）。
        extra = [x for x in with_plain if x not in nohook_plain]
        H.record("A6 唯一多出的普通引用块是 [!BOGUS] 的正文（Hugo 内建解析吞 marker，非本模板行为）",
                 len(extra) == 1 and "未知类型正文" in extra[0],
                 f"extra={[e.strip()[:40] for e in extra]}")
    else:
        H.record("A6 对照组构建产物缺失", False, "")

    # ---------- A7 CSS ----------
    css = css_text(out)
    H.record("A7 存在 .md-alert 基础样式", ".md-alert" in css, "")
    H.record("A7 五种类型各有独立配色规则",
             all(f".md-alert-{t}" in css for t in KNOWN), "")
    H.record("A7 复用设计变量（--brand / --brand-soft），暗色无需第二套颜色",
             "var(--brand)" in css and "var(--brand-soft)" in css, "")
    H.record("A7 有暗色主题下的图标色修正（深底可读）",
             'html[data-theme="dark"] .md-alert-' in css
             or "html[data-theme=dark] .md-alert-" in css, "")
    H.record("A7 提示块内代码块不横向溢出", ".md-alert pre" in css, "")
    # --minify 会去掉选择器里的空格（`.md-alert-body > *:first-child` ->
    # `.md-alert-body>*:first-child`），必须归一后再断言，否则假红。
    css_norm = css.replace(" > ", ">").replace("> ", ">").replace(" >", ">")
    H.record("A7 提示块首尾子元素去掉多余外边距",
             ".md-alert-body>*:first-child" in css_norm
             and ".md-alert-body>*:last-child" in css_norm, "")
    H.record("A7 打印样式未破坏提示块（@media print 内不含 .md-alert 隐藏规则）",
             not re.search(r"@media print[^@]*\.md-alert\s*\{[^}]*display:\s*none", css, re.S),
             "")

    # ---------- A8 零 JS / 无第三方请求 ----------
    H.record("A8 提示块 HTML 内不含 script（纯 CSS 实现）",
             all("<script" not in b for _, b in blocks), "")
    # 排除页面自身的 canonical / og:url / 语言切换链接（它们是站内地址，不是外部请求）。
    # 只有 <script src> / <link href> / <img src> 这类会真正发起网络请求的才是"外部依赖"。
    ext = re.findall(r'<(?:script|link|img|iframe)[^>]*(?:src|href)="(https?://[^"]+)"', html)
    ext = [u for u in ext if not u.startswith("https://z.example/")]
    H.record("A8 页面不含任何第三方 http(s) 资源（无 CDN 依赖）", not ext, f"{ext[:3]}")

    return {"out": out, "html": html}


def build_nohook_copy():
    """构造"无 render-blockquote.html"的同源主题副本并构建。

    唯一差异是那个钩子文件；CSS 与 i18n 从工作区同步（它们与钩子无关）。
    """
    d = os.path.join(OUT_ROOT, "_cc_nohook")
    safe_rmtree(d)
    os.makedirs(d, exist_ok=True)
    r = subprocess.run(["git", "archive", "HEAD"], cwd=REPO,
                       capture_output=True, timeout=120)
    if r.returncode != 0:
        return None, "git archive failed", 1
    import tarfile
    with tarfile.open(fileobj=io.BytesIO(r.stdout)) as tf:
        tf.extractall(d)
    # 同步工作区未提交的 CSS / i18n（保证唯一差异是钩子）
    for rel in ("assets/css/main.css", "i18n/en.yaml", "i18n/zh-CN.yaml", "i18n/zh-TW.yaml"):
        src = os.path.join(REPO, rel)
        dst = os.path.join(d, rel)
        if os.path.isfile(src):
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(src, dst)
    # 确保本副本**没有**钩子文件
    hook = os.path.join(d, "layouts/_default/_markup/render-blockquote.html")
    if os.path.exists(hook):
        os.remove(hook)

    # 用同样的探针站点构建（主题换成这个副本）
    root = os.path.join(OUT_ROOT, "_cc_nohook_site")
    safe_rmtree(root)
    for dd in ("content", "content-en", "content-zh-tw"):
        os.makedirs(os.path.join(root, dd), exist_ok=True)
    with io.open(os.path.join(root, "hugo.toml"), "w", encoding="utf-8") as f:
        f.write(ZERO_TMPL)
    for dd in ("content", "content-en", "content-zh-tw"):
        with io.open(os.path.join(root, dd, "p1.md"), "w", encoding="utf-8") as f:
            f.write(PROBE_MD)
    # 把"无钩子"副本放到一个**真实**的 themesDir 下，目录名必须叫 hugo-theme-nebula。
    # 同样不用 symlink（0.128/0.148 不解析）。
    holder = os.path.join(OUT_ROOT, "_cc_nohook_themes")
    safe_rmtree(holder)
    os.makedirs(holder, exist_ok=True)
    themedir = os.path.join(holder, "hugo-theme-nebula")
    shutil.move(d, themedir)
    out = os.path.join(root, "public")
    r2 = subprocess.run([HUGO, "--source", root, "--themesDir", holder, "--gc", "-d", out,
                         "--cleanDestinationDir"], capture_output=True, text=True,
                        encoding="utf-8", errors="ignore", timeout=300)
    return out, (r2.stdout or "") + (r2.stderr or ""), r2.returncode


# --------------------------------------------------------------------------- #
# B. 多语言 / 版本矩阵
# --------------------------------------------------------------------------- #
def run_lang_checks(main):
    """三种站点语言的默认标题必须来自 i18n（第六节：支持三语言）。

    用一个真实多语言站点构建（zh-cn 在根、en 在 /en/、zh-TW 在 /zh-tw/），
    逐个语言断言 .md-alert-title 的文案，证明标题**真的**跟随内容语言，
    而不是硬编码或回退到英文。
    """
    out = main["out"]
    EXPECT = {
        "":      ("zh-cn", ("说明", "提示", "重要", "警告", "注意")),
        "en":    ("en",    ("Note", "Tip", "Important", "Warning", "Caution")),
        "zh-tw": ("zh-TW", ("說明", "提示", "重要", "警告", "注意")),
    }
    ORDER = ["note", "tip", "important", "warning", "caution"]
    for sub, (lang, defaults) in EXPECT.items():
        rel = "p1/index.html" if not sub else f"{sub}/p1/index.html"
        html = page(out, rel)
        if not html:
            H.record(f"B1 语言 {lang}：页面存在", False, rel)
            continue
        got = {}
        for k, b in alerts(html):
            if k in KNOWN and title_of(b) in defaults:
                got[k] = title_of(b)
        want = dict(zip(ORDER, defaults))
        H.record(f"B1 语言 {lang}：五种默认标题正确来自 i18n", got == want,
                 f"got={got}")
        H.record(f"B1 语言 {lang}：自定义标题原样保留（不被 i18n 覆盖）",
                 "自定义标题" in html, "")


def run_hugo_matrix():
    """五种 Hugo 版本的提示块行为（0.128.0 必须优雅退化）。"""
    ver_dirs = hugo_matrix()
    if not ver_dirs:
        H.fatal_error("未找到 Hugo 版本矩阵目录", HUGO_ROOT)
        return

    for v, exe in sorted(ver_dirs.items()):
        out, log, rc = build_probe(f"v{v}", hugo=exe)
        if rc != 0:
            H.record(f"B2/B3 Hugo {v} 构建成功", False, log[-300:])
            continue
        html = page(out) or ""
        n = len(alerts(html))
        if v == "0.128.0":
            H.record("B2 Hugo 0.128.0 构建成功（钩子被静默忽略，不报错）", rc == 0, "")
            H.record("B2 Hugo 0.128.0 不生成提示块（优雅退化）", n == 0, f"alerts={n}")
            H.record("B2 Hugo 0.128.0 marker 行仍可见（退化为普通引用，内容不丢）",
                     "[!NOTE]" in html and "说明正文" in html, "")
            H.record("B2 Hugo 0.128.0 普通引用输出正常",
                     html.count("<blockquote>") >= 3, f"count={html.count('<blockquote>')}")
        else:
            H.record(f"B3 Hugo {v} 生成 6 个提示块", n == 6, f"alerts={n}")
            t = {k: title_of(b) for k, b in alerts(html) if k in KNOWN}
            H.record(f"B3 Hugo {v} 中文默认标题正确",
                     t.get("note") == "说明" and t.get("caution") == "注意", f"{t}")
            H.record(f"B3 Hugo {v} 未知类型未生成提示块", "md-alert-bogus" not in html, "")
            ic = icons(html)
            H.record(f"B3 Hugo {v} 五种图标互不相同",
                     len({(ic.get(k) or [''])[0] for k in KNOWN}) == 5, "")



# --------------------------------------------------------------------------- #
# C. 跨版本回归：多语言站点的 alias 空值防御
# --------------------------------------------------------------------------- #
def run_alias_defense():
    """回归：多语言站点的默认语言 alias 页在 `.Page` 为 nil 时**不得中断构建**。

    这是在本功能的版本矩阵验证中**发现的主题既有缺陷**（与提示块无关）：
    Hugo 会为默认语言额外生成一个 `/<defaultContentLanguage>/` 重定向页，
    该页**不附带目标 Page 对象**。`layouts/alias.html` 原来的
    `{{ .Page.Title | default .Permalink }}` 会以

        execute of template failed: alias.html: at <.Page.Title>:
        nil pointer evaluating page.Page.Title

    中断**整个构建**。实测 0.128.0 / 0.148.0 / 0.162.0 崩溃，
    0.166.0 / 0.167.0 不复现（Hugo 后来改成跳过这类 alias）。
    主题最低版本是 0.128.0，因此必须自行防御。

    反证：把 alias.html 的防御改回 `.Page.Title`，本小节的断言必须变红——
    已实测确认（见交付报告）。
    """
    ver_dirs = hugo_matrix()
    if not ver_dirs:
        H.fatal_error("未找到 Hugo 版本矩阵目录（alias 回归）", HUGO_ROOT)
        return

    for v, exe in sorted(ver_dirs.items()):
        out, log, rc = build_probe(f"alias_v{v}", hugo=exe)
        ok = rc == 0
        H.record(f"C Hugo {v}：多语言站点构建成功（alias 空值不再中断构建）",
                 ok, "" if ok else log[-260:])
        if not ok:
            continue
        alias = read(os.path.join(out, "zh-cn", "index.html"))
        H.record(f"C Hugo {v}：默认语言 alias 页存在", alias is not None, "")
        if alias is None:
            continue
        title = re.search(r"<title>(.*?)</title>", alias, re.S)
        H.record(f"C Hugo {v}：alias 页 title 非空（无 nil 崩溃痕迹）",
                 bool(title and title.group(1).strip()), repr(title.group(1) if title else None))
        # alias 页的既有约定必须保持：canonical + meta refresh + 无脚本
        H.record(f"C Hugo {v}：alias 页仍有 canonical",
                 'rel="canonical"' in alias, "")
        H.record(f"C Hugo {v}：alias 页仍有 meta refresh 且目标非空",
                 bool(re.search(r'http-equiv="refresh"\s+content="([^"]*url=([^"]+))"', alias))
                 or bool(re.search(r'content="0;\s*url=([^"]+)"', alias)), "")
        H.record(f"C Hugo {v}：alias 页仍不含任何 script",
                 "<script" not in alias, "")


# --------------------------------------------------------------------------- #
def main():
    main_out = guard(H, run_checks)
    if main_out:
        guard(H, run_lang_checks, main_out)
        guard(H, run_hugo_matrix)
        guard(H, run_alias_defense)
        guard(H, run_alias_defense)
    H.finish()


if __name__ == "__main__":
    main()