#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Nebula 主题验收自动化：多浏览器 × 多视口 × 站点页面

检查项：
  - 控制台错误 / 未捕获异常 / 失败请求(404 等)
  - 横向滚动与元素溢出
  - 图片变形 / 图片加载失败
  - 移动端点击区域过小（正文内联链接按 WCAG 1.4.10 内联豁免，不计入）

退出码约定（见 tools/_testlib.py）：
  * 发现任一问题            -> exit 1
  * 任一浏览器启动失败      -> exit 1
  * sitemap 获取失败        -> exit 1（无法枚举页面时审计结果不可信）
  * 目标站点不可达          -> exit 1
  * 脚本自身异常            -> exit 1

页面范围：
  * 默认抽样（关键页面 + sitemap 抽样页面）—— 适合每次 PR
  * AUDIT_FULL=1 时扫描 sitemap 中全部页面 —— 适合 release 门禁

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

# 关键入口（始终检查）
KEY_URLS = ["/", "/posts/", "/categories/", "/tags/", "/archives/", "/about/", "/index.json"]
# 显式排除：sitemap 中不该被当作 HTML 页面审计的路径
SKIP_PREFIX = ("/search/", "/index.json", "/categories/", "/tags/", "/page/")

# 已知的"故意缺失资源"白名单（压力测试数据）：用于验证图片缺失时的降级渲染，
# 属于内容作者故意为之，不是主题缺陷。白名单必须显式列出并被计数打印，
# 不允许静默忽略，避免掩盖真实问题。
INTENTIONAL_MISSING = ("not-exist.png",)

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
    src: (img.currentSrc || '').split('/').slice(-1)[0],
    nw: img.naturalWidth, nh: img.naturalHeight,
    w: Math.round(r.width), h: Math.round(r.height),
    fit: getComputedStyle(img).objectFit,
    broken: img.complete && img.naturalWidth === 0
  };
})
"""

# 点击区域：正文内联链接属于 WCAG 1.4.10「内联」豁免范围，不做要求
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


def get_urls(base, full=False):
    """返回 (urls, sitemap_ok)。sitemap 获取失败时 sitemap_ok=False，调用方必须判为致命错误。"""
    urls = list(KEY_URLS)
    sitemap_ok = False
    try:
        with urllib.request.urlopen(base + "/sitemap.xml", timeout=15) as r:
            xml = r.read().decode("utf-8")
        locs = re.findall(r"<loc>(.*?)</loc>", xml)
        from urllib.parse import urlparse as _up
        pages = []
        for loc in locs:
            path = _up(loc).path or "/"
            if any(path.startswith(p) for p in SKIP_PREFIX):
                continue
            if path.endswith("/") or path.endswith(".html"):
                pages.append(path)
        if full:
            urls += pages
        else:
            posts = [p for p in pages if p.startswith("/posts/")]
            other = [p for p in pages if not p.startswith("/posts/")]
            urls += posts[:8] + other[:12]
        sitemap_ok = len(locs) > 0
    except Exception as e:
        print("sitemap error:", e)
    urls.append("/this-page-does-not-exist/")
    seen, uniq = set(), []
    for u in urls:
        if u not in seen:
            seen.add(u)
            uniq.append(u)
    return uniq, sitemap_ok


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
            if any(resp.url.endswith(x) for x in INTENTIONAL_MISSING):
                ignored_404.append(resp.url)     # 故意缺失的测试资源，计数但不计缺陷
                return
            failed.append(f"{resp.status} {resp.url}")

    page.on("console", on_console)
    page.on("pageerror", on_pageerror)
    page.on("response", on_response)

    try:
        resp = page.goto(BASE + url, wait_until="load", timeout=25000)
    except Exception as e:
        problems.append({"type": "navigation", "detail": str(e)[:160]})
        page.remove_listener("console", on_console)
        page.remove_listener("pageerror", on_pageerror)
        page.remove_listener("response", on_response)
        return problems

    status = resp.status if resp else 0
    expect_404 = url.rstrip("/").endswith("does-not-exist")
    page.wait_for_timeout(180)

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
            if any((im["src"] or "").endswith(x) for x in INTENTIONAL_MISSING):
                ignored_404.append(im["src"])
                continue
            problems.append({"type": "broken-image", "src": im["src"]})
        elif im["nw"] and im["nh"] and im["fit"] != "cover":
            ratio_n = im["nw"] / im["nh"]
            ratio_r = im["w"] / im["h"] if im["h"] else 0
            if ratio_r and abs(ratio_n - ratio_r) / ratio_n > 0.05:
                problems.append({"type": "image-distortion", "src": im["src"],
                                 "detail": f'natural={im["nw"]}x{im["nh"]} render={im["w"]}x{im["h"]}'})

    if is_mobile:
        taps = page.evaluate(TAP_JS)
        if taps:
            problems.append({"type": "small-tap-target", "vp": vp_name, "count": len(taps), "sample": taps[:5]})

    # 404 测试页本身返回 404 属预期，不计入缺陷
    if expect_404:
        console_errors = [c for c in console_errors if "404" not in c]
        failed = [f for f in failed if "does-not-exist" not in f]
    # 若 404 全部来自"故意缺失的测试资源"，则控制台 404 报错一并豁免
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


def run(h):
    if not reachable(BASE + "/"):
        h.fatal_error("被审计站点不可达", BASE)
        return

    urls, sitemap_ok = get_urls(BASE, full=FULL)
    print(f"审计 URL: {len(urls)} 条（{'全站扫描' if FULL else '抽样'}），sitemap_ok={sitemap_ok}")
    if not sitemap_ok:
        # 只靠 8 条硬编码入口得出的"无问题"是不可信的，必须失败
        h.fatal_error("sitemap 获取失败", f"{BASE}/sitemap.xml 无法解析，无法枚举站点页面")
        return
    if len(urls) < 5:
        h.fatal_error("可审计 URL 过少", f"仅 {len(urls)} 条")
        return

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
    print("浏览器计划:", {k: len(v) for k, v in plan.items()})

    report = {}
    by_type = {}
    total_problems = 0
    ignored_log = []

    with sync_playwright() as p:
        for browser_name, vps in plan.items():
            launcher = {"chromium": p.chromium, "firefox": p.firefox, "webkit": p.webkit}[browser_name]
            try:
                browser = launch(launcher)
            except Exception as e:
                # 浏览器起不来 = 无法验证 = 必须失败，绝不能静默跳过
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
        # 显式列出被豁免的项，避免"静默忽略"掩盖真实问题
        print(f"已知故意缺失的测试资源（内容作者行为，已豁免）: {len(ignored_log)} 处")
        for s in ignored_log[:4]:
            print("   ", s)


def main():
    h = Harness("audit")
    guard(h, run, h)
    h.finish()


if __name__ == "__main__":
    main()
