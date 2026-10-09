#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""搜索边界测试（P5）：关键词类型 / 竞态 / 索引失败 / 延迟 / 大量结果 / 日期本地化。

搜索结果日期本地化（v1.0.9 P1）：搜索索引新增 UI 字段 dateDisplay，由 Hugo 在
构建期按站点语言生成；前端只负责原样输出。这里验证 DOM 里真的出现了本地化日期，
而不是机器字段 YYYY-MM-DD——环境变量 SEARCH_DATE_LOCALE 指定期望语言。

退出码约定（见 tools/_testlib.py）：断言失败 / 浏览器启动失败 / 脚本异常 -> exit 1。
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _testlib import Harness, launch as _launch, reachable, guard  # noqa: E402

from playwright.sync_api import sync_playwright  # noqa: E402

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8088"
# 引擎参数（TEST-DEFECT-R2-002）：本脚本验证搜索交互与竞态，属浏览器差异项，
# 因此支持在 chromium / firefox / webkit 上运行（默认 chromium 保持向后兼容）。
BROWSER = sys.argv[2] if len(sys.argv) > 2 else (
    os.environ.get("PW_BROWSERS") or "chromium")

DATE_LOCALE = os.environ.get("SEARCH_DATE_LOCALE", "zh-CN")
EXPECTED_DATE = {
    "zh-CN": re.compile(r"^\d{4}年\d{1,2}月\d{1,2}日"),
    "zh-TW": re.compile(r"^\d{4}年\d{1,2}月\d{1,2}日"),
    "en": re.compile(r"^[A-Z][a-z]{2} \d{1,2}, \d{4}"),
}
# 状态提示文案也随语言变（见 i18n/*.yaml 的 search.loading / search.failed）——
# 之前这里写死中文，导致脚本拿到英文站点就误报。
EXPECTED_STATUS = {
    "zh-CN": {"loading": "加载", "failed": "失败"},
    "zh-TW": {"loading": "載入", "failed": "失敗"},
    "en": {"loading": "Loading", "failed": "Failed"},
}

H = Harness("search-edge")


def rec(name, ok, detail=""):
    return H.record(name, ok, detail)


def search(page, kw, wait=700):
    page.fill("#search-input", "")
    page.fill("#search-input", kw)
    page.wait_for_timeout(wait)
    return page.locator(".search-item").count()


def _run_all():
    with sync_playwright() as p:
        launcher = {"chromium": p.chromium, "firefox": p.firefox,
                    "webkit": p.webkit}.get(BROWSER, p.chromium)
        try:
            b = _launch(launcher)
        except Exception as e:
            H.fatal_error(f"{BROWSER} 浏览器启动失败", str(e)[:200])
            return
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

        # 标点 / 正则元字符 / 尖括号 / 引号：
        # TEST-DEFECT-010：旧断言 `lambda n: n >= 0` 恒真，等于什么都没查。
        # 正确语义是"必须落到一个确定状态"：要么有结果，要么显示明确的空态提示，
        # 且全过程不产生 JS 异常（正则未转义会让 RegExp 抛错）。
        js_errs = []
        page.on("pageerror", lambda e: js_errs.append(str(e)[:120]))
        for kw in ("&", "REGEX.*+?^${}()|[]\\", "<hello>", '"quoted"', "'single'"):
            cnt = search(page, kw)
            empty = page.locator(".search-empty").count()
            rec(f'特殊查询「{kw[:16]}」有确定结果状态（有结果或明确空态）',
                (cnt > 0) or (empty > 0), f"{cnt} 条结果 / 空态提示={empty}")
        rec("特殊查询未产生 JS 异常（正则元字符已正确转义）",
            not js_errs, f"{js_errs[:2]}")

        # 搜索结果日期本地化（构建期 i18n，前端不参与格式化）
        pattern = EXPECTED_DATE.get(DATE_LOCALE)
        if pattern is None:
            rec(f"未知的 SEARCH_DATE_LOCALE: {DATE_LOCALE}", False, "配置错误")
        else:
            meta = (page.locator(".search-item .p").first.inner_text()
                    if page.locator(".search-item .p").count() else "")
            rec(f"[{DATE_LOCALE}] 搜索结果日期已本地化",
                 bool(pattern.match(meta)), f"首条元信息「{meta[:40]}」")
            rec(f"[{DATE_LOCALE}] 搜索结果不显示机器字段 YYYY-MM-DD",
                 not re.match(r"^\d{4}-\d{2}-\d{2}", meta), f"首条元信息「{meta[:40]}」")

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
        wrong_empty = EXPECTED_STATUS[DATE_LOCALE]["failed"] in txt_a
        rec("竞态：索引未就绪时不误报“无结果”", not wrong_empty, f"提示=「{txt_a[:40]}」")
        rec("竞态：索引未就绪时显示加载态",
             EXPECTED_STATUS[DATE_LOCALE]["loading"] in txt_a, f"提示=「{txt_a[:40]}」")
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
        rec("索引加载失败有明确提示",
             EXPECTED_STATUS[DATE_LOCALE]["failed"] in txt, txt[:60])
        ctx3.close()
        b.close()


def main():
    if not reachable(BASE + "/"):
        H.fatal_error("被测站点不可达", BASE)
        H.finish()
    guard(H, _run_all)
    H.finish()


if __name__ == "__main__":
    main()
