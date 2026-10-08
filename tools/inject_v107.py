"""v1.0.7 故障注入脚本（A-F）。

用法：python3 tools/inject_v107.py <A|B|C|D|E|F|restore>
每个注入都应有对应门禁变红；restore 从基线提交恢复。
"""
import io
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def patch(rel, pairs, count_check=True):
    p = os.path.join(ROOT, rel)
    s = io.open(p, encoding="utf-8").read()
    for old, new in pairs:
        if count_check:
            assert s.count(old) >= 1, f"{rel}: anchor not found: {old[:60]}"
        s = s.replace(old, new, 1)
    io.open(p, "w", encoding="utf-8", newline="").write(s)
    print(f"  patched {rel}")


def case_A():
    """A: 人为让 inventory 与 audit 脱节 —— 从 audit 的 URL 列表里漏掉一个产物页面。

    手法：audit.py 在 FULL 模式构造 urls 时丢弃一个 inventory URL，
    模拟"新增 HTML 输出模板但 audit 没跟上"。
    预期：Release audit 报 MISSING URLS > 0 并 exit 1。
    """
    patch("tools/audit.py", [(
        """        urls = list(expected) + [p for p in html_pages if p not in set(expected)]""",
        """        urls = [p for p in expected if not p.endswith("/about/")]  # INJECTED-A
        urls += [p for p in html_pages if p not in set(expected)]""")])


def case_B():
    """B: pagination discovery 第一次失败（应重试并恢复）。

    手法：让第一次抓取抛异常、之后正常。
    预期：discovery_retries >= 1，最终无 failures，审计仍 PASS。
    """
    patch("tools/audit.py", [(
        """def _fetch_once(base, path):
    \"\"\"单次抓取。返回 (html, failure_reason)，不做重试。""",
        """_INJECT_B = {"done": False}


def _fetch_once(base, path):
    \"\"\"单次抓取。返回 (html, failure_reason)，不做重试。"""
    if not _INJECT_B["done"] and path == "/":
        _INJECT_B["done"] = True
        return None, "URLError: INJECTED-B 首次失败（应被重试救回）\"""")])


def case_C():
    """C: pagination discovery 所有重试失败。

    手法：对固定 URL 永久失败。
    预期：discovery_failures 非空 -> exhausted=False -> Release audit exit 1。
    """
    patch("tools/audit.py", [(
        """def _fetch_once(base, path):
    \"\"\"单次抓取。返回 (html, failure_reason)，不做重试。""",
        """_INJECT_C = {"n": 0}


def _fetch_once(base, path):
    \"\"\"单次抓取。返回 (html, failure_reason)，不做重试。\"\"\"
    if path == "/":
        _INJECT_C["n"] += 1
        return None, f"URLError: INJECTED-C 永久失败 #{_INJECT_C['n']}\"""")])


def case_D():
    """D: 制造一个 public HTML 页面但故意不进入 sitemap。

    手法：新增一个 sitemap.disable = true 的内容页 —— 它会出现在 public/ 但不在 sitemap。
    预期：inventory 发现它（EXPECTED +1），audit 必须审计它，MISSING URLS = 0。
           若 audit 仍以 sitemap 为真值，就会漏掉它（MISSING/UNEXPECTED 差异）。
    """
    p = os.path.join(ROOT, "exampleSite/content/posts/zz-sitemap-hidden.md")
    io.open(p, "w", encoding="utf-8", newline="").write(
        """---
title: "不进 sitemap 的页面"
date: 2026-10-08
description: "该页面通过 sitemap.disable 排除出 sitemap，但必须被 inventory 覆盖"
categories: ["环境搭建"]
sitemap:
  disable: true
---

这个页面故意不出现在 sitemap.xml 中，用于验证构建产物 inventory 才是全站真值。
""")
    print("  added exampleSite/content/posts/zz-sitemap-hidden.md (sitemap.disable)")


def case_E():
    """E: 加入 javascript: 链接。

    预期：security baseline 判危险 URL scheme -> exit 1。
    """
    patch("layouts/partials/footer.html", [(
        "</footer>",
        '<a href="javascript:alert(1)">INJECTED-E</a>\n</footer>')])


def case_F():
    """F: README 改回错误的 CDN 绝对化表述。

    预期：check_docs.py 的文档一致性检查判失败。
    """
    patch("README.md", [(
        "默认配置下无外部 CDN 请求",
        "零外部 CDN 请求")], count_check=False)


CASES = {"A": case_A, "B": case_B, "C": case_C, "D": case_D, "E": case_E, "F": case_F}

if __name__ == "__main__":
    what = sys.argv[1] if len(sys.argv) > 1 else ""
    if what in CASES:
        print(f"INJECT {what}:")
        CASES[what]()
    else:
        print(__doc__)
        print("cases:", ", ".join(CASES))
