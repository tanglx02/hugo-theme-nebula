---
title: "首页布局：landing（落地页）"
date: 2026-09-04
layout: "home-showcase"
homeLayout: "landing"
toc: false
comments: false
description: "介绍型居中排版的首页布局演示。"
---

> 本页展示 `params.home.layout = "landing"` 的真实渲染结果。

## 启用方式

```toml
[params.home]
  layout = "landing"
```

## 特征

- 居中介绍型标题 + 副标题 + 站点描述
- 复用**站长名片**模块
- **无侧栏**，文章列表居中全宽，底部带一个指向内容列表的 CTA
- 完全基于已有模块组合，未新增任何新模块

下面是该布局的完整渲染：