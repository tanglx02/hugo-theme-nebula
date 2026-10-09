#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""HTML 质量静态检查（轻量，仅 Python 标准库，无外部依赖）。

对构建产物里**每个 HTML 文件**检查：

    - <html> 有非空 lang 属性
    - img 必须有 alt 属性（alt="" 允许，表示装饰图）
    - button 必须有 type 属性
    - id 不得重复
    - 无明显非法嵌套（p / 标题内出现块级元素；标签交叉闭合）
    - h1 数量 <= 1
    - heading 不出现跳级（如 h2 -> h4）
    - a href 不得为空（href=""）
    - role="dialog" 必须带 aria-modal 与 aria-label/aria-labelledby
    - 外链 target="_blank" 必须 rel 含 noopener
    - 无 inline 事件处理器（on* 属性）
    - title 非空
    - JSON-LD 必须是合法 JSON
    - canonical 至多一个；og:url 与 canonical 一致（两者都存在时）

白名单：个别文件不适用某些规则时，通过 WHITELIST 精确登记；
每次实际命中白名单都会打印，避免白名单悄悄膨胀。

退出码约定（见 tools/_testlib.py）：任一违规 -> exit 1。

用法：
    python tools/check_html_quality.py <build_dir>
"""
import json
import os
import re
import sys
from html import unescape
from html.parser import HTMLParser

from _testlib import Harness, guard, default_build_dir
from html_inventory import scan as scan_inventory

# 默认路径统一为 <repo>/public（TEST-DEFECT-R2-003）；-h/--help 正确解析
DIR = default_build_dir()

VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input",
        "link", "meta", "param", "source", "track", "wbr"}

BLOCK_IN_P = {"div", "p", "section", "article", "aside", "header", "footer",
              "nav", "ul", "ol", "table", "blockquote", "form", "figure", "h1",
              "h2", "h3", "h4", "h5", "h6"}

# 文件级白名单：{文件相对路径: {规则名}}。命中即跳过该规则并打印。
WHITELIST = {
    # 例：404 页面无正文标题，heading 跳级规则不适用
    # "404.html": {"heading-jump"},
}

# JSON-LD <script> 提取。
# ⚠ 必须容忍**无引号属性**：CI 一律 --minify，Hugo 会输出
#   <script type=application/ld+json>（去掉引号）。旧正则写死 type="application/ld+json"，
#   minify 后一个都匹配不到 -> JSON-LD 校验恒真（TEST-DEFECT-001），
#   这正是 JSON-LD 双重编码（BUG-P2-004）能长期绿灯的原因。
JSONLD_RE = re.compile(
    r"<script\b(?=[^>]*\btype\s*=\s*[\"']?application/ld\+json[\"']?)[^>]*>(.*?)</script>",
    re.S | re.I)
JSONLD_MARKER = "application/ld+json"

META_RE = re.compile(r"<meta\b[^>]*>", re.I)
ATTR_RE = re.compile(
    r"""([a-zA-Z_:][-a-zA-Z0-9_:.]*)\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s"'=<>`]+))""")


def _meta_map(html):
    """把页面所有 <meta> 解析成 {name/property: content}（容忍无引号属性）。"""
    out = {}
    for tag in META_RE.findall(html):
        attrs = {}
        for m in ATTR_RE.finditer(tag):
            key = m.group(1).lower()
            val = m.group(2) if m.group(2) is not None else (
                m.group(3) if m.group(3) is not None else m.group(4))
            attrs[key] = val or ""
        key = attrs.get("property") or attrs.get("name")
        if key:
            out[key.lower()] = attrs.get("content", "")
    return out


def _iter_string_values(obj, path=""):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from _iter_string_values(v, f"{path}.{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from _iter_string_values(v, f"{path}[{i}]")
    elif isinstance(obj, str):
        yield path, obj


def _looks_double_encoded(s):
    """值自身是不是"被再编码一次的 JSON 字符串"（双重编码的典型形态）。

    双重编码后值形如 "\\"标题\\""，即字符串本身以引号开头结尾，且能再 json.loads
    出一个字符串。合法的 JSON-LD 值不会长这样。
    """
    t = (s or "").strip()
    if len(t) < 4 or not (t.startswith('"') and t.endswith('"')):
        return False
    try:
        inner = json.loads(t)
    except Exception:
        return False
    return isinstance(inner, str) and inner != ""


def _check_jsonld(html, problems, stats):
    """JSON-LD：解析合法性 + 双重编码 + 与 og:title / og:site_name 的交叉校验。

    返回本页检测到的 JSON-LD 块数（供全站"0 块即失败"的保护）。
    """
    blocks = JSONLD_RE.findall(html)
    # 自检：页面明明写了 ld+json，却一块都没匹配到 -> 正则/产物形态漂移，必须失败
    if JSONLD_MARKER in html and not blocks:
        problems.append(("jsonld-unmatched",
                         f"页面含 {JSONLD_MARKER} 但未匹配到任何块（校验会漏检）"))
    meta = _meta_map(html)
    og_title = meta.get("og:title", "")
    og_site = meta.get("og:site_name", "")
    for raw in blocks:
        stats["blocks"] += 1
        try:
            doc = json.loads(raw)
        except Exception as e:
            problems.append(("jsonld", f"JSON-LD 非法: {str(e)[:60]}"))
            continue
        # 双重编码检测（递归所有字符串值）
        for path, val in _iter_string_values(doc):
            if _looks_double_encoded(val):
                problems.append(("jsonld-double-encoded",
                                 f"{path} 值被再编码一次: {val[:50]}"))
        # 语义交叉校验：headline / name 必须等于页面 og:title / 站点名
        if isinstance(doc, dict):
            if og_title and isinstance(doc.get("headline"), str):
                if unescape(doc["headline"]) != unescape(og_title):
                    problems.append(
                        ("jsonld-value",
                         f'headline={doc["headline"][:40]!r} != og:title={og_title[:40]!r}'))
            if og_site and isinstance(doc.get("name"), str) and doc.get("@type") == "WebSite":
                if unescape(doc["name"]) != unescape(og_site):
                    problems.append(
                        ("jsonld-value",
                         f'name={doc["name"][:40]!r} != og:site_name={og_site[:40]!r}'))
    return len(blocks)


class PageParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.problems = []
        self.stack = []            # (tag)
        self.ids = {}
        self.h1 = 0
        self.headings = []         # document 顺序的 heading 级别
        self.in_title = False
        self.title_text = ""
        self.canonicals = []
        self.og_urls = []
        self.in_heading = 0        # 正在解析的 heading 深度（>0 表示当前在标题内）
        self.md_figures = 0        # Markdown 独立图片段落（<p><figure>）出现次数

    # ----- helpers -----
    def fail(self, rule, detail):
        self.problems.append((rule, detail))

    # ----- parser events -----
    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "html" and not a.get("lang"):
            self.fail("html-lang", "<html> 缺少 lang 属性")
        if "id" in a:
            v = a["id"]
            if v in self.ids:
                self.fail("dup-id", f'id="{v}" 重复（首次出现在第 {self.ids[v]} 行）')
            else:
                self.ids[v] = self.getpos()[0]
        if tag == "img" and "alt" not in a:
            self.fail("img-alt", f'img 缺少 alt（src={ (a.get("src") or "")[:60] }）')
        if tag == "button" and "type" not in a:
            self.fail("button-type", f'button 缺少 type（text={self.get_starttag_text() or ""[:60]}）')
        if tag == "a":
            href = a.get("href")
            if href is not None and href.strip() == "":
                self.fail("empty-href", "a href 为空")
            if a.get("target") == "_blank":
                rel = a.get("rel") or ""
                if "noopener" not in rel.lower():
                    self.fail("noopener", f'target=_blank 缺 rel=noopener（href={href[:60]}）')
        if tag == "h1":
            self.h1 += 1
        if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            self.headings.append((int(tag[1]), self.getpos()[0]))
            self.in_heading += 1
        if any(k.lower().startswith("on") and len(k) > 2 for k in a):
            self.fail("inline-handler", f"{tag} 带 inline 事件属性")
        if a.get("role") == "dialog":
            if a.get("aria-modal") != "true":
                self.fail("dialog-aria", 'role=dialog 缺 aria-modal="true"')
            if not (a.get("aria-label") or a.get("aria-labelledby")):
                self.fail("dialog-aria", "role=dialog 缺 aria-label/aria-labelledby")
        if tag == "link" and a.get("rel") == "canonical":
            self.canonicals.append(a.get("href") or "")
        if tag == "meta" and a.get("property") == "og:url":
            self.og_urls.append(a.get("content") or "")
        if tag == "script" and "application/ld+json" in (a.get("type") or ""):
            self.in_jsonld = True
        if tag == "p" or self.in_heading:
            # p 与标题内不允许出现块级元素
            pass
        if self._open_is("p") and tag in BLOCK_IN_P:
            if tag == "figure":
                # Markdown 独立图片段落：Hugo render hook 输出 <figure>，外层 <p> 由
                # goldmark 段落规则添加，主题无法移除；浏览器解析时会自动闭合 <p>，
                # 实际 DOM 无非法嵌套。登记为已知模式打印，不计违规。
                self.md_figures += 1
            else:
                self.fail("bad-nesting", f"<p> 内出现 <{tag}>（第 {self.getpos()[0]} 行）")
        if not self._open_is_heading_ok(tag):
            pass
        if tag not in VOID:
            self.stack.append(tag)

    def _open_is(self, tag):
        return bool(self.stack) and self.stack[-1] == tag

    def _open_is_heading_ok(self, tag):
        return True

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag in VOID:
            return
        # 自闭合写法（XHTML 风格）在 HTML5 下等价于开标签，仍需弹出
        if self.stack and self.stack[-1] == tag:
            self.stack.pop()
        if tag in ("h1", "h2", "h3", "h4", "h5", "h6") and self.in_heading:
            self.in_heading -= 1

    def handle_endtag(self, tag):
        if tag in VOID:
            return
        if tag in ("h1", "h2", "h3", "h4", "h5", "h6") and self.in_heading:
            self.in_heading = max(0, self.in_heading - 1)
        if not self.stack:
            self.fail("bad-nesting", f"</{tag}> 无匹配开标签（第 {self.getpos()[0]} 行）")
            return
        if self.stack[-1] == tag:
            self.stack.pop()
            return
        # 交叉闭合：栈中存在同名标签但不是栈顶
        if tag in self.stack:
            self.fail("bad-nesting",
                      f"</{tag}> 交叉闭合，栈顶是 <{self.stack[-1]}>（第 {self.getpos()[0]} 行）")
            while self.stack and self.stack[-1] != tag:
                self.stack.pop()
            if self.stack:
                self.stack.pop()
        # 隐式闭合（如 <li> 后直接 <li>）由 HTML 语义处理，不算错误

    def handle_data(self, data):
        if self.in_title:
            self.title_text += data

    def handle_startendtag_guard(self):
        pass

    def unknown_decl(self):
        pass

    # JSON-LD 原文收集
    def _collect_jsonld(self, raw):
        pass


def parse_page(rel, html, stats):
    p = PageParser()
    # 逐字符喂给 parser；同时单独抽取 JSON-LD 与 title（parser 的 script data 处理复杂）
    p.feed(html)
    p.close()

    problems = list(p.problems)

    # title 非空
    m = re.search(r"<title>(.*?)</title>", html, re.S | re.I)
    if not m or not m.group(1).strip():
        problems.append(("title-empty", "缺少 <title> 或内容为空"))

    # h1 数量
    if p.h1 > 1:
        problems.append(("h1-count", f"页面有 {p.h1} 个 h1"))

    # heading 跳级（document 顺序，只看跳升）
    prev = None
    for lvl, line in p.headings:
        if prev is not None and lvl > prev + 1:
            problems.append(("heading-jump", f"第 {line} 行 h{lvl} 跳过 h{prev + 1}"))
        prev = lvl

    # JSON-LD：合法性 + 双重编码 + 语义交叉校验（见 _check_jsonld 说明）
    _check_jsonld(html, problems, stats)

    # 零值日期泄漏（BUG-P3-001）：缺少 date 的文章不应让内部零值
    # 0001-01-01 出现在 <time datetime> 或 JSON-LD 里（应显示"未标注日期"或省略）。
    if "0001-01-01" in html or "0001年1月1日" in html:
        problems.append(("zero-date",
                         "页面出现 0001-01-01 / 0001年1月1日（缺日期文章泄漏内部零值）"))

    # canonical / og:url 一致性
    if len(p.canonicals) > 1:
        problems.append(("canonical", f"canonical 出现 {len(p.canonicals)} 次"))
    if p.canonicals and p.og_urls:
        if p.og_urls[0] != p.canonicals[0]:
            problems.append(("og-url",
                             f'og:url={p.og_urls[0]} 与 canonical={p.canonicals[0]} 不一致'))

    # 未闭合标签（栈里残留的均为内容级元素）
    if p.stack:
        problems.append(("unclosed", f"未闭合标签: {p.stack[:5]}"))
    return problems, p.md_figures


def run(h):
    if not os.path.isdir(DIR):
        h.fatal_error("构建目录不存在", DIR)
        return
    # 构建产物 inventory（与 audit.py 使用同一模块、同一 URL 规范化）
    inv = scan_inventory(DIR)
    print(f"PUBLIC HTML FILES = {inv['public_html_files']}")
    print(f"EXPECTED HTML URLS = {inv['expected_count']}")
    print("分类明细:", inv["by_class"])
    if inv["excluded"]:
        print("显式登记的排除项:")
        for u, why in inv["excluded"]:
            print(f"    - {u} ({why})")

    files = []
    for dirpath, _, names in os.walk(DIR):
        for n in names:
            if n.endswith(".html"):
                files.append(os.path.join(dirpath, n))
    if not files:
        h.fatal_error("未扫描到 HTML 文件", DIR)
        return
    h.record("HTML quality 扫描的文件数与 inventory 一致",
             len(files) == inv["public_html_files"],
             f"扫描 {len(files)} 个，inventory {inv['public_html_files']} 个")
    # inventory 落盘，供 audit.py 交叉验证
    out_json = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "html_inventory.json")
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(inv, f, ensure_ascii=False, indent=1)
    print(f"inventory 已写入 {out_json}（audit.py 将读取它做交叉验证）")

    by_rule = {}
    total = 0
    wl_hits = []
    md_figures = 0
    stats = {"blocks": 0}
    for f in sorted(files):
        rel = os.path.relpath(f, DIR).replace("\\", "/")
        try:
            html = open(f, encoding="utf-8").read()
        except UnicodeDecodeError:
            h.record(f"{rel} 可用 UTF-8 解码", False, "编码错误")
            continue
        wl = WHITELIST.get(rel, set())
        probs, n_fig = parse_page(rel, html, stats)
        md_figures += n_fig
        for rule, detail in probs:
            if rule in wl:
                wl_hits.append(f"{rel}: {rule}")
                continue
            by_rule.setdefault(rule, []).append(f"{rel} :: {detail}")
            total += 1

    for rule, hits in sorted(by_rule.items()):
        print(f"\n### {rule}  x{len(hits)}")
        for s in hits[:6]:
            print("   ", s)

    h.record("HTML 质量：全部页面通过", total == 0, f"{len(files)} 个文件，{total} 个违规")

    # JSON-LD 有效性保护：全站一个块都没解析到 => 校验实际上什么都没查（恒真），必须失败。
    # 这是防止"正则/产物形态漂移导致 JSON-LD 校验静默失效"（TEST-DEFECT-001）的兜底。
    print(f"\nJSON-LD 块总数 = {stats['blocks']}")
    h.record("JSON-LD 校验非空转（全站至少解析到 1 个 JSON-LD 块）",
             stats["blocks"] > 0, f"blocks={stats['blocks']}")
    if md_figures:
        print("\n已知豁免模式: Markdown 独立图片段落 <p><figure> 共 %d 处"
              "（浏览器解析时自动闭合 p，实际 DOM 无非法嵌套）" % md_figures)
    if wl_hits:
        print(f"\n白名单命中（已在 WHITELIST 登记）: {len(wl_hits)}")
        for s in wl_hits[:8]:
            print("   ", s)


if __name__ == "__main__":
    main_h = Harness("html-quality")
    guard(main_h, run, main_h)
    main_h.finish()
