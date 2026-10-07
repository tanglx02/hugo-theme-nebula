#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""子目录部署路径验证：baseURL = https://example.com/blog/ 时，资源、链接、搜索是否全部正确。"""
import os
import shutil
import subprocess
import sys

os.environ.setdefault("NO_PROXY", "127.0.0.1,localhost")
os.environ.setdefault("no_proxy", "127.0.0.1,localhost")

from playwright.sync_api import sync_playwright

# 代理仅用于本地开发环境；CI 中不设置 PLAYWRIGHT_PROXY 即为直连
_proxy = os.environ.get("PLAYWRIGHT_PROXY")
PROXY = {"server": _proxy, "bypass": "127.0.0.1,localhost"} if _proxy else None


def _launch(module, **kw):
    return module.launch(proxy=PROXY, **kw) if PROXY else module.launch(**kw)


ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
SITE = os.path.join(ROOT, "myblog")
HUGO = r"C:\Users\Administrator\.workbuddy\binaries\hugo\bin\hugo.exe"
BUILD = os.path.join(ROOT, "tmp", "public-blog")
SERVE_ROOT = os.path.join(ROOT, "tmp", "serve")
MOUNT = os.path.join(SERVE_ROOT, "blog")
PORT = 8089
BASE = f"http://127.0.0.1:{PORT}/blog/"

print("1) 以子目录 baseURL 构建 ...")
r = subprocess.run([HUGO, "--gc", "--minify", "--baseURL", "https://example.com/blog/", "-d", BUILD],
                   cwd=SITE, capture_output=True, text=True)
print(r.stdout[-400:], r.stderr[-400:])

print("2) 部署到临时目录 ...")
shutil.rmtree(SERVE_ROOT, ignore_errors=True)
os.makedirs(SERVE_ROOT, exist_ok=True)
shutil.copytree(BUILD, MOUNT)

print("3) 启动服务器 ...")
srv = subprocess.Popen([sys.executable, os.path.join(ROOT, "tools", "serve.py"), SERVE_ROOT, str(PORT)],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
import time
time.sleep(2)

results = []


def record(name, ok, detail=""):
    results.append((name, ok, detail))
    print(("PASS  " if ok else "FAIL  ") + name + ((" :: " + str(detail)) if detail else ""))


try:
    with sync_playwright() as p:
        b = _launch(p.chromium)
        ctx = b.new_context(viewport={"width": 1440, "height": 900}, locale="zh-CN")
        page = ctx.new_page()
        bad = []
        page.on("response", lambda r: bad.append(f"{r.status} {r.url}") if r.status >= 400 else None)

        page.goto(BASE, wait_until="load")
        page.wait_for_timeout(500)
        record("子目录首页可达", page.locator(".post-card").count() > 0)
        record("子目录无失败请求", not bad, bad[:5])

        css = page.evaluate("""() => Array.from(document.querySelectorAll('link[rel=stylesheet]')).map(l => l.href)""")
        js = page.evaluate("""() => Array.from(document.querySelectorAll('script[src]')).map(s => s.src)""")
        record("CSS 路径包含 /blog/", all("/blog/" in c for c in css), css)
        record("JS 路径包含 /blog/", all("/blog/" in s for s in js if "127.0.0.1" in s), js)

        # 搜索索引路径
        idx_path = page.evaluate("""async () => {
            const r = await fetch(document.querySelector('script[src*="main"]').src);
            const t = await r.text();
            const m = t.match(/"(\\/blog\\/index\\.json|index\\.json)"/) || t.match(/'((\\/blog\\/)?index\\.json)'/);
            return m ? m[1] : (t.match(/index\\.json/) ? 'found-index.json-mention' : 'none');
        }""")
        record("搜索索引路径正确", "index.json" in str(idx_path), idx_path)

        # 实际搜索功能
        page.click("#searchTrigger")
        page.wait_for_timeout(300)
        page.fill("#search-input", "应急响应")
        page.wait_for_timeout(700)
        record("子目录下搜索可用", page.locator(".search-item").count() > 0,
               f'{page.locator(".search-item").count()} 条')
        page.keyboard.press("Escape")

        # 文章页与导航
        page.goto(BASE + "posts/03-incident-response/", wait_until="load")
        record("子目录文章页可达", "排查" in page.inner_text(".post-content"))
        imgs = page.evaluate("""() => Array.from(document.querySelectorAll(".post-content img, .article-cover img")).map(i => ({src: i.currentSrc, ok: i.naturalWidth > 0 || (i.loading === 'lazy' && !i.complete)}))""")
        record("文章页图片全部加载", all(i["ok"] for i in imgs), [i["src"] for i in imgs if not i["ok"]][:3])
        record("子目录无失败请求(文章页)", not bad, bad[:5])

        # 返回首页链接
        page.click(".brand")
        page.wait_for_load_state("load")
        record("品牌链接回到子目录首页", page.url == BASE, page.url)

        b.close()
finally:
    srv.terminate()

failed = [r for r in results if not r[1]]
print(f"\n==== {len(results)-len(failed)}/{len(results)} PASSED ====")
for n, _, d in failed:
    print("  -", n, "::", d)
