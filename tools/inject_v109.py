#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v1.0.9 故障注入工具：证明门禁真的会变红（而不是假绿灯）。

每个注入都对应一条"如果不修就会悄悄漏过去"的缺陷：

    A  搜索结果日期改成硬编码 2006-01-02
       -> tools/check_date_format.py + tools/check_search_date.py 必须 FAIL
    B  is_article_page() 退回宽泛正则 /[^/]+/[^/]+/
       -> tools/check_article_classification.py 必须 FAIL
    C  alias 页去掉 meta refresh
       -> tools/check_alias_pages.py 必须 FAIL
    D  highlight() 不做转义（先替换再输出）
       -> tools/verify_search_highlight.py 必须 FAIL
    E  workflow 改回 Node20 时代的旧 action
       -> tools/check_workflow_policy.py 必须 FAIL
    F  删除 workflow 顶层 permissions
       -> tools/check_workflow_policy.py 必须 FAIL
    G  CI matrix 多加一个浏览器
       -> tools/check_ci_jobs.py 必须 FAIL（登记数量不再匹配）

用法：
    python tools/inject_v109.py A          # 注入
    python tools/inject_v109.py A --revert # 还原（仅限本脚本改过的文件）
    python tools/inject_v109.py --list
"""
import os
import subprocess
import sys

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

INJECTIONS = {
    "A": {
        "desc": "搜索索引 dateDisplay 改为硬编码 2006-01-02（丢弃 i18n）",
        "file": "layouts/_default/index.json",
        "old": '"dateDisplay" (cond .Date.IsZero "" (.Date.Format (i18n "common.dateFormat")))',
        "new": '"dateDisplay" (cond .Date.IsZero "" (.Date.Format "2006-01-02"))',
    },
    "B": {
        "desc": "is_article_page() 退回宽泛正则（把 term 页误判成文章页）",
        "file": "tools/audit.py",
        "old": '''    secs = set(sections or content_sections())
    parts = [p for p in path.split("/") if p]
    if len(parts) != 2:
        return False
    section, slug = parts
    token = page_token or pagination_path()
    return section in secs and slug != token''',
        "new": '''    import re as _re
    return bool(_re.fullmatch(r"/[^/]+/[^/]+/", path)) and "/page/" not in path''',
    },
    "C": {
        "desc": "alias 页去掉 meta refresh（alias 将不再是重定向页）",
        "file": "layouts/alias.html",
        "old": '<meta http-equiv="refresh" content="0; url={{ .Permalink }}">\n',
        "new": "",
    },
    "D": {
        "desc": "highlight() 不做 HTML 转义（先替换再输出）",
        "file": "assets/js/main.js",
        "old": "      var out = esc(text);",
        "new": "      var out = String(text || '');",
    },
    "E": {
        "desc": "workflow 改回 Node20 时代的旧 action 版本",
        "file": ".github/workflows/ci.yml",
        "old": None,      # 多段替换，见 MULTI
        "new": None,
        "multi": [
            ("actions/checkout@v7.0.1", "actions/checkout@v4"),
            ("actions/setup-python@v7.0.0", "actions/setup-python@v5"),
            ("actions/cache@v6.1.0", "actions/cache@v4"),
            ("actions/upload-artifact@v7.0.2", "actions/upload-artifact@v4"),
        ],
    },
    "F": {
        "desc": "删除 workflow 顶层 permissions",
        "file": ".github/workflows/ci.yml",
        "old": """# 校验工具：tools/check_workflow_policy.py（禁止 *: write，必须 contents: read）
permissions:
  contents: read
""",
        "new": "",
    },
    "G": {
        "desc": "browser-tests matrix 多加一个浏览器（登记数量不再匹配）",
        "file": ".github/workflows/ci.yml",
        "old": "        browser: [chromium, firefox, webkit]\n        include:\n          - browser: chromium\n            viewports: '320,375,390,430,768,1024,1440'",
        "new": "        browser: [chromium, firefox, webkit, msedge]\n        include:\n          - browser: chromium\n            viewports: '320,375,390,430,768,1024,1440'\n          - browser: msedge\n            viewports: '375,1440'",
    },
}


def apply(code):
    inj = INJECTIONS[code]
    path = os.path.join(ROOT, inj["file"])
    text = open(path, encoding="utf-8").read()
    pairs = inj.get("multi") or [(inj["old"], inj["new"])]
    for old, new in pairs:
        if old not in text:
            print(f"FAIL  注入 {code} 找不到锚点: {old[:60]!r}")
            return 1
        text = text.replace(old, new)
    open(path, "w", encoding="utf-8").write(text)
    print(f"OK    已注入 {code}: {inj['desc']}  ({inj['file']})")
    return 0


def _git_restore(path):
    """删除型注入（new == ""）无法用 replace 反转：
       旧的实现用 str.replace("", old)，会把 old 插到每个字符之间，
       把文件撑到几万行（v1.0.9 真实翻车过）。改用 git 恢复。"""
    rel = os.path.relpath(path, ROOT).replace("\\", "/")
    p = subprocess.run(["git", "checkout", "HEAD", "--", rel],
                       cwd=ROOT, capture_output=True, text=True)
    if p.returncode != 0:
        print(f"FAIL  git 恢复 {rel} 失败: {p.stderr.strip()[:120]}")
        return 1
    # 断言恢复后确实回到了基线内容（防止把注入版也一起恢复）
    text = open(path, encoding="utf-8").read()
    return text


def revert(code):
    inj = INJECTIONS[code]
    path = os.path.join(ROOT, inj["file"])
    pairs = inj.get("multi") or [(inj["old"], inj["new"])]

    # 删除型注入（new == "" / None）：直接用 git 恢复基线。
    #   绝不能用 str.replace("", old)：Python 会把 old 插到每个字符之间，
    #   把 workflow 撑到几万行（v1.0.9 真实翻车过，见验收报告）。
    if any(new in ("", None) for _old, new in pairs):
        text = _git_restore(path)
        if text == 1:
            return 1
        for old, new in pairs:
            if old and old not in text:
                print(f"FAIL  还原 {code} 后基线锚点未恢复: {old[:60]!r}")
                return 1
            if new and new in text:
                print(f"FAIL  还原 {code} 后注入内容仍存在: {new[:60]!r}")
                return 1
        print(f"OK    已还原 {code}（git restore，删除型注入）  ({inj['file']})")
        return 0

    # 替换型注入：用注入内容反查并还原
    text = open(path, encoding="utf-8").read()
    for old, new in pairs:
        if new not in text:
            print(f"FAIL  还原 {code} 找不到注入内容: {new[:60]!r}")
            return 1
        text = text.replace(new, old)
    open(path, "w", encoding="utf-8").write(text)
    print(f"OK    已还原 {code}  ({inj['file']})")
    return 0


def main():
    if len(sys.argv) < 2 or sys.argv[1] == "--list":
        print("可用注入:")
        for k, v in INJECTIONS.items():
            print(f"  {k}: {v['desc']}  [{v['file']}]")
        return 0
    code = sys.argv[1].upper()
    if code not in INJECTIONS:
        print(f"未知注入 {code}")
        return 2
    return revert(code) if "--revert" in sys.argv else apply(code)


if __name__ == "__main__":
    sys.exit(main())
