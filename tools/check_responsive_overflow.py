#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""响应式横向溢出 & 头部导航断点门禁（BUG-P2-002）。

背景：英文站（导航文案更长）在 769–869px 视口下整页横向溢出
（scrollWidth 恒为 870；nav 433px + header-actions 217px 并排超宽），
而内容断点 768px 只在 ≤768 才隐藏行内导航。

本脚本在同一组**边界宽度**上验证：
    - 不再出现整页横向滚动（scrollWidth <= clientWidth + 1）
    - 头部断点契约：<=900px 隐藏行内导航并显示汉堡；>=901px 相反
可传多个站点（中 / 英 / 繁），逐一验证。

用法：
    python3 tools/check_responsive_overflow.py <base_url> [browser]
环境变量：
    OVERFLOW_EXTRA_URLS="http://127.0.0.1:8081,http://127.0.0.1:8082"  额外站点（如 en / zh-TW）

退出码约定（见 tools/_testlib.py）：任一断言失败 -> exit 1。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _testlib import Harness, guard, launch, reachable  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8080"
BROWSER = sys.argv[2] if len(sys.argv) > 2 else "chromium"

# 边界宽度：768/900 是断点，769/901 是断点另一侧，869 是原缺陷区间上沿
WIDTHS = [320, 375, 769, 800, 830, 869, 900, 901, 1024, 1280]
PAGES = ["/", "/posts/", "/posts/07-hugo-blog/", "/archives/"]
HEADER_BREAKPOINT = 900

PROBE = """() => {
  const nav = document.querySelector('.nav');
  const burger = document.querySelector('#burger');
  return {
    scrollWidth: document.documentElement.scrollWidth,
    clientWidth: document.documentElement.clientWidth,
    navDisplay: nav ? getComputedStyle(nav).display : 'absent',
    burgerDisplay: burger ? getComputedStyle(burger).display : 'absent',
    mqMobile: window.matchMedia('(max-width: 900px)').matches,
    innerWidth: window.innerWidth
  };
}"""


def run(h):
    bases = [BASE] + [u.strip() for u in
                      os.environ.get("OVERFLOW_EXTRA_URLS", "").split(",") if u.strip()]
    with sync_playwright() as p:
        launcher = {"chromium": p.chromium, "firefox": p.firefox, "webkit": p.webkit}[BROWSER]
        try:
            browser = launch(launcher)
        except Exception as e:
            h.fatal_error(f"{BROWSER} 启动失败", str(e)[:160])
            return

        for base in bases:
            if not reachable(base + "/"):
                h.fatal_error("站点不可达", base)
                continue
            ctx = browser.new_context(locale="zh-CN")
            pg = ctx.new_page()
            label = base.rstrip("/").split("//")[-1]

            overflows, bp_bad, checked = [], [], 0
            mobile_seen = desktop_seen = 0
            for width in WIDTHS:
                pg.set_viewport_size({"width": width, "height": 900})
                for path in PAGES:
                    try:
                        pg.goto(base + path, wait_until="load")
                    except Exception:
                        continue
                    pg.wait_for_timeout(90)
                    d = pg.evaluate(PROBE)
                    checked += 1
                    if d["scrollWidth"] > d["clientWidth"] + 1:
                        overflows.append(f'{path}@{width}px '
                                         f'scrollWidth={d["scrollWidth"]} > {d["clientWidth"]}')
                    if path != "/" or d["navDisplay"] == "absent":
                        continue
                    # 断点契约不按"像素宽度"硬判，而是与 matchMedia 的真实结果保持一致：
                    # 各引擎对滚动条是否计入视口宽度处理不同（WebKit 会在 901px 就命中
                    # max-width:900），按像素断言会产生引擎相关的假失败。
                    if d["mqMobile"]:
                        mobile_seen += 1
                        expect_nav, expect_burger = "none", "grid"
                    else:
                        desktop_seen += 1
                        expect_nav, expect_burger = "flex", "none"
                    if d["navDisplay"] != expect_nav:
                        bp_bad.append(f'{width}px(inner={d["innerWidth"]}) '
                                      f'nav.display={d["navDisplay"]} 期望 {expect_nav}'
                                      f'（matchMedia max-width:900 = {d["mqMobile"]}）')
                    if d["burgerDisplay"] != expect_burger:
                        bp_bad.append(f'{width}px burger.display={d["burgerDisplay"]} '
                                      f'期望 {expect_burger}')

            if checked == 0:
                h.fatal_error(f"[{label}] 没有执行到任何测量", "页面全部不可达")
                ctx.close()
                continue

            h.record(f"[{label}] 各边界宽度均无整页横向溢出（{checked} 次测量）",
                     not overflows, "；".join(overflows[:4]) if overflows else
                     "全部 scrollWidth <= clientWidth")
            # 断点两侧都必须真的被测到，否则"一致性"可能因只测到一侧而空转
            if mobile_seen == 0 or desktop_seen == 0:
                h.record(f"[{label}] 头部断点契约（与 matchMedia('max-width:900px') 一致）",
                         False, f"只测到单侧：mobile={mobile_seen} desktop={desktop_seen}")
            else:
                h.record(f"[{label}] 头部断点契约（与 matchMedia('max-width:900px') 一致）",
                         not bp_bad, "；".join(bp_bad[:4]) if bp_bad else
                         f"移动侧 {mobile_seen} 次 / 桌面侧 {desktop_seen} 次 均一致")
            ctx.close()

        browser.close()


if __name__ == "__main__":
    main_h = Harness("responsive-overflow")
    guard(main_h, run, main_h)
    main_h.finish()
