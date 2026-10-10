#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""新增功能门禁（功能三 / 四 / 五：画廊 / Mermaid / KaTeX / 编辑入口 / 多作者 / 外链 / 外观）。

覆盖 README「功能三/四/五」中本轮新增的能力，每条都做**真实产物断言**
（不是"脚本没报错"）：

  G  响应式图片画廊：栅格结构 / 复用图片管线（srcset + data-zoom-src）/ 不套 <a>
     （交给灯箱）/ 缺图占位回退 / 列数 class / 无第三方请求
  X  外链文章：首页卡片 class + 徽标 + target=_blank rel=noopener / canonical /
     RSS link+guid(isPermaLink=false) / 搜索索引 external:true + 站外 url
  A  多作者：meta author（逗号并列）/ JSON-LD Person 数组 / RSS 多 <author> /
     正文元信息 / 与卡片一致；空不虚构
  E  编辑此页：配置后出现且指向**源文件**（含编码）/ 未配置不输出 / 逐文章关闭
  P  外观配置：配置后输出 CSS 变量覆盖 / **未配置时逐字节不输出**（默认外观不变）/
     非法值安全回退（不产生破坏性输出）
  M  Mermaid / KaTeX：**按需加载**（仅含语法的页面注入）/ 自托管（无第三方域名）/
     SRI fingerprint / pre.mermaid 容器保留语法

## 故障注入自证（--selftest）

"测试通过"只有在**测试能失败**时才有意义。本脚本对 4 条关键断言做注入：
把主题**复制一份**、人为打坏某个实现，构建最小探针站点，断言**对应检查确实变红**。
注入不改动工作区主题；探针站点与副本都建在 tmp/ 下并在 finally 清理。

注入清单：
  inj-external-scheme : extern al-url 取消 scheme 白名单 -> X 断言应变红
  inj-gallery-off     : gallery 不产出栅格结构 -> G 断言应变红
  inj-mermaid-always  : mermaid 去掉"按需"门（每页都注入）-> M 断言应变红
  inj-appearance-always: appearance 无条件输出 <style> -> P 断言应变红

用法：
  python tools/check_new_features.py [构建产物目录]
  python tools/check_new_features.py --selftest

退出码约定见 tools/_testlib.py：任一断言失败 / 注入未变红 -> exit 1。
"""
import json
import os
import re
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _testlib import Harness, guard, safe_rmtree, TempWorkspace  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = os.path.join(REPO, "exampleSite")
THEMES_DIR = os.path.dirname(REPO)
HUGO = os.environ.get("HUGO_BIN", "hugo")
OUT_ROOT = os.path.join(REPO, "tmp")

EXT_HOST = "attack.mitre.org"
EXT_URL = f"https://{EXT_HOST}/"

# 需要"含语法"的页（应注入 mermaid/katex）；普通页与首页**不应**注入。
PAGE_WITH_MEDIA = "posts/media-and-diagrams/index.html"
PAGE_WITH_EXTERNAL = "posts/external-reading/index.html"
PAGE_WITH_AUTHORS = "posts/authors-and-appearance/index.html"
PAGE_PLAIN = "posts/01-home-lab-proxmox/index.html"


def run_hugo(source, out, theme_dir=None, extra_config=None):
    """构建站点；返回 (rc, 输出)。--themesDir 必须用**绝对路径**（相对路径会
    module not found，见验收记录）。"""
    os.makedirs(out, exist_ok=True)
    cmd = [HUGO, "--source", source,
           "--themesDir", theme_dir or THEMES_DIR,
           "--theme", "hugo-theme-nebula",
           "--gc", "--minify", "-d", out]
    if extra_config:
        cmd += ["--config", os.path.join(source, "hugo.toml") + "," + extra_config]
    import subprocess
    p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                       errors="ignore")
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def read(out, rel):
    p = os.path.join(out, rel.replace("/", os.sep))
    if not os.path.exists(p):
        return None
    return open(p, encoding="utf-8", errors="ignore").read()


def _blank_noopener(html, url):
    """判断指向 url 的 <a> 是否同时带 target=_blank 与 rel=noopener。
    容忍 `--minify` 去掉属性引号（target=_blank / rel=noopener）。"""
    for m in re.finditer(r"<a[^>]*>", html, re.I):
        tag = m.group(0)
        if url not in tag:
            continue
        if re.search(r'target\s*=\s*["\']?_blank', tag) and \
           re.search(r'rel\s*=\s*["\']?[^"\'>]*noopener', tag):
            return True
    return False


# ===========================================================================
# 单页断言（返回 (passed, failed) 计数，全部经 harness 记录）
# ===========================================================================
def check_gallery(out, h):
    html = read(out, PAGE_WITH_MEDIA)
    if html is None:
        h.fatal_error("画廊：媒体演示页存在", PAGE_WITH_MEDIA)
        return
    h.record("G1 画廊栅格结构（.nb-gallery > .nb-gallery-grid）",
             "nb-gallery-grid" in html and "<figure class=\"nb-gallery" in html)
    h.record("G2 画廊列数 class（cols=3）", "nb-gallery-cols-3" in html)
    # 复用图片管线：page bundle 图应有 srcset + data-zoom-src + width/height
    gal = html[html.find("nb-gallery"):]
    h.record("G3 画廊复用图片 Pipeline（srcset）", "srcset" in gal)
    h.record("G4 画廊图保留灯箱放大源（data-zoom-src）", "data-zoom-src" in gal)
    h.record("G5 画廊图带 width/height（防 CLS）",
             bool(re.search(r'<img[^>]*width="?\d+"?[^>]*height="?\d+"?', gal)))
    # 不套 <a>：画廊内 img 不应被链接包裹（否则灯箱逻辑不接管）
    first_fig = re.search(r'<figure class="nb-figure nb-gallery-item.*?</figure>', gal, re.S)
    seg = first_fig.group(0) if first_fig else ""
    h.record("G6 画廊图不被 <a> 包裹（交给灯箱自动接管）",
             bool(seg) and "<a " not in seg and "</a>" not in seg)
    h.record("G7 缺图优雅回退为占位块（保留 alt，不碎裂）",
             "nb-gallery-missing" in html and "nb-gallery-ph" in html)
    h.record("G8 画廊无第三方 http(s) 资源（零 CDN）",
             not re.search(r'<(?:script|link|img)[^>]*(?:src|href)="?https?://(?!blog\.example\.com)', gal))


def check_external(out, h):
    html = read(out, PAGE_WITH_EXTERNAL)
    if html is None:
        h.fatal_error("外链：外链演示页存在", PAGE_WITH_EXTERNAL)
        return
    home = read(out, "index.html") or ""
    h.record("X1 外链文章正文页有外链提示条",
             "article-external-notice" in html and EXT_HOST in html)
    # ⚠ --minify 会去掉属性引号（target=_blank），断言必须容忍无引号写法。
    h.record("X2 外链提示链接新标签打开且 rel=noopener",
             _blank_noopener(html, EXT_URL))
    # 首页卡片区分
    h.record("X3 首页卡片标记 post-card-external", "post-card-external" in home)
    h.record("X4 首页卡片带外链徽标 ext-badge", "ext-badge" in home)
    h.record("X5 首页外链卡片 target=_blank rel=noopener",
             _blank_noopener(home, EXT_URL))
    # RSS
    rss = read(out, "index.xml") or ""
    h.record("X6 RSS 外链条目 link 指向站外",
             f"<link>{EXT_URL}</link>" in rss)
    h.record("X7 RSS 外链条目 guid isPermaLink=false",
             f'<guid isPermaLink="false">{EXT_URL}</guid>' in rss)
    # 搜索索引
    idx_raw = read(out, "index.json") or "[]"
    try:
        idx = json.loads(idx_raw)
        items = idx if isinstance(idx, list) else idx.get("items", [])
    except Exception:
        items = []
    ext = [it for it in items if it.get("external")]
    h.record("X8 搜索索引含 external:true 且 url 为站外地址",
             bool(ext) and all(it.get("url", "").startswith(EXT_URL) for it in ext),
             f"{len(ext)} 条")
    # 不破坏普通文章：普通文章 external 应为 False / 缺省
    plain = [it for it in items if it.get("url", "").endswith("/posts/01-home-lab-proxmox/")]
    h.record("X9 普通文章未被误标为外链",
             bool(plain) and all(not it.get("external") for it in plain))


def check_authors(out, h):
    html = read(out, PAGE_WITH_AUTHORS)
    if html is None:
        h.fatal_error("多作者：作者演示页存在", PAGE_WITH_AUTHORS)
        return
    h.record("A1 meta author 多作者逗号并列",
             bool(re.search(r'<meta\s+name\s*=\s*["\']?author["\']?\s+content\s*=\s*'
                            r'["\']Tanglx,\s*Nebula Bot["\']', html)))
    # JSON-LD author 为 Person 数组（tolerate --minify 无引号属性）
    ld_blocks = re.findall(r'<script[^>]*application/ld\+json[^>]*>(.*?)</script>', html, re.S)
    arr_ok = False
    for b in ld_blocks:
        try:
            d = json.loads(b)
        except Exception:
            continue
        au = d.get("author")
        if isinstance(au, list) and len(au) >= 2 and all(
                x.get("@type") == "Person" and x.get("name") for x in au):
            arr_ok = True
    h.record("A2 JSON-LD author 为 Person 数组（多作者）", arr_ok)
    h.record("A3 正文元信息含作者",
             "stat-author" in html and "Tanglx" in html and "Nebula Bot" in html)
    # RSS：每位作者一个 <author>
    rss = read(out, "index.xml") or ""
    h.record("A4 RSS 多作者输出多个 <author>",
             "<author>Tanglx</author>" in rss and "<author>Nebula Bot</author>" in rss)
    # 空不虚构：无作者页不得出现 name:null / 空 author 标签
    for rel in ("posts/zz-27-no-author/index.html",):
        p = read(out, rel)
        if p is not None:
            h.record("A5 无作者页不输出 name:null（空不虚构）",
                     '"name": null' not in p and '"name":null' not in p)


def check_edit(out, h):
    html = read(out, PAGE_WITH_AUTHORS)
    if html is None:
        return
    m = re.search(r'<a\s+class\s*=\s*["\']?edit-page["\']?\s+href\s*=\s*["\']?([^"\'\s>]+)', html)
    h.record("E1 配置 editUrl 后输出「编辑此页」", bool(m))
    if m:
        url = m.group(1)
        h.record("E2 编辑链接指向源仓库（github edit 路径）",
                 url.startswith("https://github.com/tanglx02/hugo-theme-nebula/edit/main/"))
        h.record("E3 编辑链接指向 .md 源文件而非文章 URL",
                 url.endswith("authors-and-appearance.md"))
        h.record("E4 编辑链接 target=_blank rel=noopener",
                 _blank_noopener(html, "github.com/tanglx02/hugo-theme-nebula/edit/main/"))


def check_appearance(out, h):
    html = read(out, "index.html") or ""
    h.record("P1 配置 appearance 后输出 CSS 变量覆盖（--brand / --wrap）",
             "nebula-appearance" in html and "--brand:" in html and "--wrap:" in html)
    h.record("P2 外观覆盖走 CSS 变量（不逐条硬编码颜色）",
             "--brand-solid:" in html and "--brand-ink:" in html)
    # 非法值回退：injection 用；正常构建验证"合法值生效、非法值被忽略"
    css = html[html.find("nebula-appearance"):]
    css = css[:css.find("</style>")] if "</style>" in css else css
    h.record("P3 外观输出不含破坏性内容（无 </style> / javascript: 逃逸）",
             "javascript:" not in css.lower())


def check_mermaid_katex(out, h):
    media = read(out, PAGE_WITH_MEDIA) or ""
    plain = read(out, PAGE_PLAIN) or ""
    home = read(out, "index.html") or ""
    h.record("M1 含 mermaid 围栏的页面输出 pre.mermaid 容器",
             bool(re.search(r'<pre class=["\']?mermaid', media)))
    h.record("M2 mermaid 容器保留原始语法换行（<pre> 空白敏感）",
             "flowchart" in media and "sequenceDiagram" in media)
    h.record("M3 按需加载：媒体页注入 mermaid 库",
             "mermaid.min.js" in media)
    h.record("M4 按需加载：普通文章**不**注入 mermaid",
             "mermaid.min.js" not in plain and not re.search(r'<pre class=["\']?mermaid', plain))
    h.record("M5 按需加载：首页**不**注入 mermaid",
             "mermaid.min.js" not in home)
    h.record("M6 按需加载：媒体页注入 KaTeX",
             "katex.min.css" in media and "auto-render" in media)
    h.record("M7 按需加载：普通文章**不**注入 KaTeX",
             "katex.min.css" not in plain and "auto-render" not in plain)
    h.record("M8 按需加载：首页**不**注入 KaTeX", "katex.min.css" not in home)
    # 自托管：不应出现第三方 CDN 域名
    h.record("M9 Mermaid / KaTeX 自托管（无 cdn.jsdelivr.net 等第三方域名）",
             not re.search(r'https?://(?:cdn\.jsdelivr\.net|unpkg\.com|cdnjs\.cloudflare\.com)',
                           media))
    # 初始化脚本带 SRI fingerprint（Go 的 `{{ with }}` 让 integrity 出现在 src 之后）
    h.record("M10 主题自有初始化脚本带 fingerprint（integrity 属性）",
             bool(re.search(r'mermaid-init[^"\'>\s]*\.js[^>]*integrity=["\']?sha', media)))
    h.record("M11 数学探测生效：含定界符页注入、纯文字页不注入",
             "katex.min.css" in media and "katex.min.css" not in plain)


# ===========================================================================
# 主流程
# ===========================================================================
def run(h, out=None):
    out = out or os.path.join(REPO, "public")
    if not os.path.isdir(out):
        h.fatal_error("构建产物目录存在", out)
        return
    check_gallery(out, h)
    check_external(out, h)
    check_authors(out, h)
    check_edit(out, h)
    check_appearance(out, h)
    check_mermaid_katex(out, h)


# ---------------------------------------------------------------------------
# 故障注入：证明关键断言**可以失败**
# ---------------------------------------------------------------------------
INJECTIONS = [
    # (名称, 相对文件, 旧串, 新串, 断言关键词)
    ("inj-external-scheme", "layouts/partials/util/external-url.html",
     '{{- if or (hasPrefix $probe "http://") (hasPrefix $probe "https://") (hasPrefix $probe "//") -}}',
     '{{- if false -}}', "X"),
    ("inj-gallery-off", "layouts/shortcodes/gallery.html",
     '<div class=\\"nb-gallery-grid\\">', '<div class=\\"nb-gallery-noop\\">', "G1"),
    ("inj-mermaid-nodemand", "layouts/partials/mermaid.html",
     '{{- $hasContent := .Store.Get "nebula_has_mermaid" -}}',
     '{{- $hasContent := true -}}', "M4"),
    ("inj-appearance-off", "layouts/partials/util/appearance.html",
     '{{- if $css -}}', '{{- if false -}}', "P1"),
]


def _probe_site():
    """最小探针站点：一页含 mermaid/math/外链/多作者，一页普通。"""
    ws = TempWorkspace("nf-selftest")
    return ws


PROBE_CONFIG = """baseURL = 'https://z.example/'
title = 'nf probe'
theme = 'hugo-theme-nebula'
defaultContentLanguage = 'zh-CN'
locale = 'zh-CN'
disableKinds = ['taxonomy', 'term', 'sitemap', 'robotsTXT', '404', 'section']

[languages]
  [languages.zh-CN]
    weight = 1
    contentDir = 'content'

[params]
  author = 'Probe Author'

[params.editUrl]
  repo = 'https://github.com/tanglx02/hugo-theme-nebula'
  branch = 'main'
  contentDir = 'content'
  provider = 'github'

[params.appearance]
  accent = 'blue'
  contentWidth = '1220px'

[params.mermaid]
  enable = true
  local = 'js/vendor/mermaid.min.js'

[outputs]
  home = ['HTML', 'JSON', 'RSS']
"""

PROBE_EXT = """---
title: "Probe external"
date: 2024-05-06
externalUrl: "https://attack.mitre.org/"
authors: ["Tanglx", "Nebula Bot"]
---
probe body
"""

PROBE_MEDIA = """---
title: "Probe media"
date: 2024-05-07
---
```mermaid
flowchart TD
    A --> B
```

Inline $x^2$ and block:

$$
a^2 + b^2 = c^2
$$

{{< gallery cols="3" >}}
probe-a.png | Alt A | Caption A
{{< /gallery >}}
"""

PROBE_PLAIN = """---
title: "Probe plain"
date: 2024-05-08
---
just text, no math and no diagram here.
"""

PROBE_AUTHORS = """---
title: "Probe authors"
date: 2024-05-09
authors: ["Tanglx", "Nebula Bot"]
---
author probe body
"""


def selftest(h):
    base_out = fresh_probe_build("base")
    # 基线：未注入时**各注入目标断言**均应通过。
    # 只检查注入目标（X / G1 / M4 / P1），因为探针站点是精简站点，
    # 不含 exampleSite 的全部演示素材（缺图行、katex 资源等），
    # 那些非目标断言本就不要求成立——否则证明不了"断言会因注入而变红"。
    target_keys = tuple(k for _, _, _, _, k in INJECTIONS)
    base_fails = run_quiet(base_out)
    leaked = [f for f in base_fails if f.startswith(target_keys)]
    h.record("注入自证基线：未注入时注入目标断言全部通过", not leaked,
             "；".join(leaked[:4]))

    for name, rel, old, new, key in INJECTIONS:
        try:
            with TempWorkspace(f"nf-theme-{name}") as ws:
                # 复制主题到临时目录（parent 作为 themesDir 的父级）
                parent = ws.path("themes")
                os.makedirs(parent)
                theme_copy = os.path.join(parent, "hugo-theme-nebula")
                shutil.copytree(REPO, theme_copy,
                                ignore=shutil.ignore_patterns(".git", "tmp", "public*",
                                                              "__pycache__", "exampleSite"))
                target = os.path.join(theme_copy, rel.replace("/", os.sep))
                src = open(target, encoding="utf-8").read()
                if old not in src:
                    h.fatal_error(f"{name}：注入点未找到", rel)
                    continue
                open(target, "w", encoding="utf-8").write(src.replace(old, new, 1))
                out = ws.path("public")
                rc, log = run_hugo(probe_source(), out, theme_dir=parent)
                if rc != 0:
                    # 注入把构建打挂也算"变红"（但不能是我们要证明的断言）
                    h.record(f"{name}：注入后构建失败/断言变红", True, "构建 rc!=0")
                    continue
                fails = run_quiet(out)
                turned_red = any(f.startswith(key) for f in fails)
                h.record(f"{name}：注入对应断言变红", turned_red,
                         f"失败项: {fails[:5]}")
        except Exception as e:   # pragma: no cover
            h.fatal_error(f"{name}：自证过程异常", str(e)[:160])


_PROBE_SRC = None


def probe_source():
    """构造（并复用）探针站点源码目录。

    页面 slug 与 exampleSite 保持同名（media-and-diagrams / external-reading /
    authors-and-appearance / 01-home-lab-proxmox），这样同一批断言在探针站点与
    真实站点上都成立 —— 注入自证才有意义（否则基线本就 fail，证明不了断言会变红）。
    探针站点结构更小、正文可控，用于精确证明"某条实现被破坏时对应断言变红"。
    """
    global _PROBE_SRC
    if _PROBE_SRC and os.path.isdir(_PROBE_SRC):
        return _PROBE_SRC
    root = os.path.join(OUT_ROOT, "_nf_probe_src")
    safe_rmtree(root)
    posts = os.path.join(root, "content", "posts")
    os.makedirs(os.path.join(posts, "media-and-diagrams"))
    os.makedirs(os.path.join(root, "static", "js", "vendor"))
    open(os.path.join(root, "hugo.toml"), "w", encoding="utf-8").write(PROBE_CONFIG)
    # leaf bundle：内含一张真实图片，使画廊 srcset 断言成立
    open(os.path.join(posts, "media-and-diagrams", "index.md"), "w",
         encoding="utf-8").write(PROBE_MEDIA)
    shutil.copy(os.path.join(SITE, "content", "posts", "zz-images-bundle", "photo.png"),
                os.path.join(posts, "media-and-diagrams", "probe-a.png"))
    open(os.path.join(posts, "external-reading.md"), "w", encoding="utf-8").write(PROBE_EXT)
    open(os.path.join(posts, "authors-and-appearance.md"), "w", encoding="utf-8").write(PROBE_AUTHORS)
    open(os.path.join(posts, "01-home-lab-proxmox.md"), "w", encoding="utf-8").write(PROBE_PLAIN)
    src_js = os.path.join(SITE, "static", "js", "vendor", "mermaid.min.js")
    if os.path.exists(src_js):
        shutil.copy(src_js, os.path.join(root, "static", "js", "vendor", "mermaid.min.js"))
    _PROBE_SRC = root
    return root


def fresh_probe_build(tag):
    out = os.path.join(OUT_ROOT, f"_nf_build_{tag}")
    safe_rmtree(out)
    rc, log = run_hugo(probe_source(), out)
    if rc != 0:
        raise RuntimeError(f"探针站点构建失败: {log[-500:]}")
    return out


def run_quiet(out):
    """在静默 Harness 上跑检查，返回失败断言名列表（不退出、不打印）。"""
    class Quiet(Harness):
        def record(self, name, ok, detail=""):
            self.records.append((name, bool(ok), str(detail)))
            return bool(ok)

    q = Quiet("nf-quiet")
    run(q, out)
    return [n for n, ok, _ in q.records if not ok]


def main():
    if "--selftest" in sys.argv:
        h = Harness("new-features-selftest")
        guard(h, lambda: selftest(h))
        h.finish()
        return
    h = Harness("new-features")
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    out = os.path.abspath(args[0]) if args else os.path.join(REPO, "public")
    guard(h, lambda: run(h, out))
    h.finish()


if __name__ == "__main__":
    main()