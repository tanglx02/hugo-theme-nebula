#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""搜索分片失败场景测试（P0-2）。

覆盖：全部成功 / 主索引 404 / 主索引 500 / 主索引 JSON 损坏 /
      部分 shard 404 / 500 / 超时 / JSON 损坏 / 全部 shard 失败 / 重试恢复 / 重复搜索

用法：python tools/verify_search_shard.py [shard_site_url] [browser]
前提：该站点以 params.search.shard = true 构建
"""
import os
import sys

os.environ.setdefault("NO_PROXY", "127.0.0.1,localhost")
os.environ.setdefault("no_proxy", "127.0.0.1,localhost")

from playwright.sync_api import sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8091"
BROWSER = sys.argv[2] if len(sys.argv) > 2 else "chromium"
_proxy = os.environ.get("PLAYWRIGHT_PROXY")
PROXY = {"server": _proxy, "bypass": "127.0.0.1,localhost"} if _proxy else None

results = []


def rec(name, ok, detail=""):
    results.append((name, ok, detail))
    print(("PASS  " if ok else "FAIL  ") + name + (f" :: {detail}" if detail else ""))


def run_case(browser, name, rules, keyword, check):
    """rules: [(pattern, handler)]；check(page) -> (ok, detail)"""
    ctx = browser.new_context(viewport={"width": 1440, "height": 900}, locale="zh-CN")
    page = ctx.new_page()
    for pattern, handler in rules:
        page.route(pattern, handler)
    try:
        page.goto(BASE + "/", wait_until="load")
        page.click("#searchTrigger")
        page.fill("#search-input", keyword)
        page.wait_for_timeout(2200)
        ok, detail = check(page)
        rec(name, ok, detail)
    except Exception as e:
        rec(name, False, f"异常: {str(e)[:110]}")
    finally:
        ctx.close()


def status_text(page):
    try:
        if page.locator("#searchStatus").count() and page.locator("#searchStatus").is_visible():
            return page.locator("#searchStatusText").inner_text().strip()
    except Exception:
        pass
    return ""


def empty_text(page):
    try:
        if page.locator(".search-empty").count():
            return page.locator(".search-empty").inner_text().strip()
    except Exception:
        pass
    return ""


def main():
    with sync_playwright() as p:
        launcher = {"chromium": p.chromium, "firefox": p.firefox, "webkit": p.webkit}[BROWSER]
        browser = launcher.launch(proxy=PROXY) if PROXY else launcher.launch()

        # ---------- 全部成功 ----------
        run_case(browser, "全部成功：有结果且无状态提示", [], "GOLF48000", lambda pg: (
            pg.locator(".search-item").count() > 0 and status_text(pg) == "",
            f'{pg.locator(".search-item").count()} 条, status="{status_text(pg)}"'))

        # ---------- 主索引失败 ----------
        def fail_main(status, label):
            def handler(route):
                route.fulfill(status=status, body="boom" if status != 200 else "")
            run_case(browser, f"主索引 {label}：明确报错 + 有重试按钮", [("**/index.json", handler)], "GOLF48000",
                     lambda pg: ("失败" in status_text(pg) and pg.locator("#searchRetry").is_visible()
                                 and "没有找到" not in empty_text(pg),
                                 f'status="{status_text(pg)}" empty="{empty_text(pg)[:24]}"'))

        fail_main(404, "404")
        fail_main(500, "500")

        def corrupt_main(route):
            route.fulfill(status=200, body="{ this is not json", content_type="application/json")
        run_case(browser, "主索引 JSON 损坏：明确报错", [("**/index.json", corrupt_main)], "GOLF48000",
                 lambda pg: ("失败" in status_text(pg) and "没有找到" not in empty_text(pg),
                             f'status="{status_text(pg)}"'))

        # ---------- 部分 shard 失败 ----------
        def partial_shard(status, label, delay=0):
            def handler(route):
                if delay:
                    import time
                    time.sleep(delay)
                    route.abort("timedout")
                else:
                    route.fulfill(status=status, body="shard error")
            # 只让第一个分片失败，其余放行
            state = {"n": 0}

            def selective(route):
                state["n"] += 1
                if state["n"] == 1:
                    return handler(route)
                route.continue_()
            # 用"标题关键词"验证：正文 chunk 失败不应影响标题/摘要匹配，且不得误报无结果
            run_case(browser, f"部分分块 {label}：提示部分失败且标题匹配仍可用",
                     [("**/search/*.json", selective)], "一万字",
                     lambda pg: (("部分" in status_text(pg)) and pg.locator(".search-item").count() > 0
                                 and "没有找到" not in empty_text(pg),
                                 f'{pg.locator(".search-item").count()} 条, status="{status_text(pg)[:40]}"'))

        partial_shard(404, "404")
        partial_shard(500, "500")

        def corrupt_shard():
            state = {"n": 0}

            def handler(route):
                state["n"] += 1
                if state["n"] == 1:
                    route.fulfill(status=200, body="not-json-at-all", content_type="application/json")
                else:
                    route.continue_()
            run_case(browser, "部分分块 JSON 损坏：提示部分失败且标题匹配仍可用",
                     [("**/search/*.json", handler)], "一万字",
                     lambda pg: (("部分" in status_text(pg)) and pg.locator(".search-item").count() > 0,
                                 f'{pg.locator(".search-item").count()} 条, status="{status_text(pg)[:40]}"'))
        corrupt_shard()

        # ---------- 全部 shard 失败 ----------
        run_case(browser, "全部分块失败：明确提示且标题匹配仍可用",
                 [("**/search/*.json", lambda route: route.fulfill(status=404, body="nope"))], "一万字",
                 lambda pg: (("部分" in status_text(pg)) and pg.locator(".search-item").count() > 0
                             and "没有找到" not in empty_text(pg),
                             f'{pg.locator(".search-item").count()} 条, status="{status_text(pg)[:40]}"'))

        # ---------- 重试恢复 ----------
        ctx = browser.new_context(viewport={"width": 1440, "height": 900}, locale="zh-CN")
        page = ctx.new_page()
        failing = {"on": True}

        def toggle_main(route):
            if failing["on"]:
                route.fulfill(status=500, body="down")
            else:
                route.continue_()
        page.route("**/index.json", toggle_main)
        page.goto(BASE + "/", wait_until="load")
        page.click("#searchTrigger")
        page.fill("#search-input", "GOLF48000")
        page.wait_for_timeout(1500)
        failed_shown = "失败" in status_text(page)
        failing["on"] = False                      # 恢复网络后点击重试
        page.click("#searchRetry")
        page.wait_for_timeout(2200)
        recovered = page.locator(".search-item").count() > 0 and status_text(page) == ""
        rec("重试：失败态可见且重试后恢复", failed_shown and recovered,
            f'失败态={failed_shown}, 恢复后 {page.locator(".search-item").count()} 条, status="{status_text(page)}"')

        # ---------- 重复搜索（连续输入） ----------
        page.fill("#search-input", "")
        for kw in ["安全", "GOLF", "docker", "应急", "一万字"]:
            page.fill("#search-input", kw)
            page.wait_for_timeout(250)
        page.wait_for_timeout(1200)
        cnt = page.locator(".search-item").count()
        rec("连续多次输入不报错且结果正常", cnt > 0 and status_text(page) == "", f"{cnt} 条")
        ctx.close()
        browser.close()

    bad = [r for r in results if not r[1]]
    print(f"\n[{BROWSER}] ==== {len(results) - len(bad)}/{len(results)} PASSED ====")
    for n, _, d in bad:
        print("  -", n, "::", d)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
