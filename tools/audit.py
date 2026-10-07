#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Nebula 主题验收自动化：多浏览器 × 多视口 × 全页面

检查项：
  - 控制台错误 / 未捕获异常 / 失败请求(404 等)
  - 横向滚动与元素溢出
  - 图片变形（正文中 object-fit 非 cover 的图片）
  - 移动端点击区域过小
输出：tools/audit_report.json
"""
import json
import os
import sys
import urllib.request
# 环境存在 HTTP 代理，需放行本地回环地址，否则浏览器会把 localhost 也走代理
os.environ.setdefault("NO_PROXY", "127.0.0.1,localhost")
os.environ.setdefault("no_proxy", "127.0.0.1,localhost")

from playwright.sync_api import sync_playwright

# 代理仅用于本地开发环境；CI 中不设置 PLAYWRIGHT_PROXY 即为直连
_proxy = os.environ.get("PLAYWRIGHT_PROXY")
PROXY = {"server": _proxy, "bypass": "127.0.0.1,localhost"} if _proxy else None


def _launch(module, **kw):
    return module.launch(proxy=PROXY, **kw) if PROXY else module.launch(**kw)


BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8088"
ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
OUT = os.path.join(ROOT, "tools", "audit_report.json")

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

TAP_JS = """
() => Array.from(document.querySelectorAll('a,button')).map(el => {
  const r = el.getBoundingClientRect();
  if (r.width === 0 || r.height === 0) return null;
  const st = getComputedStyle(el);
  if (st.visibility === 'hidden' || st.display === 'none') return null;
  if (r.height < 24 || r.width < 24) {
    return { tag: el.tagName.toLowerCase(), cls: (typeof el.className === 'string' ? el.className : '').slice(0, 40),
             text: (el.textContent || '').trim().slice(0, 20), w: Math.round(r.width), h: Math.round(r.height) };
  }
  return null;
}).filter(Boolean)
"""


def get_urls(base):
    """从 sitemap 取所有页面 + 关键入口 + 404"""
    urls = ["/", "/posts/", "/categories/", "/tags/", "/archives/", "/about/", "/index.json"]
    try:
        with urllib.request.urlopen(base + "/sitemap.xml", timeout=10) as r:
            xml = r.read().decode("utf-8")
        import re
        locs = re.findall(r"<loc>(.*?)</loc>", xml)
        posts = []
        cats = []
        tags = []
        for loc in locs:
            from urllib.parse import urlparse as _up
            path = _up(loc).path or "/"
            if path.startswith("/posts/") and path.endswith("/"):
                posts.append(path)
            elif path.startswith("/categories/"):
                cats.append(path)
            elif path.startswith("/tags/"):
                tags.append(path)
        # 压力数据集下页面很多，抽样以保证测试时长可控
        urls += posts[:8] + cats[:5] + tags[:5]
    except Exception as e:
        print("sitemap error:", e)
    urls.append("/this-page-does-not-exist/")
    seen, uniq = set(), []
    for u in urls:
        if u not in seen:
            seen.add(u)
            uniq.append(u)
    return uniq


def check_page(page, url, vp_name, is_mobile):
    problems = []
    console_errors, page_errors, failed = [], [], []

    def on_console(msg):
        if msg.type == "error" and "livereload" not in msg.text:
            console_errors.append(msg.text[:200])
    def on_pageerror(err):
        page_errors.append(str(err)[:200])
    def on_response(resp):
        if resp.status >= 400 and "livereload" not in resp.url:
            failed.append(f"{resp.status} {resp.url}")

    page.on("console", on_console)
    page.on("pageerror", on_pageerror)
    page.on("response", on_response)

    try:
        resp = page.goto(BASE + url, wait_until="load", timeout=25000)
    except Exception as e:
        problems.append({"type": "navigation", "detail": str(e)[:160]})
        return problems
    finally:
        pass

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
    return problems


def main():
    urls = get_urls(BASE)
    print(f"URLs: {len(urls)}")
    report = {}

    # 浏览器 → 视口（控制执行规模）
    plan_all = {
        "chromium": ["320", "375", "390", "430", "768", "1024", "1440"],
        "firefox": ["375", "768", "1440"],
        "webkit": ["375", "768", "1440"],
        "msedge": ["390", "1440"],
    }
    # CI 中按 job 裁剪：AUDIT_BROWSERS=chromium / AUDIT_VIEWPORTS=320,375,...
    only = [b.strip() for b in os.environ.get("AUDIT_BROWSERS", "").split(",") if b.strip()]
    plan = {k: v for k, v in plan_all.items() if (not only or k in only)}
    vps_env = os.environ.get("AUDIT_VIEWPORTS", "")
    if vps_env.strip():
        vps = [v.strip() for v in vps_env.split(",") if v.strip()]
        plan = {k: vps for k in plan}
    print("浏览器计划:", {k: len(v) for k, v in plan.items()})

    with sync_playwright() as p:
        for browser_name, vps in plan.items():
            try:
                if browser_name == "chromium":
                    browser = _launch(p.chromium)
                elif browser_name == "firefox":
                    browser = _launch(p.firefox)
                elif browser_name == "webkit":
                    browser = _launch(p.webkit)
                else:
                    browser = _launch(p.chromium, channel="msedge")
            except Exception as e:
                report[browser_name] = {"launch_error": str(e)[:200]}
                print(f"[{browser_name}] launch failed: {str(e)[:120]}")
                continue

            browser_report = {}
            for vp in vps:
                ctx = browser.new_context(viewport=VIEWPORTS[vp], locale="zh-CN",
                                          is_mobile=int(vp) <= 430, has_touch=int(vp) <= 430)
                page = ctx.new_page()
                for url in urls:
                    probs = check_page(page, url, vp, int(vp) <= 430)
                    if probs:
                        browser_report.setdefault(vp, {})[url] = probs
                ctx.close()
                print(f"[{browser_name}] {vp}px done")
            browser.close()
            report[browser_name] = browser_report

    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=1)

    total = 0
    by_type = {}
    for b, v in report.items():
        if isinstance(v, dict) and "launch_error" in v:
            print("LAUNCH ERROR", b, v["launch_error"]); continue
        for vp, pages in v.items():
            for url, probs in pages.items():
                total += len(probs)
                for pr in probs:
                    key = (b, pr["type"])
                    by_type.setdefault(key, {"count": 0, "samples": []})
                    by_type[key]["count"] += 1
                    if len(by_type[key]["samples"]) < 4:
                        by_type[key]["samples"].append(
                            f'{vp}px {url} :: {str(pr.get("detail") or pr.get("elements") or pr.get("src") or pr.get("count"))[:170]}')
    for key in sorted(by_type, key=lambda k: -by_type[k]["count"]):
        info = by_type[key]
        print(f'\n### {key[0]} / {key[1]}  x{info["count"]}')
        for s in info["samples"]:
            print("   ", s)
    print(f"\nTOTAL PROBLEMS: {total} -> {OUT}")


if __name__ == "__main__":
    main()
