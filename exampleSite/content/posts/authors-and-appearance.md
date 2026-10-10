---
title: "作者工作流：多作者 / 编辑入口 / 外观配置"
date: 2026-10-04
lastmod: 2026-10-04
description: "多作者 Front Matter、编辑此页入口、外观配置（强调色 / 正文宽度 / 行高 / 卡片密度）演示。作者信息在正文、卡片、JSON-LD 与 RSS 四处保持一致；无作者时不虚构。"
tags: ["多作者", "编辑入口", "外观配置", "作者工作流"]
categories: ["功能演示"]
toc: true
# 多作者：列表形式。单作者时用 `author: "姓名"` 即可；都不写则回退站点 params.author。
authors: ["Tanglx", "Nebula Bot"]
---

本页演示**功能四（编辑与作者工作流）**中的三项能力：
**多作者**、**编辑此页入口**与**外观配置**。

## 一、多作者

Front Matter 支持三种写法，优先级从高到低：

1. **多作者列表** `authors = ["A", "B"]` —— 本页即用此写法；
2. **单作者** `author = "A"`；
3. **站点默认** `params.author`。

都不写时**不输出作者**——绝不虚构姓名，也不会在 JSON-LD 里出现 `"name": null`。

同一份作者信息在**四个位置**保持一致（同源于一个解析函数）：

- 正文顶部元信息（多个作者以逗号并列）；
- 首页卡片底部；
- 结构化数据 JSON-LD 的 `author`（多人时输出 `Person` 数组）；
- RSS 的 `<author>` 与 `<dc:creator>`。

> 校验方法：查看本页源码里的 `<meta name="author">` 与
> `<script type="application/ld+json">`，两者应显示 `Tanglx, Nebula Bot`。

## 二、编辑此页入口

站点配置了 `params.editUrl` 后，每篇文章底部会出现「编辑此页」按钮，
指向**源 Markdown 文件**（而非文章 URL），路径中的中文与空格会被正确编码：

```toml
[params.editUrl]
  repo = 'https://github.com/owner/repo'
  branch = 'main'
  contentDir = 'exampleSite/content'
  provider = 'github'   # github | gitlab | gitee | custom
```

- 未配置 `params.editUrl` 时，**完全不输出**该按钮（不产生死链接）；
- 单篇文章可用 Front Matter `editUrl: false` 关闭。

## 三、外观配置

`params.appearance` 让你在不改主题源码的前提下调整观感，
全部**通过统一 CSS 变量**实现，非法值一律**安全回退**：

```toml
[params.appearance]
  accent = 'blue'          # 预设：blue / teal / violet / rose / amber / emerald / custom
  accentColor = '#2b6cb0'  # accent = 'custom' 时使用的自定义色（须为合法 hex）
  contentWidth = '1220px'  # 正文容器宽度（80–1800px）
  lineHeight = '1.85'      # 正文行高（1.2–2.4）
  cardDensity = 'comfortable'  # comfortable（默认）| compact
  fontFamily = "'Inter', ..."  # 阅读字体（仅安全字符）
```

要点：

- **默认外观不变**：不配置时**不输出任何 `<style>`**，与历史产物逐字节一致；
  连显式写 `cardDensity = 'comfortable'` 也**不改变**外观（它就是默认值）。
- **不降低对比度**：内置预设的实心按钮色与文字色都预先选取为 AA 达标值；
- **非法回退**：`accent = 'rainbow'`、`contentWidth = '9999px'`、
  含 `}` / `<` 的字体名等都会被**忽略该项**，回退默认，不产生破坏性输出。

示例站启用了 `accent = 'blue'`（即主题默认蓝），因此观感与默认完全一致；
把 `accent` 改成 `'teal'` 保存后刷新，主色会整站切换。