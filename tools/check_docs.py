#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""文档一致性检查：README / CHANGELOG 中的关键表述不得回退。

本轮教训：README 曾用"零外部 CDN 请求""无 CDN"描述主题，容易让用户误解为
"任何配置下都没有第三方请求"。这里把关键表述固化成断言，防止再次回退。

检查项：
    1. README 不得出现"零外部 CDN 请求" / "无 CDN" / "完全没有 CDN"等绝对表述
    2. README 必须说明：默认无外部 CDN；启用可选评论/统计后可能加载第三方资源
    3. README 必须列出五个第三方服务：giscus / Waline / Twikoo / Disqus / busuanzi
    4. README 必须说明这些服务"默认关闭"
    5. CHANGELOG 必须存在且含当前版本条目

退出码约定（见 tools/_testlib.py）：任一断言失败 -> exit 1。

用法：python3 tools/check_docs.py [repo_root]
"""
import os
import re
import sys

from _testlib import Harness, guard

ROOT = sys.argv[1] if len(sys.argv) > 1 else os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

# Release 全站审计的**准确表述**（必须出现在 audit.py / CI / 文档中）
REQUIRED_TRUTH_WORDING = "以构建产物 HTML inventory 为真值"

# 禁止的过时表述：把 sitemap 当作全站真值
STALE_PHRASES = [
    "sitemap 中**全部可审计 HTML 页面**",
    "sitemap 中全部 HTML 页面",
    "sitemap 全部 HTML 页面",
    "覆盖 sitemap 全部 HTML 页面",
    "扫描 sitemap 中全部",
    "sitemap + pagination = 全站",
]

# 绝对化表述：出现即判失败
FORBIDDEN_PHRASES = [
    "零外部 CDN 请求",
    "零外部CDN请求",
    "无外部 CDN 请求。",       # 允许"默认…无外部 CDN 请求"这类限定表述
    "无 CDN\n",
    "完全没有 CDN",
    "任何配置下都没有外部",
    "不加载任何第三方",         # 除非紧邻"默认"限定（单独出现视为过度承诺）
]

REQUIRED_SERVICES = ["giscus", "Waline", "Twikoo", "Disqus", "busuanzi"]

# 必须出现的语义要点（任一命中即可）
REQUIRED_MEANINGS = [
    ("默认无外部 CDN", ["默认配置下无外部 CDN", "默认无外部 CDN",
                        "默认情况下主题无外部 CDN", "默认关闭可选第三方服务时无外部 CDN"]),
    ("启用后加载第三方", ["启用可选评论", "启用评论", "启用可选的评论",
                          "开启后会", "启用评论/统计"]),
]


def check_truth_wording(h):
    """Release 全站审计的表述一致性（准确表述必须在场，过时表述必须缺席）。"""
    targets = [
        ("tools/audit.py", os.path.join(ROOT, "tools", "audit.py")),
        (".github/workflows/ci.yml", os.path.join(ROOT, ".github", "workflows", "ci.yml")),
        ("README.md", os.path.join(ROOT, "README.md")),
    ]
    missing, stale = [], []
    for label, path in targets:
        if not os.path.isfile(path):
            missing.append(f"{label}(文件不存在)")
            continue
        text = open(path, encoding="utf-8").read()
        if REQUIRED_TRUTH_WORDING not in text:
            missing.append(f"{label} 缺少准确表述")
        for ph in STALE_PHRASES:
            if ph in text:
                line_no = text[: text.index(ph)].count("\n") + 1
                stale.append(f"{label}:{line_no} 仍写着「{ph}」")
    h.record("audit.py / CI / README 均声明「inventory 为全站真值」",
             not missing, "；".join(missing) if missing else "三处均已声明")
    h.record("无「sitemap = 全站」类过时表述",
             not stale, "；".join(stale[:3]) if stale else "无过时表述")


def run(h):
    readme_p = os.path.join(ROOT, "README.md")
    if not os.path.isfile(readme_p):
        h.fatal_error("README.md 不存在", readme_p)
        return
    readme = open(readme_p, encoding="utf-8").read()

    # ① 绝对化表述
    bad = []
    quoted = []          # 作为"被批评的示例"被引号包裹的引用，豁免但必须打印
    for ph in FORBIDDEN_PHRASES:
        for m in re.finditer(re.escape(ph), readme):
            line_no = readme[: m.start()].count("\n") + 1
            line_start = readme.rfind("\n", 0, m.start()) + 1
            line_end = readme.find("\n", m.end())
            line = readme[line_start: line_end if line_end > 0 else len(readme)]
            ctx = line.strip()[:80]
            # "默认配置下无外部 CDN 请求" 这类限定表述不算问题
            if "默认" in ctx:
                continue
            # 元语境：把该短语作为"被禁止/被回退的示例"引用时豁免（如更新日志、
            # 门禁说明），但必须打印，保证"引用"不会被误当成"声明"
            if re.search(r"[\"“”「」]|防止|回退|不再|这类表述|绝对化", line):
                quoted.append(f"第 {line_no} 行（作为示例引用，豁免）: {ctx}")
                continue
            bad.append(f"第 {line_no} 行: …{ctx}…")
    h.record("README 无绝对化的 CDN 表述", not bad, "；".join(bad[:3]) if bad else "干净")
    if quoted:
        print("\n被禁短语作为示例被引用（已豁免，请确认是批评性引用而非声明）:")
        for q in quoted:
            print("   ", q)

    # ② 必须说明默认无 CDN + 启用后有第三方
    missing = [name for name, pats in REQUIRED_MEANINGS
               if not any(p in readme for p in pats)]
    h.record("README 说明「默认无外部 CDN / 启用后可能加载第三方」",
             not missing, f"缺少: {missing}" if missing else "表述完整")

    # ③ 五个第三方服务必须列出
    absent = [s for s in REQUIRED_SERVICES if s not in readme]
    h.record("README 列出全部五个第三方服务（giscus/Waline/Twikoo/Disqus/busuanzi）",
             not absent, f"缺少: {absent}" if absent else "齐全")

    # ④ 默认关闭
    h.record("README 说明这些服务默认关闭",
             "默认关闭" in readme or "默认均为 false" in readme
             or "enable = false" in readme,
             "已说明默认关闭")

    # ⓹ Release 全站审计表述一致性
    check_truth_wording(h)

    # ⑤ CHANGELOG 存在且有当前版本
    # TEST-DEFECT-011：旧实现把默认版本硬编码为 1.0.7，不设 DOC_VERSION 时
    # 校验的是"两个版本之前"的条目 -> 本地/其它调用方必然假绿。
    # 现在按 DOC_VERSION -> git tag -> CHANGELOG 首个版本 依次推断，
    # 并额外与 docs/稳定基线.md 交叉核对，防止"漏更新文档"。
    chg = os.path.join(ROOT, "CHANGELOG.md")
    version, source = _resolve_version(chg)
    if os.path.isfile(chg):
        text = open(chg, encoding="utf-8").read()
        h.record(f"CHANGELOG 存在且含 v{version} 条目（版本来源：{source}）",
                 version in text, f"CHANGELOG.md 中查找 {version}")
        baseline = os.path.join(ROOT, "docs", "稳定基线.md")
        if os.path.isfile(baseline):
            btxt = open(baseline, encoding="utf-8").read()
            h.record(f"稳定基线文档记录的版本与 CHANGELOG 一致（v{version}）",
                     version in btxt,
                     f"{os.path.relpath(baseline, ROOT)} 中查找 {version}")
    else:
        h.record("CHANGELOG.md 存在", False, chg)


def _resolve_version(changelog_path):
    """推断"当前版本"：DOC_VERSION 环境变量 -> git tag -> CHANGELOG 首个版本号。

    返回 (version, source)。避免硬编码（TEST-DEFECT-011）。
    """
    env = os.environ.get("DOC_VERSION")
    if env:
        return env, "DOC_VERSION 环境变量"
    try:
        import subprocess
        r = subprocess.run(["git", "describe", "--tags", "--abbrev=0"],
                           cwd=ROOT, capture_output=True, text=True, timeout=10)
        tag = (r.stdout or "").strip().lstrip("v")
        if r.returncode == 0 and re.fullmatch(r"\d+\.\d+\.\d+", tag or ""):
            return tag, f"git tag v{tag}"
    except Exception:
        pass
    if os.path.isfile(changelog_path):
        text = open(changelog_path, encoding="utf-8").read()
        m = re.search(r"^##\s*\[?(\d+\.\d+\.\d+)", text, re.M)
        if m:
            return m.group(1), "CHANGELOG 首个版本条目"
    return "0.0.0", "无法推断（将判失败）"


if __name__ == "__main__":
    main_h = Harness("docs")
    guard(main_h, run, main_h)
    main_h.finish()
