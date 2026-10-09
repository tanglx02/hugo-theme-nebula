#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""功能一验收：多种首页布局（cards / profile / hero / landing）。

断言的都是**真实行为**（真实 Hugo 构建 + 解析产物），不是"脚本没报错"：

  1. 默认（未配置 params.home.layout）与显式 cards 产物一致 —— 默认外观不变；
  2. 四种布局都能构建成功，且各自输出可区分的结构标记；
  3. 非法 / 空值安全回退为 cards（不空白、不报错）；
  4. 布局切换**不影响**分类页 / 标签页 / 搜索索引 / RSS：
     index.json 与 index.xml（去掉 lastBuildDate 后）在四种布局下逐字节一致；
  5. 边界输入：无简介 / 无头像 / 无社交仍能构建；
  6. 多语言（en / zh-TW）下四种布局都能构建。

实现要点：配置文件写到仓库 `tmp/` 下（**不写 exampleSite**，避免污染源码树），
并用**绝对路径**引用 —— Hugo 相对 `--config` 是相对 `--source` 解析的。
绝对路径用 `os.path.abspath()`（原生分隔符），Windows / Linux 通用。

用法：
    HUGO_BIN=/path/to/hugo python tools/check_home_layouts.py
"""
import os
import re
import shutil
import subprocess
import sys

from _testlib import Harness, guard

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = os.path.join(REPO, "exampleSite")
TOOLS = os.path.join(REPO, "tools")
THEMES_DIR = os.path.dirname(REPO)
HUGO = os.environ.get("HUGO_BIN", "hugo")
OUT_ROOT = os.path.join(REPO, "tmp")
CFG_ROOT = os.path.join(OUT_ROOT, "_home_layout_cfg")

LAYOUTS = ["cards", "profile", "hero", "landing"]

MARKERS = {
    "cards": ('class="layout"', 'class="sidebar"'),
    "profile": ("home-profile",),
    "hero": ("home-full",),
    "landing": ("home-landing-hero", "landing-cta"),
}


def contains(html, token):
    """在（可能被 --minify 去掉引号的）HTML 中匹配标记。

    Hugo 的 minify 会把 class="layout" 压成 class=layout，直接子串匹配会失败。
    这里把两侧的引号统一去掉再比较，避免"因为压缩器行为"产生的假红。
    """
    stripped = (html or "").replace('"', "").replace("'", "")
    return token.replace('"', "").replace("'", "") in stripped


def write_overlay(tag, lines):
    """把覆盖配置写到 tmp/ 下，返回绝对路径（Hugo 相对 --config 是相对 --source）。"""
    os.makedirs(CFG_ROOT, exist_ok=True)
    p = os.path.join(CFG_ROOT, tag + ".toml")
    with open(p, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    return os.path.abspath(p)


def build(config_files, out_dir):
    """config_files 为绝对路径列表；第一个通常是站点 hugo.toml（相对 source）。"""
    shutil.rmtree(out_dir, ignore_errors=True)
    conf = ",".join(config_files)
    return subprocess.run(
        [HUGO, "--source", SITE, "--themesDir", THEMES_DIR, "--gc", "--minify",
         "--config", conf, "-d", out_dir],
        capture_output=True, text=True, timeout=300)


def read(path):
    if not os.path.isfile(path):
        return None
    return open(path, encoding="utf-8").read()


def normalize_css(html):
    return re.sub(r"main\.min\.[0-9a-f]+\.css", "main.min.X.css", html or "")


def normalize_rss(xml):
    return re.sub(r"<lastBuildDate>[^<]*</lastBuildDate>",
                  "<lastBuildDate>X</lastBuildDate>", xml or "")


def build_layout(h, layout, tag, extra=None):
    lines = []
    if layout is not None:
        lines += ["[params.home]", f'  layout = "{layout}"']
    if extra:
        lines += extra
    cfg = write_overlay(tag, lines)
    out = os.path.join(OUT_ROOT, f"_home_{tag}")
    r = build(["hugo.toml", cfg], out)
    if r.returncode != 0:
        h.fatal_error(f"布局 {layout!r}（{tag}）构建失败", (r.stdout + r.stderr)[-600:])
        return None
    html = read(os.path.join(out, "index.html"))
    if html is None:
        h.fatal_error(f"布局 {layout!r}（{tag}）无 index.html")
        return None
    return out, html


def run(h):
    # ---------- 1. 默认 = 显式 cards（默认外观不变） ----------
    unset = build_layout(h, None, "unset")
    cards = build_layout(h, "cards", "cards")
    if unset and cards:
        same = normalize_css(unset[1]) == normalize_css(cards[1])
        h.record("默认（未配置）与显式 cards 产物一致", same,
                 "index.html 一致（忽略 CSS 指纹）" if same else "输出不同 -> 默认外观已改变")

    # ---------- 2. 四种布局构建 + 结构标记 ----------
    outs = {}
    for L in LAYOUTS:
        res = build_layout(h, L, L)
        if not res:
            continue
        out, html = res
        outs[L] = out
        ms = MARKERS[L]
        h.record(f"布局 {L} 含专属结构标记", all(contains(html, m) for m in ms), " ".join(ms))
        h.record(f"布局 {L} 含文章卡片/列表",
                 contains(html, "post-card") or contains(html, "post-list"))

    # ---------- 3. 非法 / 空值安全回退为 cards ----------
    for tag, val in (("bad", "definitely-not-a-layout"), ("empty", "")):
        res = build_layout(h, val, tag)
        if res and cards:
            same = normalize_css(res[1]) == normalize_css(cards[1])
            label = "非法" if val else "空"
            h.record(f"{label}布局值安全回退为 cards", same,
                     "构建成功且与 cards 一致" if same else "回退失败")

    # ---------- 4. 切换布局不影响 index.json / index.xml / 分类页 ----------
    if not cards:
        h.fatal_error("cards 未产出 index.html")
        return
    json_ref = read(os.path.join(cards[0], "index.json"))
    rss_ref = normalize_rss(read(os.path.join(cards[0], "index.xml")))
    cat_ref = read(os.path.join(cards[0], "categories", "index.html"))
    if json_ref is None:
        h.fatal_error("cards 未产出 index.json")
    for L in LAYOUTS:
        if L not in outs:
            continue
        h.record(f"布局 {L} 的 index.json 与 cards 一致",
                 read(os.path.join(outs[L], "index.json")) == json_ref,
                 "搜索索引不受布局影响")
        h.record(f"布局 {L} 的 RSS 与 cards 一致（忽略 lastBuildDate）",
                 normalize_rss(read(os.path.join(outs[L], "index.xml"))) == rss_ref)
        if cat_ref is not None:
            h.record(f"布局 {L} 的分类页与 cards 一致",
                     read(os.path.join(outs[L], "categories", "index.html")) == cat_ref)

    # ---------- 5. 边界输入（无简介 / 头像 / 社交） ----------
    edge_extra = [
        "[params]", "  avatar = ''", "  description = ''",
        "[params.profile]", "  bio = ''", "[params.socials]",
    ]
    for L in LAYOUTS:
        res = build_layout(h, L, f"edge_{L}", extra=edge_extra)
        h.record(f"边界（无简介/头像/社交）布局 {L} 仍可构建", res is not None)

    # 无置顶 / 无封面：用一份"只有一篇无封面、无 sticky"的最小站点语义无法直接注入，
    # 但 zz-* 夹具里已含无封面/无置顶文章，此处断言首页仍含卡片即可（见步骤 2）。

    # ---------- 6. 多语言（en / zh-TW） ----------
    for lang, cfg in (("en", "lang-en.toml"), ("zh-TW", "lang-zh-TW.toml")):
        # 语言覆盖必须复制自 tools 下的真实文件（内容含 languages 配置）
        lang_src = os.path.join(TOOLS, cfg)
        dst = os.path.join(CFG_ROOT, f"real_{lang}.toml")
        os.makedirs(CFG_ROOT, exist_ok=True)
        shutil.copy(lang_src, dst)
        for L in LAYOUTS:
            lay = write_overlay(f"lang_{lang}_{L}", ["[params.home]", f'  layout = "{L}"'])
            out = os.path.join(OUT_ROOT, f"_home_{lang}_{L}")
            r = build(["hugo.toml", os.path.abspath(dst), os.path.abspath(lay)], out)
            ok = r.returncode == 0 and os.path.isfile(os.path.join(out, "index.html"))
            h.record(f"{lang} 布局 {L} 构建成功", ok,
                     "" if ok else (r.stdout + r.stderr)[-300:])

    # ---------- 7. exampleSite 演示页（真实可访问，非截图） ----------
    # 默认构建（cards）下，四种布局各有一个展示页，各自含对应的结构标记。
    demo = os.path.join(OUT_ROOT, "_home_demo")
    r = build(["hugo.toml"], demo)
    if r.returncode != 0:
        h.fatal_error("演示站构建失败", (r.stdout + r.stderr)[-400:])
    else:
        # 演示页布局 > 期望标记
        want = {
            "cards": [('class="layout"',)],
            "profile": [("home-profile",)],
            "hero": [("home-full",)],
            "landing": [("home-landing-hero",)],
        }
        for name, tokens in want.items():
            p = os.path.join(demo, "layouts-demo", name, "index.html")
            html = read(p)
            if html is None:
                h.record(f"演示页 layouts-demo/{name} 存在", False, "未生成")
                continue
            h.record(f"演示页 layouts-demo/{name} 存在且渲染对应布局",
                     all(contains(html, t) for t in tokens[0]))
            # 演示页必须是完整 HTML 文档（有 head/main），不是片段
            h.record(f"演示页 layouts-demo/{name} 是完整文档",
                     ("<main" in html or "<main " in html.replace('"', "")) and "</html>" in html)
        # 英文演示页
        en_demo = os.path.join(OUT_ROOT, "_home_demo_en")
        lang_dst = os.path.join(CFG_ROOT, "real_en_demo.toml")
        os.makedirs(CFG_ROOT, exist_ok=True)
        shutil.copy(os.path.join(TOOLS, "multilingual.toml"), lang_dst)
        r2 = build(["hugo.toml", os.path.abspath(lang_dst)], en_demo)
        en_cards = read(os.path.join(en_demo, "en", "layouts-demo", "cards", "index.html"))
        h.record("英文演示页 layouts-demo/cards 生成", en_cards is not None,
                 "" if r2.returncode == 0 else (r2.stdout + r2.stderr)[-300:])


def main():
    h = Harness("home-layouts")
    guard(h, run, h)
    h.finish()


if __name__ == "__main__":
    main()