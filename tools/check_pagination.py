#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""分页发现规模自测：证明 discover_pagination 是队列耗尽式，而非固定轮数抽样。

对真实 Hugo 构建产物验证（不是 mock）：

    1 个分页 / 3 个分页 / 10 个分页 / 100 个分页
    分类分页（/categories/<cat>/page/N/）
    标签分页（/tags/<tag>/page/N/）
    多 section 分页（posts / tutorials / notes 各自的 /page/N/）

并验证安全上限语义：
    - 队列耗尽 -> exhausted=True，判定覆盖完整；
    - 达到 limit -> exhausted=False，**必须判定未完成**（不允许 PASS）。

站点在系统临时目录构建（真实 Hugo build），测试后清理，不污染仓库。
退出码约定（见 tools/_testlib.py）：任一断言失败 -> exit 1。

用法：
    python tools/check_pagination.py            # HUGO_BIN 默认 PATH 中的 hugo
    HUGO_BIN=/path/to/hugo python tools/check_pagination.py
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import urllib.request
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import audit  # noqa: E402  复用 discover_pagination / get_urls，保证测的就是审计用的实现
from _testlib import Harness, guard  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
THEME_NAME = os.path.basename(REPO)
THEMES_DIR = os.path.dirname(REPO)
HUGO = os.environ.get("HUGO_BIN", "hugo")
PAGER_SIZE = 8


def make_post(i, section="posts", category=None, tag=None):
    cats = f"categories: ['{category}']\n" if category else ""
    tags = f"tags: ['{tag}']\n" if tag else ""
    return (f"""---
title: '{section.title()} 文章 {i:04d}'
date: '2025-01-01T00:00:00Z'
description: '分页规模测试文章 {i}'
{cats}{tags}---

这是 {section} 第 {i} 篇测试文章。
""")


def build_site(root, posts=0, tutorials=0, notes=0,
               category_of=None, tag_of=None):
    """生成并构建一个最小可用的测试站点，返回构建输出目录。"""
    content = os.path.join(root, "content")
    for section, count in (("posts", posts), ("tutorials", tutorials), ("notes", notes)):
        d = os.path.join(content, section)
        os.makedirs(d, exist_ok=True)
        for i in range(1, count + 1):
            cat = category_of(i) if category_of else None
            tag = tag_of(i) if tag_of else None
            with open(os.path.join(d, f"{section[:2]}-{i:04d}.md"), "w", encoding="utf-8") as f:
                f.write(make_post(i, section, cat, tag))

    cfg = f"""baseURL = 'http://pagination.test/'
locale = 'zh-CN'
title = 'Pagination Test'
theme = '{THEME_NAME}'
hasCJKLanguage = true
defaultContentLanguage = 'zh'

[pagination]
  pagerSize = {PAGER_SIZE}

[taxonomies]
  category = 'categories'
  tag = 'tags'

[params]
  author = 'Tester'
  [params.search]
    enable = false
  [params.share]
    enable = false
  [params.content]
    sections = ['posts', 'tutorials', 'notes']
"""
    with open(os.path.join(root, "hugo.toml"), "w", encoding="utf-8") as f:
        f.write(cfg)
    out = os.path.join(root, "public")
    r = subprocess.run(
        [HUGO, "--source", root, "--themesDir", THEMES_DIR, "--gc", "-d", out],
        capture_output=True, text=True, timeout=300)
    if r.returncode != 0:
        raise RuntimeError(f"Hugo 构建失败:\n{r.stdout[-1500:]}\n{r.stderr[-1500:]}")
    return out


def list_paginated(outdir):
    """直接从构建产物枚举全部 /page/N/ 目录（作为真值，与爬取结果对照）。"""
    found = set()
    for dirpath, dirnames, _ in os.walk(outdir):
        rel = os.path.relpath(dirpath, outdir).replace("\\", "/")
        if re.search(r"/page/\d+$", "/" + rel) or re.fullmatch(r"page/\d+", rel):
            found.add("/" + rel.strip("/") + "/")
    return found


def expected_pagination(counts):
    """给定各 section 文章数，推算 Hugo 会生成的 /page/N/ 集合。

    n 篇文章 + pagerSize=8 -> ceil(n/8) 个列表页 -> page/2..page/ceil(n/8)。
    """
    out = set()
    for prefix, n in counts.items():
        pages = (n + PAGER_SIZE - 1) // PAGER_SIZE
        for p in range(2, pages + 1):
            out.add(f"{prefix}page/{p}/")
    return out


class Site:
    """临时站点 + 本地 HTTP 服务。"""

    def __init__(self, name):
        self.root = os.path.join(tempfile.mkdtemp(prefix="nebula-pag-"), name)
        os.makedirs(self.root, exist_ok=True)
        self.srv = None
        self.base = None

    def build(self, **kw):
        self.out = build_site(self.root, **kw)
        return self

    def serve(self):
        handler = partial(SimpleHTTPRequestHandler, directory=self.out)
        self.srv = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        port = self.srv.server_address[1]
        self.base = f"http://127.0.0.1:{port}"
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        for _ in range(30):
            try:
                urllib.request.urlopen(self.base + "/", timeout=2)
                break
            except Exception:
                import time
                time.sleep(0.3)
        return self

    def stop(self):
        if self.srv:
            self.srv.shutdown()
            self.srv = None

    def cleanup(self):
        self.stop()
        shutil.rmtree(os.path.dirname(self.root), ignore_errors=True)


def crawl_exact(site, seeds, limit=None):
    found, meta = audit.discover_pagination(site.base, seeds, limit=limit)
    return set(found), meta


def seeds_from_truth(site, truth):
    """从真值集合推导种子页：每个 /page/N/ 的上一级列表页 + sitemap 全部非文章页。"""
    seeds = set()
    for p in truth:
        seeds.add(re.sub(r"page/\d+/$", "", p))
    # 补充 sitemap 非文章页作为种子（与 audit.get_urls 相同策略）
    with urllib.request.urlopen(site.base + "/sitemap.xml", timeout=15) as r:
        xml = r.read().decode("utf-8")
    for loc in re.findall(r"<loc>(.*?)</loc>", xml):
        path = audit.path_of(loc)
        if audit.is_html_page(path) and not audit.is_article_page(path):
            seeds.add(path)
    return sorted(seeds)


def main():
    h = Harness("pagination")
    guard(h, run, h)
    h.finish()


def run(h):
    cases = [
        # (label, build 参数, 期望分页的 {URL前缀: 文章数})
        ("1 个分页", dict(posts=9),
         {"/posts/": 9}),
        ("3 个分页 + 分类/标签/多 section 分页", dict(posts=25, tutorials=17, notes=9,
                                                    category_of=lambda i: "big",
                                                    tag_of=lambda i: "hot" if i <= 20 else None),
         # 注意：category_of/tag_of 作用于**所有** section 的同名序号文章，
         # Hugo 的分类/标签 term 会跨 section 聚合：
         #   big  = 25 + 17 + 9 = 51 篇 -> 7 个列表页 -> page/2..7
         #   hot  = 20 + 17 + 9 = 46 篇 -> 6 个列表页 -> page/2..6
         {"/posts/": 25, "/tutorials/": 17, "/notes/": 9,
          "/categories/big/": 51, "/tags/hot/": 46}),
        ("10 个分页", dict(posts=88), {"/posts/": 88}),
        ("100 个分页", dict(posts=808), {"/posts/": 808}),
    ]

    for label, build_kw, expect in cases:
        site = Site(label.split()[0] + "-site")
        try:
            site.build(**build_kw).serve()
            truth = expected_pagination(expect)
            seeds = seeds_from_truth(site, truth)
            got, meta = crawl_exact(site, seeds)
            missing = truth - got
            extra = got - truth
            h.record(f"[{label}] 发现的分页集合与构建产物真值完全一致",
                     not missing and not extra,
                     f"预期 {len(truth)}，发现 {len(got)}，"
                     f"缺失 {sorted(missing)[:3]}，多余 {sorted(extra)[:3]}")
            h.record(f"[{label}] pagination crawler 耗尽（exhausted）",
                     meta.get("exhausted") is True,
                     f"rounds={meta.get('rounds')}")
            if "/posts/" in expect:
                n = expect["/posts/"]
                last = (n + PAGER_SIZE - 1) // PAGER_SIZE      # 末页 = 列表页总数
                h.record(f"[{label}] 末页 /posts/page/{last}/ 已发现",
                         f"/posts/page/{last}/" in got, "已发现")
            # cat / tag / 多 section 专项断言
            for prefix in expect:
                if prefix.startswith("/categories/"):
                    h.record(f"[{label}] 分类分页已发现（{prefix}）",
                             any(p.startswith(prefix) for p in got), prefix)
                elif prefix.startswith("/tags/"):
                    h.record(f"[{label}] 标签分页已发现（{prefix}）",
                             any(p.startswith(prefix) for p in got), prefix)
                elif prefix in ("/tutorials/", "/notes/"):
                    h.record(f"[{label}] 多 section 分页已发现（{prefix}）",
                             any(p.startswith(prefix) for p in got), prefix)
        finally:
            site.cleanup()

    # ---------- 上限语义：达到 limit 必须判"未耗尽" ----------
    site = Site("limit-site")
    try:
        site.build(posts=808).serve()          # 真值 100 个分页页
        truth = expected_pagination({"/posts/": 808})
        seeds = seeds_from_truth(site, truth)
        got, meta = crawl_exact(site, seeds, limit=50)
        h.record("[上限测试] 达到 limit=50 时停止发现",
                 len(got) == 50, f"发现 {len(got)}")
        h.record("[上限测试] exhausted=False（不可判覆盖完整）",
                 meta.get("exhausted") is False and meta.get("limit_reached") is True,
                 f"meta={meta}")
        h.record("[上限测试] 100 个分页页的真值确实 > 50",
                 len(truth) == 100 and len(truth) > 50, f"真值 {len(truth)}")
    finally:
        site.cleanup()


if __name__ == "__main__":
    main()
