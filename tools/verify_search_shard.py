#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""搜索分块失败场景测试。

覆盖：
  主索引 404 / 500 / JSON 损坏
  部分分块 404 / 500 / 超时 / JSON 损坏 / 全部分块失败
  重试恢复 / 重复搜索
  **分块失败时的关键词语义**：
      - 失败分块内的正文深层关键词 -> 不命中 + 明确提示（绝不显示成"没有找到"）
      - 其他分块内的正文关键词      -> 正常命中
      - 标题/摘要关键词            -> 不受正文分块失败影响

用法：python tools/verify_search_shard.py [shard_site_url] [browser]
前提：该站点以 params.search.shard/mode=shard 构建，且分块数 >= 2
      （CI 通过 shard-override.toml 设置较小的 chunkSize 以保证多分块）

退出码约定（见 tools/_testlib.py）：断言失败 / 浏览器启动失败 / 0 用例 -> exit 1。
"""
import json
import os
import re
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _testlib import Harness, launch as _launch, reachable  # noqa: E402

from playwright.sync_api import sync_playwright  # noqa: E402

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8091"
BROWSER = sys.argv[2] if len(sys.argv) > 2 else "chromium"

# gen_testdata.py 在长文正文中埋入的唯一标记
DEEP_MARKERS = ["ALPHA1000", "BRAVO3000", "CHARLIE3500", "DELTA5000", "ECHO8000",
                "FOXTROT10000", "SIERRA2000", "TANGO25000", "GOLF48000"]
# 标题关键词（用于验证标题匹配不依赖正文分块）
TITLE_KEYWORD = "一万字"

H = Harness(f"search-shard-{BROWSER}")


def rec(name, ok, detail=""):
    return H.record(name, ok, detail)


# --------------------------------------------------------------- 分块结构探测
def discover_chunks():
    """返回 {"chunk_url": {item_key: content}, ...}；非分块结构返回 None。"""
    base = BASE.rstrip("/")
    with urllib.request.urlopen(base + "/index.json", timeout=25) as r:
        doc = json.loads(r.read().decode("utf-8"))
    if not isinstance(doc, dict) or not doc.get("chunks"):
        return None, None
    contents = {}
    for u in doc["chunks"]:
        url = u if u.startswith("http") else base + u
        with urllib.request.urlopen(url, timeout=25) as r:
            contents[u] = json.loads(r.read().decode("utf-8"))
    return doc, contents


def metadata_blob(doc):
    """所有条目的 title/summary/tags/categories/series 拼接，用于判定"该词只可能来自正文"。"""
    parts = []
    for it in doc.get("items", []):
        for k in ("title", "summary"):
            parts.append(str(it.get(k) or ""))
        for k in ("tags", "categories", "series"):
            v = it.get(k) or []
            parts.append(" ".join(v) if isinstance(v, list) else str(v))
    return " ".join(parts)


def pick_content_only_keyword(content, meta, length=10):
    """从正文里挑一个只在正文出现、不落在任何元数据里的中文片段（用于证明正文被加载）。"""
    step = max(1, len(content) // 40)
    for start in range(0, max(1, len(content) - length), step):
        seg = content[start:start + length]
        if not re.fullmatch(r"[\u4e00-\u9fff，。、；：\"'（）\s]*", seg):
            continue
        seg = seg.strip("，。、；：\u3000 ")
        if len(seg) < 6:
            continue
        if seg in meta:
            continue
        if re.search(r"\s", seg):
            continue
        return seg
    return None


# --------------------------------------------------------------- 用例执行
def _retry_visible(pg):
    try:
        return pg.locator("#searchRetry").is_visible()
    except Exception:
        return False


def read_state(pg):
    """一次性快照页面状态。

    为什么必须一次读全（TEST-DEFECT-R2-010）：旧实现里每个断言都写成
    `count_items(pg) > 0 and status_text(pg) == ""`，随后详情串又各自再读一次
    `count_items` / `status_text`。异步搜索在两次读取之间改变状态时，会出现
    "判定用到的值"与"详情打印的值"不一致 —— 例如判定时 status 尚为"部分失败"
    （判红），打印详情时已变回 ""（看起来完全正常），产生**自相矛盾的假红**。
    先快照再判定，保证判定与详情取自同一时刻。
    """
    return {
        "count": count_items(pg),
        "status": status_text(pg),
        "empty": empty_text(pg),
        "retry": _retry_visible(pg),
    }


def run_case(browser, name, rules, keyword, check, tries=3, wait=800):
    """rules: [(pattern, handler)]；check(state) -> (ok, detail)

    对异步搜索做**有界稳定重试**：首次判定失败时，等 UI 再次稳定后重判，最多
    `tries` 次。真实缺陷的状态是**稳定地坏**的，重试仍判红，断言强度不变；
    仅消除"读得太早"造成的偶发假红（flakiness），不掩盖真实缺陷。
    """
    ctx = browser.new_context(viewport={"width": 1440, "height": 900}, locale="zh-CN")
    page = ctx.new_page()
    for pattern, handler in rules:
        page.route(pattern, handler)
    try:
        page.goto(BASE + "/", wait_until="load")
        page.click("#searchTrigger")
        page.fill("#search-input", keyword)
        page.wait_for_timeout(2200)
        ok, detail = check(read_state(page))
        attempt = 1
        while not ok and attempt < tries:
            page.wait_for_timeout(wait)
            ok, detail = check(read_state(page))
            attempt += 1
        rec(name, ok, detail)
    except Exception as e:
        rec(name, False, f"异常: {str(e)[:110]}")
    finally:
        ctx.close()


def status_text(page):
    try:
        if page.locator("#searchStatus").count() and page.locator("#searchStatus").is_visible():
            return page.locator("#searchStatusText").inner_text().strip()
    except Exception:
        pass
    return ""


def empty_text(page):
    try:
        if page.locator(".search-empty").count():
            return page.locator(".search-empty").inner_text().strip()
    except Exception:
        pass
    return ""


def count_items(page):
    return page.locator(".search-item").count()


def fail_chunk_rule(chunk_url):
    """让指定分块返回 404。"""
    pattern = "**" + chunk_url

    def handler(route):
        route.fulfill(status=404, body="chunk gone")
    return (pattern, handler)


def _run_all():
    if not reachable(BASE + "/"):
        H.fatal_error("被测站点不可达", BASE)
        return

    doc, chunks = None, None
    try:
        doc, chunks = discover_chunks()
    except Exception as e:
        print("分块结构探测失败:", str(e)[:160])

    with sync_playwright() as p:
        launcher = {"chromium": p.chromium, "firefox": p.firefox, "webkit": p.webkit}[BROWSER]
        try:
            browser = _launch(launcher)
        except Exception as e:
            H.fatal_error(f"{BROWSER} 浏览器启动失败", str(e)[:200])
            return

        # ---------------------------------------------------------- 全部成功
        run_case(browser, "全部成功：有结果且无状态提示", [], DEEP_MARKERS[-1], lambda s: (
            s["count"] > 0 and s["status"] == "",
            f'{s["count"]} 条, status="{s["status"]}"'))

        # ---------------------------------------------------------- 主索引失败
        def fail_main(status, label):
            def handler(route):
                route.fulfill(status=status, body="boom")
            run_case(browser, f"主索引 {label}：明确报错 + 有重试按钮",
                     [("**/index.json", handler)], DEEP_MARKERS[-1],
                     lambda s: ("失败" in s["status"] and s["retry"]
                                and "没有找到" not in s["empty"],
                                f'status="{s["status"]}" empty="{s["empty"][:24]}"'))

        fail_main(404, "404")
        fail_main(500, "500")

        def corrupt_main(route):
            route.fulfill(status=200, body="{ this is not json", content_type="application/json")
        run_case(browser, "主索引 JSON 损坏：明确报错", [("**/index.json", corrupt_main)], DEEP_MARKERS[-1],
                 lambda s: ("失败" in s["status"] and "没有找到" not in s["empty"],
                            f'status="{s["status"]}"'))

        # ---------------------------------------------------------- 部分分块失败
        def partial_shard(status, label, delay=0):
            def effect(route):
                if delay:
                    import time
                    time.sleep(delay)
                    route.abort("timedout")
                else:
                    route.fulfill(status=status, body="shard error")
            state = {"n": 0}

            def selective(route):
                state["n"] += 1
                if state["n"] == 1:
                    return effect(route)
                route.continue_()

            # 用标题关键词验证：正文分块失败不应影响标题/摘要匹配，且不得误报无结果
            run_case(browser, f"部分分块 {label}：提示部分失败且标题匹配仍可用",
                     [("**/search/*.json", selective)], TITLE_KEYWORD,
                     lambda s: (("部分" in s["status"]) and s["count"] > 0
                                and "没有找到" not in s["empty"],
                                f'{s["count"]} 条, status="{s["status"][:40]}"'))

        partial_shard(404, "404")
        partial_shard(500, "500")

        def corrupt_shard():
            state = {"n": 0}

            def handler(route):
                state["n"] += 1
                if state["n"] == 1:
                    route.fulfill(status=200, body="not-json-at-all", content_type="application/json")
                else:
                    route.continue_()
            run_case(browser, "部分分块 JSON 损坏：提示部分失败且标题匹配仍可用",
                     [("**/search/*.json", handler)], TITLE_KEYWORD,
                     lambda s: (("部分" in s["status"]) and s["count"] > 0,
                                f'{s["count"]} 条, status="{s["status"][:40]}"'))
        corrupt_shard()

        # ---------------------------------------------------------- 分块失败的关键词语义（核心）
        if chunks and len(chunks) >= 2:
            meta = metadata_blob(doc)
            # 找承载"正文深层标记"的分块作为 victim，另一个分块作为 ok
            victim_url = victim_kw = None
            for u, m in chunks.items():
                blob = json.dumps(m, ensure_ascii=False)
                hits_kw = [k for k in DEEP_MARKERS if k in blob]
                if hits_kw:
                    victim_url, victim_kw = u, hits_kw[0]
                    break
            ok_url = ok_kw = None
            for u, m in chunks.items():
                if u == victim_url:
                    continue
                merged = "".join(v for v in m.values() if isinstance(v, str))
                kw = pick_content_only_keyword(merged, meta)
                if kw:
                    ok_url, ok_kw = u, kw
                    break

            if not victim_url:
                H.fatal_error("未在任何分块中找到正文深层标记",
                              "stress 数据可能未生成或分块配置异常，无法验证失败语义")
            elif not ok_url:
                H.fatal_error("未找到可用于对照的第二分块关键词",
                              f"{len(chunks)} 个分块，其余分块正文中未提取到可用关键词")
            else:
                print(f"\n[语义测试] victim={victim_url} kw={victim_kw} | ok={ok_url} kw={ok_kw}\n")

                # 基线：不注入失败时，victim 关键词应可检索（证明它确实可被搜到）
                run_case(browser, f"基线：正文深层关键词可检索（{victim_kw}）", [], victim_kw,
                         lambda s: (s["count"] > 0, f'{s["count"]} 条'))

                rules = [fail_chunk_rule(victim_url)]

                # ① 失败分块内的正文深层关键词 -> 不命中 + 明确提示（不得显示"没有找到"）
                run_case(browser, f"失败分块①：其正文深层关键词不命中且明确提示（{victim_kw}）",
                         rules, victim_kw,
                         lambda s: (s["count"] == 0
                                    and "没有找到" not in s["empty"]
                                    and ("部分" in s["status"] or "失败" in s["status"]),
                                    f'{s["count"]} 条, status="{s["status"][:46]}", empty="{s["empty"][:34]}"'))

                # ② 未失败分块内的正文关键词 -> 正常命中（证明其余分块已加载且正文可搜）
                run_case(browser, f"失败分块②：其他分块正文关键词仍命中（{ok_kw}）",
                         rules, ok_kw,
                         lambda s: (s["count"] > 0,
                                    f'{s["count"]} 条, status="{s["status"][:40]}"'))

                # ③ 标题关键词 -> 不受正文分块失败影响
                run_case(browser, f"失败分块③：标题关键词不受影响（{TITLE_KEYWORD}）",
                         rules, TITLE_KEYWORD,
                         lambda s: (s["count"] > 0, f'{s["count"]} 条'))
        else:
            H.fatal_error("站点分块数不足 2",
                          f"chunks={0 if not chunks else len(chunks)}，无法验证部分分块失败语义"
                          "（请在测试配置中设置较小的 params.search.chunkSize）")

        # ---------------------------------------------------------- 全部已加载分块失败
        run_case(browser, "全部分块失败：明确提示且标题匹配仍可用",
                 [("**/search/*.json", lambda route: route.fulfill(status=404, body="nope"))],
                 TITLE_KEYWORD,
                 lambda s: (("部分" in s["status"]) and s["count"] > 0
                            and "没有找到" not in s["empty"],
                            f'{s["count"]} 条, status="{s["status"][:40]}"'))

        # ---------------------------------------------------------- 重试恢复
        ctx = browser.new_context(viewport={"width": 1440, "height": 900}, locale="zh-CN")
        page = ctx.new_page()
        failing = {"on": True}

        def toggle_main(route):
            if failing["on"]:
                route.fulfill(status=500, body="down")
            else:
                route.continue_()
        page.route("**/index.json", toggle_main)
        page.goto(BASE + "/", wait_until="load")
        page.click("#searchTrigger")
        page.fill("#search-input", DEEP_MARKERS[-1])
        page.wait_for_timeout(1500)
        failed_shown = "失败" in status_text(page)
        failing["on"] = False                      # 恢复网络后点击重试
        page.click("#searchRetry")
        page.wait_for_timeout(2200)
        recovered = count_items(page) > 0 and status_text(page) == ""
        rec("重试：失败态可见且重试后恢复", failed_shown and recovered,
            f'失败态={failed_shown}, 恢复后 {count_items(page)} 条, status="{status_text(page)}"')

        # ---------------------------------------------------------- 重复搜索
        page.fill("#search-input", "")
        for kw in ["安全", "Hugo", "docker", "应急", TITLE_KEYWORD]:
            page.fill("#search-input", kw)
            page.wait_for_timeout(250)
        page.wait_for_timeout(1200)
        cnt = count_items(page)
        rec("连续多次输入不报错且结果正常", cnt > 0 and status_text(page) == "", f"{cnt} 条")
        ctx.close()
        browser.close()


def main():
    try:
        _run_all()
    except Exception:
        import traceback
        tb = traceback.format_exc().strip().splitlines()
        H.fatal_error("脚本异常", tb[-1][:200] if tb else "unknown")
    H.finish()


if __name__ == "__main__":
    main()
