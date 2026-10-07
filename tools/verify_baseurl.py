#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""三种 baseURL 部署验证（P6）：根 / /blog/ /blog/sub/

每种部署：独立生产构建 -> 独立静态服务器 -> 浏览器检查
  - CSS/JS/图片/favicon 可访问且路径带 basePath
  - RSS / sitemap / robots / index.json 正确
  - 页面内所有站内链接不得跳出 basePath
  - canonical / og:url / 面包屑 / 菜单 / 分类 / 标签 / 分页 正确
"""
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.request
import shlex

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _testlib import Harness, launch as _launch, reachable, guard  # noqa: E402

from playwright.sync_api import sync_playwright  # noqa: E402


ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
SITE = os.environ.get("SITE_DIR") or os.path.join(ROOT, "myblog")
HUGO_ARGS = shlex.split(os.environ.get("HUGO_ARGS", ""))
HUGO = os.environ.get("HUGO_BIN", "hugo")   # CI 中 hugo 已在 PATH；本地可用 HUGO_BIN 指定
import time as _time
DEPLOY = os.path.join(ROOT, "tmp", "deploy-" + (os.environ.get("BASEURL_RUN_ID") or _time.strftime("%H%M%S")))
PY = sys.executable

CASES = [
    # (名称, baseURL, 构建输出目录, 服务器根, 访问 URL)
    ("root", "https://example.com/", "root", "root", "http://127.0.0.1:8101/"),
    ("blog", "https://example.com/blog/", "blog", ".", "http://127.0.0.1:8102/blog/"),
    ("blog-sub", "https://example.com/blog/sub/", "blog/sub", ".", "http://127.0.0.1:8102/blog/sub/"),
]

H = Harness("baseurl")


def rec(case, name, ok, detail=""):
    return H.record(f"[{case}] {name}", ok, detail)


def build(base_url, out_dir):
    # 每次使用全新目录，避免任何递归删除（批量删除会被安全策略拦截）
    dest = os.path.join(DEPLOY, out_dir)
    os.makedirs(dest, exist_ok=True)
    cmd = [HUGO] + HUGO_ARGS + ["--gc", "--minify", "--baseURL", base_url, "-d", dest]
    p = subprocess.run(cmd, cwd=SITE, capture_output=True, text=True, encoding="utf-8", errors="ignore")
    errs = [l for l in (p.stderr + p.stdout).splitlines() if l.strip().upper().startswith("ERROR")]
    return dest, errs


def check(case, base):
    path = base.replace("http://127.0.0.1:8101", "").replace("http://127.0.0.1:8102", "")
    path = path if path != "/" else "/"
    print(f"\n=== [{case}] base={base} (basePath={path}) ===")

    with sync_playwright() as p:
        b = _launch(p.chromium)
        ctx = b.new_context(viewport={"width": 1440, "height": 900}, locale="zh-CN")
        page = ctx.new_page()
        bad = []
        page.on("response", lambda r: bad.append(f"{r.status} {r.url}") if r.status >= 400 else None)

        # 首页
        r = page.goto(base, wait_until="load")
        rec(case, "首页可达", r and r.status == 200, str(r and r.status))
        page.wait_for_timeout(700)
        rec(case, "首页无失败请求", not bad, bad[:3])

        # CSS / JS / 图片 / favicon
        assets = page.evaluate("""() => ({
            css: Array.from(document.querySelectorAll('link[rel=stylesheet]')).map(l => l.href),
            js: Array.from(document.querySelectorAll('script[src]')).map(s => s.src),
            img: Array.from(document.images).map(i => i.currentSrc).filter(Boolean)
        })""")
        for kind, urls in assets.items():
            if not urls:
                rec(case, f"{kind} 存在", False, "无")
                continue
            wrong = [u for u in urls if not u.startswith(base)]
            rec(case, f"{kind} 路径在 basePath 内", not wrong, f"{len(urls)} 个，异常 {wrong[:2]}")

        fav = page.evaluate("""async () => {
            const links = Array.from(document.querySelectorAll('link[rel*=icon]'));
            const out = [];
            for (const l of links) {
                try { const r = await fetch(l.href, {method:'HEAD'}); out.push(r.status); }
                catch(e) { out.push('ERR'); }
            }
            return out;
        }""")
        rec(case, "favicon 可访问", all(s == 200 for s in fav) and len(fav) > 0, fav)

        # 站内链接不跳出 basePath
        internal = page.evaluate("""() => Array.from(document.querySelectorAll('a[href]'))
            .map(a => a.getAttribute('href'))
            .filter(h => h && h.startsWith('/'))""")
        outside = sorted(set(h for h in internal if not h.startswith(path)))
        rec(case, "首页站内链接不跳出 basePath", not outside,
            f"{len(internal)} 条内部链接，越界 {outside[:3]}")

        # canonical / og:url
        canon = page.evaluate("""() => {
            const c = document.querySelector('link[rel=canonical]');
            const o = document.querySelector('meta[property="og:url"]');
            return { canonical: c ? c.href : null, ogurl: o ? o.content : null };
        }""")
        rec(case, "canonical 指向本站", bool(canon["canonical"]) and path in canon["canonical"], canon["canonical"])
        rec(case, "og:url 指向本站", bool(canon["ogurl"]) and path in canon["ogurl"], canon["ogurl"])

        # 搜索
        page.click("#searchTrigger")
        page.wait_for_timeout(400)
        page.fill("#search-input", "应急响应")
        page.wait_for_timeout(1200)
        rec(case, "子目录搜索可用", page.locator(".search-item").count() > 0,
            f'{page.locator(".search-item").count()} 条')
        page.keyboard.press("Escape")

        # 文章页（含面包屑 / 分类 / 标签链接）
        page.goto(base + "posts/03-incident-response/", wait_until="load")
        page.wait_for_timeout(500)
        crumb = page.evaluate("""() => Array.from(document.querySelectorAll('.breadcrumb a')).map(a => a.getAttribute('href'))""")
        rec(case, "面包屑链接在 basePath 内",
            all(h and h.startswith(path) for h in crumb) and len(crumb) > 0, crumb)
        brand = page.evaluate("""() => document.querySelector('.brand').getAttribute('href')""")
        rec(case, "Logo 链接在 basePath 内", bool(brand) and brand.startswith(path), brand)
        menu = page.evaluate("""() => Array.from(document.querySelectorAll('#mainNav a')).map(a => a.getAttribute('href')).filter(h => h && h.startsWith('/'))""")
        rec(case, "菜单链接在 basePath 内",
            all(h.startswith(path) for h in menu) and len(menu) > 0, menu[:4])
        dup_menu = [] if path == "/" else [h for h in menu if h.count(path) > 1]
        rec(case, "菜单链接无 basePath 重复", not dup_menu, f"{menu[:4]} 重复 {dup_menu[:3]}")

        # 内部链接实际可达（抽样，防止链接指向 404）
        origin = re.match(r"(https?://[^/]+)", base).group(1)
        broken = []
        for h in sorted(set(internal))[:40]:
            try:
                with urllib.request.urlopen(origin + h, timeout=10) as rr:
                    if rr.status != 200:
                        broken.append((h, rr.status))
            except Exception as e:
                broken.append((h, str(e)[:40]))
        rec(case, "首页内部链接实际可达（抽样 40 条）", not broken, broken[:3])

        # 分类页 / 标签页 / 分页
        for name, url in (("分类页", base + "categories/"), ("标签页", base + "tags/"),
                          ("归档页", base + "archives/"), ("文章列表", base + "posts/")):
            rr = page.goto(url, wait_until="load")
            page.wait_for_timeout(400)
            rec(case, f"{name} 可达", rr and rr.status == 200, str(rr and rr.status))

        # 分页可达
        page.goto(base + "posts/", wait_until="load")
        page.wait_for_timeout(400)
        has_page2 = os.path.exists(os.path.join(DEPLOY, "root" if case == "root" else ("blog" if case == "blog" else "blog/sub"), "posts", "page", "2", "index.html"))
        if has_page2:
            rr = page.goto(base + "posts/page/2/", wait_until="load")
            rec(case, "分页第 2 页可达", rr and rr.status == 200, str(rr and rr.status))

        # RSS / sitemap / robots
        for name, rel, checker in (
            ("RSS", "index.xml", lambda t: "<link>" in t and path in t),
            ("sitemap", "sitemap.xml", lambda t: t.count("<loc>") > 0),
            ("robots", "robots.txt", lambda t: "Sitemap:" in t),
            ("index.json", "index.json", lambda t: t.strip().startswith("[")),
        ):
            try:
                with urllib.request.urlopen(base + rel, timeout=20) as resp:
                    txt = resp.read().decode("utf-8", "ignore")
                rec(case, f"{name} 可访问且内容正确", checker(txt), f"{len(txt)} 字节")
                if name == "sitemap":
                    # sitemap 使用绝对 URL，判定"是否包含正确的 basePath"
                    locs = re.findall(r"<loc>(.*?)</loc>", txt)
                    bad_loc = [l for l in locs if path not in l]
                    dup = [] if path == "/" else [l for l in locs if l.count(path) > 1]
                    rec(case, "sitemap 全部 loc 在 basePath 内", not bad_loc,
                        f"{len(locs)} 条，越界 {bad_loc[:2]}")
                    rec(case, "sitemap loc 无 basePath 重复", not dup, f"重复 {dup[:2]}")
                if name == "robots":
                    sm = re.search(r"Sitemap:\s*(\S+)", txt)
                    rec(case, "robots Sitemap 指向 basePath", bool(sm) and path in sm.group(1), sm and sm.group(1))
            except Exception as e:
                rec(case, f"{name} 可访问且内容正确", False, str(e)[:80])

        ctx.close()
        b.close()


def _run_all():
    os.makedirs(DEPLOY, exist_ok=True)

    for name, base_url, out_dir, _, _ in CASES:
        dest, errs = build(base_url, out_dir)
        print(f"构建 {name} -> {dest} : {'OK' if not errs else 'ERROR'}")
        for e in errs[:3]:
            print("   ", e[:150])
        if errs:
            H.fatal_error(f"构建失败 [{name}] {base_url}", errs[0][:160])
        elif not os.path.exists(os.path.join(dest, "index.html")):
            H.fatal_error(f"构建产物缺失 [{name}]", f"{dest}/index.html 不存在")
    if H.fatal:
        return   # 构建失败时后续浏览器检查无意义

    # 启动两个静态服务器
    srv1 = subprocess.Popen([PY, os.path.join(ROOT, "tools", "serve.py"), os.path.join(DEPLOY, "root"), "8101"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    srv2 = subprocess.Popen([PY, os.path.join(ROOT, "tools", "serve.py"), DEPLOY, "8102"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        ready = False
        for _ in range(30):
            if reachable("http://127.0.0.1:8101/") and reachable("http://127.0.0.1:8102/blog/"):
                ready = True
                break
            time.sleep(1)
        if not ready:
            H.fatal_error("静态服务器启动失败", "8101 / 8102 未就绪")
            return

        for name, base_url, out_dir, _, url in CASES:
            check(name, url)
    finally:
        srv1.terminate()
        srv2.terminate()


def main():
    guard(H, _run_all)
    H.finish()


if __name__ == "__main__":
    main()
