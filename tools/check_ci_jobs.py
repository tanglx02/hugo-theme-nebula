#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CI job inventory：把 GitHub Actions 的 job 数量从"手写数字"变成**可校验事实**。

背景
----
v1.0.8 及之前的验收报告一直写"CI 13/13 全绿"，但 matrix 展开后实际只有 12 个 job
（build 4 + subdir 1 + static-checks 1 + browser-tests 3 + release-full-audit 3）。
数字一旦手写，改动 matrix 后必然再次写错 —— 而且错了没人发现。

约定
----
`.github/workflows/ci.yml` 里用注释显式登记每个 job 的展开数量：

    # CI-JOBS: build=4
    # CI-JOBS: subdir=1
    # CI-JOBS: static-checks=1
    # CI-JOBS: browser-tests=3
    # CI-JOBS: release-full-audit=3
    # CI-JOBS-TOTAL: 12
    # CI-JOBS-PUSH-TOTAL: 9      （非 tag 推送，Release job 被 if 跳过）

本脚本按 GitHub 的 matrix 展开规则（`include` 合并 `exclude` 剔除）自己算出每个
job 的实际 job 数，再与注释登记值比对：

    * 改了 matrix（例如加一个浏览器）却没更新注释  -> FAIL
    * 注释随手编的数字与 YAML 不符                -> FAIL
    * 两类数字一致                                 -> PASS

用法：
    python tools/check_ci_jobs.py                 # 校验数量
    python tools/check_ci_jobs.py --print         # 只打印清单
环境变量 CI_REPORT = 1 时额外输出机器可读的一行摘要（供最终报告引用）。

退出码约定（见 tools/_testlib.py）：不一致 / 缺注释 / 缺依赖 -> exit 1。
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _testlib import Harness, guard  # noqa: E402

try:
    import yaml
except Exception as e:      # 依赖缺失必须是硬失败
    print(f"[FATAL] 缺少依赖 PyYAML: {e}")
    print("TEST-RESULT: " + json.dumps(
        {"suite": "ci-jobs", "status": "FAIL", "reason": "missing PyYAML"},
        ensure_ascii=False))
    sys.exit(1)

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
WORKFLOW = os.path.join(ROOT, ".github", "workflows", "ci.yml")

# 注释行后面允许跟说明文字（如 "9  （非 tag 推送）"），只取第一个整数
DECL_RE = re.compile(r"^\s*#\s*CI-JOBS:\s*([A-Za-z0-9_-]+)\s*=\s*(\d+)")
TOTAL_RE = re.compile(r"^\s*#\s*CI-JOBS-TOTAL:\s*(\d+)")
PUSH_TOTAL_RE = re.compile(r"^\s*#\s*CI-JOBS-PUSH-TOTAL:\s*(\d+)")

H = Harness("ci-jobs")


def expand_job(job):
    """按 GitHub 语义展开一个 job 的所有 matrix 组合，返回 [(name, combo)]。"""
    strat = job.get("strategy") or {}
    matrix = strat.get("matrix") or {}
    keys = [k for k, v in matrix.items()
            if k not in ("include", "exclude") and isinstance(v, list)]
    if not keys:
        return [(job.get("name") or "job", {})]
    combos = [{}]
    for k in keys:
        combos = [dict(c, **{k: v}) for c in combos for v in matrix[k]]
    for inc in matrix.get("include") or []:
        shared = {k: v for k, v in inc.items() if k in keys}
        hit = False
        for c in combos:
            if all(c.get(k) == v for k, v in shared.items()):
                c.update(inc)
                hit = True
        if not hit:
            combos.append(dict(inc))
    for exc in matrix.get("exclude") or []:
        combos = [c for c in combos
                  if not all(c.get(k) == v for k, v in exc.items())]
    out = []
    for c in combos:
        label = str(job.get("name") or "job")
        for k in keys:
            label = label.replace("${{ matrix." + k + " }}", str(c.get(k)))
        out.append((label, c))
    return out


def is_tag_only(job):
    """job 是否仅 tag 推送时执行（非 tag 推送会被 skip）。"""
    cond = str(job.get("if") or "")
    return "refs/tags/v" in cond


def read_declarations(text):
    declared = {}
    total = push_total = None
    for line in text.splitlines():
        m = DECL_RE.match(line)
        if m:
            declared[m.group(1)] = int(m.group(2))
            continue
        m = TOTAL_RE.match(line)
        if m:
            total = int(m.group(1))
            continue
        m = PUSH_TOTAL_RE.match(line)
        if m:
            push_total = int(m.group(1))
    return declared, total, push_total


def run(h):
    if not os.path.isfile(WORKFLOW):
        h.fatal_error("找不到 workflow 文件", WORKFLOW)
        return
    text = open(WORKFLOW, encoding="utf-8").read()
    doc = yaml.safe_load(text)
    jobs = (doc or {}).get("jobs") or {}
    if not jobs:
        h.fatal_error("workflow 没有定义任何 job", WORKFLOW)
        return

    computed, computed_push = {}, {}
    print("=== CI job inventory（matrix 展开后）===")
    for jid, job in jobs.items():
        combos = expand_job(job)
        computed[jid] = len(combos)
        computed_push[jid] = 0 if is_tag_only(job) else len(combos)
        tag_only = "（仅 tag）" if is_tag_only(job) else ""
        print(f"  - {jid:20s} {len(combos):2d} 个 job{tag_only}"
              f"  runs-on={job.get('runs-on')}")
        if len(combos) > 1:
            for label, c in combos:
                keys = sorted(k for k in c if k not in ("viewports",))
                print(f"      - {label}: "
                      f"{', '.join(f'{k}={c[k]}' for k in keys)}")

    declared, total, push_total = read_declarations(text)
    H_total = sum(computed.values())
    H_push = sum(computed_push.values())
    print(f"\nExpected round-trip: 注释声明 TOTAL={total}, 实际展开={H_total}")
    print(f"非 tag 推送: 声明={push_total}, 实际={H_push}"
          f"（Release job 被 if 跳过）")

    if not declared or total is None:
        h.fatal_error("workflow 缺少 CI-JOBS 清单注释",
                      "请在 ci.yml 中按 '# CI-JOBS: <job>=<n>' 与 "
                      "'# CI-JOBS-TOTAL: <n>' 登记，禁止在文档里手写 job 数")
        return

    missing = sorted(set(computed) - set(declared))
    h.record("每个 job 都在注释里登记了展开数量",
             not missing, f"未登记: {missing}")

    mismatch = []
    for jid in sorted(computed):
        if jid in declared and declared[jid] != computed[jid]:
            mismatch.append(f"{jid}: 注释 {declared[jid]} != 实际 {computed[jid]}")
    h.record("注释登记的 job 数与 YAML matrix 展开结果一致",
             not mismatch, "；".join(mismatch) if mismatch
             else f"{len(declared)} 个 job 全部一致")

    h.record("CI-JOBS-TOTAL 与实际 job 总数一致",
             total == H_total, f"注释 {total} / 实际 {H_total}")
    h.record("CI-JOBS-PUSH-TOTAL 与非 tag 推送的 job 数一致",
             push_total == H_push, f"注释 {push_total} / 实际 {H_push}")

    if os.environ.get("CI_REPORT") == "1":
        print("CI-JOB-SUMMARY: " + json.dumps({
            "workflow": "ci.yml",
            "jobs_total": H_total,
            "jobs_push_no_tag": H_push,
            "per_job": computed,
            "declared_total": total,
            "declared_push_total": push_total,
        }, ensure_ascii=False))


def main():
    guard(H, run, H)
    H.finish()


if __name__ == "__main__":
    main()
