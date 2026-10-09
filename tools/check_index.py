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

# contentLimit 的影响只能由**站点配置**决定，不能靠 argv 猜测（避免测试自己
# 把"该检测"关掉）。默认按 exampleSite/hugo.toml 的实际配置解析；
# 可用 INDEX_CONTENT_LIMIT 显式覆盖以匹配非标准站点。
def _configured_content_limit():
    env = os.environ.get("INDEX_CONTENT_LIMIT")
    if env is not None and env.strip() != "":
        try:
            return int(env)
        except ValueError:
            return None
    for cfg in (os.path.join(REPO, "exampleSite", "hugo.toml"),
                os.path.join(os.path.dirname(BUILD_DIR), "hugo.toml")):
        if not os.path.isfile(cfg):
            continue
        try:
            import tomllib
            with open(cfg, "rb") as f:
                data = tomllib.load(f)
            val = (data.get("params") or {}).get("search", {}).get("contentLimit")
            return int(val) if val else 0
        except Exception:
            continue
    return 0


_env_limit_raw = _configured_content_limit()
# 0 / None 都表示"不截断" -> 此时正文必须完整（末尾标记必须在）
env_limit = _env_limit_raw if _env_limit_raw else None

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

# 正文**末尾**的唯一标记（由 tools/gen_testdata.py 生成，见 TAILMARK / TAILMARK_50K）。
# 只要正文被任何程度的截断，末尾标记必然消失 —— 这是"截断检测"的锚点。
# TEST-DEFECT-R2-001：旧版仅当 max_len > 30000 才查 GOLF48000，
# 于是"全部正文被截成 10 字"时 max_len=10，检查完全不触发 → 假绿 rc=0。
TAIL_MARKERS = ("TAILMARKER_9Z8Y7X", "TAILMARKER_50K_END")

# 整篇索引总体积下限（按条目数派生）。
# 压力测试样本的真实完整索引远超此值；若索引小到每条不足 1000 字节，
# 说明正文整段丢失（比"单条空正文"更严重，旧实现完全不看总量）。
# 实测分离度：完整索引 ~5.5KB/条、contentLimit=3000 ~1.6KB/条、
# "全部截成 10 字" ~0.38KB/条 —— 1000 字节/条 能把异常案例干净地判出来。
MIN_BYTES_PER_ENTRY = 1000


def _item_content(it):
    return (it.get("content") or "") if isinstance(it, dict) else ""


def check_truncation(data, shard_mode, merged=None, env_limit=None):
    """正文截断/丢失检测（适用于单索引与分片两种模式）。

    语义边界必须分清（这是 TEST-DEFECT-R2-001 的根因）：
      * **未配置 contentLimit**（env_limit=None）：正文必须完整 ——
        末尾标记必须在，否则就是被截断/丢失 → 判错。
        旧实现只在 `max_len > 30000` 时才查深处关键词，于是"全部正文被
        截成 10 字"时 max_len=10，检查根本不触发 → 假绿 rc=0。
      * **显式配置 contentLimit**：截断是**配置允许**的行为，不要求末尾标记；
        但要校验截断是**有界且一致的** —— 任何条目都不得超过 limit 太多，
        否则说明 limit 没有被正确应用。

    判据全部是**可证伪**的（标记在不在、长度是否超界），不用"长度接近 3000
    就算截断"这类启发式（3000 本来就是文档所载的配置值）。
    """
    all_content = [_item_content(it) for it in data if isinstance(it, dict)]
    joined = "\n".join(all_content)
    if shard_mode:
        joined += "\n" + "\n".join(
            v for v in (merged or {}).values() if isinstance(v, str))

    present = [m for m in TAIL_MARKERS if m in joined]

    if env_limit is None:
        # ---- 未配置截断：正文必须完整 ----
        if not present:
            errors.append(
                "正文末尾标记（TAILMARKER_*）全部缺失 —— 判定为正文被截断或丢失。"
                "压力测试数据在长文末尾埋有唯一标记，正常索引必然包含；"
                "标记消失只可能是截断（TEST-DEFECT-R2-001 的回归锚点）")
        else:
            print(f"末尾完整性标记: {present}")
        short = [i for i, c in enumerate(all_content)
                 if c and len(c) < 2000 and not any(m in c for m in TAIL_MARKERS)]
        if short and not present:
            errors.append(
                f"有 {len(short)} 条正文短于 2000 字符、整篇索引中又不存在任何末尾标记"
                f"—— 判定为正文被截断（未配置 contentLimit 时不应发生）")
    else:
        # ---- 显式配置 contentLimit：截断是预期行为，用"体积下限"兜底 ----
        # 不按"单条是否超过 limit"判错：截断经 partial 传参后，Hugo 对传入模板的
        # 字符串其 rune 计数与直接 `countrunes` 存在**有界偏差**（实测 limit=3000、
        # 中文 + HTML 实体正文出现 3448 的条目）。这是"软上限"特性：结果**只会
        # 高于** limit（绝不因多截而丢失正文），且不会 panic 终止整站构建。
        # 真正能证伪的是"整体小到不真实" —— 见下方 per-entry 体积检查。
        n = len(all_content) or 1
        print(f"contentLimit = {env_limit}（显式配置：截断属预期，改为校验整体体积下限"
              f" {MIN_BYTES_PER_ENTRY} 字节/条）")
        blob_bytes = len(raw.encode("utf-8")) + len(chunk_blob.encode("utf-8"))
        per_entry = blob_bytes / n
        print(f"体积/条目 = {per_entry:.0f} 字节"
              f"（下限 {MIN_BYTES_PER_ENTRY}）")
        if per_entry < MIN_BYTES_PER_ENTRY:
            errors.append(
                f"索引体积 {blob_bytes} 字节 / {n} 条 = {per_entry:.0f} 字节/条，"
                f"低于下限 {MIN_BYTES_PER_ENTRY} —— 正文可能被过度截断或整段丢失")

# ---------------- 正文校验 ----------------
chunk_blob = ""
merged_count = 0
merged_content = {}     # 分片模式：{ key: content } 合并结果（截断检测要用）
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
        merged_content = merged
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
if env_limit is None and len(near) >= 3 and len(set(near)) <= 2:
    errors.append(f"有 {len(near)} 篇正文长度几乎相同且接近 3000 字，判定为被截断"
                  f"（旧实现只 WARN，导致正文截断可上线：TEST-DEFECT-006）")

# ---------------- 截断 / 丢失检测（TEST-DEFECT-R2-001）----------------
# 单索引模式（env_limit is None）：正文必须完整 —— 末尾标记 + 体积下限。
# 分片模式：正文在 chunk 里，末尾标记与体积检测在 check_truncation /
# shard 分支里按 chunk 合并结果做。
if not shard_mode:
    check_truncation(data, shard_mode, merged=merged_content, env_limit=env_limit)
    total_bytes = len(raw.encode("utf-8"))
    n = len(data) or 1
    if env_limit is None and total_bytes / n < MIN_BYTES_PER_ENTRY:
        errors.append(
            f"索引 {total_bytes} 字节 / {n} 条 = {total_bytes / n:.0f} 字节/条，"
            f"低于下限 {MIN_BYTES_PER_ENTRY} —— 判定为正文整段丢失"
            f"（旧实现完全不看总量）")
else:
    check_truncation(data, shard_mode, merged=merged_content, env_limit=env_limit)

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
