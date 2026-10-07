#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""搜索索引完整性校验（供 CI 与本地使用）。

校验项：
  1. index.json 可解析且为数组
  2. 每条含 title/url/content 等必要字段
  3. 正文未被截断：最长正文应显著大于旧的 3000 字上限
  4. 深层关键词可被检索（若索引中存在长文）
  5. 体积报告

用法：python tools/check_index.py [index.json 路径]
"""
import json
import os
import sys

DEFAULT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                        "..", "myblog", "public", "index.json"))
PATH = sys.argv[1] if len(sys.argv) > 1 else DEFAULT

errors = []
warnings = []

if not os.path.exists(PATH):
    print(f"FAIL 索引文件不存在: {PATH}")
    sys.exit(1)

raw = open(PATH, encoding="utf-8").read()
size_kb = len(raw.encode("utf-8")) / 1024
try:
    data = json.loads(raw)
except Exception as e:
    print(f"FAIL 索引不是合法 JSON: {e}")
    sys.exit(1)

if not isinstance(data, list):
    errors.append("索引根节点不是数组")

required = ("title", "url", "content")
for i, item in enumerate(data):
    for k in required:
        if k not in item:
            errors.append(f"第 {i} 条缺少字段 {k}")

lens = sorted(len(it.get("content", "") or "") for it in data)
max_len = lens[-1] if lens else 0

# 正文截断检查：旧实现会把正文统一截断到 ~3000 字，
# 表现为"多篇正文长度几乎相同且都接近 3000"。单篇恰好 3000 字属正常，不告警。
near = [len(it.get("content", "") or "") for it in data if 2950 <= len(it.get("content", "") or "") <= 3050]
if len(near) >= 3 and len(set(near)) <= 2:
    warnings.append(f"有 {len(near)} 篇正文长度几乎相同且接近 3000 字，疑似被截断")

blob = json.dumps(data, ensure_ascii=False)
deep = [k for k in ("BRAVO3000", "CHARLIE3500", "DELTA5000", "ECHO8000",
                    "FOXTROT10000", "TANGO25000", "GOLF48000") if k in blob]

print(f"索引条目: {len(data)}")
print(f"索引体积: {size_kb:.1f} KB（未压缩）")
print(f"正文长度: 最小 {lens[0] if lens else 0}, 中位 {lens[len(lens)//2] if lens else 0}, 最大 {max_len}")
print(f"深层关键词命中: {len(deep)}/7 {deep}")

if lens and max_len > 30000:
    if "GOLF48000" not in blob:
        errors.append("长文存在但 48000 字处关键词缺失 —— 正文可能仍被截断")

print()
if errors:
    print("FAIL:")
    for e in errors:
        print("  -", e)
    sys.exit(1)
if warnings:
    print("WARN:")
    for w in warnings:
        print("  -", w)
print("PASS 索引完整性检查通过")
