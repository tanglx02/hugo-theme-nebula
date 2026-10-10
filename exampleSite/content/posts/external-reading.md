---
title: "推荐阅读：一份优秀的应急响应复盘清单"
date: 2026-10-04
lastmod: 2026-10-04
description: "外链文章演示：条目指向站外资源。首页卡片带「外链」徽标、点击新标签打开；RSS / 搜索索引同样收录站外地址，不生成站内死页。"
tags: ["外链", "应急响应", "推荐"]
categories: ["功能演示"]
# 外链文章：标记 externalUrl 即为"指向站外"的条目。
# 仅 http/https（或协议相对 //）会被接受；javascript: / data: 等危险 scheme 会被忽略，
# 当作普通文章处理——绝不把不可信地址渲染成可点击目标。
externalUrl: "https://attack.mitre.org/"
---

这篇文章本身是一个**外链条目**：它用 Front Matter 的 `externalUrl` 指向站外资源。

它演示了外链文章在**四处**的一致处理：

1. **首页卡片**：带一枚「外链」徽标，图片与标题都链接到站外，并以
   `target="_blank" rel="noopener"` 新标签打开；
2. **搜索结果**：索引里收录的是**站外地址**，点击直达外链而非站内空页；
3. **RSS**：`<link>` 与 `<guid>` 使用站外地址（`isPermaLink="false"`）；
4. **不生成死页**：卡片直接连外链，不会被当成站内页面产生 404。

安全上，`externalUrl` 只接受 **http / https / 协议相对** 三种形态；
`javascript:`、`data:text/html`、`file:` 等危险 scheme 一律被忽略，
该文章会**退化成普通站内文章**，绝不把不可信输入渲染成可点击目标。