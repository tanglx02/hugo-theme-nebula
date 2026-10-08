#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Nebula 主题交互回归测试：搜索 / 主题切换 / 菜单 / 复制 / TOC / 灯箱 / 分页 / 返回顶部 / 无 JS 降级。

退出码约定（见 tools/_testlib.py）：任一 record 为 False / 浏览器启动失败 /
异常 / 一个用例都没跑到 -> exit 1。
"""
import os
import sys
import traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _testlib import Harness, launch as _launch, reachable, guard  # noqa: E402

from playwright.sync_api import sync_playwright  # noqa: E402

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8088"

H = Harness("interactions")


def record(name, ok, detail=""):
    return H.record(name, ok, detail)


def run(browser_type, name, fn, viewport=None, mobile=False, js=True):
    with sync_playwright() as p:
        launcher = {"chromium": p.chromium, "firefox": p.firefox, "webkit": p.webkit}[browser_type]
        try:
            browser = _launch(launcher)
        except Exception as e:
            record(f"[{name}] launch", False, str(e)[:120])
            return
        ctx = browser.new_context(viewport=viewport or {"width": 1440, "height": 900},
                                  locale="zh-CN", is_mobile=mobile, has_touch=mobile,
                                  java_script_enabled=js)
        # 仅 Chromium 支持剪贴板权限预授予；WebKit/Firefox 不授予也不影响按钮交互
        if browser_type == "chromium":
            try:
                ctx.grant_permissions(["clipboard-read", "clipboard-write"])
            except Exception:
                pass
        page = ctx.new_page()
        try:
            fn(page)
        except Exception as e:
            record(f"[{name}] exception", False, str(e)[:200])
        ctx.close()
        browser.close()


def t_search(page):
    page.goto(BASE + "/", wait_until="load")
    page.click("#searchTrigger")
    page.wait_for_timeout(300)
    record("搜索弹窗打开", page.is_visible(".search-overlay.open"))
    page.fill("#search-input", "应急响应")
    page.wait_for_timeout(600)
    n = page.locator(".search-item").count()
    record("搜索返回结果", n > 0, f"{n} 条")
    record("搜索结果高亮", page.locator(".search-item mark").count() > 0)
    first_href = page.locator(".search-item").first.get_attribute("href")
    page.locator(".search-item").first.click()
    page.wait_for_load_state("load")
    record("点击搜索结果跳转", page.url.endswith((first_href or "").rstrip("/")) or (first_href or "") in page.url, page.url)

    # 键盘：Ctrl+K 打开，Esc 关闭
    page.goto(BASE + "/", wait_until="load")
    page.keyboard.press("Control+k")
    page.wait_for_timeout(300)
    record("Ctrl+K 打开搜索", page.is_visible(".search-overlay.open"))
    page.keyboard.press("Escape")
    page.wait_for_timeout(300)
    record("Esc 关闭搜索", not page.is_visible(".search-overlay.open"))

    # 无结果
    page.click("#searchTrigger")
    page.fill("#search-input", "zzz-不存在的关键词-zzz")
    page.wait_for_timeout(500)
    record("无结果提示", page.locator(".search-empty").count() > 0)
    page.keyboard.press("Escape")

    # 英文/标签搜索
    page.click("#searchTrigger")
    page.fill("#search-input", "docker")
    page.wait_for_timeout(500)
    record("英文关键词搜索", page.locator(".search-item").count() > 0)


def t_theme(page):
    page.goto(BASE + "/", wait_until="load")
    before = page.get_attribute("html", "data-theme")
    page.click("#themeToggle")
    page.wait_for_timeout(300)
    after = page.get_attribute("html", "data-theme")
    record("暗色/亮色切换", before != after, f"{before} -> {after}")
    stored = page.evaluate("() => localStorage.getItem('nebula-theme')")
    record("主题写入 localStorage", stored == after, stored)
    page.reload(wait_until="load")
    page.wait_for_timeout(200)
    record("刷新后主题保持", page.get_attribute("html", "data-theme") == after)
    # 图标切换
    sun_visible = page.evaluate("() => getComputedStyle(document.querySelector('.i-sun')).display !== 'none'")
    moon_visible = page.evaluate("() => getComputedStyle(document.querySelector('.i-moon')).display !== 'none'")
    record("主题图标互斥显示", sun_visible != moon_visible, f"sun={sun_visible} moon={moon_visible}")
    page.click("#themeToggle")
    page.wait_for_timeout(200)


EXPECT_LANG_COPIED = {"zh-CN": "已复制", "zh-TW": "已複製", "en": "Copied"}


def t_code_copy(page):
    page.goto(BASE + "/posts/04-suricata-elk/", wait_until="load")
    btn = page.locator(".code-copy").first
    # 期望文案不写死：从页面注入的 NEBULA_I18N 读取，交互测试与 i18n 测试保持一致
    expect = page.evaluate("() => (window.NEBULA_I18N || {}).copied || ''")
    record("代码复制：期望文案来自 NEBULA_I18N.copied", bool(expect), f'"{expect}"')
    lang = os.environ.get("PW_EXPECT_LANG", "").strip()
    if lang:
        want = EXPECT_LANG_COPIED.get(lang)
        record(f"代码复制：{lang} 文案符合预期", want == expect, f'期望 "{want}" 实际 "{expect}"')

    btn.click()
    timeline, hit = [], False
    for _ in range(8):
        page.wait_for_timeout(200)
        txt = btn.inner_text().strip()
        timeline.append(txt[:8])
        if expect and expect in txt:
            hit = True
            break
    record(f"代码复制按钮反馈（期望「{expect}」）", hit, " → ".join(timeline))
    # 提示结束后应恢复原文案（不是永久变成"已复制"）
    page.wait_for_timeout(2000)
    record("代码复制按钮文案已恢复", expect not in btn.inner_text().strip(),
           f'"{btn.inner_text().strip()}"')
    clip = page.evaluate("() => navigator.clipboard.readText().catch(() => '')")
    record("剪贴板内容非空", len((clip or "").strip()) > 0, (clip or "")[:40].replace("\n", " "))


def t_toc(page):
    page.goto(BASE + "/posts/03-incident-response/", wait_until="load")
    links = page.locator(".toc a")
    record("TOC 存在条目", links.count() > 1, f"{links.count()} 项")
    href = links.nth(1).get_attribute("href")
    links.nth(1).click()
    page.wait_for_timeout(700)
    # URL 中的锚点会被百分号编码，需解码后比较
    from urllib.parse import unquote
    cur_hash = "#" + (page.url.split("#")[1] if "#" in page.url else "")
    record("TOC 点击跳转锚点", unquote(cur_hash) == (href or "###"), f"{unquote(cur_hash)} vs {href}")
    active = page.locator(".toc a.active").count()
    record("TOC 高亮当前项", active >= 1, f"{active} 项 active")


def t_lightbox(page):
    page.goto(BASE + "/posts/zz-11-images/", wait_until="load")
    page.locator(".post-content img").first.click()
    page.wait_for_timeout(400)
    record("图片灯箱打开", page.is_visible("#lightbox.open"))
    page.click(".lightbox-close")
    page.wait_for_timeout(300)
    record("图片灯箱关闭（关闭按钮）", not page.is_visible("#lightbox.open"))
    # 补充：点击遮罩空白处也应关闭
    page.locator(".post-content img").first.click()
    page.wait_for_timeout(300)
    page.click("#lightbox", position={"x": 15, "y": 15})
    page.wait_for_timeout(300)
    record("图片灯箱关闭（点击遮罩）", not page.is_visible("#lightbox.open"))


def t_pagination(page):
    page.goto(BASE + "/posts/", wait_until="load")
    nxt = page.locator(".pagination a").last
    nxt.click()
    page.wait_for_load_state("load")
    record("分页跳转", "/page/2/" in page.url, page.url)
    record("第 2 页有内容", page.locator(".post-card").count() > 0,
           f'{page.locator(".post-card").count()} 张卡片')


def t_to_top(page):
    page.goto(BASE + "/posts/zz-02-10k/", wait_until="load")
    page.evaluate("() => window.scrollTo(0, 2000)")
    page.wait_for_timeout(500)
    record("返回顶部按钮出现", page.locator("#toTop.show").count() == 1)
    page.click("#toTop")
    page.wait_for_timeout(1200)
    record("返回顶部生效", page.evaluate("() => window.scrollY") < 50,
           page.evaluate("() => window.scrollY"))


def t_mobile_menu(page):
    page.goto(BASE + "/", wait_until="load")
    record("移动端默认隐藏导航", not page.is_visible("#mainNav"))
    page.click("#burger")
    page.wait_for_timeout(300)
    record("汉堡菜单展开", page.is_visible("#mainNav"))
    page.click("#mainNav a:nth-child(5)")   # 归档
    page.wait_for_load_state("load")
    record("移动端菜单跳转", "/archives" in page.url, page.url)


def t_no_js(page):
    page.goto(BASE + "/", wait_until="load")
    record("无 JS 首页可渲染", page.locator(".post-card").count() > 0,
           f'{page.locator(".post-card").count()} 张卡片')
    body = page.inner_text("body")
    record("无 JS 正文可读", "最新文章" in body)
    page.goto(BASE + "/posts/03-incident-response/", wait_until="load")
    record("无 JS 文章页可渲染", "排查" in page.inner_text(".post-content"))
    record("无 JS 代码块可见", page.locator(".code-block").count() > 0)


def t_keyboard(page):
    page.goto(BASE + "/", wait_until="load")
    for _ in range(6):
        page.keyboard.press("Tab")
    info = page.evaluate("""() => {
        const el = document.activeElement;
        const r = el.getBoundingClientRect();
        const st = getComputedStyle(el);
        return { tag: el.tagName, cls: (typeof el.className === 'string' ? el.className : '').slice(0,30),
                 outline: st.outlineWidth, w: Math.round(r.width) };
    }""")
    record("键盘 Tab 可聚焦元素", info["tag"] not in ("BODY",), info)
    record("焦点有可见轮廓", info["outline"] != "0px", info["outline"])


def _run_all():
    if not reachable(BASE + "/"):
        H.fatal_error("被测站点不可达", BASE)
        return

    only = [b.strip() for b in os.environ.get("PW_BROWSERS", "").split(",") if b.strip()]

    def want(name):
        return (not only) or (name in only)

    if want("chromium"):
        run("chromium", "chromium", t_search)
        run("chromium", "chromium", t_theme)
        run("chromium", "chromium", t_code_copy)
        run("chromium", "chromium", t_toc)
        run("chromium", "chromium", t_lightbox)
        run("chromium", "chromium", t_pagination)
        run("chromium", "chromium", t_to_top)
        run("chromium", "chromium", t_mobile_menu, viewport={"width": 375, "height": 812}, mobile=True)
        run("chromium", "chromium", t_no_js, js=False)
        run("chromium", "chromium", t_keyboard)

    if want("firefox"):
        run("firefox", "firefox", t_search)
        run("firefox", "firefox", t_theme)
        run("firefox", "firefox", t_code_copy)
        run("firefox", "firefox", t_pagination)

    if want("webkit"):
        run("webkit", "webkit", t_search)
        run("webkit", "webkit", t_theme)


def main():
    guard(H, _run_all)
    H.finish()


if __name__ == "__main__":
    main()
