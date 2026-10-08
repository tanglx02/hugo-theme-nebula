#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""搜索索引日期契约测试：date 是机器字段，dateDisplay 必须是构建期 i18n 结果。

背景（v1.0.9 P1）
----------------
搜索索引 `index.json` 原先只有 `date`（固定 `YYYY-MM-DD`），前端直接显示它，
于是三语言站点的搜索结果日期永远是 `2026-09-28`：

    zh-CN 期望 2026年9月28日 / en 期望 Sep 28, 2026 / zh-TW 期望 2026年9月28日

现在约定：**日期格式化只在 Hugo 构建期发生**（`i18n "common.dateFormat"`），
前端拿到的 `dateDisplay` 已经是正确的语言形式，JS 只负责原样输出。

本测试独立验证这条契约 —— 不依赖模板源码的字面量，而是自己按 i18n 文件里
记录的 Go layout 重新算一遍期望值再比对（施工人员 ≠ 验收人员）。

验证矩阵
--------
  * zh-CN / en / zh-TW 三种真实构建
  * 多篇文章（>= 8 条、>= 5 个不同日期）
  * 缺日期的异常文章 -> date / dateDisplay 均为空串，且不出现 0001-01-01
  * date 仍保持机器格式 `YYYY-MM-DD`（向后兼容）
  * JSON 索引结构向后兼容：旧字段一个不少，新增字段不影响老消费者

用法：
    python tools/check_search_date.py
环境变量：
    SITE_DIR / HUGO_ARGS / HUGO_BIN（与 verify_multisection.py 一致）
退出码约定（见 tools/_testlib.py）：任一断言失败 / 构建失败 -> exit 1。
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _testlib import Harness, guard  # noqa: E402

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
SITE = os.path.abspath(os.environ.get("SITE_DIR") or os.path.join(ROOT, "exampleSite"))
HUGO = os.environ.get("HUGO_BIN", "hugo")
HUGO_ARGS = os.environ.get("HUGO_ARGS", "--source . --themesDir ../..").split()

# (语言, 额外配置文件, i18n 文件)
LANGS = [
    ("zh-CN", None, "i18n/zh-CN.yaml"),
    ("en", "tools/lang-en.toml", "i18n/en.yaml"),
    ("zh-TW", "tools/lang-zh-TW.toml", "i18n/zh-TW.yaml"),
]

# 旧索引结构必须保留的字段（向后兼容）
LEGACY_FIELDS = ("title", "url", "date", "summary", "content",
                 "key", "tags", "categories", "series")

MACHINE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

H = Harness("search-date")


# ---------------------------------------------------------------- Go layout
def i18n_date_layout(lang_file):
    """从 i18n/<lang>.yaml 读出 common.dateFormat 的 Go layout 字符串。"""
    path = os.path.join(ROOT, lang_file)
    if not os.path.isfile(path):
        raise SystemExit(f"缺少 i18n 文件: {path}")
    with open(path, encoding="utf-8") as f:
        for line in f:
            m = re.match(r"\s*dateFormat:\s*['\"](.+?)['\"]\s*$", line)
            if m:
                return m.group(1)
    raise SystemExit(f"{path} 未找到 dateFormat")


def go_fmt(layout, y, m, d):
    """按 Go 参考时间 layout 格式化日期（支持本主题用到的全部 token）。

    独立实现是为了"验收不复用被测逻辑"：如果直接把主题的 i18n 结果当成期望值，
    那么模板写错时两边会一起错。
    """
    tokens = [
        ("January", lambda: _MONTHS_FULL[m - 1]),
        ("2006", lambda: "%04d" % y),
        ("Jan", lambda: _MONTHS_ABBR[m - 1]),
        ("01", lambda: "%02d" % m),
        ("02", lambda: "%02d" % d),
        ("15", lambda: "00"),
        ("04", lambda: "00"),
        ("05", lambda: "00"),
        ("1", lambda: str(m)),
        ("2", lambda: str(d)),
        ("3", lambda: str(d)),
    ]
    # 去重并保持"长者优先"，避免 Jan / January 与 1 / 01 互相抢匹配
    seen, ordered = set(), []
    for tok, fn in tokens:
        if tok in seen:
            continue
        seen.add(tok)
        ordered.append((tok, fn))
    ordered.sort(key=lambda kv: -len(kv[0]))

    out, i = [], 0
    while i < len(layout):
        for tok, fn in ordered:
            if layout.startswith(tok, i):
                out.append(fn())
                i += len(tok)
                break
        else:
            out.append(layout[i])
            i += 1
    return "".join(out)


_MONTHS_ABBR = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
_MONTHS_FULL = ["January", "February", "March", "April", "May", "June",
                "July", "August", "September", "October", "November", "December"]


# ---------------------------------------------------------------- 构建
def build(out_dir, extra_config=None):
    """构建站点。

    语言切换配置必须**复制到站点目录内**再用相对路径引用：Hugo 会静默忽略
    用 cwd 相对路径找不到、或用绝对路径给出的第二份 --config 文件，
    表现为"英文构建实际仍是中文"——如果只看产物是否存在，很容易被蒙过去。
    """
    staged = None
    args = [HUGO] + HUGO_ARGS + ["--gc", "--minify", "-d", out_dir]
    try:
        if extra_config:
            staged = "_datecheck-" + os.path.basename(extra_config)
            shutil.copyfile(os.path.join(ROOT, extra_config),
                            os.path.join(SITE, staged))
            args += ["--config", f"hugo.toml,{staged}"]
        p = subprocess.run(args, cwd=SITE, capture_output=True, text=True,
                           encoding="utf-8", errors="ignore")
        errs = [l for l in (p.stderr + p.stdout).splitlines()
                if l.strip().upper().startswith("ERROR")]
        if p.returncode != 0:
            errs.append(f"hugo exit={p.returncode}")
        return errs
    finally:
        if staged:
            staged_path = os.path.join(SITE, staged)
            if os.path.isfile(staged_path):
                os.remove(staged_path)


def built_language(out_dir):
    """读取首页 <html lang>，确认这次构建真的是目标语言。"""
    idx = os.path.join(out_dir, "index.html")
    if not os.path.isfile(idx):
        return None
    head = open(idx, encoding="utf-8", errors="ignore").read(4096)
    m = re.search(r"<html[^>]*\slang=[\"']?([A-Za-z0-9_-]+)", head)
    return m.group(1) if m else None


def load_index(out_dir):
    with open(os.path.join(out_dir, "index.json"), encoding="utf-8") as f:
        doc = json.load(f)
    return doc if isinstance(doc, list) else doc.get("items", [])



# ---------------------------------------------------------------- 主流程
def check_language(lang, extra_config, layout, out_dir):
    errs = build(out_dir, extra_config)
    if errs:
        H.fatal_error(f"[{lang}] Hugo 构建失败", "；".join(errs[:3]))
        return None
    # 语言是否真的切过去了？否则"三语言一致通过"可能只是同一份中文产物跑三遍
    got = built_language(out_dir)
    want = lang.rsplit("-", 1)[0] if lang == "zh-CN" else lang
    H.record(f"[{lang}] 构建产物 <html lang> 确为 {want}（未被静默回退）",
             (got or "").lower().startswith(want.lower()),
             f"lang={got}")
    items = load_index(out_dir)
    if len(items) < 8:
        H.fatal_error(f"[{lang}] 索引条目过少", f"{len(items)} 条，至少需 8 条")
        return items

    dated = [it for it in items if it.get("date")]
    if len(dated) < 8:
        H.fatal_error(f"[{lang}] 带日期的条目过少", f"{len(dated)} 条")

    bad_machine = [it for it in dated if not MACHINE_RE.match(it.get("date", ""))]
    H.record(f"[{lang}] date 仍为机器格式 YYYY-MM-DD（向后兼容）",
             not bad_machine,
             f"{len(dated)} 条带日期；异常 {[i.get('date') for i in bad_machine[:3]]}")

    bad_display = []
    for it in dated:
        y, m, d = (int(x) for x in it["date"].split("-"))
        expect = go_fmt(layout, y, m, d)
        if it.get("dateDisplay") != expect:
            bad_display.append(f'{it.get("url")} 期望 {expect!r} 实际 {it.get("dateDisplay")!r}')
    H.record(f"[{lang}] dateDisplay 与布局 {layout!r} 的期望值完全一致",
             not bad_display,
             f"{len(dated)} 条全部匹配" if not bad_display else "；".join(bad_display[:3]))

    # 必须"真的本地化"，不能只是换了个字段名
    same_as_machine = [it for it in dated if it.get("dateDisplay") == it.get("date")]
    H.record(f"[{lang}] dateDisplay 不等于机器字段 date（确实做了本地化）",
             not same_as_machine,
             f"layout={layout}" if not same_as_machine
             else f"退化 {len(same_as_machine)} 条")

    empty_field = [it for it in items if "dateDisplay" not in it]
    H.record(f"[{lang}] 每条索引都带 dateDisplay 字段",
             not empty_field, f"{len(items)} 条")

    missing_legacy = []
    for i, it in enumerate(items):
        lack = [k for k in LEGACY_FIELDS if k not in it]
        if lack:
            missing_legacy.append(f"第 {i} 条缺 {','.join(lack)}")
    H.record(f"[{lang}] JSON 索引结构向后兼容（旧字段齐全）",
             not missing_legacy, "；".join(missing_legacy[:3]) if missing_legacy
             else f"{len(items)} 条 × {len(LEGACY_FIELDS)} 字段")

    distinct = sorted({it["date"] for it in dated})
    H.record(f"[{lang}] 覆盖多篇文章的多个日期（>= 5 个不同日期）",
             len(distinct) >= 5, f"{len(distinct)} 个不同日期，共 {len(dated)} 条")
    return items


def check_missing_date_case():
    """缺日期场景：date / dateDisplay 都必须是空串，不能出现 0001-01-01。"""
    root = tempfile.mkdtemp(prefix="nebula-date-")
    try:
        content = os.path.join(root, "content", "posts")
        os.makedirs(content, exist_ok=True)
        with open(os.path.join(content, "has-date.md"), "w", encoding="utf-8") as f:
            f.write("---\ntitle: '有日期文章'\ndate: '2025-03-05T00:00:00Z'\n"
                    "description: '日期契约测试'\n---\n\nDATE normal case.\n")
        # 故意不写 date，且文件名不含日期前缀 -> .Date 为零值
        with open(os.path.join(content, "no-date-field.md"), "w", encoding="utf-8") as f:
            f.write("---\ntitle: '无日期文章'\ndescription: '日期契约测试 - 缺日期'\n---\n\n"
                    "DATE missing case.\n")
        with open(os.path.join(root, "hugo.toml"), "w", encoding="utf-8") as f:
            f.write("""baseURL = 'http://datetest.test/'
locale = 'zh-CN'
title = 'Date Contract Test'
theme = 'hugo-theme-nebula'
hasCJKLanguage = true
defaultContentLanguage = 'zh'

[pagination]
  pagerSize = 10

[taxonomies]
  category = 'categories'
  tag = 'tags'

[outputs]
  home = ['HTML', 'RSS', 'JSON']

[params]
  author = 'Tester'
  [params.search]
    enable = true
""")
        out = os.path.join(root, "public")
        p = subprocess.run(
            [HUGO, "--source", root, "--themesDir", os.path.dirname(ROOT),
             "--gc", "--minify", "-d", out],
            capture_output=True, text=True, encoding="utf-8", errors="ignore",
            timeout=300)
        if p.returncode != 0:
            H.fatal_error("[缺日期] Hugo 构建失败", (p.stderr or p.stdout)[-300:])
            return
        items = load_index(out)
        H.record("[缺日期] 构建成功且索引包含两篇文章", len(items) == 2,
                 f"{len(items)} 条: {[i.get('title') for i in items]}")
        by_title = {it["title"]: it for it in items}

        normal = by_title.get("有日期文章")
        missing = by_title.get("无日期文章")
        if not normal or not missing:
            H.fatal_error("[缺日期] 索引标题与预期不符", list(by_title))
            return
        H.record("[缺日期] 正常文章：date=2025-03-05，dateDisplay=2025年3月5日",
                 normal.get("date") == "2025-03-05"
                 and normal.get("dateDisplay") == "2025年3月5日",
                 f'date={normal.get("date")} dateDisplay={normal.get("dateDisplay")}')
        H.record("[缺日期] 缺日期文章：date 与 dateDisplay 均为空串",
                 missing.get("date") == "" and missing.get("dateDisplay") == "",
                 f'date={missing.get("date")!r} dateDisplay={missing.get("dateDisplay")!r}')
        raw = open(os.path.join(out, "index.json"), encoding="utf-8").read()
        H.record("[缺日期] 索引中不出现 0001-01-01 / January 1 这类零值日期",
                 "0001-01-01" not in raw and "January 1" not in raw, "无零值泄漏")
    finally:
        shutil.rmtree(root, ignore_errors=True)


def run(h):
    base = os.path.join(ROOT, "tmp", "search-date")
    os.makedirs(base, exist_ok=True)
    seen_layouts, displays_by_lang = {}, {}
    for lang, extra, i18n_file in LANGS:
        layout = i18n_date_layout(i18n_file)
        seen_layouts[lang] = layout
        if extra and not os.path.isfile(os.path.join(ROOT, extra)):
            h.fatal_error(f"[{lang}] 缺少语言配置文件", extra)
            continue
        items = check_language(lang, extra, layout,
                           os.path.join(base, f"public-{lang}"))
        if items:
            displays_by_lang[lang] = [
                it.get("dateDisplay") for it in items if it.get("date")]

    h.record("三种语言的 dateFormat 布局已分别读取",
             len(set(seen_layouts.values())) >= 2, str(seen_layouts))
    # 同一篇文章在 zh-CN 与 en 下必须给出不同字符串（证明真的按语言走了）
    if "zh-CN" in displays_by_lang and "en" in displays_by_lang:
        common = set(displays_by_lang["zh-CN"]) & set(displays_by_lang["en"])
        h.record("zh-CN 与 en 的 dateDisplay 集合互不相同",
                 not common, f"交集 {len(common)} 个")
        zh = [s for s in displays_by_lang["zh-CN"] if s][:1]
        en = [s for s in displays_by_lang["en"] if s][:1]
        h.record("zh-CN 日期形如 2026年9月28日",
                 bool(zh) and bool(re.fullmatch(r"\d{4}年\d{1,2}月\d{1,2}日", zh[0])),
                 zh[0] if zh else "无")
        h.record("en 日期形如 Sep 28, 2026",
                 bool(en) and bool(re.fullmatch(r"[A-Z][a-z]{2} \d{1,2}, \d{4}", en[0])),
                 en[0] if en else "无")
    if "zh-TW" in displays_by_lang:
        tw = [s for s in displays_by_lang["zh-TW"] if s][:1]
        h.record("zh-TW 日期形如 2026年9月28日（按 i18n 布局本地化）",
                 bool(tw) and bool(re.fullmatch(r"\d{4}年\d{1,2}月\d{1,2}日", tw[0])),
                 tw[0] if tw else "无")

    check_missing_date_case()


def main():
    guard(H, run, H)
    H.finish()


if __name__ == "__main__":
    main()
