#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""搜索边界测试（P5）：关键词类型 / 竞态 / 索引失败 / 延迟 / 大量结果。"""
import os
import sys

os.environ.setdefault("NO_PROXY", "127.0.0.1,localhost")
os.environ.setdefault("no_proxy", "127.0.0.1,localhost")

from playwright.sync_api import sync_playwright

# 代理仅用于本地开发环境；CI 中不设置 PLAYWRIGHT_PROXY 即为直连
_proxy = os.environ.get("PLAYWRIGHT_PROXY")
PROXY = {"server": _proxy, "bypass": "127.0.0.1,localhost"} if _proxy else None


def _launch(module, **kw):
    return module.launch(proxy=PROXY, **kw) if PROXY else module.launch(**kw)


BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8088"

results = []


def rec(name, ok, detail=""):
    results.append((name, ok, detail))
    print(("PASS  " if ok else "FAIL  ") + name + (f" :: {detail}" if detail else ""))


def search(page, kw, wait=700):
    page.fill("#search-input", "")
    page.fill("#search-input", kw)
    page.wait_for_timeout(wait)
    return page.locator(".search-item").count()


def main():
    with sync_playwright() as p:
        b = _launch(p.chromium)
        ctx = b.new_context(viewport={"width": 1440, "height": 900}, locale="zh-CN")
        page = ctx.new_page()

        # ---------- 基础关键词类型 ----------
        page.goto(BASE + "/", wait_until="load")
        page.click("#searchTrigger")
        page.wait_for_timeout(1200)   # 让索引先加载完

        cases = [
            ("中文连续关键词", "应急响应", lambda n: n > 0),
            ("英文关键词", "suricata", lambda n: n > 0),
            ("英文大写（大小写不敏感）", "SURICATA", lambda n: n > 0),
            ("英文小写", "docker", lambda n: n > 0),
            ("数字关键词", "48000", lambda n: n > 0),
            ("emoji 关键词", "🚀", lambda n: n > 0),
            ("标点/符号", "&", lambda n: n >= 0),
            ("正则特殊字符", "REGEX.*+?^${}()|[]\\", lambda n: n >= 0),
            ("多关键词 AND", "docker 逃逸", lambda n: n > 0),
            ("多关键词 AND（不相关）", "docker zzzzzz", lambda n: n == 0),
            ("文章末尾关键词", "FOXTROT10000", lambda n: n > 0),
            ("正文 3000 字后关键词", "CHARLIE3500", lambda n: n > 0),
            ("正文 8000 字关键词", "ECHO8000", lambda n: n > 0),
            ("五万字深处关键词", "GOLF48000", lambda n: n > 0),
            ("空搜索", "", lambda n: n == 0),
            ("无结果搜索", "zzz-not-exist-keyword", lambda n: n == 0),
            ("高频词（结果可能超过 20）", "安全", lambda n: n > 0),
        ]
        for name, kw, check in cases:
            n = search(page, kw)
            rec(name, check(n), f'"{kw[:28]}" -> {n} 条')

        # 结果上限
        n = search(page, "安全")
        rec("结果数上限 <= 20", n <= 20, f"{n} 条")

        # 无结果提示
        search(page, "zzz-not-exist-keyword")
        rec("无结果有明确提示", page.locator(".search-empty").count() > 0)
        ctx.close()

        # ---------- 竞态 A：索引请求挂起时，不应误报"无结果" ----------
        ctx2 = b.new_context(viewport={"width": 1440, "height": 900}, locale="zh-CN")
        page2 = ctx2.new_page()
        def hang(route):
            pass            # 不 continue / 不 fulfill：请求保持挂起，模拟慢网络
        page2.route("**/index.json", hang)
        page2.goto(BASE + "/", wait_until="load")
        page2.click("#searchTrigger")
        page2.fill("#search-input", "FOXTROT10000")   # 打开后立即输入
        page2.wait_for_timeout(900)
        txt_a = page2.locator(".search-empty").inner_text() if page2.locator(".search-empty").count() else ""
        wrong_empty = "没有找到" in txt_a
        rec("竞态：索引未就绪时不误报“无结果”", not wrong_empty, f"提示=「{txt_a[:40]}」")
        rec("竞态：索引未就绪时显示加载态", "加载" in txt_a, f"提示=「{txt_a[:40]}」")
        ctx2.close()

        # ---------- 竞态 B：索引延迟后到达，应自动补渲染出结果 ----------
        ctx2b = b.new_context(viewport={"width": 1440, "height": 900}, locale="zh-CN")
        page2b = ctx2b.new_page()
        state = {"delay": True}
        def slow_once(route):
            if state["delay"]:
                state["delay"] = False
                # 延迟响应：先等一会儿再放行（不阻塞 Playwright 主线程的方式）
                import time
                time.sleep(2.0)
            route.continue_()
        page2b.route("**/index.json", slow_once)
        page2b.goto(BASE + "/", wait_until="domcontentloaded")
        page2b.click("#searchTrigger")
        page2b.fill("#search-input", "GOLF48000")
        page2b.wait_for_timeout(4000)
        n_race = page2b.locator(".search-item").count()
        rec("竞态：索引延迟到达后自动出结果", n_race > 0, f"{n_race} 条")
        ctx2b.close()

        # ---------- 索引加载失败 ----------
        ctx3 = b.new_context(viewport={"width": 1440, "height": 900}, locale="zh-CN")
        page3 = ctx3.new_page()
        page3.route("**/index.json", lambda route: route.fulfill(status=404, body="not found"))
        page3.goto(BASE + "/", wait_until="load")
        page3.click("#searchTrigger")
        page3.fill("#search-input", "应急响应")
        page3.wait_for_timeout(1500)
        txt = page3.locator(".search-empty").inner_text() if page3.locator(".search-empty").count() else ""
        rec("索引加载失败有明确提示", "失败" in txt, txt[:60])
        ctx3.close()
        b.close()

    bad = [r for r in results if not r[1]]
    print(f"\n==== {len(results) - len(bad)}/{len(results)} PASSED ====")
    for n, _, d in bad:
        print("  -", n, "::", d)


if __name__ == "__main__":
    main()
