---
title: "用 Hugo 从零搭建技术博客：一套可维护的工作流"
date: 2026-08-08
lastmod: 2026-08-08
description: "为什么选 Hugo、目录怎么组织、怎么写主题模板、怎么自动化部署，以及内容沉淀的一些习惯建议。"
author: "Tanglx"
tags: ["Hugo", "博客", "效率"]
categories: ["效率工具"]
cover: "/img/cover/hugo.svg"
toc: true
---

折腾过 WordPress、Typecho、Hexo，最后停在 Hugo。原因很实在：**快、纯静态、无数据库、单二进制**。这篇把我的工作流完整记下来。

## 为什么是 Hugo

| 方案 | 构建速度 | 依赖 | 痛点 |
| --- | --- | --- | --- |
| WordPress | 动态 | PHP + MySQL | 慢、要打补丁、备份麻烦 |
| Hexo | 中等 | Node.js | 文章多了以后构建很慢 |
| **Hugo** | 极快 | 单个二进制 | 模板语法需要适应 |
| Gatsby | 慢 | Node + 大量依赖 | 依赖地狱 |

一个几百篇的站点，Hugo 全量构建通常在 1 秒以内：

```bash
hugo --minify
# Total in 412 ms
```

## 目录组织

我的习惯是按年份分目录 + 文件名带序号：

```text
content/
├── posts/
│   ├── 2025/
│   │   ├── 01-xxx.md
│   │   └── 02-yyy.md
│   └── 2026/
│       ├── 01-aaa.md
│       └── 02-bbb.md
├── about/
│   └── index.md
└── archives/
    └── _index.md
```

`_index.md` 是 section 首页，`index.md` 是普通页面，这个区别刚上手容易搞混。

## Front Matter 约定

```yaml
---
title: "文章标题"
date: 2026-08-08
lastmod: 2026-08-08
description: "一句话摘要，会用于列表页和 SEO"
tags: ["Hugo", "博客"]
categories: ["效率工具"]
cover: "/img/cover/xxx.png"
sticky: false
toc: true
---
```

用 `archetypes/default.md` 固化模板，`hugo new posts/xxx.md` 直接生成：

```bash
hugo new posts/2026/03-new-post.md
```

## 主题开发要点

自己写主题其实不难，记住这几个核心概念就够：

1. **baseof.html** 是骨架，用 `block "main"` 占位
2. **模板查找顺序**：`layouts/xxx.html` → `themes/xxx/layouts/_default/xxx.html`
3. **partials** 是可复用片段，用 `partial "name.html" .` 调用
4. **资源管道**处理 CSS/JS：

```go-html-template
{{ $css := resources.Get "css/main.css" | minify | fingerprint }}
<link rel="stylesheet" href="{{ $css.RelPermalink }}" integrity="{{ $css.Data.Integrity }}">
```

5. **Markup Render Hook** 可以接管代码块、标题、图片的渲染：

```text
layouts/_default/_markup/
├── render-codeblock.html   # 代码块加复制按钮
├── render-heading.html     # 标题加锚点
└── render-image.html       # 图片懒加载
```

6. **搜索索引**用 JSON 输出：

```toml
[outputs]
  home = ["HTML", "RSS", "JSON"]
```

```go-html-template
{{/* layouts/_default/index.json */}}
{{- $index := slice -}}
{{- range where site.RegularPages "Section" "posts" -}}
  {{- $index = $index | append (dict "title" .Title "url" .RelPermalink) -}}
{{- end -}}
{{ $index | jsonify }}
```

## 本地预览与构建

```bash
# 预览（含草稿）
hugo server -D --bind 0.0.0.0 --port 1313

# 生产构建
hugo --minify --gc

# 检查即将发布的草稿
hugo list drafts
```

## 自动化部署

GitHub Actions 推送到 Pages：

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
          hugo-version: '0.128.0'
          extended: true
      - run: hugo --minify
      - uses: peaceiris/actions-gh-pages@v4
        with:
          github_token: ${{ secrets.GITHUB_TOKEN }}
          publish_dir: ./public
```

{{< notice info >}}
自建服务器更简单：本地 `hugo --minify` 后 `rsync -avz --delete public/ user@host:/var/www/blog/` 就行。静态站点的好处就是部署方式随便挑。
{{< /notice >}}

## 写内容的习惯

工具只是工具，真正难的是持续写。我的几条经验：

- ** troubleshooting 当场记**：解决问题时的报错信息、命令、思路，事后再补必丢细节
- **README 式写作**：先写「我遇到什么问题 → 怎么解决的 → 为什么」，再润色
- **代码块要可复制**：贴命令时把变量替换成真实值，别让读者猜
- **配图统一风格**：截图、架构图保持统一的配色和字体

## 小结

Hugo 的学习曲线主要在模板语法，但一旦跨过去，后面维护成本极低。我现在写完一篇 `git push` 就完事，剩下的交给 CI。
