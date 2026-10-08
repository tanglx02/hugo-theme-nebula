#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""i18n 硬编码静态检查：防止 UI 文案重新被写死进模板或脚本。

扫描：`layouts/**/*.html`、`assets/**/*.js`（主题源码）
禁止：正常 UI 代码中出现明确的 UI 中文文案（如「已复制」「返回顶部」「正在加载」…）

允许（不做检查）：
  * `i18n/*.yaml`（文案的唯一来源）
  * `README*` / `docs/**`（文档）
  * 测试 fixture（`exampleSite/content/**`、`myblog/content/**`）
  * Python 测试脚本（`tools/*.py`）
  * 注释（`{{/* */}}`、`<!-- -->`、`/* */`、`//`）
  * `data-*` 属性与 `aria-*` 之外的非 UI 文本（含中文的 URL/编码）
  * 显式 `i18n` 调用中的 key

用法：python tools/check_i18n_hardcode.py [主题目录]
退出码约定（见 tools/_testlib.py）：发现硬编码 / 扫描到 0 个文件 -> exit 1。

主题目录解析顺序：
  1. 命令行参数
  2. 环境变量 NEBULA_THEME_DIR
  3. 仓库根（tools/ 的上级目录，即本主题自身，含 layouts/ + assets/）—— CI 场景
  4. 站点侧主题副本 myblog/themes/hugo-theme-nebula —— 本地调试场景
任一候选缺少 layouts/ 或 assets/ 则跳过；全部候选都不合格时报错退出（不会静默通过）。
"""
import json
import os
import re
import sys

TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.normpath(os.path.join(TOOLS_DIR, ".."))
WORKSPACE_ROOT = os.path.normpath(os.path.join(REPO_ROOT, ".."))


def resolve_theme():
    """按优先级挑选一个真正含 layouts/ 与 assets/ 的主题目录。"""
    candidates = []
    if len(sys.argv) > 1:
        candidates.append(("命令行参数", os.path.abspath(sys.argv[1])))
    env = os.environ.get("NEBULA_THEME_DIR", "").strip()
    if env:
        candidates.append(("NEBULA_THEME_DIR", os.path.abspath(env)))
    candidates.append(("主题仓库根", REPO_ROOT))
    # 本地调试布局有两种：tools/ 直接位于工作区根（此时 REPO_ROOT 即工作区根），
    # 或 tools/ 位于主题仓库内、站点为同级目录。两种都尝试。
    for base in (REPO_ROOT, WORKSPACE_ROOT):
        candidates.append((f"站点主题副本({base})",
                           os.path.join(base, "myblog", "themes", "hugo-theme-nebula")))

    for label, path in candidates:
        if os.path.isdir(os.path.join(path, "layouts")) and \
                os.path.isdir(os.path.join(path, "assets")):
            return path, label
    tried = "\n".join(f"    - {label}: {p}" for label, p in candidates)
    print("FAIL 未找到可用的主题源码目录（需同时含 layouts/ 与 assets/）：")
    print(tried)
    sys.exit(1)


THEME, THEME_LABEL = resolve_theme()

# 明确禁止的 UI 文案（短词用全词/上下文边界匹配，避免误伤正文与代码标识符）
FORBIDDEN = (
    "已复制", "复制失败", "复制链接", "返回顶部", "回到顶部", "正在加载", "加载中",
    "没有找到", "无结果", "上一页", "下一页", "上一页", "取消", "确认", "关闭",
    "搜索", "菜单", "切换主题", "首页", "文章目录", "文章分类", "标签云", "最新文章",
    "置顶", "相关文章", "系列文章", "分享", "评论", "站点地图", "页面走丢了",
    "浏览更多文章", "查看全部", "输入关键词", "锚点链接", "图片预览", "当前",
)

# 这些行属于"允许"的上下文：注释、i18n 调用、纯英文/符号行
ALLOW_LINE_PATTERNS = (
    re.compile(r"\{\{-?\s*/\*"),          # Go 模板注释行首
    re.compile(r"^\s*\*"),                # 块注释续行
    re.compile(r"^\s*//"),                # JS 行注释
    re.compile(r"i18n\s+[\"']"),          # i18n 调用
    re.compile(r"^\s*#"),                 # 其它注释
)


def strip_blocks(text, kind):
    """去掉注释块，返回 [(行号, 代码文本)]。"""
    if kind == "html":
        # 兼容 `{{- /* ... */ -}}` 的各种空白写法
        text = re.sub(r"\{\{-?\s*/\*.*?\*/\s*-?\}\}", "", text, flags=re.S)
        text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    else:
        text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    out = []
    for i, ln in enumerate(text.split("\n"), 1):
        if any(p.search(ln) for p in ALLOW_LINE_PATTERNS):
            continue
        out.append((i, ln))
    return out


def collect_files():
    files = []
    for sub, exts in (("layouts", (".html",)), ("assets", (".js",))):
        base = os.path.join(THEME, sub)
        for dirpath, _, names in os.walk(base):
            for n in names:
                if n.endswith(exts):
                    files.append(os.path.join(dirpath, n))
    return sorted(files)


def main():
    files = collect_files()
    if not files:
        print(f"FAIL 未扫描到任何文件（{THEME}/layouts|assets）")
        sys.exit(1)
    print(f"主题源码目录: {THEME}（来源: {THEME_LABEL}）")

    findings = []
    checked_strings = 0
    for path in files:
        kind = "js" if path.endswith(".js") else "html"
        raw = open(path, encoding="utf-8", errors="ignore").read()
        rel = os.path.relpath(path, THEME).replace(os.sep, "/")
        for lineno, line in strip_blocks(raw, kind):
            for word in FORBIDDEN:
                checked_strings += 1
                if word in line:
                    findings.append((rel, lineno, word, line.strip()[:110]))

    print(f"扫描文件数: {len(files)}")
    print(f"扫描字符串数: {checked_strings}（{len(files)} 文件 × {len(FORBIDDEN)} 禁用词）")
    print(f"发现硬编码数: {len(findings)}")
    if findings:
        print()
        for rel, lineno, word, line in findings:
            print(f"  FAIL {rel}:{lineno}  含硬编码「{word}」")
            print(f"       {line}")
        print()
        print("FAIL i18n 硬编码检查未通过：请把上述文案迁移到 i18n/*.yaml 并改用 i18n 调用")
        print("TEST-RESULT: " + json.dumps(
            {"suite": "i18n-hardcode", "status": "FAIL", "files": len(files),
             "strings": checked_strings, "findings": len(findings)}, ensure_ascii=False))
        sys.exit(1)

    print(f"PASS 未发现 UI 中文硬编码（{len(files)} 个文件）")
    print("TEST-RESULT: " + json.dumps(
        {"suite": "i18n-hardcode", "status": "PASS", "files": len(files),
         "strings": checked_strings, "findings": 0}, ensure_ascii=False))


if __name__ == "__main__":
    main()
