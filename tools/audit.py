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
from html_inventory import scan as scan_inventory  # noqa: E402

from playwright.sync_api import sync_playwright  # noqa: E402

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8088"
ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
OUT = os.path.join(ROOT, "tools", "audit_report.json")
# Release 全站模式的真值来自构建产物 inventory；可用 AUDIT_BUILD_DIR 覆盖
BUILD_DIR = os.environ.get("AUDIT_BUILD_DIR", os.path.join(ROOT, "public"))
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


PAGINATION_HREF_RE = re.compile(r'href=["\']?([^"\'> ]*/page/\d+/)')

DISCOVERY_RETRIES = 2          # 每个 URL 的重试次数（总尝试 = 1 + 2 = 3 次）


def _fetch_once(base, path):
    """单次抓取。返回 (html, failure_reason)，不做重试。

    重试由 _fetch_with_retry 负责 —— 这样注入的假 fetch 也能被重试覆盖，
    重试语义才可被 tools/test_pagination_retry.py 真实验证。
    """
    try:
        with urllib.request.urlopen(base + path, timeout=10) as r:
            return r.read().decode("utf-8", "ignore"), None
    except Exception as e:
        return None, f"{type(e).__name__}: {str(e)[:80]}"


def _fetch_with_retry(fetch, base, path, stats):
    """带重试的抓取。全部重试失败才返回失败 —— **不再静默 continue**。"""
    last_err = None
    for attempt in range(DISCOVERY_RETRIES + 1):
        stats["attempts"] += 1
        html, err = fetch(base, path)
        if err is None:
            return html, None
        last_err = err
        if attempt < DISCOVERY_RETRIES:
            stats["retries"] += 1
            if stats["retries"] <= 10:
                print(f"  [retry {attempt + 1}/{DISCOVERY_RETRIES}] {path} -> {err}")
    return None, last_err


def discover_pagination(base, seeds, limit=None, fetch=None):
    """队列耗尽式分页发现（Hugo 的 sitemap 不包含 /page/N/）。

    从种子页（列表页 / 分类 term / 标签 term / 归档等所有可能产生分页的页面）
    出发做 BFS：解析页面上所有含 /page/N/ 的链接，新发现的分页页继续入队，
    **直到队列耗尽（没有任何新分页页）为止**。

    完成条件必须同时满足：
      * 队列耗尽；
      * discovery_failures 为空。

    任何一次抓取在耗尽重试后仍失败，都记入 discovery_failures，
    FULL 模式下据此判 FAIL —— 绝不允许"抓取失败 + 队列空 + 判 PASS"。

    limit 是防失控的安全上限，不是覆盖目标：达到即 exhausted=False，
    调用方必须判定"未完成全站审计"并 FAIL。

    fetch 仅用于测试注入（默认走真实 HTTP）。
    """
    if limit is None:
        limit = int(os.environ.get("AUDIT_PAGINATION_LIMIT", "10000"))
    if fetch is None:
        fetch = _fetch_once

    found = set()
    visited = set()
    queue = []
    for p in seeds:
        if p not in visited:
            visited.add(p)
            queue.append(p)
    rounds = 0
    limit_reached = False
    stats = {"attempts": 0, "retries": 0}
    failures = []

    while queue and not limit_reached:
        rounds += 1
        next_frontier = []
        for page_path in queue:
            html, err = _fetch_with_retry(fetch, base, page_path, stats)
            if err is not None:
                failures.append({"url": page_path, "error": err})
                if len(failures) <= 10:
                    print(f"  [discovery-failure] {page_path} -> {err}")
                elif len(failures) == 11:
                    print("  [discovery-failure] ...（后续失败不再逐条打印，"
                          "最终以 DISCOVERY FAILURES 计数判定）")
                continue
            for href in PAGINATION_HREF_RE.findall(html):
                path = path_of(href if href.startswith("/") else "/" + href)
                if path in found or path in visited:
                    continue
                if len(found) >= limit:
                    limit_reached = True
                    break
                found.add(path)
                visited.add(path)
                next_frontier.append(path)
            if limit_reached:
                break
        queue = next_frontier

    queue_exhausted = not queue
    meta = {
        "discovered": len(found),
        "rounds": rounds,
        "limit": limit,
        "queue_exhausted": queue_exhausted,
        "discovery_attempts": stats["attempts"],
        "discovery_retries": stats["retries"],
        "discovery_failures": failures,
        "limit_reached": limit_reached,
        # 只有队列耗尽且零失败才算覆盖完整
        "exhausted": queue_exhausted and not failures and not limit_reached,
    }
    return sorted(found), meta


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
             "skipped": [], "audited_html": 0, "missing_specials": [], "sitemap_ok": False,
             "pagination_crawl": None, "sitemap_bad_urls": [],
             "sitemap_only_urls": [], "not_in_sitemap": []}
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
        stats["sitemap_html"] = len(html_pages)
        stats["skipped"] = skipped
        stats["sitemap_ok"] = len(locs) > 0
        # sitemap 独立质量检查：URL 必须合法
        stats["sitemap_bad_urls"] = [l for l in locs
                                     if not l.startswith(("http://", "https://"))]
    except Exception as e:
        print("sitemap error:", e)

    if full:
        # ---- Release 全站真值 = 构建产物 inventory（不是 sitemap）----
        inv = scan_inventory(BUILD_DIR)
        stats["inventory"] = inv
        expected = list(inv["expected_html_urls"])
        stats["public_html_files"] = inv["public_html_files"]

        # sitemap 仅作为独立 SEO 索引检查，不再充当全站真值
        stats["sitemap_only_urls"] = [p for p in html_pages
                                      if p not in set(expected)]
        stats["not_in_sitemap"] = [p for p in expected
                                   if p not in set(html_pages)]

        # 分页发现：种子取 inventory 中的"正常内容页且非文章页"
        # （alias 页本身不含分页链接，抓它纯属浪费；它仍在审计列表里）
        alias_urls = set(inv.get("urls_by_class", {}).get("alias", []))
        seeds = [p for p in expected
                 if not is_article_page(p) and p not in alias_urls] or ["/", "/posts/"]
        extra, crawl = discover_pagination(base, seeds)
        stats["pagination_crawl"] = crawl
        stats["extra_pagination"] = len([p for p in extra if p not in set(expected)])

        # 审计 URL = inventory 真值 + sitemap 独有的 URL + 新发现的分页
        urls = list(expected) + [p for p in html_pages if p not in set(expected)]
        urls += [p for p in extra if p not in set(urls)]
        seen, uniq = set(), []
        for u in urls:
            if u not in seen:
                seen.add(u)
                uniq.append(u)
        urls = uniq
        stats["audited_html"] = len(urls)
        for name, pred in REQUIRED_COVERAGE:
            if not any(pred(p) for p in urls):
                stats["missing_specials"].append(name)
    else:
        posts = [p for p in html_pages if p.startswith("/posts/")]
        cats = [p for p in html_pages if p.startswith("/categories/")]
        tags = [p for p in html_pages if p.startswith("/tags/")]
        pages = [p for p in html_pages if "/page/" in p]
        if not pages:      # sitemap 不含分页，抽样时按需抓一份（抽样模式允许小额上限）
            pages, _ = discover_pagination(base, ["/", "/posts/"], limit=20)
            if pages:
                stats["pagination_crawl_sampled"] = True
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


def _loaded_expr():
    """JS 片段：图片是否算"已加载好"。

    只统计**真正会发起网络请求**的图片：
      * 必须有非空 src / currentSrc —— 否则（如灯箱容器里那个待填的 `<img alt="">`）
        永远不会 complete，webkit 下会被误判成"懒加载图片未完成"；
      * 尺寸为 0 的元素（display:none / 未布局）同样跳过。

    注意不能用 `!i.complete` 单独判定：`complete` 在图片还在排队解码时即为 true，
    但那时 `naturalWidth` 可能仍是 0。因此要求 complete 且已解码出实际宽度。
    """
    return """() => Array.from(document.images).filter(i => {
            const s = i.currentSrc || i.getAttribute('src') || '';
            if (!s) return false;
            const r = i.getBoundingClientRect();
            if (r.width === 0 || r.height === 0) return false;
            return true;
        })"""


REVIEW_ROUNDS = 2      # 首轮之后的复查轮数（预算逐轮加倍）


def settle_lazy_images(page, budget_ms=8000):
    """滚动触发懒加载 -> 等图片完成 -> 滚回顶部 -> 有界等待网络静默 -> 复查。

    返回未完成图片的**明细列表**（用于 image-not-loaded 判定与 CI 日志定位）。

    两个关键点：
      1. **必须先等网络静默，再采样 pending**。此前把 pending 采样放在 networkidle
         之前，等于"等完网络却用旧快照下结论"，CI 机器负载高时会误报。
      2. **只统计真正会加载的图片**（有 src 且有尺寸）。灯箱里那个待填的
         `<img alt="">` 没有 src，webkit 下 `complete` 长期为 false，
         会被误判成"懒加载图片未完成"—— 这是审计脚本缺陷，不是产品缺陷。
    """
    base = _loaded_expr()

    def pending_now():
        """返回未完成图片的**明细**（而不只是数量），便于 CI 日志直接定位。"""
        # 故意缺失的测试资源（白名单）不应计入"未加载"——它们本来就加载不出来。
        # 判定 broken-image 时已按 pathname 精确豁免，这里必须同步豁免，
        # 否则同一张图会先被豁免一次、又被判"未完成"一次（CI 上表现为 Release 审计挂掉）。
        exempt = json.dumps(list(INTENTIONAL_MISSING_PATHS))
        try:
            return page.evaluate(
                base + f"""
                .filter(i => !i.complete || i.naturalWidth === 0)
                .filter(i => !({exempt}).includes((i.currentSrc || i.getAttribute('src') || '')
                                                 .replace(/^https?:\\/\\/[^/]+/, '')
                                                 .replace(/[?#].*$/, '')))
                .map(i => ({{
                    src: (i.currentSrc || i.getAttribute('src') || '').split('/').pop(),
                    path: (i.currentSrc || i.getAttribute('src') || '')
                             .replace(/^https?:\\/\\/[^/]+/, '').replace(/[?#].*$/, ''),
                    complete: i.complete,
                    nw: i.naturalWidth,
                    loading: i.getAttribute('loading') || '',
                    w: Math.round(i.getBoundingClientRect().width),
                    h: Math.round(i.getBoundingClientRect().height)
                }}))""")
        except Exception:
            return []

    def wait_loaded():
        try:
            page.wait_for_function(
                base + ".every(i => i.complete && i.naturalWidth > 0)",
                timeout=budget_ms)
        except Exception:
            pass

    try:
        page.evaluate(SCROLL_JS)
    except Exception:
        pass

    wait_loaded()
    try:
        page.wait_for_load_state("networkidle", timeout=4000)
    except Exception:
        pass

    pending = pending_now()
    # 分级复查：CI runner 负载高时，webkit 解码 SVG 封面会明显排队
    # （实测 3s 人为延迟下需要约 12s 才收敛）。单次 8s 预算 + 单次复查
    # 仍会偶发误报，因此复查预算逐轮加倍；但**判定标准不变**——
    # 所有轮次结束后仍未完成的图片照样判为缺陷，不会被"多等几轮"洗白。
    for attempt in range(1, REVIEW_ROUNDS + 1):
        if not pending:
            break
        try:
            page.evaluate(SCROLL_JS)
        except Exception:
            pass
        try:
            page.wait_for_function(
                base + ".every(i => i.complete && i.naturalWidth > 0)",
                timeout=budget_ms * (2 ** attempt))
        except Exception:
            pass
        try:
            page.wait_for_load_state("networkidle", timeout=4000)
        except Exception:
            pass
        pending = pending_now()
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
        # 打印明细而非仅数量：否则 CI 只能看到"1 张图片未完成"，
        # 无法判断是哪张、是否偶发，必须靠猜。
        detail_lines = "; ".join(
            f'{p.get("src") or "(no-src)"}[loading={p.get("loading") or "-"},'
            f'complete={p.get("complete")},nw={p.get("nw")},'
            f'box={p.get("w")}x{p.get("h")}]'
            for p in pending_images[:4])
        problems.append({"type": "image-not-loaded",
                         "detail": f"{len(pending_images)} 张图片在滚动触发懒加载后仍未完成: {detail_lines}",
                         "src": ", ".join((p.get("src") or "(no-src)") for p in pending_images[:4])})

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
    crawl = stats.get("pagination_crawl") or {}
    inv = stats.get("inventory") or {}
    loaded_urls = set()      # 实际加载过的 HTML URL（用于报告与交叉验证）

    # ---------------- 覆盖证明（Release 报告的核心数字）----------------
    print(f"模式: {'FULL（全站）' if FULL else 'SAMPLED（抽样）'}")
    PROBE = "/this-page-does-not-exist/"     # 404 探针：故意不存在的 URL，不参与 inventory 比对
    if FULL:
        expected = set(inv.get("expected_html_urls") or [])
        audited = set(urls) - {PROBE}
        missing = sorted(expected - audited)
        unexpected = sorted(audited - expected)
        sitemap_urls = set(stats.get("sitemap_only_urls") or []) | set(expected) - set(
            stats.get("not_in_sitemap") or [])
        print("=== Release HTML 覆盖证明 ===")
        print(f"PUBLIC HTML FILES = {inv.get('public_html_files')}")
        print(f"FILESYSTEM EXPECTED URLS = {len(expected)}")
        print(f"SITEMAP HTML URLS = {stats['sitemap_html']}")
        print(f"DISCOVERED PAGINATION URLS = {crawl.get('discovered')} "
              f"(其中 inventory 之外的新增: {stats.get('extra_pagination')})")
        print("  注：分页页本身也在构建产物中，crawler 的作用是交叉验证"
              "没有 inventory 之外的分页遗漏")
        print(f"AUDITED HTML URLS = {len(audited)}")
        print(f"MISSING URLS = {len(missing)}" + (f" {missing[:5]}" if missing else ""))
        print(f"UNEXPECTED URLS = {len(unexpected)}" + (f" {unexpected[:5]}" if unexpected else ""))
        print(f"DISCOVERY FAILURES = {len(crawl.get('discovery_failures') or [])}")
        print(f"PAGINATION EXHAUSTED = {'YES' if crawl.get('exhausted') else 'NO'}")
        print(f"DISCOVERY ATTEMPTS = {crawl.get('discovery_attempts')} "
              f"(RETRIES = {crawl.get('discovery_retries')})")
        print(f"构建产物分类: {inv.get('by_class')}")
        if inv.get("excluded"):
            print("显式登记的排除项（不应为空而不说明）:")
            for u, why in inv["excluded"]:
                print(f"    - {u} ({why})")
        # sitemap 与 inventory 的双向差异（可观测性）
        only_sitemap = sorted(set(stats.get("sitemap_only_urls") or []))
        not_in_sitemap = sorted(set(stats.get("not_in_sitemap") or []))
        print(f"仅在 sitemap、不在构建产物: {len(only_sitemap)}")
        print(f"在构建产物、被 sitemap 排除: {len(not_in_sitemap)}（例如 /page/1/ 别名页）")
        if not_in_sitemap[:3]:
            print(f"    例: {not_in_sitemap[:3]}")
    else:
        expected = set()
        audited = set(urls) - {PROBE}
        missing = unexpected = []
        print(f"SITEMAP HTML PAGES = {stats['sitemap_html']} (sitemap <loc> 总数 {stats['sitemap_total']})")
        print(f"AUDITED HTML PAGES = {stats['audited_html']}")
    if stats["skipped"]:
        print(f"SKIPPED NON-HTML ENDPOINTS = {len(stats['skipped'])}")
        for p_, why in stats["skipped"][:10]:
            print(f"    - {p_}  ({why})")
    else:
        print("SKIPPED NON-HTML ENDPOINTS = 0")
    print(f"404 PROBE = 1 ({PROBE}，不参与 inventory 比对)"
          f"  |  本次实际加载 {len(urls)} 个 URL")

    # ---------------- 硬断言 ----------------
    if not stats["sitemap_ok"]:
        h.fatal_error("sitemap 检查失败", f"{BASE}/sitemap.xml 无法解析")
        return
    if stats.get("sitemap_bad_urls"):
        h.fatal_error("sitemap 含非法 URL", str(stats["sitemap_bad_urls"][:5]))
        return
    if FULL:
        # ⓪ 与 check_html_quality 的 inventory 交叉验证
        # （两套检查必须用同一份规范化结果；任何一套漏掉都要 CI 红）
        inv_json = os.path.join(ROOT, "tools", "html_inventory.json")
        if os.path.isfile(inv_json):
            with open(inv_json, encoding="utf-8") as f:
                other = json.load(f)
            other_urls = set(other.get("expected_html_urls") or [])
            only_audit = sorted(expected - other_urls)
            only_other = sorted(other_urls - expected)
            print(f"交叉验证 check_html_quality inventory: "
                  f"{len(other_urls)} 个 URL"
                  f"{'（一致）' if not only_audit and not only_other else '（不一致）'}")
            if only_audit or only_other:
                h.fatal_error("audit 与 HTML quality 的 inventory 不一致",
                              f"仅 audit 有: {only_audit[:5]}；"
                              f"仅 HTML quality 有: {only_other[:5]}")
                return
            h.record("audit 与 HTML quality inventory 完全一致",
                     True, f"{len(other_urls)} 个 URL")
        else:
            print("交叉验证: 未找到 tools/html_inventory.json（跳过，"
                  "CI 中 static-checks 会先生成）")

        # ① 构建产物 inventory 100% 被审计
        if missing:
            h.fatal_error("构建产物中存在未被审计的 HTML（inventory 覆盖不完整）",
                          f"缺失 {len(missing)} 个: {missing[:8]}")
            return
        if unexpected:
            h.fatal_error("审计了构建产物中不存在的 URL",
                          f"多出 {len(unexpected)} 个: {unexpected[:8]}")
            return
        # ② 分页发现零失败
        fails = crawl.get("discovery_failures") or []
        if fails:
            h.fatal_error("分页发现存在抓取失败（不允许 fetch failed + exhausted）",
                          "；".join(f"{f['url']} -> {f['error']}" for f in fails[:5]))
            return
        # ③ 队列耗尽（未达上限）
        if not crawl.get("exhausted"):
            if crawl.get("limit_reached"):
                detail = (f"发现 {crawl.get('discovered')} 个分页页即达到 "
                          f"limit={crawl.get('limit')}，可能仍有未发现的分页页。"
                          f"判定：未完成全站审计。")
            else:
                detail = "队列未耗尽或存在抓取失败，判定：未完成全站发现。"
            h.fatal_error("分页爬取未完成（未耗尽 / 达到安全上限）", detail)
            return
        if stats["missing_specials"]:
            h.fatal_error("全站审计缺少必需页面类型", "、".join(stats["missing_specials"]))
            return
    if len(urls) < 5:
        h.fatal_error("可审计 URL 过少", f"仅 {len(urls)} 条")
        return

    if FULL:
        h.record("Release 覆盖：构建产物 HTML 100% 被审计（inventory 真值）",
                 not missing, f"{len(expected)} 个 URL，缺失 {len(missing)}")
        h.record("Release 覆盖：无审计产物中不存在的 URL",
                 not unexpected, f"多出 {len(unexpected)} 个")
        h.record("分页发现零失败（discovery_failures = 0）",
                 not crawl.get("discovery_failures"),
                 f"attempts={crawl.get('discovery_attempts')} "
                 f"retries={crawl.get('discovery_retries')}")
        h.record("分页爬取已耗尽（exhausted）",
                 bool(crawl.get("exhausted")),
                 f"rounds={crawl.get('rounds')} limit={crawl.get('limit')} "
                 f"discovered={crawl.get('discovered')}")
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
                           "urls": len(urls), "plan": plan,
                           "loaded_urls": sorted(loaded_urls),
                           "expected_urls": sorted(expected) if FULL else []}}
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
                    if url not in loaded_urls:
                        loaded_urls.add(url)
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
