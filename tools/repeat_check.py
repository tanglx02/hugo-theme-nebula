#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""重复运行某个浏览器测试脚本 N 次，用于**检测偶发假红 / flaky**。

背景（TEST-DEFECT-R2-009）：浏览器回归测试里存在"依赖时序"的脆弱断言——
例如先 `window.scrollTo(0, 0)` 再用固定等待判定页面是否可滚动，而站点 CSS 设了
`html { scroll-behavior: smooth }`，无头浏览器动画被节流时该调用**不会立即归零**，
于是同一条断言在本机会话里几乎总是 PASS、在 CI 上偶发 FAIL。单跑一次无法发现，
必须**连续多次**运行才能暴露。

本工具只做一件事：把同一脚本对同一 URL 连续跑 N 次，汇总每次退出码，
只要有任意一次非零退出即判定为不稳定（exit 1）。它不替代门禁，而是给
"这个测试到底稳不稳"这个问题一个可复现的答案。

用法：
    python3 tools/repeat_check.py <script.py> <base_url> [engine] [-n N]
    python3 tools/repeat_check.py tools/verify_modal_scroll.py http://127.0.0.1:8080 firefox -n 6

退出码：全部一致通过 -> 0；出现任一失败 -> 1（便于在 CI 里当门禁）。
"""
import os
import re
import subprocess
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _testlib import EXIT_FAIL, EXIT_PASS, REPO_ROOT  # noqa: E402


def main():
    args = list(sys.argv[1:])
    n = 3
    if "-n" in args:
        i = args.index("-n")
        n = int(args[i + 1])
        del args[i:i + 2]
    if len(args) < 2:
        print(__doc__)
        return EXIT_FAIL

    script, url = args[0], args[1]
    engine = args[2] if len(args) > 2 else "chromium"
    if not os.path.isabs(script):
        script = os.path.join(REPO_ROOT, script)

    cmd = [sys.executable, script, url, engine]
    results = []
    for i in range(n):
        r = subprocess.run(cmd, capture_output=True, text=True)
        line = next((l for l in r.stdout.splitlines() if l.startswith("TEST-RESULT")), "(无 TEST-RESULT)")
        m = re.search(r'"passed":\s*(\d+).*?"failed":\s*(\d+).*?"total":\s*(\d+)', line)
        summary = f"{m.group(1)}/{m.group(3)}" if m else line[:60]
        fails = [l for l in r.stdout.splitlines() if l.startswith("FAIL")]
        print(f"[run {i + 1}/{n}] rc={r.returncode}  {summary}")
        for f in fails:
            print("        ", f)
        if r.returncode != 0 and not m:
            print("        STDERR:", (r.stderr or "").strip()[-300:])
        results.append(r.returncode)

    tally = Counter("PASS" if rc == 0 else "FAIL" for rc in results)
    print(f"\n==== repeat-check: {os.path.basename(script)} [{engine}] "
          f"{n} runs -> {dict(tally)} ====")
    if len(tally) == 1 and tally.get("PASS", 0) == n:
        print("RESULT: STABLE (all passed)")
        return EXIT_PASS
    if tally.get("PASS", 0) and tally.get("FAIL", 0):
        print("RESULT: FLAKY (同一脚本多次运行结果不一致 —— 存在偶发假红/假绿)")
    else:
        print("RESULT: ALWAYS-FAIL (每次都失败)")
    return EXIT_FAIL


if __name__ == "__main__":
    sys.exit(main())