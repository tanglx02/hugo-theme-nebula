#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""pagination crawler 的"文章页判定"与"分页路径可配置"专项回归（v1.0.9 P2）。

背景
----
* 旧判定 `re.fullmatch(r"/[^/]+/[^/]+/", path)` 会把 `/categories/linux/`、
  `/tags/hugo/` 这些**两级 term 页**当成文章页，于是它们从 crawl 种子里被剔除，
  这些名单页自己的分页可能就漏掉了。
  新判定基于 `params.content.sections`：只有 `/<section>/<slug>/` 才是文章页。

* `page` 不能再写死：Hugo 支持 `[pagination] path = "p"`（已实测会在
  `/posts/p/2/` 生成分页）。crawler 必须能读取/推断当前的分页路径片段。

本测试两部分：
    1. 纯逻辑（不需要 Hugo）：各类 URL 的判定表 + 证明旧规则确实会误判
    2. 真实构建（需要 Hugo）：默认路径与自定义路径（"p"）两种站点，
       验证 crawler 发现结果 == 构建产物真值；并反证"写死 page"会失效

用法：
    python tools/check_article_classification.py
环境变量：HUGO_BIN（默认 PATH 中的 hugo）
退出码约定（见 tools/_testlib.py）：任一断言失败 / 构建失败 -> exit 1。
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
import audit  # noqa: E402
from _testlib import Harness, guard  # noqa: E402
from html_inventory import scan as scan_inventory  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
THEME_NAME = os.path.basename(REPO)
THEMES_DIR = os.path.dirname(REPO)
HUGO = os.environ.get("HUGO_BIN", "hugo")
PAGER_SIZE = 5

# 旧实现（保留用于回归证明：它确实会把 term 页误判成文章页）
LEGACY_RE = re.compile(r"/[^/]+/[^/]+/")

H = Harness("article-classification")


def set_sections_env(sections):
    """切换 audit.content_sections() 解析出的内容 section 列表。"""
    key = "AUDIT_CONTENT_SECTIONS"
    old = os.environ.get(key)
    os.environ[key] = ",".join(sections)
    return old


def restore_env(key, old):
    if old is None:
        os.environ.pop(key, None)
    else:
        os.environ[key] = old


# ---------------------------------------------------------------- ① 纯逻辑
def check_table():
    # (URL, 期望是否文章页, 说明)
    cases = [
        ("/posts/hello-world/", True, "posts 文章页"),
        ("/tutorials/hugo-start/", True, "tutorials 文章页"),
        ("/notes/daily-1/", True, "notes 文章页"),
        ("/projects/app/", True, "projects 文章页"),
        ("/categories/linux/", False, "分类 term 页"),
        ("/tags/hugo/", False, "标签 term 页"),
        ("/categories/", False, "分类首页"),
        ("/tags/", False, "标签首页"),
        ("/archives/", False, "归档页"),
        ("/page/2/", False, "根分页"),
        ("/posts/page/2/", False, "posts 分页"),
        ("/categories/linux/page/2/", False, "分类 term 分页"),
        ("/tags/hugo/page/2/", False, "标签 term 分页"),
        ("/", False, "首页"),
        ("/about/", False, "单页（不在 content sections 内）"),
        ("/search/", False, "非 HTML endpoint"),
    ]
    for url, expect, label in cases:
        got = audit.is_article_page(url, page_token="page")
        H.record(f"判定 {url} -> {'文章页' if expect else '非文章页'}（{label}）",
                 got == expect, f"实际 {'文章页' if got else '非文章页'}")

    # 回归证明：旧规则会把 term 页误判成文章页 —— 这正是要修的缺陷
    misfired = [u for u in ("/categories/linux/", "/tags/hugo/", "/tags/运维/")
                if LEGACY_RE.fullmatch(u) and "/page/" not in u]
    H.record("回归证据：旧规则 /[^/]+/[^/]+/ 确实会误判 term 页为文章页",
             len(misfired) == 3, f"误判 {len(misfired)}/3")

    # 自定义 content sections 必须生效（不能写死 posts/tutorials/notes/projects）
    old = set_sections_env(["blog"])
    try:
        H.record("自定义 sections=['blog']：/blog/x/ 是文章页",
                 audit.is_article_page("/blog/x/") is True, "/blog/x/")
        H.record("自定义 sections=['blog']：/posts/x/ 不再是文章页",
                 audit.is_article_page("/posts/x/") is False, "/posts/x/")
    finally:
        restore_env("AUDIT_CONTENT_SECTIONS", old)

    old = set_sections_env(["posts"])
    try:
        H.record("默认单 section=['posts']：/tutorials/x/ 不是文章页",
                 audit.is_article_page("/tutorials/x/") is False, "/tutorials/x/")
    finally:
        restore_env("AUDIT_CONTENT_SECTIONS", old)

    # 分页路径片段可配置时，/posts/p/2/ 形状也不能被判成文章页
    H.record("自定义 pagination path='p'：/posts/p/ 不算文章页",
             audit.is_article_page("/posts/p/", page_token="p") is False, "/posts/p/")


# ---------------------------------------------------------------- ② 真实构建
def make_post(i, section, category, tag):
    return f"""---
title: '{section.title()} 文章 {i:02d}'
date: '2025-02-{(i % 28) + 1:02d}T00:00:00Z'
categories: ['{category}']
tags: ['{tag}']
description: 'classification test {i}'
---

这是 {section} 的第 {i} 篇测试文章。
"""


def build_site(root, posts=12, tutorials=8, pagination_path=None):
    for sec, n in (("posts", posts), ("tutorials", tutorials)):
        d = os.path.join(root, "content", sec)
        os.makedirs(d, exist_ok=True)
        for i in range(1, n + 1):
            cat = "cat-a" if i % 2 else "cat-b"
            tag = "tag-hot" if i % 3 else "tag-cold"
            with open(os.path.join(d, f"{sec[:2]}-{i:02d}.md"), "w", encoding="utf-8") as f:
                f.write(make_post(i, sec, cat, tag))
    cfg = f"""baseURL = 'http://classification.test/'
locale = 'zh-CN'
title = 'Classification Test'
theme = '{THEME_NAME}'
hasCJKLanguage = true
defaultContentLanguage = 'zh'

[pagination]
  pagerSize = {PAGER_SIZE}
{("  path = '" + pagination_path + "'") if pagination_path else ""}

[taxonomies]
  category = 'categories'
  tag = 'tags'

[outputs]
  home = ['HTML', 'JSON']

[params]
  author = 'Tester'
  [params.content]
    sections = ['posts', 'tutorials']
  [params.search]
    enable = false
  [params.share]
    enable = false
"""
    with open(os.path.join(root, "hugo.toml"), "w", encoding="utf-8") as f:
        f.write(cfg)
    out = os.path.join(root, "public")
    p = subprocess.run([HUGO, "--source", root, "--themesDir", THEMES_DIR,
                        "--gc", "-d", out],
                       capture_output=True, text=True, encoding="utf-8",
                       errors="ignore", timeout=300)
    if p.returncode != 0:
        raise RuntimeError(f"Hugo 构建失败: {(p.stderr or p.stdout)[-800:]}")
    return out


def serve(outdir):
    handler = partial(SimpleHTTPRequestHandler, directory=outdir)
    srv = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    port = srv.server_address[1]
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{port}"
    for _ in range(30):
        try:
            urllib.request.urlopen(base + "/", timeout=2)
            break
        except Exception:
            import time
            time.sleep(0.3)
    return srv, base


def truth_paginated(outdir, token):
    """文件系统真值：所有 /.../<token>/<N>/ 目录（含别名页 /<token>/1/）。"""
    found = set()
    pat = re.compile(r"/" + re.escape(token) + r"/\d+$")
    for dirpath, _, _ in os.walk(outdir):
        rel = os.path.relpath(dirpath, outdir).replace("\\", "/")
        if pat.search("/" + rel):
            found.add("/" + rel.strip("/") + "/")
    return found


def check_real_site(label, pagination_path, expect_token):
    root = tempfile.mkdtemp(prefix=f"nebula-cls-{label}-")
    srv = None
    try:
        out = build_site(root, pagination_path=pagination_path)
        inv = scan_inventory(out)
        expected = list(inv["expected_html_urls"])
        alias = set(inv.get("urls_by_class", {}).get("alias", []))
        old_env = set_sections_env(["posts", "tutorials"])
        try:
            # ① 从构建产物反推分页路径片段
            detected = audit.detect_pagination_token(expected)
            H.record(f"[{label}] 从构建产物反推 pagination.path = {expect_token}",
                     detected == expect_token, f"反推得到 {detected}")

            # ② 真实 URL 上的分类正确性
            secs = ("posts", "tutorials")
            arts = [p for p in expected if audit.is_article_page(p, secs, expect_token)]
            terms = [p for p in expected
                     if re.fullmatch(r"/(categories|tags)/[^/]+/", p)]
            H.record(f"[{label}] 文章页全部形如 /<section>/<slug>/",
                     arts and all(p.startswith(("/posts/", "/tutorials/"))
                                  and p.count("/") == 3 for p in arts),
                     f"{len(arts)} 个文章页")
            H.record(f"[{label}] 区分/categories/<term>/、/tags/<term>/ 均不是文章页",
                     bool(terms) and all(not audit.is_article_page(p, secs, expect_token)
                                         for p in terms),
                     f"{len(terms)} 个 term 页")

            # ③ crawler 发现结果 == 文件系统真值
            #    种子必须**排除分页页本身**：它们是 BFS 的产物而不是起点，
            #    放进去会让新发现的分页全部命中 visited，discovered 恒为 0。
            seeds = [p for p in expected
                     if not audit.is_article_page(p, secs, expect_token)
                     and not audit.is_pagination_page(p, expect_token)
                     and p not in alias]
            H.record(f"[{label}] crawl 种子包含分类/标签 term 页（不再被当成文章页剔除）",
                     any(p.startswith("/categories/") for p in seeds)
                     and any(p.startswith("/tags/") for p in seeds),
                     f"{len(seeds)} 个种子")
            H.record(f"[{label}] crawl 种子不含分页页（否则交叉验证退化为找不到任何分页）",
                     not [p for p in seeds
                          if audit.is_pagination_page(p, expect_token)],
                     f"{len(seeds)} 个种子")

            srv, base = serve(out)
            got, meta = audit.discover_pagination(base, seeds, page_token=expect_token)
            # 真值：构建产物里所有分页页；别名分页页（/page/1/ 形）按设计不被任何
            # 页面链接，只能由 inventory 直接覆盖，不能要求 crawler 爬到
            truth = truth_paginated(out, expect_token) - set(
                p for p in alias if audit.is_pagination_page(p, expect_token))
            missing = sorted(truth - set(got))
            extra = sorted(set(got) - truth)
            H.record(f"[{label}] crawler 发现结果与构建产物真值一致",
                     not missing and not extra,
                     f"真值 {len(truth)} / 发现 {len(got)}；缺失 {missing[:3]}；多余 {extra[:3]}")
            H.record(f"[{label}] crawler 耗尽（exhausted）且零失败",
                     meta.get("exhausted") is True
                     and not meta.get("discovery_failures"),
                     f"rounds={meta.get('rounds')} failures={len(meta.get('discovery_failures') or [])}")
            H.record(f"[{label}] 至少发现 2 个以上的分页页（规模足够有说服力）",
                     len(got) >= 3, f"{len(got)} 个")

            # ④ 反证：写死 page 时，自定义路径站点一个分页都发现不了
            if expect_token != "page":
                wrong, wrong_meta = audit.discover_pagination(
                    base, seeds, page_token="page")
                H.record(f"[{label}] 反证：写死 page 会漏掉全部自定义路径分页",
                         len(wrong) == 0, f"写死 page 只发现 {len(wrong)} 个"
                         f"（真实 {len(truth)} 个）")
                H.record(f"[{label}] 反证：写死 page 会『假绿』（队列也耗尽，但一个分页都没发现）",
                         wrong_meta.get("exhausted") is True and len(wrong) == 0,
                         f"exhausted={wrong_meta.get('exhausted')} discovered={len(wrong)}"
                         f"（真实 {len(truth)} 个）——必须以构建产物为准推断 token")
        finally:
            restore_env("AUDIT_CONTENT_SECTIONS", old_env)
    finally:
        if srv:
            srv.shutdown()
        shutil.rmtree(root, ignore_errors=True)


def run(h):
    check_table()
    check_real_site("page", None, "page")
    check_real_site("p", "p", "p")


def main():
    guard(H, run, H)
    H.finish()


if __name__ == "__main__":
    main()
