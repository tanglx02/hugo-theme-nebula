#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""诊断工具：全文搜索是否覆盖正文深处关键词（索引静态检查 + 浏览器端到端）。

⚠ 结构说明（TEST-DEFECT-018）
----------------------------
本文件此前有一段**缩进错位**的代码：浏览器逻辑被缩进到了 `_launch()` 里，
于是 `check_browser()` 只打印一行就返回 None —— 后面的代码永远不会执行，
且脚本永远 exit 0（"无退出码无断言"）。现已修正结构，并接入 tools/_testlib.py：
只要关键词在索引中缺失或在浏览器里搜不到，进程就会 exit 1。

它是**诊断工具而非 CI 门禁**（CI 由 check_index / verify_search_shard /
verify_search_edge 覆盖同类断言），但"看起来在跑其实没跑"的形态必须消除。

用法：
    python3 tools/repro_search.py [base_url]
默认 http://127.0.0.1:8088
"""
import json
import os
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _testlib import Harness, guard, launch, reachable  # noqa: E402

os.environ.setdefault("NO_PROXY", "127.0.0.1,localhost")
os.environ.setdefault("no_proxy", "127.0.0.1,localhost")

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8088"

# 埋点关键词 -> 预期所在字符位置
MARKERS = [
    ("ALPHA1000", 1000),
    ("BRAVO3000", 3000),
    ("CHARLIE3500", 3500),
    ("DELTA5000", 5000),
    ("ECHO8000", 8000),
    ("FOXTROT10000", 10000),
    ("SIERRA2000", 2000),
    ("TANGO25000", 25000),
    ("GOLF48000", 48000),
]


def fetch(url):
    with urllib.request.urlopen(url, timeout=30) as r:
        return r.read().decode("utf-8")


def index_blob_and_items():
    """兼容单文件（数组）与分片（{items, chunks}）两种索引结构。

    分片模式：正文在 chunk 文件里，必须把 chunk 一并读进来才算"全文"。
    """
    raw = fetch(BASE + "/index.json")
    print(f"index.json 体积: {len(raw.encode('utf-8')) / 1024:.1f} KB")
    data = json.loads(raw)
    chunks = []
    if isinstance(data, dict):
        items = data.get("items") or []
        chunks = data.get("chunks") or []
    else:
        items = data
    parts = [json.dumps(items, ensure_ascii=False)]
    for u in chunks:
        try:
            parts.append(fetch(BASE.rstrip("/") + u if u.startswith("/") else u))
        except Exception as e:
            print(f"  chunk 读取失败 {u}: {e}")
    return "".join(parts), items


def check_index(h):
    print("=== [1] 索引文件静态检查 ===")
    blob, items = index_blob_and_items()
    missing = []
    for kw, pos in MARKERS:
        found = kw in blob
        where = ""
        for item in items:
            c = item.get("content", "") or ""
            if kw in c:
                where = f'(命中 {(item.get("title") or "")[:12]}，content 长度 {len(c)})'
                break
        print(f"  {kw:<16} 位置约 {pos:>6} 字 : 索引中{'存在' if found else '缺失'} {where}")
        if not found:
            missing.append(kw)
    lens = sorted(len(i.get("content", "") or "") for i in items)
    if lens:
        print(f"  content 长度: 最小 {lens[0]}, 中位 {lens[len(lens)//2]}, "
              f"最大 {lens[-1]}, 共 {len(items)} 篇")
    h.record("索引包含全部深层关键词（全文未截断）", not missing,
             f"缺失: {missing}" if missing else f"{len(MARKERS)} 个关键词全部命中")


def check_browser(h):
    print("\n=== [2] 浏览器端到端搜索 ===")
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = launch(p.chromium)
        ctx = b.new_context(viewport={"width": 1440, "height": 900}, locale="zh-CN")
        page = ctx.new_page()
        page.goto(BASE + "/", wait_until="load")
        page.click("#searchTrigger")
        page.wait_for_timeout(900)   # 等索引加载
        miss = []
        for kw, pos in MARKERS:
            page.fill("#search-input", "")
            page.fill("#search-input", kw)
            page.wait_for_timeout(450)
            n = page.locator(".search-item").count()
            empty = page.locator(".search-empty").count() > 0
            print(f"  {kw:<16} 位置约 {pos:>6} 字 : 结果 {n} 条"
                  f"{'（无结果提示）' if empty else ''}")
            if n == 0:
                miss.append(kw)
        b.close()
    h.record("浏览器搜索能命中全部深层关键词", not miss,
             f"未命中: {miss}" if miss else f"{len(MARKERS)} 个关键词全部命中")


def run(h):
    if not reachable(BASE + "/"):
        h.fatal_error("站点不可达", BASE)
        return
    try:
        check_index(h)
    except Exception as e:
        h.record("索引静态检查", False, str(e)[:160])
    try:
        check_browser(h)
    except Exception as e:
        h.record("浏览器端到端搜索", False, str(e)[:160])


if __name__ == "__main__":
    main_h = Harness("repro-search")
    guard(main_h, run, main_h)
    main_h.finish()
