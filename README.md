# Nebula — 一款清爽现代的 Hugo 博客主题

[![Hugo](https://img.shields.io/badge/Hugo-%E2%89%A5%200.128-blue)](https://gohugo.io/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![GitHub](https://img.shields.io/badge/GitHub-tanglx02-black)](https://github.com/tanglx02/hugo-theme-nebula)

一款为技术博客设计的 Hugo 主题：**卡片流首页 + 焦点图、全站模糊搜索、暗色模式、文章目录、代码高亮与一键复制**。零运行时依赖、零外部 CDN 请求，构建后即是一个完全静态的站点。

| 亮色 | 暗色 |
| --- | --- |
| ![首页亮色](docs/screenshots/01-home-light.png) | ![首页暗色](docs/screenshots/04-home-dark.png) |

| 文章页（含目录） | 全站搜索（Ctrl + K） |
| --- | --- |
| ![文章页](docs/screenshots/03-post-dark.png) | ![搜索](docs/screenshots/05-search.png) |

| 归档页 | 移动端 |
| --- | --- |
| ![归档](docs/screenshots/06-archive.png) | ![移动端](docs/screenshots/07-mobile.png) |

## 特性

- 🎴 **焦点图 + 卡片流首页**：置顶文章自动进入顶部焦点区，其余文章以封面卡片呈现
- 🔍 **全站搜索**：`Ctrl + K` 或 `/` 呼出，标题 / 标签 / 正文加权匹配，关键词高亮，键盘上下选择
- 🌗 **暗色模式**：跟随系统偏好，手动切换后记忆选择，无闪烁
- 📑 **文章目录（TOC）**：自动生成，滚动时高亮当前小节
- 💻 **代码块增强**：macOS 风格窗口、语言标签、一键复制，亮暗两套语法配色
- 🖼️ **图片灯箱**：点击正文图片放大查看
- 📱 **完全响应式**：桌面双栏 + 移动端抽屉菜单
- 🗂️ **归档 / 分类 / 标签**：按年份时间线归档，分类、标签总览页
- 💬 **评论系统**：可选接入 giscus / Waline / Twikoo / Disqus
- 🚀 **SEO 就绪**：Open Graph、Twitter Card、JSON-LD、RSS、sitemap、robots.txt
- ⚡ **零依赖**：无 jQuery、无外部字体、无 CDN 请求，CSS/JS 自动压缩并带完整性校验

## 环境要求

- **Hugo extended** ≥ 0.128（extended 版本必需，普通版无法编译）

### 版本兼容

最低版本不是拍脑袋写的：主题在 CI 中用多个真实 Hugo 版本对 `exampleSite` 做生产构建验证（`.github/workflows/ci.yml`）。

| Hugo 版本 | 构建结果 | 说明 |
| --- | --- | --- |
| 0.128.0 | ✅ 通过 | 声明的最低支持版本 |
| 0.162.0 | ✅ 通过 | |
| 0.167.0 | ✅ 通过 | 开发与验收所用版本 |
| latest | ✅ 通过 | CI 每次提交验证 |

> 分片索引（`params.search.shard = true`）依赖较新的 `resources.Publish` 行为，实测 **0.167+ 可用，0.162 及以下不可用**；默认的单一索引文件模式在所有支持版本均可用。

```bash
# Windows (scoop / winget 二选一)
scoop install hugo-extended
winget install Hugo.Hugo.Extended

# macOS
brew install hugo

# Linux (Debian/Ubuntu 可直接下载二进制)
# https://github.com/gohugoio/hugo/releases
```

验证：`hugo version` 输出包含 `extended` 字样。

## 快速开始

### 1. 创建站点

```bash
hugo new site myblog
cd myblog
```

### 2. 安装主题

**方式 A：git submodule（推荐，便于更新）**

```bash
git init
git submodule add https://github.com/tanglx02/hugo-theme-nebula.git themes/hugo-theme-nebula
```

**方式 B：直接克隆**

```bash
git clone https://github.com/tanglx02/hugo-theme-nebula.git themes/hugo-theme-nebula
```

### 3. 配置站点

将站点根目录的 `hugo.toml` 替换为（这是最小可运行配置，完整配置见下方）：

```toml
baseURL = 'https://your-domain.com/'
locale = 'zh-CN'
title = '我的博客'
theme = 'hugo-theme-nebula'
hasCJKLanguage = true

[pagination]
  pagerSize = 8                   # 每页文章数（Hugo >= 0.128 用此项，旧的 paginate 已失效）

[outputs]
  home = ['HTML', 'RSS', 'JSON']   # JSON 用于生成搜索索引，必须保留

[markup]
  [markup.highlight]
    noClasses = false              # 必须为 false，代码高亮配色随主题切换
  [markup.goldmark.renderer]
    unsafe = true

[params]
  author = '你的名字'
  description = '博客描述'

[[menu.main]]
  name = '首页'
  url = '/'
  weight = 1
[[menu.main]]
  name = '文章'
  url = '/posts/'
  weight = 2
```

### 4. 写第一篇文章并预览

```bash
hugo new content posts/hello-world.md
# 编辑 content/posts/hello-world.md，把 draft 改为 false

hugo server -D
# 打开 http://localhost:1313
```

### 5. 试用示例站点

仓库自带 `exampleSite/`（含 7 篇示例文章与全部配置），可以直接预览：

```bash
git clone https://github.com/tanglx02/hugo-theme-nebula.git
cd hugo-theme-nebula
hugo server --source exampleSite --themesDir ../..
```

## 配置参考

以下是 `hugo.toml` 的完整配置项（与 `exampleSite/hugo.toml` 一致）：

```toml
[params]
  author = 'Tanglx'                     # 作者名，显示在卡片与文章页
  subtitle = '记录安全与运维的每一次实践'  # 首页副标题
  description = '站点 SEO 描述'
  avatar = 'img/avatar.png'             # 头像，放在站点 static/ 下
  logoText = 'N'                        # 无 logo 图时导航栏显示的字母
  homePostCount = 8                     # 首页"最新文章"数量
  footerText = 'Keep Learning.'
  license = '本文采用 CC BY-NC-SA 4.0 许可，转载请注明来源。'

  [params.profile]
    bio = '侧边栏个人名片的一句话简介'

  [params.socials]                      # 留空即不显示对应图标
    github = 'https://github.com/yourname'
    email = 'mailto:you@example.com'
    bilibili = 'https://space.bilibili.com/xxx'

  [params.sidebar]
    hotCount = 6                        # 侧边栏"最新文章"条数

  [params.search]
    enable = true                       # 全站搜索开关
    contentLimit = 0                    # 单篇正文索引上限（0 = 不限制，保证全文可搜）
    shard = false                       # true = 正文分片索引（需 Hugo 0.167+）

  [params.views]
    enable = false                      # 卡片上显示"浏览量"占位（配合自建统计）

  [params.busuanzi]
    enable = false                      # 不蒜子访问统计

  # 评论系统：provider 可选 giscus / waline / twikoo / disqus
  [params.comments]
    enable = false
    provider = 'giscus'
    [params.comments.giscus]
      repo = 'yourname/yourrepo'
      repoID = 'R_xxxxxxx'
      category = 'Announcements'
      categoryID = 'DIC_xxxxxxx'
    [params.comments.waline]
      serverURL = 'https://your-waline.example.com'
    [params.comments.twikoo]
      envId = 'https://your-twikoo.example.com'
    [params.comments.disqus]
      shortname = 'your-shortname'
```

**导航菜单**：

```toml
[[menu.main]]
  name = '归档'
  url = '/archives/'
  weight = 5

# 外链菜单项
[[menu.main]]
  name = 'GitHub'
  url = 'https://github.com/yourname'
  weight = 6
  [menu.main.params]
    external = true          # 新标签页打开
```

**归档页**：创建 `content/archives/_index.md`：

```yaml
---
title: "文章归档"
layout: "archive"
---
```

## 写文章

### Front Matter

`hugo new content posts/xxx.md` 会基于主题模板生成：

```yaml
---
title: "文章标题"
date: 2026-10-08
lastmod: 2026-10-08
draft: false
author: ""              # 留空使用站点 author
description: "摘要，显示在列表卡片与搜索结果中"
tags: ["Hugo"]
categories: ["效率工具"]
cover: "/img/cover/xx.png"  # 封面图，放站点 static/img/ 下；留空显示渐变占位
sticky: false           # true 时置顶并进入首页焦点图
toc: true               # 是否显示文章目录
comments: true          # 是否显示评论
---
```

### 内置 Shortcodes

```go-html-template
{{</* notice info */>}}
提示内容，type 可选 info / warning / danger / success
{{</* /notice */>}}

{{</* button "查看源码" "https://github.com/yourname/repo" */>}}
```

## 目录结构

```text
themes/hugo-theme-nebula/
├── archetypes/default.md          # 新文章模板
├── assets/
│   ├── css/main.css               # 全部样式（CSS 变量驱动，改色只需改变量）
│   └── js/main.js                 # 搜索 / 暗色 / 复制 / TOC / 灯箱
├── layouts/
│   ├── _default/
│   │   ├── baseof.html            # 页面骨架
│   │   ├── single.html            # 文章页
│   │   ├── list.html              # 列表页（分类/标签/栏目）
│   │   ├── terms.html             # 分类/标签总览
│   │   ├── archive.html           # 归档页
│   │   ├── index.json             # 搜索索引
│   │   └── _markup/               # Markdown 渲染钩子
│   │       ├── render-codeblock.html   # 代码块（窗口 + 复制）
│   │       ├── render-heading.html     # 标题锚点
│   │       └── render-image.html       # 图片懒加载
│   ├── index.html                 # 首页（焦点图 + 卡片流）
│   ├── 404.html
│   ├── robots.txt
│   └── partials/                  # header / footer / sidebar / comments ...
├── static/img/                    # 默认 favicon 与头像
├── theme.toml
└── exampleSite/                   # 示例站点（含示例文章与完整配置）
```

## 自定义

### 改主题色

编辑 `assets/css/main.css` 顶部的变量即可，全站（含暗色模式）联动：

```css
:root {
  --brand: #409eff;        /* 主色 */
  --brand-dark: #337ecc;   /* 主色 hover */
  --accent: #f56c6c;       /* 强调色（置顶标记等） */
}

html[data-theme="dark"] {
  --brand: #4fa3ff;
}
```

### 注入统计代码 / 自定义字体

在**站点**目录（不是主题目录）创建 `layouts/partials/extra-head.html`，内容会被插入每个页面的 `</head>` 前，主题升级不会丢失：

```html
<script async src="https://analytics.example.com/script.js"></script>
```

同理还有 `layouts/partials/extra-footer.html`。

### 添加自己的头像 / Logo

```text
myblog/
└── static/
    └── img/
        ├── avatar.png     # params.avatar 指向的路径
        └── logo.png       # params.logo = 'img/logo.png' 时替换文字 logo
```

## 部署

### GitHub Pages（Actions 自动构建）

在站点仓库创建 `.github/workflows/deploy.yml`：

```yaml
name: Deploy Hugo
on:
  push:
    branches: [main]
jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          submodules: true
      - uses: peaceiris/actions-hugo@v3
        with:
          hugo-version: '0.167.0'
          extended: true
      - run: hugo --minify --gc
      - uses: peaceiris/actions-gh-pages@v4
        with:
          github_token: ${{ secrets.GITHUB_TOKEN }}
          publish_dir: ./public
```

### 自有服务器

```bash
hugo --minify --gc
rsync -avz --delete public/ user@server:/var/www/blog/
```

## 全文搜索与索引体积

搜索索引由 `layouts/_default/index.json` 在构建期生成，包含每篇文章的 **完整正文纯文本**（做过空白压缩），因此正文任意位置的词都能被检索到 —— 包括几万字长文的末尾。前端对标题 / 标签 / 分类 / 摘要 / 正文分级加权，多个关键词之间是 **AND** 关系。

索引体积参考（未压缩，压缩后通常为 1/3 左右）：

| 内容规模 | index.json |
| --- | --- |
| 25 篇（含 1 篇 1 万字、1 篇 5 万字） | ≈ 218 KB |
| 单篇 5 万字文章 | ≈ 145 KB |

当文章数量很大、单一索引变得过大时，可开启**分片模式**：

```toml
[params.search]
  shard = true    # 需要 Hugo 0.167+
```

此时 `index.json` 只保留元数据（示例中 218 KB → 9 KB），每篇文章的正文单独输出到 `search/<slug>.json`，前端在打开搜索时并发拉取并缓存。两种模式的检索能力完全一致，分片模式适合文章数量多、希望首屏更轻的场景。

## 质量验收

v1.0.2 经过一轮第三方复验，覆盖：

- **构建**：根目录、`/blog/`、`/blog/sub/` 三种 baseURL 的生产构建；每轮修改后均执行 clean build（删除 `public` 与 `resources`）后独立静态服务器验证；草稿 / 未来日期文章在生产构建中正确排除
- **版本兼容**：Hugo 0.128.0 / 0.162.0 / 0.167.0 真实构建（CI 另加 latest）
- **浏览器**：Chromium、Firefox、WebKit(Safari 引擎)、Edge 四套内核
- **视口**：320 / 375 / 390 / 430 / 768 / 1024 / 1440 px，无横向滚动与元素溢出
- **压力数据**：极短 / 1 万字 / 5 万字 / 无分类 / 无标签 / 无封面 / 多封面 / 超长标题 / 超长摘要 / 超长无空格串 / 20 标签 10 分类 / 18 个代码块（未知语言、无语言、带参数）/ 大量图片与链接图片 / 表格嵌套列表引用脚注 / 特殊字符多语言 emoji / 草稿 / 未来 / 极早日期 / 四种时区
- **搜索**：23 项边界测试，含正文深层关键词（3000 / 3500 / 5000 / 8000 / 10000 / 25000 / 48000 字处）、竞态、索引加载失败
- **交互与无障碍**：搜索、主题切换、移动菜单、代码复制、TOC、灯箱（键盘 / 焦点 / Esc / 链接图片）、分页、返回顶部；禁用 JS 后正文与导航仍可读
- **链接与资源**：全站站内链接零死链、无 404 资源、无控制台错误

已知限制：

- 未内置 KaTeX / MathJax，数学公式不会渲染为公式排版（可自行在 `extra-head.html` 中引入）
- 正文内联链接的点击区域小于 24px（属 WCAG 2.2 内联豁免，放大 padding 会破坏正文排版）
- 分片索引需要 Hugo 0.167+；默认的单文件索引模式在所有支持版本可用
- 移动端仅在 WebKit 引擎下模拟验证，未做真机手势测试
- 访问统计与评论为可选外部服务，默认关闭，未接入真实服务验证

## 常见问题

**Q：搜索不工作？**
确认 `hugo.toml` 里有 `[outputs] home = ['HTML', 'RSS', 'JSON']`，构建后站点根目录应存在 `index.json`。

**Q：代码块没有语法颜色？**
确认 `markup.highlight.noClasses = false`。该值若为 true，Hugo 会输出内联样式的亮色配色，无法随暗色模式切换。

**Q：首页焦点图不显示？**
焦点区取最新的 3 篇文章（置顶优先）。给文章加封面：`cover: "/img/xx.png"`（图片放 `static/img/`），无封面时自动使用主题内置渐变占位图。

**Q：如何升级主题？**
submodule 方式：`git submodule update --remote themes/hugo-theme-nebula`。

**Q：部署到 GitHub Pages 子目录（`https://xxx.github.io/repo/`）后图片/CSS 404？**
主题的封面图、菜单、图标路径都经过统一规范化，front matter 里的 `cover` 写 `/img/a.png` 或 `img/a.png` 都可以正确解析。若仍有 404，请确认 `baseURL` 末尾带斜杠且与实际部署路径一致。

## 更新日志

### v1.0.2（第三方复验修复）

**P1 全文搜索**
- 修复：索引对正文使用 `truncate 3000`，导致正文 3000 字之后的内容完全无法搜索。现收录完整正文（空白压缩），并新增 `contentLimit` 可选上限与 `shard` 分片模式（218 KB → 9 KB）。CI 内置"深层关键词必须可检索"的断言，防止回归。

**P1 版本兼容**
- 修复：主题声明支持 0.128，但代码块渲染依赖 0.162 才有的 `type` 选项。现已消除该依赖（未知语言改为零 API 依赖的纯文本输出），并在 CI 中用 0.128 / 0.162 / 0.167 / latest 四个版本实测构建。

**P2 JSON-LD 时间**
- 修复：`datePublished` / `dateModified` 时区被硬编码为 `+08:00`，现使用日期对象自身的偏移（RFC3339）。UTC、+08:00、-05:00、+05:30 四种时区实测准确。

**P2 灯箱无障碍**
- 新增：`role="dialog"` / `aria-modal` / 可访问名称 / 关闭按钮；键盘可聚焦与 Enter 打开；打开后焦点移入、Esc 关闭、关闭后焦点归还触发图片。
- 修复：Markdown 中 `[![img](x)](url)` 的图片不再被灯箱拦截点击，链接行为保持正常。

**P2/P5 搜索健壮性**
- 修复：打开搜索框后立即输入时的竞态（索引未就绪会误报"无结果"）——现在先等待索引，加载中显示明确状态，加载完成后自动补渲染。
- 新增：索引加载失败给出明确错误提示；输入防抖；正文命中时从匹配位置截取摘要片段。
- 新增：23 项搜索边界测试（中英文 / 大小写 / 数字 / emoji / 正则特殊字符 / 多词 AND / 空搜索 / 无结果 / 结果上限 / 索引失败 / 延迟竞态）。

**子目录部署**
- 修复：`[[menu.main]] url` 已被 Hugo 解析为带 basePath 的路径，转换后出现 `/blog/blog/posts/` 重复路径。现检测已含 basePath 的路径并原样返回。
- 验证：根 / `/blog/` / `/blog/sub/` 三种 baseURL 下 81 项检查全部通过（资源、favicon、RSS、sitemap、robots、index.json、菜单、Logo、面包屑、分类、标签、分页、canonical、og:url、内部链接可达性）。

### v1.0.1（发布前验收修复）

- 修复：无标签 / 无分类文章会导致构建失败
- 修复：Markdown 图片渲染钩子在 Hugo 0.167 下字段不兼容导致构建失败
- 修复：子目录部署时封面图、菜单、图标路径缺少 basePath 造成 404
- 修复：面包屑与品牌链接使用绝对域名，子目录部署时跳出站点
- 修复：超长不可断文本（长 URL / 长单词）撑破 grid 容器引发整页横向滚动
- 修复：Firefox 下复制代码时按钮无反馈
- 修复：缺少 `favicon.ico`；补充 SVG + ICO 双图标
- 优化：相关文章改为同分类优先
- 优化：robots.txt 不再屏蔽分类 / 标签页
- 优化：超长标题、目录项、摘要的行数限制与断词
- 无障碍：焦点可见轮廓、`prefers-reduced-motion`、触屏点击区域 ≥ 24px
- 移除：灯箱占位图空 `src`（避免多余请求）

### v1.0.0

首个正式版本。

## 开发

```bash
# 克隆后直接跑示例站
hugo server --source exampleSite --themesDir ../..

# 重新生成示例封面图（Python 脚本，可选）
python tools/gen_covers.py
```

欢迎提 Issue 和 PR。

## 许可证

[MIT](LICENSE) © 2026 tanglx02
