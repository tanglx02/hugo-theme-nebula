#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""复现/验证：全文搜索是否覆盖正文深处关键词。

用法：python tools/repro_search.py [base_url]
默认 http://127.0.0.1:8088
"""
import json
import os
import sys
import urllib.request

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


def check_index():
    """静态检查：index.json 的 content 字段是否包含全部埋点关键词"""
    print("=== [1] 索引文件静态检查 ===")
    raw = fetch(BASE + "/index.json")
    print(f"index.json 体积: {len(raw.encode('utf-8')) / 1024:.1f} KB")
    data = json.loads(raw)
    blob = json.dumps(data, ensure_ascii=False)
    ok = True
    for kw, pos in MARKERS:
        found = kw in blob
        # 定位出现在哪篇文章的 content 长度上
        where = ""
        for item in data:
            c = item.get("content", "") or ""
            if kw in c:
                where = f'(命中 {item["title"][:12]}，content 长度 {len(c)})'
                break
        print(f"  {kw:<16} 位置约 {pos:>6} 字 : 索引中{'存在' if found else '缺失'} {where}")
        if not found:
            ok = False
    # 输出 content 长度分布
    lens = sorted(len(i.get("content", "") or "") for i in data)
    print(f"  content 长度: 最小 {lens[0]}, 中位 {lens[len(lens)//2]}, 最大 {lens[-1]}, 共 {len(data)} 篇")
    return ok


def check_browser():
    """端到端：真实浏览器打开搜索框，逐词搜索"""
    print("\n=== [2] 浏览器端到端搜索 ===")
    from playwright.sync_api import sync_playwright

# 代理仅用于本地开发环境；CI 中不设置 PLAYWRIGHT_PROXY 即为直连
_proxy = os.environ.get("PLAYWRIGHT_PROXY")
PROXY = {"server": _proxy, "bypass": "127.0.0.1,localhost"} if _proxy else None


def _launch(module, **kw):
    return module.launch(proxy=PROXY, **kw) if PROXY else module.launch(**kw)

    results = []
    with sync_playwright() as p:
        b = _launch(p.chromium)
        ctx = b.new_context(viewport={"width": 1440, "height": 900}, locale="zh-CN")
        page = ctx.new_page()
        page.goto(BASE + "/", wait_until="load")
        page.click("#searchTrigger")
        page.wait_for_timeout(800)   # 等索引加载
        for kw, pos in MARKERS:
            page.fill("#search-input", "")
            page.fill("#search-input", kw)
            page.wait_for_timeout(500)
            n = page.locator(".search-item").count()
            empty = page.locator(".search-empty").count() > 0
            results.append((kw, pos, n, empty))
            print(f"  {kw:<16} 位置约 {pos:>6} 字 : 结果 {n} 条 {'（无结果提示）' if empty else ''}")
        b.close()
    return results


if __name__ == "__main__":
    try:
        ok = check_index()
    except Exception as e:
        print("索引检查失败:", e)
        ok = False
    try:
        res = check_browser()
    except Exception as e:
        print("浏览器检查失败:", e)
        res = []
    print("\n=== 结论 ===")
    if res:
        miss = [r[0] for r in res if r[2] == 0]
        print(f"索引包含全部关键词: {ok}")
        print(f"浏览器搜索全部命中: {not miss}" + (f"，未命中: {miss}" if miss else ""))
