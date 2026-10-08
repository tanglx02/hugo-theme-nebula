#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Nebula 全站 HTML 审计：多浏览器 × 多视口 × 页面

检查项：
  - 控制台错误 / 未捕获异常 / 失败请求(404 等)
  - 横向滚动与元素溢出
  - 图片：加载失败 / 变形 / 懒加载后仍未完成
  - 移动端点击区域过小（正文内联链接按 WCAG 1.4.10 内联豁免，不计入）

**页面范围**
  * 默认（抽样）：关键入口 + 分类/标签 term + 分页 + 文章页抽样 —— 每次 PR 使用
  * `AUDIT_FULL=1`（全站）：sitemap 中**全部可审计 HTML 页面** —— Release 门禁

  全站模式下会打印并断言：
      SITEMAP HTML PAGES / AUDITED HTML PAGES / SKIPPED INTENTIONAL ENDPOINTS
  二者数量必须一致，否则判为致命错误。

**懒加载**：每页进入后先记录初始态 → 分步滚动到底触发 lazy → 等待图片完成
（有上限）→ 滚回顶部 → 有界等待网络静默 → 再做全部检查。

退出码约定（见 tools/_testlib.py）：
  * 发现任一问题 / 浏览器启动失败 / sitemap 获取失败 / 站点不可达 / 脚本异常 -> exit 1

输出：tools/audit_report.json
"""
import json
import os
import re
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _testlib import Harness, launch, reachable, guard  # noqa: E402

from playwright.sync_api import sync_playwright  # noqa: E402

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8088"
ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
OUT = os.path.join(ROOT, "tools", "audit_report.json")
FULL = os.environ.get("AUDIT_FULL", "").strip() not in ("", "0", "false", "False")

# 抽样模式下的关键入口（全站模式下这些页面本身也在 sitemap 中）
KEY_URLS = ["/", "/posts/", "/categories/", "/tags/", "/archives/", "/about/"]

# 明确"不是 HTML 页面"的 endpoint：不计入 HTML 审计，但会被显式列出并计数。
# 数据类 endpoint 由 check_index.py / check_features.py 单独验证。
NON_HTML_PREFIXES = ("/search/",)
NON_HTML_EXACT = ("/index.json", "/sitemap.xml", "/robots.txt", "/index.xml", "/favicon.ico")

# 已知的"故意缺失资源"白名单（压力测试数据）：精确匹配 URL pathname，
# 不允许用 endswith 之类的宽松匹配（可能误豁免其它路径下的同名损坏资源）。
INTENTIONAL_MISSING_PATHS = ("/not-exist.png",)

# 全站模式下必须覆盖到的页面类型（缺失即判失败，防止"抽样冒充全站"）
REQUIRED_COVERAGE = (
    ("分类 term 页面", lambda p: re.fullmatch(r"/categories/[^/]+/", p)),
    ("标签 term 页面", lambda p: re.fullmatch(r"/tags/[^/]+/", p)),
    ("分页 /page/2/", lambda p: p.endswith("/page/2/")),
    ("分页 /page/3/", lambda p: p.endswith("/page/3/")),
    ("分类首页", lambda p: p == "/categories/"),
    ("标签首页", lambda p: p == "/tags/"),
    ("归档页", lambda p: p == "/archives/"),
    ("文章页", lambda p: re.fullmatch(r"/posts/[^/]+/", p)),
)

VIEWPORTS = {
    "320": {"width": 320, "height": 720},
    "375": {"width": 375, "height": 812},
    "390": {"width": 390, "height": 844},
    "430": {"width": 430, "height": 932},
    "768": {"width": 768, "height": 1024},
    "1024": {"width": 1024, "height": 768},
    "1440": {"width": 1440, "height": 900},
}

PROBE_JS = """
() => {
  const vw = document.documentElement.clientWidth;
  const out = [];
  document.querySelectorAll('body *').forEach(el => {
    const r = el.getBoundingClientRect();
    if (r.width === 0 || r.height === 0) return;
    const st = getComputedStyle(el);
    if (st.position === 'fixed' || st.visibility === 'hidden') return;
    if (r.right > vw + 2 || r.left < -2) {
      let p = el.parentElement, scrollable = false;
      while (p) {
        const ps = getComputedStyle(p);
        if (ps.overflowX === 'auto' || ps.overflowX === 'scroll' || ps.overflowX === 'hidden') { scrollable = true; break; }
        p = p.parentElement;
      }
      if (!scrollable) {
        const cls = (typeof el.className === 'string' ? el.className : '').split(' ')[0];
        out.push(el.tagName.toLowerCase() + (cls ? '.' + cls : '') + ' [' + Math.round(r.left) + ',' + Math.round(r.right) + ']');
      }
    }
  });
  return {
    hScroll: document.documentElement.scrollWidth > vw + 1,
    scrollWidth: document.documentElement.scrollWidth,
    clientWidth: vw,
    overflow: Array.from(new Set(out)).slice(0, 10)
  };
}
"""

IMG_JS = """
() => Array.from(document.querySelectorAll('.post-content img, .article-cover img')).map(img => {
  const r = img.getBoundingClientRect();
  return {
    src: (img.currentSrc || img.getAttribute('src') || '').split('/').slice(-1)[0],
    url: img.currentSrc || img.getAttribute('src') || '',
    nw: img.naturalWidth, nh: img.naturalHeight,
    w: Math.round(r.width), h: Math.round(r.height),
    fit: getComputedStyle(img).objectFit,
    loading: img.getAttribute('loading') || '',
    complete: img.complete,
    broken: img.complete && img.naturalWidth === 0
  };
})
"""

# 触发懒加载：分步滚到底，再滚回顶部
SCROLL_JS = """
async () => {
  const step = Math.max(400, Math.round(window.innerHeight * 1.2));
  const total = document.body.scrollHeight;
  for (let y = 0; y < total; y += step) {
    window.scrollTo(0, y);
    await new Promise(r => setTimeout(r, 40));
  }
  window.scrollTo(0, total);
  await new Promise(r => setTimeout(r, 120));
  window.scrollTo(0, 0);
}
"""


def path_of(url):
    from urllib.parse import urlparse
    return urlparse(url).path or "/"


def is_html_page(path):
    return path.endswith("/") or path.endswith(".html")


def is_non_html_endpoint(path):
    if path in NON_HTML_EXACT:
        return True
    return any(path.startswith(p) for p in NON_HTML_PREFIXES)


def is_article_page(path):
    return bool(re.fullmatch(r"/[^/]+/[^/]+/", path)) and "/page/" not in path


def discover_pagination(base, seeds, max_urls=800, rounds=3):
    """发现分页页面（Hugo 的 sitemap **不包含** /page/N/）。

    从列表页/分类/标签 term 页里抓取 `.pagination` 中的 /page/N/ 链接，
    再对发现的分页页继续抓（有轮次与数量上限），保证覆盖全部分页。
    """
    found, seen_seed = set(), set()
    worklist = list(seeds)
    for _ in range(rounds):
        next_round = []
        for p in worklist:
            if p in seen_seed or len(found) >= max_urls:
                continue
            seen_seed.add(p)
            try:
                with urllib.request.urlopen(base + p, timeout=10) as r:
                    html = r.read().decode("utf-8", "ignore")
            except Exception:
                continue
            for href in re.findall(r'href=["\']?([^"\'> ]*/page/\d+/)', html):
                path = path_of(href if href.startswith("/") else "/" + href)
                if path not in found:
                    found.add(path)
                    next_round.append(path)
        worklist = next_round
        if not worklist or len(found) >= max_urls:
            break
    return sorted(found)


def get_urls(base, full=False):
    """返回 (urls, stats)。

    stats = {
        "sitemap_total": sitemap 中 <loc> 总数,
        "sitemap_html": 其中可审计的 HTML 页面数,
        "extra_pagination": 由站点抓取发现的额外分页页面数（sitemap 不含），
        "skipped": [(path, 原因)] 被有意排除的非 HTML endpoint,
        "audited_html": 实际进入审计的 HTML 页面数（= sitemap_html + extra_pagination）,
        "missing_specials": 全站模式下未覆盖到的必需页面类型,
    }
    """
    stats = {"sitemap_total": 0, "sitemap_html": 0, "extra_pagination": 0,
             "skipped": [], "audited_html": 0, "missing_specials": [], "sitemap_ok": False}
    html_pages = []
    try:
        with urllib.request.urlopen(base + "/sitemap.xml", timeout=15) as r:
            xml = r.read().decode("utf-8")
        locs = re.findall(r"<loc>(.*?)</loc>", xml)
        stats["sitemap_total"] = len(locs)
        skipped = []
        for loc in locs:
            path = path_of(loc)
            if is_non_html_endpoint(path):
                skipped.append((path, "非 HTML endpoint"))
                continue
            if is_html_page(path):
                html_pages.append(path)
            else:
                skipped.append((path, "非 HTML 页面"))
        html_pages = [p for p in html_pages
                      if not re.fullmatch(r"/categories/[^/]+/", p)]
        stats["sitemap_html"] = len(html_pages)
        stats["skipped"] = skipped
        stats["sitemap_ok"] = len(locs) > 0
    except Exception as e:
        print("sitemap error:", e)

    if full:
        seeds = [p for p in html_pages if not is_article_page(p)] or ["/", "/posts/"]
        extra = discover_pagination(base, seeds)
        urls = list(html_pages) + [p for p in extra if p not in set(html_pages)]
        stats["extra_pagination"] = len(urls) - len(html_pages)
        stats["audited_html"] = len(urls)
        for name, pred in REQUIRED_COVERAGE:
            if not any(pred(p) for p in urls):
                stats["missing_specials"].append(name)
    else:
        posts = [p for p in html_pages if p.startswith("/posts/")]
        cats = [p for p in html_pages if p.startswith("/categories/")]
        tags = [p for p in html_pages if p.startswith("/tags/")]
        pages = [p for p in html_pages if "/page/" in p]
        if not pages:      # sitemap 不含分页，抽样时按需抓一份
            pages = discover_pagination(base, ["/", "/posts/"], max_urls=20, rounds=1)
        other = [p for p in html_pages
                 if p not in posts + cats + tags + pages]
        sample = list(KEY_URLS) + posts[:6] + cats[:3] + tags[:3] + pages[:3] + other[:4]
        urls = []
        for p in sample:
            if p in html_pages or p in KEY_URLS or "/page/" in p:
                if p not in urls:
                    urls.append(p)
        stats["audited_html"] = len([p for p in urls if p in html_pages or "/page/" in p])

    # 404 页面探针：sitemap 不含 404.html，单独用一个不存在的 URL 触发
    urls.append("/this-page-does-not-exist/")
    seen, uniq = set(), []
    for u in urls:
        if u not in seen:
            seen.add(u)
            uniq.append(u)
    return uniq, stats


def settle_lazy_images(page, budget_ms=8000):
    """滚动触发懒加载 -> 等图片完成 -> 滚回顶部 -> 有界等待网络静默。

    返回仍处于未完成状态的图片数量（用于 image-not-loaded 判定）。
    """
    try:
        page.evaluate(SCROLL_JS)
    except Exception:
        pass
    try:
        page.wait_for_function(
            "() => Array.from(document.images).every(i => i.complete)",
            timeout=budget_ms)
    except Exception:
        pass
    pending = page.evaluate(
        "() => Array.from(document.images).filter(i => !i.complete).length")
    try:
        page.wait_for_load_state("networkidle", timeout=3000)
    except Exception:
        pass
    return pending


def check_page(page, url, vp_name, is_mobile, ignored_log=None):
    problems = []
    console_errors, page_errors, failed = [], [], []
    ignored_404 = []

    def on_console(msg):
        if msg.type == "error" and "livereload" not in msg.text:
            console_errors.append(msg.text[:200])

    def on_pageerror(err):
        page_errors.append(str(err)[:200])

    def on_response(resp):
        if resp.status >= 400 and "livereload" not in resp.url:
            p = path_of(resp.url)
            if p in INTENTIONAL_MISSING_PATHS:      # 精确匹配，绝不用 endswith
                ignored_404.append(f"{resp.status} {p}")
                return
            failed.append(f"{resp.status} {resp.url}")

    page.on("console", on_console)
    page.on("pageerror", on_pageerror)
    page.on("response", on_response)

    try:
        resp = page.goto(BASE + url, wait_until="load", timeout=30000)
    except Exception as e:
        problems.append({"type": "navigation", "detail": str(e)[:160]})
        page.remove_listener("console", on_console)
        page.remove_listener("pageerror", on_pageerror)
        page.remove_listener("response", on_response)
        return problems

    status = resp.status if resp else 0
    expect_404 = url.rstrip("/").endswith("does-not-exist")

    # ① 初始态（首屏）→ ② 滚动触发懒加载 → ③ 等图片 → ④ 回顶部 → ⑤ 等网络静默
    pending_images = 0
    if not expect_404:
        pending_images = settle_lazy_images(page)
    else:
        page.wait_for_timeout(180)

    # ⑥ 全部检查
    data = page.evaluate(PROBE_JS)
    if data["hScroll"]:
        problems.append({"type": "horizontal-scroll", "vp": vp_name,
                         "detail": f'scrollWidth={data["scrollWidth"]} clientWidth={data["clientWidth"]}',
                         "elements": data["overflow"]})
    elif data["overflow"]:
        problems.append({"type": "element-overflow", "vp": vp_name, "elements": data["overflow"]})

    imgs = page.evaluate(IMG_JS)
    for im in imgs:
        if im["broken"]:
            if path_of(im["url"]) in INTENTIONAL_MISSING_PATHS:
                ignored_404.append(f"broken {path_of(im['url'])}")
                continue
            problems.append({"type": "broken-image", "src": im["src"]})
            continue
        if im["nw"] and im["nh"] and im["fit"] != "cover":
            ratio_n = im["nw"] / im["nh"]
            ratio_r = im["w"] / im["h"] if im["h"] else 0
            if ratio_r and abs(ratio_n - ratio_r) / ratio_n > 0.05:
                problems.append({"type": "image-distortion", "src": im["src"],
                                 "detail": f'natural={im["nw"]}x{im["nh"]} render={im["w"]}x{im["h"]}'})
    if pending_images:
        problems.append({"type": "image-not-loaded",
                         "detail": f"{pending_images} 张图片在滚动触发懒加载后仍未完成"})

    if is_mobile:
        taps = page.evaluate(TAP_JS)
        if taps:
            problems.append({"type": "small-tap-target", "vp": vp_name, "count": len(taps), "sample": taps[:5]})

    # 404 测试页本身返回 404 属预期，不计入缺陷
    if expect_404:
        console_errors = [c for c in console_errors if "404" not in c]
        failed = [f for f in failed if "does-not-exist" not in f]
    # 仅当 404 全部来自白名单时才豁免控制台 404 报错
    if ignored_404 and not failed:
        console_errors = [c for c in console_errors if "404" not in c]
    if status >= 400 and not expect_404:
        problems.append({"type": "http-status", "detail": str(status)})
    if console_errors:
        problems.append({"type": "console-error", "detail": console_errors[:4]})
    if page_errors:
        problems.append({"type": "js-exception", "detail": page_errors[:4]})
    if failed:
        problems.append({"type": "failed-request", "detail": failed[:6]})

    page.remove_listener("console", on_console)
    page.remove_listener("pageerror", on_pageerror)
    page.remove_listener("response", on_response)
    if ignored_log is not None and ignored_404:
        ignored_log.append(f"{vp_name}px {url} :: {sorted(set(ignored_404))[:3]}")
    return problems


TAP_JS = """
() => Array.from(document.querySelectorAll('a,button')).map(el => {
  const r = el.getBoundingClientRect();
  if (r.width === 0 || r.height === 0) return null;
  const st = getComputedStyle(el);
  if (st.visibility === 'hidden' || st.display === 'none') return null;
  if (el.closest('.post-content')) return null;          // WCAG 内联豁免
  if (st.display === 'inline' && st.position === 'static' && el.closest('p,li,figcaption')) return null;
  if (r.height < 24 || r.width < 24) {
    return { tag: el.tagName.toLowerCase(), cls: (typeof el.className === 'string' ? el.className : '').slice(0, 40),
             text: (el.textContent || '').trim().slice(0, 20), w: Math.round(r.width), h: Math.round(r.height) };
  }
  return null;
}).filter(Boolean)
"""


def run(h):
    if not reachable(BASE + "/"):
        h.fatal_error("被审计站点不可达", BASE)
        return

    urls, stats = get_urls(BASE, full=FULL)
    print(f"模式: {'FULL（全站）' if FULL else 'SAMPLED（抽样）'}")
    print(f"SITEMAP HTML PAGES = {stats['sitemap_html']} (sitemap <loc> 总数 {stats['sitemap_total']})")
    if FULL:
        print(f"EXTRA PAGINATION PAGES = {stats['extra_pagination']} "
              f"(Hugo sitemap 不含 /page/N/，由站点实际链接抓取)")
    print(f"AUDITED HTML PAGES = {stats['audited_html']}")
    if stats["skipped"]:
        print(f"SKIPPED INTENTIONAL ENDPOINTS = {len(stats['skipped'])}")
        for p, why in stats["skipped"][:10]:
            print(f"    - {p}  ({why})")
    else:
        print("SKIPPED INTENTIONAL ENDPOINTS = 0")
    print(f"探针页面: /this-page-does-not-exist/ (404.html)  |  本次实际加载 {len(urls)} 个 URL")

    if not stats["sitemap_ok"]:
        h.fatal_error("sitemap 获取失败", f"{BASE}/sitemap.xml 无法解析，无法枚举站点页面")
        return
    if FULL and (stats["audited_html"] - stats["extra_pagination"]) != stats["sitemap_html"]:
        h.fatal_error("全站审计页面数与 sitemap 不一致",
                      f"sitemap 页 {stats['sitemap_html']}，实际审计 sitemap 页 "
                      f"{stats['audited_html'] - stats['extra_pagination']}")
        return
    if FULL and stats["missing_specials"]:
        h.fatal_error("全站审计缺少必需页面类型", "、".join(stats["missing_specials"]))
        return
    if len(urls) < 5:
        h.fatal_error("可审计 URL 过少", f"仅 {len(urls)} 条")
        return

    if FULL:
        h.record("全站审计覆盖 sitemap 全部 HTML 页面",
                 True, f"{stats['audited_html']} 页")
        for name, pred in REQUIRED_COVERAGE:
            hit = [p for p in urls if pred(p)][:1]
            h.record(f"覆盖面：{name} 已纳入审计", bool(hit), hit[0] if hit else "未找到")

    plan_all = {
        "chromium": ["320", "375", "390", "430", "768", "1024", "1440"],
        "firefox": ["375", "768", "1440"],
        "webkit": ["375", "768", "1440"],
    }
    only = [b.strip() for b in os.environ.get("AUDIT_BROWSERS", "").split(",") if b.strip()]
    plan = {k: v for k, v in plan_all.items() if (not only or k in only)}
    vps_env = os.environ.get("AUDIT_VIEWPORTS", "")
    if vps_env.strip():
        vps = [v.strip() for v in vps_env.split(",") if v.strip()]
        plan = {k: vps for k in plan}
    if not plan:
        h.fatal_error("未选择任何浏览器", f"AUDIT_BROWSERS={os.environ.get('AUDIT_BROWSERS')}")
        return
    print("浏览器计划:", {k: f"{len(v)} 视口 × {len(urls)} 页" for k, v in plan.items()})

    report = {"coverage": {**stats, "mode": "full" if FULL else "sampled",
                           "urls": len(urls), "plan": plan}}
    by_type = {}
    total_problems = 0
    ignored_log = []

    with sync_playwright() as p:
        for browser_name, vps in plan.items():
            launcher = {"chromium": p.chromium, "firefox": p.firefox, "webkit": p.webkit}[browser_name]
            try:
                browser = launch(launcher)
            except Exception as e:
                h.fatal_error(f"{browser_name} 浏览器启动失败", str(e)[:200])
                continue

            browser_report = {}
            for vp in vps:
                ctx = browser.new_context(viewport=VIEWPORTS[vp], locale="zh-CN",
                                          is_mobile=int(vp) <= 430, has_touch=int(vp) <= 430)
                page = ctx.new_page()
                vp_problems = 0
                for url in urls:
                    probs = check_page(page, url, vp, int(vp) <= 430, ignored_log)
                    if probs:
                        browser_report.setdefault(vp, {})[url] = probs
                        vp_problems += len(probs)
                        total_problems += len(probs)
                        for pr in probs:
                            key = (browser_name, pr["type"])
                            by_type.setdefault(key, {"count": 0, "samples": []})
                            by_type[key]["count"] += 1
                            if len(by_type[key]["samples"]) < 4:
                                by_type[key]["samples"].append(
                                    f'{vp}px {url} :: ' +
                                    str(pr.get("detail") or pr.get("elements") or pr.get("src") or pr.get("count"))[:170])
                ctx.close()
                h.record(f"[{browser_name}] {vp}px × {len(urls)} 页",
                         vp_problems == 0,
                         "无问题" if vp_problems == 0 else f"{vp_problems} 个问题")
            browser.close()
            report[browser_name] = browser_report

    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=1)

    for key in sorted(by_type, key=lambda k: -by_type[k]["count"]):
        info = by_type[key]
        print(f'\n### {key[0]} / {key[1]}  x{info["count"]}')
        for s in info["samples"]:
            print("   ", s)
    print(f"\nTOTAL PROBLEMS: {total_problems} -> {OUT}")
    if ignored_log:
        print(f"白名单豁免（故意缺失的测试资源，已逐条列出）: {len(ignored_log)} 处")
        for s in ignored_log[:6]:
            print("   ", s)


def main():
    h = Harness("audit")
    guard(h, run, h)
    h.finish()


if __name__ == "__main__":
    main()
