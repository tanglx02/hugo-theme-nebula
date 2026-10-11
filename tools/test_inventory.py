#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""inventory 自身一致性测试：URL 规范化 + 冲突保护。

在临时目录里构造真实的构建产物形态，验证：

    1. index.html        -> /
    2. about/index.html  -> /about/
    3. 404.html          -> /404.html（非 index 命名）
    4. 普通 .html 文件     -> /x.html
    5. /page/N/index.html-> /posts/page/2/
    6. 中文目录名          -> percent-encoded
    7. 空格目录名          -> %20
    8. 已编码文件名        -> 保持编码（不二次编码）
    9. URL 冲突（两个文件 normalize 成同一 URL）-> exit 1
   10. 分类 site/alias/error 正确
   11. 加号路径（authors/c++-工程师）-> 字面 "+"（TEST-DEFECT-R3-010）
   12. 已编码 %2B 不二次编码、也不被解码
   13. c++/ 与 c%2B%2B/ 两个不同目录不折叠为同一 URL

跨平台：路径统一走 os.path 与正斜杠，Windows / Linux 行为一致。

退出码约定（见 tools/_testlib.py）：任一断言失败 -> exit 1。
"""
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import html_inventory as inv_mod  # noqa: E402
from _testlib import Harness, guard  # noqa: E402

REPO = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))


def write(root, rel, content="<html><body>x</body></html>"):
    p = os.path.join(root, rel.replace("/", os.sep))
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        f.write(content)
    return p


def run(h):
    tmp = tempfile.mkdtemp(prefix="nebula-inv-")
    try:
        # ---------- 1-8 规范化 ----------
        write(tmp, "index.html")
        write(tmp, "about/index.html")
        write(tmp, "404.html")
        write(tmp, "plain.html")
        write(tmp, "posts/page/2/index.html")
        write(tmp, "posts/page/10/index.html")
        write(tmp, "分类 1/index.html")          # 中文 + 空格
        write(tmp, "%E5%B7%B2%E7%BC%96%E7%A0%81/index.html")   # 已编码名
        # TEST-DEFECT-R3-010：Hugo 对 taxonomy term 保留字面 "+"。
        # 作者 "C++ 工程师" 的真实产物目录就是 `authors/c++-工程师/`（见
        # check_author_pages ON5），sitemap / 页面链接 / 浏览器地址栏均为字面 "+"，
        # inventory 必须与该形态一致（此前被编成 %2B 导致全站审计假差异）。
        write(tmp, "authors/c++-工程师/index.html")   # 加号 + 中文混合
        write(tmp, "tags/C++与高并发/index.html")     # 加号 + 中文（无空格）
        # 已编码目录名里的 %2B 必须保持原样（% 在 safe 中，不二次编码）
        write(tmp, "p%2Bq/index.html")
        # R3-010 不折叠断言的夹具：字面加号目录 vs 已编码目录（磁盘上是两个不同目录）
        write(tmp, "c++/index.html")
        write(tmp, "c%2B%2B/index.html")
        write(tmp, "alias1/index.html",           # alias 形态（meta refresh）
               '<html><head><meta http-equiv=refresh content="0;url=/"></head></html>')
        inv = inv_mod.scan(tmp)
        urls = set(inv["expected_html_urls"])

        for expect, label in (
            ("/", "根 index.html"),
            ("/about/", "嵌套 index.html"),
            ("/404.html", "非 index 命名的 404.html"),
            ("/plain.html", "普通 .html 文件"),
            ("/posts/page/2/", "/page/N/index.html"),
            ("/posts/page/10/", "/page/10/"),
            ("/%E5%88%86%E7%B1%BB%201/", "中文 + 空格目录"),
            ("/%E5%B7%B2%E7%BC%96%E7%A0%81/", "已编码目录名（不二次编码）"),
            # 加号保留字面形态（Hugo 真实输出），中文部分照常 percent-encode
            ("/authors/c++-%E5%B7%A5%E7%A8%8B%E5%B8%88/", "加号作者路径（R3-010）"),
            ("/tags/C++%E4%B8%8E%E9%AB%98%E5%B9%B6%E5%8F%91/", "加号 + 中文混合路径"),
            # 已编码的 %2B 原样保留，不得变成 %252B 也不得解码成 +
            ("/p%2Bq/", "已编码 %2B 目录名（不二次编码、不解码）"),
        ):
            h.record(f"规范化：{label} -> {expect}", expect in urls,
                     "" if expect in urls else f"实际集合缺 {expect}")

        # 两个不同的文件不得被规范化成同一个 URL（R3-010 回归）：
        # `c++/`（Hugo 字面加号形态）与 `c%2B%2B/`（已编码形态）必须得到
        # 两个不同的规范化字符串 —— 若把 + 编成 %2B，二者会被折叠成同一 URL。
        h.record("规范化：c++/ 与 c%2B%2B/ 不折叠为同一 URL",
                 "/c++/" in urls and "/c%2B%2B/" in urls,
                 f"实际: {sorted(u for u in urls if u.startswith('/c'))}")

        h.record("inventory 自身无 URL 冲突（14 个文件 -> 14 个 URL）",
                 inv["public_html_files"] == len(urls) == 14,
                 f"files={inv['public_html_files']} urls={len(urls)}")

        # ---------- 10 分类 ----------
        by = inv["by_class"]
        h.record("分类正确：site / alias / error",
                 by.get("site", 0) == 12 and by.get("alias", 0) == 1 and by.get("error", 0) == 1,
                 str(by))

        # ---------- 9 冲突 ----------
        # 构造冲突：foo/index.html 与 foo.html 之外，再造一个大小写/编码等价形式
        # 最直接的冲突：a/index.html 与 a/index.html 之外无法制造同名文件，
        # 因此用「已编码名」与「解码名」构造等价冲突：
        #   "x y/index.html" -> /x%20y/
        #   "x%20y/index.html" -> /x%2520y/   （不会冲突）
        # 换一种：Windows 上文件名不区分大小写无法可靠制造，
        # 用「目录名末尾的 index.html 变体」：deep/index.html 与 deep/../deep/index.html
        # 不现实。改用直接构造：同名文件在两个不同子目录经 normalize 后相同是不可能的，
        # 因此这里验证 detect 逻辑本身：临时 monkeypatch normalize 使其产生碰撞。
        orig = inv_mod.normalize_url
        try:
            inv_mod.normalize_url = lambda rel: "/same/"     # 全部映射到同一 URL
            write(tmp, "collide/index.html")
            write(tmp, "collide2/index.html")
            raised = False
            try:
                inv_mod.scan(tmp)
            except inv_mod.InventoryCollision as e:
                raised = True
                n = len(e.collisions)
                files = {c[1] for c in e.collisions} | {c[2] for c in e.collisions}
            h.record("URL 冲突时抛出 InventoryCollision 并可定位文件",
                     raised, f"冲突组数={n if raised else 0}")
            h.record("冲突记录包含双方文件路径",
                     raised and n >= 1 and len(files) >= 2,
                     f"涉及 {len(files) if raised else 0} 个文件")
        finally:
            inv_mod.normalize_url = orig
            for d in ("collide", "collide2"):
                shutil.rmtree(os.path.join(tmp, d.replace("/", os.sep)), ignore_errors=True)

        # 恢复后应恢复正常
        inv2 = inv_mod.scan(tmp)
        h.record("冲突排除后 inventory 恢复正常",
                 inv2["public_html_files"] == inv["public_html_files"],
                 f"{inv2['public_html_files']} 个文件")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main_h = Harness("inventory")
    guard(main_h, run, main_h)
    main_h.finish()
