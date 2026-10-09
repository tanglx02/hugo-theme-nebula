#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""子目录部署路径验证：baseURL = https://example.com/blog/ 时，资源、链接、搜索是否全部正确。

⚠ 本脚本此前**没有任何退出码**（既无 sys.exit 也无 TEST-RESULT），
   一旦失败 CI 仍视为通过 —— 是仓库里唯一"任何失败退出码都不变"的验证脚本
   （TEST-DEFECT-009）。现在统一接入 tools/_testlib.py 的 Harness：
   失败 / 空用例 / 环境问题一律 exit 1。

用法：
    python3 tools/subdir_test.py
环境变量：
    HUGO_BIN   hugo 可执行文件（默认 PATH 中的 hugo）
    SUBDIR_SITE  站点目录（默认 <repo>/myblog）
退出码约定（见 tools/_testlib.py）：任一断言失败 -> exit 1。
"""
import os
import shutil
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _testlib import Harness, guard, launch, reachable  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
SITE = os.path.abspath(os.environ.get("SUBDIR_SITE") or os.path.join(ROOT, "myblog"))
HUGO = os.environ.get("HUGO_BIN", "hugo")
BUILD = os.path.join(ROOT, "tmp", "public-blog")
SERVE_ROOT = os.path.join(ROOT, "tmp", "serve")
MOUNT = os.path.join(SERVE_ROOT, "blog")
PORT = 8089
BASE = f"http://127.0.0.1:{PORT}/blog/"


def run(h):
    if not os.path.isdir(SITE):
        h.fatal_error("站点目录不存在", SITE)
        return

    r = subprocess.run([HUGO, "--gc", "--minify", "--baseURL", "https://example.com/blog/",
                        "-d", BUILD], cwd=SITE, capture_output=True, text=True,
                       encoding="utf-8", errors="ignore")
    errs = [ln for ln in (r.stdout + r.stderr).splitlines()
            if ln.strip().upper().startswith("ERROR")]
    if r.returncode != 0 or errs:
        h.fatal_error("子目录 baseURL 构建失败",
                      (errs[0] if errs else f"rc={r.returncode}")[:180])
        return

    shutil.rmtree(SERVE_ROOT, ignore_errors=True)
    os.makedirs(SERVE_ROOT, exist_ok=True)
    shutil.copytree(BUILD, MOUNT)

    srv = subprocess.Popen([sys.executable, os.path.join(ROOT, "tools", "serve.py"),
                            SERVE_ROOT, str(PORT)],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(20):
            if reachable(BASE, timeout=2):
                break
            time.sleep(0.5)
        else:
            h.fatal_error("子目录静态服务器不可达", BASE)
            return

        with sync_playwright() as p:
            b = launch(p.chromium)
            ctx = b.new_context(viewport={"width": 1440, "height": 900}, locale="zh-CN")
            page = ctx.new_page()
            bad = []
            page.on("response", lambda r: bad.append(f"{r.status} {r.url}")
                    if r.status >= 400 else None)

            page.goto(BASE, wait_until="load")
            page.wait_for_timeout(400)
            h.record("子目录首页可达", page.locator(".post-card").count() > 0)
            h.record("子目录无失败请求", not bad, bad[:5])

            css = page.evaluate(
                "() => Array.from(document.querySelectorAll('link[rel=stylesheet]')).map(l => l.href)")
            js = page.evaluate(
                "() => Array.from(document.querySelectorAll('script[src]')).map(s => s.src)")
            h.record("CSS 路径包含 /blog/", bool(css) and all("/blog/" in c for c in css), css)
            h.record("JS 路径包含 /blog/",
                     all("/blog/" in s for s in js if "127.0.0.1" in s), js)

            idx_path = page.evaluate("""async () => {
                const el = document.querySelector('script[src*="main"]');
                if (!el) return 'no-main-script';
                const r = await fetch(el.src);
                const t = await r.text();
                const m = t.match(/(\\/blog\\/index\\.json|index\\.json)/);
                return m ? m[1] : 'none';
            }""")
            h.record("搜索索引路径正确", "index.json" in str(idx_path), idx_path)

            page.click("#searchTrigger")
            page.wait_for_timeout(300)
            page.fill("#search-input", "应急响应")
            page.wait_for_timeout(800)
            n = page.locator(".search-item").count()
            h.record("子目录下搜索可用", n > 0, f"{n} 条")
            page.keyboard.press("Escape")
            page.wait_for_timeout(200)

            page.goto(BASE + "posts/03-incident-response/", wait_until="load")
            h.record("子目录文章页可达", "排查" in page.inner_text(".post-content"))
            imgs = page.evaluate("""() => Array.from(
                document.querySelectorAll('.post-content img, .article-cover img'))
                .map(i => ({src: i.currentSrc,
                            ok: i.naturalWidth > 0 || (i.loading === 'lazy' && !i.complete)}))""")
            h.record("文章页图片全部加载", all(i["ok"] for i in imgs),
                     [i["src"] for i in imgs if not i["ok"]][:3])
            h.record("子目录无失败请求(文章页)", not bad, bad[:5])

            page.click(".brand")
            page.wait_for_load_state("load")
            h.record("品牌链接回到子目录首页", page.url == BASE, page.url)

            b.close()
    finally:
        srv.terminate()
        try:
            srv.wait(timeout=5)
        except Exception:
            srv.kill()


if __name__ == "__main__":
    main_h = Harness("subdir")
    guard(main_h, run, main_h)
    main_h.finish()
