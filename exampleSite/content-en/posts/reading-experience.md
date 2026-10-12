---
title: "Reading experience: progress bar / focus mode / print"
date: 2026-09-30
lastmod: 2026-09-30
description: "Demo of the theme's reading-experience features: reading progress bar, back-to-top, focus mode, and print styles."
tags: ["reading", "focus-mode", "print"]
categories: ["Feature demos"]
toc: true
---

This page demonstrates **feature 2 (reading experience)**. The table of contents,
the reading progress bar, the back-to-top button (bottom-right) and the focus-mode
button (bottom-left) are all live — try them.

## 1. Reading progress bar

The thin line at the top of the viewport tracks the **article body**
(`.post-content`) rather than the whole document, so it fills exactly when you reach
the last paragraph — it is not stretched further by the footer, related posts or comments.

- Start: when the article body aligns with the top of the viewport.
- End: when the bottom of the article body reaches the bottom of the viewport.
- Shorter than the viewport: it is treated as fully read (never stuck at 0%).

## 2. Back to top

After scrolling past 400px, a round button appears in the bottom-right corner.
It is a native `<button>`: focus it with Tab, activate with Enter / Space.
With the OS "reduce motion" preference it jumps instantly instead of smooth-scrolling.

## 3. Focus mode

Activating **Focus mode** (bottom-left):

- keeps the **article body** and the **site header navigation** (you can always leave the page);
- collapses the sidebar, TOC, tags, prev/next, related posts, series, share and comments;
- persists across reloads via localStorage;
- exits with Escape.

> Focus mode never hides the body and never removes navigation — that is a hard
> requirement, otherwise readers would be trapped inside the mode.

## 4. Print styles

Open print preview (Ctrl/Cmd + P):

| Element | On paper |
| --- | --- |
| progress bar / back-to-top / focus button | removed |
| header / footer / sidebar | removed |
| share / prev-next / related / comments | removed |
| body | kept, black on white, print-friendly size and leading |
| http(s) links inside body | full URL appended (not clickable once printed) |
| code blocks | wrapped, no horizontal overflow |
| images / tables | kept off page breaks where possible |

## 5. Configuration

Site defaults (`hugo.toml`):

```toml
[params.reading]
  progressBar = true    # reading progress bar, default true
  backToTop   = true    # back to top, default true
  focusMode   = false   # focus mode entry, default false (new feature, off by default)
```

Per-article overrides (Front Matter, affects only that page):

```yaml
---
showProgress: false    # hide the progress bar on this page
showBackToTop: false   # hide back-to-top on this page
showFocusMode: true    # show the focus-mode button on this page
---
```

{{< details "Why does `false` actually work here?" >}}
The common Hugo idiom `.Params.flag | default true` returns **true** when `flag: false`,
because `default` only treats zero values as empty and `false` *is* the zero value of
`bool`. This theme resolves such flags through `util/bool-param.html` (based on `isset`),
so an explicit `false` is never swallowed. The same fix covers the long-standing
`showDate` / `toc` / `comments` / `breadcrumb` switches.
{{< /details >}}