---
title: "Content components: file trees, badges, buttons and collapsibles"
date: 2026-10-03
lastmod: 2026-10-03
description: "Technical content components: the filetree shortcode, inline badges, buttons with URL scheme validation, and zero-JS collapsibles. Path-safe escaping, no third-party requests."
tags: ["file tree", "badge", "button", "collapsible", "technical writing"]
categories: ["Feature demo"]
toc: true
---

This page demonstrates the third group of **feature 3 (technical content components)**:
**file trees**, **badges**, **buttons** and **collapsibles**.

All four share one bottom line: **zero JavaScript, zero third-party requests**.
What they emit is semantic HTML; all styling comes from the theme's own CSS.

## 1. File tree: draw a directory structure verbatim

Writing a directory tree directly in Markdown runs into three unavoidable traps:
four-space indentation becomes a code block, consecutive lines are merged into one
paragraph, and leading runs of spaces are collapsed by HTML.
The `filetree` shortcode takes all of that off your hands and guarantees one thing —
**what you write is what gets shown**.

{{< filetree "Typical Hugo site layout" >}}
my-hugo-site/
├── archetypes/
│   └── default.md
├── assets/
│   ├── css/
│   │   └── custom.css
│   └── js/
│       └── analytics.js
├── content/
│   ├── _index.md
│   └── posts/
│       └── hello-world.md
├── layouts/
│   └── shortcodes/
│       └── filetree.html
├── static/
│   └── img/
│       └── avatar.svg
├── hugo.toml
└── README.md
{{< /filetree >}}

The title is an optional first argument; omit it and only the tree is shown:

{{< filetree >}}
theme/
├── layouts/
└── assets/
{{< /filetree >}}

### Special characters in file names are safe

This "path safety" is not an afterthought — it is a deliberate design constraint.
The tree below deliberately contains characters that are sensitive to both HTML and
Markdown. In the output they are **either preserved verbatim or escaped as entities**;
they never become tags and are never parsed as Markdown:

{{< filetree "Special file names" >}}
src/
├── a&b.ts
├── <x>.ts
├── "q" 'r' `s`.ts
└── [index].md
{{< /filetree >}}

Backticks, square brackets, `&`, angle brackets and quotes are all kept character-for-character.
So even if someone wrote a `<script>` into a file name, the output would contain only
entity characters — never an executable tag.

## 2. Badges: inline micro-labels

Badges suit short markers such as a version, platform, status or language.
There are three equivalent forms and six built-in variants:

{{< badge "v1.0.9" >}} default

{{< badge "stable" "success" >}} named variant

{{< badge "deprecated" "danger" >}} named parameters

{{< badge "experimental" "warning" >}} warning

{{< badge "info" "info" >}} info

{{< badge "muted" "muted" >}} muted

The variants are fixed to six keys:
`default`, `info`, `success`, `warning`, `danger` and `muted`.

| Variant | Syntax | Typical use |
| --- | --- | --- |
| `default` | `{{</* badge "v1.0" */>}}` | neutral markers, versions |
| `info` | `{{</* badge "Info" "info" */>}}` | supplementary notes |
| `success` | `{{</* badge "Stable" "success" */>}}` | passing, released |
| `warning` | `{{</* badge "Beta" "warning" */>}}` | caution, unfinished |
| `danger` | `{{</* badge "Deprecated" "danger" */>}}` | breaking, unsupported |
| `muted` | `{{</* badge "Archived" "muted" */>}}` | de-emphasised |

**An unknown variant silently falls back to `default`** rather than failing the build —
a typo by a content author should not break the whole site. This matches the convention of
alerts (`[!BOGUS]` degrades to a plain quote). Precisely because of that, the variant value
is strictly limited to the whitelist: anything out of range is normalised to `default`,
cutting off the path that would otherwise inject a script through the class attribute.

## 3. Buttons: a clear call to action

Buttons are for a definite next step — download, external link, email, navigation:

{{< button "Read the docs" "/posts/" >}}
{{< button "GitHub profile" "https://github.com/tanglx02" >}}
{{< button "Email me" "mailto:tanglx@aliyun.com" >}}

### URL scheme validation

A button's link is **not emitted as-is**; it first passes a scheme whitelist:

- **Allowed**: `http://`, `https://`, protocol-relative `//`, `mailto:`, `tel:`,
  and any **scheme-less** relative path / root path / anchor
  (e.g. `posts/x/`, `/about/`, `#sec`);
- **Rejected**: `javascript:`, `vbscript:`, `data:`, `file:`, `ftp:` and every other scheme,
  plus the empty value.

A link judged unsafe **emits no `<a>`**. Instead it renders as a non-clickable placeholder
with a readable hint (the text comes from i18n, so it follows the site language):

{{< button "This button is blocked" "javascript:alert(1)" >}}
{{< button "So is this one" "data:text/html,<script>alert(1)</script>" >}}

The reasoning is direct: a naive `href="{{ .Get 1 }}"` may get a filter from Hugo's
template engine, but those rules change with the Go version and cannot express
"only these schemes are allowed". **Deciding in the template** is what lets the assertion
run against the built artifact — once a `javascript:` shows up in the output, it is too late.

There is also a classic bypass to defend against: browsers ignore whitespace inside
`java<TAB>script:`. So the value is stripped of all whitespace and control characters
before comparison, and `java` + tab + `script:` is blocked just the same.

### Opening behaviour and in-site paths

- **External links** (`http/https/protocol-relative`) automatically get
  `target="_blank"` and `rel="noopener"` — a new tab with no `window.opener` hazard;
- **`mailto:` / `tel:`** and **in-site links** get no `target` — email and phone go to the
  system, in-site navigation stays in the same window;
- in-site relative paths are normalised, so they stay correct under a
  **sub-path baseURL** (e.g. `baseURL = '.../blog/'`).

## 4. Collapsibles: optional supplementary detail

A collapsible holds "read it if you want" material — derivations, edge cases, side notes.
It is built on native `<details>` / `<summary>`, **zero JavaScript**,
natively usable with keyboard and screen readers:

{{< details "Why is it collapsed by default?" >}}
If every aside were expanded, the body of a long article would be interrupted by branches.
Collapsing the secondary material keeps a one-line hint by default, lets readers expand on
demand, and keeps the main narrative tight.
{{< /details >}}

To start expanded, pass `open` — note that here you **must use named parameters throughout**:

{{< details title="I start expanded" open="true" >}}
This is the effect of `open="true"`: it is already expanded when the page loads.
{{< /details >}}

Mixing a positional argument with a named one, on the other hand, **fails the build outright**:

```
{{</* details "Title" open="true" */>}}
```

That is not specific to this component — it is a hard rule for all Hugo shortcodes —
so the examples here use the `title=` + `open=` named form.
(Incidentally, this snippet only displays as code because it uses Hugo's escape form
`{{</* */>}}` — otherwise it would actually be executed during the build.)

A collapsible can hold lists, code blocks, even other components:

{{< details "A code block inside a collapsible" >}}
```bash
hugo --gc --minify
```
{{< /details >}}

> Aside: why a shortcode rather than a literal `<details>`?
> Because the theme defaults to `unsafe = false` (a safe default), a bare `<details>`
> written in Markdown is treated as raw HTML and **dropped wholesale** by goldmark,
> leaving only a `WARN Raw HTML omitted` in the build log — the content silently vanishes
> while the build succeeds. Through the shortcode, content goes down the normal Markdown
> pipeline and is both complete and safe.

## 5. Nesting

These four components nest with **tabs** and **steps**. When nested, a child does not hand
its HTML straight to the parent; it returns a placeholder token, so the parent's Markdown
pass cannot drop the raw HTML:

{{< tabs >}}
{{< tab "Tree view" >}}

{{< filetree "Nested in a tab" >}}
project/
├── src/
└── tests/
{{< /filetree >}}

{{< /tab >}}
{{< tab "Collapsed note" >}}

{{< details "A collapsible inside a tab" >}}
This demonstrates the "tab → collapsible" nesting.
{{< /details >}}

{{< /tab >}}
{{< /tabs >}}

## 6. What happens without JavaScript

The answer: **nothing is lost**.

These four components are entirely server-rendered plus CSS. Disabling JavaScript does not
affect their display, expansion or clicking (native elements carry their own interaction).
This is the same design constraint they share with tabs and steps.

## 7. Printing and version compatibility

- **Printing**: collapsibles **expand automatically** when printing (otherwise their content
  would be lost); button chrome is simplified; badges and file trees render normally.
- **Version compatibility**: all four are implemented purely with shortcodes and CSS, with
  identical output structure across every Hugo version the theme supports (0.128.0 and up);
  CI asserts an identical structure signature on all five versions.