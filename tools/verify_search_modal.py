#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""搜索弹窗 Modal 无障碍专项测试（实测 19 项断言）。

契约（由 assets/js/main.js 的 createModalA11y 提供，搜索与灯箱共用）：
    role=dialog / aria-modal / 可访问名称 / 焦点移入 / Tab 循环 /
    背景 inert / Escape / 遮罩关闭 / 焦点恢复 / 幂等开关 / 深链不报错

测试项：
     1 鼠标打开          2 Ctrl+K 打开       3 快捷键 / 打开
     4 输入框自动 focus  5 Tab × N          6 Shift+Tab × N
     7 焦点不逃出 dialog 8 背景 inert       9 Escape 关闭
    10 遮罩点击关闭     11 关闭后焦点恢复   12 快速重复开关
    13 ?q= 深链接      14 en/zh-CN/zh-TW 可访问名称正确

用法：
    python3 tools/verify_search_modal.py <base_url> [chromium|firefox|webkit]

退出码约定（见 tools/_testlib.py）：任一断言失败 -> exit 1。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _testlib import Harness, guard, launch, reachable  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8080"
BROWSER = sys.argv[2] if len(sys.argv) > 2 else "chromium"
PAGE = "/"
PROBE = "/posts/04-suricata-elk/"


def active_info(pg):
    return pg.evaluate("""() => {
        const a = document.activeElement;
        const ov = document.querySelector('#searchOverlay');
        return {
            tag: a ? a.tagName.toLowerCase() : null,
            id: a ? a.id : null,
            cls: a ? (typeof a.className === 'string' ? a.className : '') : '',
            inOverlay: !!(ov && a && ov.contains(a)),
            isBody: a === document.body
        };
    }""")


def open_state(pg):
    return pg.evaluate("""() => {
        const ov = document.querySelector('#searchOverlay');
        const main = document.querySelector('main');
        const header = document.querySelector('.site-header');
        return {
            open: !!(ov && ov.classList.contains('open')),
            ariaModal: ov ? ov.getAttribute('aria-modal') : null,
            role: ov ? ov.getAttribute('role') : null,
            label: ov ? (ov.getAttribute('aria-label') || '') : '',
            mainInert: !!(main && main.hasAttribute('inert')),
            mainAriaHidden: !!(main && main.getAttribute('aria-hidden') === 'true'),
            headerInert: !!(header && header.hasAttribute('inert'))
        };
    }""")


def bg_inert_count(pg):
    return pg.evaluate("""() => {
        return ['.progress-bar', '.site-header', 'main', '.site-footer', '.to-top']
            .reduce((acc, sel) => acc +
                Array.from(document.querySelectorAll(sel))
                    .filter(n => n.hasAttribute('inert')).length, 0);
    }""")


def run(h):
    if not reachable(BASE + "/"):
        h.fatal_error("站点不可达", BASE)
        return

    with sync_playwright() as p:
        launcher = {"chromium": p.chromium, "firefox": p.firefox, "webkit": p.webkit}[BROWSER]
        try:
            browser = launch(launcher)
        except Exception as e:
            h.fatal_error(f"{BROWSER} 启动失败", str(e)[:160])
            return

        ctx = browser.new_context(viewport={"width": 1280, "height": 900}, locale="zh-CN")
        pg = ctx.new_page()
        pg.goto(BASE + PAGE, wait_until="load")

        # ---------- 1 鼠标打开 ----------
        pg.click("#searchTrigger")
        pg.wait_for_timeout(220)
        st = open_state(pg)
        h.record("1. 鼠标点击触发器可打开搜索弹窗", st["open"], f"open={st['open']}")

        # ---------- 4 + 8 输入框 focus 与背景 inert ----------
        act = active_info(pg)
        h.record("4. 打开后焦点自动进入搜索输入框",
                 act["id"] == "search-input" and act["inOverlay"], f"active=#{act['id']}")
        inert_n = bg_inert_count(pg)
        h.record("8. 打开时背景内容被标记 inert / aria-hidden",
                 st["mainInert"] and st["mainAriaHidden"] and inert_n >= 2,
                 f"inert 节点 {inert_n} 个，main inert={st['mainInert']}")

        # ---------- 5 Tab × N：焦点循环 ----------
        seq_ok = True
        seen = []
        for _ in range(8):
            pg.keyboard.press("Tab")
            pg.wait_for_timeout(60)
            a = active_info(pg)
            seen.append(a["id"] or a["tag"])
            if not a["inOverlay"]:
                seq_ok = False
                break
        h.record("5. Tab 连续 8 次焦点始终在 dialog 内", seq_ok, " → ".join(seen[:5]))
        h.record("7. 焦点无法逃出 dialog（背景元素未被聚焦）", seq_ok,
                 "所有 Tab 落点均在 overlay 内")

        # ---------- 6 Shift+Tab × N ----------
        seq_ok = True
        seen = []
        for _ in range(6):
            pg.keyboard.press("Shift+Tab")
            pg.wait_for_timeout(60)
            a = active_info(pg)
            seen.append(a["id"] or a["tag"])
            if not a["inOverlay"]:
                seq_ok = False
                break
        h.record("6. Shift+Tab 连续 6 次焦点仍在 dialog 内", seq_ok, " → ".join(seen[:5]))

        # ---------- 9 Escape ----------
        pg.keyboard.press("Escape")
        pg.wait_for_timeout(220)
        st = open_state(pg)
        h.record("9. Escape 可关闭搜索弹窗", not st["open"], f"open={st['open']}")

        # ---------- 11 关闭后焦点恢复 ----------
        act = active_info(pg)
        h.record("11. 关闭后焦点恢复到触发元素（#searchTrigger）",
                 act["id"] == "searchTrigger", f"active=#{act['id']}")
        n_inert = bg_inert_count(pg)
        h.record("11b. 关闭后背景 inert 全部解除", n_inert == 0, f"剩余 inert {n_inert} 个")

        # ---------- 2 Ctrl+K ----------
        pg.keyboard.press("Control+k")
        pg.wait_for_timeout(220)
        h.record("2. Ctrl+K 可打开搜索弹窗", open_state(pg)["open"], "")
        pg.keyboard.press("Escape")
        pg.wait_for_timeout(200)

        # ---------- 3 快捷键 / ----------
        pg.evaluate("() => document.body.focus()")
        pg.keyboard.press("/")
        pg.wait_for_timeout(220)
        h.record("3. 快捷键 / 可打开搜索弹窗", open_state(pg)["open"], "")
        pg.keyboard.press("Escape")
        pg.wait_for_timeout(200)

        # ---------- 10 遮罩点击关闭 ----------
        pg.click("#searchTrigger")
        pg.wait_for_timeout(220)
        # 点击遮罩本体（而非内部 modal）
        box = pg.evaluate("""() => {
            const ov = document.querySelector('#searchOverlay');
            const r = ov.getBoundingClientRect();
            return {x: r.left + 4, y: r.top + 4};
        }""")
        pg.mouse.click(box["x"], box["y"])
        pg.wait_for_timeout(240)
        h.record("10. 点击遮罩关闭搜索弹窗", not open_state(pg)["open"], "")

        # ---------- 12 快速重复开关 ----------
        errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)[:120]))
        for _ in range(5):
            pg.click("#searchTrigger")
            pg.wait_for_timeout(70)
            pg.keyboard.press("Escape")
            pg.wait_for_timeout(70)
        pg.wait_for_timeout(200)
        st = open_state(pg)
        n_inert = bg_inert_count(pg)
        act = active_info(pg)
        h.record("12. 快速重复开关 5 次后状态干净（无残留 inert / 无 JS 错误）",
                 (not st["open"]) and n_inert == 0 and not errs,
                 f"open={st['open']} inert={n_inert} errors={errs[:1]}")
        h.record("12b. 快速重复开关后焦点仍正确（#searchTrigger）",
                 act["id"] == "searchTrigger", f"active=#{act['id']}")

        # ---------- 13 ?q= 深链接 ----------
        pg2 = ctx.new_page()
        pg2.goto(BASE + PAGE + "?q=suricata", wait_until="load")
        pg2.wait_for_timeout(400)
        st2 = open_state(pg2)
        val = pg2.evaluate("() => (document.querySelector('#search-input') || {}).value || ''")
        h.record("13. ?q= 深链接自动打开搜索并填入关键词",
                 st2["open"] and "suricata" in val, f"open={st2['open']} value={val!r}")
        pg2.keyboard.press("Escape")
        pg2.wait_for_timeout(250)
        act2 = pg2.evaluate("""() => {
            const a = document.activeElement;
            return {id: a ? a.id : null,
                    tag: a ? a.tagName.toLowerCase() : null,
                    isBody: a === document.body};
        }""")
        h.record("13b. ?q= 深链关闭后焦点合理恢复且不报错",
                 act2["id"] == "searchOverlay" or act2["isBody"],
                 f"active=#{act2['id'] or act2['tag']}")
        pg2.close()
        ctx.close()

        # ---------- 14 三语言可访问名称 ----------
        # 多语言构建产物通过 SEARCH_MODAL_URLS 提供（CI 中分别构建 en / zh-TW 站点）：
        #   SEARCH_MODAL_URLS="http://127.0.0.1:8080,http://127.0.0.1:8081,http://127.0.0.1:8082"
        # 顺序固定为 zh-CN, en, zh-TW；缺省则只测当前站。
        extra = [u.strip() for u in os.environ.get("SEARCH_MODAL_URLS", "").split(",")
                 if u.strip()]
        targets = [(lang, url, expect) for lang, url, expect in (
            ("zh-CN", BASE, "搜索"),
            ("en", extra[0] if len(extra) > 0 else None, "Search"),
            ("zh-TW", extra[1] if len(extra) > 1 else None, "搜尋"),
        ) if url]
        for lang, url, expect in targets:
            c2 = browser.new_context(viewport={"width": 1280, "height": 900}, locale=lang)
            pg3 = c2.new_page()
            pg3.goto(url + PAGE, wait_until="load")
            name = pg3.evaluate("""() => {
                const ov = document.querySelector('#searchOverlay');
                if (!ov) return '';
                return ov.getAttribute('aria-label') || ov.getAttribute('aria-labelledby') || '';
            }""")
            ok = expect in name
            if lang == "en":
                # 英文站不应出现硬编码中文
                ok = ok and not any(ord(ch) > 0x4E00 for ch in name)
            h.record(f"14. {lang} 搜索弹窗可访问名称正确（{expect}）", ok,
                     f"aria-label={name!r} @ {url}")
            c2.close()
        if len(targets) < 3:
            msg = (f"仅验证了 {len(targets)} 种语言"
                   f"（提供 SEARCH_MODAL_URLS 可覆盖 en / zh-TW）")
            # TEST-DEFECT-019：旧实现只 print 提示，覆盖不足时静默降级为"通过"。
            # CI 里设 REQUIRE_SEARCH_LANGS=1，覆盖不足直接判失败。
            if os.environ.get("REQUIRE_SEARCH_LANGS", "").strip() not in ("", "0", "false"):
                h.record("多语言可访问名称覆盖完整（要求 zh-CN / en / zh-TW 三种）",
                         False, msg)
            else:
                print("提示: " + msg)

        browser.close()


if __name__ == "__main__":
    main_h = Harness("search-modal")
    guard(main_h, run, main_h)
    main_h.finish()
