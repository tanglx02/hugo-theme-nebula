---
title: "首页布局：hero（全幅焦点区）"
date: 2026-09-03
layout: "home-showcase"
homeLayout: "hero"
toc: false
comments: false
description: "全幅焦点区优先、无侧栏的首页布局演示。"
---

> 本页展示 `params.home.layout = "hero"` 的真实渲染结果。

## 启用方式

```toml
[params.home]
  layout = "hero"
```

## 特征

- 顶部为**加高的全幅焦点区**
- **不使用侧栏**，文章列表全宽呈现
- 无封面 / 无置顶时退化为纯文字卡片，仍可正常构建

下面是该布局的完整渲染：