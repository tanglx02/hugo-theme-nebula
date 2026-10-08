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

    # ⑤ CHANGELOG 存在且有当前版本
    chg = os.path.join(ROOT, "CHANGELOG.md")
    if os.path.isfile(chg):
        text = open(chg, encoding="utf-8").read()
        version = os.environ.get("DOC_VERSION", "1.0.7")
        h.record(f"CHANGELOG 存在且含 v{version} 条目",
                 version in text, f"CHANGELOG.md 中查找 {version}")
    else:
        h.record("CHANGELOG.md 存在", False, chg)


if __name__ == "__main__":
    main_h = Harness("docs")
    guard(main_h, run, main_h)
    main_h.finish()
