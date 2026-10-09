#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""搜索弹窗 / 灯箱「页面滚动锁定」回归测试（BUG-P1-001）。

背景：历史上把 body.style.overflow 的锁定与恢复放在搜索模块自己的 open()/close()
里，而遮罩点击、Escape 走的是 createModalA11y 内部的 close()，于是这些路径关闭后
body.overflow 永久停在 hidden，页面彻底滚不动（三引擎复现）。

修复后滚动锁由 createModalA11y 统一用**引用计数**管理，本脚本逐条证明：
    - 遮罩 / Escape / 深链 / 快速重复开关 / 关闭按钮 各条关闭路径都恢复滚动
    - 恢复的是**打开前的真实值**（不是无条件置空）
    - 关闭后页面真的能**被用户滚动**（mouse wheel / PageDown，而不是只看 style 字符串）
      —— 注意：overflow:hidden 仍允许 window.scrollTo 程序化滚动，所以
         程序化 scrollTo 不能用来判定"用户能否滚动"，必须用真实输入事件。
    - 关闭后焦点处于合理位置、背景 inert 已解除
    - 交替路径重复 5 轮不残留
    - 两个模态同时打开时，关闭一个**不会**解除另一个仍然持有的滚动锁

用法：
    python3 tools/verify_modal_scroll.py <base_url> [chromium|firefox|webkit]

退出码约定（见 tools/_testlib.py）：任一断言失败 -> exit 1。
"""
import os
import re
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _testlib import Harness, guard, launch, reachable  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8080"
BROWSER = sys.argv[2] if len(sys.argv) > 2 else "chromium"

CANDIDATE_PAGES = [
    "/posts/07-hugo-blog/", "/posts/06-ssh-hardening/", "/posts/05-docker-escape/",
    "/posts/04-suricata-elk/", "/posts/03-incident-response/", "/posts/02-waf-bypass/",
    "/posts/01-home-lab-proxmox/",
    # gen_testdata.py 生成的图片页（灯箱相关用例依赖）
    "/posts/zz-11-images/", "/posts/zz-images-bundle/",
    "/", "/posts/",
]


def overflow_state(pg):
    return pg.evaluate("""() => {
        const b = document.body, h = document.documentElement;
        return {
            bodyInline: b.style.overflow || '',
            bodyComputed: getComputedStyle(b).overflow,
            htmlComputed: getComputedStyle(h).overflow,
            scrollY: window.scrollY
        };
    }""")


def user_can_scroll(pg):
    """真实用户输入滚动判定：先回顶，再用滚轮 + PageDown，看 scrollY 是否真的变化。

    不能用 window.scrollTo 判定：overflow:hidden 依然允许程序化滚动。
    """
    pg.evaluate("() => window.scrollTo(0, 0)")
    pg.wait_for_timeout(60)
    pg.mouse.move(400, 400)
    pg.mouse.wheel(0, 900)
    pg.wait_for_timeout(220)
    y = pg.evaluate("() => window.scrollY")
    if y <= 50:
        pg.keyboard.press("PageDown")
        pg.wait_for_timeout(220)
        y = pg.evaluate("() => window.scrollY")
    return {"scrollY": y, "moved": y > 50}


def overlay_open(pg):
    return pg.evaluate(
        "() => { const o=document.querySelector('#searchOverlay');"
        " return !!(o && o.classList.contains('open')); }")


def lightbox_open(pg):
    return pg.evaluate(
        "() => { const l=document.querySelector('#lightbox');"
        " return !!(l && l.classList.contains('open')); }")


def active_id(pg):
    return pg.evaluate(
        "() => { const a=document.activeElement;"
        " return a ? (a.id || a.tagName.toLowerCase()) : null; }")


def bg_inert(pg):
    return pg.evaluate("""() => ['.progress-bar', '.site-header', 'main', '.site-footer', '.to-top']
        .reduce((n, s) => n + Array.from(document.querySelectorAll(s))
            .filter(x => x.hasAttribute('inert')).length, 0)""")


def _sitemap_pages(base):
    try:
        with urllib.request.urlopen(base + "/sitemap.xml", timeout=8) as r:
            xml = r.read().decode("utf-8", "ignore")
    except Exception:
        return []
    out = []
    for loc in re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", xml):
        path = loc.split("://", 1)[-1]
        path = path[path.find("/"):] if "/" in path else "/"
        out.append(path or "/")
    return out


def pick_long_page(browser):
    ctx = browser.new_context(viewport={"width": 1024, "height": 700})
    pg = ctx.new_page()
    chosen = None
    for p in CANDIDATE_PAGES:
        try:
            pg.goto(BASE + p, wait_until="load")
        except Exception:
            continue
        if pg.evaluate("() => document.documentElement.scrollHeight > window.innerHeight + 400"):
            chosen = p
            break
    ctx.close()
    return chosen


def pick_image_page(browser):
    """找一个含 .post-content img.zoomable 的页面（灯箱用例需要）。"""
    cands = [p for p in CANDIDATE_PAGES if "zz-" in p]
    cands += [p for p in _sitemap_pages(BASE) if p not in cands][:30]
    ctx = browser.new_context(viewport={"width": 1024, "height": 700})
    pg = ctx.new_page()
    chosen = None
    for p in cands:
        try:
            pg.goto(BASE + p, wait_until="load")
        except Exception:
            continue
        if pg.evaluate("() => document.querySelectorAll('.post-content img.zoomable').length > 0"):
            chosen = p
            break
    ctx.close()
    return chosen


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

        page_url = pick_long_page(browser)
        if not page_url:
            h.fatal_error("找不到可滚动页面（无法验证滚动恢复）", str(CANDIDATE_PAGES))
            browser.close()
            return
        image_page = pick_image_page(browser)
        print(f"长页面: {page_url}  图片页: {image_page or '(无)'}")

        ctx = browser.new_context(viewport={"width": 1024, "height": 700}, locale="zh-CN")
        # 故障注入（TEST-DEFECT-R2-002 思路）：SCROLL_FOCUS_BUG=1 时把 focus() 的
        # 选项参数剥掉，模拟"未使用 preventScroll"的历史实现，用于自证 2d 断言
        # 确实会在回归时变红（默认关闭，不影响正常门禁）。
        if os.environ.get("SCROLL_FOCUS_BUG", "").strip() in ("1", "true", "True"):
            ctx.add_init_script(
                "(() => { const f = HTMLElement.prototype.focus;"
                " HTMLElement.prototype.focus = function(){ return f.call(this); }; })();")
        pg = ctx.new_page()
        errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)[:140]))

        def got():
            pg.goto(BASE + page_url, wait_until="load")

        # ---------- 0 基线 ----------
        got()
        st = overflow_state(pg)
        sc = user_can_scroll(pg)
        h.record("0. 基线：页面可被用户滚动，body 未被锁",
                 sc["moved"] and st["bodyComputed"] != "hidden",
                 f"overflow={st['bodyComputed']} scrollY={sc['scrollY']}")

        # ---------- 1 打开即锁定 ----------
        pg.click("#searchTrigger")
        pg.wait_for_timeout(280)
        st = overflow_state(pg)
        locked = user_can_scroll(pg)
        h.record("1. 打开搜索弹窗时页面被锁定（背景不可滚动）",
                 st["bodyComputed"] == "hidden" and not locked["moved"],
                 f"overflow={st['bodyComputed']} 用户滚动被阻止={not locked['moved']}")

        # ---------- 2 遮罩关闭 ----------
        box = pg.evaluate("""() => { const r=document.querySelector('#searchOverlay').getBoundingClientRect();
            return {x: r.left + 4, y: r.top + 4}; }""")
        pg.mouse.click(box["x"], box["y"])
        pg.wait_for_timeout(280)
        st = overflow_state(pg)
        sc = user_can_scroll(pg)
        h.record("2. 遮罩点击关闭后 overflow 恢复且页面可被用户滚动",
                 (not overlay_open(pg)) and st["bodyComputed"] != "hidden" and sc["moved"],
                 f"overflow={st['bodyComputed']} scrollY={sc['scrollY']}")
        h.record("2b. 遮罩关闭后焦点恢复到触发元素", active_id(pg) == "searchTrigger",
                 f"active=#{active_id(pg)}")
        h.record("2c. 遮罩关闭后背景 inert 全部解除", bg_inert(pg) == 0,
                 f"剩余 inert {bg_inert(pg)}")

        # ---------- 2d 关闭弹窗不得移动页面滚动位置（BUG-R2-004） ----------
        # 症状：把焦点还给触发元素时若不阻止滚动，Chromium/WebKit 会把文档滚回
        # 触发按钮的静态位置，用户在长文中开关搜索后页面位置被拉走。
        # 判据：关闭后的 scrollY 与打开后（同一锁定位置）相比漂移不得超过容差。
        # 实测：修复前 Chromium −358px / WebKit −65px；修复后三引擎漂移 = 0px。
        pg.evaluate("() => window.scrollTo(0, 1600)")
        pg.wait_for_timeout(150)
        pg.click("#searchTrigger")
        pg.wait_for_timeout(280)
        y_open = pg.evaluate("() => window.scrollY")
        pg.keyboard.press("Escape")
        pg.wait_for_timeout(320)
        y_close = pg.evaluate("() => window.scrollY")
        drift = abs(y_close - y_open)
        h.record("2d. 关闭弹窗后页面滚动位置不被改变（preventScroll，BUG-R2-004）",
                 drift <= 60, f"open={y_open:.0f} close={y_close:.0f} 漂移={drift:.0f}px")

        # ---------- 3 Escape（焦点在触发元素上） ----------
        got()
        pg.click("#searchTrigger")
        pg.wait_for_timeout(240)
        pg.keyboard.press("Escape")
        pg.wait_for_timeout(280)
        st = overflow_state(pg)
        sc = user_can_scroll(pg)
        h.record("3. Escape 关闭后 overflow 恢复且页面可被用户滚动",
                 (not overlay_open(pg)) and st["bodyComputed"] != "hidden" and sc["moved"],
                 f"overflow={st['bodyComputed']} scrollY={sc['scrollY']}")

        # ---------- 4 Escape（焦点在输入框内） ----------
        got()
        pg.click("#searchTrigger")
        pg.wait_for_timeout(240)
        pg.click("#search-input")
        pg.keyboard.press("Escape")
        pg.wait_for_timeout(280)
        st = overflow_state(pg)
        h.record("4. 焦点在输入框内按 Escape 关闭后滚动同样恢复",
                 (not overlay_open(pg)) and st["bodyComputed"] != "hidden",
                 f"overflow={st['bodyComputed']}")

        # ---------- 5 ?q= 深链 + Escape ----------
        pg.goto(BASE + page_url + "?q=security", wait_until="load")
        pg.wait_for_timeout(450)
        opened = overlay_open(pg)
        st_open = overflow_state(pg)
        pg.keyboard.press("Escape")
        pg.wait_for_timeout(320)
        st = overflow_state(pg)
        sc = user_can_scroll(pg)
        h.record("5. ?q= 深链打开后 Escape 关闭 -> 滚动恢复",
                 opened and st_open["bodyComputed"] == "hidden"
                 and (not overlay_open(pg)) and st["bodyComputed"] != "hidden" and sc["moved"],
                 f"打开时={st_open['bodyComputed']} 关闭后={st['bodyComputed']}")
        h.record("5b. ?q= 深链关闭后焦点合理（overlay 自身或 body）",
                 active_id(pg) in ("searchOverlay", "body"), f"active=#{active_id(pg)}")

        # ---------- 5c ?q= 深链 + 遮罩 ----------
        pg.goto(BASE + page_url + "?q=security", wait_until="load")
        pg.wait_for_timeout(450)
        box = pg.evaluate("""() => { const r=document.querySelector('#searchOverlay').getBoundingClientRect();
            return {x: r.left + 4, y: r.top + 4}; }""")
        pg.mouse.click(box["x"], box["y"])
        pg.wait_for_timeout(300)
        st = overflow_state(pg)
        sc = user_can_scroll(pg)
        h.record("5c. ?q= 深链 + 遮罩关闭 -> 滚动恢复",
                 (not overlay_open(pg)) and st["bodyComputed"] != "hidden" and sc["moved"],
                 f"overflow={st['bodyComputed']}")

        # ---------- 6 页面原有非默认 overflow ----------
        got()
        pg.evaluate("() => { document.body.style.overflow = 'auto'; }")
        pg.click("#searchTrigger")
        pg.wait_for_timeout(240)
        pg.keyboard.press("Escape")
        pg.wait_for_timeout(280)
        st = overflow_state(pg)
        h.record("6. 打开前的非默认 overflow 被原样恢复（不是无条件置空）",
                 st["bodyInline"] == "auto",
                 f"关闭后 body.style.overflow={st['bodyInline']!r}（期望 'auto'）")
        pg.evaluate("() => { document.body.style.overflow = ''; }")

        # ---------- 7 快速 打开->关闭->再打开 ----------
        got()
        errs.clear()
        pg.click("#searchTrigger")
        pg.wait_for_timeout(70)
        pg.keyboard.press("Escape")
        pg.wait_for_timeout(70)
        pg.click("#searchTrigger")
        pg.wait_for_timeout(230)
        still_open = overlay_open(pg)
        locked2 = overflow_state(pg)["bodyComputed"] == "hidden"
        pg.keyboard.press("Escape")
        pg.wait_for_timeout(280)
        st = overflow_state(pg)
        sc = user_can_scroll(pg)
        h.record("7. 快速 打开→关闭→再打开：第二次打开仍正确锁定",
                 still_open and locked2, f"open={still_open} 锁定={locked2}")
        h.record("7b. 快速开关后最终状态干净（解锁 / 可滚动 / 无 JS 错误）",
                 (not overlay_open(pg)) and st["bodyComputed"] != "hidden"
                 and sc["moved"] and not errs,
                 f"overflow={st['bodyComputed']} errors={errs[:1]}")

        # ---------- 8 开关过程中连续键盘事件 ----------
        got()
        errs.clear()
        pg.click("#searchTrigger")
        pg.wait_for_timeout(220)
        for key in ("Tab", "Tab", "Shift+Tab", "ArrowDown", "ArrowUp", "a", "Enter", "Escape"):
            pg.keyboard.press(key)
            pg.wait_for_timeout(50)
        pg.wait_for_timeout(280)
        st = overflow_state(pg)
        sc = user_can_scroll(pg)
        h.record("8. 开关过程中连续键盘事件后状态干净（无卡死 / 无 JS 错误）",
                 (not overlay_open(pg)) and st["bodyComputed"] != "hidden"
                 and sc["moved"] and not errs,
                 f"overflow={st['bodyComputed']} errors={errs[:1]}")

        # ---------- 9 交替路径重复 5 轮 ----------
        got()
        errs.clear()
        cycle_ok, residue = True, ""
        for i in range(5):
            pg.click("#searchTrigger")
            pg.wait_for_timeout(80)
            if i % 2 == 0:
                pg.keyboard.press("Escape")
            else:
                b = pg.evaluate("""() => { const r=document.querySelector('#searchOverlay')
                    .getBoundingClientRect(); return {x: r.left + 4, y: r.top + 4}; }""")
                pg.mouse.click(b["x"], b["y"])
            pg.wait_for_timeout(110)
            if (not overlay_open(pg)) and overflow_state(pg)["bodyComputed"] == "hidden":
                cycle_ok = False
                residue = f"第 {i + 1} 轮关闭后仍锁定"
                break
        st = overflow_state(pg)
        sc = user_can_scroll(pg)
        h.record("9. 交替 Escape / 遮罩重复 5 轮：每轮干净、最终可滚动",
                 cycle_ok and st["bodyComputed"] != "hidden" and sc["moved"] and not errs,
                 residue or f"overflow={st['bodyComputed']} errors={errs[:1]}")

        # ---------- 10 双模态：关闭一个不解除另一个的锁 ----------
        if not image_page:
            h.record("10. 双模态叠加（搜索 + 灯箱）滚动锁互不干扰", False,
                     "站点无 .post-content img.zoomable，灯箱不可用 -> 该路径未验证")
            h.record("11. 点击关闭按钮关闭后滚动恢复（灯箱 .lightbox-close）", False,
                     "站点无 .zoomable 图片 -> 该路径未验证")
        else:
            pg.goto(BASE + image_page, wait_until="load")
            pg.wait_for_timeout(200)
            pg.evaluate("() => document.querySelector('.post-content img.zoomable').click()")
            pg.wait_for_timeout(320)
            lb = lightbox_open(pg)
            lb_locked = overflow_state(pg)["bodyComputed"] == "hidden"
            h.record("10a. 灯箱打开时页面被锁定", lb and lb_locked,
                     f"lightbox={lb} overflow={overflow_state(pg)['bodyComputed']}")
            # 灯箱打开时用 Ctrl+K 打开搜索（搜索的 document keydown 未被灯箱拦截）
            pg.keyboard.press("Control+k")
            pg.wait_for_timeout(320)
            both = overlay_open(pg) and lightbox_open(pg)
            if both:
                st = overflow_state(pg)
                # 只关灯箱（程序化触发其关闭按钮；inert 会阻断真实点击）
                pg.evaluate("""() => { const c=document.querySelector('#lightbox .lightbox-close');
                    if (c) c.dispatchEvent(new MouseEvent('click', {bubbles:true, cancelable:true})); }""")
                pg.wait_for_timeout(320)
                st2 = overflow_state(pg)
                h.record("10b. 两个模态同时打开时仍锁定，关闭灯箱后搜索未关闭且滚动锁仍在",
                         (not lightbox_open(pg)) and overlay_open(pg)
                         and st2["bodyComputed"] == "hidden",
                         f"关闭后 lightbox={lightbox_open(pg)} search={overlay_open(pg)} "
                         f"overflow={st2['bodyComputed']}")
                pg.keyboard.press("Escape")
                pg.wait_for_timeout(320)
                st3 = overflow_state(pg)
                sc = user_can_scroll(pg)
                h.record("10c. 最后一个模态关闭后滚动解锁",
                         (not overlay_open(pg)) and (not lightbox_open(pg))
                         and st3["bodyComputed"] != "hidden" and sc["moved"],
                         f"overflow={st3['bodyComputed']}")
            else:
                h.record("10b. 两个模态同时打开时仍锁定，关闭灯箱后搜索未关闭且滚动锁仍在", False,
                         f"未能同时打开（lightbox={lightbox_open(pg)} search={overlay_open(pg)}）")
            # ---------- 11 关闭按钮路径 ----------
            pg.goto(BASE + image_page, wait_until="load")
            pg.wait_for_timeout(200)
            pg.evaluate("() => document.querySelector('.post-content img.zoomable').click()")
            pg.wait_for_timeout(320)
            pg.click("#lightbox .lightbox-close")
            pg.wait_for_timeout(320)
            st = overflow_state(pg)
            sc = user_can_scroll(pg)
            h.record("11. 点击关闭按钮关闭后滚动恢复（灯箱 .lightbox-close）",
                     (not lightbox_open(pg)) and st["bodyComputed"] != "hidden" and sc["moved"],
                     f"overflow={st['bodyComputed']}")

        search_has_close = pg.evaluate("""() => !!document.querySelector(
            '#searchOverlay button[class*="close"], #searchOverlay .search-close')""")
        print(f"注：搜索弹窗含独立关闭按钮 = {search_has_close}"
              f"（当前设计为遮罩 / Escape 关闭；关闭按钮路径由灯箱覆盖）")

        ctx.close()
        browser.close()


if __name__ == "__main__":
    main_h = Harness("modal-scroll")
    guard(main_h, run, main_h)
    main_h.finish()
