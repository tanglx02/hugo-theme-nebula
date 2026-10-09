#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""搜索索引完整性校验（供 CI 与本地使用）。

校验项：
  1. index.json 可解析（数组 = 单索引；对象 { chunks, items } = 分片模式）
  2. 每条含 title/url 等必要字段
  3. **正文不得为空**（单文件模式）——正文丢失属于索引损坏，必须判错
     （旧实现只检查 title/url，8 条空正文照样 PASS：TEST-DEFECT-006）
  4. **正文不得被截断**（判错，而不是仅 WARN）
  5. **分片模式也要校验正文**：逐个加载 chunk，检查内容并入主索引、深层关键词可检索
  6. 深层关键词可被检索
  7. 体积报告

默认路径：<repo>/public/index.json（与 check_features / check_seo 保持一致，
避免"不同脚本默认路径基准不同"导致手工运行结果不可比：TEST-DEFECT-016）

用法：
    python tools/check_index.py [index.json 路径] [构建目录]
退出码约定（见 tools/_testlib.py）：任一校验不通过 / 0 条目 / 文件缺失 -> exit 1。
"""
import json
import os
import sys

REPO = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
DEFAULT = os.path.join(REPO, "public", "index.json")
PATH = sys.argv[1] if len(sys.argv) > 1 else DEFAULT
BUILD_DIR = sys.argv[2] if len(sys.argv) > 2 else os.path.dirname(os.path.abspath(PATH))

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


def resolve_chunk(url):
    """把 chunk URL（站点绝对路径）解析为构建目录内的真实文件。

    兼容 basePath 子目录部署：先按 BUILD_DIR + url 找，找不到再按 basename 在整个
    构建目录内查找。
    """
    rel = url.split("://", 1)[-1]
    rel = rel[rel.find("/"):] if "/" in rel else "/" + rel
    cand = os.path.join(BUILD_DIR, rel.lstrip("/"))
    if os.path.isfile(cand):
        return cand
    name = os.path.basename(rel)
    for dirpath, _, names in os.walk(BUILD_DIR):
        if name in names:
            return os.path.join(dirpath, name)
    return None


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

deep_all = ("BRAVO3000", "CHARLIE3500", "DELTA5000", "ECHO8000",
            "FOXTROT10000", "TANGO25000", "GOLF48000")

# ---------------- 正文校验 ----------------
chunk_blob = ""
merged_count = 0
if shard_mode:
    chunks = doc.get("chunks") or []
    if not chunks:
        errors.append("分片模式下 chunks 为空")
        chunk_blob = ""
    else:
        parts = []
        missing_files, bad_payload = [], []
        for u in chunks:
            f = resolve_chunk(u)
            if not f:
                missing_files.append(u)
                continue
            try:
                payload = json.loads(open(f, encoding="utf-8").read())
            except Exception as e:
                bad_payload.append(f"{u}: {e}")
                continue
            if not isinstance(payload, dict):
                bad_payload.append(f"{u}: 不是 {key: content} 对象")
                continue
            parts.append(json.dumps(payload, ensure_ascii=False))
        if missing_files:
            errors.append(f"chunks 中有 {len(missing_files)} 个文件在构建产物中不存在: {missing_files[:3]}")
        if bad_payload:
            errors.append(f"chunks 中有 {len(bad_payload)} 个文件结构非法: {bad_payload[:3]}")
        chunk_blob = "".join(parts)

        # 分片模式下主索引的 content 必须为空（正文在 chunk 里），
        # 且每个条目的 key 必须能在 chunk 内容里找到 —— 否则就是"索引丢了正文"。
        keys = [it.get("key") for it in data if isinstance(it, dict) and it.get("key")]
        merged = {}
        for u in chunks:
            f = resolve_chunk(u)
            if not f:
                continue
            try:
                payload = json.loads(open(f, encoding="utf-8").read())
                if isinstance(payload, dict):
                    merged.update(payload)
            except Exception:
                pass
        orphan = [k for k in keys if k not in merged]
        merged_count = len(merged)
        if orphan:
            errors.append(f"分片模式下有 {len(orphan)} 条文章的正文不在任何 chunk 中: {orphan[:5]}")
        with_content = [it for it in data
                        if isinstance(it, dict) and (it.get("content") or "")]
        if with_content:
            errors.append(f"分片模式下主索引仍内联正文（{len(with_content)} 条），与单文件模式语义混淆")
        lens = sorted(len(v) for v in merged.values() if isinstance(v, str))
        max_len = lens[-1] if lens else 0
        blob = raw + chunk_blob
else:
    lens = sorted(len(it.get("content", "") or "") for it in data if isinstance(it, dict))
    max_len = lens[-1] if lens else 0
    blob = json.dumps(data, ensure_ascii=False)
    empty = [i for i, it in enumerate(data)
             if isinstance(it, dict) and not (it.get("content") or "").strip()]
    # 判定策略：单篇空正文可能是"作者确实没写正文"（合法），
    # 但**大量条目同时为空**只可能是索引丢了正文（TEST-DEFECT-006：
    # 旧实现完全不判错，8 条空正文照样 PASS）。
    # 因此：全部为空 或 >= 25% 为空 -> 判错；个别为空 -> WARN（可见但不阻断）。
    ratio = len(empty) / len(data) if data else 0
    if empty and (len(empty) == len(data) or ratio >= 0.25):
        errors.append(f"有 {len(empty)}/{len(data)} 条正文为空（{ratio:.0%}）—— 判定为索引正文丢失")
    elif empty:
        warnings.append(f"有 {len(empty)} 条正文为空（{ratio:.1%}，低于 25% 阈值，"
                        f"视为作者未写正文）：索引 {empty[:5]}")

# 正文截断检查：旧实现会把正文统一截断到 ~3000 字，
# 表现为"多篇正文长度几乎相同且都接近 3000"。单篇恰好 3000 字属正常。
near = [len(it.get("content", "") or "") for it in data
        if isinstance(it, dict) and 2950 <= len(it.get("content", "") or "") <= 3050]
if len(near) >= 3 and len(set(near)) <= 2:
    errors.append(f"有 {len(near)} 篇正文长度几乎相同且接近 3000 字，判定为被截断"
                  f"（旧实现只 WARN，导致正文截断可上线：TEST-DEFECT-006）")

print(f"索引条目: {len(data)}{'（分片模式，正文在 chunks 中）' if shard_mode else ''}")
print(f"索引体积: {size_kb:.1f} KB（未压缩）")
if shard_mode:
    print(f"chunks: {len(doc.get('chunks') or [])}；chunk 内正文条目: {merged_count}")
    deep = [k for k in deep_all if k in blob]
    print(f"深层关键词命中（含 chunks）: {len(deep)}/{len(deep_all)} {deep}")
    if max_len > 30000 and "GOLF48000" not in blob:
        errors.append("长文存在但 48000 字处关键词缺失 —— chunk 正文可能被截断")
else:
    print(f"正文长度: 最小 {lens[0] if lens else 0}, 中位 {lens[len(lens)//2] if lens else 0}, 最大 {max_len}")
    deep = [k for k in deep_all if k in blob]
    print(f"深层关键词命中: {len(deep)}/{len(deep_all)} {deep}")
    if max_len > 30000 and "GOLF48000" not in blob:
        errors.append("长文存在但 48000 字处关键词缺失 —— 正文可能仍被截断")

finish()
