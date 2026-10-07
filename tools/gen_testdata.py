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
    body10k = filler(10200, MARKERS_10K)
    created.append(write("02-10k.md", """
title: "一万字长文与搜索埋点"
date: 2026-05-04
description: "用于验证全文搜索能否检索正文深处的关键词。"
tags: ["长文", "搜索"]
categories: ["压力测试"]
cover: "/img/cover/lab.svg"
""", "本篇在不同字符位置埋入唯一关键词，用于验证全文搜索覆盖范围。\n\n" + body10k))

    # 3. 5 万字文章（含 3 个定位埋点）
    body50k = filler(50000, MARKERS_50K)
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

    print(f"已生成 {len(created)} 篇测试文章")
    for p in created:
        print("  ", os.path.basename(p), os.path.getsize(p) // 1024, "KB")


def clean():
    n = 0
    for f in os.listdir(POSTS):
        if f.startswith(PREFIX):
            os.remove(os.path.join(POSTS, f))
            n += 1
    print(f"已清理 {n} 篇测试文章")


if __name__ == "__main__":
    if "--clean" in sys.argv:
        clean()
    else:
        main()
