# Nebula — 一款清爽现代的 Hugo 博客主题

[![CI](https://github.com/tanglx02/hugo-theme-nebula/actions/workflows/ci.yml/badge.svg)](https://github.com/tanglx02/hugo-theme-nebula/actions/workflows/ci.yml)
[![Hugo](https://img.shields.io/badge/Hugo-%E2%89%A5%200.128-blue)](https://gohugo.io/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

面向技术博客的 Hugo 主题：**卡片流首页 + 焦点图、完整全文搜索、暗色模式、文章目录、图片 Pipeline、系列文章、代码高亮与一键复制**。零运行时依赖、零外部 CDN 请求。

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
- 🔗 **分享**：可选开关（复制链接 / X / Telegram / Facebook / Reddit / 微博 / 微信）
- 📡 **RSS 增强**：标题 / 描述 / 作者 / 分类 / pubDate / updated，支持 `fullContent` 全文输出
- 🔎 **SEO**：canonical、OG、Twitter Card、BlogPosting + WebSite JSON-LD、SearchAction、hreflang、sitemap、robots
- ♿ **无障碍**：键盘可达、焦点可见、`prefers-reduced-motion`、触屏点击区 ≥ 24px
- ⚡ **零依赖**：无 jQuery / 无外部字体 / 无 CDN

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
| `shard` | 主索引只含元数据，正文拆到 `search/<slug>.json`，前端并发加载 | 大型站点 |
| `auto`（默认） | 按正文总体积自动在 single / shard 之间选择（阈值 `autoThreshold`） | 推荐 |

实测数据（每篇约 3000 字，`auto` 默认阈值 500KB）：

| 文章数 | single 主索引 | auto 结果 |
| --- | --- | --- |
| 25 篇 | 225 KB | 单索引（未超阈值） |
| 100 篇 | 899 KB | 分片 |
| 300 篇 | 2.6 MB | 分片 |
| 500 篇 | 4.4 MB | 分片（主索引约 10 KB + 500 个分片） |

搜索索引加载失败时会有明确提示：主索引失败显示错误并可**重试**；部分分片失败时提示"部分索引加载失败（N 篇未能加载）"且仍返回其他文章的结果（不会误报"没有找到"）。

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

主题内置 `i18n/zh-CN.yaml`、`zh-TW.yaml`、`en.yaml`。单语言站点无需配置；多语言站点示例：

```toml
defaultContentLanguage = 'zh-cn'
[languages]
  [languages.zh-cn]
    languageName = '简体中文'
    weight = 1
    [languages.zh-cn.params]
      description = '中文站点描述'
  [languages.en]
    languageName = 'English'
    weight = 2
```

多语言站点会自动输出 `hreflang` 标签。JS 中的提示文案通过模板注入（`window.NEBULA_I18N`），不在脚本里硬编码。

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

CI（`.github/workflows/ci.yml`）在 GitHub Actions 上**真实运行**以下检查，任一失败即 CI 失败：

| Job | 内容 |
| --- | --- |
| Build (0.128 / 0.162 / 0.167 / latest) | 生成压力数据 → 生产构建 → 产物校验 → 搜索索引完整性 → 草稿/未来排除 → livereload 检查 |
| Sub-directory baseURL | `/blog/` 构建 + 断言无越界路径、无 basePath 重复 |
| Static checks | 站内死链、索引完整性、功能断言（图片/Series/RSS/SEO/代码块/i18n）、多 Section 构建、auto 阈值分片 |
| Browser tests (chromium / firefox / webkit) | 响应式审计（320–1440）、交互、灯箱 Focus Trap、搜索边界与竞态、分片失败处理、三种 baseURL 部署 |

本地运行（Windows 需设置 `HUGO_BIN`，本地有代理时设置 `PLAYWRIGHT_PROXY`）：

```bash
export HUGO_BIN=/path/to/hugo          # Linux/macOS 可省略（默认 hugo）
python3 tools/serve.py public 8080 &   # 独立静态服务器（勿用 hugo server 产物测试）

python3 tools/link_check.py public                 # 死链
python3 tools/check_index.py public/index.json     # 索引完整性
python3 tools/check_features.py public             # 功能断言
AUDIT_BROWSERS=chromium python3 tools/audit.py http://127.0.0.1:8080
PW_BROWSERS=chromium python3 tools/interactions.py http://127.0.0.1:8080
python3 tools/verify_lightbox.py http://127.0.0.1:8080 chromium
python3 tools/verify_search_edge.py http://127.0.0.1:8080
python3 tools/verify_search_shard.py http://127.0.0.1:8090 chromium
python3 tools/bench_index.py 25,100,300,500        # 索引规模压测
```

## 更新日志

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
