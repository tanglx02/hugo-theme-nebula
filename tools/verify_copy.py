#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""复制语义专项测试：确保"复制"永远不会把失败/超时伪装成成功。

覆盖（代码块复制按钮 + 分享"复制链接"按钮 + 微信复制按钮共用同一实现）：

  A. Clipboard resolve            -> 显示成功
  B. Clipboard reject             -> 显示失败
  C. Clipboard 长时间 pending     -> **超时判失败**（绝不显示成功）★ 回归重点
  D. 无 Clipboard API + fallback 成功 -> 显示成功
  E. 无 Clipboard API + fallback 失败（execCommand 返回 false）-> 显示失败
  F. 成功/失败提示结束后恢复原按钮文案
  G. 代码块复制按钮同样遵守上述语义

期望文案不写死：从页面注入的 `window.NEBULA_I18N` 读取（copied / copyFailed），
因此本测试与语言无关，可配合 zh-CN / zh-TW / en 任意语言构建运行。

用法：python tools/verify_copy.py [base_url] [browser]
退出码约定（见 tools/_testlib.py）：任一断言失败 / 浏览器启动失败 / 0 用例 -> exit 1。
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _testlib import Harness, launch, reachable, guard  # noqa: E402

from playwright.sync_api import sync_playwright  # noqa: E402

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8088"
BROWSER = sys.argv[2] if len(sys.argv) > 2 else "chromium"
POST = "/posts/04-suricata-elk/"     # 有代码块与（开启分享时的）分享卡片

H = Harness(f"copy-{BROWSER}")

# 在页面脚本执行前替换 clipboard / execCommand，以便精确控制三种 Promise 结果
CLIP_STUB = """
(function () {
  window.__copyMode = 'resolve';     // resolve | reject | pending | absent
  window.__execOk = false;           // document.execCommand('copy') 的返回值
  window.__writeCalls = 0;

  function stubWrite() {
    window.__writeCalls++;
    var mode = window.__copyMode;
    if (mode === 'resolve') return Promise.resolve();
    if (mode === 'reject') return Promise.reject(new Error('denied'));
    if (mode === 'pending') return new Promise(function () {});   // 永不 settle
    return Promise.reject(new Error('unexpected-mode'));
  }

  try {
    Object.defineProperty(navigator, 'clipboard', {
      configurable: true,
      get: function () {
        return window.__copyMode === 'absent' ? undefined : { writeText: stubWrite };
      }
    });
  } catch (e) { window.__clipStubError = String(e); }

  var origExec = document.execCommand ? document.execCommand.bind(document) : null;
  document.execCommand = function (cmd) {
    if (cmd === 'copy') return window.__execOk === true;
    return origExec ? origExec(cmd) : false;
  };
})();
"""


def labels(page):
    return page.evaluate("""() => {
        const t = window.NEBULA_I18N || {};
        return { copied: t.copied || '', copyFailed: t.copyFailed || '' };
    }""")


def read_text(page, sel):
    return page.evaluate("""(sel) => {
        const el = document.querySelector(sel);
        return el ? (el.textContent || '').trim() : null;
    }""", sel)


def set_mode(page, mode, exec_ok):
    page.evaluate("""(o) => { window.__copyMode = o.mode; window.__execOk = o.exec; }""",
                  {"mode": mode, "exec": exec_ok})


def click_and_read(page, sel, wait_ms):
    """点击后等待 wait_ms，返回 (文案, 是否命中成功文案, 是否命中失败文案)。"""
    page.evaluate("(sel) => document.querySelector(sel).click()", sel)
    page.wait_for_timeout(wait_ms)
    txt = read_text(page, sel) or ""
    return txt


def _run_all():
    with sync_playwright() as p:
        launcher = {"chromium": p.chromium, "firefox": p.firefox, "webkit": p.webkit}[BROWSER]
        try:
            browser = launch(launcher)
        except Exception as e:
            H.fatal_error(f"{BROWSER} 浏览器启动失败", str(e)[:200])
            return
        ctx = browser.new_context(viewport={"width": 1280, "height": 900}, locale="zh-CN")
        ctx.add_init_script(CLIP_STUB)
        page = ctx.new_page()
        page.goto(BASE + POST, wait_until="load")

        err = page.evaluate("() => window.__clipStubError || ''")
        if err:
            H.record("clipboard 桩注入成功", False, err[:120])
        else:
            H.record("clipboard 桩注入成功", True)

        L = labels(page)
        H.record("页面注入 copied/copyFailed 文案", bool(L["copied"]) and bool(L["copyFailed"]),
                 f'copied="{L["copied"]}" copyFailed="{L["copyFailed"]}"')

        share = '.share-card [data-share="copy"]'
        has_share = page.locator(share).count() > 0
        H.record("存在分享复制按钮（params.share.enable）", has_share,
                 f"{page.locator('[data-share=\"copy\"]').count()} 个")
        if not has_share:
            H.record("分享复制语义测试可执行", False, "页面无 [data-share=copy] 按钮")
            browser.close()
            return

        orig_share_text = read_text(page, share)

        # ---------------------------------------------------------- A
        set_mode(page, "resolve", False)
        txt = click_and_read(page, share, 400)
        H.record("A. Clipboard resolve → 成功", L["copied"] in txt, f'"{txt}"')

        # ---------------------------------------------------------- F（承接 A 的成功提示）
        page.wait_for_timeout(1800)
        txt = read_text(page, share)
        H.record("F. 成功提示结束后恢复原文案", txt == orig_share_text,
                 f'"{txt}" (原: "{orig_share_text}")')

        # ---------------------------------------------------------- B
        set_mode(page, "reject", False)
        txt = click_and_read(page, share, 500)
        H.record("B. Clipboard reject → 失败", L["copyFailed"] in txt and L["copied"] not in txt,
                 f'"{txt}"')
        page.wait_for_timeout(2400)
        H.record("F2. 失败提示结束后恢复原文案", read_text(page, share) == orig_share_text,
                 f'"{read_text(page, share)}"')

        # ---------------------------------------------------------- C ★ 回归重点
        set_mode(page, "pending", False)
        txt = click_and_read(page, share, 1600)      # 超过 1200ms 超时阈值
        H.record("C. Clipboard 长时间 pending → 判失败（绝不假成功）★",
                 L["copyFailed"] in txt and L["copied"] not in txt, f'"{txt}"')
        page.wait_for_timeout(2400)

        # ---------------------------------------------------------- D
        set_mode(page, "absent", True)
        txt = click_and_read(page, share, 500)
        H.record("D. 无 Clipboard API + fallback 成功 → 成功", L["copied"] in txt, f'"{txt}"')
        page.wait_for_timeout(1800)

        # ---------------------------------------------------------- E
        set_mode(page, "absent", False)
        txt = click_and_read(page, share, 500)
        H.record("E. fallback 明确失败（execCommand=false）→ 失败",
                 L["copyFailed"] in txt and L["copied"] not in txt, f'"{txt}"')
        page.wait_for_timeout(2400)

        # ---------------------------------------------------------- 微信按钮同语义
        wc = page.locator('[data-share="copy"]').nth(1)
        if wc.count() > 0:
            set_mode(page, "pending", False)
            wc.click()
            page.wait_for_timeout(1600)
            wtxt = (wc.text_content() or "").strip()
            H.record("C2. 微信复制在 pending 下同样判失败",
                     L["copyFailed"] in wtxt and L["copied"] not in wtxt, f'"{wtxt}"')
        else:
            H.record("微信复制按钮存在", False, "未渲染（providers 未含 wechat）")

        # ---------------------------------------------------------- G 代码块复制按钮
        set_mode(page, "pending", False)
        code_ok = True
        if page.locator(".code-copy").count() == 0:
            code_ok = False
            H.record("G. 代码块复制按钮存在", False, "页面无 .code-copy")
        else:
            btn = page.locator(".code-copy").first
            orig = (btn.inner_text() or "").strip()
            btn.click()
            page.wait_for_timeout(1600)
            cur = (btn.inner_text() or "").strip()
            H.record("G. 代码块复制 pending → 判失败（绝不假成功）★",
                     L["copyFailed"] in cur and L["copied"] not in cur, f'"{cur}" (原: "{orig}")')
            page.wait_for_timeout(2400)
            H.record("G2. 代码块按钮文案恢复", (btn.inner_text() or "").strip() == orig,
                     f'"{btn.inner_text()}"')

        ctx.close()
        browser.close()


def main():
    if not reachable(BASE + "/"):
        H.fatal_error("被测站点不可达", BASE)
        H.finish()
    guard(H, _run_all)
    H.finish()


if __name__ == "__main__":
    main()
