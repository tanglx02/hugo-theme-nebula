"""性能基线测量：首屏加载 / 搜索索引 / 搜索响应 / JS heap。

用法：python tools/perf_baseline.py <base_url>   # 需先 serve.py <public_dir> <port>
输出 JSON（stdout 最后一个 JSON 块），供 docs/性能基线.md 引用。
"""
import json
import sys
import time

from playwright.sync_api import sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8103"

with sync_playwright() as p:
    b = p.chromium.launch()
    ctx = b.new_context(viewport={"width": 1280, "height": 900})
    pg = ctx.new_page()

    # ---- 首屏（home）----
    t0 = time.time()
    pg.goto(BASE + "/", wait_until="load")
    load_ms = (time.time() - t0) * 1000
    res = pg.evaluate("""() => {
        const ents = performance.getEntriesByType('resource');
        const bytes = ents.reduce((s, e) => s + (e.transferSize || e.encodedBodySize || 0), 0);
        return {count: ents.length, bytes};
    }""")
    fcp = pg.evaluate("() => { const e = performance.getEntriesByType('paint');"
                      " return e.length ? e[e.length-1].startTime : 0 }")

    # ---- 搜索索引（index.json）----
    t1 = time.time()
    idx_status = pg.request.get(BASE + "/index.json")
    idx_ms = (time.time() - t1) * 1000
    idx_bytes = len(idx_status.body())
    idx_posts = idx_status.text().count('"path"')

    # ---- 搜索交互（打开搜索框 -> 输入 -> 首条结果）----
    pg.keyboard.press("Control+k")
    try:
        pg.wait_for_selector("#searchModal, .search-modal", state="visible", timeout=3000)
    except Exception:
        pg.click("#searchTrigger")
        pg.wait_for_selector("#searchModal, .search-modal", state="visible", timeout=5000)
    t2 = time.time()
    sel = "#searchModal input, .search-modal input, #searchInput"
    pg.fill(sel, "suricata")
    pg.wait_for_selector(".search-result, .search-item", timeout=8000)
    search_ms = (time.time() - t2) * 1000
    n_results = len(pg.query_selector_all(".search-result, .search-item"))

    # ---- JS heap（仅 chromium）----
    heap = pg.evaluate("() => performance.memory ? {used: performance.memory.usedJSHeapSize,"
                       " total: performance.memory.totalJSHeapSize} : null")

    print(json.dumps({
        "home_load_ms": round(load_ms),
        "home_fcp_ms": round(fcp),
        "home_resource_count": res["count"],
        "home_resource_kb": round(res["bytes"] / 1024),
        "index_fetch_ms": round(idx_ms),
        "index_kb": round(idx_bytes / 1024),
        "index_path_count": idx_posts,
        "search_first_result_ms": round(search_ms),
        "search_result_count": n_results,
        "js_heap_used_mb": round(heap["used"] / 1048576, 1) if heap else None,
        "js_heap_total_mb": round(heap["total"] / 1048576, 1) if heap else None,
    }, ensure_ascii=False, indent=1))
    b.close()
