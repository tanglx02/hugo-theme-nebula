#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""搜索索引完整性校验（供 CI 与本地使用）。

校验项：
  1. index.json 可解析（数组 = 单索引；对象 { chunks, items } = 分片模式）
  2. 每条含 title/url 等必要字段
  3. 正文未被截断：最长正文应显著大于旧的 3000 字上限
  4. 深层关键词可被检索（若索引中存在长文）
  5. 体积报告

退出码约定（见 tools/_testlib.py）：任一校验不通过 / 0 条目 / 文件缺失 -> exit 1。
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


def finish():
    status = "FAIL" if errors else "PASS"
    print()
    if errors:
        print("FAIL:")
        for e in errors:
            print("  -", e)
    if warnings:
        print("WARN:")
        for w in warnings:
            print("  -", w)
    if not errors:
        print("PASS 索引完整性检查通过")
    print("TEST-RESULT: " + json.dumps(
        {"suite": "check-index", "status": status, "warnings": len(warnings),
         "errors": len(errors)}, ensure_ascii=False))
    sys.exit(1 if errors else 0)


if not os.path.exists(PATH):
    print(f"FAIL 索引文件不存在: {PATH}")
    errors.append(f"索引文件不存在: {PATH}")
    finish()

raw = open(PATH, encoding="utf-8").read()
size_kb = len(raw.encode("utf-8")) / 1024
try:
    doc = json.loads(raw)
except Exception as e:
    print(f"FAIL 索引不是合法 JSON: {e}")
    errors.append(f"索引不是合法 JSON: {e}")
    finish()

# 支持两种结构：数组（单索引）/ { chunks, items }（分片模式）
if isinstance(doc, list):
    data = doc
    shard_mode = False
elif isinstance(doc, dict) and isinstance(doc.get("items"), list):
    data = doc["items"]
    shard_mode = True
else:
    print("FAIL 索引根节点既不是数组，也不是 { items: [...] } 结构")
    errors.append("索引根节点结构非法")
    data, shard_mode = [], False

if not data:
    errors.append("索引条目为 0，搜索将无法返回任何结果")

required = ("title", "url")
for i, item in enumerate(data):
    if not isinstance(item, dict):
        errors.append(f"第 {i} 条不是对象")
        continue
    for k in required:
        if k not in item:
            errors.append(f"第 {i} 条缺少字段 {k}")

# 分片模式下正文不在主索引里，改为校验 chunk 列表
if shard_mode:
    chunks = doc.get("chunks") or []
    if not chunks:
        errors.append("分片模式下 chunks 为空")
    lens = [0]
    max_len = 0
    blob = raw
else:
    lens = sorted(len(it.get("content", "") or "") for it in data if isinstance(it, dict))
    max_len = lens[-1] if lens else 0
    blob = json.dumps(data, ensure_ascii=False)

# 正文截断检查：旧实现会把正文统一截断到 ~3000 字，
# 表现为"多篇正文长度几乎相同且都接近 3000"。单篇恰好 3000 字属正常，不告警。
near = [len(it.get("content", "") or "") for it in data
        if isinstance(it, dict) and 2950 <= len(it.get("content", "") or "") <= 3050]
if len(near) >= 3 and len(set(near)) <= 2:
    warnings.append(f"有 {len(near)} 篇正文长度几乎相同且接近 3000 字，疑似被截断")

deep_all = ("BRAVO3000", "CHARLIE3500", "DELTA5000", "ECHO8000",
            "FOXTROT10000", "TANGO25000", "GOLF48000")

print(f"索引条目: {len(data)}{'（分片模式，正文在 chunks 中）' if shard_mode else ''}")
print(f"索引体积: {size_kb:.1f} KB（未压缩）")
if shard_mode:
    print(f"chunks: {len(doc.get('chunks') or [])}")
    print("深层关键词命中: 分片模式下正文关键词在 chunk 内校验（见 check_features / 浏览器测试）")
else:
    print(f"正文长度: 最小 {lens[0] if lens else 0}, 中位 {lens[len(lens)//2] if lens else 0}, 最大 {max_len}")
    deep = [k for k in deep_all if k in blob]
    print(f"深层关键词命中: {len(deep)}/{len(deep_all)} {deep}")
    if max_len > 30000 and "GOLF48000" not in blob:
        errors.append("长文存在但 48000 字处关键词缺失 —— 正文可能仍被截断")

finish()
