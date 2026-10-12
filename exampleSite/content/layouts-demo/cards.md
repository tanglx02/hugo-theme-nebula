---
title: "首页布局：cards（默认）"
date: 2026-09-01
layout: "home-showcase"
homeLayout: "cards"
toc: false
comments: false
description: "焦点图 + 卡片流的默认首页布局演示。"
---

> 本页展示 `params.home.layout = "cards"`（**默认布局**）的真实渲染结果。
> 它直接复用主题的首页 partial，因此这里看到的就是开启该布局后首页的样子。

## 启用方式

```toml
[params]
  # 默认即为 cards，无需配置；如需显式声明：
[params.home]
  layout = "cards"      # cards | profile | hero | landing
```

## 特征

- 顶部焦点区（置顶文章 + 最新文章，最多 3 篇）
- 主体为**卡片流**（封面缩略图 + 标题 + 摘要 + 作者/日期/阅读时长）
- 右侧为侧栏（站长名片 / 最新文章 / 分类 / 标签云）

下面是该布局的完整渲染：