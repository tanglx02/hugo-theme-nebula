# Nebula — 一款清爽现代的 Hugo 博客主题

[![CI](https://github.com/tanglx02/hugo-theme-nebula/actions/workflows/ci.yml/badge.svg)](https://github.com/tanglx02/hugo-theme-nebula/actions/workflows/ci.yml)
[![Hugo](https://img.shields.io/badge/Hugo-%E2%89%A5%200.128-blue)](https://gohugo.io/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

面向技术博客的 Hugo 主题：**卡片流首页 + 焦点图、完整全文搜索、暗色模式、文章目录、图片 Pipeline、系列文章、代码高亮与一键复制**。零运行时依赖；默认配置下无外部 CDN 请求（启用可选评论/统计功能后会加载对应第三方服务资源，见下方说明）。

| 亮色 | 暗色 |
| --- | --- |
| ![首页亮色](docs/screenshots/01-home-light.png) | ![首页暗色](docs/screenshots/04-home-dark.png) |

| 文章页（含目录） | 全站搜索 |
| --- | --- |
| ![文章页](docs/screenshots/03-post-dark.png) | ![搜索](docs/screenshots/05-search.png) |

| 归档页 | 移动端 |
| --- | --- |
| ![归档](docs/screenshots/06-archive.png) | ![移动端](docs/screenshots/07-mobile.png) |

## 特性

- 🎴 **焦点图 + 卡片流首页**：置顶文章自动进入焦点区
- 🔍 **完整全文搜索**：正文任意位置（含数万字长文末尾）均可检索；`Ctrl+K` / `/` 呼出；支持 `?q=` 深链
- 🧩 **自动索引模式**：`mode = "auto"` 按索引体积自动决定单文件或分片，无需用户判断
- 🌗 **暗色模式**：跟随系统 + 手动切换 + 记忆
- 📑 **文章目录**：自动生成、滚动高亮
- 🖼️ **图片 Pipeline**：page bundle 图片自动生成 WebP 多尺寸 `srcset`，带 `width/height` 防 CLS；static 路径保持原样
- 📚 **系列文章**：`series` + `series_order`，显示进度与系列内上下篇
- 💻 **代码块**：macOS 风格窗口、语言标签、`filename` / 行号 / 指定行高亮、一键复制
- 🖼️ **灯箱**：`role=dialog` + Focus Trap（Tab 循环、背景 inert、Esc 关闭、焦点归还）
- 🌍 **i18n**：内置 `zh-CN` / `zh-TW` / `en`
- 🔀 **多 Section**：内容范围通过 `params.content.sections` 配置，不写死 `posts`
- 🔗 **分享**：可选开关（复制链接 / X / Telegram / Facebook / Reddit / 微博 / 微信），
  复制失败会明确提示"复制失败，请手动复制"，**绝不把超时/被拒伪装成成功**
- 📡 **RSS 增强**：标题 / 描述 / 作者 / 分类 / pubDate / updated，支持 `fullContent` 全文输出
- 🔎 **SEO**：canonical、OG、Twitter Card、BlogPosting + WebSite JSON-LD、SearchAction、hreflang、sitemap、robots
- ♿ **无障碍**：键盘可达、焦点可见、`prefers-reduced-motion`、触屏点击区 ≥ 24px
- 🛡️ **发布门禁**：Release 全站审计覆盖 sitemap 全部 HTML 页面（含分类/标签 term 与分页），
  三浏览器 × 四视口；i18n 硬编码静态扫描防回归；测试脚本失败一律 `exit 1`
- ⚡ **默认零依赖**：无 jQuery / 无外部字体 / 默认无外部 CDN 请求；
  启用可选的评论或统计功能后，页面会加载对应第三方服务的资源（见下方"第三方服务说明"）

## 环境要求

- **Hugo extended** ≥ 0.128（extended 版本必需：图片 WebP 处理与 SCSS 需要）

### 版本兼容（CI 实测）

最低版本不是估计值：CI 用多个真实 Hugo 版本对 `exampleSite` 做生产构建。

| Hugo 版本 | 构建结果 |
| --- | --- |
| 0.128.0 | ✅ 通过 |
| 0.162.0 | ✅ 通过 |
| 0.167.0 | ✅ 通过 |
| latest | ✅ 通过 |

> 搜索分片（`mode = "shard"` / auto 触发分片）依赖较新的 `resources.Publish`，实测 **0.167+ 可用**；单文件索引模式在所有支持版本均可用。

## 快速开始

```bash
hugo new site myblog && cd myblog
git init
git submodule add https://github.com/tanglx02/hugo-theme-nebula.git themes/hugo-theme-nebula
```

最小配置（`hugo.toml`）：

```toml
baseURL = 'https://your-domain.com/'
locale = 'zh-CN'
title = '我的博客'
theme = 'hugo-theme-nebula'
hasCJKLanguage = true

[pagination]
  pagerSize = 8                   # 每页文章数（Hugo ≥ 0.128 用此项，旧的 paginate 已失效）

[outputs]
  home = ['HTML', 'RSS', 'JSON']  # JSON 用于生成搜索索引，必须保留

[markup]
  [markup.highlight]
    noClasses = false             # false = 使用 CSS class，代码配色可随暗色模式切换
  [markup.goldmark]
    [markup.goldmark.renderer]
      unsafe = false              # 主题不依赖 raw HTML；仅当你的文章需要原始 HTML 时才设为 true

[params]
  author = '你的名字'
  description = '博客描述'
```

写文章并预览：

```bash
hugo new content posts/hello-world.md
hugo server -D      # 打开 http://localhost:1313
```

> 生产构建请用 `hugo --gc --minify`，**不要**把 `hugo server` 的输出当作生产产物（它会注入 livereload）。

## 完整配置参考

```toml
[params]
  author = 'Tanglx'
  subtitle = '记录安全与运维的每一次实践'
  description = '站点 SEO 描述'
  avatar = 'img/avatar.svg'              # 放站点 static/ 下
  logoText = 'N'                         # 无 logo 图时导航栏显示的字母
  homePostCount = 8                      # 首页"最新文章"数量
  footerText = 'Keep Learning.'
  license = '本文采用 CC BY-NC-SA 4.0 许可，转载请注明来源。'

  [params.profile]
    bio = '侧边栏个人名片简介'

  [params.socials]                       # 留空即不显示对应图标
    github = 'https://github.com/yourname'
    email = 'mailto:you@example.com'
    bilibili = 'https://space.bilibili.com/xxx'

  [params.sidebar]
    hotCount = 6

  # ---------- 内容范围（不再写死 posts） ----------
  [params.content]
    sections = ["posts"]                 # 可多个：["posts", "tutorials", "notes"]

  # ---------- 搜索 ----------
  [params.search]
    enable = true
    mode = "auto"                        # auto（默认）| single | shard
    autoThreshold = 512000               # auto 模式的阈值（正文总字节数，约 500KB）
    contentLimit = 0                     # 单篇正文索引上限（0 = 不限制，保证全文可搜）
    shard = false                        # 兼容旧配置：true 等价于 mode = "shard"

  # ---------- 图片 Pipeline ----------
  [params.images]
    widths = [480, 768, 1200]            # 生成的宽度档位
    sizes = "(max-width: 768px) 100vw, 900px"
    quality = 85
    format = "webp"

  # ---------- RSS ----------
  [params.rss]
    fullContent = false                  # true = 输出全文（content:encoded），false = 仅摘要
    limit = 20

  # ---------- 分享（默认关闭） ----------
  [params.share]
    enable = false
    providers = ["copy", "x", "telegram", "facebook"]   # 可选 reddit / weibo / wechat

  # ---------- 评论（默认关闭） ----------
  [params.comments]
    enable = false
    provider = 'giscus'                  # giscus | waline | twikoo | disqus
    [params.comments.giscus]
      repo = 'yourname/yourrepo'
      repoID = 'R_xxxxxxx'
      category = 'Announcements'
      categoryID = 'DIC_xxxxxxx'

  [params.views]
    enable = false
  [params.busuanzi]
    enable = false
```

### 第三方服务说明（可选功能）

主题**默认配置下不加载任何第三方资源**（已由 CI 断言）。以下功能一旦启用，
页面会加载对应第三方服务的脚本/样式，其可用性与隐私政策由服务方决定：

| 功能 | 服务 | 加载的资源 | 备注 |
| --- | --- | --- | --- |
| 评论（giscus） | giscus.app | `https://giscus.app/client.js` 及其 iframe | locale 跟随站点语言，可用 `comments.giscus.lang` 覆盖 |
| 评论（Waline） | Waline + unpkg | `unpkg.com` 上的 CSS/JS + 你自建的 `serverURL` | locale 跟随站点语言，可用 `comments.waline.lang` 覆盖 |
| 评论（Twikoo） | Twikoo + jsDelivr | `cdn.jsdelivr.net` 上的 JS + 你自建的 `envId` | locale 跟随站点语言，可用 `comments.twikoo.lang` 覆盖 |
| 评论（Disqus） | disqus.com | `https://<shortname>.disqus.com/embed.js` 及其 iframe | Disqus 无 locale 参数，语言在其后台配置 |
| 访问统计（busuanzi） | busuanzi.ibruce.info | 不蒜子统计脚本 | 仅 `params.busuanzi.enable = true` 时加载 |
| 浏览量（views） | 你自己的统计后端 | 取决于 `params.views` 配置 | 默认关闭 |

评论组件语言映射：站点语言 `zh` / `zh-cn` / `zh-hans` → `zh-CN`；
`zh-tw` / `zh-hant` / `zh-hk` → `zh-TW`；`en` / `en-us` / `en-gb` → `en`。
未命中映射的语言会原样传给第三方组件，不会强造不存在的 locale。

### 多语言站点

主题完整支持 Hugo multilingual（`[languages]` 配置）：

- 页面 `<html lang>`、`og:locale`（含 `og:locale:alternate`）、`hreflang` 自动输出；
- UI 文案内置 zh-CN / zh-TW / en 三语言，评论组件 locale 跟随站点语言；
- 分类、标签、Series、搜索索引、RSS 均按语言隔离。

主题**没有语言切换按钮**——语言切换通过 URL 结构与 `<link rel="alternate" hreflang>` 完成
（如 zh-CN 在根路径、en 在 `/en/` 子路径），这是有意为之的轻量设计。

### 导航菜单

```toml
[[menu.main]]
  name = '首页'
  url = '/'
  weight = 1
[[menu.main]]
  name = '归档'
  url = '/archives/'
  weight = 5
[[menu.main]]
  name = 'GitHub'
  url = 'https://github.com/yourname'
  weight = 6
  [menu.main.params]
    external = true        # 新标签页打开
```

归档页需要 `content/archives/_index.md`：

```yaml
---
title: "文章归档"
layout: "archive"
---
```

## 全文搜索与索引模式

索引由 `layouts/_default/index.json` 在构建期生成，包含每篇文章的**完整正文纯文本**（仅压缩连续空白），因此正文任意位置都能被检索。

三种模式：

| 模式 | 行为 | 适用 |
| --- | --- | --- |
| `single` | 单个 `index.json` 包含全部正文 | 小型站点，最简单 |
| `shard` | 主索引只含元数据，正文按**体积分块**（chunk）到 `search/chunk-N.json`，前端并发加载 | 中大型站点 |
| `auto`（默认） | 按正文总体积自动在 single / shard 之间选择（阈值 `autoThreshold`） | 推荐 |

```toml
[params.search]
  enable = true
  mode = "auto"          # auto | single | shard（兼容旧的 shard = true）
  autoThreshold = 512000 # auto 模式阈值（字节）
  chunkSize = 204800     # 分片模式下每个 chunk 的目标体积（字符数）
  contentLimit = 0       # 单篇正文上限，0 = 不限制
```

实测数据（每篇约 3000 字，Chromium，本地静态服务器）：

| 文章数 | 模式 | 主索引 | chunk 数 | 索引加载 | 搜索等待 | JS 堆 |
| --- | --- | --- | --- | --- | --- | --- |
| 500 | single | 4.4 MB | – | 532 ms | 647 ms | 6.1 MB |
| 500 | auto→shard | 84 KB | 22 | 163 ms | 248 ms | 5.9 MB |
| 1000 | single | 8.8 MB | – | 1283 ms | 1322 ms | 8.6 MB |
| 1000 | auto→shard | 168 KB | 44 | 331 ms | 379 ms | 8.8 MB |
| 2000 | single | 17.6 MB | – | 3988 ms | 3989 ms | 23.5 MB |
| 2000 | auto→shard | 338 KB | 87 | 1344 ms | 1347 ms | 25.7 MB |

> 分片按**体积**合并（而不是每篇一个文件）：请求数与正文总量成正比，而不是与文章数成正比。
> 2000 篇时若按文章分片会产生 2000 个请求，实测搜索延迟明显劣化。

搜索索引加载失败时会有明确提示：主索引失败显示错误并可**重试**；部分分片失败时提示"部分索引加载失败（N 篇未能加载）"且仍返回其他文章的结果（**不会误报"没有找到"**）。

## 图片处理

两种图片写法，行为不同：

1. **page bundle 资源**（推荐）：把图片与 `index.md` 放在同一目录，正文写 `![说明](photo.png)`
   → 自动生成 WebP 多尺寸 `srcset`、`sizes`、`width/height`（防 CLS）、`loading="lazy"`，并保留原图供灯箱放大。
2. **static 路径或外链**：`![说明](/img/a.png)`、`https://…`
   → 与旧版完全一致，不做处理（**已有站点的资源写法不受影响**）。

SVG 等不可处理的资源会按原样输出。缺失图片不会导致构建失败。

## 系列文章（Series）

```yaml
---
title: "Hugo 建站系列：主题与样式"
series: ["Hugo 建站系列"]
series_order: 2          # 可选；缺省时按日期排序
---
```

文章页会显示系列名、进度（第 N 篇 / 共 M 篇）、系列全部文章列表、系列内上一篇/下一篇。**未配置 `series` 时完全不输出**，不影响原有的上一篇/下一篇导航。

## 多语言（i18n）

主题内置 `i18n/zh-CN.yaml`、`zh-TW.yaml`、`en.yaml`。**模板与 JS 中的 UI 文案全部来自 i18n**，
JS 侧通过 `window.NEBULA_I18N` 注入（脚本内不硬编码文案，仅有英文兜底以防注入失败）。

单语言站点无需配置；多语言站点示例（**注意 Hugo ≥ 0.158 用 `locale` 决定翻译包，仅改
`defaultContentLanguage` 不够**）：

```toml
defaultContentLanguage = 'zh-CN'
locale = 'zh-CN'

[languages]
  [languages.zh-CN]
    label = '简体中文'
    weight = 1
    [languages.zh-CN.params]
      description = '中文站点描述'
  [languages.en]
    label = 'English'
    weight = 2
```

多语言站点会自动输出 `hreflang` 标签。

### 导航菜单跟随语言

给菜单项加 `identifier`，主题会查找 `menu.<identifier>` 词条（缺失时回退到 `name`，因此
旧配置完全兼容）：

```toml
[[menu.main]]
  identifier = 'posts'    # → i18n 词条 menu.posts
  name = '文章'            # 回退值
  url = '/posts/'
  weight = 2
```

内置 identifier：`home` `posts` `categories` `tags` `archives` `about` `aboutMe`；
自定义 identifier 只需在 `i18n/<lang>.yaml` 里补一个 `menu.<identifier>` 词条。

## Front Matter 字段

```yaml
---
title: "文章标题"
date: 2026-10-08
lastmod: 2026-10-08
draft: false
description: "摘要：用于列表卡片、搜索片段与 SEO"
author: ""                # 留空使用站点 author
tags: ["Hugo"]
categories: ["效率工具"]
series: ["Hugo 建站系列"] # 可选
series_order: 1           # 可选
cover: "/img/cover/x.png" # 封面；无则用渐变占位
sticky: false             # true = 置顶并进入首页焦点区

# ---- 显示控制（全部可选，默认值与历史视觉一致）----
toc: true                 # 目录
comments: true            # 评论
showDate: true            # 日期
showLastmod: false        # 更新日期
showReadingTime: true     # 阅读时长
showWordCount: true       # 字数
showTags: true            # 标签
showRelated: true         # 相关文章
showNav: true             # 上下篇导航
showSeries: true          # 系列卡片
showShare: false          # 分享（也可用 params.share.enable 全局开启）
lightbox: true            # 图片灯箱
---
```

## 分享

默认关闭。开启后为纯链接按钮（不加载任何第三方脚本）：

```toml
[params.share]
  enable = true
  providers = ["copy", "x", "telegram", "facebook", "weibo", "wechat"]
```

## 代码块

````markdown
```js {filename="app.js"}
console.log(1)
```

```python {filename="utils.py" linenos=true hl_lines="2-3"}
import os
print(1)
print(2)
```
````

支持 `filename`（显示文件名）、`linenos`（行号）、`hl_lines`（高亮行）、未知语言与无语言代码块（安全降级为纯文本）。

## exampleSite / 本地开发

```bash
git clone https://github.com/tanglx02/hugo-theme-nebula.git
cd hugo-theme-nebula

# 生成压力测试数据（可选，用于跑完整测试）
python3 tools/gen_testdata.py --posts-dir exampleSite/content/posts

# 预览示例站点
hugo server --source exampleSite --themesDir ../..

# 生产构建
hugo --source exampleSite --themesDir ../.. --gc --minify -d ../public
```

## 测试与 CI

### 退出码约定（这是 CI 门禁可信的前提）

`tools/` 下所有测试脚本共用 `tools/_testlib.py`：

| 情况 | 退出码 |
| --- | --- |
| 产品问题 / 断言失败 | 1 |
| 测试脚本自身异常 | 1 |
| 依赖缺失（playwright / pillow） | 1 |
| 浏览器无法启动 | 1 |
| 被测站点 / 静态服务器不可达 | 1 |
| 一个用例都没执行到 | 1 |
| 全部通过 | 0 |

最后一个输出行是机器可读结果，便于 CI 与报告解析：

```
TEST-RESULT: {"suite": "audit", "status": "PASS", "passed": 7, "failed": 0, "total": 7}
```

> 没有这条约定的"打印 FAIL 但进程仍 exit 0"会让 CI 变成假绿灯 —— CI 是否可信，
> 唯一标准是**失败时进程 exit≠0 且 GitHub Actions 真的变红**。

### CI Job

`.github/workflows/ci.yml` 在 GitHub Actions 上**真实运行**以下检查，任一失败即 CI 失败：

| Job | 内容 |
| --- | --- |
| Build (0.128 / 0.162 / 0.167 / latest) | 生成压力数据 → 生产构建 → 产物校验 → 索引完整性 → 草稿/未来排除 → livereload 检查 |
| Sub-directory baseURL | `/blog/` 构建 + 断言无越界路径、无 basePath 重复 |
| Static checks | 死链、索引完整性、功能断言、**i18n 静态硬编码扫描**、**i18n 三语言构建与文案校验**、**多 Section 完整回归**、auto 阈值分片 |
| Browser tests (chromium / firefox / webkit) | 响应式审计（320–1440）、交互回归、**复制语义专项**、灯箱 Focus Trap、搜索边界与竞态、**分片失败深层关键词语义**、三种 baseURL 部署 |
| Release full-site audit (chromium / firefox / webkit) | 仅 tag（`v*`）或手动触发：`AUDIT_FULL=1` 扫描 sitemap 中**全部 HTML 页面**（320/375/768/1440），并断言覆盖了分类 term、标签 term、分页、归档等必需页面类型 |

> PR 阶段用抽样页面保证时长可控；Release 阶段用全量页面。
> 全站模式会打印 `SITEMAP HTML PAGES` / `EXTRA PAGINATION PAGES` / `AUDITED HTML PAGES`
> 并断言三者一致 —— **抽样冒充全站会被直接判失败**。
>
> Hugo 的 sitemap 不包含 `/page/N/`，这些分页页由审计脚本沿站点真实链接抓取并单独计数。

### 全站审计的覆盖保证

`AUDIT_FULL=1` 不只是"跑得多"，还会主动证明没有漏：

- **数量一致**：`sitemap_html + extra_pagination == audited_html`，对不上即失败；
- **类型齐全**：`分类 term / 标签 term / page/2/ / page/3/ / 分类首页 / 标签首页 / 归档页 / 文章页`
  任一类型缺失即失败；
- **白名单精确匹配**：故意缺失的测试资源按 **pathname 精确比对**豁免。
  绝不使用 `endswith` —— 否则 `/images/not-exist.png` 这类真实损坏资源会被误豁免成假绿灯。

### 复制行为的硬性约定

代码块复制、分享复制链接、微信复制共用同一实现，**结果只有成功 / 失败两种**：

| 场景 | 结果 |
| --- | --- |
| `navigator.clipboard.writeText` resolve | 成功 |
| `writeText` reject | 走 fallback |
| `writeText` 长时间 pending（>1200ms） | 走 fallback，**绝不显示成功** |
| 无 Clipboard API | 走 fallback |
| `document.execCommand('copy')` 返回非 `true` | **失败**（显示"复制失败，请手动复制"） |

`tools/verify_copy.py` 对以上每条路径都有断言（13 例），并对代码块按钮、
分享按钮、微信按钮分别验证。

### 本地运行

```bash
export HUGO_BIN=/path/to/hugo          # Linux/macOS 可省略（默认 hugo）
export PLAYWRIGHT_PROXY=http://127.0.0.1:port   # 本地有 HTTP 代理时才需要
python3 tools/serve.py public 8080 &   # 独立静态服务器（勿用 hugo server 产物测试）

python3 tools/link_check.py public                 # 死链（失败即 exit 1）
python3 tools/check_index.py public/index.json     # 索引完整性
python3 tools/check_features.py public             # 功能断言（26 项）
python3 tools/check_i18n_hardcode.py               # UI 文案是否被写死进模板/脚本
python3 tools/verify_i18n.py public zh-CN          # 渲染结果文案是否来自 i18n
SITE_DIR=exampleSite HUGO_ARGS='--source . --themesDir ../..' \
  python3 tools/verify_multisection.py             # 多 Section 完整回归
AUDIT_BROWSERS=chromium python3 tools/audit.py http://127.0.0.1:8080
AUDIT_FULL=1 AUDIT_BROWSERS=chromium AUDIT_VIEWPORTS=320,375,768,1440 \
  python3 tools/audit.py http://127.0.0.1:8080     # 等价于 Release 全站审计
python3 tools/verify_copy.py http://127.0.0.1:8080 chromium   # 复制语义（13 例）
PW_BROWSERS=chromium python3 tools/interactions.py http://127.0.0.1:8080
python3 tools/verify_lightbox.py http://127.0.0.1:8080 chromium
python3 tools/verify_search_edge.py http://127.0.0.1:8080
python3 tools/verify_search_shard.py http://127.0.0.1:8090 chromium
python3 tools/bench_index.py 500,1000,2000         # 索引规模压测（记录体积/请求数/耗时/内存）
```

> `check_i18n_hardcode.py` 会自动定位主题源码目录：命令行参数 > `NEBULA_THEME_DIR` >
> 仓库根 > 站点侧 `myblog/themes/hugo-theme-nebula`；全部候选都不合格时报错退出，
> 不会因为"扫不到文件"而静默通过。


## 更新日志

### v1.0.5 — 发布门禁与测试覆盖修复

**发布门禁**

- Release 全站审计从"chromium 单浏览器 2 视口"升级为 **chromium / firefox / webkit 三浏览器 ×
  320/375/768/1440 四视口**，并接入复制语义与交互回归
- 全站审计**取消了 taxonomy / page 排除**：v1.0.4 的 `AUDIT_FULL=1` 实际漏掉分类、标签 term 页与
  `/page/N/` 分页页，122 个 sitemap 页里只审了 105 个。现覆盖 **122 + 3 分页 = 125 个 HTML 页面**
- 新增两条硬断言，防止"抽样冒充全站"：
  - `sitemap_html + extra_pagination == audited_html`（数量对不上即失败）
  - 分类 term / 标签 term / `page/2/` / `page/3/` / 分类首页 / 标签首页 / 归档页 / 文章页
    任一类型缺失即失败
- Hugo sitemap 不含 `/page/N/`，改为沿站点真实链接多轮抓取分页，并单独计数

**复制行为的真实缺陷**

- 此前 `writeText` 的 Promise 若长时间 pending，400ms 后走 fallback，而 fallback **不检查
  `execCommand` 返回值**就调用成功回调 —— 复制实际失败，界面却提示"已复制"
- 修复后：只有 clipboard resolve 才算成功；reject / pending 超时 / 无 Clipboard API /
  `execCommand` 返回非 `true`，**一律判失败**并提示"复制失败，请手动复制"
- 超时阈值 400ms → 1200ms；代码块复制、分享复制链接、微信复制统一到同一个 `copyText` 实现
- 新增 `common.copyFailed`（zh-CN / zh-TW / en）与 `.copy-failed` 失败态样式

**i18n 防回归**

- 新增 `tools/check_i18n_hardcode.py`：扫描 `layouts/**/*.html` 与 `assets/**/*.js`，
  命中 36 个禁用 UI 文案即失败（注释、`i18n` 调用、README 除外）
- 扫描到 0 个文件时同样 `exit 1`，不会因路径解析错误而静默通过；
  主题目录按 `命令行参数 > NEBULA_THEME_DIR > 仓库根 > 站点主题副本` 依次探测
- `tools/interactions.py` 的复制断言改为读取 `NEBULA_I18N.copied`，不再写死"已复制"

**四次故意注入验证（门禁非假绿）**

| # | 注入内容 | 预期变红的 CI 步骤 | Run |
| --- | --- | --- | --- |
| 1 | 复制超时重新伪装成成功 | Copy semantics（chromium / firefox） | `37711591702` |
| 2 | `share.copyLink` 改回硬编码中文 | i18n static check | `37712114477` |
| 3 | 全站审计静默丢弃分类 term 页 | Release full-site audit（三浏览器） | `37713385742` |
| 4 | 文章内引入真实损坏资源 `/images/not-exist.png` | 死链检查 + 三浏览器 Audit | `37713921224` |

第 4 项附带做了 A/B 对照：把白名单从 pathname 精确匹配放宽为 `endswith` 后，
审计报 `0 问题`（假绿）；换回精确匹配后报 `3 个 broken-image`（正确判红）。

### v1.0.4 — CI 可靠性终验

**测试体系（本轮重点）**

- `tools/_testlib.py`：统一退出码约定 —— 断言失败 / 脚本异常 / 依赖缺失 / 浏览器启动失败 /
  站点不可达 / 零用例执行，一律 `exit 1`；输出机器可读 `TEST-RESULT:` 行
- 修复此前 `audit.py`、`interactions.py`、`verify_search_edge.py`、`verify_baseurl.py`、
  `link_check.py` 只打印 FAIL 却 `exit 0` 的假绿问题（CI 因此无法捕捉真实回归）
- `audit.py` 新增：sitemap 获取失败即失败、浏览器启动失败即失败、`AUDIT_FULL=1` 全站扫描
- CI 新增 `Release full-site audit` job（仅 tag / 手动触发，sitemap 全量页面）
- 新增 `tools/verify_i18n.py`（UI 文案来源校验）、`tools/verify_multisection.py`（多 Section 完整回归）

**i18n 完整性**

- 模板层 UI 文案迁移到 i18n（导航、面包屑、侧栏标题、分页 aria、日期格式、阅读时长、
  归档/列表/词条统计、灯箱 aria、锚点 aria、404、评论、许可证默认文案）
- 修复 `i18n` 占位符 Bug：Hugo 只解析 Go 模板语法 `{{ .n }}`，此前的 `{n}` 会原样输出
  （页面上直接显示 `共 {posts} 篇文章`）
- 菜单支持 `identifier` + `menu.*` 词条，导航随语言切换（`name` 作为回退，旧配置兼容）
- JS 中不再硬编码任何 UI 文案（中文零残留，仅保留英文兜底）

**搜索**

- 分片失败时不再把"索引不全"显示成"没有找到"：新增 `search.partialNoResult` 文案
- 新增深层关键词语义测试：失败分块的正文关键词不命中但明确提示、其他分块关键词仍命中、
  标题/摘要匹配不受影响
- 压测 500 / 1000 / 2000 篇（记录 chunk 数、请求数、体积、耗时、JS 堆），确认 2000 篇下
  single 模式搜索 3.99s、分片模式 1.35s，并给出下一版优化方向

**其他**

- 新增 `tools/normalize_eol.py`、`tools/verify_multisection.py`；测试脚本全部跨平台（无本机硬编码路径）
- `link_check.py` 对"故意断链"的测试夹具改为显式白名单 + 打印，不静默忽略

### v1.0.3

- **CI 覆盖真实浏览器测试**：Playwright（Chromium/Firefox/WebKit）+ 死链 + 功能断言 + 多 baseURL，任一失败即 CI 失败
- **灯箱完整 Focus Trap**：Tab/Shift+Tab 在 dialog 内循环、背景 `inert`、Esc/关闭按钮/遮罩关闭、焦点归还、链接图片走原生跳转
- **分片加载失败可见化**：主索引失败显示错误 + 重试；部分分片失败明确提示且不影响其他结果（不再静默吞掉）
- **搜索 `mode = auto`**：按索引体积自动切换 single/shard；阈值可配置；向后兼容 `shard = true`
- **内容 section 可配置**：`params.content.sections`，不再写死 `posts`
- **i18n 基础架构**：zh-CN / zh-TW / en，JS 文案由模板注入
- **不再要求 `unsafe = true`**：主题核心不依赖 raw HTML
- **图片 Pipeline**：page bundle 图片生成 WebP + `srcset` + 尺寸防 CLS；static 路径不破坏
- **SEO 增强**：WebSite JSON-LD + SearchAction（配合 `?q=` 深链）、og:image 尺寸/alt、hreflang
- **RSS 增强**：作者 / 分类 / updated / `fullContent` 开关
- **Series**：系列名、进度、系列内上下篇（未配置时不输出）
- **文章级显示控制**：`toc` / `comments` / `showDate` / `showLastmod` / `showReadingTime` / `showWordCount` / `showTags` / `showRelated` / `showNav` / `showSeries` / `showShare` / `lightbox`
- **分享**：可选 providers，纯链接实现
- **代码块**：支持 `filename` / `linenos` / `hl_lines`
- 修复：`range` 内数值型外部变量赋值不生效导致的 auto 模式失效；SVG 资源调用 `.Width` 崩溃；`with` 改写上下文导致的 Series 模板错误

### v1.0.2

- 修复索引截断（正文 3000 字后无法搜索）；修复版本兼容声明；JSON-LD 时区；灯箱无障碍；搜索竞态；子目录菜单路径重复；Firefox 首次复制无反馈

### v1.0.1

- 发布前验收修复（构建阻塞、子目录路径、响应式溢出、无障碍等 14 项）

### v1.0.0

- 首个正式版本

## 已知限制

- 未内置 KaTeX / MathJax（数学公式不渲染为公式排版；可在 `layouts/partials/extra-head.html` 自行引入）
- 正文内联链接的点击区域 < 24px（WCAG 2.2 内联豁免，放大 padding 会破坏排版）
- 搜索分片需要 Hugo 0.167+
- 移动端仅在 WebKit 引擎下模拟验证，未做真机测试
- 访问统计与评论为可选外部服务，默认关闭，未与真实服务联调

## 许可证

[MIT](LICENSE) © 2026 tanglx02
