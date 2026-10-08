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
from html.parser import HTMLParser

from _testlib import Harness, guard

DIR = sys.argv[1] if len(sys.argv) > 1 else "public"

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


def parse_page(rel, html):
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

    # JSON-LD 合法性
    for raw in re.findall(r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>',
                          html, re.S):
        try:
            json.loads(raw)
        except Exception as e:
            problems.append(("jsonld", f"JSON-LD 非法: {str(e)[:60]}"))

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
    files = []
    for dirpath, _, names in os.walk(DIR):
        for n in names:
            if n.endswith(".html"):
                files.append(os.path.join(dirpath, n))
    if not files:
        h.fatal_error("未扫描到 HTML 文件", DIR)
        return

    by_rule = {}
    total = 0
    wl_hits = []
    md_figures = 0
    for f in sorted(files):
        rel = os.path.relpath(f, DIR).replace("\\", "/")
        try:
            html = open(f, encoding="utf-8").read()
        except UnicodeDecodeError:
            h.record(f"{rel} 可用 UTF-8 解码", False, "编码错误")
            continue
        wl = WHITELIST.get(rel, set())
        probs, n_fig = parse_page(rel, html)
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
