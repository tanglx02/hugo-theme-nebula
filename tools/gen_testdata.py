#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成可重复的压力测试数据集（固定种子，结果稳定）。

覆盖：极短 / 1 万字 / 5 万字 / 无分类标签封面 / 多封面 /
超长标题 / 超长摘要 / 超长无空格串 / 大量分类标签 / 大量代码块 /
大量图片与链接图片 / 表格嵌套列表引用脚注 / 特殊字符多语言 emoji /
草稿 / 未来 / 过期 / 极早 / 跨时区日期。

用法：
    python tools/gen_testdata.py            # 生成
    python tools/gen_testdata.py --clean    # 清理
"""
import os
import random
import shutil
import sys

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))


def _posts_dir():
    """默认生成到 myblog/content/posts；可通过 --posts-dir 覆盖（CI 用 exampleSite）。"""
    if "--posts-dir" in sys.argv:
        return os.path.abspath(sys.argv[sys.argv.index("--posts-dir") + 1])
    for cand in (os.path.join(ROOT, "myblog", "content", "posts"),
                 os.path.join(ROOT, "exampleSite", "content", "posts")):
        if os.path.isdir(os.path.dirname(cand)):
            return cand
    return os.path.join(ROOT, "content", "posts")


POSTS = _posts_dir()
PREFIX = "zz-"

random.seed(20261008)   # 固定种子，保证可重复

# 中文 filler 句子池（用于构造长文）
SENTENCES = [
    "安全运营的核心在于持续可见性与快速响应能力，两者缺一不可。",
    "在实际环境中，日志采集的完整性直接决定了溯源分析的成败。",
    "主机入侵排查应当遵循先保全后处置的原则，避免破坏现场证据。",
    "网络分区与最小权限是容器环境最基本也最容易被忽视的防线。",
    "规则调优需要结合真实流量反复验证，切忌一次性全量上线。",
    "自动化脚本可以显著降低重复劳动，但也引入了新的维护成本。",
    "应急响应演练的价值在于暴露流程缺陷，而不是走一遍过场。",
    "监控告警的阈值设置需要兼顾误报率与漏报率的平衡关系。",
    "权限收敛应当以业务最小集为起点，逐步按需放开而非反向操作。",
    "数据备份的可恢复性远比备份本身更重要，需要定期验证恢复。",
    "加密传输与存储是合规底线，但密钥管理才是真正的难点所在。",
    "安全建设是持续过程，不存在一劳永逸的产品或解决方案。",
]

# 1 万字文章中的埋点关键词（位置: 关键词）
MARKERS_10K = {
    1000: "ALPHA1000",
    3000: "BRAVO3000",
    3500: "CHARLIE3500",
    5000: "DELTA5000",
    8000: "ECHO8000",
    10000: "FOXTROT10000",
}
# 5 万字文章中的埋点关键词
MARKERS_50K = {
    2000: "SIERRA2000",
    25000: "TANGO25000",
    48000: "GOLF48000",
}

# **正文最末尾**的唯一标记（TEST-DEFECT-R2-001）。
# 与上面的"位置埋点"不同：它们的价值在于——
#   只要正文被任何程度的截断（哪怕是截到 10 字符），末尾标记必然消失。
#   旧版 check_index 只在 `max_len > 30000` 时才检查深处关键词，
#   于是"全部条目被截断成 10 字"时 max_len 只有 10，检查根本不触发 → 假绿 rc=0。
TAILMARK = "TAILMARKER_9Z8Y7X"
TAILMARK_50K = "TAILMARKER_50K_END"


def filler(target_len, markers):
    """生成长度 >= target_len 的正文，并在指定字符位置插入唯一关键词。"""
    buf = []
    length = 0
    markers = dict(sorted(markers.items()))
    mi = 0
    positions = list(markers.keys())

    def next_sentence():
        return random.choice(SENTENCES)

    while length < target_len:
        # 到达下一个埋点位置则先插入关键词
        if mi < len(positions) and length >= positions[mi]:
            buf.append(f"【埋点标记 {markers[positions[mi]]}】")
            length += len(markers[positions[mi]]) + 8
            mi += 1
            continue
        s = next_sentence()
        buf.append(s)
        length += len(s)
        if length % 400 < 20:
            buf.append("\n\n## 小节标题 " + str(length // 400 + 1) + "\n\n")
            length += 14
    # 补齐未插入的埋点（末尾追加）
    while mi < len(positions):
        buf.append(f"【埋点标记 {markers[positions[mi]]}】")
        mi += 1
    return "".join(buf)


def tailmark_filler(target_len, markers, tailmark):
    """同 filler，但在**正文最末尾**追加唯一标记（用于截断检测）。

    标记前放一句普通中文：这样"按字符截断"与"按字节截断"都会把它切掉，
    检测对两种截断方式都敏感。
    """
    return filler(target_len, markers) + f"\n\n末尾完整性标记：{tailmark}\n"


def write(name, front, body):
    path = os.path.join(POSTS, PREFIX + name)
    with open(path, "w", encoding="utf-8") as f:
        f.write("---\n" + front.strip() + "\n---\n\n" + body + "\n")
    return path


def main():
    os.makedirs(POSTS, exist_ok=True)
    created = []

    # 1. 极短文章
    created.append(write("01-short.md", """
title: "极短文章"
date: 2026-05-02
description: "一句话。"
tags: ["短"]
categories: ["压力测试"]
""", "只有一句话。"))

    # 2. 1 万字文章（含 6 个定位埋点）
    body10k = tailmark_filler(10200, MARKERS_10K, TAILMARK)
    created.append(write("02-10k.md", """
title: "一万字长文与搜索埋点"
date: 2026-05-04
description: "用于验证全文搜索能否检索正文深处的关键词。"
tags: ["长文", "搜索"]
categories: ["压力测试"]
cover: "/img/cover/lab.svg"
""", "本篇在不同字符位置埋入唯一关键词，用于验证全文搜索覆盖范围。\n\n" + body10k))

    # 3. 5 万字文章（含 3 个定位埋点）
    body50k = tailmark_filler(50000, MARKERS_50K, TAILMARK_50K)
    created.append(write("03-50k.md", """
title: "五万字超长文章"
date: 2026-05-06
description: "用于验证超长文章的索引完整性与体积。"
tags: ["超长文"]
categories: ["压力测试"]
""", "五万字压力测试正文。\n\n" + body50k))

    # 4. 无分类 / 无标签 / 无封面
    created.append(write("04-notaxonomy.md", """
title: "无分类无标签无封面"
date: 2026-05-08
""", "这篇文章没有分类、没有标签、也没有封面图，用于验证模板在字段缺失时的健壮性。\n\n正文内容。"))

    # 5. 多封面字段（cover + images）
    created.append(write("05-multicover.md", """
title: "多封面字段文章"
date: 2026-05-10
description: "同时存在 cover 与 images 字段。"
tags: ["封面"]
categories: ["压力测试"]
cover: "/img/cover/waf.svg"
images:
  - "/img/cover/soc.svg"
  - "/img/cover/ir.svg"
""", "同时提供 cover 与 images 两个字段，验证封面解析优先级。"))

    # 6. 超长标题
    long_title = "超长标题压力测试" + "这是一个非常非常长的标题用于验证卡片与标题区域的换行截断表现" * 3
    created.append(write("06-longtitle.md", f"""
title: "{long_title}"
date: 2026-05-12
description: "超长标题测试。"
tags: ["标题"]
categories: ["压力测试"]
""", "超长标题正文。"))

    # 7. 超长摘要
    long_desc = "这是一段刻意写得非常长的摘要文本" * 30
    created.append(write("07-longsummary.md", f"""
title: "超长摘要文章"
date: 2026-05-14
description: "{long_desc}"
tags: ["摘要"]
categories: ["压力测试"]
""", "超长摘要正文。"))

    # 8. 超长无空格字符串
    created.append(write("08-longword.md", """
title: "超长连续字符串"
date: 2026-05-16
description: "超长无空格字符串与长 URL 测试。"
tags: ["溢出"]
categories: ["压力测试"]
""", "超长无空格字符串：" + "A" * 200 + "\n\n长 URL：https://example.com/" + "segment/" * 40 + "?a=1&b=2\n\n连续标点：" + "。" * 80))

    # 9. 大量分类与标签
    tags = "\n".join([f'  - "标签{i}"' for i in range(1, 21)])
    cats = "\n".join([f'  - "分类{i}"' for i in range(1, 11)])
    created.append(write("09-manytaxonomy.md", f"""
title: "大量分类与标签"
date: 2026-05-18
description: "20 个标签 10 个分类。"
tags:
{tags}
categories:
{cats}
""", "大量分类与标签的正文。"))

    # 10. 大量代码块（含未知语言 / 无语言 / 带参数 / 超长行）
    code_parts = []
    code_parts.append("```python\nprint('python block')\n```\n")
    code_parts.append("```bash\necho 'bash block'\n```\n")
    code_parts.append("```unknownlang123\nthis language does not exist\n```\n")
    code_parts.append("```\nplain block without language\n```\n")
    code_parts.append('```go {linenos=true hl_lines="2"}\npackage main\nfunc main() {}\n```\n')
    code_parts.append('```js {filename="app.js"}\nconsole.log(1)\n```\n')
    code_parts.append('```python {filename="utils.py" linenos=true hl_lines="2-3"}\nimport os\nprint(1)\nprint(2)\n```\n')
    code_parts.append("```\n" + "X" * 300 + "\n```\n")
    for i in range(12):
        code_parts.append(f"```bash\necho 'block {i}'\nls -la /tmp/{i}\n```\n")
    created.append(write("10-codeblocks.md", """
title: "大量代码块与未知语言"
date: 2026-05-20
description: "代码块渲染压力测试。"
tags: ["代码块"]
categories: ["压力测试"]
""", "## 代码块集合\n\n" + "\n".join(code_parts)))

    # 11. 大量图片与链接图片
    imgs = []
    for i in range(8):
        imgs.append(f"![图片{i}](/img/cover/lab.svg \"图片标题{i}\")\n")
    imgs.append("[![被链接包裹的图片](/img/cover/waf.svg)](https://example.com/link-target \"链接标题\")\n")
    imgs.append('[![站内链接图片](/img/cover/soc.svg)](/posts/01-home-lab-proxmox/)\n')
    created.append(write("11-images.md", """
title: "大量图片与链接图片"
date: 2026-05-22
description: "图片渲染与灯箱交互测试。"
tags: ["图片"]
categories: ["压力测试"]
""", "## 图片\n\n" + "\n".join(imgs)))

    # 12. 表格 / 嵌套列表 / 引用 / 脚注
    created.append(write("12-blocks.md", """
title: "表格列表引用脚注"
date: 2026-05-24
description: "复杂 Markdown 结构测试。"
tags: ["排版"]
categories: ["压力测试"]
""", """
## 表格

| 列A | 列B | 列C |
| --- | --- | --- |
| 数据1 | 数据2 | 数据3 |
| 超长单元格内容用于测试表格在窄屏下的表现aaaaaaaaaaaaaaaaaaaaaaaa | B | C |

## 嵌套列表

1. 一级有序
   - 二级无序
     1. 三级有序
        - 四级无序
2. 一级有序第二项

- 无序 A
  - 嵌套 B
    - 嵌套 C

## 引用

> 一级引用
> > 二级嵌套引用
> > > 三级嵌套引用

## 脚注

这里有脚注引用[^1]和第二个[^note]。

[^1]: 脚注内容一。
[^note]: 脚注内容二，名字较长。
"""))

    # 13. 特殊字符 / 多语言混排 / emoji
    created.append(write("13-special.md", """
title: "特殊字符 多语言 Emoji 🚀 & <script> & \\"引号\\""
date: 2026-05-26
description: "特殊字符转义测试 ⚡ <tag> & \\"quote\\" & 'single'"
tags: ["特殊字符", "emoji", "多语言"]
categories: ["压力测试"]
""", """
## 多语言混排

中文 English 日本語 한국어 Русский العربية Español Français Deutsch 🎉🚀⚡

## HTML 特殊字符

- 尖括号：`<div class="x">&amp;</div>`
- & 符号：AT&T 与 `a && b`
- 引号：'single' "double" “中文” ‘中文’
- 反斜杠与路径：C:\\Windows\\System32\\

## Emoji

安全工程师日常 🔐 排查告警 ⚠️ 加固主机 🛡️ 写脚本 🐍 应急响应 🚨

## 正则特殊字符（搜索用）

REGEX.*+?^${}()|[\\]\\\\ TEST
"""))

    # 14. 草稿
    created.append(write("14-draft.md", """
title: "草稿文章不应出现在生产构建"
date: 2026-05-28
tags: ["草稿"]
categories: ["压力测试"]
draft: true
""", "草稿正文。"))

    # 15. 未来文章
    created.append(write("15-future.md", """
title: "未来文章不应出现在生产构建"
date: 2027-11-30
tags: ["未来"]
categories: ["压力测试"]
""", "未来文章正文。"))

    # 16. 过期 / 极早日期
    created.append(write("16-early.md", """
title: "极早日期文章"
date: 1999-01-01
description: "极早日期测试。"
tags: ["早期"]
categories: ["压力测试"]
""", "1999 年的文章。"))

    # 17-20. 跨时区日期（JSON-LD 时区验证）
    tz_cases = [
        ("17-tz-utc.md", "2026-03-01T10:30:00Z", "UTC 时间文章"),
        ("18-tz-plus8.md", "2026-03-02T18:45:00+08:00", "东八区时间文章"),
        ("19-tz-minus5.md", "2026-03-03T08:15:00-05:00", "西五区时间文章"),
        ("20-tz-plus0530.md", "2026-03-04T12:00:00+05:30", "印度时区文章"),
    ]
    for name, date, title in tz_cases:
        created.append(write(name, f"""
title: "{title}"
date: {date}
description: "时区测试 {date}"
tags: ["时区"]
categories: ["压力测试"]
""", f"时区测试：{date}"))

    # 18. 多 section（tutorials / notes / projects）
    CONTENT = os.path.join(ROOT, "myblog", "content")
    if not os.path.isdir(os.path.dirname(CONTENT)) or "--posts-dir" in sys.argv:
        # CI 场景：posts 目录的上一级即 content
        CONTENT = os.path.dirname(POSTS)
    MULTI_SECTIONS = (
        ("tutorials", ["多 Section 教程一", "多 Section 教程二"], 24),
        ("notes", ["多 Section 笔记"], 26),
        ("projects", ["多 Section 项目一", "多 Section 项目二"], 27),
    )
    for sec, titles, day in MULTI_SECTIONS:
        d = os.path.join(CONTENT, sec)
        os.makedirs(d, exist_ok=True)
        for i, t in enumerate(titles):
            fp = os.path.join(d, f"{PREFIX}{sec}-{i+1}.md")
            with open(fp, "w", encoding="utf-8") as f:
                f.write(f"""---
title: "{t}"
date: 2026-09-{day + i:02d}
description: "{sec} section 测试文章（{i + 1}）"
tags: ["多section", "{sec}"]
categories: ["压力测试"]
series: ["跨 Section 系列"]
series_order: {i + 1}
---

这是 {sec} section 下的文章，用于验证 params.content.sections 配置。
内容包含唯一标记 {sec.upper()}SECTION{i+1}。

## 小节

{filler(400, {})}
""")
            created.append(fp)

    # 19. Series（系列文章 3 篇，含系列顺序）
    SERIES = ["Hugo 建站系列：从零到上线", "Hugo 建站系列：主题与样式", "Hugo 建站系列：部署与优化"]
    for i, t in enumerate(SERIES, 1):
        fp = os.path.join(POSTS, f"{PREFIX}series-{i}.md")
        with open(fp, "w", encoding="utf-8") as f:
            f.write(f"""---
title: "{t}"
date: 2026-04-{20 + i:02d}
description: "系列文章第 {i} 篇"
tags: ["series测试"]
categories: ["压力测试"]
series: ["Hugo 建站系列"]
series_order: {i}
---

## 系列第 {i} 篇

这是系列文章的第 {i} 篇，用于验证系列导航（第 N 篇 / 共 M 篇、系列上一篇/下一篇）。

正文内容示例。
""")
        created.append(fp)

    # 20. 图片 bundle（page bundle + 真实图片资源，验证 Images Pipeline）
    try:
        from PIL import Image, ImageDraw
        bundle = os.path.join(POSTS, f"{PREFIX}images-bundle")
        os.makedirs(bundle, exist_ok=True)
        for name, fmt, size in (("photo.png", "PNG", (1600, 900)),
                                ("photo.jpg", "JPEG", (1400, 800)),
                                ("anim.webp", "WEBP", (1000, 600))):
            im = Image.new("RGB", size, (30, 60, 120))
            d = ImageDraw.Draw(im)
            for i in range(0, size[0], 80):
                d.line([(i, 0), (i, size[1])], fill=(64, 158, 255), width=3)
            for j in range(0, size[1], 80):
                d.line([(0, j), (size[0], j)], fill=(124, 92, 255), width=3)
            d.text((40, 40), f"Nebula {name}", fill=(255, 255, 255))
            im.save(os.path.join(bundle, name), format=fmt, quality=88)
        # 小 SVG（非 raster，保持原样输出）
        with open(os.path.join(bundle, "vector.svg"), "w", encoding="utf-8") as f:
            f.write('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 120" width="200" height="120">'
                    '<rect width="200" height="120" fill="#409eff"/><circle cx="100" cy="60" r="40" fill="#fff"/></svg>')

        with open(os.path.join(bundle, "index.md"), "w", encoding="utf-8") as f:
            f.write("""---
title: "图片 Bundle（Images Pipeline）"
date: 2026-05-30
description: "page bundle 图片：WebP + srcset + 尺寸防 CLS"
tags: ["图片", "bundle"]
categories: ["压力测试"]
---

## 大 PNG（走 Pipeline 生成 WebP 多尺寸）

![大图 PNG](photo.png "PNG 图片标题")

## 大 JPEG

![大图 JPEG](photo.jpg)

## WebP 源图

![WebP](anim.webp)

## SVG（非 raster，保持原图输出）

![SVG 图](vector.svg)

## 链接包裹的 bundle 图片（应保留原生跳转）

[![链接图片](photo.png)](/posts/01-home-lab-proxmox/)

## 缺失图片（应优雅降级）

![缺失的图片](not-exist.png)
""")
        created.append(os.path.join(bundle, "index.md"))
    except ImportError:
        print("  (未安装 Pillow，跳过图片 bundle 生成)")

    # 21. 边界内容（BUG-P1-003 回归 + TEST-DEFECT-013 覆盖盲区）
    #     这些输入此前从未进入过 CI：空标题 / 单字符标题 / 单 CJK / 单 emoji /
    #     纯空白标题 / 空正文 / author 为空 / 非 ASCII slug / BOM front matter。
    #     它们必须能**成功构建**（旧实现 slicestr 越界会终止整站构建）。
    edges = [
        ("21-empty-title.md", 'title: ""', "边界：空标题。"),
        ("22-one-char.md", 'title: "A"', "边界：单字符 ASCII 标题。"),
        ("23-one-cjk.md", 'title: "中"', "边界：单字符 CJK 标题。"),
        ("24-one-emoji.md", 'title: "😀"', "边界：单个 emoji 标题。"),
        ("25-blank-title.md", 'title: "   "', "边界：纯空白标题。"),
        ("26-empty-body.md", 'title: "空正文文章"', ""),
        ("27-no-author.md", 'title: "无作者（author 为空）"\nauthor: ""', "边界：author 为空。"),
        ("28-mixed-title.md",
         'title: "中英混合 Emoji 🚀 长标题 ABCDEFG 一二三四五"', "边界：中英 emoji 混合标题。"),
        ("29-中文-slug.md", 'title: "非 ASCII slug"', "边界：文件名含中文（非 ASCII slug）。"),
    ]
    for name, front, body in edges:
        created.append(write(name, front + "\ndate: 2026-06-01", body))

    # 21b. BOM front matter（部分编辑器会在文件头写入 UTF-8 BOM）
    bom_path = os.path.join(POSTS, f"{PREFIX}30-bom.md")
    with open(bom_path, "w", encoding="utf-8-sig") as f:
        f.write('---\ntitle: "BOM front matter"\ndate: 2026-06-02\n---\n\n正文。\n')
    created.append(bom_path)

    # 21c. 完全没有 date 字段（BUG-P3-001 回归数据）：
    #      页面侧必须显示本地化的"未标注日期"，绝不出现 0001 年 / 0001年1月1日。
    created.append(write("31-no-date.md", 'title: "无日期文章（front matter 无 date）"',
                         "边界：缺少 date 字段。"))

    print(f"已生成 {len(created)} 篇测试文章")
    for p in created:
        print("  ", os.path.basename(p), os.path.getsize(p) // 1024, "KB")


def clean():
    """清理测试数据。

    TEST-DEFECT-014：旧实现只对 POSTS 里的 zz-* 调 os.remove，
      - 遇到 `zz-images-bundle/` 这种**目录**会抛 IsADirectoryError 直接崩；
      - 多 section 数据（content/tutorials|notes|projects）**永不清理**，
        跨次运行会读到上一次的残留。
    现在：目录用 rmtree，多 section 一并清理，并回收空目录。
    """
    n = 0
    content = os.path.dirname(POSTS)
    targets = [POSTS] + [os.path.join(content, s) for s in ("tutorials", "notes", "projects")]
    for d in targets:
        if not os.path.isdir(d):
            continue
        for f in sorted(os.listdir(d)):
            if not f.startswith(PREFIX):
                continue
            p = os.path.join(d, f)
            try:
                if os.path.isdir(p):
                    shutil.rmtree(p, ignore_errors=True)
                else:
                    os.remove(p)
                n += 1
            except OSError as e:
                print(f"  清理失败 {p}: {e}")
    # 因测试数据而变空的多 section 目录一并回收
    for s in ("tutorials", "notes", "projects"):
        d = os.path.join(content, s)
        try:
            if os.path.isdir(d) and not os.listdir(d):
                os.rmdir(d)
        except OSError:
            pass
    print(f"已清理 {n} 项测试数据（含目录与多 section）")


if __name__ == "__main__":
    if "--clean" in sys.argv:
        clean()
    else:
        main()
