#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""站点级 SEO / feed / 测试数据泄漏检查（仅标准库）。

检查构建产物：

    - robots.txt 存在且含 User-agent 与 Sitemap 行
    - sitemap.xml 可解析（XML），每个 <loc> 都是 http(s) URL
    - RSS（/index.xml）可解析：<rss> 根元素、channel title/link 非空
    - 文章页（/posts/*/）均有非空 meta description
    - 测试数据泄漏：构建产物不得包含分页自测工具的标记内容
      （NEBULA-PAGTEST 文案 / pagination.test baseURL），
      防止测试工具生成的临时站点内容混进真实构建。

per-page 的 JSON-LD / canonical / og:url / title 检查在 check_html_quality.py。

退出码约定（见 tools/_testlib.py）：任一断言失败 -> exit 1。

用法：
    python tools/check_seo.py <build_dir>
"""
import os
import re
import sys
import xml.etree.ElementTree as ET

from _testlib import Harness, guard

REPO = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
# 默认路径与 check_index / check_features 统一（TEST-DEFECT-016：基准不一致会让
# 手工运行结果不可比）
DIR = sys.argv[1] if len(sys.argv) > 1 else os.path.join(REPO, "public")

LEAK_MARKS = ("NEBULA-PAGTEST", "pagination.test")


def run(h):
    if not os.path.isdir(DIR):
        h.fatal_error("构建目录不存在", DIR)
        return

    # ---------- robots.txt ----------
    robots_p = os.path.join(DIR, "robots.txt")
    robots_ok = False
    if os.path.exists(robots_p):
        txt = open(robots_p, encoding="utf-8").read()
        robots_ok = ("User-agent" in txt) and ("Sitemap:" in txt)
    h.record("robots.txt 存在且含 User-agent / Sitemap", robots_ok)

    # ---------- sitemap.xml ----------
    sm_ok, sm_count, bad_locs = False, 0, []
    try:
        tree = ET.parse(os.path.join(DIR, "sitemap.xml"))
        ns = {"s": tree.getroot().tag.split("}")[0].strip("{")} if "}" in tree.getroot().tag else {}
        locs = [e.text or "" for e in tree.iter() if e.tag.endswith("loc")]
        sm_count = len(locs)
        bad_locs = [u for u in locs if not u.startswith(("http://", "https://"))]
        sm_ok = sm_count > 0 and not bad_locs
    except Exception as e:
        bad_locs.append(str(e)[:80])
    h.record("sitemap.xml 可解析且 URL 全部合法", sm_ok, f"{sm_count} 个 URL")

    # ---------- RSS ----------
    rss_ok, rss_items = False, 0
    try:
        root = ET.parse(os.path.join(DIR, "index.xml")).getroot()
        if root.tag == "rss":
            ch = root.find("channel")
            title = (ch.findtext("title") or "").strip() if ch is not None else ""
            link = (ch.findtext("link") or "").strip() if ch is not None else ""
            rss_items = len(root.findall(".//item"))
            rss_ok = bool(title) and bool(link)
    except Exception:
        rss_ok = False
    h.record("RSS（/index.xml）可解析且 channel 信息完整", rss_ok, f"{rss_items} 个 item")

    # ---------- 文章页 meta description ----------
    # 旧实现：posts/ 不存在时循环直接跳过 -> "缺失 0 篇" -> 真空 PASS（TEST-DEFECT-007）。
    # 现在改为：优先 posts/，否则扫描所有 */*/index.html 的文章页；且**至少检查到 1 页**。
    missing_desc = []
    candidates = []
    posts_dir = os.path.join(DIR, "posts")
    if os.path.isdir(posts_dir):
        for name in sorted(os.listdir(posts_dir)):
            page = os.path.join(posts_dir, name, "index.html")
            if os.path.isfile(page):
                candidates.append(f"/posts/{name}/")
    else:
        for dirpath, _, names in os.walk(DIR):
            if "index.html" not in names:
                continue
            rel = os.path.relpath(dirpath, DIR).replace("\\", "/")
            if rel.count("/") == 1:                 # 形如 <section>/<slug>
                candidates.append(f"/{rel}/")
    for url in candidates:
        page = os.path.join(DIR, url.strip("/"), "index.html")
        html = open(page, encoding="utf-8").read()
        # minify 会去掉属性引号（name=description），两种形态都接受
        if '<meta name="description"' not in html and \
                re.search(r'<meta\s+name=description[\s>]', html) is None:
            missing_desc.append(url)
    if not candidates:
        h.fatal_error("没有扫描到任何文章页（构建产物不完整，meta description 检查会空转）",
                      f"posts 目录存在={os.path.isdir(posts_dir)}；考察路径={DIR}")
    else:
        h.record("文章页均有 meta description", not missing_desc,
                 f"检查 {len(candidates)} 页，缺失 {len(missing_desc)}: {missing_desc[:4]}")

    # ---------- 测试数据泄漏 ----------
    leaks = []
    scanned = 0
    for dirpath, _, names in os.walk(DIR):
        for n in names:
            p = os.path.join(dirpath, n)
            if not n.endswith((".html", ".json", ".xml", ".txt")):
                continue
            try:
                data = open(p, encoding="utf-8").read()
            except UnicodeDecodeError:
                continue
            scanned += 1
            for mark in LEAK_MARKS:
                if mark in data:
                    leaks.append(f"{os.path.relpath(p, DIR)} :: {mark}")
    if scanned == 0:
        h.fatal_error("泄漏扫描没有读到任何文件（构建产物缺失，检查会空转）", DIR)
    else:
        h.record("无测试数据泄漏（分页自测标记 / 临时 baseURL）", not leaks,
                 f"{len(leaks)} 处" if leaks else f"干净（扫描 {scanned} 个文件）")


if __name__ == "__main__":
    main_h = Harness("seo")
    guard(main_h, run, main_h)
    main_h.finish()
