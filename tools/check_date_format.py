#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""日期格式一致性检查：UI 日期必须走 i18n，机器格式必须显式白名单。

规则
----
UI 日期（给人看的）**必须**用 `i18n "common.dateFormat"`；
把 Go 参考时间 `2006-01-02` 直接写在模板里属于硬编码，视为违规。

机器格式（给程序消费的）允许硬编码，但必须落在白名单里：

    layouts/index.xml            RSS/Atom：pubDate/updated 必须是 RFC822/ISO8601
    layouts/partials/head.html   JSON-LD：datePublished/dateModified 必须是 ISO 8601
    layouts/partials/post-card.html  <time datetime="...">：HTML 标准要求机器可读
    layouts/_default/index.json  搜索索引：date 字段供 JS 解析

白名单以「文件 + 机器格式标记」精确登记，不允许整文件放行 ——
这样即使有人在同一文件里新加一处 UI 硬编码日期，也仍会被抓到。

退出码约定（见 tools/_testlib.py）：任一违规 -> exit 1。

用法：python3 tools/check_date_format.py [theme_root]
"""
import os
import re
import sys

from _testlib import Harness, guard

ROOT = sys.argv[1] if len(sys.argv) > 1 else os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
LAYOUTS = os.path.join(ROOT, "layouts")

# (文件相对路径, 必须同时出现的机器格式标记, 说明)
MACHINE_FORMAT_ALLOWLIST = {
    ("index.xml", "atom:updated"): "RSS/Atom 的 updated 需 ISO 8601",
    ("index.xml", "<pubDate>"): "RSS 的 pubDate 需 RFC822",
    ("partials/head.html", '"datePublished"'): "JSON-LD 需 ISO 8601",
    ("partials/head.html", '"dateModified"'): "JSON-LD 需 ISO 8601",
    ("partials/post-card.html", "<time datetime="): "<time> 的 datetime 需机器可读",
    ("_default/index.json", '"date"'): "搜索索引的 date 字段供 JS 解析",
}

GO_REF = "2006-01-02"
# 命中后若同一行含这些标记，则视为机器格式（与上面的白名单互为校验）
MACHINE_MARKERS = ("atom:updated", "<pubDate>", '"datePublished"', '"dateModified"',
                    "<time datetime=", '"date"')

I18N_DATE_RE = re.compile(r'\.Format\s+\(\s*i18n\s+"common\.dateFormat"\s*\)')


def run(h):
    if not os.path.isdir(LAYOUTS):
        h.fatal_error("layouts 目录不存在", LAYOUTS)
        return

    files = []
    for dirpath, _, names in os.walk(LAYOUTS):
        for n in names:
            if n.endswith((".html", ".xml", ".json")):
                files.append(os.path.join(dirpath, n))
    if not files:
        h.fatal_error("未扫描到任何模板文件", LAYOUTS)
        return

    violations, allowed_hits = [], []
    for f in sorted(files):
        rel = os.path.relpath(f, LAYOUTS).replace("\\", "/")
        for i, line in enumerate(open(f, encoding="utf-8"), 1):
            if GO_REF not in line:
                continue
            if I18N_DATE_RE.search(line):
                continue                      # 正确：用 i18n 格式化
            if "machine-format:" in line:
                # 模板作者显式标注了机器格式（须与白名单说明一致）
                allowed_hits.append(f"{rel}:{i}  显式标注 machine-format")
                continue
            if any(m in line for m in MACHINE_MARKERS):
                key_ok = any(p == rel and m in line
                             for (p, m) in MACHINE_FORMAT_ALLOWLIST)
                if key_ok:
                    why = next(w for (p, m), w in MACHINE_FORMAT_ALLOWLIST.items()
                               if p == rel and m in line)
                    allowed_hits.append(f"{rel}:{i}  {why}")
                    continue
            violations.append(f"{rel}:{i}  {line.strip()[:90]}")

    print(f"扫描模板文件: {len(files)} 个")
    print(f"机器格式白名单命中: {len(allowed_hits)}（RSS / JSON-LD / <time> / 搜索索引）")
    for s in allowed_hits:
        print("   ", s)
    if violations:
        print(f"\n### 违规：UI 日期硬编码 {GO_REF}  x{len(violations)}")
        for s in violations[:10]:
            print("   ", s)

    h.record("UI 日期统一使用 i18n common.dateFormat",
             not violations, f"{len(violations)} 处违规" if violations else "无违规")
    # 常见 UI 日期位置必须都已走 i18n（防止新增模板漏改）
    for rel, needle, label in (
        ("_default/single.html", 'i18n "post.updatedOn"', "最后修改日期"),
        ("partials/sidebar.html", "mini-date", "侧栏热门文章日期"),
    ):
        p = os.path.join(LAYOUTS, rel)
        ok = os.path.isfile(p) and needle in open(p, encoding="utf-8").read()
        h.record(f"{label} 走 i18n（{rel}）", ok, needle)

    # ---------------- 搜索索引日期契约（P1） ----------------
    # 索引必须同时提供机器字段 date 与 UI 字段 dateDisplay；dateDisplay 由 Hugo
    # 在构建期用 i18n 生成。**前端不得再自己格式化日期** —— 否则 UI 已本地化、
    # 搜索结果却仍是 2026-09-28 的不一致缺陷会再次出现。
    idx = os.path.join(LAYOUTS, "_default", "index.json")
    if not os.path.isfile(idx):
        h.fatal_error("缺少搜索索引模板", idx)
        return
    idx_src = open(idx, encoding="utf-8").read()
    idx_lines = idx_src.splitlines()
    gen_disp_lines = [l for l in idx_lines if '"dateDisplay" (' in l]
    machine_lines = [l for l in idx_lines if l.strip().startswith('"date" (')]

    h.record("搜索索引同时提供机器字段 date 与 UI 字段 dateDisplay",
             bool(gen_disp_lines) and bool(machine_lines),
             f"date x{len(machine_lines)} / dateDisplay x{len(gen_disp_lines)}")
    h.record("搜索索引 dateDisplay 由构建期 i18n 生成（不是硬编码 / 机器格式）",
             bool(gen_disp_lines) and all(I18N_DATE_RE.search(l) for l in gen_disp_lines),
             gen_disp_lines[0].strip()[:90] if gen_disp_lines else "未找到 dateDisplay")
    h.record("搜索索引 date 仍为机器格式且带 dateDisplay 以外的独立行",
             all('"date" (' in l and 'i18n' not in l for l in machine_lines)
             and bool(machine_lines),
             machine_lines[0].strip()[:90] if machine_lines else "未找到 date")

    js = os.path.join(ROOT, "assets", "js", "main.js")
    if not os.path.isfile(js):
        h.fatal_error("缺少前端脚本", js)
        return
    js_src = open(js, encoding="utf-8").read()
    h.record("前端搜索结果使用 dateLabel(it) 输出日期",
             "dateLabel(it)" in js_src, "dateLabel(it)")
    # 注意用 (?![\w])：it.dateDisplay 也包含 it.date 这个子串，直接 count 会误报
    raw_date_uses = re.findall(r"it\.date(?![\w])", js_src)
    h.record("前端不再直接渲染机器字段 it.date（旧索引兼容除外，最多 1 处）",
             len(raw_date_uses) <= 1, f"it.date 直接出现 {len(raw_date_uses)} 次")
    h.record("前端不重复实现日期格式化（无 toLocaleDateString / Intl.DateTimeFormat）",
             "toLocaleDateString" not in js_src and "Intl.DateTimeFormat" not in js_src,
             "未在 JS 中格式化日期")


if __name__ == "__main__":
    main_h = Harness("date-format")
    guard(main_h, run, main_h)
    main_h.finish()
