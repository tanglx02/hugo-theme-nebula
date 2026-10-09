---
title: "首页布局：profile（个人档案）"
date: 2026-09-02
layout: "home-showcase"
homeLayout: "profile"
toc: false
comments: false
description: "以站长名片为主体的首页布局演示。"
---

> 本页展示 `params.home.layout = "profile"` 的真实渲染结果。

## 启用方式

```toml
[params.home]
  layout = "profile"
```

## 特征

- 顶部以**站长名片**（头像 / 简介 / 统计 / 社交）为主体
- 文章以卡片流呈现，**不显示顶部焦点图**
- 保留侧栏
- 无头像 / 无社交时自动降级（主题内置头像 + 空社交）

下面是该布局的完整渲染：