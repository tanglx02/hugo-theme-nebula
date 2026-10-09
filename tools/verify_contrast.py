#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""文字对比度门禁（WCAG 2.1 AA，BUG-P2-003）。

背景：v1.0.9 独立测试报告实测浅色主题存在多处对比度不足（最低 2.39:1），
包括 muted 文本（.search-trigger/.mini-date/.profile-desc 3.47–3.66:1）、
chip 类标签（2.39–2.48:1）。根因是一组颜色 token 直接拿鲜亮色当**文字色**／
拿鲜亮色当**承载白字的背景**。

本脚本在真实浏览器里取 computed style，按 WCAG 相对亮度公式（含 alpha 合成）
逐元素计算对比度，浅色 / 深色两套主题都要达标：
  - 普通文字（< 18.66px bold 或 < 24px）要求 >= 4.5:1
  - 大号文字要求 >= 3:1
并且要求"每个受检选择器至少命中 1 个元素"——否则视为**空转**，判定失败，
避免选择器改名后门禁悄悄失效（假绿）。

用法：
    python3 tools/verify_contrast.py <base_url> [chromium|firefox|webkit]

退出码约定（见 tools/_testlib.py）：任一对比度不足 / 选择器空转 -> exit 1。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _testlib import Harness, guard, launch, reachable  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8080"
BROWSER = sys.argv[2] if len(sys.argv) > 2 else "chromium"

# 受检页面（覆盖首页 / 文章 / 系列，缺失的页面会被跳过并记录）
PAGES = ["/", "/posts/", "/posts/07-hugo-blog/", "/posts/zz-series-1/", "/archives/"]

# 必须命中的选择器（每个至少 1 个元素，否则判"空转"失败）
REQUIRED_SELECTORS = [
    ".search-trigger", ".chip-cat", ".chip-tag",
    ".profile-desc", ".mini-date", ".post-summary",
    ".site-footer", ".breadcrumb a", ".toc a",
]
# 尽力而为的选择器（命中就检查，不强制存在）
OPTIONAL_SELECTORS = [
    ".chip-sticky", ".series-now", ".series-progress", ".series-idx",
    ".pagination .current", ".cat-list a", ".tag-cloud a", "time", ".stat",
]
SELECTORS = REQUIRED_SELECTORS + OPTIONAL_SELECTORS

MEASURE_JS = """(sels) => {
  function lin(c){c/=255;return c<=0.03928?c/12.92:Math.pow((c+0.055)/1.055,2.4);}
  function L(r){return 0.2126*lin(r[0])+0.7152*lin(r[1])+0.0722*lin(r[2]);}
  function parse(s){const m=s.match(/rgba?\\(([^)]+)\\)/);if(!m)return null;
    const p=m[1].split(',').map(x=>parseFloat(x));return {rgb:[p[0],p[1],p[2]],a:p.length>3?p[3]:1};}
  function over(fg,bg){return fg.rgb.map((v,i)=>v*fg.a+bg[i]*(1-fg.a));}
  function compBg(el){let layers=[],n=el;while(n&&n!==document.documentElement){
    const c=parse(getComputedStyle(n).backgroundColor);
    if(c&&c.a>0){layers.push(c);if(c.a>=0.999)break;} n=n.parentElement;}
    let bg=[255,255,255];for(let i=layers.length-1;i>=0;i--)bg=over(layers[i],bg);return bg;}
  const out=[];
  for(const s of sels){
    let found=0;
    for(const el of document.querySelectorAll(s)){
      if(!el.offsetWidth&&!el.offsetHeight) continue;
      const t=(el.textContent||'').trim(); if(!t) continue;
      const cs=getComputedStyle(el); const fg=parse(cs.color); if(!fg) continue;
      const bg=compBg(el); const f=over(fg,bg);
      const l1=L(f),l2=L(bg); const hi=Math.max(l1,l2),lo=Math.min(l1,l2);
      out.push({sel:s,text:t.slice(0,20),size:parseFloat(cs.fontSize),weight:cs.fontWeight,
        ratio:Math.round((hi+0.05)/(lo+0.05)*100)/100});
      found++; if(found>=3) break;   // 每个选择器最多取 3 个样本
    }
    if(found===0) out.push({sel:s,empty:true,ratio:0,size:0,weight:'',text:''});
  }
  return out;
}"""


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

        for theme in ("light", "dark"):
            ctx = browser.new_context(viewport={"width": 1280, "height": 900}, locale="zh-CN")
            rows = []
            used_pages = []
            for path in PAGES:
                pg = ctx.new_page()
                try:
                    pg.goto(BASE + path, wait_until="load")
                except Exception:
                    pg.close()
                    continue
                pg.wait_for_timeout(150)
                # 主题用 data-theme 属性驱动（主题自身也是这么切的）。
                # 不靠 localStorage 预置：跨文档边界不可靠，实测会静默退回 light。
                pg.evaluate(
                    "() => { document.documentElement.setAttribute('data-theme', '%s'); }" % theme)
                # 关键：主题带 `transition: all .2s`，切换后立刻取色会拿到**过渡中间值**
                # （实测 dark 下 .search-trigger 被读成 1.1:1 的假故障）。测量前先禁用过渡。
                pg.add_style_tag(content="*,*::before,*::after{transition:none !important;"
                                          "animation:none !important;}")
                pg.wait_for_timeout(150)
                actual = pg.evaluate(
                    "() => document.documentElement.getAttribute('data-theme')")
                if actual != theme:
                    h.fatal_error(f"无法切换到 {theme} 主题", f"data-theme={actual}")
                    pg.close()
                    continue
                r = pg.evaluate(MEASURE_JS, SELECTORS)
                if r:
                    rows += r
                    used_pages.append(path)
                pg.close()
            ctx.close()

            if not used_pages:
                h.fatal_error(f"{theme} 主题没有任何页面可测", str(PAGES))
                continue

            by_sel = {}
            for r in rows:
                by_sel.setdefault(r["sel"], []).append(r)

            # 1) 空转保护：必需选择器必须命中
            missing = [s for s in REQUIRED_SELECTORS
                       if not any(not x.get("empty") for x in by_sel.get(s, []))]
            h.record(f"[{theme}] 受检选择器未空转（必需项全部命中）",
                     not missing,
                     f"未命中: {missing}" if missing else
                     f"{len(REQUIRED_SELECTORS)} 个必需选择器均命中，页面 {used_pages}")

            # 2) 对比度阈值
            fails = []
            samples = 0
            for r in rows:
                if r.get("empty"):
                    continue
                samples += 1
                size, weight = r["size"], str(r["weight"])
                bold = weight in ("700", "bold", "800", "900")
                large = size >= 24 or (size >= 18.66 and bold)
                need = 3.0 if large else 4.5
                if r["ratio"] < need:
                    fails.append(f'{r["sel"]} {r["ratio"]}:1 < {need} ({size}px w={weight}) {r["text"]!r}')
            h.record(f"[{theme}] 文字对比度全部达标 WCAG AA（{samples} 项样本）",
                     not fails, "；".join(fails[:5]) if fails else "全部 >= 4.5:1（大号文字 >= 3:1）")

        browser.close()


if __name__ == "__main__":
    main_h = Harness("contrast")
    guard(main_h, run, main_h)
    main_h.finish()
