---
title: "Home layout: cards (default)"
date: 2026-09-01
layout: "home-showcase"
homeLayout: "cards"
toc: false
comments: false
description: "Live render of the default focus-area + card-stream home layout."
---

> This page renders `params.home.layout = "cards"` (**the default**) for real,
> by reusing the theme's own home partials.

## Enable

```toml
[params.home]
  layout = "cards"      # cards | profile | hero | landing
```

## Traits

- Focus area on top (featured + latest, up to 3 posts)
- A **card stream** body (thumbnail + title + summary + author/date/reading time)
- Right sidebar (profile / latest / categories / tag cloud)

Full render below: