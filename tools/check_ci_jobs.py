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
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _testlib import (  # noqa: E402
    EXIT_FAIL, EXIT_PASS, Harness, TempWorkspace, guard,
)

try:
    import yaml
except Exception as e:      # 依赖缺失必须是硬失败
    print(f"[FATAL] 缺少依赖 PyYAML: {e}")
    print("TEST-RESULT: " + json.dumps(
        {"suite": "ci-jobs", "status": "FAIL", "reason": "missing PyYAML"},
        ensure_ascii=False))
    sys.exit(1)

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
# 允许用 CI_WORKFLOW 指向隔离副本 —— 供故障注入测试在不改动真实 workflow 的前提下
# 验证门禁确实会变红（TEST-DEFECT-R2-002）。
WORKFLOW = os.environ.get("CI_WORKFLOW") or os.path.join(ROOT, ".github", "workflows", "ci.yml")

# ---- 结构契约（TEST-DEFECT-015）----
# 只比数量的门禁有两个漏洞：① 注释与 workflow 同文件，自指（改数量+改注释即通过）；
# ② job 改名 / 删掉某个门禁、或 matrix 取值被换掉（chromium -> edge）时数量不变，检测不到。
# 因此这里把"必须存在的 job"与"必须出现的 matrix 取值"也固定下来。
# 改动这些结构时，必须**同时**改这里与 workflow 注释 —— 这是有意的双向登记。
REQUIRED_JOBS = ("build", "subdir", "static-checks", "browser-tests", "release-full-audit")
REQUIRED_MATRIX = {
    "build": {"hugo-version": {"0.128.0", "0.148.0", "0.162.0", "0.166.0", "0.167.0", "latest"}},
    "browser-tests": {"browser": {"chromium", "firefox", "webkit"}},
    "release-full-audit": {"browser": {"chromium", "firefox", "webkit"}},
}

# ---- 关键步骤 / 关键命令契约（TEST-DEFECT-R2-002）----
# 只校验数量、job 名与 matrix 取值，对"覆盖静默消失"几乎不敏感：
#   * 删除某个关键步骤        -> 数量/名称都不变 -> 旧实现漏检
#   * step `if: false` / `&& false` -> 步骤永不执行 -> 漏检
#   * `continue-on-error: true` -> 步骤失败也不影响 job -> 漏检
#   * `run:` 换成 `echo skipped` 这类空命令 -> 漏检
# 这里把"每个关键 job 必须真正执行的命令 / 步骤"固定下来：token 只要从全部步骤的
# 名称与 run 命令里消失，就判红。因此删除步骤、改空命令都会命中。
REQUIRED_STEP_TOKENS = {
    "build": [
        "gen_testdata.py",
        "hugo --source exampleSite",
        "Check boundary fixtures",
        "check_index.py",
        "check_search_modes.py",
        "draft",
        "livereload",
    ],
    "static-checks": [
        "link_check.py", "check_index.py", "check_features.py",
        "check_i18n_hardcode.py", "verify_i18n.py", "verify_multisection.py",
        "html_inventory.py", "check_alias_pages.py", "check_search_date.py",
        "check_article_classification.py",
        "check_ci_jobs.py",              # 自指：删除本门禁自身会立即判红
        "check_workflow_policy.py", "check_docs.py", "check_date_format.py",
        "check_html_quality.py", "security_baseline.py",
        "test_pagination_retry.py", "test_inventory.py", "check_seo.py",
        "check_comments.py", "check_pagination.py", "verify_multilingual.py",
        # 功能一 / 二 / 三·四·五 的产物门禁：删除或改空命令即判红。
        # 末尾的 --selftest 单独登记，保证"故障注入自证"本身不能被悄悄摘掉。
        "check_home_layouts.py", "check_reading_experience.py",
        "check_new_features.py public", "check_new_features.py --selftest",
    ],
    "browser-tests": [
        "audit.py", "interactions.py", "verify_copy.py", "verify_lightbox.py",
        "verify_search_modal.py", "verify_modal_scroll.py",
        "verify_search_edge.py", "verify_search_highlight.py",
        "verify_search_shard.py", "verify_baseurl.py",
        "verify_contrast.py", "check_responsive_overflow.py",
    ],
    "release-full-audit": [
        "gen_testdata.py", "hugo --source exampleSite", "link_check.py",
        "html_inventory.py", "check_html_quality.py", "check_alias_pages.py",
        "AUDIT_FULL", "verify_copy.py", "interactions.py",
    ],
}

# 必须运行在**所有**浏览器引擎上的检查（TEST-DEFECT-R2-020 / R2-002）：
# 这些步骤涉及真实浏览器差异（搜索交互与竞态 / 键盘 / XSS 渲染安全 / 日期 i18n /
# 高亮特殊字符 / 分片失败语义 / baseURL 部署 / 对比度 / 响应式断点），
# 因此不得再被 `if: matrix.browser == 'chromium'` 单引擎门控。
THREE_ENGINE_TOKENS = {
    "verify_search_edge.py", "verify_search_highlight.py", "verify_search_shard.py",
    "verify_baseurl.py", "verify_contrast.py", "check_responsive_overflow.py",
}
# 仅 tag 推送才执行的 job（Release 门禁）：if 必须显式以 refs/tags/v 为条件
TAG_GATED_JOBS = ("release-full-audit",)
TAG_COND_RE = re.compile(r"startsWith\s*\(\s*github\.ref\s*,\s*['\"]refs/tags/v['\"]\s*\)")

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
    """job 是否仅 tag 推送时执行（非 tag 推送会被 skip）。

    TEST-DEFECT-015：旧实现用 `"refs/tags/v" in cond` 子串判断，条件被改写或删掉
    也可能命中/漏判。这里改为严格匹配 startsWith(github.ref, 'refs/tags/v')。
    """
    cond = str(job.get("if") or "")
    return TAG_COND_RE.search(cond) is not None


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

    # ---- 结构契约：job 集合 / matrix 取值 / tag 门控（TEST-DEFECT-015）----
    absent = [j for j in REQUIRED_JOBS if j not in jobs]
    h.record("必需 job 全部存在（防止改名或删除门禁后数量不变而漏检）",
             not absent, f"缺失: {absent}" if absent else f"{list(REQUIRED_JOBS)} 均在")

    matrix_bad = []
    for jid, spec in REQUIRED_MATRIX.items():
        job = jobs.get(jid) or {}
        matrix = ((job.get("strategy") or {}).get("matrix") or {})
        for key, want in spec.items():
            got = set(matrix.get(key) or [])
            if got != want:
                matrix_bad.append(f"{jid}.{key}: 实际 {sorted(got)} != 期望 {sorted(want)}")
    h.record("关键 matrix 取值未被替换（如浏览器/ Hugo 版本）",
             not matrix_bad, "；".join(matrix_bad) if matrix_bad else "全部匹配")

    gate_bad = []
    for jid in TAG_GATED_JOBS:
        job = jobs.get(jid) or {}
        if not TAG_COND_RE.search(str(job.get("if") or "")):
            gate_bad.append(f"{jid} 未以 refs/tags/v 为执行条件")
    h.record("Release 门禁仍然只在 tag 推送时执行（未被静默关闭）",
             not gate_bad, "；".join(gate_bad) if gate_bad else f"{list(TAG_GATED_JOBS)} 均可疑条件通过")

    # ---- job 级恒假条件：把关键 job 用 `if: false` 关掉，job 数量与名称都不变 ----
    # TEST-DEFECT-R2-002：旧实现只检测 **step** 级恒假，给整个 `browser-tests`/`build`
    # job 加 `if: false`（或 `... && false`）会让所有浏览器/构建检查永不执行，
    # 却完全检测不到。这里要求：**非 tag 门控**的必需 job 不得带恒假条件。
    job_dead = []
    for jid in REQUIRED_JOBS:
        if jid in TAG_GATED_JOBS:
            continue        # tag 门控 job 的 if 由上一条专门校验
        raw = (jobs.get(jid) or {}).get("if")
        if raw is None:
            continue
        if isinstance(raw, bool):
            cond = "false" if raw is False else "true"
        else:
            cond = str(raw).strip().lower()
        if cond in ("false", "${{ false }}") or re.search(r"&&\s*false", cond):
            job_dead.append(f"{jid}: if 恒假（整个 job 永不执行）")
    h.record("必需 job 没有被 job 级恒假条件整体关停",
             not job_dead, "；".join(job_dead) if job_dead else "无恒假 job 条件")

    # ---- matrix 条件步骤：`if: matrix.<key> == '<value>'` 的取值必须在 matrix 里真实存在 ----
    # TEST-DEFECT-020：chromium 专属步骤若改成不存在的取值，会**永远不执行**且无任何报错。
    cond_re = re.compile(r"matrix\.([A-Za-z0-9_]+)\s*==\s*['\"]([^'\"]+)['\"]")
    cond_bad, cond_ok = [], 0
    for jid, job in jobs.items():
        matrix = ((job.get("strategy") or {}).get("matrix") or {})
        for st in (job.get("steps") or []):
            if not isinstance(st, dict):
                continue
            for m in cond_re.finditer(str(st.get("if") or "")):
                key, val = m.group(1), m.group(2)
                allowed = set(matrix.get(key) or [])
                if not allowed:
                    continue        # 不是 matrix 条件（如 env 变量），跳过
                if val in allowed:
                    cond_ok += 1
                else:
                    cond_bad.append(f"job {jid}: step 条件 matrix.{key}=='{val}' "
                                    f"不在 {sorted(allowed)} 中（该步骤永远不会执行）")
    if cond_ok or cond_bad:
        h.record("matrix 条件步骤的取值真实存在（不会静默不执行）",
                 not cond_bad, "；".join(cond_bad[:3]) if cond_bad
                 else f"{cond_ok} 个 matrix 条件步骤取值均有效")

    # ---- 关键步骤 / 关键命令契约（TEST-DEFECT-R2-002）----
    def step_blob(job):
        """一个 job 全部步骤的可见文本（name + run + uses + env + if 值）。"""
        parts = []
        for st in (job.get("steps") or []):
            if not isinstance(st, dict):
                parts.append(str(st))
                continue
            for k in ("name", "run", "uses", "if", "with"):
                parts.append(json.dumps(st.get(k), ensure_ascii=False))
        return "\n".join(parts)

    token_missing = []
    for jid, toks in REQUIRED_STEP_TOKENS.items():
        blob = step_blob(jobs.get(jid) or {})
        for t in toks:
            if t not in blob:
                token_missing.append(f"{jid}: 缺少关键步骤/命令 '{t}'")
    h.record("每个关键 job 的关键步骤与命令仍然存在（删除/清空步骤即判红）",
             not token_missing, "；".join(token_missing[:5]) if token_missing
             else f"{sum(len(v) for v in REQUIRED_STEP_TOKENS.values())} 个关键命令全部存在")

    # job 级 continue-on-error：会掩盖整个 job 的失败
    coe_jobs = [jid for jid, j in jobs.items() if j.get("continue-on-error") is True]
    # step 级 continue-on-error：会掩盖关键步骤的失败
    coe_steps = []
    for jid, job in jobs.items():
        for st in (job.get("steps") or []):
            if isinstance(st, dict) and st.get("continue-on-error") is True:
                coe_steps.append(f"{jid}/{st.get('name') or st.get('uses') or st.get('run', '')[:30]}")
    h.record("没有 job 级 continue-on-error 掩盖失败",
             not coe_jobs, f"发现: {coe_jobs}")
    h.record("没有 step 级 continue-on-error 掩盖关键步骤失败",
             not coe_steps, "；".join(coe_steps[:5]) if coe_steps else "无")

    # 步骤条件被写成恒假（if: false / ... && false / 空 run）
    dead_steps = []
    for jid, job in jobs.items():
        for st in (job.get("steps") or []):
            if not isinstance(st, dict):
                continue
            raw_cond = st.get("if")
            # 注意：YAML 会把 `if: false` 解析成布尔 False，不能写成 `raw_cond or ""`
            # （False 是 falsy，会被误判成"无条件"从而漏检）。
            if raw_cond is None:
                cond = ""
            elif isinstance(raw_cond, bool):
                cond = "false" if raw_cond is False else "true"
            else:
                cond = str(raw_cond).strip().lower()
            label = st.get("name") or st.get("uses") or (st.get("run") or "")[:40]
            if cond in ("false", "${{ false }}") or re.search(r"&&\s*false", cond):
                dead_steps.append(f"{jid}/{label}: if 恒假（步骤永不执行）")
            # run 步骤被换成明显空转命令
            run = str(st.get("run") or "").strip()
            if st.get("run") is not None and run and re.fullmatch(r"(echo\s+.*|true|:)", run):
                dead_steps.append(f"{jid}/{label}: run 为空转命令 → '{run[:40]}'")
    h.record("没有步骤被写成恒假条件或被替换为空转命令",
             not dead_steps, "；".join(dead_steps[:5]) if dead_steps else "无")

    # ---- 三引擎覆盖（TEST-DEFECT-R2-002 / 020）----
    # 对涉及浏览器差异的检查：承载该命令的步骤不得再被单引擎条件门控。
    single_engine = []
    for jid, job in jobs.items():
        for st in (job.get("steps") or []):
            if not isinstance(st, dict):
                continue
            run = str(st.get("run") or "")
            cond = str(st.get("if") or "")
            for tok in THREE_ENGINE_TOKENS:
                if tok in run:
                    m = re.search(r"matrix\.browser\s*==\s*['\"]([^'\"]+)['\"]", cond)
                    if m:
                        single_engine.append(f"{jid}/{tok}: 被 matrix.browser=='{m.group(1)}' 单引擎门控")
    h.record("浏览器差异检查运行在三引擎上（不再单引擎门控）",
             not single_engine, "；".join(single_engine[:5]) if single_engine else "全部三引擎")

    if os.environ.get("CI_REPORT") == "1":
        print("CI-JOB-SUMMARY: " + json.dumps({
            "workflow": "ci.yml",
            "jobs_total": H_total,
            "jobs_push_no_tag": H_push,
            "per_job": computed,
            "declared_total": total,
            "declared_push_total": push_total,
        }, ensure_ascii=False))


def _mutate(text, kind):
    """对 workflow 文本施加一类故障注入，返回改后的文本。

    每类注入都对应一种"覆盖静默消失"的真实风险；若门禁无感知，就是假绿。
    """
    if kind == "delete-step":
        # 删除一条关键步骤（整行 + 其后的 run 块）：数量/名称/matrix 都不变
        for tok in ("check_index.py public/index.json public", "link_check.py public"):
            idx = text.find(tok)
            if idx >= 0:
                start = text.rfind("\n      - ", 0, idx)
                end = text.find("\n      - ", idx + len(tok))
                if end < 0:
                    end = len(text)
                return text[:start] + text[end:]
        raise RuntimeError("注入点未找到: delete-step")
    if kind == "step-if-false":
        # 给一个关键步骤加 if: false（永不执行）
        for tok in ("python3 tools/link_check.py public",):
            idx = text.find(tok)
            start = text.rfind("\n      - ", 0, idx)
            return text[:start] + "\n        if: false" + text[start:]
        raise RuntimeError("注入点未找到: step-if-false")
    if kind == "job-if-false":
        # 给 browser-tests 整个 job 加 if: false
        idx = text.find("  browser-tests:\n")
        end = text.find("\n    steps:", idx)
        return text[:end] + "\n    if: false" + text[end:]
    if kind == "continue-on-error":
        # 给一个关键步骤加 continue-on-error: true
        idx = text.find("python3 tools/link_check.py public")
        start = text.rfind("\n      - ", 0, idx)
        return text[:start] + "\n        continue-on-error: true" + text[start:]
    if kind == "echo-skipped":
        # 把 run 命令替换为空转命令
        return text.replace("python3 tools/link_check.py public", "echo skipped")
    if kind == "single-engine":
        # 给三引擎检查加单引擎门控
        return text.replace(
            "- name: Three baseURL deployments (/, /blog/, /blog/sub/)",
            "- name: Three baseURL deployments (/, /blog/, /blog/sub/)\n"
            "        if: matrix.browser == 'chromium'")
    if kind == "swap-matrix-value":
        # 换掉 matrix 取值（chromium -> edge）：数量不变、结构契约必须命中
        return text.replace("browser: [chromium, firefox, webkit]",
                            "browser: [edge, firefox, webkit]")
    raise RuntimeError(f"未知注入类型: {kind}")


def selftest():
    """故障注入自证：证明**关键检查在故障时确实失败**（TEST-DEFECT-R2-002）。

    做法：把真实 workflow 复制到隔离临时目录，逐类注入故障后调用自身（通过
    CI_WORKFLOW 指向副本），要求子进程 **非零退出**；全部注入都变红才算自证成功。
    这直接回应"不得删断言/扩白名单/关检查/只改期望值" —— 是门禁本体的负向证据。
    """
    src = os.path.join(ROOT, ".github", "workflows", "ci.yml")
    if not os.path.isfile(src):
        print(f"[FATAL] 找不到 workflow: {src}")
        sys.exit(EXIT_FAIL)
    base = open(src, encoding="utf-8").read()

    injections = [
        ("delete-step", "删除关键步骤（link_check / check_index）"),
        ("step-if-false", "关键步骤 if: false"),
        ("job-if-false", "browser-tests job if: false"),
        ("continue-on-error", "关键步骤 continue-on-error: true"),
        ("echo-skipped", "关键命令替换为 echo skipped"),
        ("single-engine", "三引擎检查被单引擎门控"),
        ("swap-matrix-value", "matrix 浏览器取值被替换"),
    ]

    print("=== CI 门禁故障注入自证（每类注入都必须让门禁变红）===")
    h = Harness("ci-jobs-selftest")
    env = dict(os.environ)
    with TempWorkspace("cijobs-selftest") as ws:
        for kind, desc in injections:
            mutated = _mutate(base, kind)
            path = ws.path(f"ci-{kind}.yml")
            with open(path, "w", encoding="utf-8") as f:
                f.write(mutated)
            env["CI_WORKFLOW"] = path
            p = subprocess.run([sys.executable, os.path.abspath(__file__)],
                               capture_output=True, text=True, encoding="utf-8",
                               errors="ignore", env=env)
            rc = p.returncode
            # 在子进程输出里找是哪一条断言抓到的（便于人工确认不是误命中）
            hit = [l for l in p.stdout.splitlines()
                   if l.startswith("FAIL") and ("关键" in l or "matrix" in l
                                                or "恒假" in l or "三引擎" in l
                                                or "continue-on-error" in l or "空转" in l)]
            h.record(f"注入[{kind}] 使门禁变红（rc!=0）", rc != 0,
                     f"{desc} -> rc={rc}" + (f"，命中: {hit[0][:80]}" if hit else ""))
    h.finish()


def main():
    if "--selftest" in sys.argv[1:]:
        selftest()
        return
    guard(H, run, H)
    H.finish()


if __name__ == "__main__":
    main()
