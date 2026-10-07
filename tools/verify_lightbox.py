#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""灯箱专项测试（P0-1）：dialog 语义 / Focus Trap / 键盘 / 焦点恢复 / 链接图片。

覆盖场景：鼠标打开、Enter 打开、Space 打开、Tab、Shift+Tab、Escape、
          点击遮罩、点击关闭按钮、焦点恢复、链接图片跳转、背景 inert。

用法：python tools/verify_lightbox.py [base_url] [browser]

退出码约定（见 tools/_testlib.py）：任一断言失败 / 浏览器启动失败 /
0 个用例 -> exit 1。
"""
import json
import os
import sys
import traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _testlib import Harness, launch as _launch, reachable  # noqa: E402

from playwright.sync_api import sync_playwright  # noqa: E402

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8088"
BROWSER = sys.argv[2] if len(sys.argv) > 2 else "chromium"
IMG_PAGE = "/posts/zz-11-images/"

H = Harness(f"lightbox-{BROWSER}")


def rec(name, ok, detail=""):
    return H.record(name, ok, detail)


def _run_all():
    if not reachable(BASE + "/"):
        H.fatal_error("被测站点不可达", BASE)
        return
    with sync_playwright() as p:
        launcher = {"chromium": p.chromium, "firefox": p.firefox, "webkit": p.webkit}[BROWSER]
        try:
            b = _launch(launcher)
        except Exception as e:
            H.fatal_error(f"{BROWSER} 浏览器启动失败", str(e)[:200])
            return
        ctx = b.new_context(viewport={"width": 1440, "height": 900}, locale="zh-CN")
        page = ctx.new_page()
        page.goto(BASE + IMG_PAGE, wait_until="load")
        page.wait_for_timeout(600)

        # ---------- 语义 ----------
        attrs = page.evaluate("""() => {
            const el = document.getElementById('lightbox');
            return el ? { role: el.getAttribute('role'), modal: el.getAttribute('aria-modal'),
                          label: el.getAttribute('aria-label'), tabindex: el.getAttribute('tabindex'),
                          hidden: el.getAttribute('aria-hidden') } : null;
        }""")
        rec("dialog 语义完整", bool(attrs and attrs["role"] == "dialog" and attrs["modal"] == "true"), attrs)
        rec("dialog 有可访问名称", bool(attrs and attrs["label"]), attrs and attrs["label"])

        img_aria = page.evaluate("""() => {
            const img = document.querySelector('.post-content img');
            return { tabindex: img.getAttribute('tabindex'), role: img.getAttribute('role'),
                     label: img.getAttribute('aria-label'), zoomable: img.classList.contains('zoomable') };
        }""")
        rec("图片可聚焦且有语义", img_aria["tabindex"] == "0" and img_aria["role"] == "button" and bool(img_aria["label"]), img_aria)

        # ---------- 场景 1：鼠标打开 ----------
        page.locator(".post-content img").first.click()
        page.wait_for_timeout(350)
        rec("① 鼠标点击打开", page.is_visible("#lightbox.open"))
        rec("   打开后焦点在 dialog 内", page.evaluate("""() => {
            const lb = document.getElementById('lightbox');
            return lb.contains(document.activeElement);
        }"""))
        rec("   背景已 inert（不可键盘交互）", page.evaluate("""() => {
            const m = document.querySelector('main'), h = document.querySelector('.site-header');
            return !!(m && m.hasAttribute('inert')) && !!(h && h.hasAttribute('inert'));
        }"""))

        # ---------- 场景 2：Tab 循环 ----------
        inside = []
        for _ in range(5):
            page.keyboard.press("Tab")
            page.wait_for_timeout(120)
            inside.append(page.evaluate("""() => {
                const lb = document.getElementById('lightbox');
                return lb.contains(document.activeElement);
            }"""))
        rec("② Tab 焦点不逃出 dialog（5 次）", all(inside), f"记录={inside}")

        # ---------- 场景 3：Shift+Tab 循环 ----------
        back_inside = []
        for _ in range(3):
            page.keyboard.press("Shift+Tab")
            page.wait_for_timeout(120)
            back_inside.append(page.evaluate("""() => {
                const lb = document.getElementById('lightbox');
                return lb.contains(document.activeElement);
            }"""))
        rec("③ Shift+Tab 焦点不逃出 dialog（3 次）", all(back_inside), f"记录={back_inside}")

        # ---------- 场景 4：Escape 关闭 + 焦点恢复 ----------
        page.keyboard.press("Escape")
        page.wait_for_timeout(300)
        rec("④ Escape 关闭", not page.is_visible("#lightbox.open"))
        rec("   关闭后焦点归还触发图片", page.evaluate("() => document.activeElement.tagName === 'IMG'"),
            page.evaluate("() => document.activeElement.tagName"))
        rec("   关闭后背景解除 inert", page.evaluate("""() => {
            const m = document.querySelector('main');
            return !(m && m.hasAttribute('inert'));
        }"""))

        # ---------- 场景 5：Enter 打开 ----------
        page.evaluate("() => document.querySelector('.post-content img').focus()")
        page.keyboard.press("Enter")
        page.wait_for_timeout(350)
        rec("⑤ Enter 键打开", page.is_visible("#lightbox.open"))
        page.keyboard.press("Escape")
        page.wait_for_timeout(250)

        # ---------- 场景 6：Space 打开 ----------
        page.evaluate("() => document.querySelector('.post-content img').focus()")
        page.keyboard.press(" ")
        page.wait_for_timeout(350)
        rec("⑥ Space 键打开", page.is_visible("#lightbox.open"))
        page.keyboard.press("Escape")
        page.wait_for_timeout(250)

        # ---------- 场景 7：点击遮罩关闭 ----------
        page.locator(".post-content img").first.click()
        page.wait_for_timeout(300)
        page.click("#lightbox", position={"x": 15, "y": 15})
        page.wait_for_timeout(300)
        rec("⑦ 点击遮罩关闭", not page.is_visible("#lightbox.open"))

        # ---------- 场景 8：点击关闭按钮 ----------
        page.locator(".post-content img").first.click()
        page.wait_for_timeout(300)
        page.click(".lightbox-close")
        page.wait_for_timeout(300)
        rec("⑧ 点击关闭按钮关闭", not page.is_visible("#lightbox.open"))

        # 关闭按钮可键盘访问（Tab 到它并 Enter 触发）
        page.locator(".post-content img").first.click()
        page.wait_for_timeout(300)
        focused_close = page.evaluate("() => document.activeElement.classList.contains('lightbox-close')")
        rec("   关闭按钮可获得焦点", focused_close,
            page.evaluate("() => document.activeElement.className"))
        if focused_close:
            page.keyboard.press("Enter")
            page.wait_for_timeout(300)
            rec("   关闭按钮键盘可触发", not page.is_visible("#lightbox.open"))
        else:
            page.keyboard.press("Escape")

        # ---------- 场景 9：链接图片 ----------
        link_info = page.evaluate("""() => {
            const imgs = Array.from(document.querySelectorAll('.post-content img'));
            const all = imgs.map(i => i.closest('a')).filter(Boolean);
            const internal = all.find(a => (a.getAttribute('href') || '').startsWith('/'));
            const a = internal || all[0];
            const wrapped = imgs.find(i => i.closest('a'));
            return a ? { href: a.getAttribute('href'),
                         wrappedZoomable: wrapped.classList.contains('zoomable'),
                         wrappedTabindex: wrapped.getAttribute('tabindex') } : null;
        }""")
        rec("存在链接包裹图片（测试数据）", link_info is not None, link_info)
        if link_info:
            rec("链接图片未被灯箱接管", not link_info["wrappedZoomable"] and link_info["wrappedTabindex"] is None, link_info)
            page.locator(f'.post-content a[href="{link_info["href"]}"] img').first.click()
            page.wait_for_timeout(1100)
            rec("⑨ 点击链接图片不开灯箱", not page.is_visible("#lightbox.open"))
            rec("   点击链接图片走原生跳转", link_info["href"] in page.url, page.url)

        ctx.close()
        b.close()


def main():
    try:
        _run_all()
    except Exception:
        tb = traceback.format_exc().strip().splitlines()
        H.fatal_error("脚本异常", tb[-1][:200] if tb else "unknown")
    H.finish()


if __name__ == "__main__":
    main()
