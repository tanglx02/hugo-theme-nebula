---
title: "内容组件：文件树、徽标、按钮与折叠块"
date: 2026-10-03
lastmod: 2026-10-03
description: "技术内容组件演示：filetree 文件树、badge 徽标、button 按钮（含 URL scheme 安全校验）与 details 折叠块。全部零 JavaScript、零第三方请求，路径特殊字符安全转义。"
tags: ["文件树", "徽标", "按钮", "折叠块", "技术写作"]
categories: ["功能演示"]
toc: true
---

本页演示**功能三（技术内容组件）**的第三组：**文件树**、**徽标**、**按钮**与**折叠块**。

四个组件都遵循同一条底线：**零 JavaScript、零第三方请求**，
输出的是语义化 HTML，样式全部由主题自有的 CSS 承担。

## 一、文件树：把目录结构原样画出来

用 Markdown 直接写目录树有三个绕不开的坑：4 空格缩进被当成代码块、
连续行被合并成一个段落、行首的连续空格被 HTML 折叠。
`filetree` 短代码把这些交给你不管，只保证一件事——**你写什么，就显示什么**。

{{< filetree "Hugo 站点典型结构" >}}
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

标题是可选的第一参数；不写标题，就只显示树本身：

{{< filetree >}}
theme/
├── layouts/
└── assets/
{{< /filetree >}}

### 文件名里的特殊字符是安全的

这份"路径安全"不是顺带一提，而是一条明确的设计约束。
下面这棵树刻意塞进了 HTML 与 Markdown 的敏感字符，
它们在产物里**要么原样保留、要么被转义成实体**，
绝不会变成标签、也绝不会被当成 Markdown 标记解析：

{{< filetree "特殊文件名" >}}
src/
├── a&b.ts
├── <x>.ts
├── "q" 'r' `s`.ts
└── [index].md
{{< /filetree >}}

反引号、方括号、`&`、尖括号、引号都逐字保留。
这意味着就算有人把一段 `<script>` 之类的文本写进文件名，
输出里也只会出现实体字符，不会产生可执行的标签。

## 二、徽标：行内小标签

徽标适合标注版本号、平台、状态、语言这类**短标记**。
它有三种等价写法，以及六个内置变体：

{{< badge "v1.0.9" >}} 默认样式

{{< badge "稳定" "success" >}} 指定变体

{{< badge "已弃用" "danger" >}} 具名参数

{{< badge "实验中" "warning" >}} 警告色

{{< badge "信息" "info" >}} 信息色

{{< badge "次要" "muted" >}} 弱化色

可用的变体固定为六个：
`default`、`info`、`success`、`warning`、`danger`、`muted`。

| 变体 | 写法 | 典型用途 |
| --- | --- | --- |
| `default` | `{{</* badge "v1.0" */>}}` | 中性标记、版本号 |
| `info` | `{{</* badge "信息" "info" */>}}` | 补充说明 |
| `success` | `{{</* badge "稳定" "success" */>}}` | 通过、已发布 |
| `warning` | `{{</* badge "实验中" "warning" */>}}` | 注意、未定型 |
| `danger` | `{{</* badge "已弃用" "danger" */>}}` | 破坏性、不再支持 |
| `muted` | `{{</* badge "归档" "muted" */>}}` | 弱化、次要信息 |

**未知变体会静默回退到 `default`**，而不是让构建失败——
内容作者的笔误不应该中断整站构建，这与提示块（`[!BOGUS]` 退化为普通引用）的约定一致。
但也正因如此，变体值会被严格限制在白名单内：
任何越界值都会被归一为 `default`，从根上断掉借 class 属性注入脚本的路径。

## 三、按钮：正文里的行动号召

按钮用于"下载、外链、邮件、跳转"这类明确的下一步动作：

{{< button "查看文档" "/posts/" >}}
{{< button "GitHub 主页" "https://github.com/tanglx02" >}}
{{< button "邮箱联系" "mailto:tanglx@aliyun.com" >}}

### URL scheme 安全校验

按钮的链接**不是原样输出**，而是先过一道 scheme 白名单：

- **放行**：`http://`、`https://`、协议相对 `//`、`mailto:`、`tel:`，
  以及**不含 scheme** 的相对路径 / 根路径 / 锚点（如 `posts/x/`、`/about/`、`#sec`）；
- **拒绝**：`javascript:`、`vbscript:`、`data:`、`file:`、`ftp:` 等一切其它 scheme，
  以及空值。

被判为不安全的链接**不会输出 `<a>`**，而是渲染成不可点击的占位块，
并带上可读的提示（文案走 i18n，随语言站点切换）：

{{< button "这个按钮会被拦截" "javascript:alert(1)" >}}
{{< button "这个也会" "data:text/html,<script>alert(1)</script>" >}}

这么做的原因很直接：`href="{{ .Get 1 }}"` 这类直出写法，
虽然 Hugo 的模板引擎会给 URL 上下文加一道过滤，但那道过滤规则随 Go 版本变化、
也无法表达"只允许这几个 scheme"。**把判定放在模板层**，才能在构建产物里直接断言——
等真的扫到产物里出现 `javascript:`，就已经晚了。

另外还要防一种经典绕过：浏览器会忽略 `java<TAB>script:` 里的空白字符。
因此判定前会先剥掉所有空白与控制字符再比对，`java` + 制表符 + `script:` 同样会被拦下。

### 链接的打开方式与站内路径

- **外链**（`http/https/协议相对`）自动带上 `target="_blank"` 与 `rel="noopener"`，
  在新标签页打开且不留 `window.opener` 隐患；
- **`mailto:` / `tel:`** 与**站内链接**不加 `target`——
  邮件、电话交给系统处理，站内跳转保持同窗口；
- 站内相对路径会统一规范化，因此在**子目录 baseURL**（如 `baseURL = '.../blog/'`）
  部署下同样指向正确。

## 四、折叠块：可选的补充说明

折叠块用来收纳"想看再看"的补充内容——推导过程、边界情况、次要说明。
它基于原生 `<details>` / `<summary>`，**零 JavaScript**，键盘与读屏天然可用：

{{< details "为什么默认是折叠的？" >}}
长文里如果每个补充说明都展开，正文会被大量的旁枝打断阅读节奏。
把次要内容折叠起来，默认只留一句话提示，
读者可以按需展开，主线叙述保持紧凑。
{{< /details >}}

需要默认展开时用 `open` 参数——注意此时**必须全部用具名参数**：

{{< details title="我是默认展开的" open="true" >}}
这是 `open="true"` 的效果，进入页面时就已经展开。
{{< /details >}}

而"位置参数 + 具名参数"混用的写法会**直接构建失败**：

```
{{</* details "标题" open="true" */>}}
```

这不只是本组件的限制，而是 Hugo 对所有 shortcode 的硬性规则，
因此本页示例统一使用 `title=` + `open=` 的具名写法。
（顺带一提：这段示例本身用了 Hugo 的转义写法 `{{</* */>}}` 才能被当成代码显示——
否则它会在构建时被真的执行。）

折叠块里可以放列表、代码块、甚至其它组件：

{{< details "折叠块里放代码" >}}
```bash
hugo --gc --minify
```
{{< /details >}}

> 补充：为什么这里要用 shortcode 而不是直接写 `<details>`？
> 因为主题默认 `unsafe = false`（安全默认值），直接写在 Markdown 里的裸
> `<details>` 会被 goldmark 当作原始 HTML **整段丢弃**，只在构建日志留下一行
> `WARN Raw HTML omitted`——正文静默消失，构建却成功。改用 shortcode 后，
> 内容走正常的 Markdown 渲染管线，既完整又安全。

## 五、可嵌套

这四个组件可以和**标签页**、**步骤**互相嵌套。
嵌套时子组件不会直接把 HTML 交给父级，而是以占位符形式返回，
避免父级的 Markdown 渲染把原始 HTML 丢掉：

{{< tabs >}}
{{< tab "目录一览" >}}

{{< filetree "嵌套在标签页里" >}}
project/
├── src/
└── tests/
{{< /filetree >}}

{{< /tab >}}
{{< tab "折叠说明" >}}

{{< details "标签页内的折叠块" >}}
这里同时演示了"标签页 → 折叠块"的嵌套。
{{< /details >}}

{{< /tab >}}
{{< /tabs >}}

## 六、没有 JavaScript 会怎样

答案是：**什么都不会少**。

这四个组件完全是服务端渲染 + CSS，
禁用 JavaScript 不会影响它们的显示、展开或点击（原生元素自带交互）。
这也是它们与标签页、步骤共享的同一条设计约束。

## 七、打印与版本兼容

- **打印**：折叠块在打印时会**自动展开**正文（否则内容会漏印）；
  按钮的交互样式会被简化，徽标与文件树正常输出。
- **版本兼容**：四个组件全部由 shortcode 与 CSS 实现，
  在主题支持的全部 Hugo 版本（0.128.0 起）上产物结构一致，
  CI 对五个版本逐版本断言结构签名完全相同。