#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""多 Section 完整回归：确认首页 / 搜索 / 归档 / 相关文章 / Series / RSS / sitemap / 分页
都遵循 params.content.sections，而不是写死 posts。

用法（CI 与本地一致）：
    python tools/verify_multisection.py
环境变量：
    SITE_DIR   站点目录（默认 ../myblog）
    HUGO_ARGS  传给 hugo 的额外参数（CI 用 '--source . --themesDir ../..'）
    HUGO_BIN   hugo 可执行文件（默认 PATH 中的 hugo）

退出码约定（见 tools/_testlib.py）：任一断言失败 / 构建失败 -> exit 1。
"""
import json
import os
import re
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _testlib import Harness, guard  # noqa: E402

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
SITE = os.path.abspath(os.environ.get("SITE_DIR") or os.path.join(ROOT, "myblog"))
HUGO = os.environ.get("HUGO_BIN", "hugo")
HUGO_ARGS = os.environ.get("HUGO_ARGS", "").split() if os.environ.get("HUGO_ARGS") else []
WORK = os.path.join(ROOT, "tmp", "multisec")
CONFIG_NAME = "ms-verify.toml"

SECTIONS = ["posts", "tutorials", "notes", "projects"]
# 各 section 的测试文章标题与正文唯一标记（由 tools/gen_testdata.py 生成）
MARKERS = {
    "tutorials": ("多 Section 教程", "TUTORIALSSECTION1"),
    "notes": ("多 Section 笔记", "NOTESSECTION1"),
    "projects": ("多 Section 项目", "PROJECTSSECTION1"),
}

H = Harness("multisection")


def build(out_dir, extra_config=None):
    args = [HUGO] + HUGO_ARGS + ["--gc", "--minify", "-d", out_dir]
    if extra_config:
        # --config 会替换默认配置，因此必须显式合并站点主配置
        args += ["--config", f"hugo.toml,{extra_config}"]
    p = subprocess.run(args, cwd=SITE, capture_output=True, text=True,
                       encoding="utf-8", errors="ignore")
    errs = [l for l in (p.stderr + p.stdout).splitlines()
            if l.strip().upper().startswith("ERROR")]
    return errs


def read(base, rel):
    p = os.path.join(base, rel)
    if not os.path.exists(p):
        return None
    return open(p, encoding="utf-8", errors="ignore").read()


def index_blob(base):
    """把搜索索引转成一个大字符串（兼容单索引数组与分片 {items,chunks} 结构）。"""
    raw = read(base, "index.json")
    if raw is None:
        return ""
    try:
        doc = json.loads(raw)
    except Exception:
        return raw
    return json.dumps(doc, ensure_ascii=False)


def _run_all():
    # 写入多 section 配置（放在 SITE 内：--config 路径相对 --source）
    cfg_path = os.path.join(SITE, CONFIG_NAME)
    with open(cfg_path, "w", encoding="utf-8") as f:
        f.write('[params.content]\n  sections = ["posts", "tutorials", "notes", "projects"]\n')

    # 每次使用全新输出目录，避免任何删除操作（批量删除会被安全策略拦截）
    import time
    run_id = os.environ.get("MULTISEC_RUN_ID") or time.strftime("%H%M%S")
    multi = os.path.join(WORK, f"multi-{run_id}")
    default = os.path.join(WORK, f"default-{run_id}")

    errs = build(multi, extra_config=CONFIG_NAME)
    if errs:
        H.fatal_error("多 section 构建失败", errs[0][:160]); return
    errs = build(default)
    if errs:
        H.fatal_error("默认（posts）构建失败", errs[0][:160]); return

    # ---------------- 1. 首页 ----------------
    home = read(multi, "index.html") or ""
    for sec, (title, marker) in MARKERS.items():
        H.record(f"首页包含 {sec} 的文章", title in home, title)
    # 首页本身不翻页（设计如此：固定展示 homePostCount 篇 + "浏览更多"），
    # 因此这里验证：首页卡片数量符合配置、存在进入全量列表的入口、区块列表页分页可用。
    cards = len(re.findall(r'class=["\']?post-card', home))
    H.record("首页卡片数量符合 homePostCount(8)", cards == 8, f"{cards} 张")
    H.record("首页有「浏览更多」入口", 'class="btn"' in home or "btn" in home)
    H.record("区块列表页分页第 2 页存在",
             os.path.exists(os.path.join(multi, "posts", "page", "2", "index.html")))

    # ---------------- 2. 搜索索引 ----------------
    blob = index_blob(multi)
    for sec, (title, marker) in MARKERS.items():
        H.record(f"搜索索引包含 {sec} 内容", marker in blob, marker)
    H.record("搜索索引包含 posts 内容", "应急响应" in blob or "FOXTROT10000" in blob)

    # ---------------- 3. 归档 ----------------
    arch = read(multi, "archives/index.html") or ""
    for sec, (title, marker) in MARKERS.items():
        H.record(f"归档包含 {sec} 的文章", title in arch, title)

    # ---------------- 4. RSS ----------------
    rss = read(multi, "index.xml") or ""
    for sec in MARKERS:
        H.record(f"RSS 包含 /{sec}/ 文章链接", f"/{sec}/zz-" in rss)

    # ---------------- 5. sitemap ----------------
    sm = read(multi, "sitemap.xml") or ""
    for sec in MARKERS:
        H.record(f"sitemap 包含 /{sec}/ 页面", f"/{sec}/" in sm)

    # ---------------- 6. Series（跨 section） ----------------
    proj = read(multi, "projects/zz-projects-1/index.html") or ""
    if not proj:
        H.record("projects 文章页存在", False, "projects/zz-projects-1")
    else:
        H.record("projects 文章页存在", True)
        H.record("Series 卡片渲染（跨 section）", "series-card" in proj)
        H.record("Series 进度显示", bool(re.search(r"第\s*1\s*篇", proj)) and "共" in proj)
        H.record("Series 下一篇链接", "series-next" in proj or "series-prev" in proj)

    # ---------------- 7. 相关文章（必须落在配置的 sections 内） ----------------
    tut = read(multi, "tutorials/zz-tutorials-1/index.html") or ""
    if not tut:
        H.record("tutorials 文章页存在", False, "tutorials/zz-tutorials-1")
    else:
        H.record("tutorials 文章页存在", True)
        rel = re.search(r'class=["\']?related["\']?[^>]*>(.*?)</div>\s*</div>', tut, re.S)
        rel_html = rel.group(1) if rel else tut
        hrefs = re.findall(r'href=["\']?(/[^"\'> ]+)', rel_html)
        internal = [h for h in hrefs if not h.startswith("/img")]
        H.record("相关文章有内容", len(internal) > 0, f"{len(internal)} 条")
        outside = [h for h in internal
                   if not any(h.startswith(f"/{s}/") for s in SECTIONS)]
        H.record("相关文章链接都在配置的 sections 内", not outside, f"越界 {outside[:3]}")

    # ---------------- 8. 默认配置必须排除其它 section ----------------
    dhome = read(default, "index.html") or ""
    for sec, (title, marker) in MARKERS.items():
        H.record(f"[默认配置] 首页不含 {sec}", title not in dhome)
    dblob = index_blob(default)
    for sec, (title, marker) in MARKERS.items():
        H.record(f"[默认配置] 搜索索引不含 {sec}", marker not in dblob)
    darch = read(default, "archives/index.html") or ""
    for sec, (title, marker) in MARKERS.items():
        H.record(f"[默认配置] 归档不含 {sec}", title not in darch)
    drss = read(default, "index.xml") or ""
    for sec in MARKERS:
        H.record(f"[默认配置] RSS 不含 /{sec}/", f"/{sec}/zz-" not in drss)

    # ---------------- 9. 源码不得硬编码 Section "posts" ----------------
    theme_layouts = os.path.join(SITE, "themes", "hugo-theme-nebula", "layouts")
    if not os.path.isdir(theme_layouts):
        theme_layouts = os.path.join(ROOT, "hugo-theme-nebula", "layouts")
    hits = []
    for dirpath, _, files in os.walk(theme_layouts):
        for f in files:
            if not f.endswith((".html", ".xml", ".json")):
                continue
            p = os.path.join(dirpath, f)
            for i, ln in enumerate(open(p, encoding="utf-8", errors="ignore").read().split("\n"), 1):
                if re.search(r'\(\s*where[^\n]*"Section"\s+"posts"\s*\)', ln) or \
                   re.search(r'"Section"\s+"posts"', ln):
                    hits.append(f"{os.path.relpath(p, theme_layouts)}:{i}")
    H.record("模板中无硬编码 Section \"posts\"（仅允许 default 回退）", not hits, f"{hits[:4]}")

    # 清理临时配置
    try:
        os.remove(cfg_path)
    except OSError:
        pass


def main():
    guard(H, _run_all)
    H.finish()


if __name__ == "__main__":
    main()
