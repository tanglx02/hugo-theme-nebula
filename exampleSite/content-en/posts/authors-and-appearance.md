---
title: "Author workflow: multiple authors / edit link / appearance"
date: 2026-10-04
lastmod: 2026-10-04
description: "Multiple-author front matter, the 'Edit this page' link, and appearance configuration (accent / content width / line height / card density). Author info stays consistent across body, card, JSON-LD and RSS; no author is never fabricated."
tags: ["authors", "edit-link", "appearance", "author-workflow"]
categories: ["Feature demos"]
toc: true
# Multiple authors: list form. Use `author: "Name"` for a single author; omit both to
# fall back to the site-level params.author.
authors: ["Tanglx", "Nebula Bot"]
---

This page demonstrates three parts of **feature 4 (authoring workflow)**:
**multiple authors**, the **edit-this-page link**, and **appearance configuration**.

## 1. Multiple authors

Front matter supports three forms, in priority order:

1. **Author list** `authors = ["A", "B"]` — used by this page;
2. **Single author** `author = "A"`;
3. **Site default** `params.author`.

If none are set, **no author is output** — a name is never fabricated, and JSON-LD never
contains `"name": null`.

The same author data is kept consistent in **four places** (all from one resolver):

- the meta line at the top of the article (multiple authors joined by commas);
- the home-page card footer;
- the structured-data JSON-LD `author` (a `Person` array when there are several);
- the RSS `<author>` and `<dc:creator>`.

> To verify: look at `<meta name="author">` and `<script type="application/ld+json">`
> in this page's source — both should read `Tanglx, Nebula Bot`.

## 2. Edit this page

Once the site configures `params.editUrl`, every article shows an "Edit this page" button
that points at the **source Markdown file** (not the article URL), with CJK characters and
spaces in the path correctly encoded:

```toml
[params.editUrl]
  repo = 'https://github.com/owner/repo'
  branch = 'main'
  contentDir = 'exampleSite/content'
  provider = 'github'   # github | gitlab | gitee | custom
```

- With no `params.editUrl`, the button is **not rendered at all** (no dead link);
- A single page can opt out with front matter `editUrl: false`.

## 3. Appearance

`params.appearance` lets you tune the look without touching theme source, all via
**unified CSS variables**, with **safe fallback** for invalid values:

```toml
[params.appearance]
  accent = 'blue'          # preset: blue / teal / violet / rose / amber / emerald / custom
  accentColor = '#2b6cb0'  # custom colour when accent = 'custom' (must be valid hex)
  contentWidth = '1220px'  # content width (80–1800px)
  lineHeight = '1.85'      # body line-height (1.2–2.4)
  cardDensity = 'comfortable'  # comfortable (default) | compact
  fontFamily = "'Inter', ..."  # reading font (safe characters only)
```

Key points:

- **Default look unchanged**: when nothing is configured, **no `<style>` is emitted**,
  byte-identical to the historical output; even writing `cardDensity = 'comfortable'`
  changes nothing (it *is* the default).
- **Contrast is never lowered**: built-in presets pick AA-compliant solid/ink colours;
- **Invalid values fall back**: `accent = 'rainbow'`, `contentWidth = '9999px'`,
  a font name containing `}` / `<`, etc. are simply ignored — no destructive output.

The example site sets `accent = 'blue'` (the theme default), so it looks exactly like the
stock theme; change `accent` to `'teal'`, reload, and the accent colour switches site-wide.