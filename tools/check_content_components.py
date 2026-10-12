#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""功能三验收：技术内容组件。

覆盖：
  * **Markdown 提示块**（GitHub Alerts 风格：NOTE/TIP/IMPORTANT/WARNING/CAUTION）；
  * **标签页**（tabs / tab）与**步骤**（steps / step），含**交叉嵌套**；
  * 面板内代码块复用统一管线（语言标签 + 一键复制）；
  * 多语言（zh-CN / zh-TW / en）+ Hugo 0.128.0 ~ 0.167.0 版本矩阵；
  * 跨版本回归：多语言站点 alias 空值防御。

其余组件（文件树 / 按钮 / 徽标 / 画廊 / 可选 Mermaid+KaTeX）会陆续并入后续小节。

断言的都是**直接证明真实行为**的东西，不是"脚本没报错"：

A. 构建产物（真实 Hugo 构建 + 解析 HTML / CSS）
   A1 五种已知类型各自生成提示块，class 与类型一一对应；
   A2 五种图标**互不相同**（防"复制 note 图标"这类静默退化）；
   A3 默认标题走 i18n：中文站中文、英文站英文；
   A4 自定义标题（[!WARNING] 标题）优先于 i18n 默认；
   A5 未知类型（[!BOGUS]）**不**生成提示块，也不让构建失败；
   A6 **普通引用逐字节不变**：与"同一主题去掉本钩子"的构建产物做全站 diff=0；
   A7 CSS 提示块样式齐全，且复用设计变量（暗色模式无需第二套颜色）；
   A8 零 JS：产物中提示块不含 <script>；不引用任何第三方域名。

B. 多语言 / 版本矩阵
   B1 简体中文、繁體中文、English 三种站点语言的默认标题正确；
   B2 Hugo 0.128.0 优雅退化（无 md-alert、构建成功、marker 行可见）；
   B3 Hugo 0.148.0 / 0.162.0 / 0.166.0 / 0.167.0 均正常生成。

C. 功能三（第二、三项）：标签页与步骤
   C1 tabs 容器 id 唯一 / tab 按钮与 tabpanel 计数 / aria-selected 初值；
   C2 服务端写死 hidden（无 JS 才不会面板重叠）；
   C3 步骤 <ol> 语义 + 可选标题（无标题不输出空标题）；
   C4 **交叉嵌套内容完整**（回归：unsafe=false 下 markdownify 丢弃原始 HTML）；
   C5 面板/步骤内代码块复用统一管线（语言标签 + 复制按钮）；
   C6 零 JS 内容不丢（纯 CSS 覆盖 UA 的 [hidden]）+ 序号由 CSS counter 生成；
   C7 无障碍 / 打印展开 / prefers-reduced-motion；
   C8 tabs.js 按需注入（用了 tabs 的页面才有）且带 fingerprint；
   C9 组件页零第三方请求；
   C10 五版本产物结构签名完全一致；
   C11 反证：去掉 token 机制后嵌套内容必须真的丢失（证明 C4 有区分力）。

用法：
    python tools/check_content_components.py
环境变量：
    HUGO_BIN          Hugo 可执行文件（默认 hugo，用于"当前版本"相关断言）
    HUGO_MATRIX_DIR   Hugo 版本矩阵目录（B2/B3/C10/C 小节）
"""

import difflib
import io
import os
import re
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _testlib import Harness, guard, safe_rmtree  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = os.path.join(REPO, "exampleSite")
THEMES_DIR = os.path.dirname(REPO)
HUGO = os.environ.get("HUGO_BIN", "hugo")
OUT_ROOT = os.path.join(REPO, "tmp")
# Hugo 版本矩阵目录：默认指向工作区内的验收环境（可用 HUGO_MATRIX_DIR 覆盖）。
# 找不到时**不是**致命错误，而是跳过 B2/B3 并在汇总里说明（CI 里由 compat_matrix 覆盖）。
HUGO_ROOT = os.environ.get(
    "HUGO_MATRIX_DIR",
    os.path.join(os.path.dirname(os.path.dirname(REPO)),
                 "tmp", "hugo博客主题验收测试", "r2", "_env", "hugo"))

ZERO_TMPL = """baseURL = 'https://z.example/'
title = 'cc probe'
theme = 'hugo-theme-nebula'
defaultContentLanguage = 'zh-cn'
disableKinds = ['taxonomy', 'term', 'RSS', 'sitemap', 'robotsTXT', '404', 'section']

[languages]
  [languages.zh-cn]
    weight = 1
    contentDir = 'content'
  [languages.en]
    weight = 2
    contentDir = 'content-en'
  [languages.zh-TW]
    weight = 3
    contentDir = 'content-zh-tw'
"""

# 探针正文：覆盖 5 种类型 + 自定义标题 + 未知类型 + 普通引用 + 嵌套
PROBE_MD = """---
title: "CC Probe"
date: 2024-05-06
draft: false
---

> 普通单段引用

尾随段落 A

> 普通多段一
>
> 普通多段二

> [!NOTE]
> 说明正文

> [!TIP]
> 提示正文

> [!IMPORTANT]
> 重要正文

> [!WARNING]
> 警告正文

> [!CAUTION]
> 注意正文

> [!WARNING] 自定义标题
> 自定义正文

> [!BOGUS]
> 未知类型正文

> 末尾引用
"""

# 功能三（第二、三项）探针：标签页 tabs/tab + 步骤 steps/step + 交叉嵌套。
# 计数期望（供 C1 断言）：
#   tabs 容器 2；tab 按钮 4；tabpanel 4；每容器首面板可见其余 hidden（共 2 hidden）；
#   steps ol 2；li.step 5；带标题的 step-title 3；面板/步骤内代码块 5（各带复制按钮）。
PROBE_COMPONENTS_MD = """---
title: "CC Components"
date: 2024-05-07
draft: false
---

## 1 独立标签页

{{< tabs >}}
{{< tab "Linux" >}}

```bash
apt-get update
```

{{< /tab >}}
{{< tab "Windows" >}}

```powershell
winget install X
```

{{< /tab >}}
{{< /tabs >}}

## 2 独立步骤（含可选标题）

{{< steps >}}
{{< step "准备" >}}

```bash
uname -a
```

{{< /step >}}
{{< step >}}

无标题步骤正文 NOHEAD-TEXT

{{< /step >}}
{{< step "收尾" >}}

完成 COMPLETE-TEXT

{{< /step >}}
{{< /steps >}}

## 3 标签页内嵌步骤（回归：嵌套内容不得被 markdownify 丢弃）

{{< tabs >}}
{{< tab "脚本" >}}

{{< steps >}}
{{< step >}}

```bash
curl -fsSL https://example.com/install.sh | bash
```

{{< /step >}}
{{< step >}}

verify NESTED-VERIFY

{{< /step >}}
{{< /steps >}}

{{< /tab >}}
{{< tab "手动" >}}

手动说明 MANUAL-TEXT

{{< /tab >}}
{{< /tabs >}}
"""

# 功能三:文件树 / 徽标 / 按钮 scheme 校验 / 折叠块 的探针。
#
# 特意塞进正文的「危险输入」——全部必须在产物层被安全处理：
#   * 文件名里的 <x> / & / 引号 / 反引号（HTML 与 Markdown 双重敏感）
#   * badge 变体的 class 逃逸尝试（x" onmouseover="alert(1)）
#   * button 的 javascript: / 空白绕过 / vbscript: / data:text/html / file: / 空值
#
# ⚠ `@@TAB@@` / `@@NL@@` 是**占位符**，由 probe_media() 在写入探针时替换成
#   真实的制表符与换行符（见函数说明）。为什么不直接把控制字符写在源码里：
#   （a）编辑器/工具链容易在保存时把制表符转成空格，让"空白绕过"用例静默失效；
#   （b）源码里出现裸换行会破坏这个多行字符串本身的缩进语义。
#   这同时提醒我们：`java\<TAB>script:` 才是浏览器真正会执行的绕过形态，
#   而 `java\tscript:`（字面反斜杠）只是一个普通相对路径（已验证会被安全编码）。
#
# 期望计数（供 D 段断言）：
#   filetree 2；badge 5；a.btn 4（外链 / mailto / 站内相对 / tel）；
#   span.btn-disabled 6（javascript: / TAB 空白绕过 / vbscript: /
#   data:text/html / file: / 空值）；
#   nb-details 2（1 闭合 1 open）。
#
# ⚠ 关于"换行绕过"：Hugo 的 shortcode **词法分析器**拒绝带裸换行的引号参数
#   （`unterminated quoted string in shortcode parameter-argument`），因此
#   `java<NL>script:` 这类绕过在本主题的短代码入口**根本无法构造**。这一点由
#   run_newline_arg_check() 单独断言（构建必须失败）。可构造的空白绕过只有
#   制表符，由下面的 TAB 用例覆盖（必须在模板层被"先剥空白再判定"拦下）。
PROBE_MEDIA_MD = """---
title: "CC Media"
date: 2024-05-08
draft: false
---

## 1 文件树（含特殊字符文件名）

{{< filetree "示例项目结构" >}}
my-app/
├── package.json
├── src/
│   ├── a&b.ts
│   ├── <x>.ts
│   └── "q" 'r' `s`.ts
└── README.md
{{< /filetree >}}

无标题的文件树（属性式 title）：

{{< filetree title="属性标题" >}}
root/
└── only.txt
{{< /filetree >}}

## 2 徽标

默认 {{< badge "v1.0.9" >}}
指定变体 {{< badge "稳定" "success" >}}
具名参数 {{< badge text="已弃用" type="danger" >}}
未知变体 {{< badge "草稿" "bogus" >}}
注入尝试 {{< badge "坏" "x\\" onmouseover=\\"alert(1)" >}}

## 3 按钮（URL scheme 校验）

{{< button "外链" "https://example.com/a?x=1&y=2" >}}
{{< button "邮件" "mailto:hi@example.com" >}}
{{< button "站内" "posts/other/" >}}
{{< button "电话" "tel:+8610000000000" >}}
{{< button "JS" "javascript:alert(1)" >}}
{{< button "TAB 绕过" "java@@TAB@@script:alert(1)" >}}
{{< button "VB" "vbscript:msgbox(1)" >}}
{{< button "DATA" "data:text/html,<script>alert(1)</script>" >}}
{{< button "文件" "file:///etc/passwd" >}}
{{< button "空" "" >}}

## 4 折叠块

{{< details "默认闭合" >}}
折叠正文 DETAILS-CLOSED-TEXT
{{< /details >}}

{{< details title="默认展开" open="true" >}}
展开正文 DETAILS-OPEN-TEXT
{{< /details >}}
"""

HUGO_VERSIONS = ("0.128.0", "0.148.0", "0.162.0", "0.166.0", "0.167.0")
# 可执行文件名随平台变化：Windows 是 hugo.exe，CI（Linux）是 hugo。
HUGO_EXE = "hugo.exe" if os.name == "nt" else "hugo"


def hugo_matrix():
    """返回 {版本: 可执行文件路径}；目录不存在则返回空 dict（由调用方判为致命错误）。"""
    got = {}
    if not os.path.isdir(HUGO_ROOT):
        return got
    for v in HUGO_VERSIONS:
        exe = os.path.join(HUGO_ROOT, v, HUGO_EXE)
        if os.path.isfile(exe):
            got[v] = exe
    return got


KNOWN = ["note", "tip", "important", "warning", "caution"]
H = Harness("content_components")


# --------------------------------------------------------------------------- #
# 工具
# --------------------------------------------------------------------------- #
def probe_media(body):
    """把 PROBE_MEDIA_MD 里的占位符替换成真实控制字符。

    为什么需要占位符（而不是直接把制表符写进源码）：
      * 编辑器/格式化工具很容易在保存时把制表符改成空格，而"空白绕过"用例
        一旦失去那个制表符就**静默失效**（依然构建成功、断言依然通过，
        但实际什么都没测到）；
      * 源码中出现裸换行还会破坏多行字符串自身的缩进。
    因此统一在写出探针文件的那一刻把 @@TAB@@ / @@NL@@ 还原成真实字符。
    """
    return (body.replace("@@TAB@@", "\t")
                .replace("@@NL@@", "\n"))


def build_probe(tag, lang=None, extra_toml="", hugo=HUGO, pages=None, minify=False,
                theme_dir=None):
    """在 tmp 下搭一个最小站点（不写 exampleSite），返回 (out_dir, log, rc)。

    为什么要最小站点而不是直接用 exampleSite：
      * 提示块的断言需要**可控的正文**（精确含 5 种类型 + 未知类型 + 普通引用）；
      * 最小站点只有 1 个页面，diff 的对象唯一，字节比较不会被无关差异干扰；
      * 不往 exampleSite 写任何探针文件（§11 要求临时文件必须清理）。

    pages：额外页面 {文件名: 正文}，与 p1.md 一起写进三个内容目录（用于组件探针）。
    theme_dir：覆盖主题目录（用于"被改动过的主题副本"的对照实验）。
    """
    root = os.path.join(OUT_ROOT, f"_cc_{tag}")
    safe_rmtree(root)
    for d in ("content", "content-en", "content-zh-tw"):
        os.makedirs(os.path.join(root, d), exist_ok=True)
    with io.open(os.path.join(root, "hugo.toml"), "w", encoding="utf-8") as f:
        f.write(ZERO_TMPL + extra_toml)
    for d in ("content", "content-en", "content-zh-tw"):
        with io.open(os.path.join(root, d, "p1.md"), "w", encoding="utf-8") as f:
            f.write(PROBE_MD)
        for name, body in (pages or {}).items():
            with io.open(os.path.join(root, d, name), "w", encoding="utf-8") as f:
                f.write(probe_media(body))
    out = os.path.join(root, "public")
    # themesDir 直接用**真实的主题父目录**（与 exampleSite 的 `--themesDir ../..` 等价）。
    # 不要用符号链接/junction 造 themes/ 目录：Hugo 0.128.0 / 0.148.0 不解析符号链接，
    # 会报 `module "hugo-theme-nebula" not found`（0.162+ 才跟随）。真实路径在五个
    # 版本上行为一致，也更贴近 exampleSite 的实际用法。
    cmd = [hugo, "--source", root, "--themesDir", theme_dir or THEMES_DIR, "--gc",
           "-d", out, "--cleanDestinationDir"]
    if minify:
        cmd.append("--minify")
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                       errors="ignore", timeout=300)
    return out, (r.stdout or "") + (r.stderr or ""), r.returncode


def read(p):
    if not os.path.isfile(p):
        return None
    return io.open(p, encoding="utf-8").read()


def page(out, rel="p1/index.html"):
    return read(os.path.join(out, *rel.split("/")))


def alerts(html):
    """解析出 [(type, block_html)]，只匹配提示块。"""
    if not html:
        return []
    return re.findall(
        r'<blockquote class="md-alert md-alert-(\w+)">(.*?)</blockquote>', html, re.S)


def icons(html):
    """每种类型的 svg 内部路径（用于比对图标是否各不相同）。"""
    got = {}
    for t, body in alerts(html):
        m = re.search(r"<svg[^>]*>(.*?)</svg>", body, re.S)
        got.setdefault(t, []).append(m.group(1).strip() if m else "")
    return got


def title_of(body):
    m = re.search(r'class="md-alert-title">(.*?)</span>', body)
    return m.group(1).strip() if m else None


def css_text(out):
    d = os.path.join(out, "css")
    if not os.path.isdir(d):
        return ""
    for n in sorted(os.listdir(d)):
        if n.startswith("main") and n.endswith(".css"):
            return read(os.path.join(d, n)) or ""
    return ""


def css_norm(css):
    """归一化 CSS 空白，兼容 --minify（`.a > b` -> `.a>b`）。"""
    return css.replace(" > ", ">").replace("> ", ">").replace(" >", ">")


def tabs_containers(html):
    return re.findall(r'<div class="tabs" id="([^"]+)">(.*?)(?=<div class="tabs" id=|\Z)',
                      html, re.S)


def count(pat, s):
    return len(re.findall(pat, s))


# --------------------------------------------------------------------------- #
# A. 构建产物断言
# --------------------------------------------------------------------------- #
def run_checks():
    out, log, rc = build_probe("main", hugo=HUGO)
    if rc != 0:
        H.fatal_error("探针站点构建失败", log[-800:])
        return None
    html = page(out)
    if html is None:
        H.fatal_error("探针页面未生成", out)
        return None

    blocks = alerts(html)
    got_types = [t for t, _ in blocks]

    # ---------- A1 五种类型 ----------
    # warning 在探针里出现两次：一次默认标题、一次自定义标题，二者都要验证。
    expect = {"note": 1, "tip": 1, "important": 1, "warning": 2, "caution": 1}
    for t in KNOWN:
        n = got_types.count(t)
        H.record(f"A1 [!{t.upper()}] 生成提示块且数量正确", n == expect[t],
                 f"count={n} expected={expect[t]}")
    H.record("A1 提示块总数 = 6（5 种类型 + 1 个自定义标题）",
             len(blocks) == 6, f"total={len(blocks)} types={got_types}")
    H.record("A1 class 命名空间为 md-alert md-alert-<type>（语义标记）",
             all(re.search(rf'<blockquote class="md-alert md-alert-{t}">', html) for t in KNOWN),
             "")

    # ---------- A2 图标互不相同（防静默退化成同一个图标） ----------
    ic = icons(html)
    first = {t: (ic.get(t) or [""])[0] for t in KNOWN}
    uniq = set(first.values())
    H.record("A2 五种类型的图标**互不相同**（不是复制同一个图标）",
             len(uniq) == 5 and all(first[t] for t in KNOWN),
             f"unique={len(uniq)} sizes={{{', '.join(f'{k}:{len(v)}' for k, v in first.items())}}}")
    H.record("A2 图标是内联 SVG（无外部图标字体/CDN 请求）",
             html.count("<svg viewBox=\"0 0 24 24\"") >= 5, "")
    H.record("A2 图标标记 aria-hidden（装饰性，不干扰读屏）",
             all('aria-hidden="true"' in body for _, body in blocks), "")

    # ---------- A3 默认标题走 i18n（中文站） ----------
    # 取"每种类型里**没有**自定义标题（即 .AlertTitle 为空）"的那一个块
    zh = {}
    for t, b in blocks:
        if t in KNOWN and title_of(b) in ("说明", "提示", "重要", "警告", "注意",
                                          "Note", "Tip", "Important", "Warning", "Caution"):
            zh[t] = title_of(b)
    H.record("A3 中文站默认标题为中文（说明/提示/重要/警告/注意）",
             zh == {"note": "说明", "tip": "提示", "important": "重要",
                    "warning": "警告", "caution": "注意"}, f"{zh}")

    # ---------- A4 自定义标题优先 ----------
    custom = [b for t, b in blocks if t == "warning"]
    titles = [title_of(b) for b in custom]
    H.record("A4 自定义标题（[!WARNING] 自定义标题）覆盖 i18n 默认",
             "自定义标题" in titles, f"{titles}")
    H.record("A4 自定义标题不改变类型与图标（仍是 warning）",
             any(title_of(b) == "自定义标题" and first["warning"] in b for _, b in blocks), "")

    # ---------- A5 未知类型不生成提示块 ----------
    H.record("A5 未知类型 [!BOGUS] **不**生成提示块",
             "md-alert-bogus" not in html and "bogus" not in got_types, f"{got_types}")
    H.record("A5 未知类型仍按普通引用渲染（正文保留）",
             "未知类型正文" in html, "")
    H.record("A5 构建成功（未知类型不让构建失败）", rc == 0, f"rc={rc}")

    # ---------- A6 普通引用逐字节不变 ----------
    # 方法：同一主题，唯一差异 = 是否存在 render-blockquote.html。
    # 用 git archive 取 HEAD 版本做"无钩子"对照组，并同步工作区的 CSS/i18n
    # （CSS/i18n 与钩子无关，必须一致，否则 diff 会因配色差异而误报）。
    nohook, log_nh, rc_nh = build_nohook_copy()
    H.record("A6 对照组（无钩子）构建成功", rc_nh == 0, f"rc={rc_nh}")
    if nohook:
        h2 = page(nohook)
        # 只比较正文块之前与之后的内容：
        #   * 正文块**内**必然不同（提示块取代了普通引用），这是本功能的定义；
        #   * 但正文块**外**必须逐字节一致（含阅读统计之外的全部外壳）。
        # 注意：阅读统计的"字数"会变（Hugo 的 .WordCount 连同 `[!NOTE]` 标记一起计数），
        # 这属于**预期差异**，因此把统计区一并排除，避免把正确行为误判为回归。
        def outside(s_html):
            if not s_html:
                return ""
            m = re.search(r'<div class="post-content[^"]*"[^>]*>(.*?)</div>\s*</article>',
                          s_html, re.S)
            core = m.group(1) if m else s_html
            stripped = s_html.replace(core, "\x00CORE\x00")
            stripped = re.sub(r'<span class="stat">.*?</span>', "", stripped, flags=re.S)
            return stripped
        a, b = outside(h2), outside(html)
        same = bool(a) and a == b
        if not same:
            d = list(difflib.unified_diff(a.splitlines(), b.splitlines(),
                                          "nohook", "withhook", lineterm=""))
            H.record("A6 正文块之外的内容逐字节不变（空壳/元信息/导航/页脚 diff=0）",
                     False, ("diff: " + " | ".join(d[2:14]))[:600])
        else:
            H.record("A6 正文块之外的内容逐字节不变（空壳/元信息/导航/页脚 diff=0）", True, "")
        # 再单独证明：**真正的普通引用**（正文里没有任何 `[!X]` 标记）的 HTML 片段一致。
        # 排除两类：
        #   * `[!NOTE]` 等已知类型 -> 本就被替换成提示块；
        #   * `[!BOGUS]` 未知类型   -> Hugo 内建的 alert 解析器仍会**吞掉 marker 行**
        #     （实测 0.148~0.167 一致，与模板无关），因此片段文本必然不同，属预期。
        def quotes(h):
            return re.findall(r"<blockquote>\n(.*?)</blockquote>", h or "", re.S)

        with_plain = quotes(html)                                    # 全部非 alert 块
        nohook_plain = [x for x in quotes(h2) if "[!" not in x]      # 对照组里真·普通引用
        # 对照组里带 marker 的块（[!NOTE] 等）在 withhook 里已被提示块取代，不参与比较。
        missing = [x for x in nohook_plain if x not in with_plain]
        H.record("A6 对照组中的真·普通引用全部原样保留（逐字节一致）",
                 bool(nohook_plain) and not missing,
                 f"nohook={len(nohook_plain)} missing={len(missing)}")
        # withhook 相对对照组"多出来"的普通引用块，只应是 [!BOGUS] 的正文：
        # Hugo 内建的 alert 解析器会吞掉未知类型的 marker 行（实测 0.148~0.167 一致，
        # 与模板无关；无钩子时该 marker 会被当普通文本保留，故两边必然差这一处）。
        extra = [x for x in with_plain if x not in nohook_plain]
        H.record("A6 唯一多出的普通引用块是 [!BOGUS] 的正文（Hugo 内建解析吞 marker，非本模板行为）",
                 len(extra) == 1 and "未知类型正文" in extra[0],
                 f"extra={[e.strip()[:40] for e in extra]}")
    else:
        H.record("A6 对照组构建产物缺失", False, "")

    # ---------- A7 CSS ----------
    css = css_text(out)
    H.record("A7 存在 .md-alert 基础样式", ".md-alert" in css, "")
    H.record("A7 五种类型各有独立配色规则",
             all(f".md-alert-{t}" in css for t in KNOWN), "")
    H.record("A7 复用设计变量（--brand / --brand-soft），暗色无需第二套颜色",
             "var(--brand)" in css and "var(--brand-soft)" in css, "")
    H.record("A7 有暗色主题下的图标色修正（深底可读）",
             'html[data-theme="dark"] .md-alert-' in css
             or "html[data-theme=dark] .md-alert-" in css, "")
    H.record("A7 提示块内代码块不横向溢出", ".md-alert pre" in css, "")
    # --minify 会去掉选择器里的空格（`.md-alert-body > *:first-child` ->
    # `.md-alert-body>*:first-child`），必须归一后再断言，否则假红。
    css_norm = css.replace(" > ", ">").replace("> ", ">").replace(" >", ">")
    H.record("A7 提示块首尾子元素去掉多余外边距",
             ".md-alert-body>*:first-child" in css_norm
             and ".md-alert-body>*:last-child" in css_norm, "")
    H.record("A7 打印样式未破坏提示块（@media print 内不含 .md-alert 隐藏规则）",
             not re.search(r"@media print[^@]*\.md-alert\s*\{[^}]*display:\s*none", css, re.S),
             "")

    # ---------- A8 零 JS / 无第三方请求 ----------
    H.record("A8 提示块 HTML 内不含 script（纯 CSS 实现）",
             all("<script" not in b for _, b in blocks), "")
    # 排除页面自身的 canonical / og:url / 语言切换链接（它们是站内地址，不是外部请求）。
    # 只有 <script src> / <link href> / <img src> 这类会真正发起网络请求的才是"外部依赖"。
    ext = re.findall(r'<(?:script|link|img|iframe)[^>]*(?:src|href)="(https?://[^"]+)"', html)
    ext = [u for u in ext if not u.startswith("https://z.example/")]
    H.record("A8 页面不含任何第三方 http(s) 资源（无 CDN 依赖）", not ext, f"{ext[:3]}")

    return {"out": out, "html": html}


def build_nohook_copy():
    """构造"同一份主题、只少 render-blockquote.html"的对照组并构建。

    关键：对照组必须与工作区**逐字节一致**（含未提交的 scripts.html / main.js），
    否则指纹化的资源名前缀等与"钩子"无关的差异会制造 diff，
    把 A6 的"唯一差异 = 钩子"前提打破（实测：曾因此假红）。

    因此这里直接复制工作区主题（排除构建产物与缓存），只删掉那一个钩子文件。
    这比"git archive HEAD + 手工同步 CSS/i18n"更严格：无需列举要同步的文件，
    也就不会因为漏同步而假红。
    """
    d = os.path.join(OUT_ROOT, "_cc_nohook")
    safe_rmtree(d)

    # ⚠ 不要在复制后再 os.remove 掉钩子文件 —— 某些执行环境把单文件删除
    #   重定向到系统回收站（SHFileOperationW），在 tmp 目录下会失败并中断测试。
    #   改为在 copytree 阶段就**排除**该文件：既避开删除操作，语义也更明确
    #   （"对照组从来没有过这个钩子"，而不是"复制完再删掉"）。
    def _skip_blockquote_hook(dirpath, names):
        skip = set(shutil.ignore_patterns(
            "tmp", "public", "public-*", ".git", "myblog", "__pycache__",
            "resources")(dirpath, names))
        if os.path.basename(dirpath.replace("\\", "/")) == "_markup":
            skip |= {n for n in names if n == "render-blockquote.html"}
        return skip

    shutil.copytree(REPO, d, ignore=_skip_blockquote_hook)
    hook = os.path.join(d, "layouts/_default/_markup/render-blockquote.html")
    if os.path.exists(hook):          # 兜底：万一 copytree 的 ignore 未生效
        raise RuntimeError("对照组里仍存在 render-blockquote.html，A6 前提被破坏")

    # 用同样的探针站点构建（主题换成这个副本）
    root = os.path.join(OUT_ROOT, "_cc_nohook_site")
    safe_rmtree(root)
    for dd in ("content", "content-en", "content-zh-tw"):
        os.makedirs(os.path.join(root, dd), exist_ok=True)
    with io.open(os.path.join(root, "hugo.toml"), "w", encoding="utf-8") as f:
        f.write(ZERO_TMPL)
    for dd in ("content", "content-en", "content-zh-tw"):
        with io.open(os.path.join(root, dd, "p1.md"), "w", encoding="utf-8") as f:
            f.write(PROBE_MD)
    # 把"无钩子"副本放到一个**真实**的 themesDir 下，目录名必须叫 hugo-theme-nebula。
    # 同样不用 symlink（0.128/0.148 不解析）。
    holder = os.path.join(OUT_ROOT, "_cc_nohook_themes")
    safe_rmtree(holder)
    os.makedirs(holder, exist_ok=True)
    themedir = os.path.join(holder, "hugo-theme-nebula")
    shutil.move(d, themedir)
    out = os.path.join(root, "public")
    r2 = subprocess.run([HUGO, "--source", root, "--themesDir", holder, "--gc", "-d", out,
                         "--cleanDestinationDir"], capture_output=True, text=True,
                        encoding="utf-8", errors="ignore", timeout=300)
    return out, (r2.stdout or "") + (r2.stderr or ""), r2.returncode


# --------------------------------------------------------------------------- #
# B. 多语言 / 版本矩阵
# --------------------------------------------------------------------------- #
def run_lang_checks(main):
    """三种站点语言的默认标题必须来自 i18n（第六节：支持三语言）。

    用一个真实多语言站点构建（zh-cn 在根、en 在 /en/、zh-TW 在 /zh-tw/），
    逐个语言断言 .md-alert-title 的文案，证明标题**真的**跟随内容语言，
    而不是硬编码或回退到英文。
    """
    out = main["out"]
    EXPECT = {
        "":      ("zh-cn", ("说明", "提示", "重要", "警告", "注意")),
        "en":    ("en",    ("Note", "Tip", "Important", "Warning", "Caution")),
        "zh-tw": ("zh-TW", ("說明", "提示", "重要", "警告", "注意")),
    }
    ORDER = ["note", "tip", "important", "warning", "caution"]
    for sub, (lang, defaults) in EXPECT.items():
        rel = "p1/index.html" if not sub else f"{sub}/p1/index.html"
        html = page(out, rel)
        if not html:
            H.record(f"B1 语言 {lang}：页面存在", False, rel)
            continue
        got = {}
        for k, b in alerts(html):
            if k in KNOWN and title_of(b) in defaults:
                got[k] = title_of(b)
        want = dict(zip(ORDER, defaults))
        H.record(f"B1 语言 {lang}：五种默认标题正确来自 i18n", got == want,
                 f"got={got}")
        H.record(f"B1 语言 {lang}：自定义标题原样保留（不被 i18n 覆盖）",
                 "自定义标题" in html, "")


def run_hugo_matrix():
    """五种 Hugo 版本的提示块行为（0.128.0 必须优雅退化）。"""
    ver_dirs = hugo_matrix()
    if not ver_dirs:
        H.fatal_error("未找到 Hugo 版本矩阵目录", HUGO_ROOT)
        return

    for v, exe in sorted(ver_dirs.items()):
        out, log, rc = build_probe(f"v{v}", hugo=exe)
        if rc != 0:
            H.record(f"B2/B3 Hugo {v} 构建成功", False, log[-300:])
            continue
        html = page(out) or ""
        n = len(alerts(html))
        if v == "0.128.0":
            H.record("B2 Hugo 0.128.0 构建成功（钩子被静默忽略，不报错）", rc == 0, "")
            H.record("B2 Hugo 0.128.0 不生成提示块（优雅退化）", n == 0, f"alerts={n}")
            H.record("B2 Hugo 0.128.0 marker 行仍可见（退化为普通引用，内容不丢）",
                     "[!NOTE]" in html and "说明正文" in html, "")
            H.record("B2 Hugo 0.128.0 普通引用输出正常",
                     html.count("<blockquote>") >= 3, f"count={html.count('<blockquote>')}")
        else:
            H.record(f"B3 Hugo {v} 生成 6 个提示块", n == 6, f"alerts={n}")
            t = {k: title_of(b) for k, b in alerts(html) if k in KNOWN}
            H.record(f"B3 Hugo {v} 中文默认标题正确",
                     t.get("note") == "说明" and t.get("caution") == "注意", f"{t}")
            H.record(f"B3 Hugo {v} 未知类型未生成提示块", "md-alert-bogus" not in html, "")
            ic = icons(html)
            H.record(f"B3 Hugo {v} 五种图标互不相同",
                     len({(ic.get(k) or [''])[0] for k in KNOWN}) == 5, "")



# --------------------------------------------------------------------------- #
# C. 跨版本回归：多语言站点的 alias 空值防御
# --------------------------------------------------------------------------- #
def run_alias_defense():
    """回归：多语言站点的默认语言 alias 页在 `.Page` 为 nil 时**不得中断构建**。

    这是在本功能的版本矩阵验证中**发现的主题既有缺陷**（与提示块无关）：
    Hugo 会为默认语言额外生成一个 `/<defaultContentLanguage>/` 重定向页，
    该页**不附带目标 Page 对象**。`layouts/alias.html` 原来的
    `{{ .Page.Title | default .Permalink }}` 会以

        execute of template failed: alias.html: at <.Page.Title>:
        nil pointer evaluating page.Page.Title

    中断**整个构建**。实测 0.128.0 / 0.148.0 / 0.162.0 崩溃，
    0.166.0 / 0.167.0 不复现（Hugo 后来改成跳过这类 alias）。
    主题最低版本是 0.128.0，因此必须自行防御。

    反证：把 alias.html 的防御改回 `.Page.Title`，本小节的断言必须变红——
    已实测确认（见交付报告）。
    """
    ver_dirs = hugo_matrix()
    if not ver_dirs:
        H.fatal_error("未找到 Hugo 版本矩阵目录（alias 回归）", HUGO_ROOT)
        return

    for v, exe in sorted(ver_dirs.items()):
        out, log, rc = build_probe(f"alias_v{v}", hugo=exe)
        ok = rc == 0
        H.record(f"C Hugo {v}：多语言站点构建成功（alias 空值不再中断构建）",
                 ok, "" if ok else log[-260:])
        if not ok:
            continue
        alias = read(os.path.join(out, "zh-cn", "index.html"))
        H.record(f"C Hugo {v}：默认语言 alias 页存在", alias is not None, "")
        if alias is None:
            continue
        title = re.search(r"<title>(.*?)</title>", alias, re.S)
        H.record(f"C Hugo {v}：alias 页 title 非空（无 nil 崩溃痕迹）",
                 bool(title and title.group(1).strip()), repr(title.group(1) if title else None))
        # alias 页的既有约定必须保持：canonical + meta refresh + 无脚本
        H.record(f"C Hugo {v}：alias 页仍有 canonical",
                 'rel="canonical"' in alias, "")
        H.record(f"C Hugo {v}：alias 页仍有 meta refresh 且目标非空",
                 bool(re.search(r'http-equiv="refresh"\s+content="([^"]*url=([^"]+))"', alias))
                 or bool(re.search(r'content="0;\s*url=([^"]+)"', alias)), "")
        H.record(f"C Hugo {v}：alias 页仍不含任何 script",
                 "<script" not in alias, "")


# --------------------------------------------------------------------------- #
# C. 功能三（第二、三项）：标签页 tabs/tab + 步骤 steps/step
#
# ⚠ 这些探针用 --minify 构建（与 CI 生产构建一致）。Hugo 的 minifier 会**去掉
#   属性值两端的引号**（`class="tabs"` -> `class=tabs`）并压缩 CSS 空白
#   （`.a > b` -> `.a>b`）。因此断言一律写成"引号可选 + 空白归一"的形态，
#   否则会在生产产物上假红（本轮实测踩过）。
# --------------------------------------------------------------------------- #
NESTED_BLOCKTOKEN = "NEBULABLOCKTOKEN"


def run_component_checks():
    """构建含 tabs/steps 的探针站点，断言**真实产物**的结构与行为。"""
    out, log, rc = build_probe(
        "comp", pages={"p2.md": PROBE_COMPONENTS_MD}, minify=True)
    if rc != 0:
        H.fatal_error("组件探针站点构建失败", log[-800:])
        return None
    html = page(out, "p2/index.html")
    if html is None:
        H.fatal_error("组件探针页面未生成", out)
        return None
    css = css_norm(css_text(out))

    # ---------- C1 服务端渲染的结构与计数 ----------
    containers = re.findall(r'<div class="?tabs"? id="?(tabs-\d+)"?', html)
    H.record("C1 两个 tabs 容器，id 页内唯一（tabs-1/tabs-2）",
             containers == ["tabs-1", "tabs-2"], f"{containers}")
    n_tab = count(r'class="?tabs-tab"?[\s>]', html)
    n_panel = count(r'role="?tabpanel"?', html)
    H.record("C1 tab 按钮 = 4（每个容器 2 个）", n_tab == 4, f"{n_tab}")
    H.record("C1 tabpanel = 4", n_panel == 4, f"{n_panel}")
    H.record("C1 每个容器恰好 1 个 aria-selected=true（首个）",
             count(r'aria-selected="?true"?', html) == 2
             and count(r'aria-selected="?false"?', html) == 2, "")
    H.record("C1 tablist 数量 = 2 且都带 aria-label（i18n 文案）",
             count(r'role="?tablist"?', html) == 2
             and count(r'role="?tablist"?[^>]*aria-label=', html) == 2, "")

    # ---------- C2 服务端就写好 hidden（无 JS 才不会重叠） ----------
    hiddens = count(r'<div class="?tabs-panel"?[\s>][^>]*\bhidden\b', html)
    H.record("C2 服务端写死 hidden：每个容器只留首面板可见（合计 2 个 hidden）",
             hiddens == 2, f"hidden={hiddens}")

    # ---------- C3 步骤：ol 语义 + CSS counter 序号 ----------
    H.record("C3 steps 渲染为 <ol class=\"steps\">（有序列表语义 + aria-label）",
             count(r'<ol class="?steps"?[\s>][^>]*aria-label=', html) == 2, "")
    H.record("C3 li.step = 5（3 + 2）", count(r'<li class="?step"?[\s>]', html) == 5, "")
    H.record("C3 step-title = 2（仅带标题的步骤输出；无标题的不输出空标题）",
             count(r'class="?step-title"?[\s>]', html) == 2, "")
    H.record("C3 无标题步骤不输出空 step-title（内容仍在）",
             "NOHEAD-TEXT" in html
             and count(r'class="?step-title"?[^>]*></p>', html) == 0, "")

    # ---------- C4 交叉嵌套：内容必须完整（回归：markdownify 丢弃原始 HTML） ----------
    # 这是第六节踩过的坑：unsafe=false 下父级 markdownify 会把子组件的原始 HTML
    # 整段丢掉。修复是 token 占位符机制，因此这里必须断言
    #   (a) 嵌套内容（NESTED-VERIFY / MANUAL-TEXT）真的在产物里；
    #   (b) **没有** token 残留；
    #   (c) **没有** `<!-- raw HTML omitted -->`；
    #   (d) 嵌套的 steps 的 <ol> 落在对应 tabpanel 内（而不是被提到容器外）。
    H.record("C4 标签页内嵌步骤：步骤正文保留（NESTED-VERIFY）",
             "NESTED-VERIFY" in html, "")
    H.record("C4 标签页内嵌步骤：嵌套 <ol class=\"steps\"> 落在 tabpanel 内部",
             bool(re.search(r'role="?tabpanel"?[^>]*>.*?<ol class="?steps"?', html, re.S)), "")
    H.record("C4 嵌套未留下占位符 token 残留", NESTED_BLOCKTOKEN not in html, "")
    H.record("C4 嵌套未触发 raw HTML omitted", "raw HTML omitted" not in html, "")

    # ---------- C5 面板/步骤内代码块复用统一管线（语言标签 + 复制按钮） ----------
    H.record("C5 面板内代码块带语言标签（bash/powershell 来自 highlight）",
             bool(re.search(r'language-(bash|powershell)', html)), "")
    H.record("C5 面板/步骤内代码块带一键复制按钮（复用 render-codeblock hook）",
             count(r'class="?code-copy"?[\s>]', html) == 4, f"{count(r'code-copy', html)}")

    # ---------- C6 零 JS 内容不丢（纯 CSS 覆盖 UA 的 [hidden]） ----------
    H.record("C6 默认态 .tabs-panel[hidden]{display:block}（覆盖 UA，无 JS 全部可见）",
             ".tabs-panel[hidden]{display:block}" in css, "")
    H.record("C6 默认态导航条隐藏 .tabs-nav{display:none}",
             ".tabs-nav{display:none}" in css, "")
    H.record("C6 增强态才收成标签页 .tabs-enhanced .tabs-panel[hidden]{display:none}",
             ".tabs-enhanced .tabs-panel[hidden]{display:none}" in css, "")
    H.record("C6 增强态由脚本自加 .tabs-enhanced（而非依赖 has-js）",
             bool(re.search(r'\.tabs-enhanced \.tabs-nav\{display:flex', css)), "")
    H.record("C6 序号由 CSS counter 生成（零 JS）",
             "counter-reset:nebula-step" in css and "counter(nebula-step)" in css, "")
    H.record("C6 序号圆点用 --brand-solid + 白字（对比度约定）",
             bool(re.search(r'background:var\(--brand-solid\);color:#fff', css)), "")

    # ---------- C7 无障碍 / 打印 / 动效偏好 ----------
    H.record("C7 标签按钮是原生 <button type=\"button\">（键盘/读屏可用）",
             count(r'<button type="?button"? class="?tabs-tab"?', html) == 4, "")
    H.record("C7 tabpanel 与 tab 通过 aria-controls/labelledby 关联",
             count(r'aria-controls="?tabs-', html) == 4
             and count(r'aria-labelledby="?tabs-', html) == 4, "")
    H.record("C7 面板内容区 <=0 溢出保护（min-width:0）", ".step-body{min-width:0}" in css, "")
    H.record("C7 打印时全部面板展开（.tabs-panel[hidden]{display:block !important}）",
             bool(re.search(r"@media print.*?\.tabs-panel\[hidden\]\{display:block\s*!important",
                            css, re.S)), "")
    H.record("C7 打印时导航条隐藏（display:none !important）",
             bool(re.search(r"@media print.*?\.tabs-nav\{display:none\s*!important", css, re.S)), "")
    H.record("C7 尊重 prefers-reduced-motion（去掉切换过渡）",
             bool(re.search(r"@media\s*\(prefers-reduced-motion:\s*reduce\)\s*\{"
                            r".*?\.tabs-enhanced \.tabs-tab\{transition:none", css, re.S)), "")

    # ---------- C8 按需加载：tabs.js 只在用了 tabs 的页面注入 ----------
    tabjs = re.findall(r'<script src="?([^" >]*js/tabs[.\-][^" >]*)"?', html)
    H.record("C8 用过 tabs 的页面注入 tabs.js", bool(tabjs), f"{tabjs[:1]}")
    H.record("C8 tabs.js 带 fingerprint 完整性属性",
             bool(re.search(r'<script src="?[^" >]*js/tabs[.\-][^" >]*"?[^>]*integrity="?sha',
                            html)), "")
    # 反面对照：没用 tabs 的页面**不得**出现 tabs.js（证明"按需"是真的，
    # 而不是"每页都塞一份"）。p1 只有提示块，没有 tabs。
    p1 = page(out, "p1/index.html") or ""
    H.record("C8 未使用 tabs 的页面不注入 tabs.js（按需加载真实生效）",
             bool(p1) and not re.search(r'js/tabs[.\-]', p1), "")
    H.record("C8 未使用 tabs 的页面也不输出标签页样式依赖的脚本标记",
             "nebula_has_tabs" not in p1, "")

    # ---------- C9 无第三方请求（延续 A8 的零外部依赖约束） ----------
    ext = re.findall(r'<(?:script|link|img|iframe)[^>]*(?:src|href)="?(https?://[^" >]+)"?', html)
    ext = [u for u in ext if not u.startswith("https://z.example/")]
    H.record("C9 组件页不含第三方 http(s) 资源", not ext, f"{ext[:3]}")

    return {"out": out, "html": html, "css": css}


def run_component_matrix():
    """五版本上 tabs/steps 的结构与内容一致性（含 0.128.0 无降级）。"""
    ver_dirs = hugo_matrix()
    if not ver_dirs:
        H.fatal_error("未找到 Hugo 版本矩阵目录（组件）", HUGO_ROOT)
        return
    sigs = {}
    for v, exe in sorted(ver_dirs.items()):
        out, log, rc = build_probe(f"comp_v{v}", pages={"p2.md": PROBE_COMPONENTS_MD},
                                   hugo=exe, minify=True)
        if rc != 0:
            H.record(f"C10 Hugo {v} 组件页构建成功", False, log[-300:])
            continue
        html = page(out, "p2/index.html") or ""
        sig = (count(r'<div class="?tabs"? id="?tabs-', html),
               count(r'class="?tabs-tab"?[\s>]', html),
               count(r'role="?tabpanel"?', html),
               count(r'<ol class="?steps"?[\s>]', html),
               count(r'<li class="?step"?[\s>]', html))
        sigs[v] = sig
        H.record(f"C10 Hugo {v} 结构计数正确（2/4/4/2/5）", sig == (2, 4, 4, 2, 5), f"{sig}")
        H.record(f"C10 Hugo {v} 嵌套内容完整（NESTED-VERIFY / MANUAL-TEXT）",
                 "NESTED-VERIFY" in html and "MANUAL-TEXT" in html, "")
        H.record(f"C10 Hugo {v} 无 token 残留 / 无 raw HTML omitted",
                 NESTED_BLOCKTOKEN not in html and "raw HTML omitted" not in html, "")
        H.record(f"C10 Hugo {v} tabs.js 按需注入",
                 bool(re.search(r'js/tabs[.\-]', html)), "")
    H.record("C10 五个 Hugo 版本产物结构签名完全一致",
             len(sigs) >= 2 and len(set(sigs.values())) == 1, f"{sigs}")


def run_media_checks():
    """D 段：文件树 / 徽标 / 按钮 scheme 校验 / 折叠块。

    全部断言都指向**真实产物**：要么证明危险输入被安全处理，要么证明特殊字符
    没有破坏 HTML 结构。`--minify` 会去掉属性引号，故正则一律"引号可选"。
    """
    out, log, rc = build_probe(
        "media", pages={"p3.md": PROBE_MEDIA_MD}, minify=True)
    if rc != 0:
        H.fatal_error("媒体组件探针站点构建失败", log[-800:])
        return None
    html = page(out, "p3/index.html")
    if html is None:
        H.fatal_error("媒体组件探针页面未生成", out)
        return None
    css = css_norm(css_text(out))

    # ---------- D1 文件树：结构与"不解析 Markdown" ----------
    H.record("D1 文件树 render 为 <figure class=filetree> ×2",
             count(r'<figure class="?filetree"?', html) == 2,
             f"{count(r'filetree', html)}")
    H.record("D1 有标题的用 <figcaption>（位置参数）",
             "示例项目结构" in html and count(r'<figcaption class="?filetree-title"?', html) == 2, "")
    H.record("D1 属性式 title 也生效（属性标题）", "属性标题" in html, "")
    H.record("D1 树形缩进与 box-drawing 字符原样保留（在 <pre> 内）",
             bool(re.search(r'<pre class="?filetree-body"?>\s*my-app/', html))
             and "├──" in html and "└──" in html, "")
    # 关键：文件名里的 Markdown 敏感字符必须**不被解析**（逐字保留）
    H.record("D1 文件名里的反引号未被 Markdown 解析（逐字保留，无 <code> 包裹）",
             "`s`.ts" in html and '<code>`s`' not in html, "")
    # 关键：文件名里的引号被转义成实体（证明真的走了转义，而不是原样输出）
    H.record("D1 文件名里的双/单引号被转义为实体（不破坏属性与文本）",
             "&#34;q&#34;" in html and "&#39;r&#39;" in html, "")
    # 关键：文件名里的 <x> 必须被转义，不得变成真实标签
    H.record("D1 文件名里的 <x> 被转义为实体（未变成标签）",
             "&lt;x&gt;" in html and "<x>" not in html, "")
    H.record("D1 文件名里的 & 被转义（未变成实体起始符）",
             "a&amp;b.ts" in html, "")
    # 零 JS：只在 filetree 的 <figure> 内部检查（不能跨块匹配到别处的 script）
    fig = re.search(r'<figure class="?filetree"?.*?</figure>', html, re.S)
    H.record("D1 文件树内部不含任何 script（零 JS）",
             bool(fig) and "<script" not in fig.group(0), "")

    # ---------- D2 徽标 ----------
    H.record("D2 徽标 render 为 <span class=badge> ×5",
             count(r'<span class="?badge badge-', html) == 5,
             f"{count(r'badge-', html)}")
    H.record("D2 默认变体（无第二参数）", count(r'badge badge-default', html) >= 1, "")
    H.record("D2 具名参数 text= / type= 生效（danger）", "badge-danger" in html, "")
    H.record("D2 未知变体静默回退 default（不报错、不产生 bogus 类）",
             count(r'badge badge-default', html) == 3 and "badge-bogus" not in html,
             f"default={count(r'badge badge-default', html)}")
    # 安全：变体值里的 class 逃逸尝试必须被消灭
    H.record("D2 变体值里的 class 逃逸尝试被消灭（无 onmouseover / 无额外类）",
             "onmouseover" not in html and 'x" ' not in html, "")
    H.record("D2 徽标全部是 <span>（行内语义，不用 div/button 污染结构）",
             count(r'<span class="?badge badge-', html) == 5, "")

    # ---------- D3 按钮 URL scheme 校验（第六节明确要求） ----------
    # 探针里前 4 个是安全链接：外链 / mailto / 站内相对 / tel。
    a_btns = re.findall(r'<a class="?btn"?([^>]*)>', html)
    sp_btns = re.findall(r'<span class="?btn btn-disabled"?', html)
    H.record("D3 放行 4 个安全链接（外链 / mailto / 站内相对 / tel）",
             len(a_btns) == 4, f"a.btn={len(a_btns)}")
    H.record("D3 拦截不安全链接（javascript: / TAB 空白绕过 / vbscript: / "
             "data:text/html / file:）与 1 个空值 → 输出 span.btn-disabled",
             len(sp_btns) == 6, f"span.btn-disabled={len(sp_btns)}")
    # 最关键的断言：危险 scheme 不得出现在任何 href 里
    bad = re.findall(r'href="?(?:javascript|vbscript|data:text/html|file):?', html, re.I)
    H.record("D3 产物里不出现任何危险 scheme 的 href", not bad, f"{bad[:3]}")
    # 空白绕过：`java<TAB>script:` 是浏览器会执行的形态，必须在**模板层**就被识破
    # （判定前先剥掉所有空白与控制字符再比对）。真正的裸换行在短代码入口无法构造，
    # 由 run_newline_arg_check() 单独断言构建失败。
    H.record("D3 制表符绕过（java\\t script:）被拦截，未进入 href",
             "java" not in html or not re.search(r"java[\s\u0000-\u0020]*script\s*:", html, re.I),
             "")
    H.record("D3 被拦截的按钮不含 href（不留 href=\"\" 空链接）",
             not re.search(r'<span class="?btn btn-disabled"?[^>]*href=', html), "")
    H.record("D3 被拦截按钮带 aria-disabled（语义上明确不可用）",
             count(r'btn-disabled"?[^>]*aria-disabled="?true', html) == 6, "")
    H.record("D3 被拦截按钮带 title 提示（i18n components.linkBlocked 生效，非空属性）",
             bool(re.search(r'btn-disabled"?[^>]*title="?[^" >]+', html)), "")
    # 外链 rel 约定（只在 <a class="btn"> 的标签内部检查，不跨块）
    H.record("D3 仅外链加 target=_blank + rel=noopener",
             len([t for t in a_btns if "target" in t]) == 1
             and bool(re.search(r'class="?btn"?[^>]*target="?_blank"?[^>]*rel="?noopener', html)), "")
    H.record("D3 mailto:/tel: 不加 target（交给系统处理）",
             bool(re.search(r'href="?mailto:hi@example\.com"?>', html))
             and bool(re.search(r'href="?tel:\+8610000000000"?>', html))
             and not [t for t in a_btns if ("mailto:" in t or "tel:" in t) and "target" in t], "")
    H.record("D3 站内相对路径被规范化为根相对（rel-url 生效）",
             bool(re.search(r'href="?/posts/other/?', html)), "")
    H.record("D3 外链 URL 的查询串完整保留（& 转义为实体且不丢失）",
             "https://example.com/a?x=1&amp;y=2" in html, "")

    # ---------- D4 折叠块 ----------
    fig_d = re.search(r'<details class="?nb-details"?.*?</details>', html, re.S)
    H.record("D4 折叠块 render 为原生 <details class=nb-details> ×2",
             count(r'<details class="?nb-details"?', html) == 2, "")
    H.record("D4 默认闭合：只有 1 个 details 带 open",
             count(r'<details class="?nb-details"? open', html) == 1, "")
    H.record("D4 open=\"true\" 时展开（DETAILS-OPEN-TEXT 在内）",
             "DETAILS-OPEN-TEXT" in html, "")
    H.record("D4 标题走 <summary>，内容完整（DETAILS-CLOSED-TEXT 未丢，"
             "回归：裸 <details> 被 goldmark 丢弃）",
             "DETAILS-CLOSED-TEXT" in html and count(r'<summary', html) == 2, "")
    H.record("D4 折叠块内部零 JS（原生元素，无 script / 无 aria 补丁）",
             bool(fig_d) and "<script" not in fig_d.group(0), "")

    # ---------- D5 CSS：三组样式齐全且复用设计变量 ----------
    H.record("D5 .filetree 基础样式存在且等宽保留空白",
             ".filetree{" in css and "white-space:pre" in css, "")
    H.record("D5 .badge 六个变体样式齐全",
             all(f".badge-{x}" in css for x in
                 ("default", "info", "success", "warning", "danger", "muted")), "")
    H.record("D5 .badge-default 用 --brand-solid 承载白字（AA 约定）",
             bool(re.search(r'\.badge-default\{background:var\(--brand-solid\);color:#fff', css)), "")
    H.record("D5 其余徽标变体用 *-ink 文字（不用鲜亮 --brand 当文字）",
             "color:var(--brand-ink)" in css and "color:var(--accent-ink)" in css, "")
    H.record("D5 有暗色主题下的徽标配色",
             bool(re.search(r'html\[data-theme="?dark"?\] \.badge-', css)), "")
    H.record("D5 .btn-disabled 有独立样式（不再继承可点击外观）",
             ".btn-disabled{" in css and "cursor:not-allowed" in css, "")
    H.record("D5 .nb-details 有自定义展开标记（+/−）且隐藏原生三角",
             ".nb-details-summary::before" in css
             and "-webkit-details-marker" in css, "")
    H.record("D5 打印时折叠块强制展开正文（否则内容漏印）",
             bool(re.search(r"@media print.*?\.nb-details-body\{display:block\s*!important",
                            css, re.S)), "")

    # ---------- D6 零第三方请求 ----------
    ext = re.findall(r'<(?:script|link|img|iframe)[^>]*(?:src|href)="?(https?://[^" >]+)"?', html)
    ext = [u for u in ext if not u.startswith("https://z.example/")]
    H.record("D6 媒体组件页不含第三方 http(s) 资源", not ext, f"{ext[:3]}")

    return {"out": out, "html": html}


def run_media_matrix():
    """D7：五版本上 filetree/badge/button/details 的行为一致性。"""
    ver_dirs = hugo_matrix()
    if not ver_dirs:
        H.fatal_error("未找到 Hugo 版本矩阵目录（媒体组件）", HUGO_ROOT)
        return
    sigs = {}
    for v, exe in sorted(ver_dirs.items()):
        out, log, rc = build_probe(f"media_v{v}", pages={"p3.md": PROBE_MEDIA_MD},
                                   hugo=exe, minify=True)
        if rc != 0:
            H.record(f"D7 Hugo {v} 媒体组件页构建成功", False, log[-300:])
            continue
        html = page(out, "p3/index.html") or ""
        sig = (count(r'<figure class="?filetree"?', html),
               count(r'<span class="?badge badge-', html),
               len(re.findall(r'<a class="?btn"?', html)),
               count(r'<span class="?btn btn-disabled"?', html),
               count(r'<details class="?nb-details"?', html))
        sigs[v] = sig
        H.record(f"D7 Hugo {v} 结构计数正确（2/5/4/6/2）", sig == (2, 5, 4, 6, 2), f"{sig}")
        H.record(f"D7 Hugo {v} 危险 scheme 未泄漏到 href",
                 not re.search(r'href="?(?:javascript|vbscript|data:text/html|file):?', html, re.I), "")
        H.record(f"D7 Hugo {v} 空白绕过（java<TAB>script:）被拦截",
                 not re.search(r"java[\s\u0000-\u0020]*script\s*:", html, re.I), "")
        H.record(f"D7 Hugo {v} 折叠块内容完整（裸 <details> 被丢弃的回归）",
                 "DETAILS-CLOSED-TEXT" in html, "")
    H.record("D7 五个 Hugo 版本产物结构签名完全一致",
             len(sigs) >= 2 and len(set(sigs.values())) == 1, f"{sigs}")


def run_media_regression():
    """D8 反证：去掉 scheme 校验后，危险 scheme 必须真的泄漏 —— 证明 D3 有区分力。

    注意坏副本必须**保留 safeURL**：真实模板正是用 `safeURL` 放行白名单与相对路径的，
    而 `safeURL` 会**绕过 Go html/template 自带的 urlFilter**。因此"只要不写 scheme
    校验，危险 scheme 就会原样进入 href"——这正是校验存在的原因。若坏副本不写
    safeURL，Go 的 urlFilter 会把危险 scheme 替换成 `#ZgotmplZ`，反证就测不出差异。
    """
    holder = os.path.join(OUT_ROOT, "_cc_media_broken_themes")
    safe_rmtree(holder)
    os.makedirs(holder, exist_ok=True)
    dst = os.path.join(holder, "hugo-theme-nebula")
    shutil.copytree(REPO, dst, ignore=shutil.ignore_patterns(
        "tmp", "public", "public-*", ".git", "myblog", "__pycache__", "resources"))
    # 修复前行为：URL 直出 safeURL，不做任何 scheme 判定
    with io.open(os.path.join(dst, "layouts", "shortcodes", "button.html"),
                 "w", encoding="utf-8") as f:
        f.write('<a class="btn" href="{{ .Get 1 | safeURL }}"'
                '{{ if hasPrefix (.Get 1) "http" }} target="_blank" rel="noopener"{{ end }}>'
                '{{ .Get 0 }}</a>\n')
    out, log, rc = build_probe("media_broken", pages={"p3.md": PROBE_MEDIA_MD},
                               theme_dir=holder)
    if rc != 0:
        H.record("D8 反证：坏副本也能构建（差异只在是否被拦截）", False, log[-300:])
        return
    html = page(out, "p3/index.html") or ""
    leaked = re.search(r'href="?(?:javascript|vbscript|data:text/html|file):?', html, re.I)
    H.record("D8 反证：去掉 scheme 校验后危险 scheme 泄漏（证明 D3 有区分力）",
             bool(leaked), f"泄漏={leaked.group(0)[:60] if leaked else None}")
    H.record("D8 反证：坏副本不再输出 span.btn-disabled（拦截确实来自校验）",
             count(r'btn-disabled', html) == 0, f"{count(r'btn-disabled', html)}")


def run_mixed_args_check():
    """D9 回归：Hugo **不允许**混用位置参数与具名参数（跨全版本一致）。

    这条不是主题的选择，而是 Hugo shortcode 的硬性规则：

        {{< details "标题" open="true" >}}    ->  ERROR:
            got named parameter 'open'. Cannot mix named and positional parameters
        {{< details title="标题" open="true" >}}  -> OK

    为什么要专门测它：本轮写文档与探针时都踩过 —— 因为旧版 Hugo 在某些写法下
    **不报错**，很容易让人以为"位置参数 + 具名参数"是可用的，于是文档给出一个
    会让用户构建失败的示例。把它固化成断言，就再也不会写出这样的示例。

    这里同时验证**后果**：混用时是"构建失败"，而不是"静默忽略其中一个参数"——
    后者才是真正危险的（内容会悄悄丢标题）。
    """
    mixed = """---
title: "CC Mixed"
date: 2024-05-09
draft: false
---

{{< details "位置标题" open="true" >}}
混合参数正文 MIXED-ARGS-TEXT
{{< /details >}}
"""
    out, log, rc = build_probe("mixed", pages={"p4.md": mixed})
    H.record("D9 混用位置参数与具名参数时构建**失败**（Hugo 硬性规则）",
             rc != 0, f"rc={rc}（若为 0 说明该版本静默容忍，文档示例会误导用户）")
    H.record("D9 失败原因是明确的 'Cannot mix named and positional parameters'",
             "Cannot mix named and positional parameters" in log,
             log[-200:] if "Cannot mix" not in log else "")
    H.record("D9 未把混合参数的页面悄悄产出（不是静默忽略参数）",
             page(out, "p4/index.html") is None, "")
    safe_rmtree(out)

    # 对照组：全具名写法必须成功 —— 证明"失败"来自混用，而不是组件本身有问题
    ok_cfg = mixed.replace('{{< details "位置标题" open="true" >}}',
                           '{{< details title="具名标题" open="true" >}}')
    out2, log2, rc2 = build_probe("named", pages={"p4.md": ok_cfg})
    H.record("D9 对照组：全具名写法构建成功（归因正确）", rc2 == 0,
             "" if rc2 == 0 else log2[-260:])
    if rc2 == 0:
        h = page(out2, "p4/index.html") or ""
        H.record("D9 对照组的 title 与 open 都生效",
                 "具名标题" in h and re.search(r'<details class="?nb-details"? open', h) is not None, "")
        H.record("D9 对照组正文完整（MIXED-ARGS-TEXT）", "MIXED-ARGS-TEXT" in h, "")
    safe_rmtree(out2)


def run_newline_arg_check():
    """D9b 结构性事实：Hugo 词法层拒绝"引号参数内裸换行"，故换行绕过无法构造。

    `java<NL>script:alert(1)` 曾是按钮 scheme 校验里的一个用例，但实测发现：
    把裸换行塞进短代码的引号参数，Hugo **词法分析器**直接报

        unterminated quoted string in shortcode parameter-argument: 'java

    也就是说，从本主题的 shortcode 入口**根本无法把带换行的 URL 送进来**；能
    送进来的空白绕过只有制表符（已由 D3 覆盖）。这里把它固化为断言，是为了避免
    未来有人"想当然"地再加一个无法构造的换行用例，导致探针站点整站构建失败
    （本脚本曾经的 8 项失败就是这么来的）。
    """
    md = ('---\ntitle: "CC NL"\ndate: 2024-05-10\ndraft: false\n---\n\n'
          '{{< button "NL" "java\nscript:alert(1)" >}}\n')
    out, log, rc = build_probe("nl", pages={"p5.md": md})
    H.record("D9b 带裸换行的引号参数导致构建失败（词法层拒绝，绕过不可构造）",
             rc != 0, f"rc={rc}")
    H.record("D9b 失败原因是 'unterminated quoted string'",
             "unterminated quoted string" in log, log[-200:] if "unterminated" not in log else "")
    H.record("D9b 未产出该页面（不是静默容忍）", page(out, "p5/index.html") is None, "")
    safe_rmtree(out)


def run_nested_regression():
    """反证：去掉 token 占位符机制后，嵌套内容必须**真的**丢失 —— 证明 C4 有区分力。

    做法：把主题复制一份，把 util/nested-block.html 改成"直接返回内联 HTML"
    （即修复前的行为），其余一字不改。若 C4 的断言在坏副本上变红，
    说明它们测得的是真实行为，而不是"脚本恰好没报错"。
    """
    holder = os.path.join(OUT_ROOT, "_cc_broken_themes")
    safe_rmtree(holder)
    os.makedirs(holder, exist_ok=True)
    dst = os.path.join(holder, "hugo-theme-nebula")
    shutil.copytree(REPO, dst, ignore=shutil.ignore_patterns(
        "tmp", "public", "public-*", ".git", "myblog", "__pycache__", "resources"))
    broken = os.path.join(dst, "layouts", "partials", "util", "nested-block.html")
    with io.open(broken, "w", encoding="utf-8") as f:
        f.write("{{- .html -}}\n")   # 修复前行为：内联原始 HTML -> 被 markdownify 丢弃

    out, log, rc = build_probe("broken", pages={"p2.md": PROBE_COMPONENTS_MD},
                               theme_dir=holder)
    if rc != 0:
        H.record("C11 反证：坏副本也能构建（差异只在内容，不在构建）", False, log[-300:])
        return
    html = page(out, "p2/index.html") or ""
    # 反证成立的条件：坏副本上 C4 的断言会失败
    lost = "NESTED-VERIFY" not in html
    omitted = "raw HTML omitted" in html
    H.record("C11 反证：去掉 token 机制后嵌套内容确实丢失（证明 C4 有区分力）",
             lost, f"lost={lost} omitted={omitted}")
    H.record("C11 反证：坏副本出现 raw HTML omitted（修复前的可观测症状）",
             omitted, "")


# --------------------------------------------------------------------------- #
def main():
    main_out = guard(H, run_checks)
    if main_out:
        guard(H, run_lang_checks, main_out)
        guard(H, run_hugo_matrix)
        guard(H, run_component_checks)
        guard(H, run_component_matrix)
        guard(H, run_media_checks)
        guard(H, run_media_matrix)
        guard(H, run_media_regression)
        guard(H, run_mixed_args_check)
        guard(H, run_newline_arg_check)
        guard(H, run_nested_regression)
        guard(H, run_alias_defense)
    H.finish()


if __name__ == "__main__":
    main()