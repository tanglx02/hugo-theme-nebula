#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Hugo 版本兼容矩阵：用多个真实 Hugo 版本构建 exampleSite，并校验产物正确性。

用法：python tools/compat_matrix.py
"""
import json
import os
import re
import shutil
import subprocess

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
THEME = os.path.join(ROOT, "hugo-theme-nebula")
OUT = os.path.join(ROOT, "tmp", "compat")

VERSIONS = {
    "0.128.0": os.path.join(os.environ.get("TEMP", "C:/tmp"), "hugovers", "0.128.0", "hugo.exe"),
    "0.162.0": os.path.join(os.environ.get("TEMP", "C:/tmp"), "hugovers", "0.162.0", "hugo.exe"),
    "0.167.0": r"C:\Users\Administrator\.workbuddy\binaries\hugo\bin\hugo.exe",
}


def build(version, exe):
    dest = os.path.join(OUT, version)
    shutil.rmtree(dest, ignore_errors=True)
    os.makedirs(dest, exist_ok=True)
    p = subprocess.run([exe, "--source", "exampleSite", "--themesDir", "../..",
                        "--gc", "--minify", "-d", dest],
                       cwd=THEME, capture_output=True, text=True, encoding="utf-8", errors="ignore")
    errs = [l for l in (p.stderr + p.stdout).splitlines() if l.strip().upper().startswith("ERROR")]
    return dest, errs, (p.stderr + p.stdout)


def inspect(dest):
    res = {}
    html_files = 0
    for dirpath, _, files in os.walk(dest):
        html_files += sum(1 for f in files if f.endswith(".html"))
    res["html_pages"] = html_files

    idx = os.path.join(dest, "index.json")
    if os.path.exists(idx):
        data = json.load(open(idx, encoding="utf-8"))
        res["index_items"] = len(data)
        res["index_kb"] = os.path.getsize(idx) // 1024
        res["max_content"] = max((len(i.get("content", "") or "") for i in data), default=0)
        blob = json.dumps(data, ensure_ascii=False)
        res["deep_marker"] = "GOLF48000" in blob
    else:
        res["index_items"] = 0

    # 代码块渲染情况
    code_page = os.path.join(dest, "posts", "zz-10-codeblocks", "index.html")
    if os.path.exists(code_page):
        html = open(code_page, encoding="utf-8").read()
        res["code_blocks"] = len(re.findall(r"code-block", html))
        res["chroma"] = len(re.findall(r"chroma", html))
        res["unknown_lang_ok"] = "does not exist" in html or "unknownlang123" in html
    # JSON-LD 时区
    tz_page = os.path.join(dest, "posts", "zz-18-tz-plus8", "index.html")
    if os.path.exists(tz_page):
        html = open(tz_page, encoding="utf-8").read()
        m = re.search(r'"datePublished"\s*:\s*"([^"]+)"', html)
        res["datePublished"] = m.group(1) if m else "缺失"
    return res


def main():
    print("Hugo 版本兼容矩阵（构建 exampleSite 并校验产物）\n")
    summary = {}
    for version, exe in VERSIONS.items():
        if not os.path.exists(exe):
            print(f"[{version}] 跳过：未找到 {exe}")
            continue
        dest, errs, log = build(version, exe)
        info = inspect(dest)
        ok = not errs
        summary[version] = (ok, info, errs[:2])
        print(f"[{version}] 构建 {'成功' if ok else '失败'}")
        if errs:
            for e in errs[:2]:
                print("   ERROR:", e[:160])
        print(f"   页面 {info.get('html_pages')} | 索引 {info.get('index_items')} 条 / {info.get('index_kb')}KB "
              f"| 最大正文 {info.get('max_content')} 字 | 深处关键词 {info.get('deep_marker')}")
        print(f"   代码块 {info.get('code_blocks')} | chroma {info.get('chroma')} "
              f"| datePublished {info.get('datePublished')}")

    print("\n结论：")
    passed = [v for v, (ok, _, _) in summary.items() if ok]
    failed = [v for v, (ok, _, _) in summary.items() if not ok]
    print("  构建通过:", passed)
    print("  构建失败:", failed or "无")
    if passed:
        print("  建议 min_version =", min(passed))


if __name__ == "__main__":
    main()
