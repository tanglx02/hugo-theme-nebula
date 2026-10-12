#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""静态死链与资源检查：扫描构建产物目录下所有 HTML，校验站内链接与静态资源是否存在。

用法：
    python tools/link_check.py [构建产物目录]

缺省产物目录统一为 `<repo>/public`（见 `_testlib.default_build_dir`）。
此前缺省写死为 `<repo>/myblog/public` —— 该目录早已不在仓库里，**裸跑必然
"目录不存在"**，而 CI 因显式传参侥幸通过（属"只在 CI 里能跑"的隐性缺陷）。

退出码约定（见 tools/_testlib.py）：
  * 发现死链                    -> exit 1
  * 目录不存在 / 扫描到 0 个文件 -> exit 1（结果不可信）
"""
import json
import os
import re
import sys
from urllib.parse import unquote, urlparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _testlib import default_build_dir  # noqa: E402

ROOT = default_build_dir()
ROOT = os.path.normpath(ROOT)

# 已知的"故意断链"白名单（压力测试数据）：用于验证图片缺失时的降级渲染，
# 属于内容作者故意为之，不是主题缺陷。白名单必须显式列出并会被计数打印，
# 不允许静默忽略，避免掩盖真实问题。
INTENTIONAL_BROKEN = {
    ("posts/zz-images-bundle/index.html", "/not-exist.png"),
}


def finish(status, passed, failed, detail=""):
    print("TEST-RESULT: " + json.dumps({
        "suite": "link-check", "status": status,
        "passed": passed, "failed": failed, "detail": detail,
    }, ensure_ascii=False))
    sys.exit(0 if status == "PASS" else 1)


if not os.path.isdir(ROOT):
    print(f"FAIL 目录不存在: {ROOT}")
    finish("FAIL", 0, 1, "public 目录不存在")

# 兼容 hugo --minify 输出（属性可能不带引号）
HREF_RE = re.compile(r'(?:href|src)=(?:"([^"]*)"|\'([^\']*)\'|([^\s>]+))')
# 兼容性修补（本轮）：扫描前**剥离**代码如下文与注释。
# 原因：行内 code span（单反引号）里的示例文本如 `href="{{ .Get 1 }}"`
# 会被裸正则当作真实链接，进而被判为死链 —— 这是**假红**，不是产品缺陷。
# `<pre>` / `<code>` 内的内容是供人阅读的示例，不是可导航链接；HTML 注释同理。
# 剥离后仍保留"扫描到 0 条链接即失败"的保护，避免检查失去对象后假绿。
CODE_OR_COMMENT_RE = re.compile(r'<code\b[^>]*>.*?</code>|<pre\b[^>]*>.*?</pre>|<!--.*?-->',
                                re.S | re.I)
HTML_FILES = []

for dirpath, _, files in os.walk(ROOT):
    for f in files:
        if f.endswith((".html", ".xml")):
            HTML_FILES.append(os.path.join(dirpath, f))

print(f"扫描 {len(HTML_FILES)} 个文件")
if not HTML_FILES:
    print("FAIL 未扫描到任何 HTML 文件，死链检查结果不可信")
    finish("FAIL", 0, 1, "0 个 HTML 文件")


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
    # 剥离 code/pre/注释后再提取链接（见 CODE_OR_COMMENT_RE 注释：避免代码示例被当链接）
    content = CODE_OR_COMMENT_RE.sub(" ", content)
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

# 过滤显式白名单（故意断链），并单独打印，保证不被静默掩盖
ignored = [p for p in problems if (p[0].replace(os.sep, "/"), p[1]) in INTENTIONAL_BROKEN]
problems = [p for p in problems if (p[0].replace(os.sep, "/"), p[1]) not in INTENTIONAL_BROKEN]
if ignored:
    print(f"  已知故意断链（压力测试数据，验证降级渲染）: {len(ignored)} 条")
    for src, url in ignored:
        print(f"    - {src} -> {url}")

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
    finish("PASS", checked, 0)
else:
    finish("FAIL", checked, len(problems), f"{len(problems)} 条死链")
