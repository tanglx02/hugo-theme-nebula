#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""搜索索引规模压测（A-1）：25 / 100 / 300 / 500 篇下 index.json 体积与加载/搜索耗时。

用法：python tools/bench_index.py [规模列表，如 25,100,300,500]
环境：HUGO_BIN（默认 hugo）、PLAYWRIGHT_PROXY（可选）
"""
import io
import os
import random
import shutil
import subprocess
import sys
import time

os.environ.setdefault("NO_PROXY", "127.0.0.1,localhost")
os.environ.setdefault("no_proxy", "127.0.0.1,localhost")

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
THEME = os.path.join(ROOT, "hugo-theme-nebula")
WORK = os.path.join(ROOT, "tmp", "bench")
HUGO = os.environ.get("HUGO_BIN", "hugo")
SIZES = [int(x) for x in (sys.argv[1].split(",") if len(sys.argv) > 1 else ["25", "100", "300", "500"])]

random.seed(20261008)
SENT = ["安全运营的核心在于持续可见性", "日志采集完整性决定溯源成败", "主机排查应先保全后处置",
        "网络分区与最小权限是基本防线", "规则调优需结合真实流量验证", "自动化降低重复劳动但增加维护成本"]


def gen_site(n, site_dir, mode, per_post_chars=3000):
    # 不删除既有文件：直接覆盖写入（每个规模使用独立站点目录，避免触发批量删除保护）
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
        # 每篇埋一个唯一关键词，便于搜索延迟测量
        body.append(f"\n\n关键词 MARKER{i:04d} 结束。")
        with io.open(os.path.join(site_dir, "content", "posts", f"post-{i:04d}.md"), "w", encoding="utf-8") as f:
            f.write(f"---\ntitle: \"文章 {i:04d}\"\ndate: 2026-01-{(i % 28) + 1:02d}\n"
                    f"description: \"第 {i} 篇\"\ntags: [\"t{i % 20}\"]\ncategories: [\"c{i % 8}\"]\n---\n\n"
                    + "".join(body) + "\n")


def build(site_dir, out_dir, mode):
    shutil.rmtree(out_dir, ignore_errors=True)
    t0 = time.time()
    # themesDir 与 -d 都使用绝对路径，避免受 --source 相对解析影响
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


def browser_timing(base, keyword):
    """打开搜索 → 输入 → 结果出现耗时（ms）"""
    from playwright.sync_api import sync_playwright
    _p = os.environ.get("PLAYWRIGHT_PROXY")
    proxy = {"server": _p, "bypass": "127.0.0.1,localhost"} if _p else None
    with sync_playwright() as pw:
        launcher = pw.chromium
        b = launcher.launch(proxy=proxy) if proxy else launcher.launch()
        page = b.new_context(viewport={"width": 1440, "height": 900}, locale="zh-CN").new_page()
        t0 = time.time()
        page.goto(base + "/", wait_until="load")
        load_ms = (time.time() - t0) * 1000
        page.click("#searchTrigger")
        t1 = time.time()
        page.fill("#search-input", keyword)
        try:
            page.wait_for_selector(".search-item", timeout=15000)
            search_ms = (time.time() - t1) * 1000
        except Exception:
            search_ms = -1
        n = page.locator(".search-item").count()
        b.close()
        return load_ms, search_ms, n


def main():
    os.makedirs(WORK, exist_ok=True)
    print(f"{'规模':>6} {'模式':>7} {'构建s':>7} {'主索引KB':>9} {'分片KB':>8} {'分片数':>6} {'搜索ms':>8} {'命中':>5}")
    for n in SIZES:
        for mode in ("single", "auto"):
            site_dir = os.path.join(WORK, f"site-{n}")
            run_id = os.environ.get("BENCH_RUN_ID") or time.strftime("%H%M%S")
            out_dir = os.path.join(WORK, f"out-{n}-{mode}-{run_id}")
            if mode == "single":
                gen_site(n, site_dir, "single")
            else:
                gen_site(n, site_dir, "auto")
            dur, errs = build(site_dir, out_dir, mode)
            size, shard_total, shard_n = measure(out_dir)
            if errs:
                print("构建错误:", errs[:2])
            # 浏览器测量（仅 single/auto 各测一次，抽样规模）
            search_ms, hits = -1, -1
            if n in (SIZES[0], SIZES[-1]):
                import threading
                import http.server
                import functools
                handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=out_dir)
                handler.log_message = lambda *a, **k: None
                port = 8123
                srv = http.server.ThreadingHTTPServer(("127.0.0.1", port), handler)
                th = threading.Thread(target=srv.serve_forever, daemon=True)
                th.start()
                try:
                    _, search_ms, hits = browser_timing(f"http://127.0.0.1:{port}", f"MARKER{n-1:04d}")
                except Exception as e:
                    print(f"  (浏览器测量跳过: {str(e)[:70]})")
                finally:
                    srv.shutdown()
            print(f"{n:>6} {mode:>7} {dur:>7.1f} {size/1024:>9.1f} {shard_total/1024:>8.1f} {shard_n:>6} "
                  f"{search_ms:>8.0f} {hits:>5}")


if __name__ == "__main__":
    main()
