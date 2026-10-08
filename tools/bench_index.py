#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""搜索索引规模压测。

记录（每个规模 × 模式）：
  - 构建耗时
  - 主索引体积 / 分片(chunk)总体积 / chunk 数量
  - 搜索时发起的索引相关请求数（index.json + search/*.json）
  - 页面加载耗时、索引加载耗时、搜索等待耗时（ms）
  - JS 堆内存峰值（MB，Chromium）
  - 浏览器脚本执行时间（ms，CDP ScriptDuration 差值，作为 CPU 开销代理）

用法：python tools/bench_index.py [规模列表，如 500,1000,2000]
环境：HUGO_BIN（默认 hugo）、PLAYWRIGHT_PROXY（可选）、BENCH_RUN_ID（输出目录后缀）
"""
import io
import functools
import http.server
import json
import os
import random
import subprocess
import sys
import threading
import time

os.environ.setdefault("NO_PROXY", "127.0.0.1,localhost")
os.environ.setdefault("no_proxy", "127.0.0.1,localhost")

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
THEME = ROOT                      # 仓库根即主题根（tools/ 的上一级）
WORK = os.path.join(ROOT, "tmp", "bench")
HUGO = os.environ.get("HUGO_BIN", "hugo")
SIZES = [int(x) for x in (sys.argv[1].split(",") if len(sys.argv) > 1 else ["500", "1000", "2000"])]
RUN_ID = os.environ.get("BENCH_RUN_ID") or time.strftime("%H%M%S")

random.seed(20261008)
SENT = ["安全运营的核心在于持续可见性", "日志采集完整性决定溯源成败", "主机排查应先保全后处置",
        "网络分区与最小权限是基本防线", "规则调优需结合真实流量验证", "自动化降低重复劳动但增加维护成本"]

RESULTS = []


def gen_site(n, site_dir, mode, per_post_chars=3000):
    posts_dir = os.path.join(site_dir, "content", "posts")
    os.makedirs(posts_dir, exist_ok=True)
    with io.open(os.path.join(site_dir, "hugo.toml"), "w", encoding="utf-8") as f:
        f.write(f'''baseURL = 'https://bench.example.com/'
locale = 'zh-CN'
title = 'Bench'
theme = 'hugo-theme-nebula'
hasCJKLanguage = true
[pagination]
  pagerSize = 10
[outputs]
  home = ['HTML', 'RSS', 'JSON']
[markup]
  [markup.highlight]
    noClasses = false
[params]
  author = 'bench'
  [params.search]
    mode = '{mode}'
''')
    for i in range(n):
        body = []
        length = 0
        while length < per_post_chars:
            s = random.choice(SENT)
            body.append(s + "。")
            length += len(s) + 1
        body.append(f"\n\n关键词 MARKER{i:04d} 结束。")
        with io.open(os.path.join(posts_dir, f"post-{i:04d}.md"), "w", encoding="utf-8") as f:
            f.write(f"---\ntitle: \"文章 {i:04d}\"\ndate: 2026-01-{(i % 28) + 1:02d}\n"
                    f"description: \"第 {i} 篇\"\ntags: [\"t{i % 20}\"]\ncategories: [\"c{i % 8}\"]\n---\n\n"
                    + "".join(body) + "\n")


def build(site_dir, out_dir, mode):
    t0 = time.time()
    p = subprocess.run([HUGO, "--source", site_dir, "--themesDir", os.path.dirname(THEME),
                        "--gc", "--minify", "-d", out_dir],
                       cwd=THEME, capture_output=True, text=True, encoding="utf-8", errors="ignore")
    dur = time.time() - t0
    errs = [l for l in (p.stdout + p.stderr).splitlines() if l.strip().upper().startswith("ERROR")]
    return dur, errs


def measure(out_dir):
    idx = os.path.join(out_dir, "index.json")
    size = os.path.getsize(idx) if os.path.exists(idx) else 0
    shard_dir = os.path.join(out_dir, "search")
    shard_total = 0
    shard_n = 0
    if os.path.isdir(shard_dir):
        for f in os.listdir(shard_dir):
            shard_total += os.path.getsize(os.path.join(shard_dir, f))
            shard_n += 1
    return size, shard_total, shard_n


def browser_metrics(base, keyword):
    """返回 dict：请求数 / 传输字节 / 加载 / 索引加载 / 搜索耗时 / JS 堆 / 脚本执行时间"""
    from playwright.sync_api import sync_playwright
    _p = os.environ.get("PLAYWRIGHT_PROXY")
    proxy = {"server": _p, "bypass": "127.0.0.1,localhost"} if _p else None
    out = {"req": 0, "bytes": 0, "page_ms": -1, "index_ms": -1, "search_ms": -1,
           "hits": -1, "heap_mb": -1, "script_ms": -1}
    with sync_playwright() as pw:
        b = pw.chromium.launch(proxy=proxy) if proxy else pw.chromium.launch()
        ctx = b.new_context(viewport={"width": 1440, "height": 900}, locale="zh-CN")
        page = ctx.new_page()
        idx_reqs, idx_bytes, idx_last = [], [0], [0.0]

        def on_response(r):
            u = r.url
            if u.endswith("index.json") or "/search/" in u:
                idx_reqs.append(u)
                try:
                    body = r.body()
                    idx_bytes[0] += len(body)
                except Exception:
                    pass
                idx_last[0] = time.time()
        page.on("response", on_response)

        t0 = time.time()
        page.goto(base + "/", wait_until="load")
        out["page_ms"] = (time.time() - t0) * 1000

        cdp = ctx.new_cdp_session(page)
        cdp.send("Performance.enable")

        def metrics():
            m = {x["name"]: x["value"] for x in cdp.send("Performance.getMetrics")["metrics"]}
            return m
        m0 = metrics()

        page.click("#searchTrigger")
        t1 = time.time()
        page.fill("#search-input", keyword)
        try:
            page.wait_for_selector(".search-item", timeout=30000)
            out["search_ms"] = (time.time() - t1) * 1000
        except Exception:
            out["search_ms"] = -1
        out["index_ms"] = (idx_last[0] - t1) * 1000 if idx_last[0] else -1
        # 等索引相关请求全部结束
        page.wait_for_timeout(1500)
        out["hits"] = page.locator(".search-item").count()
        m1 = metrics()
        out["script_ms"] = (m1.get("ScriptDuration", 0) - m0.get("ScriptDuration", 0)) * 1000
        out["heap_mb"] = m1.get("JSHeapUsedSize", -1) / (1024 * 1024)
        out["req"] = len(idx_reqs)
        out["bytes"] = idx_bytes[0]
        b.close()
    return out


def main():
    os.makedirs(WORK, exist_ok=True)
    print(f"{'规模':>6} {'模式':>7} {'构建s':>7} {'主索引KB':>9} {'chunkKB':>8} {'chunk数':>7} "
          f"{'请求数':>6} {'传输KB':>7} {'页ms':>7} {'索引ms':>7} {'搜索ms':>7} {'堆MB':>6} {'脚本ms':>7} {'命中':>5}")
    for n in SIZES:
        for mode in ("single", "auto"):
            site_dir = os.path.join(WORK, f"site-{n}-{mode}-{RUN_ID}")
            out_dir = os.path.join(WORK, f"out-{n}-{mode}-{RUN_ID}")
            gen_site(n, site_dir, mode)
            dur, errs = build(site_dir, out_dir, mode)
            size, shard_total, shard_n = measure(out_dir)
            if errs:
                print("构建错误:", errs[:2])
            met = {}
            try:
                handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=out_dir)
                handler.log_message = lambda *a, **k: None
                port = 8123
                srv = http.server.ThreadingHTTPServer(("127.0.0.1", port), handler)
                threading.Thread(target=srv.serve_forever, daemon=True).start()
                try:
                    met = browser_metrics(f"http://127.0.0.1:{port}", f"MARKER{n-1:04d}")
                finally:
                    srv.shutdown()
            except Exception as e:
                print(f"  (浏览器测量跳过: {str(e)[:80]})")
            row = {
                "n": n, "mode": mode, "build_s": round(dur, 1),
                "index_kb": round(size / 1024, 1), "chunk_kb": round(shard_total / 1024, 1),
                "chunks": shard_n, **{k: (round(v, 1) if isinstance(v, float) else v)
                                      for k, v in met.items()},
            }
            RESULTS.append(row)
            print(f"{n:>6} {mode:>7} {dur:>7.1f} {size/1024:>9.1f} {shard_total/1024:>8.1f} {shard_n:>7} "
                  f"{met.get('req', -1):>6} {met.get('bytes', 0)/1024:>7.1f} {met.get('page_ms', -1):>7.0f} "
                  f"{met.get('index_ms', -1):>7.0f} {met.get('search_ms', -1):>7.0f} "
                  f"{met.get('heap_mb', -1):>6.1f} {met.get('script_ms', -1):>7.0f} {met.get('hits', -1):>5}")

    out_json = os.path.join(WORK, f"bench-{RUN_ID}.json")
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(RESULTS, f, ensure_ascii=False, indent=1)
    print(f"\n结果已写入 {out_json}")

    # 压测属于性能观测：出现构建错误或索引为空才判失败
    bad = [r for r in RESULTS if r["index_kb"] <= 0]
    if bad:
        print("FAIL 部分规模未产出索引:", bad)
        sys.exit(1)


if __name__ == "__main__":
    main()
