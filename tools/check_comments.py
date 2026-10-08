#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""评论系统验证：provider 渲染、locale 跟随站点语言、关闭时不加载第三方资源。

验证方式为**真实 Hugo 构建**（exampleSite + 配置 overlay），检查构建产物 HTML：

    1. 评论关闭（默认）：全站 HTML 不得出现任何第三方评论资源 URL
       （giscus.app / unpkg.com / cdn.jsdelivr.net / disqus.com）
    2. giscus：data-lang 跟随站点语言（zh-CN 站 -> zh-CN，en 页 -> en）
    3. waline / twikoo：lang 参数跟随站点语言
    4. disqus：脚本 src 使用配置的 shortname（Disqus 无 locale 参数，不检查语言）
    5. provider 显式覆盖：giscus.lang = 'en' 时 zh 站也输出 data-lang="en"
    6. 静态检查：comments.html 不得在映射表之外硬编码 locale

另外验证 multilingual 构建下 html lang 与页面语言一致（zh-CN 根路径 / en 子路径）。

退出码约定（见 tools/_testlib.py）：任一断言失败 -> exit 1。

用法：
    python tools/check_comments.py
    HUGO_BIN=/path/to/hugo python tools/check_comments.py
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile

from _testlib import Harness, guard

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = os.path.join(REPO, "exampleSite")
THEME_NAME = os.path.basename(REPO)
THEMES_DIR = os.path.dirname(REPO)
TOOLS = os.path.join(REPO, "tools")
HUGO = os.environ.get("HUGO_BIN", "hugo")

THIRD_PARTY_MARKS = (
    "giscus.app", "unpkg.com", "cdn.jsdelivr.net", "disqus.com",
)


def build(extra_config=None, out="public-check"):
    """构建 exampleSite（可叠加配置 overlay），返回输出目录。"""
    outdir = os.path.join(REPO, out)
    shutil.rmtree(outdir, ignore_errors=True)
    args = [HUGO, "--source", SITE, "--themesDir", THEMES_DIR, "--gc", "-d", outdir]
    if extra_config:
        # --config 路径相对 --source；把 overlay 复制进 SITE 以简化路径
        name = os.path.basename(extra_config)
        shutil.copy(extra_config, os.path.join(SITE, name))
        try:
            args += ["--config", f"hugo.toml,{name}"]
            r = subprocess.run(args, capture_output=True, text=True, timeout=300)
        finally:
            os.remove(os.path.join(SITE, name))
    else:
        r = subprocess.run(args, capture_output=True, text=True, timeout=300)
    if r.returncode != 0:
        raise RuntimeError(f"Hugo 构建失败:\n{r.stdout[-1200:]}\n{r.stderr[-1200:]}")
    return outdir


def read_html(outdir, rel):
    path = os.path.join(outdir, rel.lstrip("/"))
    if not os.path.exists(path):
        # 兼容 pretty URL 目录形式
        path = os.path.join(outdir, rel.strip("/"), "index.html")
    with open(path, encoding="utf-8") as f:
        return f.read()


def iter_html(outdir):
    for dirpath, _, files in os.walk(outdir):
        for fn in files:
            if fn.endswith(".html"):
                with open(os.path.join(dirpath, fn), encoding="utf-8") as f:
                    yield os.path.relpath(os.path.join(dirpath, fn), outdir), f.read()


def run(h):
    # ---------- 1. 默认（评论关闭）：零第三方评论资源 ----------
    out = build()
    leaks = []
    for rel, html in iter_html(out):
        for mark in THIRD_PARTY_MARKS:
            if mark in html:
                leaks.append(f"{rel}: {mark}")
    h.record("评论关闭时不加载任何第三方评论资源", not leaks, f"{len(leaks)} 处泄漏" if leaks else "全站干净")
    shutil.rmtree(out, ignore_errors=True)

    # ---------- 2. giscus + multilingual：locale 跟随页面语言 ----------
    out = build(os.path.join(TOOLS, "multilingual.toml"))
    # 先验证 multilingual overlay 与 giscus 组合
    shutil.rmtree(out, ignore_errors=True)
    out = build(os.path.join(TOOLS, "comments-giscus.toml"))  # 单语言 zh 站
    zh_post = read_html(out, "/posts/01-home-lab-proxmox/index.html")
    h.record("giscus：zh 站 data-lang=zh-CN",
             'data-lang="zh-CN"' in zh_post, "见 data-lang 属性")
    shutil.rmtree(out, ignore_errors=True)

    # multilingual：zh 根路径 + en 子路径
    # 需要同时叠加 multilingual 与 giscus 两个 overlay
    merged = os.path.join(TOOLS, "_ml-giscus.toml")
    with open(merged, "w", encoding="utf-8") as f:
        for fn in ("multilingual.toml", "comments-giscus.toml"):
            with open(os.path.join(TOOLS, fn), encoding="utf-8") as src:
                f.write(src.read() + "\n")
    out = build(merged)
    zh_post = read_html(out, "/posts/01-home-lab-proxmox/index.html")
    en_post = read_html(out, "/en/posts/01-home-lab-proxmox/index.html")
    h.record("multilingual + giscus：zh 页 data-lang=zh-CN",
             'data-lang="zh-CN"' in zh_post, "zh 页")
    h.record("multilingual + giscus：en 页 data-lang=en",
             'data-lang="en"' in en_post, "en 页")
    h.record("multilingual：zh 页 html lang=zh-CN",
             'lang="zh-CN"' in zh_post, "html lang")
    h.record("multilingual：en 页 html lang=en",
             'lang="en"' in en_post, "html lang")
    h.record("multilingual：hreflang 双向输出",
             'hreflang="zh-CN"' in zh_post and 'hreflang="en-US"' in zh_post
             and 'hreflang="zh-CN"' in en_post and 'hreflang="en-US"' in en_post,
             "AllTranslations（zh-CN / en-US）")
    shutil.rmtree(out, ignore_errors=True)
    os.remove(merged)

    # ---------- 3/4. waline / twikoo / disqus ----------
    out = build(os.path.join(TOOLS, "comments-waline.toml"))
    html = read_html(out, "/posts/01-home-lab-proxmox/index.html").replace("\\/", "/")
    h.record("waline：lang=zh-CN 且 serverURL 正确",
             "lang: 'zh-CN'" in html and "serverURL: 'https://waline.example.com'" in html,
             "waline init（Hugo JS 转义已归一化）")
    shutil.rmtree(out, ignore_errors=True)

    out = build(os.path.join(TOOLS, "comments-twikoo.toml"))
    html = read_html(out, "/posts/01-home-lab-proxmox/index.html").replace("\\/", "/")
    h.record("twikoo：lang=zh-CN 且 envId 正确",
             "lang: 'zh-CN'" in html and "envId: 'https://twikoo.example.com'" in html,
             "twikoo init（Hugo JS 转义已归一化）")
    shutil.rmtree(out, ignore_errors=True)

    out = build(os.path.join(TOOLS, "comments-disqus.toml"))
    html = read_html(out, "/posts/01-home-lab-proxmox/index.html")
    h.record("disqus：脚本 src 使用配置的 shortname",
             "https://nebula-test.disqus.com/embed.js" in html, "embed.js")
    shutil.rmtree(out, ignore_errors=True)

    # ---------- 5. provider 显式覆盖 ----------
    out = build(os.path.join(TOOLS, "comments-giscus-override.toml"))
    html = read_html(out, "/posts/01-home-lab-proxmox/index.html")
    h.record("giscus.lang 显式覆盖：zh 站输出 data-lang=en",
             'data-lang="en"' in html, "覆盖生效")
    shutil.rmtree(out, ignore_errors=True)

    # ---------- 6. 静态检查：映射表之外不得硬编码 locale ----------
    src = open(os.path.join(REPO, "layouts", "partials", "comments.html"), encoding="utf-8").read()
    # 剔除映射表定义区（dict ... 定义行），剩余部分不得出现写死的 zh-CN / zh-TW locale 赋值
    body = re.sub(r"\{\{-?\s*\$locMap\s*:?=.*?\}\}", "", src, flags=re.S)
    bad = re.findall(r'(data-lang|lang)\s*[:=]\s*[\'"]zh-(?:CN|TW)[\'"]', body)
    h.record("comments.html 映射表之外无硬编码 locale", not bad, f"{len(bad)} 处" if bad else "干净")


if __name__ == "__main__":
    main_h = Harness("comments")
    guard(main_h, run, main_h)
    main_h.finish()
