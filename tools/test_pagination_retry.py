#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""分页发现的重试与失败语义测试（四种场景，注入假 fetch，不依赖网络）。

场景：
    1. 正常分页：无失败 -> exhausted=True, failures=0
    2. 第一次失败第二次成功 -> 重试生效，最终成功，exhausted=True
    3. 前两次失败第三次成功 -> 重试次数足够，exhausted=True
    4. 所有重试均失败 -> discovery_failures 非空，**exhausted=False**

第 4 条是本测试的核心：旧实现里"抓取失败 + 队列空 = exhausted=True + PASS"
是可能的假绿，现在必须判为未完成。

用法：python3 tools/test_pagination_retry.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import audit  # noqa: E402
from _testlib import Harness, guard  # noqa: E402

# 假站点：/ 链到 /posts/page/2/，/posts/page/2/ 链到 /posts/page/3/
SITE = {
    "/": '<a href="/posts/page/2/">next</a>',
    "/posts/page/2/": '<a href="/posts/page/3/">next</a>',
    "/posts/page/3/": '<a href="/posts/page/4/">next</a>',
    "/posts/page/4/": '<a href="/posts/page/5/">next</a>',
}
SEEDS = ["/"]


def make_fetch(fail_plan):
    """fail_plan: {url: 需要连续失败的次数}；超过该次数即成功。"""
    state = {}

    def fetch(base, path):
        n = state.get(path, 0)
        need = fail_plan.get(path, 0)
        if n < need:
            state[path] = n + 1
            return None, f"URLError: 模拟第 {n + 1} 次失败"
        return SITE.get(path, "<html></html>"), None

    return fetch


def run(h):
    # --- 场景 1：正常分页 ---
    found, meta = audit.discover_pagination("", SEEDS, fetch=make_fetch({}))
    h.record("场景1 正常分页：4 个分页页全部发现",
             found == ["/posts/page/2/", "/posts/page/3/", "/posts/page/4/", "/posts/page/5/"],
             str(found))
    h.record("场景1 零失败且 exhausted=True",
             meta["discovery_failures"] == [] and meta["exhausted"] is True,
             f"failures={len(meta['discovery_failures'])} attempts={meta['discovery_attempts']}")

    # --- 场景 2：第一次失败第二次成功 ---
    found, meta = audit.discover_pagination("", SEEDS, fetch=make_fetch({"/": 1}))
    h.record("场景2 首次失败重试后恢复，仍发现 4 个分页页",
             len(found) == 4, f"found={len(found)}")
    h.record("场景2 重试被记录（discovery_retries >= 1）",
             meta["discovery_retries"] >= 1,
             f"retries={meta['discovery_retries']}")
    h.record("场景2 无最终失败且 exhausted=True",
             meta["discovery_failures"] == [] and meta["exhausted"] is True,
             f"failures={len(meta['discovery_failures'])}")

    # --- 场景 3：前两次失败第三次成功 ---
    found, meta = audit.discover_pagination("", SEEDS, fetch=make_fetch({"/": 2}))
    h.record("场景3 两次失败后第三次成功，发现 4 个分页页",
             len(found) == 4, f"found={len(found)}")
    h.record("场景3 重试次数为 2（DISCOVERY_RETRIES）",
             meta["discovery_retries"] == 2, f"retries={meta['discovery_retries']}")
    h.record("场景3 无最终失败且 exhausted=True",
             meta["discovery_failures"] == [] and meta["exhausted"] is True,
             f"failures={len(meta['discovery_failures'])}")

    # --- 场景 4：所有重试均失败 ---
    found, meta = audit.discover_pagination(
        "", SEEDS, fetch=make_fetch({"/": 99, "/posts/page/2/": 99}))
    h.record("场景4 全部重试失败：discovery_failures 非空",
             len(meta["discovery_failures"]) > 0,
             f"failures={len(meta['discovery_failures'])}")
    h.record("场景4 关键：exhausted 必须为 False（不得判 PASS）",
             meta["exhausted"] is False,
             f"exhausted={meta['exhausted']}（旧实现会误判为 True）")
    h.record("场景4 失败记录含 URL 与异常",
             all("url" in f and "error" in f for f in meta["discovery_failures"]),
             str(meta["discovery_failures"][:1]))
    # 失败页面不会入队（其链接无从发现），所以尝试次数恰好是 1 + 2 次重试
    h.record("场景4 尝试次数 = 3（1 次 + 2 次重试；失败页不入队）",
             meta["discovery_attempts"] == 3,
             f"attempts={meta['discovery_attempts']}, retries={meta['discovery_retries']}")
    h.record("场景4 失败页未入队，其分页链接无从发现（属预期）",
             found == [] and meta["queue_exhausted"] is True,
             f"found={found}, queue_exhausted={meta['queue_exhausted']}")


if __name__ == "__main__":
    main_h = Harness("pagination-retry")
    guard(main_h, run, main_h)
    main_h.finish()
