#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""构建产物 HTML inventory —— Release 全站审计的真值来源。

为什么需要它
------------
`sitemap.xml` 是 **SEO 索引**，不是构建产物清单：Hugo 允许页面通过
`sitemap.disable` 把它排除出 sitemap。因此"sitemap + pagination = 全站 HTML"
这个等式在逻辑上不成立 —— 一个页面可以完全不出现在 sitemap 里，却真实存在于
构建产物中。

真正的全站真值只能是**文件系统 inventory**：构建完成后 public/ 下每一个
`.html` 文件都代表一个必须被浏览器审计过的 URL。

URL 规范化
----------
    public/index.html                    -> /
    public/about/index.html              -> /about/
    public/posts/a/index.html            -> /posts/a/
    public/posts/page/2/index.html       -> /posts/page/2/
    public/404.html                      -> /404.html   （非 index 命名，原样保留）

分类（仅用于报告，**不排除任何页面**）
------------------------------------
    site     正常内容页
    alias    Hugo 生成的 meta-refresh 冗余别名页（/page/1/ 等）
    error    404.html 等错误页
    other    其它命名不规则但仍需审计的 HTML

使用：
    python3 tools/html_inventory.py public            # 打印统计
    python3 tools/html_inventory.py public --json out.json
"""
import argparse
import json
import os
import re
import sys

# 这些路径即便出现在 public/ 下也不是站点页面（当前无预留，每项必须给理由）
EXCLUDE_PATHS = {
    # 例：".well-known/acme-challenge/index.html": "证书验证，非页面"
}


def normalize_url(rel_path):
    """把 public 下的相对路径规范化为 URL（percent-encoded）。

    必须 percent-encode：中文路径直接交给 urlopen 会抛
    UnicodeEncodeError（HTTP 请求行只能是 ASCII），且浏览器实际请求的
    也是编码后的形式 —— 统一编码后，inventory / audit / HTML quality
    三方比较的才是同一个字符串。
    """
    from urllib.parse import quote
    p = rel_path.replace("\\", "/").lstrip("/")
    if p.endswith("/index.html"):
        p = p[: -len("index.html")]
    elif p == "index.html":
        p = ""
    # safe 里包含 "%"：文件系统里可能已存在 percent-encoded 的目录名
    # （Hugo 某些输出），若不保留会被二次编码成 %25...
    return "/" + quote(p, safe="/~!*()'-._%")


def classify(url, content):
    if url == "/404.html" or url.endswith("/404.html"):
        return "error"
    # Hugo 的分页别名页：只有 head 里的 meta refresh + canonical，没有正文
    if "<meta http-equiv=refresh" in content.replace('"', "").replace("'", "") \
            or re.search(r'http-equiv=["\']?refresh', content):
        return "alias"
    return "site"


class InventoryCollision(Exception):
    """两个不同 HTML 文件规范化成同一 URL —— inventory 失去可信度。"""

    def __init__(self, collisions, build_dir):
        self.collisions = collisions
        self.build_dir = build_dir
        super().__init__(f"{len(collisions)} 组 URL 冲突")


def scan(build_dir, read_content=True):
    """扫描构建目录，返回 inventory dict。"""
    if not os.path.isdir(build_dir):
        raise SystemExit(f"构建目录不存在: {build_dir}")
    files = []
    for dirpath, _, names in os.walk(build_dir):
        for n in names:
            if n.endswith(".html"):
                full = os.path.join(dirpath, n)
                rel = os.path.relpath(full, build_dir).replace("\\", "/")
                files.append((rel, full))
    files.sort()

    urls, by_class, excluded = [], {}, []
    owner = {}          # url -> 产生它的文件（用于检测 normalize 冲突）
    collisions = []    # [(url, file_a, file_b), ...]
    for rel, full in files:
        url = normalize_url(rel)
        if rel in EXCLUDE_PATHS:
            excluded.append((url, EXCLUDE_PATHS[rel]))
            continue
        if url in owner and owner[url] != rel:
            # 两个不同文件规范化成同一 URL —— inventory 本身就不可信，必须失败
            collisions.append((url, owner[url], rel))
            continue
        owner[url] = rel
        content = ""
        if read_content:
            try:
                with open(full, encoding="utf-8") as f:
                    content = f.read()
            except UnicodeDecodeError:
                content = ""
        kind = classify(url, content)
        urls.append(url)
        by_class.setdefault(kind, []).append(url)
    if collisions:
        raise InventoryCollision(collisions, build_dir)
    return {
        "build_dir": os.path.abspath(build_dir),
        "public_html_files": len(files),
        "expected_html_urls": urls,
        "expected_count": len(urls),
        "by_class": {k: len(v) for k, v in sorted(by_class.items())},
        # other = 未落入 site/alias/error 任一分类的页面（当前分类已全覆盖，恒为 0；
        # 保留该字段以便将来新增分类时仍能看到"未归类"数量）
        "other_count": len([u for u in urls
                             if not any(u in v for v in by_class.values())]),
        "class_samples": {k: v[:2] for k, v in sorted(by_class.items())},
        "urls_by_class": {k: sorted(v) for k, v in sorted(by_class.items())},
        "excluded": excluded,
    }


def report(inv):
    print(f"PUBLIC HTML FILES = {inv['public_html_files']}")
    print(f"EXPECTED HTML URLS = {inv['expected_count']}")
    print("分类明细（仅用于报告，不排除任何页面）:")
    for k, v in inv["by_class"].items():
        samples = inv["class_samples"].get(k, [])
        print(f"  - {k:8s} {v:4d}  例: {', '.join(samples[:2])}")
    if inv["excluded"]:
        print("显式登记的排除项:")
        for url, why in inv["excluded"]:
            print(f"  - {url}  ({why})")
    else:
        print("显式登记的排除项: 无（未排除任何 HTML）")
    aliases = inv["by_class"].get("alias", 0)
    if aliases:
        print(f"提示: {aliases} 个 alias 页是 Hugo 生成的 meta-refresh 冗余别名（如 /page/1/），"
              f"仍必须审计")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("build_dir", nargs="?", default="public")
    ap.add_argument("--json", help="把 inventory 写入该 json 文件")
    args = ap.parse_args()
    try:
        inv = scan(args.build_dir)
    except InventoryCollision as e:
        print(f"FAIL  构建产物存在 {len(e.collisions)} 组 URL 冲突"
              f"（不同 HTML 文件规范化成同一 URL，inventory 已不可信）:")
        for url, a, b in e.collisions[:10]:
            print(f"    - {url}")
            print(f"        {a}")
            print(f"        {b}")
        sys.exit(1)
    report(inv)
    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(inv, f, ensure_ascii=False, indent=1)
        print(f"inventory 已写入 {args.json}")


if __name__ == "__main__":
    main()
