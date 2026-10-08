#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""真实多语言站点回归（Hugo multilingual build，非 locale 替换）。

用 tools/multilingual.toml 对 exampleSite 做真实双语言构建：
    zh-CN 在根路径（URL 与单语言版一致），en 在 /en/ 子路径（独立 contentDir）。

验证（全部基于构建产物，不用浏览器）：
    - URL 结构：zh 根路径 / en 子路径
    - 同一篇文章两个语言版本内容正确（中文 / 英文标题）
    - html lang 与页面语言一致
    - hreflang 双向输出且 href 指向正确语言版本
    - canonical 指向各语言自身 URL
    - og:locale（zh_CN / en_US）与 og:locale:alternate
    - RSS：/index.xml 与 /en/index.xml 均可解析
    - sitemap 包含两个语言版本
    - 分类 / 标签：/en/categories/environment/ 等按语言隔离
    - 搜索：/en/index.json 存在且含英文内容
    - Series：同一 series 在两个语言下各自渲染（跨语言不串）
    - UI 文案：复用 verify_i18n.py 对 /en/ 做完整断言

退出码约定（见 tools/_testlib.py）：任一断言失败 -> exit 1。

用法：
    python tools/verify_multilingual.py       # HUGO_BIN 默认 hugo
"""
import os
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET

from _testlib import Harness, guard

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = os.path.join(REPO, "exampleSite")
TOOLS = os.path.join(REPO, "tools")
THEMES_DIR = os.path.dirname(REPO)
HUGO = os.environ.get("HUGO_BIN", "hugo")
PY = sys.executable

ZH_POST = "/posts/01-home-lab-proxmox/index.html"
EN_POST = "/en/posts/01-home-lab-proxmox/index.html"
ZH_TITLE_MARK = "从零搭建家庭安全实验室"
EN_TITLE_MARK = "Building a Home Security Lab"


def read(root, rel):
    p = os.path.join(root, rel.lstrip("/"))
    if not os.path.isfile(p):
        return None
    return open(p, encoding="utf-8").read()


def run(h):
    out = os.path.join(REPO, "public-multilingual")
    shutil.rmtree(out, ignore_errors=True)
    # --config 相对 --source 解析：把 overlay 复制进 SITE，用后删除
    overlay_name = "_verify-multilingual.toml"
    shutil.copy(os.path.join(TOOLS, "multilingual.toml"), os.path.join(SITE, overlay_name))
    try:
        r = subprocess.run(
            [HUGO, "--source", SITE, "--themesDir", THEMES_DIR, "--gc",
             "--config", f"hugo.toml,{overlay_name}", "-d", out],
            capture_output=True, text=True, timeout=300)
    finally:
        os.remove(os.path.join(SITE, overlay_name))
    if r.returncode != 0:
        h.fatal_error("multilingual 构建失败", (r.stdout + r.stderr)[-800:])
        return

    zh = read(out, ZH_POST)
    en = read(out, EN_POST)
    if zh is None or en is None:
        h.fatal_error("双语言文章页缺失",
                      f"zh={zh is not None} en={en is not None}")
        return

    # URL + 内容
    h.record("zh 页在根路径且含中文标题", ZH_TITLE_MARK in zh, ZH_POST)
    h.record("en 页在 /en/ 子路径且含英文标题", EN_TITLE_MARK in en, EN_POST)

    # html lang
    h.record("zh 页 html lang=zh-CN", 'lang="zh-CN"' in zh)
    h.record("en 页 html lang=en", 'lang="en"' in en)

    # hreflang：双向且 href 指向正确语言
    ok = ('hreflang="zh-CN"' in zh and 'hreflang="en-US"' in zh
          and 'hreflang="zh-CN"' in en and 'hreflang="en-US"' in en)
    h.record("hreflang 双语言双向输出", ok)
    en_href = f'hreflang="en-US" href="https://blog.example.com{EN_POST.replace("index.html", "")}"'
    h.record("zh 页 hreflang=en-US 指向 en 版 URL", en_href in zh)

    # canonical
    h.record("zh canonical 指向根路径版本",
             'href="https://blog.example.com/posts/01-home-lab-proxmox/"' in zh)
    h.record("en canonical 指向 /en/ 版本",
             'href="https://blog.example.com/en/posts/01-home-lab-proxmox/"' in en)

    # og:locale
    h.record("zh og:locale=zh_CN 且 alternate=en_US",
             'og:locale" content="zh_CN"' in zh and 'og:locale:alternate" content="en_US"' in zh)
    h.record("en og:locale=en_US 且 alternate=zh_CN",
             'og:locale" content="en_US"' in en and 'og:locale:alternate" content="zh_CN"' in en)

    # RSS
    rss_ok = True
    try:
        zh_rss = ET.parse(os.path.join(out, "index.xml")).getroot()
        en_rss = ET.parse(os.path.join(out, "en/index.xml")).getroot()
        rss_ok = (zh_rss.tag == "rss" and en_rss.tag == "rss"
                  and "blog.example.com/en/" in (en_rss.find("channel/link").text or ""))
    except Exception as e:
        rss_ok = False
        h.record("RSS 解析", False, str(e)[:80])
    h.record("zh / en RSS 均存在且 en channel 指向 /en/", rss_ok)

    # sitemap：multilingual 下根 sitemap 是 sitemapindex，逐语言列出子 sitemap
    try:
        sm = open(os.path.join(out, "sitemap.xml"), encoding="utf-8").read()
        idx_ok = "/en/sitemap.xml" in sm and "/zh-cn/sitemap.xml" in sm
        en_sm = open(os.path.join(out, "en/sitemap.xml"), encoding="utf-8").read()
        h.record("sitemapindex 同时列出 zh-cn 与 en 子 sitemap", idx_ok)
        h.record("en 子 sitemap 包含英文文章页",
                 "/en/posts/01-home-lab-proxmox/" in en_sm)
    except Exception as e:
        h.record("sitemap 双语言结构", False, str(e)[:80])

    # 分类 / 标签按语言隔离
    h.record("/en/categories/ 存在", os.path.isfile(os.path.join(out, "en/categories/index.html")))
    h.record("/en/categories/environment/ 存在（en 分类 term）",
             os.path.isfile(os.path.join(out, "en/categories/environment/index.html")))
    h.record("/categories/environment/ 不存在（分类按语言隔离，zh 侧无此 term）",
             not os.path.exists(os.path.join(out, "categories/environment/index.html")))

    # 搜索索引
    en_idx = read(out, "/en/index.json")
    zh_idx = read(out, "/index.json")
    h.record("/en/index.json 存在且含英文内容",
             en_idx is not None and EN_TITLE_MARK in en_idx)
    h.record("zh /en/index.json 不串语言（zh 索引无英文文章正文）",
             zh_idx is not None and EN_TITLE_MARK not in zh_idx)

    # Series：两语言各自渲染（各 2 篇），且互不串语言
    zh_series_title = "WAF 绕过实战"
    h.record("zh 页 series-card 渲染", "series-card" in zh)
    h.record("en 页 series-card 渲染", "series-card" in en)
    h.record("zh series 含中文系列文章（语言隔离）",
             zh_series_title in zh and EN_TITLE_MARK.split(":")[0] not in zh.split("series-card")[0])
    h.record("en series 不含 zh 独有标题",
             zh_series_title not in en)

    # UI 文案：复用 verify_i18n 对 en 子目录做完整断言
    r2 = subprocess.run([PY, os.path.join(TOOLS, "verify_i18n.py"), out + "/en", "en"],
                        capture_output=True, text=True, timeout=120)
    h.record("en 站 UI 文案（verify_i18n 全量断言）", r2.returncode == 0,
             (r2.stdout + r2.stderr).strip().splitlines()[-1][:100] if r2.returncode else "全绿")

    shutil.rmtree(out, ignore_errors=True)


if __name__ == "__main__":
    main_h = Harness("multilingual")
    guard(main_h, run, main_h)
    main_h.finish()
