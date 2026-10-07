#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""静态死链与资源检查：扫描 public/ 下所有 HTML，校验站内链接与静态资源是否存在。"""
import os
import re
import sys
from urllib.parse import unquote, urlparse

ROOT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "myblog", "public")
ROOT = os.path.normpath(ROOT)

# 兼容 hugo --minify 输出（属性可能不带引号）
HREF_RE = re.compile(r'(?:href|src)=(?:"([^"]*)"|\'([^\']*)\'|([^\s>]+))')
HTML_FILES = []

for dirpath, _, files in os.walk(ROOT):
    for f in files:
        if f.endswith((".html", ".xml")):
            HTML_FILES.append(os.path.join(dirpath, f))

print(f"扫描 {len(HTML_FILES)} 个文件")


def exists_for(url_path: str) -> bool:
    """判断站内 URL 路径是否有对应文件/目录首页"""
    p = unquote(url_path.split("?")[0].split("#")[0])
    if not p.startswith("/"):
        return True  # 相对路径按当前目录处理，跳过
    rel = p.lstrip("/")
    target = os.path.join(ROOT, rel)
    if os.path.isfile(target):
        return True
    if os.path.isfile(os.path.join(target, "index.html")):
        return True
    # 目录不带尾斜杠的情况（如 /about）
    if os.path.isdir(target) and os.path.isfile(os.path.join(target, "index.html")):
        return True
    return False


problems = []
checked = 0
for html in HTML_FILES:
    try:
        content = open(html, encoding="utf-8", errors="ignore").read()
    except Exception:
        continue
    for match in set(HREF_RE.findall(content)):
        u = (match[0] or match[1] or match[2] or "").strip()
        if not u or u.startswith(("#", "mailto:", "tel:", "javascript:", "data:")):
            continue
        if u.startswith("//"):
            continue
        parsed = urlparse(u)
        if parsed.scheme in ("http", "https"):
            continue  # 外链不校验（构建期无法保证可达）
        if not u.startswith("/"):
            # 相对路径：按文件所在目录解析
            base_dir = os.path.dirname(html)
            target = os.path.normpath(os.path.join(base_dir, u))
            checked += 1
            if not (os.path.exists(target) or os.path.exists(target + ".html")):
                problems.append((os.path.relpath(html, ROOT), u))
            continue
        checked += 1
        if not exists_for(u):
            problems.append((os.path.relpath(html, ROOT), u))

print(f"校验链接 {checked} 条，问题 {len(problems)} 条")
seen = set()
for src, url in problems:
    key = (src.split(os.sep)[0], url)
    if key in seen:
        continue
    seen.add(key)
    print(f"  死链: {src} -> {url}")
    if len(seen) > 40:
        print("  ... (更多省略)")
        break

if not problems:
    print("  ✅ 无死链")
