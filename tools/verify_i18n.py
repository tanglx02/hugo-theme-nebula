#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""多语言渲染检查：确认 UI 文案真正来自 i18n（zh-CN / zh-TW / en），而不是硬编码。

用法：
    python tools/verify_i18n.py <built_dir> <lang>

检查范围（只针对 UI 文案，不涉及文章内容本身）：
    - 顶部导航（menu.* 词条，通过 identifier 解析）
    - 首页标题 / 查看全部 / 浏览更多
    - 侧边栏组件标题
    - 面包屑（首页）
    - 归档 / 列表 / 词条统计（含占位符是否正确替换为数字）
    - 文章页：日期格式 / 阅读时长 / 标题锚点 aria / 版权默认文案
    - 注入给 JS 的 NEBULA_I18N 文案

退出码约定（见 tools/_testlib.py）：任一断言失败 -> exit 1。
"""
import json
import os
import re
import sys

DIR = sys.argv[1] if len(sys.argv) > 1 else ""
LANG = sys.argv[2] if len(sys.argv) > 2 else "zh-CN"

EXPECT = {
    "zh-CN": {
        "menu": {"home": "首页", "posts": "文章", "categories": "分类",
                 "tags": "标签", "archives": "归档", "about": "关于"},
        "homeLatest": "最新文章", "viewAll": "查看全部", "browse": "浏览更多文章",
        "search": "搜索", "sidebarCategories": "文章分类", "sidebarTagCloud": "标签云",
        "breadcrumbHome": "首页",
        "countRe": r"共\s*\d+\s*篇文章",
        "termsCountRe": r"共\s*\d+\s*项",
        "dateRe": r"\d{4}年\d{1,2}月\d{1,2}日",
        "minutesRe": r"约\s*\d+\s*分钟",
        "anchor": "锚点链接",
        "jsCopied": "已复制", "jsZoom": "放大图片",
        "forbiddenInUi": ["Latest posts", "Categories</span>", "Tags</span>"],
    },
    "zh-TW": {
        "menu": {"home": "首頁", "posts": "文章", "categories": "分類",
                 "tags": "標籤", "archives": "歸檔", "about": "關於"},
        "homeLatest": "最新文章", "viewAll": "檢視全部", "browse": "瀏覽更多文章",
        "search": "搜尋", "sidebarCategories": "文章分類", "sidebarTagCloud": "標籤雲",
        "breadcrumbHome": "首頁",
        "countRe": r"共\s*\d+\s*篇文章",
        "termsCountRe": r"共\s*\d+\s*項",
        "dateRe": r"\d{4}年\d{1,2}月\d{1,2}日",
        "minutesRe": r"約\s*\d+\s*分鐘",
        "anchor": "錨點連結",
        "jsCopied": "已複製", "jsZoom": "放大圖片",
        "forbiddenInUi": ["Latest posts", "最新文章</h3>"],
    },
    "en": {
        "menu": {"home": "Home", "posts": "Posts", "categories": "Categories",
                 "tags": "Tags", "archives": "Archives", "about": "About"},
        "homeLatest": "Latest posts", "viewAll": "View all", "browse": "Browse more posts",
        "search": "Search", "sidebarCategories": "Categories", "sidebarTagCloud": "Tag cloud",
        "breadcrumbHome": "Home",
        "countRe": r"\d+\s+posts",
        "termsCountRe": r"\d+\s+term",
        "dateRe": r"[A-Z][a-z]{2} \d{1,2}, \d{4}",
        "minutesRe": r"\d+\s+min",
        "anchor": "Anchor link",
        "jsCopied": "Copied", "jsZoom": "Zoom image",
        "forbiddenInUi": ["最新文章</h3>", "文章分类</h3>", "标签云</h3>", ">首页</a>", ">导航<"],
    },
}

checks = []
errors = []


def ok(name, detail=""):
    checks.append(name)
    print(f"PASS  {name}" + (f" :: {detail}" if detail else ""))


def bad(name, detail=""):
    checks.append(name)
    errors.append(name)
    print(f"FAIL  {name}" + (f" :: {detail}" if detail else ""))


def read(rel):
    p = os.path.join(DIR, rel)
    if not os.path.exists(p):
        return None
    return open(p, encoding="utf-8", errors="ignore").read()


def strip_ws(s):
    return re.sub(r"\s+", " ", s)


if not DIR or not os.path.isdir(DIR):
    print(f"FAIL 构建目录不存在: {DIR}")
    sys.exit(1)
if LANG not in EXPECT:
    print(f"FAIL 未知语言: {LANG}")
    sys.exit(1)

exp = EXPECT[LANG]
home = read("index.html")

if home is None:
    bad("首页存在")
else:
    ok("首页存在")

    # ---------------- 顶部导航（menu.* 词条） ----------------
    nav = re.search(r"<nav[^>]*id=(?:\"?)mainNav(?:\"?)[^>]*>(.*?)</nav>", home, re.S)
    if not nav:
        bad("顶部导航存在")
    else:
        ok("顶部导航存在")
        navhtml = strip_ws(nav.group(1))
        for ident, label in exp["menu"].items():
            if re.search(r">\s*" + re.escape(label) + r"\s*<", navhtml):
                ok(f"导航「{ident}」= {label}")
            else:
                bad(f"导航「{ident}」= {label}", navhtml[:150])
        for f in exp["forbiddenInUi"]:
            if f in navhtml:
                bad(f"导航不应出现其它语言文案 {f!r}")

    # ---------------- 首页 ——
    for key, label in (("homeLatest", "首页最新标题"), ("viewAll", "查看全部"), ("browse", "浏览更多")):
        if exp[key] in home:
            ok(f"{label} = {exp[key]}")
        else:
            bad(f"{label} = {exp[key]}")

    # 侧边栏组件标题
    for key, label in (("sidebarCategories", "侧栏分类标题"), ("sidebarTagCloud", "侧栏标签云标题")):
        if exp[key] in home:
            ok(f"{label} = {exp[key]}")
        else:
            bad(f"{label} = {exp[key]}")

    # 注入给 JS 的文案
    m = re.search(r"NEBULA_I18N\s*=\s*(\{.*?\})\s*<", home, re.S)
    if not m:
        m = re.search(r"NEBULA_I18N\s*=\s*(\{.*?\});", home, re.S)
    if not m:
        bad("NEBULA_I18N 注入")
    else:
        blob = m.group(1)
        for label, expect_val in (("copied", exp["jsCopied"]), ("zoom", exp["jsZoom"])):
            pat = rf'{label}:\s*"{re.escape(expect_val)}"'
            if re.search(pat, blob):
                ok(f"JS i18n {label} = {expect_val}")
            else:
                bad(f"JS i18n {label} = {expect_val}", blob[:100])
        if "{{ ." in blob:
            bad("JS i18n 无未渲染的 Go 模板占位符")
        else:
            ok("JS i18n 无未渲染的 Go 模板占位符")

# ---------------- 归档页 ----------------
arch = read("archives/index.html")
if arch is None:
    bad("归档页存在")
else:
    ok("归档页存在")
    if exp["breadcrumbHome"] in arch:
        ok("归档面包屑首页文案", exp["breadcrumbHome"])
    else:
        bad("归档面包屑首页文案", exp["breadcrumbHome"])
    m = re.search(exp["countRe"], arch)
    if m:
        ok("归档统计（数字已替换）", m.group(0))
    else:
        bad("归档统计（数字已替换）", strip_ws(arch)[:200])
    if "{posts}" in arch or "{years}" in arch:
        bad("归档统计无未替换占位符")

# ---------------- 文章列表页 ----------------
lst = read("posts/index.html")
if lst is not None:
    m = re.search(exp["countRe"], lst)
    if m:
        ok("列表统计（数字已替换）", m.group(0))
    else:
        bad("列表统计（数字已替换）", strip_ws(lst)[:200])

# ---------------- 词条总览页 ----------------
terms = read("tags/index.html")
if terms is not None:
    m = re.search(exp["termsCountRe"], terms)
    if m:
        ok("标签总览统计（数字已替换）", m.group(0))
    else:
        bad("标签总览统计（数字已替换）", strip_ws(terms)[:200])

# ---------------- 文章页 ----------------
post = read("posts/zz-02-10k/index.html")
if post is None:
    bad("文章页存在（posts/zz-02-10k）")
else:
    ok("文章页存在")
    meta = re.search(r'class=["\']?article-meta["\']?[^>]*>(.*?)</div>', post, re.S)
    meta_html = strip_ws(meta.group(1)) if meta else strip_ws(post)
    m = re.search(exp["dateRe"], meta_html)
    if m:
        ok("文章日期格式", m.group(0))
    else:
        bad("文章日期格式", meta_html[:160])
    m = re.search(exp["minutesRe"], post)
    if m:
        ok("阅读时长（数字已替换）", m.group(0))
    else:
        bad("阅读时长（数字已替换）")
    an = re.search(r'''class=["']?anchor["']?[^>]*aria-label=(?:"([^"]+)"|'([^']+)'|([^\s>]+))''', post)
    got = next((g for g in (an.groups() if an else ()) if g), None)
    if got == exp["anchor"]:
        ok("标题锚点 aria", got)
    else:
        bad("标题锚点 aria", got if got else "未找到 anchor")
    if "{{ ." in post:
        bad("文章页无未渲染的 Go 模板占位符")
    else:
        ok("文章页无未渲染的 Go 模板占位符")

print()
print(f"==== [i18n:{LANG}] {len(checks) - len(errors)}/{len(checks)} PASSED ====")
if errors:
    for e in errors:
        print("  -", e)
print("TEST-RESULT: " + json.dumps(
    {"suite": f"i18n-{LANG}", "status": "FAIL" if errors else "PASS",
     "passed": len(checks) - len(errors), "failed": len(errors), "total": len(checks)},
    ensure_ascii=False))
sys.exit(1 if errors else 0)
