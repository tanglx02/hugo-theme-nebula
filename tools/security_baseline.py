#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""安全基线检查（轻量，仅标准库，不引入重量级依赖）。

扫描范围：
    A. 构建产物 public/ 下的 HTML
    B. 主题源码 layouts/ + assets/（模板与脚本里的危险写法）

检查项：
    1. javascript: / vbscript: / data:text/html URL
    2. 空 href（href="" 或 href="#" 以外的空形态）
    3. target="_blank" 缺 rel="noopener"
    4. 明显危险的 inline event handler（on* 属性，且不在白名单内）
    5. 非预期外部 <script src>（构建产物里）
    6. 非预期 <iframe>（构建产物里）
    7. 非预期第三方域名（构建产物里的 http(s) 外链）
    8. raw HTML / unsafe 配置变化：markup.goldmark.renderer.unsafe 必须为 false
    9. 主题源码中的危险 API（eval / document.write / innerHTML 拼接等）

白名单：ALLOWED_SCRIPT_HOSTS / ALLOWED_IFRAME_HINT / ALLOWED_HANDLERS
每次命中白名单都会打印，避免白名单悄悄膨胀。

退出码约定（见 tools/_testlib.py）：任一违规 -> exit 1。

用法：
    python3 tools/security_baseline.py <build_dir> [theme_root]
"""
import os
import re
import sys

from _testlib import Harness, guard, default_build_dir

# 默认路径统一为 <repo>/public（TEST-DEFECT-R2-003）；-h/--help 正确解析
BUILD_DIR = default_build_dir()
THEME = sys.argv[2] if len(sys.argv) > 2 else os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ---------- 白名单（每次命中都会打印）----------
ALLOWED_SCRIPT_HOSTS = {
    # 主题自身不加载任何外部脚本；评论/统计为用户可选功能，默认关闭。
    # 构建产物里出现这些域名说明对应功能被启用 —— 不算漏洞，但必须可见。
    "giscus.app", "unpkg.com", "cdn.jsdelivr.net", "busuanzi.ibruce.info",
    "cdn.jsdelivr.net", "lf9-cdn-tos.bytecdntp.com",
}
# 主题允许的第三方外链域名（社交链接等）
ALLOWED_LINK_HOSTS = {
    "gohugo.io", "github.com", "twitter.com", "t.me", "facebook.com",
    "reddit.com", "weibo.com", "space.bilibili.com", "giscus.app",
    "unpkg.com", "cdn.jsdelivr.net", "busuanzi.ibruce.info",
    "waline.example.com", "twikoo.example.com", "disqus.com",
    # IANA 保留的示例域名：tools/gen_testdata.py 用它构造"链接包裹的图片"等
    # 刻意外链样本（修好 minify 漏检后（TEST-DEFECT-002）该真实外链才被看见）
    "example.com", "example.org", "example.net",
    # exampleSite 的"外链文章"演示（content/posts/external-reading.md 用 externalUrl
    # 指向 MITRE ATT&CK 知识库）：这是**内容里的普通外链**，不是主题加载的资源，
    # 属于正常引用，列入可见白名单（每次命中都会打印，仍可审计）。
    "attack.mitre.org",
}


def host_allowed(host, whitelist=ALLOWED_LINK_HOSTS):
    """域名白名单：精确匹配或子域匹配（www./service. 等）。"""
    host = host.lower()
    return any(host == w or host.endswith("." + w) for w in whitelist)
# 允许存在的 inline handler（主题自身需要；应尽量少）
ALLOWED_HANDLERS = set()

# 行级白名单：(文件相对路径, 行内特征) -> 豁免理由
# 每次命中都会打印，保证白名单可见、可审计。
ALLOWED_JS_LINES = {
    ("assets/js/main.js", "btn.innerHTML = ok"):
        "复制按钮文案切换：ok/ICON_OK/old 均为构建期常量与 i18n 文案，无用户输入",
}

DANGEROUS_URL_SCHEMES = ("javascript:", "vbscript:", "data:text/html")

# 主题源码里的危险 API（模板/JS 中不应出现）
DANGEROUS_JS = [
    (r"\beval\s*\(", "eval() 调用"),
    (r"\bdocument\.write\s*\(", "document.write()"),
    (r"new\s+Function\s*\(", "new Function()"),
    (r"\.innerHTML\s*=\s*[^;]*\+\s*", "innerHTML 字符串拼接"),
]

# 恶意 URL 出现在属性中（href/src/action/formaction/xlink:href）
# ⚠ 必须容忍 **无引号 / 单引号** 属性：CI 一律 --minify，Hugo 会把
#   href="javascript:..." 输出成 href=javascript:...，旧正则只认双引号 -> 漏检。
#   （TEST-DEFECT-002）
URL_ATTR_RE = re.compile(
    r"(href|src|action|formaction|xlink:href)\s*=\s*"
    r"(?:\"([^\"]*)\"|'([^']*)'|([^\s\"'=<>`]+))", re.I)
SCRIPT_SRC_RE = re.compile(
    r"<script[^>]+src\s*=\s*(?:\"([^\"]*)\"|'([^']*)'|([^\"'\s>]+))", re.I)
IFRAME_RE = re.compile(r"<iframe[^>]*>", re.I)
ANY_URL_RE = re.compile(r"https?://([a-z0-9.-]+)", re.I)
# inline handler：同样容忍无引号（onclick=alert(1)）
HANDLER_RE = re.compile(r"\son([a-z]+)\s*=\s*[\"']?", re.I)


def _attr_val(m):
    """取 (attr, url[, ...]) 匹配中第一个非 None 的取值组。"""
    for i in range(2, 5):
        if m.lastindex is not None and i <= m.lastindex and m.group(i) is not None:
            return m.group(i)
    return ""


def url_attrs(html):
    """产出 (属性名, 取值)，兼容双引号 / 单引号 / 无引号三种写法。"""
    for m in URL_ATTR_RE.finditer(html):
        yield m.group(1), _attr_val(m)


def script_srcs(html):
    for m in SCRIPT_SRC_RE.finditer(html):
        yield _attr_val(m)


A_TAG_RE = re.compile(r"<a\b[^>]*>", re.I)
LINK_TAG_RE = re.compile(r"<link\b[^>]*>", re.I)
META_TAG_RE = re.compile(r"<meta\b[^>]*>", re.I)
CANONICAL_IN_TAG_RE = re.compile(r"rel\s*=\s*[\"']?canonical[\"']?", re.I)
OGURL_IN_TAG_RE = re.compile(r"property\s*=\s*[\"']?og:url[\"']?", re.I)
HREF_IN_TAG_RE = re.compile(
    r"href\s*=\s*(?:\"([^\"]*)\"|'([^']*)'|([^\s\"'=<>`]+))", re.I)
CONTENT_IN_TAG_RE = re.compile(
    r"content\s*=\s*(?:\"([^\"]*)\"|'([^']*)'|([^\s\"'=<>`]+))", re.I)


def _first_group(m):
    if m is None:
        return ""
    return m.group(1) if m.group(1) is not None else (
        m.group(2) if m.group(2) is not None else (m.group(3) or ""))


def site_hosts(html):
    """本页声明的"自己"的主机名（canonical / og:url），用于区分同源与外链。

    没有这一步，修复 minify 漏检后（TEST-DEFECT-002）会立刻把站点自身的绝对 URL
    （canonical、og:url）当成"第三方域名"误报。
    """
    hosts = set()
    for tag in LINK_TAG_RE.findall(html):
        if CANONICAL_IN_TAG_RE.search(tag):
            hm = ANY_URL_RE.match(_first_group(HREF_IN_TAG_RE.search(tag)))
            if hm:
                hosts.add(hm.group(1).lower())
    for tag in META_TAG_RE.findall(html):
        if OGURL_IN_TAG_RE.search(tag):
            hm = ANY_URL_RE.match(_first_group(CONTENT_IN_TAG_RE.search(tag)))
            if hm:
                hosts.add(hm.group(1).lower())
    return hosts


def check_html(path, rel, hits):
    try:
        html = open(path, encoding="utf-8").read()
    except (UnicodeDecodeError, OSError):
        return
    low = html.lower()

    # 1 危险 URL scheme
    for attr, url in url_attrs(html):
        u = url.strip().lower().replace("\t", "").replace("\n", "")
        for scheme in DANGEROUS_URL_SCHEMES:
            if u.startswith(scheme):
                hits.append(("dangerous-url-scheme", rel,
                             f'{attr}="{url[:60]}"'))
        if u == "":
            hits.append(("empty-href", rel, f'{attr}=""'))

    # 2 target=_blank 缺 noopener
    for m in re.finditer(r"<a[^>]*>", html, re.I):
        tag = m.group(0)
        if 'target="_blank"' in tag or "target=_blank" in tag:
            if "noopener" not in tag.lower():
                hits.append(("target-blank-no-noopener", rel, tag[:80]))

    # 3 inline event handler
    for m in HANDLER_RE.finditer(low):
        name = "on" + m.group(1)
        if name not in ALLOWED_HANDLERS:
            hits.append(("inline-handler", rel, name))

    # 4 非预期外部 script
    for src in script_srcs(html):
        if src.startswith("data:"):
            hits.append(("data-url-script", rel, src[:60]))
            continue
        if src.startswith("/") or src.startswith("."):
            continue
        m = re.search(r"https?://([^/]+)", src)
        if m and not host_allowed(m.group(1), ALLOWED_SCRIPT_HOSTS):
            hits.append(("unexpected-external-script", rel, src[:80]))

    # 5 非预期 iframe
    for tag in IFRAME_RE.findall(html):
        if "giscus" not in tag and "twitter" not in tag:
            hits.append(("unexpected-iframe", rel, tag[:80]))

    # 6 非预期第三方域名（**仅 <a> 外链**，且放行本页声明的同源主机）
    own = site_hosts(html)
    for tag in A_TAG_RE.findall(html):
        m = HREF_IN_TAG_RE.search(tag)
        if not m:
            continue
        url = _first_group(m)
        if not url.lower().startswith("http"):
            continue
        hm = ANY_URL_RE.match(url)
        if hm and hm.group(1).lower() in own:
            continue                       # 同源（canonical/og:url 声明的主机）
        if hm and not host_allowed(hm.group(1)):
            hits.append(("unexpected-third-party-domain", rel, url[:80]))


# ---------- 浮层（dialog 型 modal）无障碍契约 ----------
# 任何新增 modal 都必须满足：role / aria-modal / 可访问名称（静态层）；
# 交互层（focus owner / focus restore / Escape / 背景 inert）由
# tools/verify_search_modal.py 与 tools/verify_lightbox.py 在浏览器里验证。
OVERLAY_REQUIRED_ATTRS = ("role=", "aria-modal=", "aria-label=")
OVERLAY_A11Y_HITS = []
OVERLAY_RE = re.compile(
    r'<(?:div|section)[^>]*class=(?:"[^"]*"|\'[^\']*\'|[^\s>]+)'
    r'[^>]*>', re.I)


def check_overlays(build_dir, hits):
    for dirpath, _, names in os.walk(build_dir):
        for n in names:
            if not n.endswith(".html"):
                continue
            f = os.path.join(dirpath, n)
            rel = os.path.relpath(f, build_dir).replace("\\", "/")
            try:
                html = open(f, encoding="utf-8").read()
            except (UnicodeDecodeError, OSError):
                continue
            for tag in OVERLAY_RE.findall(html):
                if "role=" not in tag:
                    continue                    # 不是 dialog 型浮层
                if not re.search(r'(overlay|lightbox|modal)', tag, re.I):
                    continue                    # class 不是浮层
                missing = [a for a in OVERLAY_REQUIRED_ATTRS if a not in tag]
                if missing:
                    hits.append(("dialog-aria", rel,
                                 f"浮层缺少 {', '.join(missing)} :: {tag[:70]}"))
                else:
                    OVERLAY_A11Y_HITS.append(rel)


def check_source(root, hits, wl_hits):
    """主题源码：危险 JS API + unsafe 配置。"""
    targets = []
    for sub in ("layouts", "assets"):
        d = os.path.join(root, sub)
        for dirpath, _, names in os.walk(d):
            for n in names:
                if n.endswith((".html", ".js")):
                    targets.append(os.path.join(dirpath, n))
    for f in targets:
        rel = os.path.relpath(f, root).replace("\\", "/")
        try:
            src = open(f, encoding="utf-8").read()
        except (UnicodeDecodeError, OSError):
            continue
        for pat, label in DANGEROUS_JS:
            for m in re.finditer(pat, src):
                # 表达式可能跨多行，按**起始行**取整行内容做判定
                line = src[src.rfind("\n", 0, m.start()) + 1:
                           src.find("\n", m.start())]
                # 已转义后拼接视为安全：表达式可能跨行，esc() 常写在下一行，
                # 因此对**整段匹配**做检测，而不是只看起始行
                if re.search(r"\besc(apeHtml)?\s*\(|textContent", m.group(0)):
                    wl_hits.append(f"{rel}: innerHTML 拼接已转义（{label}）")
                    continue
                # 显式行级白名单
                key = (rel.replace("\\", "/"), line.strip()[:40])
                if key in ALLOWED_JS_LINES:
                    wl_hits.append(f"{rel}: 行级白名单（{label}）—— "
                                   f"{ALLOWED_JS_LINES[key]}")
                    continue
                hits.append(("dangerous-js-api", rel, label))
        if re.search(r"""(href|src|action)\s*=\s*["']?\s*(javascript|vbscript):""",
                     src, re.I):
            hits.append(("dangerous-url-scheme", rel, "模板中写死 javascript:/vbscript:"))

    # unsafe 配置：exampleSite 默认必须 false
    for cfg in (os.path.join(root, "exampleSite", "hugo.toml"),):
        if not os.path.isfile(cfg):
            continue
        text = open(cfg, encoding="utf-8").read()
        m = re.search(r"\[markup\.goldmark\.renderer\][^\[]*?unsafe\s*=\s*(\w+)", text)
        if m and m.group(1).lower() == "true":
            hits.append(("goldmark-unsafe-true",
                         os.path.relpath(cfg, root).replace("\\", "/"),
                         "markup.goldmark.renderer.unsafe = true"))
        elif not m:
            wl_hits.append(f"{os.path.basename(cfg)}: 未显式声明 unsafe（按默认 false 处理）")


def run(h):
    if not os.path.isdir(BUILD_DIR):
        h.fatal_error("构建目录不存在", BUILD_DIR)
        return
    hits, wl_hits = [], []
    n = 0
    for dirpath, _, names in os.walk(BUILD_DIR):
        for name in names:
            if name.endswith(".html"):
                n += 1
                rel = os.path.relpath(os.path.join(dirpath, name), BUILD_DIR)
                check_html(os.path.join(dirpath, name), rel.replace("\\", "/"), hits)
    check_overlays(BUILD_DIR, hits)
    check_source(THEME, hits, wl_hits)
    print(f"扫描 HTML 文件: {n} 个；主题源码: {THEME}")

    # 空扫描保护：构建产物一个 HTML 都没有时，"0 违规"毫无意义。
    # （TEST-DEFECT-008：旧实现会把"产物缺失"当成"安全"而 PASS。）
    if n == 0:
        h.fatal_error("未扫描到任何 HTML 文件（构建产物缺失或路径错误）", BUILD_DIR)
        return

    # 浮层 dialog 语义（role / aria-modal / 可访问名称）
    if OVERLAY_A11Y_HITS:
        print(f"浮层 dialog 语义合规: {len(OVERLAY_A11Y_HITS)} 处")
        for item in OVERLAY_A11Y_HITS[:6]:
            print("   ", item)

    # 白名单命中（必须可见）
    if wl_hits:
        print(f"白名单/默认命中（需人工确认）: {len(wl_hits)}")
        for s in wl_hits:
            print("   ", s)

    if hits:
        by = {}
        for kind, where, detail in hits:
            by.setdefault(kind, []).append(f"{where} :: {detail}")
        for kind, items in sorted(by.items()):
            print(f"\n### {kind}  x{len(items)}")
            for s in items[:6]:
                print("   ", s)

    h.record("安全基线：构建产物与主题源码无危险模式",
             not hits, f"{n} 个 HTML，{len(hits)} 个违规")
    # 分项记录，便于定位
    for kind in ("dangerous-url-scheme", "empty-href", "target-blank-no-noopener",
                 "inline-handler", "unexpected-external-script", "unexpected-iframe",
                 "unexpected-third-party-domain", "dangerous-js-api",
                 "goldmark-unsafe-true", "data-url-script"):
        cnt = len([x for x in hits if x[0] == kind])
        if cnt:
            h.record(f"安全项 {kind}", False, f"{cnt} 处")


if __name__ == "__main__":
    main_h = Harness("security")
    guard(main_h, run, main_h)
    main_h.finish()
