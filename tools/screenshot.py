#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""用 Playwright 对本地 Hugo 站点截图，用于主题 README 配图。"""
import os
from playwright.sync_api import sync_playwright

BASE = "http://localhost:1313"
OUT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                    "..", "docs", "screenshots"))
os.makedirs(OUT, exist_ok=True)


def main():
    with sync_playwright() as p:
        b = p.chromium.launch()

        # ---------- 桌面端 ----------
        ctx = b.new_context(viewport={"width": 1440, "height": 950},
                            device_scale_factor=1.5, locale="zh-CN")
        page = ctx.new_page()

        page.goto(BASE, wait_until="networkidle")
        page.screenshot(path=f"{OUT}/01-home-light.png", full_page=True)

        # 搜索弹窗
        page.click("#searchTrigger")
        page.wait_for_timeout(400)
        page.fill("#search-input", "应急响应")
        page.wait_for_timeout(700)
        page.screenshot(path=f"{OUT}/05-search.png")

        page.keyboard.press("Escape")
        page.wait_for_timeout(300)

        # 文章页
        page.goto(f"{BASE}/posts/03-incident-response/", wait_until="networkidle")
        page.wait_for_timeout(300)
        page.screenshot(path=f"{OUT}/02-post-light.png", full_page=True)

        # 暗色模式
        page.click("#themeToggle")
        page.wait_for_timeout(600)
        page.screenshot(path=f"{OUT}/03-post-dark.png", full_page=True)

        page.goto(BASE, wait_until="networkidle")
        page.wait_for_timeout(400)
        page.screenshot(path=f"{OUT}/04-home-dark.png", full_page=True)

        # 归档页
        page.goto(f"{BASE}/archives/", wait_until="networkidle")
        page.wait_for_timeout(300)
        page.screenshot(path=f"{OUT}/06-archive.png")

        ctx.close()

        # ---------- 移动端 ----------
        m = b.new_context(viewport={"width": 390, "height": 844},
                          device_scale_factor=2, locale="zh-CN",
                          is_mobile=True, has_touch=True)
        mp = m.new_page()
        mp.goto(BASE, wait_until="networkidle")
        mp.wait_for_timeout(300)
        mp.screenshot(path=f"{OUT}/07-mobile.png")
        m.close()

        b.close()
        print("screenshots ->", OUT)
        for f in sorted(os.listdir(OUT)):
            print(" ", f, os.path.getsize(os.path.join(OUT, f)) // 1024, "KB")


if __name__ == "__main__":
    main()
