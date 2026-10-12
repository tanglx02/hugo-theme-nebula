#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Alias 页面专项静态检查（v1.0.9 P2）。

为什么单独检查
--------------
Hugo 会为每个分页第一页生成一份 **`page/1/` 形式的 meta-refresh 别名页**（本主题
示例站点 83 个）。这些页面：

  * 在构建产物 inventory 里 —— 所以 Release 全站审计会"加载"它们；
  * 但浏览器打开后会被立刻重定向到 canonical 页 —— 于是**浏览器里观察到的其实是
    目标页**，页面的真实结构没有被验证过。

因此不能把"全站浏览器审计通过"当成 alias 页合格的证据：alias 检查必须独立做、
静态做 —— 不依赖重定向后的最终状态。

对每个 alias HTML 检查：

  1. 文件真实存在
  2. 有且仅有一个 meta refresh，且带合法的延迟与 url 目标
  3. 有 canonical
  4. refresh target 合法（http/https 绝对 URL，路径非空）且存在于构建产物
  5. 不是自引用（target 不等于自己）
  6. 没有额外 JS（无 <script>）与 inline 事件处理器
  7. 没有破损的本地资源（link/img/script 引用的站内文件必须存在）
  8. lang 合法，且与站点其它页面使用同一语言集合
  9. 有非空 <title>

用法：python tools/check_alias_pages.py <build_dir>
退出码约定（见 tools/_testlib.py）：任一违规 / 无 alias 页 -> exit 1。
"""
import os
import re
import sys
from urllib.parse import urlparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _testlib import Harness, guard, default_build_dir  # noqa: E402
from html_inventory import scan as scan_inventory, normalize_url  # noqa: E402

# 默认路径统一为 <repo>/public（TEST-DEFECT-R2-003）；-h/--help 正确解析
DIR = default_build_dir()

REFRESH_RE = [
    re.compile(r'<meta[^>]*http-equiv=["\']?refresh["\']?[^>]*content=["\']([^"\']+)["\']', re.I),
    re.compile(r'<meta[^>]*content=["\']([^"\']+)["\'][^>]*http-equiv=["\']?refresh["\']', re.I),
]
CANONICAL_RE = re.compile(
    r'<link[^>]*rel=["\']?canonical["\']?[^>]*href=["\']?([^"\'> ]+)', re.I)
TITLE_RE = re.compile(r"<title>(.*?)</title>", re.I | re.S)
SCRIPT_RE = re.compile(r"<script", re.I)
INLINE_HANDLER_RE = re.compile(r"\son[a-z]+\s*=", re.I)
LOCAL_REF_RE = re.compile(r'<(?:link|img|script|source)[^>]*?(?:href|src)=["\']?([^"\'> ]+)', re.I)
HTML_LANG_RE = re.compile(r"<html[^>]*\slang=[\"']?([A-Za-z0-9_-]+)")
DELAY_RE = re.compile(r"\s*(\d+)\s*;")

BCP47_RE = re.compile(r"^[a-zA-Z]{2,3}(-[a-zA-Z]{2,8}){0,3}$")

H = Harness("alias-pages")


def collect_files(build_dir):
    """返回 {规范化 URL: 文件绝对路径}。"""
    mapping = {}
    for dirpath, _, names in os.walk(build_dir):
        for n in names:
            if not n.endswith(".html"):
                continue
            full = os.path.join(dirpath, n)
            rel = os.path.relpath(full, build_dir).replace("\\", "/")
            mapping.setdefault(normalize_url(rel), os.path.abspath(full))
    return mapping


def parse_refresh(html):
    """返回 (raw_content, delay_seconds, target_url)。"""
    for rx in REFRESH_RE:
        m = rx.search(html)
        if not m:
            continue
        content = m.group(1)
        d = DELAY_RE.match(content)
        delay = int(d.group(1)) if d else None
        t = re.search(r"url\s*=\s*(.+)$", content, re.I | re.S)
        target = t.group(1).strip().strip("'\"") if t else None
        return content, delay, target
    return None, None, None


def target_to_site_url(target, expected_set):
    """把 meta refresh 的绝对 URL 转成 inventory 的规范化路径。"""
    if not target:
        return None
    path = urlparse(target).path or "/"
    rel = path.lstrip("/")
    if not rel:
        return "/"
    cand = normalize_url(rel)
    if cand in expected_set:
        return cand
    # 兼容目标 URL 未 percent-encode 的情况：再尝试原样比对一次
    cand2 = "/" + rel
    return cand2 if cand2 in expected_set else cand


def run(h):
    if not os.path.isdir(DIR):
        h.fatal_error("构建目录不存在", DIR)
        return
    inv = scan_inventory(DIR)
    alias_urls = set(inv.get("urls_by_class", {}).get("alias", []))
    expected = set(inv.get("expected_html_urls") or [])
    files = collect_files(DIR)

    h.record("构建产物扫描到的 HTML 文件数与 inventory 一致",
             len(files) == inv["public_html_files"],
             f"文件 {len(files)} / inventory {inv['public_html_files']}")
    if not alias_urls:
        h.fatal_error("构建产物中没有 alias 页面",
                      "Inventory 未发现 meta-refresh 别名页，本检查失去对象——"
                      "若站点确实不应生成 alias，请显式登记这一预期")
        return

    # 站点主体页面使用的语言集合（alias 必须与之相同，不能自成一国）
    site_langs = set()
    for url, full in files.items():
        if url in alias_urls or url.endswith("/404.html"):
            continue
        try:
            head = open(full, encoding="utf-8", errors="ignore").read(4096)
        except OSError:
            continue
        m = HTML_LANG_RE.search(head)
        if m:
            site_langs.add(m.group(1).lower())

    problems = {}      # rule -> [detail]
    checked = 0

    def fail(rule, detail):
        problems.setdefault(rule, []).append(detail)

    for url in sorted(alias_urls):
        full = files.get(url)
        if not full or not os.path.isfile(full):
            fail("alias-file-missing", f"{url}：文件不存在")
            continue
        checked += 1
        rel_display = os.path.relpath(full, DIR).replace("\\", "/")
        try:
            html = open(full, encoding="utf-8", errors="ignore").read()
        except Exception as e:
            fail("alias-unreadable", f"{url}：{e}")
            continue

        # ① meta refresh
        content, delay, target = parse_refresh(html)
        if content is None:
            fail("meta-refresh", f"{url}：缺少 meta http-equiv=refresh")
        else:
            if delay is None:
                fail("meta-refresh-delay", f"{url}：refresh content 缺少秒数 -> {content!r}")
            if not target:
                fail("meta-refresh-target", f"{url}：refresh content 缺少 url 目标 -> {content!r}")

        # ② canonical
        canon_list = CANONICAL_RE.findall(html)
        if len(canon_list) != 1:
            fail("canonical", f"{url}：canonical 数量应为 1，实际 {len(canon_list)}")

        # ③④ target 合法且存在
        if target:
            parsed = urlparse(target)
            if parsed.scheme not in ("http", "https"):
                fail("target-scheme", f"{url}：目标不是 http(s) URL -> {target}")
            site_url = target_to_site_url(target, expected)
            if site_url is None or site_url not in expected:
                fail("target-missing", f"{url}：目标不在构建产物中 -> {target}")
            # ⑤ 不能指向自己
            if site_url == url:
                fail("target-self", f"{url}：refresh 目标指向自己")
            if canon_list and target_to_site_url(canon_list[0], expected) != site_url:
                fail("canonical-target-mismatch",
                     f"{url}：canonical {canon_list[0]} 与 refresh 目标 {target} 不一致")

        # ⑥ 额外 JS / inline handler
        if SCRIPT_RE.search(html):
            fail("extra-js", f"{url}：alias 页不应包含 <script>")
        if INLINE_HANDLER_RE.search(html):
            fail("inline-handler", f"{url}：alias 页不应包含 inline 事件处理器")

        # ⑦ 破损本地资源
        for ref in LOCAL_REF_RE.findall(html):
            if ref.startswith(("http://", "https://", "//", "data:", "mailto:", "#")):
                continue
            rel = ref.lstrip("/")
            if not os.path.exists(os.path.join(DIR, rel)):
                fail("broken-resource", f"{url}：引用的资源不存在 -> {ref}")

        # ⑧ lang 合法
        m = HTML_LANG_RE.search(html)
        if not m:
            fail("html-lang", f"{url}：<html> 缺少 lang 属性")
        else:
            lang = m.group(1)
            if not BCP47_RE.match(lang):
                fail("html-lang-format", f"{url}：lang 不是合法 BCP47 值 -> {lang}")
            elif site_langs and lang.lower() not in site_langs:
                fail("html-lang-inconsistent",
                     f"{url}：lang={lang} 与站点其它页面不符 {sorted(site_langs)}")

        # ⑨ title 非空
        tm = TITLE_RE.search(html)
        if not tm or not tm.group(1).strip():
            fail("title-empty", f"{url}：<title> 缺失或为空")
        _ = rel_display

    print(f"ALIAS PAGES = {len(alias_urls)}（来自 inventory alias 分类）")
    print(f"实际读取并检查 = {checked}")
    print(f"站点语言集合 = {sorted(site_langs)}")
    total = sum(len(v) for v in problems.values())
    if problems:
        print("\n### 违规明细")
        for rule in sorted(problems):
            hits = problems[rule]
            print(f"  - {rule} x{len(hits)}")
            for s in hits[:6]:
                print("      ", s)
    h.record("alias 页面：文件真实存在",
             "alias-file-missing" not in problems,
             f"{checked}/{len(alias_urls)} 个存在")
    h.record("alias 页面：每个都有唯一的 meta refresh 且带合法目标",
             not {"meta-refresh", "meta-refresh-delay", "meta-refresh-target"} & set(problems),
             f"{len(problems.get('meta-refresh', []))} 个异常")
    h.record("alias 页面：每个都有且仅有一个 canonical",
             "canonical" not in problems, f"{len(problems.get('canonical', []))} 个异常")
    h.record("alias 页面：refresh 目标均为构建产物中的真实页面",
             "target-missing" not in problems and "target-scheme" not in problems,
             f"{len(problems.get('target-missing', []))} 个异常")
    h.record("alias 页面：无自引用，且 canonical 与 refresh 目标一致",
             "target-self" not in problems and "canonical-target-mismatch" not in problems,
             f"{len(problems.get('target-self', []))} 个异常")
    h.record("alias 页面：无额外 JS / inline 事件处理器",
             "extra-js" not in problems and "inline-handler" not in problems,
             f"{len(problems.get('extra-js', []))} 个异常")
    h.record("alias 页面：引用的本地资源均存在",
             "broken-resource" not in problems,
             f"{len(problems.get('broken-resource', []))} 个异常")
    h.record("alias 页面：lang 合法且与站点语言一致",
             not {"html-lang", "html-lang-format", "html-lang-inconsistent"} & set(problems),
             f"{len(problems.get('html-lang', []))} 个异常")
    h.record("alias 页面：title 非空",
             "title-empty" not in problems,
             f"{len(problems.get('title-empty', []))} 个异常")
    h.record("alias 页面静态检查全部通过", total == 0, f"共 {total} 个违规")


def main():
    guard(H, run, H)
    H.finish()


if __name__ == "__main__":
    main()
