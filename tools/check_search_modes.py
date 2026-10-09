#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""搜索索引模式 / 阈值边界 构建测试（BUG-P1-002 回归）。

背景（v1.0.9 独立测试报告的 P1-002）
------------------------------------
默认 `mode = "auto"` 在正文总量超过 `autoThreshold`（默认 512000 字节）时会自动
切到分片，而分片分支调用 `resources.Publish`（Hugo 0.167 起才提供）。
Hugo 0.128–0.162 上因此**整站构建失败**；CI 矩阵虽跑了这些版本，但 exampleSite
内容量太小，永远走不到分片分支 —— 门禁"绿"了，缺陷还在。

本工具按**真实索引字节数**（不是文章篇数）验证：
  1. 低于阈值 -> auto 走单文件
  2. 恰好等于阈值 -> auto 走单文件（判定是严格 `>`）
  3. 高于阈值 -> auto 走分片（支持 Publish 的版本）/ 回退单文件并在旧版本仍能构建
  4. 显式 single -> 始终单文件（所有版本）
  5. 显式 shard -> >=0.167 分片；旧版本**明确报错**（不静默降级）
  6. 索引 URL / chunk 文件真实存在、可解析
  7. 全文搜索能力未被削减：长文后半部分的埋点关键词必须出现在索引（或其 chunk）中

"边界"如何精确命中：先用一个很大的阈值构建一次，量出**真实**正文总字节数 T，
再用 T-1 / T / T+1 作为 autoThreshold 各构建一次 —— 这样 1 与 2 的边界是按真实
字节数判定，而不是靠猜文章数。

用法：
    python3 tools/check_search_modes.py            # 用 PATH 中的 hugo
    HUGO_BIN=/path/to/hugo python3 tools/check_search_modes.py
退出码约定（见 tools/_testlib.py）：任一断言失败 / 构建异常 -> exit 1。
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
THEME_PARENT = os.path.dirname(ROOT)
THEME_NAME = os.path.basename(ROOT)
HUGO = os.environ.get("HUGO_BIN", "hugo")

WORK = os.path.join(tempfile.gettempdir(), "nebula-search-modes")
DEFAULT_THRESHOLD = 512000

# 长文后半部分的埋点：放在正文最后，专门用于证明"没有截断"
TAIL_MARKER = "TAILMARKER-ZZZ-9999"


def run(cmd, cwd=None):
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True,
                          encoding="utf-8", errors="ignore")


def hugo_version():
    r = run([HUGO, "version"])
    m = re.search(r"v?(\d+)\.(\d+)\.(\d+)", r.stdout or "")
    if not m:
        return None
    return tuple(int(x) for x in m.groups())


def supports_publish(ver):
    return ver[0] > 0 or ver[1] >= 167


def make_site(name, posts, with_search=True):
    """posts: [(slug, body_bytes_ascii)]，正文用 ASCII 填充，字节数可精确预期。"""
    site = os.path.join(WORK, name)
    shutil.rmtree(site, ignore_errors=True)
    os.makedirs(os.path.join(site, "content", "posts"), exist_ok=True)
    themes = os.path.join(site, "themes")
    os.makedirs(themes, exist_ok=True)
    link = os.path.join(themes, THEME_NAME)
    try:
        os.symlink(ROOT, link)
    except (OSError, NotImplementedError):
        shutil.copytree(ROOT, link, ignore=shutil.ignore_patterns(
            ".git", "public*", "tmp", "resources", "node_modules"))
    with open(os.path.join(site, "hugo.toml"), "w", encoding="utf-8") as f:
        f.write("baseURL = 'https://example.com/'\n"
                f"title = 'SearchModeTest'\n"
                f"theme = '{THEME_NAME}'\n"
                "disableKinds = ['taxonomy','term','rss','sitemap','robotsTXT']\n"
                "[params]\n"
                "  author = 'Tester'\n"
                + ("  [params.search]\n    enable = true\n" if with_search else "")
                + "[outputs]\n  home = ['HTML','JSON']\n")
    for slug, size in posts:
        body = ("a" * max(0, size - len(TAIL_MARKER))) + TAIL_MARKER
        with open(os.path.join(site, "content", "posts", slug + ".md"),
                  "w", encoding="utf-8") as f:
            f.write(f'---\ntitle: "{slug}"\ndate: 2026-01-01\n---\n\n{body}\n')
    return site


def threshold_cfg(site, value, mode=None):
    """写一个只覆盖 autoThreshold / mode 的附加配置，返回文件名（站点内）。"""
    name = "_thr.toml"
    with open(os.path.join(site, name), "w", encoding="utf-8") as f:
        f.write("[params.search]\n")
        if mode:
            f.write(f'  mode = "{mode}"\n')
        f.write(f"  autoThreshold = {value}\n")
    return name


def build(site, out):
    shutil.rmtree(out, ignore_errors=True)
    cfg = os.path.join(site, "_thr.toml")
    args = [HUGO, "-s", site, "-d", out, "--gc"]
    if os.path.isfile(cfg):
        args += ["--config", "hugo.toml,_thr.toml"]
    r = run(args)
    errs = [ln for ln in (r.stdout + r.stderr).splitlines() if "ERROR" in ln.upper()]
    return r.returncode, (errs[0] if errs else ""), r.stdout + r.stderr


def index_info(out):
    p = os.path.join(out, "index.json")
    if not os.path.isfile(p):
        return None
    d = json.load(open(p, encoding="utf-8"))
    if isinstance(d, dict):
        items = d.get("items") or []
        return {"shard": True, "items": items, "chunks": d.get("chunks") or []}
    return {"shard": False, "items": d, "chunks": []}


def content_bytes(info):
    return sum(len((i.get("content") or "").encode("utf-8")) for i in info["items"])


def blob_of(out, info):
    parts = [json.dumps(info["items"], ensure_ascii=False)]
    for u in info["chunks"]:
        rel = u.split("://", 1)[-1]
        rel = rel[rel.find("/"):] if "/" in rel else "/" + rel
        for cand in (os.path.join(out, rel.lstrip("/")),
                     os.path.join(out, os.path.basename(rel))):
            if os.path.isfile(cand):
                parts.append(open(cand, encoding="utf-8").read())
                break
    return "".join(parts)


def run_all(h):
    ver = hugo_version()
    if ver is None:
        h.fatal_error("无法获取 hugo 版本（HUGO_BIN 是否正确？）", HUGO)
        return
    print(f"hugo = {'.'.join(map(str, ver))}   supports resources.Publish = {supports_publish(ver)}")
    os.makedirs(WORK, exist_ok=True)

    # ---------------- A. 精确边界：真实正文总字节数 T，阈值 T-1 / T / T+1 ----------------
    site = make_site("small", [("edge", 3000)])
    huge = threshold_cfg(site, 999999999)
    out = os.path.join(WORK, "out-small")
    rc, err, log = build(site, out)
    if rc != 0:
        h.fatal_error("边界站点构建失败", err or log[-200:])
        return
    info = index_info(out)
    if not info:
        h.fatal_error("未生成 index.json", out)
        return
    T = content_bytes(info)
    print(f"真实正文总字节数 T = {T}")
    h.record("可量出真实正文总字节数（用于精确边界判定）", T > 0, f"T={T}")

    cases = [(T - 1, True, "低于阈值"), (T, False, "恰好等于阈值"), (T + 1, False, "高于阈值")]
    for thr, expect_shard, label in cases:
        threshold_cfg(site, max(0, thr))
        rc, err, log = build(site, out)
        if rc != 0:
            h.record(f"auto 阈值 {label}（threshold={thr}）可构建", False, err or log[-160:])
            continue
        inf = index_info(out)
        shard = bool(inf and inf["shard"])
        if expect_shard:
            if supports_publish(ver):
                h.record(f"auto 阈值 {label} -> 分片", shard,
                         f"threshold={thr} T={T} shard={shard}")
            else:
                # 旧版本：必须回退为单文件且**构建成功**（这正是 BUG-P1-002 的修复点）
                h.record(f"auto 阈值 {label} -> 旧版本回退单文件且构建成功",
                         (not shard) and rc == 0, f"shard={shard} rc={rc}")
        else:
            h.record(f"auto 阈值 {label} -> 单文件", not shard,
                     f"threshold={thr} T={T} shard={shard}")

    # ---------------- B. 默认阈值 512000：真正"低于/高于"的站点 ----------------
    for name, size, expect_shard_default in (
            ("below", 400000, False),      # 400KB 正文 < 512000 -> 单文件
            ("above", 600000, True)):      # 600KB 正文 > 512000 -> 分片（或旧版本回退）
        s = make_site("big-" + name, [("long", size)])
        cfg = os.path.join(s, "_thr.toml")
        if os.path.isfile(cfg):
            os.remove(cfg)                 # 用主题默认阈值
        o = os.path.join(WORK, "out-" + name)
        rc, err, log = build(s, o)
        if rc != 0:
            h.record(f"默认阈值 512000：{name} 站点可构建", False, err or log[-160:])
            continue
        inf = index_info(o)
        shard = bool(inf and inf["shard"])
        if expect_shard_default and not supports_publish(ver):
            ok = (not shard) and rc == 0
            h.record("默认阈值 512000：超阈值站点在旧 Hugo 上回退单文件并构建成功", ok,
                     f"正文≈{size}B shard={shard} rc={rc}")
        else:
            h.record(f"默认阈值 512000：{'超' if expect_shard_default else '低于'}阈值站点 -> "
                     f"{'分片' if expect_shard_default else '单文件'}",
                     shard == expect_shard_default,
                     f"正文≈{size}B shard={shard}")
        if inf and expect_shard_default and supports_publish(ver):
            missing = [u for u in inf["chunks"]
                       if not os.path.isfile(os.path.join(o, u.lstrip("/")))]
            h.record("分片的 chunk URL 全部对应真实文件", not missing,
                     f"缺失 {missing[:3]}" if missing else f"{len(inf['chunks'])} 个 chunk 均存在")
            h.record("分片模式下主索引不再内联正文（避免语义混淆）",
                     content_bytes(inf) == 0, f"内联字节={content_bytes(inf)}")
            h.record("全文能力未削减：长文末尾埋点出现在 chunk 中",
                     TAIL_MARKER in blob_of(o, inf), TAIL_MARKER)

    # ---------------- C. 显式模式 ----------------
    site = make_site("explicits", [("one", 3000)])
    for mode, expect_shard in (("single", False), ("shard", True)):
        threshold_cfg(site, 999999999, mode=mode)     # 关掉 auto 的自动判断
        out = os.path.join(WORK, "out-mode-" + mode)
        rc, err, log = build(site, out)
        if mode == "shard" and not supports_publish(ver):
            ok = rc != 0 and "需要 Hugo >= 0.167.0" in log
            h.record("显式 shard 在旧 Hugo 上明确报错并给出替代方案（不静默降级）", ok,
                     f"rc={rc} 提示={(err or '')[:90]}")
            continue
        if rc != 0:
            h.record(f"显式 {mode} 模式可构建", False, err or log[-160:])
            continue
        inf = index_info(out)
        shard = bool(inf and inf["shard"])
        h.record(f"显式 {mode} 模式 -> {'分片' if expect_shard else '单文件'}",
                 shard == expect_shard, f"shard={shard}")
        if inf:
            h.record(f"显式 {mode}：长文末尾埋点可检索（全文未截断）",
                     TAIL_MARKER in blob_of(out, inf), TAIL_MARKER)

    # 默认阈值下的单文件站点也必须保留全文
    inf = index_info(os.path.join(WORK, "out-below"))
    if inf:
        h.record("单文件模式下长文末尾埋点存在于索引中（全文未截断）",
                 TAIL_MARKER in blob_of(os.path.join(WORK, "out-below"), inf), TAIL_MARKER)


if __name__ == "__main__":
    main_h = Harness("search-modes")
    guard(main_h, run_all, main_h)
    main_h.finish()
