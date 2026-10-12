---
title: "Recommended: a solid incident-response retro checklist"
date: 2026-10-04
lastmod: 2026-10-04
description: "External-article demo: the item points off-site. The home card shows an External badge and opens in a new tab; RSS and the search index also store the off-site URL without creating a dead in-site page."
tags: ["external", "incident-response", "recommended"]
categories: ["Feature demos"]
# External article: an `externalUrl` marks an item that points off-site.
# Only http/https (or protocol-relative //) is accepted; dangerous schemes such as
# javascript: / data: are ignored and the page is treated as a normal in-site article —
# an untrusted URL is never rendered as a clickable target.
externalUrl: "https://attack.mitre.org/"
---

This article is itself an **external item**: its front matter `externalUrl` points off-site.

It shows how external articles are handled consistently in **four places**:

1. **Home card**: carries an "External" badge; the image and title both link off-site and
   open in a new tab with `target="_blank" rel="noopener"`;
2. **Search results**: the index stores the **off-site URL**, so clicking goes straight
   there instead of a dead in-site page;
3. **RSS**: `<link>` and `<guid>` use the off-site URL (`isPermaLink="false"`);
4. **No dead page**: the card links directly off-site; no in-site 404 is generated.

Security-wise, `externalUrl` only accepts **http / https / protocol-relative** URL forms;
dangerous schemes like `javascript:`, `data:text/html`, `file:` are ignored and the
article **degrades to a normal in-site article** — an untrusted input is never rendered as
a clickable target.