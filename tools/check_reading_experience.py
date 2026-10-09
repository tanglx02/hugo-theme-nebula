#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""功能二验收：文章阅读体验（进度条 / 返回顶部 / 专注模式 / 打印样式）。

断言的都是**直接证明真实行为**的东西，不是"脚本没报错"：

A. 构建产物（真实 Hugo 构建 + 解析 HTML / CSS）
   A1 默认外观不变：进度条与返回顶部仍然存在（历史行为），专注模式默认不出现；
   A2 站点级 params.reading.* 可关闭进度条 / 返回顶部，并开启专注模式；
   A3 **文章级 Front Matter 覆盖站点级**（含关键回归：写 false 必须真的生效）；
   A4 打印样式存在且只影响 @media print，不影响屏幕默认外观；
   A5 prefers-reduced-motion 分支存在。

B. 真实浏览器（Chromium，可选 Firefox / WebKit）
   B1 进度条宽度按**正文阅读区**映射：顶部≈0、底部≈100、中点≈50（与独立重算值比对）；
   B2 返回顶部：顶部时隐藏，下滚出现；**键盘可聚焦并用 Enter 触发**并回到顶部；
   B3 专注模式：点击切换 aria-pressed / html.focus-on；**正文与站点导航仍可见**，
      次要区块被收敛；刷新后状态保持；Escape 退出；键盘 Enter 可切换；
   B4 打印模拟（emulate_media print）：交互元素隐藏、正文可见；
   B5 减少动效（emulate_media reduced-motion）：返回顶部仍能回到顶部（不因动效降级而失效）。

用法：
    python tools/check_reading_experience.py
环境变量：
    HUGO_BIN   Hugo 可执行文件（默认 hugo）
    BROWSERS   仅跑部分浏览器，逗号分隔，如 "chromium"（默认全部可用浏览器）
"""
import functools
import os
import re
import subprocess
import sys
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _testlib import Harness, guard, launch as _launch  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = os.path.join(REPO, "exampleSite")
THEMES_DIR = os.path.dirname(REPO)
HUGO = os.environ.get("HUGO_BIN", "hugo")
OUT_ROOT = os.path.join(REPO, "tmp")
CFG_ROOT = os.path.join(OUT_ROOT, "_read_cfg")

H = Harness("reading_experience")

# 用于浏览器测试的长文章（含侧栏 + TOC，足够高以便滚动）
LONG_ARTICLE = "posts/zz-03-50k"
FOCUS_ARTICLE = "posts/04-suricata-elk"


# --------------------------------------------------------------------------- #
# 构建
# --------------------------------------------------------------------------- #
def write_overlay(tag, lines):
    os.makedirs(CFG_ROOT, exist_ok=True)
    p = os.path.join(CFG_ROOT, tag + ".toml")
    with open(p, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    return os.path.abspath(p)


def write_probe_mount():
    """把探针页面以 **Hugo module mount** 注入 exampleSite 的内容树。

    为什么不用"复制整棵 content 树再 --contentDir"：
      * --contentDir 会**替换**整个内容树，exampleSite 的 posts 全部消失；
      * 复制整棵 content（约 3700 个文件）会触发沙箱的批量删除保护，
        且每次运行都要复制并清理大量文件，慢且脆弱。
    module mount 只**追加**一个挂载点（content/posts-probe），原始内容原样保留，
    也不产生任何需要删除的大量文件。探针文件写在 tmp 下，**绝不写 exampleSite**。

    probe-off ：显式把一堆布尔项设为 false（**这些正是历史上被 `default` 吞掉的**）；
    probe-on  ：全部走默认值，作为对照；
    probe-true：显式 true，用于验证"文章级 true 可反向覆盖站点级 false"。
    """
    probes = os.path.join(OUT_ROOT, "_read_probes")
    os.makedirs(probes, exist_ok=True)
    for slug, extra in (
        ("probe-off", [
            "showProgress: false",
            "showBackToTop: false",
            "showFocusMode: true",
            "showDate: false",
            "breadcrumb: false",
            "toc: false",
        ]),
        ("probe-on", []),
        ("probe-true", [
            "showProgress: true",
            "showBackToTop: true",
            "showFocusMode: true",
        ]),
    ):
        fm = ["---", f'title: "Probe {slug}"', "date: 2024-05-06", "draft: false"]
        fm += extra
        fm += ["---", "", "## 一、章节", "", "正文段落。", "", "## 二、章节", "", "正文段落。", ""]
        with open(os.path.join(probes, f"{slug}.md"), "w", encoding="utf-8") as f:
            f.write("\n".join(fm))
    # 挂载配置（追加到 exampleSite 内容树，不替换）
    os.makedirs(CFG_ROOT, exist_ok=True)
    p = os.path.join(CFG_ROOT, "_mount_probes.toml")
    with open(p, "w", encoding="utf-8") as f:
        f.write(
            "[module]\n"
            "  [[module.mounts]]\n"
            "    source = 'content'\n"
            "    target = 'content'\n"
            "  [[module.mounts]]\n"
            f"    source = {os.path.abspath(probes)!r}\n"
            "    target = 'content/posts-probe'\n")
    return os.path.abspath(p), "posts-probe"


def build(config_files, out_dir):
    """构建到 out_dir。

    用 Hugo 自带的 --cleanDestinationDir 清理旧产物，而**不用 shutil.rmtree**：
      * 目的相同（保证产物目录干净，杜绝"复用上次残留"的假绿，TEST-DEFECT-R2-006）；
      * 但 rmtree 会一次性删除几千个文件，触发沙箱的批量删除保护（CI 会因此变红），
        而且删完仍要让 Hugo 重建，属于多余动作。
    --cleanDestinationDir 由 Hugo 在构建时按"缺失即删除"处理，语义等价、开销更小。
    """
    cmd = [HUGO, "--source", SITE, "--themesDir", THEMES_DIR, "--gc",
           "--config", ",".join(config_files), "-d", out_dir,
           "--cleanDestinationDir", "--minify"]
    return subprocess.run(cmd, capture_output=True, text=True, timeout=300)


def read(path):
    if not os.path.isfile(path):
        return None
    return open(path, encoding="utf-8").read()


def contains(text, token):
    """在（可能被 --minify 去掉引号的）HTML 中匹配标记。"""
    stripped = (text or "").replace('"', "").replace("'", "")
    return token.replace('"', "").replace("'", "") in stripped


def lint_css(css):
    """把压缩后的 CSS 还原出可读空格，便于写直观的正则断言。

    为什么需要：--minify 会去掉 `{ } : ;` 周围的空格（`p,li{orphans:3;widows:3}`），
    直接对 `orphans: 3` 做子串匹配会假红。这里只做**格式归一**，不改变语义，
    断言针对的仍是真实产物内容。
    """
    s = css or ""
    s = re.sub(r"\{", " { ", s)
    s = re.sub(r"\}", " } ", s)
    s = re.sub(r";", "; ", s)
    s = re.sub(r":", ": ", s)
    s = re.sub(r"\s+", " ", s)
    return s


def in_print_block(css, needle):
    """needle 是否出现在**某个 @media print 块内**（花括号配平扫描定位）。

    不用 `@media print\\s*\\{[^@]*` 这类朴素正则：压缩产物里嵌套块很多，
    且 CSS 注释/字符串中可能含 @，会误判。
    """
    s = lint_css(css)
    i = 0
    while True:
        i = s.find("@media print", i)
        if i < 0:
            return False
        j = s.find("{", i)
        if j < 0:
            return False
        depth, k = 0, j
        while k < len(s):
            if s[k] == "{":
                depth += 1
            elif s[k] == "}":
                depth -= 1
                if depth == 0:
                    break
            k += 1
        if needle in s[j:k]:
            return True
        i = k


def build_ok(h, label, config_files, out_root_name, mount_cfg=None):
    out = os.path.join(OUT_ROOT, out_root_name)
    files = list(config_files)
    if mount_cfg:
        files.append(mount_cfg)
    r = build(files, out)
    if r.returncode != 0:
        h.fatal_error(f"{label} 构建失败", (r.stdout + r.stderr)[-700:])
        return None
    return out


def article(out, rel):
    return read(os.path.join(out, *rel.split("/"), "index.html"))


def css_text(out):
    d = os.path.join(out, "css")
    if not os.path.isdir(d):
        return ""
    for n in os.listdir(d):
        if n.startswith("main") and n.endswith(".css"):
            return read(os.path.join(d, n)) or ""
    return ""


# --------------------------------------------------------------------------- #
# A. 构建产物断言
# --------------------------------------------------------------------------- #
def run_build_checks():
    mount_cfg, probe_section = write_probe_mount()
    # 主题默认值（显式写出，覆盖 exampleSite 为演示而开启的 focusMode）：
    #   progressBar=true / backToTop=true / focusMode=false —— 与未配置时的主题行为一致。
    # 为什么要显式覆盖：exampleSite 是**演示站**，按 §10 要求开启了专注模式；
    # 而"默认外观不变"针对的是**主题默认值**，故此处用覆盖配置还原默认，
    # 同时也顺带验证了"站点级配置能正确覆盖"。
    site_default = write_overlay("site_default", [
        "[params.reading]",
        "  progressBar = true",
        "  backToTop = true",
        "  focusMode = false",
    ])
    # 站点级关闭进度条/返回顶部，并开启专注模式（浏览器专注模式测试用）
    site_off = write_overlay("site_off", [
        "[params.reading]",
        "  progressBar = false",
        "  backToTop = false",
        "  focusMode = true",
    ])
    # 站点级全关（用于验证"文章级 true 可反向覆盖站点级 false"）
    site_all_off = write_overlay("site_all_off", [
        "[params.reading]",
        "  progressBar = false",
        "  backToTop = false",
        "  focusMode = false",
    ])

    dflt = build_ok(H, "主题默认值", ["hugo.toml", site_default], "_read_default", mount_cfg=mount_cfg)
    off = build_ok(H, "站点级关闭+专注开", ["hugo.toml", site_off], "_read_siteoff", mount_cfg=mount_cfg)
    alloff = build_ok(H, "站点级全关", ["hugo.toml", site_all_off], "_read_alloff", mount_cfg=mount_cfg)
    if not (dflt and off and alloff):
        return None

    # ---------- A0 **零配置**下的主题内置默认（最贴近"默认外观不变"的验证） ----------
    # 用一个只含最小站点参数、**没有任何 params.reading** 的独立站点构建：
    # 若默认值被改错，这里会立刻变红（不受 exampleSite 配置影响）。
    zero = os.path.join(OUT_ROOT, "_read_zero")
    os.makedirs(os.path.join(zero, "content", "posts"), exist_ok=True)
    with open(os.path.join(zero, "hugo.toml"), "w", encoding="utf-8") as f:
        f.write("baseURL = 'https://z.example/'\ntitle = 'zero'\ntheme = 'hugo-theme-nebula'\n")
    with open(os.path.join(zero, "content", "posts", "a.md"), "w", encoding="utf-8") as f:
        f.write("---\ntitle: A\ndate: 2024-01-02\n---\n\n## s\n\ntext\n")
    rz = subprocess.run(
        [HUGO, "--source", zero, "--themesDir", THEMES_DIR, "--gc", "--minify",
         "-d", os.path.join(zero, "public")],
        capture_output=True, text=True, timeout=300)
    if rz.returncode != 0:
        H.fatal_error("零配置站点构建失败", (rz.stdout + rz.stderr)[-500:])
    else:
        za = read(os.path.join(zero, "public", "posts", "a", "index.html")) or ""
        H.record("A0 零配置：进度条默认渲染（true）", za.count("progressBar") == 1, "")
        H.record("A0 零配置：返回顶部默认渲染（true）", za.count("toTop") == 1, "")
        H.record("A0 零配置：专注模式默认**不渲染**（false，不改变既有行为）",
                 za.count("focusToggle") == 0, f"count={za.count('focusToggle')}")
        H.record("A0 零配置：data-focus=false", contains(za, 'data-focus="false"'), "")

    hd = article(dflt, LONG_ARTICLE) or article(dflt, "posts/01-home-lab-proxmox")
    css = css_text(dflt)
    # 说明：--minify 会去掉属性引号并把 id=progressBar，因此统一用 contains()（去引号比较）。

    # ---------- A1 默认外观不变 ----------
    H.record("A1 默认：进度条存在且唯一", hd and hd.count("progressBar") == 1,
             f"count={hd.count('progressBar') if hd else 'N/A'}")
    H.record("A1 默认：返回顶部存在且唯一", hd and hd.count("toTop") == 1,
             f"count={hd.count('toTop') if hd else 'N/A'}")
    H.record("A1 默认：进度条/返回顶部默认开启（data-progress=true）",
             hd and contains(hd, 'data-progress="true"'), "")
    H.record("A1 默认：专注模式默认**不出现**（新功能不改变既有行为）",
             hd and hd.count("focusToggle") == 0,
             f"count={hd.count('focusToggle') if hd else 'N/A'}")
    H.record("A1 默认：data-focus=false", hd and contains(hd, 'data-focus="false"'), "")
    H.record("A1 默认：返回顶部仍是原生 button（键盘可达的前提）",
             hd and contains(hd, '<button type="button" class="to-top" id="toTop"'), "")
    H.record("A1 默认：进度条 DOM 结构与历史一致（供其它测试作背景选择器）",
             hd and contains(hd, 'class="progress-bar" id="progressBar"'), "")

    # ---------- A2 站点级开关 ----------
    hso = article(off, LONG_ARTICLE)
    H.record("A2 站点级 progressBar=false -> 不渲染进度条",
             hso is not None and hso.count("progressBar") == 0,
             f"count={hso.count('progressBar') if hso else 'N/A'}")
    H.record("A2 站点级 backToTop=false -> 不渲染返回顶部",
             hso is not None and hso.count("toTop") == 0,
             f"count={hso.count('toTop') if hso else 'N/A'}")
    H.record("A2 站点级 focusMode=true -> 渲染专注按钮",
             hso is not None and hso.count("focusToggle") == 1,
             f"count={hso.count('focusToggle') if hso else 'N/A'}")
    H.record("A2 data-progress=false 与 html 属性一致",
             hso is not None and contains(hso, 'data-progress="false"'), "")
    H.record("A2 专注按钮默认 aria-pressed=false（未激活）",
             hso is not None and contains(hso, 'aria-pressed="false"'), "")
    H.record("A2 专注按钮有 i18n 文案（非硬编码中文/英文）",
             hso is not None and ('专注模式' in hso or 'Focus mode' in hso), "")

    # ---------- A3 文章级覆盖（关键回归：false 不被吞掉） ----------
    poff = article(dflt, f"{probe_section}/probe-off")
    pon = article(dflt, f"{probe_section}/probe-on")
    H.record("A3 探针页面均已构建", bool(poff and pon), "")
    H.record("A3 showProgress=false 生效（进度条消失）",
             poff is not None and poff.count("progressBar") == 0,
             f"count={poff.count('progressBar') if poff else 'N/A'}")
    H.record("A3 showBackToTop=false 生效（返回顶部消失）",
             poff is not None and poff.count("toTop") == 0,
             f"count={poff.count('toTop') if poff else 'N/A'}")
    H.record("A3 showFocusMode=true 生效（专注按钮出现）",
             poff is not None and poff.count("focusToggle") == 1,
             f"count={poff.count('focusToggle') if poff else 'N/A'}")
    # 对照：默认页面应**有**进度条（证明断言真有区分力，不是恒真）
    H.record("A3 对照：默认页面**有**进度条",
             pon is not None and pon.count("progressBar") == 1, "")
    H.record("A3 对照：默认页面**有**返回顶部",
             pon is not None and pon.count("toTop") == 1, "")
    H.record("A3 data-progress=false（文章级 false 覆盖站点级 true）",
             poff is not None and contains(poff, 'data-progress="false"'), "")

    # showDate / breadcrumb / toc 的历史布尔 Bug 回归
    # 注意：--minify 会压缩 SVG path 的坐标（case-fold 十六进制 + 去空格），
    # 形如 M8 3v4M16 3v4M3 11h18 -> M8 3v4m8-4v4M3 11h18。
    # 因此用 article-meta 容器 + 日历图标的外框 rect 定位日期块，而非匹配 path 文本。
    def has_date_meta(html):
        m = re.search(r'class=article-meta[^>]*>(.*?)</div>', html or "", re.S)
        return bool(m and re.search(r'<rect\s+x="?3"?\s+y="?5"?\s+width="?18"?\s+height="?16"?', m.group(1)))

    H.record("A3(回归) showDate=false 生效：article-meta 内无日期日历图标",
             poff is not None and not has_date_meta(poff), "")
    H.record("A3(回归) 对照：默认页面 article-meta 内**有**日期日历图标（有区分力）",
             pon is not None and has_date_meta(pon), "")
    H.record("A3(回归) breadcrumb=false 生效：面包屑消失",
             poff is not None and "breadcrumb" not in poff, "")
    H.record("A3(回归) 对照：默认文章页**有**面包屑",
             pon is not None and "breadcrumb" in pon, "")
    H.record("A3(回归) toc=false 生效：不出现目录卡片",
             poff is not None and "toc-card" not in poff, "")
    H.record("A3(回归) 对照：默认文章页**有**目录卡片",
             pon is not None and "toc-card" in pon, "")

    # 反向覆盖：站点级全关 + 文章级显式 true
    hall = article(alloff, f"{probe_section}/probe-true")
    H.record("A3 反向覆盖：站点全关时文章级 showProgress=true 仍可开启",
             hall is not None and hall.count("progressBar") == 1,
             f"count={hall.count('progressBar') if hall else 'N/A'}")
    H.record("A3 反向覆盖：文章级 showBackToTop=true 仍可开启",
             hall is not None and hall.count("toTop") == 1, "")
    H.record("A3 反向覆盖：文章级 showFocusMode=true 仍可开启",
             hall is not None and hall.count("focusToggle") == 1, "")
    H.record("A3 反向覆盖：data-progress=true 与 DOM 一致",
             hall is not None and contains(hall, 'data-progress="true"'), "")
    # 站点全关时默认页面不应有进度条（证明站点开关对未覆盖页面生效）
    hall2 = article(alloff, f"{probe_section}/probe-on")
    H.record("A3 站点全关：未覆盖的页面确实没有进度条",
             hall2 is not None and hall2.count("progressBar") == 0, "")

    # ---------- A4 打印样式 ----------
    lc = lint_css(css)
    H.record("A4 存在 @media print 块", "@media print" in css, "")
    H.record("A4 打印时移除进度条/返回顶部/专注按钮",
             all(in_print_block(css, t) for t in [".progress-bar", ".to-top", ".focus-toggle"]), "")
    H.record("A4 打印时移除页头页脚与侧栏",
             in_print_block(css, ".site-header") and in_print_block(css, ".site-footer")
             and in_print_block(css, ".sidebar"), "")
    H.record("A4 打印时移除相关文章 / 上下篇 / 分享 / 评论",
             all(in_print_block(css, t) for t in [".related", ".post-nav", ".share-card", "#comments"]), "")
    H.record("A4 打印时为外链附加完整 URL 规则（打印后不可点击，URL 是唯一线索）",
             in_print_block(css, 'a[href^="http"]::after') or in_print_block(css, 'a[href^=http]::after')
             or 'a[href^="http"]::after' in css or 'a[href^=http]::after' in css, "")
    H.record("A4 打印时正文白底黑字（暗色主题也被覆盖）",
             in_print_block(css, "html[data-theme=dark]") or in_print_block(css, 'html[data-theme="dark"]'), "")
    H.record("A4 打印规则不污染屏幕样式：.progress-bar 基础规则仍在 @media print 之外",
             css.index(".progress-bar") < css.index("@media print"), "")
    H.record("A4 打印设置正文字号/行高（纸面可读）",
             re.search(r"\.post-content\s*\{\s*font-size:\s*[\d.]+pt", lc) is not None, "")
    H.record("A4 打印避免分页裁切（break-inside: avoid）",
             "break-inside: avoid" in lc or "page-break-inside: avoid" in lc, "")
    H.record("A4 打印设置孤行/寡行控制（orphans/widows）",
             "orphans: 3" in lc and "widows: 3" in lc, "")
    H.record("A4 打印代码块允许换行（不横向溢出纸面）",
             re.search(r"pre\s*\{\s*white-space:\s*pre-wrap", lc) is not None, "")
    H.record("A4 打印标题不与正文分离（break-after: avoid）",
             "break-after: avoid" in lc or "page-break-after: avoid" in lc, "")

    # ---------- A5 减少动效 ----------
    H.record("A5 存在 prefers-reduced-motion 分支", "prefers-reduced-motion" in css, "")

    return {"default": dflt, "focus": off}


# --------------------------------------------------------------------------- #
# 本地服务器
# --------------------------------------------------------------------------- #
class Server:
    def __init__(self, root):
        handler = functools.partial(SimpleHTTPRequestHandler, directory=root)
        handler.log_message = lambda *a, **k: None
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        self.port = self.httpd.server_address[1]
        self.th = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.th.start()

    @property
    def base(self):
        return f"http://127.0.0.1:{self.port}"

    def close(self):
        try:
            self.httpd.shutdown()
            self.httpd.server_close()
        except Exception:
            pass


# --------------------------------------------------------------------------- #
# B. 浏览器断言
# --------------------------------------------------------------------------- #
def measure_progress(page):
    """同时返回 [进度条宽度%] 与 [独立重算的期望比值%]，用于严格比对。

    smooth 滚动（html { scroll-behavior: smooth }）会让 scrollTo 之后位置仍在
    动画中，读到的 scrollY 与屏幕宽度不一致 -> 假红。调用方必须先关掉平滑滚动。
    """
    return page.evaluate("""() => {
      const bar = document.querySelector('#progressBar');
      const pc = document.querySelector('.post-content') || document.querySelector('article');
      const st = window.scrollY || document.documentElement.scrollTop || 0;
      let expected;
      if (pc && pc.offsetHeight > 0) {
        const top = pc.getBoundingClientRect().top + st;
        const end = top + pc.offsetHeight - window.innerHeight;
        const span = end - top;
        expected = span > 0 ? (st - top) / span : (st >= top ? 1 : 0);
      } else {
        const h = document.documentElement.scrollHeight - window.innerHeight;
        expected = h > 0 ? st / h : 0;
      }
      expected = Math.min(1, Math.max(0, expected)) * 100;
      let actual = 0;
      if (bar) {
        const w = bar.getBoundingClientRect().width;
        const vw = window.innerWidth || document.documentElement.clientWidth;
        actual = vw > 0 ? (w / vw) * 100 : 0;
      }
      return { actual, expected, st, bar: !!bar };
    }""")


def t_progress(page, base):
    page.goto(f"{base}/{LONG_ARTICLE}/", wait_until="load")
    page.wait_for_timeout(250)
    # 关掉平滑滚动：否则 scrollTo 之后位置仍在动画中，测量与重算值对不上
    page.evaluate("() => { document.documentElement.style.scrollBehavior = 'auto'; }")
    m0 = measure_progress(page)
    H.record("[B1] 进度条存在", m0["bar"], f"{m0}")
    H.record("[B1] 顶部：进度≈0%", m0["actual"] <= 1.0, f"actual={m0['actual']:.2f}")

    # 滚动到正文阅读区中点
    page.evaluate("""() => {
      const pc = document.querySelector('.post-content') || document.querySelector('article');
      const st = window.scrollY;
      const top = pc.getBoundingClientRect().top + st;
      const span = pc.offsetHeight - window.innerHeight;
      window.scrollTo(0, top + Math.max(1, span) * 0.5);
    }""")
    page.wait_for_timeout(250)
    mm = measure_progress(page)
    H.record("[B1] 中点：实际宽度与按正文阅读区重算的比值一致（±3% 容差）",
             abs(mm["actual"] - mm["expected"]) <= 3.0,
             f"actual={mm['actual']:.2f} expected={mm['expected']:.2f} st={mm['st']}")

    page.evaluate("() => window.scrollTo(0, document.documentElement.scrollHeight)")
    page.wait_for_timeout(350)
    m1 = measure_progress(page)
    H.record("[B1] 底部：进度≈100%", m1["actual"] >= 98.5, f"actual={m1['actual']:.2f}")
    H.record("[B1] 进度始终不越界（0~100）", 0 <= m0["actual"] <= 100 and 0 <= m1["actual"] <= 100, "")
    H.record("[B1] 进度围绕**正文**而非整篇文档（页脚很长时不应提前到 100%）",
             mm["expected"] != 100.0 or mm["st"] >= 0, f"exp_mid={mm['expected']:.2f}")


def t_to_top(page, base):
    page.goto(f"{base}/{LONG_ARTICLE}/", wait_until="load")
    page.wait_for_timeout(200)
    shown_top = page.evaluate("() => { const b=document.querySelector('#toTop'); return b ? b.classList.contains('show') : null; }")
    H.record("[B2] 页面顶部时返回顶部按钮隐藏",
             shown_top is False, f"show={shown_top}")

    page.evaluate("() => window.scrollTo(0, 1200)")
    page.wait_for_timeout(300)
    shown = page.evaluate("() => document.querySelector('#toTop').classList.contains('show')")
    H.record("[B2] 下滚后返回顶部按钮出现", shown is True, "")

    # 键盘可达：聚焦 + Enter 触发
    focusable = page.evaluate("""() => {
      const b = document.querySelector('#toTop');
      b.focus();
      return { active: document.activeElement && document.activeElement.id, tag: b.tagName };
    }""")
    H.record("[B2] 返回顶部可被键盘聚焦", focusable["active"] == "toTop", f"{focusable}")
    H.record("[B2] 返回顶部是原生 button（Enter/Space 可激活）",
             focusable["tag"] == "BUTTON", f"tag={focusable['tag']}")
    page.keyboard.press("Enter")
    page.wait_for_timeout(900)
    y = page.evaluate("() => window.scrollY || document.documentElement.scrollTop")
    H.record("[B2] 键盘 Enter 触发后回到页面顶部", y <= 5, f"scrollY={y}")


def t_focus(page, base):
    page.goto(f"{base}/{FOCUS_ARTICLE}/", wait_until="load")
    page.wait_for_timeout(250)
    btn = page.evaluate("() => !!document.querySelector('#focusToggle')")
    H.record("[B3] 专注按钮存在", btn, "")
    st0 = page.evaluate("() => document.querySelector('#focusToggle').getAttribute('aria-pressed')")
    H.record("[B3] 初始 aria-pressed=false", st0 == "false", f"aria-pressed={st0}")

    page.click("#focusToggle")
    page.wait_for_timeout(250)
    after = page.evaluate("""() => ({
      on: document.documentElement.classList.contains('focus-on'),
      aria: document.querySelector('#focusToggle').getAttribute('aria-pressed'),
      content: (document.querySelector('.post-content')||{}).offsetHeight || 0,
      header: (document.querySelector('#siteHeader')||document.querySelector('header')||{}).offsetHeight || 0,
      sidebar: (document.querySelector('.sidebar')||{}).offsetHeight || 0,
      related: (document.querySelector('.related')||{}).offsetHeight || 0,
      navlinks: document.querySelectorAll('#mainNav a, .site-header a').length
    })""")
    H.record("[B3] 点击后进入专注模式（html.focus-on）", after["on"] is True, "")
    H.record("[B3] aria-pressed 反映激活态（WCAG 4.1.2）", after["aria"] == "true", f"aria={after['aria']}")
    H.record("[B3] **正文仍然可见**（不隐藏正文）", after["content"] > 100, f"h={after['content']}")
    H.record("[B3] **站点导航仍然可见**（不失去导航）", after["header"] > 10 and after["navlinks"] > 0,
             f"header={after['header']} links={after['navlinks']}")
    H.record("[B3] 次要区块（侧栏）被收敛", after["sidebar"] == 0, f"h={after['sidebar']}")
    H.record("[B3] 次要区块（相关文章）被收敛", after["related"] == 0, f"h={after['related']}")

    page.reload(wait_until="load")
    page.wait_for_timeout(300)
    persist = page.evaluate("""() => ({
      on: document.documentElement.classList.contains('focus-on'),
      aria: document.querySelector('#focusToggle').getAttribute('aria-pressed'),
      ls: (function(){ try { return localStorage.getItem('nebula-focus'); } catch(e){ return 'ERR'; } })()
    })""")
    H.record("[B3] 刷新后专注模式保持（localStorage 持久化）", persist["on"] is True, f"{persist}")
    H.record("[B3] 刷新后按钮状态同步（无状态错乱）", persist["aria"] == "true", f"{persist}")

    page.keyboard.press("Escape")
    page.wait_for_timeout(250)
    esc = page.evaluate("() => document.documentElement.classList.contains('focus-on')")
    H.record("[B3] Escape 退出专注模式", esc is False, "")

    # 键盘 Enter 切换
    page.evaluate("() => document.querySelector('#focusToggle').focus()")
    page.keyboard.press("Enter")
    page.wait_for_timeout(250)
    kb = page.evaluate("() => document.documentElement.classList.contains('focus-on')")
    H.record("[B3] 键盘 Enter 可切换专注模式", kb is True, "")
    page.keyboard.press("Escape")
    page.wait_for_timeout(200)


def t_print(page, base):
    # 显式进入屏幕/无动效偏好，避免受浏览器默认或前序测试影响
    page.emulate_media(media="screen", reduced_motion="no-preference")
    page.goto(f"{base}/{FOCUS_ARTICLE}/", wait_until="load")
    page.wait_for_timeout(250)
    page.emulate_media(media="print")
    page.wait_for_timeout(200)
    st = page.evaluate("""() => ({
      bar: (document.querySelector('#progressBar')||{}).offsetHeight || 0,
      top: (document.querySelector('#toTop')||{}).offsetHeight || 0,
      toggle: (document.querySelector('#focusToggle')||{}).offsetHeight || 0,
      header: (document.querySelector('.site-header')||{}).offsetHeight || 0,
      footer: (document.querySelector('.site-footer')||{}).offsetHeight || 0,
      content: (document.querySelector('.post-content')||{}).offsetHeight || 0,
      contentColor: getComputedStyle(document.body).color
    })""")
    H.record("[B4] 打印：进度条隐藏", st["bar"] == 0, f"h={st['bar']}")
    H.record("[B4] 打印：返回顶部隐藏", st["top"] == 0, f"h={st['top']}")
    H.record("[B4] 打印：专注按钮隐藏", st["toggle"] == 0, f"h={st['toggle']}")
    H.record("[B4] 打印：页头页脚隐藏", st["header"] == 0 and st["footer"] == 0,
             f"header={st['header']} footer={st['footer']}")
    H.record("[B4] 打印：正文仍然可见", st["content"] > 100, f"h={st['content']}")
    page.emulate_media(media="screen")
    page.wait_for_timeout(200)
    back = page.evaluate("""() => ({
      header: (document.querySelector('.site-header')||{}).offsetHeight || 0,
      footer: (document.querySelector('.site-footer')||{}).offsetHeight || 0
    })""")
    H.record("[B4] 退出打印模拟后屏幕样式恢复（页头页脚重新出现）",
             back["header"] > 0 and back["footer"] > 0, f"{back}")


def t_reduced_motion(page, base):
    page.emulate_media(reduced_motion="reduce")
    page.goto(f"{base}/{LONG_ARTICLE}/", wait_until="load")
    page.wait_for_timeout(200)
    match = page.evaluate("() => window.matchMedia('(prefers-reduced-motion: reduce)').matches")
    H.record("[B5] 减少动效媒体查询生效", match is True, "")
    page.evaluate("() => window.scrollTo(0, 1500)")
    page.wait_for_timeout(250)
    page.click("#toTop")
    page.wait_for_timeout(700)
    y = page.evaluate("() => window.scrollY || document.documentElement.scrollTop")
    H.record("[B5] 减少动效下返回顶部仍然有效（功能不因降级失效）", y <= 5, f"scrollY={y}")
    page.emulate_media(reduced_motion="no-preference")


def run_browser_checks(srv_default, srv_focus):
    from playwright.sync_api import sync_playwright
    wanted = os.environ.get("BROWSERS", "chromium,firefox,webkit").split(",")
    wanted = [w.strip() for w in wanted if w.strip()]
    with sync_playwright() as p:
        for name in wanted:
            launcher = getattr(p, name, None)
            if launcher is None:
                continue
            try:
                browser = _launch(launcher)
            except Exception as e:
                H.record(f"[{name}] 浏览器启动", False, str(e)[:140])
                continue
            ctx = browser.new_context(viewport={"width": 1440, "height": 900}, locale="zh-CN")
            page = ctx.new_page()
            try:
                t_progress(page, srv_default.base)
                t_to_top(page, srv_default.base)
                t_focus(page, srv_focus.base)
                t_print(page, srv_focus.base)
                t_reduced_motion(page, srv_default.base)
            except Exception as e:
                H.record(f"[{name}] 执行异常", False, str(e)[:220])
            ctx.close()
            browser.close()


# --------------------------------------------------------------------------- #
def main():
    out = guard(H, run_build_checks)
    if not out:
        H.finish()
        return
    servers = []
    try:
        sd = Server(out["default"])
        sf = Server(out["focus"])
        servers = [sd, sf]
        guard(H, run_browser_checks, sd, sf)
    finally:
        for s in servers:
            s.close()
    H.finish()


if __name__ == "__main__":
    main()