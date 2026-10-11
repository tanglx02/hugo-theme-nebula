#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""check_index.py 的 contentLimit 模式测试（TEST-DEFECT-R3-011）。

背景：check_index.py 用 TAILMARKER（正文末尾唯一标记）检测意外截断 ——
未配置 contentLimit 时正文必须完整；但**有意配置 contentLimit** 的构建里
末尾标记被合法截掉。旧实现的配置解析只读 exampleSite/hugo.toml，一旦构建
用了 `--config` 叠加层（CI 的 shard-override 模式、check_search_modes 的
阈值探针），就探测不到 contentLimit -> 合法构建被假红。

本测试用**合成索引**直接驱动 check_index.py（子进程 + 真实退出码），
覆盖五种行为，同时就是"默认模式与截断模式行为均正确"的故障注入自证：

    1. 默认（未配置 contentLimit）+ 完整正文（含末尾标记）   -> rc 0
    2. 默认 + 正文被截断（末尾标记消失）                     -> rc 1  （检测仍然有效）
    3. 配置 contentLimit（叠加层文件）+ 合法有界截断          -> rc 0  （不再假红）
    4. 配置 contentLimit + 条目大幅超过上限（limit 未生效）   -> rc 1
    5. 配置 contentLimit + 正文整段丢失（体积/条目过低）      -> rc 1

退出码约定（见 tools/_testlib.py）：任一断言失败 -> exit 1。
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _testlib import Harness, guard  # noqa: E402

REPO = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
CHECK_INDEX = os.path.join(REPO, "tools", "check_index.py")

TAIL = "TAILMARKER_9Z8Y7X"


def content(chars, tail=False):
    """生成 chars 长度的合成正文（ASCII，保证 1 字节/字符）。"""
    unit = "Nebula search index integrity probe. "
    base = (unit * (chars // len(unit) + 2))[:chars]
    return (base + " " + TAIL) if tail else base


def make_site(tmp, entries, site_limit=None):
    """在 tmp 下构造 BUILD_DIR=public + 可选的叠加配置 hugo.toml，返回 BUILD_DIR。"""
    build = os.path.join(tmp, "public")
    os.makedirs(build, exist_ok=True)
    idx = [{"title": f"t{i}", "url": f"/posts/p{i}/", "key": f"k{i}", "content": c}
           for i, c in enumerate(entries)]
    with open(os.path.join(build, "index.json"), "w", encoding="utf-8") as f:
        json.dump(idx, f, ensure_ascii=False)
    if site_limit:
        # 模拟 `--config hugo.toml,overlay.toml` 的叠加层（不叫 hugo.toml，
        # 证明配置感知真的覆盖叠加层而不只是主配置）
        with open(os.path.join(tmp, "overlay-limit.toml"), "w", encoding="utf-8") as f:
            f.write(f'[params.search]\n  contentLimit = {site_limit}\n')
    return build


def run_check(build):
    env = dict(os.environ)
    env.pop("INDEX_CONTENT_LIMIT", None)     # 测试必须走"配置感知"路径而非环境变量
    p = subprocess.run([sys.executable, CHECK_INDEX,
                        os.path.join(build, "index.json"), build],
                       capture_output=True, text=True, encoding="utf-8",
                       errors="ignore", env=env, timeout=120)
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def run(h):
    tmp = tempfile.mkdtemp(prefix="nebula-checkidx-")
    try:
        # ---- 1 默认 + 完整正文 -> PASS ----
        b = make_site(os.path.join(tmp, "s1"), [content(1500, tail=True)] * 4)
        rc, out = run_check(b)
        h.record("默认模式：完整正文（末尾标记在场）-> 通过", rc == 0,
                 out.splitlines()[-2][:100] if rc else "rc=0")

        # ---- 2 默认 + 截断 -> FAIL（检测未被削弱）----
        b = make_site(os.path.join(tmp, "s2"), [content(10)] * 4)
        rc, out = run_check(b)
        h.record("默认模式：正文被截断（末尾标记消失）-> 必须判红",
                 rc != 0 and ("末尾标记" in out or "TAILMARKER" in out),
                 f"rc={rc}")

        # ---- 3 配置 contentLimit（叠加层）+ 合法有界截断 -> PASS（假红修复）----
        b = make_site(os.path.join(tmp, "s3"), [content(3200)] * 4, site_limit=3000)
        rc, out = run_check(b)
        h.record("配置模式（叠加层 contentLimit=3000）：合法有界截断 -> 通过（R3-011 假红修复）",
                 rc == 0, "rc=0" if rc == 0 else out[-300:])

        # ---- 4 配置 contentLimit + 条目大幅超上限 -> FAIL ----
        entries = [content(1500)] * 3 + [content(5000)]
        b = make_site(os.path.join(tmp, "s4"), entries, site_limit=300)
        rc, out = run_check(b)
        h.record("配置模式：条目长度超过 2×limit+2000（limit 未生效）-> 必须判红",
                 rc != 0 and "limit 未被正确应用" in out, f"rc={rc}")

        # ---- 5 配置 contentLimit + 正文整段丢失 -> FAIL ----
        b = make_site(os.path.join(tmp, "s5"), [content(10)] * 4, site_limit=3000)
        rc, out = run_check(b)
        h.record("配置模式：正文整段丢失（体积/条目低于下限）-> 必须判红",
                 rc != 0 and "低于下限" in out, f"rc={rc}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main_h = Harness("check-index-modes")
    guard(main_h, run, main_h)
    main_h.finish()
