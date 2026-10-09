---
title: "Home layout: profile"
date: 2026-09-02
layout: "home-showcase"
homeLayout: "profile"
toc: false
comments: false
description: "Live render of the profile-first home layout."
---

> This page renders `params.home.layout = "profile"` for real.

## Enable

```toml
[params.home]
  layout = "profile"
```

## Traits

- The **profile card** (avatar / bio / stats / socials) leads the page
- Posts render as a card stream, **no focus area**
- Sidebar retained
- Degrades gracefully with no avatar / no socials

Full render below: