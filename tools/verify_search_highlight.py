#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""搜索高亮回归：特殊字符必须"能搜到"，且高亮不能破坏 HTML / 不能注入脚本。

为什么单独测
------------
highlight() 的实现顺序是「先 esc 文本，再做正则替换包 <mark>」——
一旦顺序反了、或漏掉某个字符，就会出现：

  * 文本被浏览器当成标签解析（`<hello>` 变成元素，文本消失）
  * 出现无效实体（`&amp;amp;` 双重转义、`&lt;mark&gt;` 被当成标签）
  * 正则元字符未转义 -> 查询报语法错误，或把 `.` 当通配符匹配到不该匹配的项
  * 最坏情况：查询串 / 索引内容里的 `<img onerror=...>` 被写进 innerHTML -> XSS

本测试用 Playwright 拦截 `/index.json`，注入一份**刻意构造的恶意/边界内容**
（不修改站点源码、不需要额外构建），逐项验证渲染结果。

用法：python tools/verify_search_highlight.py <base_url> [browser]
退出码约定（见 tools/_testlib.py）：断言失败 / 浏览器启动失败 -> exit 1。
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _testlib import Harness, launch as _launch, reachable, guard  # noqa: E402

from playwright.sync_api import sync_playwright  # noqa: E402

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8088"
BROWSER = sys.argv[2] if len(sys.argv) > 2 else "chromium"

H = Harness("search-highlight")

# 刻意构造的边界内容：HTML 标签 / 实体 / 正则元字符 / 引号 / XSS
CRAFTED = [
    {
        "title": "A&B <hello>",
        "url": "/posts/amp-tag/",
        "date": "2026-09-28",
        "dateDisplay": "2026年9月28日",
        "summary": "标签与和号",
        "content": "A&B <hello> 正文",
        "key": "amp-tag",
        "tags": ["tag&1"],
        "categories": [],
        "series": [],
    },
    {
        "title": "foo&bar",
        "url": "/posts/foo-bar/",
        "date": "2026-09-29",
        "dateDisplay": "2026年9月29日",
        "summary": "和号连写",
        "content": "foo&bar baz",
        "key": "foo-bar",
        "tags": [],
        "categories": [],
        "series": [],
    },
    {
        "title": "REGEX.*+?^${}()|[]\\",
        "url": "/posts/regex/",
        "date": "2026-09-30",
        "dateDisplay": "2026年9月30日",
        "summary": "正则元字符",
        "content": "REGEX.*+?^${}()|[]\\ 正文",
        "key": "regex",
        "tags": [],
        "categories": [],
        "series": [],
    },
    {
        "title": 'quote "double" and \'single\'',
        "url": "/posts/quotes/",
        "date": "2026-10-01",
        "dateDisplay": "2026年10月1日",
        "summary": "引号",
        "content": 'quote "double" and \'single\'',
        "key": "quotes",
        "tags": [],
        "categories": [],
        "series": [],
    },
    {
        "title": "<mark>already</mark> marked",
        "url": "/posts/mark/",
        "date": "2026-10-02",
        "dateDisplay": "2026年10月2日",
        "summary": "已有 mark 标签文本",
        "content": "<mark>already</mark> marked",
        "key": "mark",
        "tags": [],
        "categories": [],
        "series": [],
    },
    {
        "title": '<img src=x onerror="window.__xss=1">',
        "url": "/posts/xss/",
        "date": "2026-10-03",
        "dateDisplay": "2026年10月3日",
        "summary": "注入尝试",
        "content": '<img src=x onerror="window.__xss=1"> payload',
        "key": "xss",
        "tags": [],
        "categories": [],
        "series": [],
    },
    {
        "title": "tom &amp; jerry",
        "url": "/posts/entity/",
        "date": "2026-10-04",
        "dateDisplay": "2026年10月4日",
        "summary": "已经是实体的文本",
        "content": "tom &amp; jerry",
        "key": "entity",
        "tags": [],
        "categories": [],
        "series": [],
    },
]

PROBE_JS = """
() => {
  const items = Array.from(document.querySelectorAll('.search-item'));
  return items.map(el => {
    const t = el.querySelector('.t');
    return {
      html: t ? t.innerHTML : '',
      text: t ? t.textContent : '',
      marks: t ? t.querySelectorAll('mark').length : 0,
      nested: t ? t.querySelectorAll('mark mark').length : 0,
      imgs: el.querySelectorAll('img').length,
      scripts: el.querySelectorAll('script').length,
      href: el.getAttribute('href') || ''
    };
  });
}
"""


def search(page, kw, wait=600):
    page.fill("#search-input", "")
    page.fill("#search-input", kw)
    page.wait_for_timeout(wait)
    return page.evaluate(PROBE_JS)


def _run_all():
    with sync_playwright() as p:
        launcher = {"chromium": p.chromium, "firefox": p.firefox,
                    "webkit": p.webkit}.get(BROWSER)
        if launcher is None:
            H.fatal_error("未知浏览器", BROWSER)
            return
        try:
            b = _launch(launcher)
        except Exception as e:
            H.fatal_error(f"{BROWSER} 浏览器启动失败", str(e)[:200])
            return
        console_errors = []
        page_errors = []
        ctx = b.new_context(viewport={"width": 1440, "height": 900}, locale="zh-CN")

        def fake_index(route):
            route.fulfill(status=200, content_type="application/json",
                          body=json.dumps(CRAFTED, ensure_ascii=False))
        ctx.route("**/index.json", fake_index)

        page = ctx.new_page()
        page.on("console", lambda m: console_errors.append(m.text[:200])
                if m.type == "error" else None)
        page.on("pageerror", lambda e: page_errors.append(str(e)[:200]))
        page.goto(BASE + "/", wait_until="load")
        page.click("#searchTrigger")
        page.wait_for_timeout(900)

        # ---------- ① & 与 < > ----------
        rows = search(page, "A&B")
        hit = [r for r in rows if "A&B" in r["text"]]
        H.record("查询 A&B 能搜到，且 <hello> 被当作文本而非标签",
                 len(hit) == 1 and hit and hit[0]["text"] == "A&B <hello>",
                 f"{len(hit)} 条，text={hit[0]['text']!r}" if hit
                 else f"{len(rows)} 条，未命中")
        if hit:
            H.record("高亮未产生无效实体（无 &amp;amp; / &amp;lt; / &amp;gt;）",
                     not re.search(r"&amp;(amp|lt|gt|quot);", hit[0]["html"]),
                     hit[0]["html"][:120])
            H.record("高亮未把 <hello> 变成标签（DOM 中没有 hello 元素）",
                     page.evaluate("() => document.querySelectorAll('hello').length") == 0,
                     "hello 元素数 = 0")

        # ---------- ② 纯和号 ----------
        rows = search(page, "foo&bar")
        hit = [r for r in rows if r["text"] == "foo&bar"]
        H.record("查询 foo&bar 命中且文本完整",
                 len(hit) == 1, f"{len(hit)} 条")

        # ---------- ③ 正则元字符 ----------
        rows = search(page, "REGEX.*+?^${}()|[]\\")
        hit = [r for r in rows if "REGEX" in r["text"]]
        H.record("正则元字符查询按字面匹配（不报错、不误匹配全部）",
                 len(hit) == 1, f"{len(hit)} 条命中（索引共 {len(CRAFTED)} 条）")
        if hit:
            H.record("正则元字符高亮后文本与原文一致",
                     hit[0]["text"] == "REGEX.*+?^${}()|[]\\", f"{hit[0]['text']!r}")
        H.record("正则元字符查询未抛出 JS 异常",
                 not [e for e in page_errors if "RegExp" in e or "Invalid" in e],
                 f"pageerror={len(page_errors)}")

        # ---------- ④ 引号 ----------
        rows = search(page, "quote")
        hit = [r for r in rows if "quote" in r["text"]]
        H.record("含双引号/单引号的标题渲染不破坏结构",
                 len(hit) == 1 and "'single'" in hit[0]["text"]
                 and '"double"' in hit[0]["text"],
                 f"{hit[0]['text']!r}" if hit else f"{len(rows)} 条")

        # ---------- ⑤ 已有 <mark> 文本 ----------
        rows = search(page, "mark")
        hit = [r for r in rows if "already" in r["text"]]
        H.record("标题里的字面 <mark> 渲染为文本，不产生嵌套 <mark>",
                 bool(hit) and hit[0]["text"] == "<mark>already</mark> marked"
                 and hit[0]["nested"] == 0,
                 f"text={hit[0]['text']!r} nested={hit[0]['nested']}" if hit
                 else "未命中")

        # ---------- ⑥ XSS ----------
        # ⚠ 非空断言：旧实现用 all(r["imgs"] == 0 for r in rows)，
        #   当 rows 为空时 all() 恒为 True -> XSS 检查"全空过"（TEST-DEFECT-010）。
        #   必须先证明"确实搜到了注入条目"，再看它有没有被渲染成真实元素。
        rows = search(page, "onerror")
        H.record("注入型条目确实被搜到（否则后面的 XSS 断言是空转）",
                 len(rows) >= 1, f"{len(rows)} 条")
        H.record("注入型内容渲染为文本：结果里没有真实 <img> 元素",
                 len(rows) >= 1 and all(r["imgs"] == 0 for r in rows),
                 f"{sum(r['imgs'] for r in rows)} 个 img 元素（{len(rows)} 条结果）")
        H.record("注入型内容未执行脚本（window.__xss 未定义）",
                 page.evaluate("() => typeof window.__xss === 'undefined'"),
                 "window.__xss 未定义")
        H.record("结果里没有 <script> 元素",
                 len(rows) >= 1 and all(r["scripts"] == 0 for r in rows),
                 f"{sum(r['scripts'] for r in rows)} 个 script（{len(rows)} 条结果）")
        rows = search(page, "payload")
        H.record("XSS 条目确实被搜到", len(rows) >= 1, f"{len(rows)} 条")
        H.record("XSS 条目的 href 仍是构造时的相对 URL（未被注入协议）",
                 len(rows) >= 1 and all(r["href"] in ("", "/posts/xss/") for r in rows),
                 f"href={[r['href'] for r in rows][:3]}")

        # ---------- ⑦ 源文本里本身就带 HTML 实体 ----------
        # 正确语义：**原样呈现源字符串**。索引里存的是 "tom &amp; jerry"，
        # esc() 转义一次后写进 innerHTML，textContent 应当仍是同一个字符串。
        # （`&amp;amp;` 是合法实体，渲染出来的就是字面量 "&amp;" —— 不丢字、不破结构。
        #  反过来"识别实体不再转义"才会把源文本改掉。）
        rows = search(page, "jerry")
        hit = [r for r in rows if "jerry" in r["text"]]
        src_text = "tom &amp; jerry"
        H.record("源文本含 HTML 实体时原样呈现（不丢字、不变形）",
                 bool(hit) and hit[0]["text"] == src_text,
                 f"text={hit[0]['text']!r}" if hit else "未命中")
        H.record("渲染结果里没有残缺实体（裸 & 必须已转成 &amp;/&lt;/&gt;/&quot;）",
                 bool(hit) and not re.search(r"&(?!(amp|lt|gt|quot|#\d+|#x[0-9a-fA-F]+);)",
                                             hit[0]["html"]),
                 f"html={hit[0]['html'][:80]!r}" if hit else "未命中")

        # ---------- ⑧ 总体 ----------
        H.record("全过程无 console error",
                 not console_errors, f"{len(console_errors)} 条：{console_errors[:2]}")
        H.record("全过程无未捕获 JS 异常",
                 not page_errors, f"{len(page_errors)} 条：{page_errors[:2]}")

        ctx.close()
        b.close()


def main():
    if not reachable(BASE + "/"):
        H.fatal_error("被测站点不可达", BASE)
        H.finish()
    guard(H, _run_all)
    H.finish()


if __name__ == "__main__":
    main()
