---
title: "Callouts: NOTE / TIP / IMPORTANT / WARNING / CAUTION"
date: 2026-10-01
lastmod: 2026-10-01
description: "Markdown callouts demo: five semantic types, custom titles, localized default titles, unknown-type fallback, dark-mode colours. Pure render hook + CSS, zero JavaScript."
tags: ["callouts", "markdown", "typography"]
categories: ["Feature demos"]
toc: true
---

This page demonstrates the first item of **feature 3 (technical content components)**:
**Markdown callouts**.

The syntax matches GitHub / Obsidian alerts exactly — write the type marker inside a
blockquote. **No shortcode, no JavaScript.**

## 1. The five semantic types

> [!NOTE]
> Useful context the reader can skim.

> [!TIP]
> An easier or recommended way to do it.

> [!IMPORTANT]
> Key information required to finish the task.

> [!WARNING]
> Something that may cause problems and needs attention right now.

> [!CAUTION]
> A risk or negative outcome — verify before acting.

## 2. Custom titles

Put text after the type marker to replace the default title (the type and icon stay):

> [!WARNING] Back up before touching production
> Every command below needs root. Take a snapshot first.

> [!TIP] One-liner
> `hugo server -D` previews drafts.

## 3. Default titles follow the content language

Without a custom title the heading comes from the theme's i18n:

| Language | note | tip | important | warning | caution |
| --- | --- | --- | --- | --- | --- |
| English | Note | Tip | Important | Warning | Caution |
| 简体中文 | 说明 | 提示 | 重要 | 警告 | 注意 |
| 繁體中文 | 說明 | 提示 | 重要 | 警告 | 注意 |

Open the Chinese site (`/`) and this page renders Chinese headings.

## 4. Anything can live inside

> [!TIP] Rich content in a callout
> Lists, code and links all render normally:
>
> - first
> - second
>
> ```bash
> sudo systemctl restart docker
> ```
>
> See the [Hugo docs](https://gohugo.io/).

Nested quotes work too:

> [!NOTE]
> Outer callout
>
> > Inner plain quote

## 5. Unknown types never break the build

`[!BOGUS]` below is **not** a known type. The theme renders it as a **plain
blockquote** instead of a callout — the build never fails and no wrong colour appears:

> [!BOGUS]
> This type is not one of NOTE / TIP / IMPORTANT / WARNING / CAUTION.

## 6. Plain quotes are unchanged

A quote without a type marker uses Hugo's default rendering, **byte-for-byte identical**
to what the theme produced before callouts existed:

> This is a plain quote.
> No left colour bar, no icon, no bold heading.

## 7. Dark mode

Toggle dark mode in the header: all five types adapt their accent bar and icon to the
dark palette, reusing the theme's existing design tokens with no extra requests.

## 8. Version compatibility

The blockquote render hook is supported from **Hugo 0.148.0**. On **0.128.0** Hugo
silently ignores this file, so callouts degrade to plain quotes (the `[!NOTE]` marker
line is shown verbatim). The build **never fails** and nothing else is affected —
which is why the theme's minimum version stays at 0.128.0.