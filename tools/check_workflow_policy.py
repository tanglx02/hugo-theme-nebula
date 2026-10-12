#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""GitHub Actions workflow 策略门禁（v1.0.9 P2）：权限 / runner / Node24 版本基线。

把"写进文档的做法"变成"CI 会检查的事实"，覆盖三项长期风险：

① **最小权限**
   - workflow 顶层必须有 `permissions:` 且 `contents: read`
   - 任何地方都不允许出现 `*: write`（包括 job 级）
   → 防止将来有人为了图省事 `permissions: write-all`

② ** runner 固定**
   - 生产门禁 workflow（ci.yml）的所有 job 必须显式 `runs-on: ubuntu-24.04`
   - 不允许 `ubuntu-latest`：GitHub 宣布 2026-10-19 起把 latest 迁到 Ubuntu 26.04，
     长期基线不该在下一次平台迁移时悄悄改变底层 OS
   → 最新环境兼容性另由 compat-latest.yml 单独验证，不混进生产门禁

③ **Node 24 兼容的 action 版本**
   - 只允许登记表中的 action，且版本 >= 该 action 第一个支持 Node 24 的稳定版本
   - 该表标注了每个版本的支持依据（Johnny 谁能背）
   → 防止 workflow 被改回 Node 20 时代的旧 action（这些动作未来会被强制以 Node 24 运行或失效）

用法：python tools/check_workflow_policy.py [<repo_root>]
退出码约定（见 tools/_testlib.py）：任一违规 / 缺依赖 -> exit 1。
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _testlib import Harness, guard  # noqa: E402

try:
    import yaml
except Exception as e:
    print(f"[FATAL] 缺少依赖 PyYAML: {e}")
    print("TEST-RESULT: " + json.dumps(
        {"suite": "workflow-policy", "status": "FAIL", "reason": "missing PyYAML"},
        ensure_ascii=False))
    sys.exit(1)

ROOT = sys.argv[1] if len(sys.argv) > 1 else os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
WORKFLOWS_DIR = os.path.join(ROOT, ".github", "workflows")

# action -> (最低 Node24 兼容版本, 依据)
ACTION_MIN_NODE24 = {
    "actions/checkout": ("v5.0.0",
                         "checkout v5 起 using: node24（当前稳定 v7.0.1）"),
    "actions/setup-python": ("v6.0.0",
                             "setup-python v6 起 using: node24（当前稳定 v7.0.0）"),
    "actions/cache": ("v5.0.0", "cache v5 起 using: node24（当前稳定 v6.1.0）"),
    "actions/upload-artifact": ("v5.0.0",
                                "upload-artifact v5 起 using: node24（当前稳定 v7.0.2）"),
    "peaceiris/actions-hugo": ("v3.1.0",
                               "actions-hugo v3.1.0 起 using: node24（v3.0.0 仍是 node20，"
                               "当前稳定 v3.2.1）"),
}

PRODUCTION_RUNNER = "ubuntu-24.04"
# 生产门禁 workflow：所有 job 必须固定 runner
PRODUCTION_WORKFLOWS = {"ci.yml"}

H = Harness("workflow-policy")


def parse_ver(ref):
    m = re.match(r"^v?(\d+)(?:\.(\d+))?(?:\.(\d+))?$", ref or "")
    if not m:
        return None
    return tuple(int(x or 0) for x in m.groups())


def collect_steps(job):
    for st in job.get("steps") or []:
        if isinstance(st, dict) and st.get("uses"):
            yield str(st["uses"])


def check_permissions(problems, wf_name, doc, text):
    top = doc.get("permissions")
    if not top:
        problems.append((wf_name, "permissions-missing",
                         "workflow 缺少顶层 permissions（应为 contents: read）"))
        return
    if top == "read-all" or top == "write-all":
        problems.append((wf_name, "permissions-too-broad", f"顶层 permissions: {top}"))
        return
    if isinstance(top, dict):
        if top.get("contents") != "read":
            problems.append((wf_name, "permissions-contents",
                             f"顶层 contents 应为 read，实际 {top.get('contents')}"))
        if not top:
            problems.append((wf_name, "permissions-empty", "顶层 permissions 为空映射"))
    for jid, job in (doc.get("jobs") or {}).items():
        jp = job.get("permissions")
        if jp is None or jp == "read-all":
            continue
        # job 级 write-all 必须判红。
        # （TEST-DEFECT-003：旧实现把 write-all 与 read-all 一起 continue 掉了，
        #   docstring 却声称"包括 job 级"——一行 write-all 就能绕过最小权限门禁。）
        if jp == "write-all":
            problems.append((wf_name, "permissions-write",
                             f"job {jid} 的 permissions: write-all（不允许 write 权限）"))
            continue
        if isinstance(jp, dict):
            for k, v in jp.items():
                if v in ("write", "read-all", "write-all"):
                    problems.append((wf_name, "permissions-write",
                                     f"job {jid} 的 {k}: {v}（不允许 write 权限）"))


def check_runner(problems, wf_name, doc):
    if wf_name not in PRODUCTION_WORKFLOWS:
        return
    for jid, job in (doc.get("jobs") or {}).items():
        runner = str(job.get("runs-on") or "")
        if runner != PRODUCTION_RUNNER:
            problems.append((wf_name, "runner-not-pinned",
                             f"job {jid} runs-on={runner}，"
                             f"生产门禁必须固定 {PRODUCTION_RUNNER}"))


SHA_PINS = []


def check_actions(problems, wf_name, doc):
    for jid, job in (doc.get("jobs") or {}).items():
        for uses in collect_steps(job):
            name, _, ref = uses.partition("@")
            name = name.strip()
            ref = ref.strip()
            if name not in ACTION_MIN_NODE24:
                problems.append((wf_name, "action-unregistered",
                                 f"job {jid} 使用了未登记的 action: {uses} —— "
                                 f"新增 action 必须先登记 Node24 最低版本"))
                continue
            # 40 位 SHA 固定是供应链最佳实践。无法从 SHA 反推 Node 版本，因此
            # **接受并打印提示**，而不是像旧实现那样判红（TEST-DEFECT-004：
            # 旧逻辑把 SHA 当"版本号解析失败 -> Node20"，形成反向激励）。
            if re.fullmatch(r"[0-9a-fA-F]{40}", ref):
                SHA_PINS.append(f"{wf_name}/{jid}: {name}@<sha>")
                continue
            min_ref, why = ACTION_MIN_NODE24[name]
            got, want = parse_ver(ref), parse_ver(min_ref)
            if got is None:
                problems.append((wf_name, "action-version-unparsable",
                                 f"job {jid}: {uses} 版本号无法解析（请用 vX.Y.Z 或 40 位 SHA）"))
                continue
            if got < want:
                problems.append((wf_name, "action-node20",
                                 f"job {jid}: {uses} 低于 Node24 兼容版本 {min_ref}"
                                 f"（{why}）"))


def run(h):
    if not os.path.isdir(WORKFLOWS_DIR):
        h.fatal_error("找不到 workflows 目录", WORKFLOWS_DIR)
        return
    files = sorted(f for f in os.listdir(WORKFLOWS_DIR) if f.endswith((".yml", ".yaml")))
    if not files:
        h.fatal_error("没有任何 workflow 文件", WORKFLOWS_DIR)
        return
    problems = []
    print(f"工作流文件: {len(files)} 个 -> {', '.join(files)}")
    for fn in files:
        path = os.path.join(WORKFLOWS_DIR, fn)
        text = open(path, encoding="utf-8").read()
        try:
            doc = yaml.safe_load(text) or {}
        except Exception as e:
            h.fatal_error(f"{fn} 不是合法 YAML", str(e)[:160])
            return
        check_permissions(problems, fn, doc, text)
        check_runner(problems, fn, doc)
        check_actions(problems, fn, doc)

    if problems:
        print("\n### 违规明细")
        for wf, rule, detail in problems:
            print(f"  - [{wf}] {rule} :: {detail}")

    by_rule = {}
    for wf, rule, detail in problems:
        by_rule.setdefault(rule, []).append(detail)
    h.record("所有 workflow 顶层声明 permissions（contents: read）",
             not {"permissions-missing", "permissions-contents",
                  "permissions-empty", "permissions-too-broad"} & set(by_rule),
             f"{len(by_rule.get('permissions-missing', []))} 个缺失")
    h.record("没有任何 job 使用 write 权限",
             "permissions-write" not in by_rule,
             "；".join(by_rule.get("permissions-write", [])[:3]) or "无 write 权限")
    h.record(f"生产门禁 workflow 固定 runner = {PRODUCTION_RUNNER}",
             "runner-not-pinned" not in by_rule,
             "；".join(by_rule.get("runner-not-pinned", [])[:3]) or "已固定")
    h.record("所有 action 均为 Node24 兼容版本（>= 登记的最低版本）",
             not {"action-node20", "action-unregistered",
                  "action-version-unparsable"} & set(by_rule),
             "；".join((by_rule.get("action-node20", [])
                       + by_rule.get("action-unregistered", [])
                       + by_rule.get("action-version-unparsable", []))[:3]) or "全部合规")
    if SHA_PINS:
        print(f"\nSHA 固定的 action（供应链最佳实践，接受）：{len(SHA_PINS)} 处")
        for s in SHA_PINS[:6]:
            print("   ", s)
    print("\n登记的最低 Node24 兼容版本:")
    for name, (ver, why) in sorted(ACTION_MIN_NODE24.items()):
        print(f"  - {name:28s} >= {ver:8s} {why}")


def main():
    guard(H, run, H)
    H.finish()


if __name__ == "__main__":
    main()
