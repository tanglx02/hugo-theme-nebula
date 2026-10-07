#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把站点内调试完成的主题同步回主题仓库（含 exampleSite 与文档截图）。"""
import os
import shutil

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
SRC = os.path.join(ROOT, "myblog", "themes", "hugo-theme-nebula")
DST = os.path.join(ROOT, "hugo-theme-nebula")
SITE = os.path.join(ROOT, "myblog")

SKIP_IN_DST = {"docs", "exampleSite", ".git", "README.md", "LICENSE", ".gitignore"}

# 1) 同步主题文件（保留仓库自身的 docs/exampleSite/README 等）
if os.path.exists(SRC):
    for item in os.listdir(SRC):
        src_item = os.path.join(SRC, item)
        dst_item = os.path.join(DST, item)
        if os.path.isdir(src_item):
            # dirs_exist_ok=True：直接覆盖，不做递归删除（避免批量删除保护）
            shutil.copytree(src_item, dst_item, dirs_exist_ok=True)
        else:
            shutil.copy2(src_item, dst_item)
    print("主题文件已同步")

# 2) 同步 exampleSite（站点配置 + 内容 + 静态资源）
ex = os.path.join(DST, "exampleSite")
os.makedirs(ex, exist_ok=True)
shutil.copy2(os.path.join(SITE, "hugo.toml"), os.path.join(ex, "hugo.toml"))
for sub in ("content", "static"):
    src_sub = os.path.join(SITE, sub)
    dst_sub = os.path.join(ex, sub)
    if os.path.exists(src_sub):
        # 压力测试数据不进仓库（由 tools/gen_testdata.py 按需生成，CI 中自动生成）
        shutil.copytree(src_sub, dst_sub, dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns("zz-*"))
print("exampleSite 已同步")

# 3) 同步截图
shots = os.path.join(ROOT, "docs", "screenshots")
if os.path.exists(shots):
    d = os.path.join(DST, "docs", "screenshots")
    if os.path.exists(d):
        shutil.rmtree(d)
    shutil.copytree(shots, d)
    print("截图已同步")


# 4) 同步测试工具（CI 需要）
tools_src = os.path.join(ROOT, "tools")
tools_dst = os.path.join(DST, "tools")
if os.path.exists(tools_src):
    os.makedirs(tools_dst, exist_ok=True)
    for f in os.listdir(tools_src):
        if f.endswith((".py", ".toml")):
            shutil.copy2(os.path.join(tools_src, f), os.path.join(tools_dst, f))
    print("tools 已同步")


# 4) 同步测试工具（CI 需要）
tools_src = os.path.join(ROOT, "tools")
tools_dst = os.path.join(DST, "tools")
if os.path.exists(tools_src):
    os.makedirs(tools_dst, exist_ok=True)
    for f in os.listdir(tools_src):
        if f.endswith((".py", ".toml")):
            shutil.copy2(os.path.join(tools_src, f), os.path.join(tools_dst, f))
    print("tools 已同步")

print("同步完成 ->", DST)
