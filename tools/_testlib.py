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
import shutil
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


# ---------------------------------------------------------------------------
# 默认构建目录：统一基准（TEST-DEFECT-016 / TEST-DEFECT-R2-003）
# ---------------------------------------------------------------------------
def default_build_dir(argv=None):
    """解析"构建产物目录"参数的统一入口。

    为什么需要它：此前各脚本默认路径不一致 —— `check_index` / `check_seo` /
    `check_features` 用 `<repo>/public`，而 `check_html_quality` /
    `security_baseline` / `html_inventory` / `check_alias_pages` 用 **cwd 相对**
    的 `public`。于是同一份产物，从仓库根运行与从 tools/ 运行得到不同结论，
    手工复核结果不可比，也容易在 CI 外误判。

    约定：
      * 显式传参 -> 用传参（相对路径按 cwd 解析，符合直觉）；
      * 未传参   -> 用 `<repo>/public`（与实际 `hugo -d public` 输出一致）；
      * `-h/--help` -> 打印用法后 exit 0（不再被当成路径处理，
        旧实现会把 `--help` 当目录名，报"目录不存在"）。
    """
    args = list(sys.argv[1:] if argv is None else argv)
    if any(a in ("-h", "--help") for a in args):
        print("用法: python tools/<script>.py [构建目录]   "
              "（缺省 <repo>/public；-h/--help 显示本帮助）")
        sys.exit(EXIT_PASS)
    for a in args:
        if not a.startswith("-"):
            return os.path.abspath(a)
    return os.path.join(REPO_ROOT, "public")


# ---------------------------------------------------------------------------
# 临时产物：安全路径与"每次运行都从空目录开始"的隔离语义
# ---------------------------------------------------------------------------
REPO_ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
TMP_ROOT = os.path.join(REPO_ROOT, "tmp")


def safe_rmtree(path, boundary=TMP_ROOT):
    """受边界约束的递归删除 —— 只允许删除 boundary 之下的路径。

    为什么必须有这个约束（TEST-DEFECT-R2-004 / R2-006）：
      测试脚本要"每次构建前清空产物目录"，如果直接对从环境变量/argv 拼出来的
      路径调用 shutil.rmtree，一旦传进来的是 `/`、仓库根、或用户的 home，
      就是一次不可逆的灾难。这里强制：规范化后的绝对路径必须**真在** boundary
      之下（且不等于 boundary 本身），否则拒绝并抛错。

    返回 True 表示已删除/不存在；越界抛 ValueError。
    """
    if not path:
        return True
    target = os.path.normpath(os.path.abspath(path))
    root = os.path.normpath(os.path.abspath(boundary))
    if target == root or not target.startswith(root + os.sep):
        raise ValueError(
            f"拒绝删除越界路径: {target}（必须位于 {root} 之内，且不等于它自身）")
    if os.path.exists(target):
        shutil.rmtree(target, ignore_errors=True)
    return True


def fresh_dir(path, boundary=TMP_ROOT):
    """删除并重建目录：保证每次运行都从**空目录**开始，绝不复用上次残留。

    TEST-DEFECT-R2-006 的根因就是复用 `tmp/public-blog` 却不清理：
    删掉源文章后旧 HTML 仍在，测试照样 10/10 假绿。
    """
    safe_rmtree(path, boundary=boundary)
    os.makedirs(path, exist_ok=True)
    return path


class TempWorkspace:
    """带唯一 run-id 的临时目录，支持 `with` 保证成功/失败/异常都清理。

    与 `.gitignore` 的分工必须清楚：`.gitignore` 只影响 git 是否上报，**不能**
    阻止残留文件污染下一次运行、更不能阻止旧的产物被当成新的构建结果复用。
    真正的隔离只能靠运行期：唯一目录 + 前置清空 + finally 清理。

    用法：
        with TempWorkspace("deploy") as ws:
            out = ws.path("root")
    """

    def __init__(self, prefix, keep=False, boundary=TMP_ROOT):
        self.prefix = prefix
        self.keep = keep or os.environ.get("KEEP_TMP", "") not in ("", "0", "false", "False")
        self.boundary = boundary
        self.path_root = None

    def __enter__(self):
        os.makedirs(self.boundary, exist_ok=True)
        self.path_root = os.path.join(
            self.boundary, f"{self.prefix}-{os.getpid()}-{int(_unique_suffix())}")
        safe_rmtree(self.path_root, boundary=self.boundary)   # 防 run-id 碰撞
        os.makedirs(self.path_root, exist_ok=True)
        return self

    def path(self, *parts):
        return os.path.join(self.path_root, *parts)

    def __exit__(self, exc_type, exc, tb):
        if self.keep:
            print(f"[KEEP_TMP] 保留临时目录以便排查: {self.path_root}")
            return False
        try:
            safe_rmtree(self.path_root, boundary=self.boundary)
        except Exception as e:      # pragma: no cover
            print(f"[WARN] 临时目录清理失败 {self.path_root}: {e}")
        return False


def _unique_suffix():
    import random
    import time
    return f"{time.time_ns()}{random.randint(0, 9999):04d}"


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
