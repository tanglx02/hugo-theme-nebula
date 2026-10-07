#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Nebula 测试脚本公共工具：统一的结果收集与退出码约定。

**所有 tools/*.py 测试脚本必须遵守本约定**（这是 CI 质量门禁可信的前提）：

| 情况                                   | 退出码 |
| -------------------------------------- | ------ |
| 产品问题 / 断言失败 / 检查项不通过      | 1      |
| 测试脚本自身异常                        | 1      |
| 依赖缺失（playwright / pillow 未安装）  | 1      |
| 浏览器无法启动                          | 1      |
| 被审计站点 / 静态服务器不可达            | 1      |
| 一个测试用例都没执行到                   | 1      |
| 全部通过                                | 0      |

最后一个输出行是机器可读结果，便于 CI 与报告解析：

    TEST-RESULT: {"suite": "audit", "status": "PASS", "passed": 7, "failed": 0, "total": 7}

用法：

    from _testlib import Harness, launch, reachable, guard

    def main():
        h = Harness("audit")
        guard(h, lambda: run_checks(h))   # 自动把未捕获异常转成 FAIL
        h.finish()                        # 统一的汇总 + sys.exit

    if __name__ == "__main__":
        main()
"""
from __future__ import annotations

import json
import os
import sys
import traceback
import urllib.request

# 环境里可能存在 HTTP 代理，必须放行本地回环，否则浏览器/urllib 会走代理
os.environ.setdefault("NO_PROXY", "127.0.0.1,localhost")
os.environ.setdefault("no_proxy", "127.0.0.1,localhost")

EXIT_PASS = 0
EXIT_FAIL = 1


def proxy_kwargs():
    """仅本地开发环境需要代理（PLAYWRIGHT_PROXY）；CI 不设置即直连。"""
    srv = os.environ.get("PLAYWRIGHT_PROXY")
    if not srv:
        return {}
    return {"proxy": {"server": srv, "bypass": "127.0.0.1,localhost"}}


def launch(module, **kw):
    """启动浏览器；失败会抛异常，由调用方记录为致命错误（最终 exit 1）。"""
    return module.launch(**proxy_kwargs(), **kw)


def reachable(url, timeout=6):
    """目标站点是否可达。不可达时调用方必须判定为致命错误。"""
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return 200 <= r.status < 400
    except Exception:
        return False


def require_playwright():
    """依赖缺失必须是硬失败，不能静默跳过。"""
    try:
        import playwright  # noqa: F401
    except Exception as e:  # pragma: no cover
        print(f"[FATAL] 缺少依赖 playwright: {e}")
        print("TEST-RESULT: " + json.dumps(
            {"suite": "unknown", "status": "FAIL", "reason": "missing playwright"},
            ensure_ascii=False))
        sys.exit(EXIT_FAIL)


class Harness:
    """结果收集器。finish() 是唯一出口，保证失败一定 exit!=0。"""

    def __init__(self, suite, allow_empty=False):
        self.suite = suite
        # allow_empty=True 仅用于「0 用例也算通过」的极少数场景，测试脚本一律保持 False
        self.allow_empty = allow_empty
        self.records = []   # [(name, ok, detail)]
        self.fatal = []     # [(name, detail)] 环境/脚本层面致命错误

    # ------------------------------------------------------------------ 记录
    def record(self, name, ok, detail=""):
        ok = bool(ok)
        self.records.append((name, ok, str(detail)))
        line = ("PASS  " if ok else "FAIL  ") + name
        if detail != "":
            line += f" :: {detail}"
        print(line)
        return ok

    def fatal_error(self, name, detail=""):
        """脚本自身 / 环境层面的致命错误：即使用例通过，最终也必须 exit 1。"""
        self.fatal.append((name, str(detail)))
        self.record(f"[FATAL] {name}", False, detail)
        return False

    # ------------------------------------------------------------------ 汇总
    @property
    def failed(self):
        return [r for r in self.records if not r[1]]

    @property
    def status(self):
        if self.fatal or self.failed:
            return "FAIL"
        if len(self.records) == 0 and not self.allow_empty:
            return "FAIL"
        return "PASS"

    def finish(self):
        total = len(self.records)
        passed = total - len(self.failed)
        problems = []
        if self.fatal:
            problems.append(f"{len(self.fatal)} 个致命错误：{[f[0] for f in self.fatal]}")
        if total == 0 and not self.allow_empty:
            problems.append("没有执行到任何测试用例（按失败处理，防止假绿）")

        print()
        print(f"==== [{self.suite}] {passed}/{total} PASSED ====")
        if self.failed:
            print("FAILED:")
            for n, _, d in self.failed:
                print("  -", n, "::", d)
        for p in problems:
            print("PROBLEM:", p)
        print("TEST-RESULT: " + json.dumps({
            "suite": self.suite,
            "status": self.status,
            "passed": passed,
            "failed": len(self.failed),
            "total": total,
            "fatal": [f[0] for f in self.fatal],
        }, ensure_ascii=False))
        sys.exit(EXIT_PASS if self.status == "PASS" else EXIT_FAIL)


def guard(harness, fn, *args, **kwargs):
    """执行测试主体；未捕获异常一律转成致命错误（而不是让脚本静默崩掉）。"""
    try:
        return fn(*args, **kwargs)
    except SystemExit:
        raise
    except Exception:
        tb = traceback.format_exc().strip().splitlines()
        harness.fatal_error("脚本异常", tb[-1][:220] if tb else "unknown")
        return None
