#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把站点内调试完成的主题同步回主题仓库（含 exampleSite、测试工具与文档截图）。

设计原则：
  * 不做递归删除（批量删除会被安全策略拦截，也可能误删仓库文件），统一用
    copytree(dirs_exist_ok=True) / copy2 覆盖；
  * 压力测试数据（zz-*）不进仓库，由 tools/gen_testdata.py 按需生成；
  * 仓库专属文件（README/LICENSE/docs/.github/.gitignore/tools）不被站点覆盖。
"""
import os
import shutil

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
SRC = os.path.join(ROOT, "myblog", "themes", "hugo-theme-nebula")
DST = os.path.join(ROOT, "hugo-theme-nebula")
SITE = os.path.join(ROOT, "myblog")

# 仓库自身的文件，站点侧不应覆盖
KEEP_IN_DST = {"docs", "exampleSite", ".github", ".git", "README.md", "LICENSE",
               ".gitignore", "tools"}

# ---------------------------------------------------------------- 1) 主题本体
if os.path.exists(SRC):
    for item in sorted(os.listdir(SRC)):
        if item in KEEP_IN_DST:
            continue
        src_item = os.path.join(SRC, item)
        dst_item = os.path.join(DST, item)
        if os.path.isdir(src_item):
            shutil.copytree(src_item, dst_item, dirs_exist_ok=True)
        else:
            shutil.copy2(src_item, dst_item)
    print("主题文件已同步")

# ------------------------------------------------------------- 2) exampleSite
ex = os.path.join(DST, "exampleSite")
os.makedirs(ex, exist_ok=True)
shutil.copy2(os.path.join(SITE, "hugo.toml"), os.path.join(ex, "hugo.toml"))
for sub in ("content", "static"):
    src_sub = os.path.join(SITE, sub)
    if os.path.exists(src_sub):
        # 压力测试数据不进仓库（由 tools/gen_testdata.py 按需生成，CI 中自动生成）
        shutil.copytree(src_sub, os.path.join(ex, sub), dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns("zz-*"))
print("exampleSite 已同步")

# ------------------------------------------------------------------ 3) 截图
shots = os.path.join(ROOT, "docs", "screenshots")
if os.path.exists(shots):
    shutil.copytree(shots, os.path.join(DST, "docs", "screenshots"), dirs_exist_ok=True)
    print("截图已同步")

# --------------------------------------------------------------- 4) 测试工具
tools_src = os.path.join(ROOT, "tools")
tools_dst = os.path.join(DST, "tools")
if os.path.exists(tools_src):
    os.makedirs(tools_dst, exist_ok=True)
    n = 0
    for f in sorted(os.listdir(tools_src)):
        if f.endswith((".py", ".toml", ".txt")):
            shutil.copy2(os.path.join(tools_src, f), os.path.join(tools_dst, f))
            n += 1
    print(f"测试工具已同步（{n} 个文件）")

print("同步完成 ->", DST)
