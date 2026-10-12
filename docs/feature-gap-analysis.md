# Nebula 功能差距分析（功能完善与产品定型阶段）

> **本文档的产生方式**：逐项读取并核对当前代码（`layouts/**`、`assets/**`、`i18n/**`、
> `exampleSite/**`、`tools/**`、`.github/workflows/ci.yml`），**不以 README 是否提及**作为
> 功能存在与否的判据。凡标注"已实现"的条目，均给出文件与具体位置；凡标注"缺失"的条目，
> 均给出已执行的检索证据。

## 0. 基线核对（先核对再定差距）

| 项 | 值 |
| --- | --- |
| 仓库根 | `E:/Work/项目开发/hugo博客开发/hugo-theme-nebula` |
| 分析时分支 | `fix/third-party-audit-v1.0.9-r2` |
| 分析时 HEAD | `4bbda0bba04ce9947eb7aa86298846335ab388a7` |
| 工作区状态 | `git status --porcelain` 为空（干净） |
| `v1.0.9` 标签指向 | `bc152c8807325092ead7aa5f8125e0cb27bf84df`（未移动） |
| 上游跟踪 | `origin/fix/third-party-audit-v1.0.9-r2` |
| 功能分支 | `feat/theme-feature-completion`（从 `4bbda0b` 创建，本阶段所有提交均在此分支） |

### 第二轮修复成果（本阶段必须保留，不得覆盖或丢失）

| 编号 | 内容 | 落点 |
| --- | --- | --- |
| BUG-R2-003 | 头像 URL 为空/危险 scheme/解析为站点根时回退，不再渲染 `<img src="/">` | `layouts/partials/util/avatar-url.html`、`post-card.html`、`sidebar.html` |
| BUG-R2-001 | `contentLimit` 按 **rune** 截断，中文正文不再 `slicestr` 越界 panic | `layouts/partials/util/slice-runes.html`、`_default/index.json` |
| BUG-R2-002 | 0.166.0 能力探测（`resources.Publish`）改用数值版本比较，`cond` 不再触发旧版本字段访问错误 | `_default/index.json`、`partials/util/locale.html` |
| BUG-R2-004 | 弹窗关闭焦点归还加 `preventScroll`，不再把页面滚回顶部 | `assets/js/main.js` `createModalA11y.close()` |
| BUG-R2-005 | JSON-LD `author` 无作者时**省略字段**，不输出 `"name": null` | `layouts/partials/head.html` |
| TEST-DEFECT-R2-001~009 | 测试假绿与偶发假红修复（含滚动断言 instant 回顶 + 相对位移判定） | `tools/_testlib.py`、`tools/verify_modal_scroll.py`、`tools/repeat_check.py` |

> 本阶段新增代码**不得**破坏以上任一项；`tools/check_html_quality.py`（`zero-date` /
> JSON-LD）、`check_index.py`（正文完整性）、`verify_contrast.py`、`verify_modal_scroll.py`、
> `security_baseline.py` 等门禁断言**不得降低**。

---

## 1. 已实现功能（代码核实，本轮必须保持兼容）

### 1.1 首页与列表

| 功能 | 状态 | 证据 |
| --- | --- | --- |
| 卡片流首页（焦点区 hero + 卡片流 + 侧栏） | ✅ 已实现 | `layouts/index.html`；`layouts/partials/post-card.html` |
| 置顶文章进入焦点区（`sticky`） | ✅ 已实现 | `index.html:5-6` `$pinned := where $posts "Params.sticky" true` |
| 首页文章数量配置 | ✅ 已实现 | `site.Params.homePostCount | default 8` |
| 列表页 + 分页 | ✅ 已实现 | `_default/list.html`、`partials/pagination.html`（首尾 + 当前±2 + 省略号） |
| 归档页（含**无日期**单独分组） | ✅ 已实现 | `_default/archive.html`（`$dated` / `$undated` 分组，避免 "0001 年"） |
| 分类/标签词条页 | ✅ 已实现 | `_default/terms.html`、`_default/list.html` taxonomy 分支 |
| 404 页 | ✅ 已实现 | `layouts/404.html` |
| alias 页 | ✅ 已实现 | `layouts/alias.html`（另有 `check_alias_pages.py` 独立静态验证） |

### 1.2 阅读体验（现状）

| 功能 | 状态 | 证据 / 说明 |
| --- | --- | --- |
| 文章目录 TOC（滚动高亮） | ✅ 已实现 | `single.html:148-163`；`main.js` `updateTOC()`（`offsetTop <= scrollY+120`） |
| 面包屑 | ✅ 已实现 | `single.html:25-35`（首页 / 分类 / 正文）；`list.html`、`archive.html`、`terms.html` 亦有 |
| 上下篇导航 | ✅ 已实现 | `single.html:99-114`（`PrevInSection` / `NextInSection`） |
| 相关文章（同分类优先 + 最新补齐） | ✅ 已实现 | `single.html:120-141` |
| 系列文章卡片（进度 + 系列内上下篇） | ✅ 已实现 | `partials/series.html` |
| 阅读时长 / 字数 | ✅ 已实现 | `single.html:56-69`（空正文不显示 0 分钟 / 0 字） |
| **阅读进度条** | ⚠️ 已实现但**不可配置、算法不符阅读区** | `baseof.html:7` `#progressBar`；`main.js:64-73`；按**整页** `scrollHeight - innerHeight` 计算，且**始终启用**、无 `params` 开关、无文章级开关 |
| **返回顶部按钮** | ⚠️ 已实现但**不可配置** | `baseof.html:18-20` `#toTop`；`main.js:70`（`st>400` 显示）、`main.js:74-76`（smooth 回顶）；**始终启用**、无开关 |
| 文章级显示开关 | ✅ 已实现 | `single.html:5-14` `showDate`/`showLastmod`/`showReadingTime`/`showWordCount`/`showTags`/`showRelated`/`showShare`/`showSeries`/`showNav`/`comments`/`toc`/`lightbox` |
| 专注阅读模式 | ❌ **缺失** | 检索 `focus-mode|focusMode|zen-mode|zenMode` → 无结果 |
| 打印样式 | ❌ **缺失** | 检索 `@media print|@page` in `assets/css/main.css` → 无结果 |

### 1.3 技术内容表达（现状）

| 功能 | 状态 | 证据 / 说明 |
| --- | --- | --- |
| 代码块（mac 窗口 / 语言标签 / `filename` / `linenos` / `hl_lines`） | ✅ 已实现 | `_default/_markup/render-codeblock.html`；未知语言降级纯文本 |
| 一键复制（统一实现，绝不算"超时成功"） | ✅ 已实现 | `main.js` `copyText()`（1200ms 超时 → fallback，`execCommand` 非 `true` 即失败） |
| 标题锚点 | ✅ 已实现 | `_default/_markup/render-heading.html` |
| 图片 Pipeline（page bundle → WebP srcset/sizes/width/height） | ✅ 已实现 | `_default/_markup/render-image.html`；`params.images` 可配置 |
| 灯箱（dialog + Focus Trap + 键盘 + 链接图片放行） | ✅ 已实现 | `baseof.html:22-31`；`main.js` `createModalA11y` |
| Markdown 提示块 | ⚠️ **部分实现**：仅 `shortcode` 且类型不匹配 | `layouts/shortcodes/notice.html` 支持 `info`/`warning`/`danger`/`success`；**不**支持 NOTE/TIP/IMPORTANT/WARNING/CAUTION 五类，**不**支持纯 Markdown `> [!NOTE]` 语法（无 alert Render Hook） |
| 按钮 shortcode | ✅ 已实现 | `layouts/shortcodes/button.html`（含 `http` 前缀 external 处理） |
| 标签页（tabs） | ❌ **缺失** | 检索 `layouts/` 内 `tabs` → 无结果 |
| 步骤（steps） | ❌ **缺失** | 检索 `layouts/` 内 `steps` → 无结果 |
| 文件树（filetree） | ❌ **缺失** | 检索 `filetree|file-tree` → 无结果 |
| 徽标（badge） | ❌ **缺失** | 检索 `layouts/` 内 `badge` → 仅 `index.html:18` 的 `hero-badges`（无关） |
| 图片画廊（gallery） | ❌ **缺失** | 检索 `layouts/` 内 `gallery` → 无结果 |
| Mermaid | ❌ **缺失** | 检索 `mermaid` → 无结果 |
| KaTeX / MathJax | ❌ **缺失**（README「已知限制」亦声明未内置） | 检索 `katex|mathjax` → 无结果 |

### 1.4 搜索

| 功能 | 状态 | 证据 |
| --- | --- | --- |
| 完整全文搜索（正文任意位置） | ✅ 已实现 | `_default/index.json`（`$content := .Plain`，仅压缩空白，不截断） |
| 三种索引模式 `auto`/`single`/`shard` | ✅ 已实现 | `index.json`；`auto` 按 `autoThreshold` 自动选择 |
| 分片按**体积**分块（非按文章） | ✅ 已实现 | `index.json:118-144` `chunkSize` 累积 |
| 版本能力回退（<0.166 auto 回退单文件；显式 shard 报错） | ✅ 已实现 | `index.json:104-112` |
| 前端竞态保护 / 加载态 / 失败重试 / 分片部分失败提示 | ✅ 已实现 | `main.js` `loadIndex()`/`render()`（token 丢弃过期渲染）；`search-modal.html` `#searchStatus`/`#searchRetry` |
| 搜索链接 scheme 白名单（SEC-01） | ✅ 已实现 | `main.js` `safeHref()` |
| 高亮实体安全（`& < > " '`） | ✅ 已实现 | `main.js` `highlight()`（先 `esc` 后正则）；`verify_search_highlight.py` |
| `Ctrl+K` / `/` / `?q=` 深链 | ✅ 已实现 | `main.js` |
| 日期 UI 本地化（`dateDisplay` 构建期生成） | ✅ 已实现 | `index.json`；`main.js` `dateLabel()`（不重复实现格式化） |

### 1.5 外观与主题

| 功能 | 状态 | 证据 |
| --- | --- | --- |
| 暗色模式（跟随系统 + 手动 + 记忆 + 防 FOUC） | ✅ 已实现 | `head.html:19-28`；`main.js:15-31`；CSS `html[data-theme="dark"]` |
| 设计 token（`--brand`/`--brand-solid`/`--brand-ink`/`--accent-ink`/`--text-muted`/`--radius`/`--wrap`…） | ✅ 已实现 | `assets/css/main.css:14-65`（浅深两套） |
| 对比度 AA 契约（文字 token 分工） | ✅ 已实现 | `main.css:5-11` 注释 + `verify_contrast.py` |
| `prefers-reduced-motion` 降级 | ✅ 已实现 | `main.css:116-123` |
| 响应式断点（头部 900px 契约 + ≤900px 触控目标 44×44） | ✅ 已实现 | `main.css:1342`；`check_responsive_overflow.py` |
| 强调色方案（内置多套可选） | ❌ **缺失** | 无 `params.appearance`/`accent` 相关模板注入；`--brand` 硬编码在 CSS |
| 正文宽度可配置 | ❌ **缺失** | `--wrap: 1220px` 为固定值，无模板注入 |
| 阅读字体 / 行高可配置 | ❌ **缺失** | `body { font-size:15.5px; line-height:1.75 }` 固定 |
| 卡片密度 / 列表布局可配置 | ❌ **缺失** | 无 `params.list` 相关注入 |
| 不同模式（浅/深）边距排版差异 | ❌ **缺失** | 深色仅换颜色 token，不调间距 |

### 1.6 作者与编辑工作流

| 功能 | 状态 | 证据 |
| --- | --- | --- |
| 单作者（`Params.author` → `site.Params.author` 回退） | ✅ 已实现 | `single.html:95`、`head.html:16`、`index.xml:32-33`、`post-card.html:4` |
| 站点级作者画像（头像 / 简介 / 统计 / 社交） | ✅ 已实现 | `partials/sidebar.html:1-44` |
| **多作者（Front Matter 作者列表）** | ❌ **缺失** | 检索 `Params.authors` → 无结果；仅单个字符串 |
| **独立作者档案页** | ❌ **缺失** | 无 `taxonomies.authors` 或作者页模板 |
| **编辑此页入口** | ❌ **缺失** | 检索 `editUrl|edit_url|editLink|edit-page|EditThisPage` → 无结果 |
| **外链文章类型** | ❌ **缺失** | 检索 `externalUrl|params.external|external_url|linkUrl` → 仅 `header.html`/`footer.html` 的**菜单项** external，与文章无关 |

### 1.7 导航与 SEO / 订阅 / 评论

| 功能 | 状态 | 证据 |
| --- | --- | --- |
| 菜单（`main`/`nav`/`footer` 三组，支持 `external` 新标签） | ✅ 已实现 | `header.html:12-22`、`footer.html:11-17` |
| 菜单跟随语言（`identifier` → `menu.*` 词条，`name` 回退） | ✅ 已实现 | `partials/util/menu-label.html` |
| **嵌套（多级）菜单** | ❌ **缺失** | 检索 `header.html` 内 `children|HasChildren` → 无结果；仅平铺一级 |
| canonical / OG / Twitter Card | ✅ 已实现 | `head.html:17,30-53` |
| JSON-LD（WebSite + SearchAction + BlogPosting） | ✅ 已实现 | `head.html:83-125`（整体 `jsonify` + `safeJS`，避免二次编码） |
| hreflang / `og:locale:alternate` | ✅ 已实现 | `head.html:37-64`（走 `util/locale.html`） |
| RSS（作者 / 分类 / updated / `fullContent` / `limit`） | ✅ 已实现 | `layouts/index.xml` |
| sitemap / robots | ✅ 已实现 | `enableRobotsTXT`、`layouts/robots.txt` |
| 分享（7 providers，纯链接无第三方脚本） | ✅ 已实现 | `partials/share.html` |
| 评论（giscus/waline/twikoo/disqus，locale 跟随站点） | ✅ 已实现 | `partials/comments.html` |
| 浏览量（views / busuanzi 可选） | ✅ 已实现 | `post-card.html:62-67`；`scripts.html:8-11` |
| 多 Section（`params.content.sections`） | ✅ 已实现 | `index.html`、`single.html`、`index.json`、`index.xml` 均使用 |

### 1.8 工程与质量基建

| 项 | 状态 | 证据 |
| --- | --- | --- |
| i18n 三语言（zh-CN / zh-TW / en） | ✅ 已实现 | `i18n/*.yaml` |
| UI 文案零硬编码门禁 | ✅ 已实现 | `tools/check_i18n_hardcode.py` |
| 测试退出码统一（失败即 exit 1） | ✅ 已实现 | `tools/_testlib.py` `Harness.finish()` |
| 临时目录边界约束 | ✅ 已实现 | `tools/_testlib.py` `safe_rmtree`/`TempWorkspace` |
| CI 矩阵（6 Hugo × 3 浏览器 + subdir + static + release） | ✅ 已实现 | `.github/workflows/ci.yml`；`check_ci_jobs.py` 计算 job 数 |
| 扩展点（`extra-head` / `extra-footer`） | ✅ 已实现 | `partials/extra-head.html`、`extra-footer.html` |
| Modal 无障碍工厂（复用） | ✅ 已实现 | `main.js` `createModalA11y` |

---

## 2. 部分实现（需在本轮补齐，且必须**新增配置开启**、默认外观不变）

| # | 功能 | 现状 | 差距 |
| --- | --- | --- | --- |
| P1 | 首页布局 | 仅一种（hero + 卡片流），硬编码在 `index.html` | 无法用配置切换 `profile`/`hero`/`landing`；无 `params.home.layout` |
| P2 | 阅读进度条 | 存在，**始终启用** | 无 `params` / 文章级开关；按整页高度计算，未按正文阅读区；未遵守"可配置" |
| P3 | 返回顶部 | 存在，**始终启用** | 无开关；显示阈值硬编码 `400`；键盘可达性未专项验证 |
| P4 | 提示块 | 仅 `shortcode`，4 种类型 | 不匹配 NOTE/TIP/IMPORTANT/WARNING/CAUTION；不支持纯 Markdown `> [!NOTE]`（需 Render Hook） |
| P5 | 面包屑 | 存在（首页 / 分类 / 正文） | 未体现 section 层级；未覆盖独立作者页等新页面类型 |

### 关键约束（来自用户第三节）

- 现有配置**继续有效**（`homePostCount`、`params.images`、`params.search.*` 等不得改名）。
- **默认外观不变**：`cards` 必须仍是默认布局；进度条/返回顶部若要可配置，其**默认值**必须与当前观感一致。
- 新功能优先**新增配置开启**，不引入无必要的 JS/CSS/运行时依赖。
- 不重复模块、不改 `theme.toml` 的 `min_version`（仍为 **0.128.0**）、不降低测试断言。

---

## 3. 真正缺失（本轮需实现）

| # | 功能 | 检索证据 |
| --- | --- | --- |
| M1 | 多种首页布局（`profile` / `hero` / `landing`） | `index.html` 硬编码单一结构；无 `params.home.layout` |
| M2 | 阅读进度条可配置 + 按**正文阅读区**计算 | `main.js:66-68` 用整页高度；无 params |
| M3 | 返回顶部可配置 + 键盘可达 | `baseof.html:18-20` 无开关 |
| M4 | 专注阅读模式 | 检索 `focus-mode|zen-mode` → 无 |
| M5 | 打印样式 | 检索 `@media print|@page` → 无 |
| M6 | Markdown 提示块 Render Hooks（五类型 + GitHub alert 语法） | `layouts/_default/_markup/` 仅 codeblock/heading/image 三个 hook，无 blockquote hook |
| M7 | 标签页 shortcode | 检索 `tabs` → 无 |
| M8 | 步骤 shortcode | 检索 `steps` → 无 |
| M9 | 文件树 shortcode | 检索 `filetree` → 无 |
| M10 | 徽标 shortcode | 检索 `badge` → 无 |
| M11 | 图片画廊 shortcode | 检索 `gallery` → 无 |
| M12 | Mermaid 可选支持 | 检索 `mermaid` → 无 |
| M13 | KaTeX 可选支持 | 检索 `katex|mathjax` → 无 |
| M14 | 编辑此页入口 | 检索 `editUrl|EditThisPage` → 无 |
| M15 | 多作者 Front Matter + 作者展示/JSON-LD/RSS 一致 | 检索 `Params.authors` → 无 |
| M16 | 独立作者档案页（优先用 Hugo 内容与分类机制） | 无 `authors` taxonomy / 作者页模板 |
| M17 | 外链文章（首页卡片区分 / canonical / RSS / 搜索索引 / 新标签） | 检索 `externalUrl` → 无 |
| M18 | 嵌套菜单 | `header.html` 无 `children` 处理 |
| M19 | 外观配置（强调色方案 / 正文宽度 / 字体行高 / 卡片密度 / 边距排版） | CSS token 固定；无模板注入 |
| M20 | 配置参考文档（新增项） | README 未覆盖上述新增配置 |

---

## 4. 候选功能：价值与复杂度

> 价值 = 对"技术博客 + 安全/运维内容"场景的实际收益；复杂度 = 实现 + 跨 Hugo 版本 + 三浏览器 + 无障碍验证的总成本。
> 分级：★ 低 / ★★ 中 / ★★★ 高。

| 功能 | 价值 | 复杂度 | 依赖/风险 | 备注 |
| --- | --- | --- | --- | --- |
| M1 多种首页布局 | ★★★ | ★★ | 需保证切换不影响分类/标签/搜索/RSS | 保留 `cards` 默认 |
| M2 进度条按阅读区 | ★★ | ★★ | 复用现有 `#progressBar`，改算法+开关 | 不新增 DOM |
| M3 返回顶部可配置 | ★★ | ★ | 复用现有 `#toTop` | 加键盘/开关 |
| M4 专注阅读模式 | ★★ | ★★ | 不隐藏正文、不失去导航、不破坏焦点 | 需可键盘退出 |
| M5 打印样式 | ★★ | ★ | 纯 CSS | 移除导航/侧栏/浮层，展开链接 |
| M6 提示块 Render Hooks | ★★★ | ★★ | 需兼容 0.128（blockquote hook 支持需验证） | 纯 CSS，不用 JS |
| M7 Tabs | ★★★ | ★★ | 代码块嵌套 / Markdown 解析 / 无 JS 降级 | 可纯 CSS/`details` 实现 |
| M8 Steps | ★★ | ★★ | 同上 | 可纯 CSS 序号 |
| M9 文件树 | ★★ | ★★ | 文件名路径特殊字符安全 | 纯 CSS 树形 |
| M10 徽标 | ★★ | ★ | 纯行内 | 低风险 |
| M11 图片画廊 | ★★★ | ★★★ | 复用现有 Pipeline + 灯箱，不重复建设 | 需响应式排列/键盘/触摸/回退 |
| M12 Mermaid 可选 | ★★★ | ★★★ | 默认零请求；按需加载；CDN 需 SRI+限制 | 失败给提示或原始内容 |
| M13 KaTeX 可选 | ★★ | ★★★ | 同上 | 与 Mermaid 共用按需加载策略 |
| M14 编辑此页 | ★★ | ★★ | 路径含中文/空格/special 需 encode；无配置不输出 | 逐文章可禁用 |
| M15 多作者 | ★★★ | ★★ | 兼容单 `author` 与站点回退；JSON-LD/RSS/正文一致 | 安全转义 |
| M16 作者档案页 | ★★ | ★★ | 优先用 Hugo 内容与分类机制 | 可与 M15 合并 |
| M17 外链文章 | ★★ | ★★★ | 首页卡片区分 / canonical / RSS / 搜索索引豁免 | 不信任任意输入 |
| M18 嵌套菜单 | ★ | ★★ | 移动端交互 + 无障碍 | 价值较低 |
| M19 外观配置 | ★★★ | ★★ | 统一变量体系；非法值安全回退；不降低对比度 | 默认外观不变 |
| M20 配置文档 | ★★★ | ★ | 纯文档 + 可执行一致性断言 | `check_docs.py` 需同步 |

---

## 5. 建议本轮实现及验收标准

> 全部实现项遵循：**默认外观不变**、**新功能新增配置开启**、**不改最低版本 0.128.0**、
> **不降低任何现有测试断言**。

### 5.1 功能一：多种首页布局（M1）

**配置**：`params.home.layout`（新增，值为 `cards` | `profile` | `hero` | `landing`，默认 `cards`）。

- 保留 `cards` 为默认，其渲染结果与当前**逐字节等价**（由现有截图/断言比对）。
- `profile`：以站点作者画像（头像/简介/社交）为首页主体，文章以紧凑列表呈现。
- `hero`：全幅焦点区（现有 hero 增强版，仅当有封面/置顶时有视觉差异）。
- `landing`：基于**已有模块**组合（无新模块）。
- 空简介 / 无头像 / 无社交 / 无置顶 / 无封面 / 文章数为 0 或不足一页 / 中英双语 / 移动端 /
  子目录 baseURL 均需正常。

**验收标准**：
1. 切换 `layout` 后，分类页、标签页、搜索索引（`index.json` 内容不变）、RSS 输出**不受影响**（断言：切换前后 `index.json` 与 `index.xml` 内容一致）。
2. 四种布局在同一份内容下均能构建成功且无控制台错误（三浏览器审计）。
3. `cards` 与基线产物对比无差异。
4. exampleSite 提供四种布局可运行示例。

### 5.2 功能二：文章阅读体验（P2/P3/M2/M3/M4/M5）

**配置**（均为新增，默认值与当前观感一致）：
- `params.reading.progressBar`（默认 `true`，保持现状）→ 文章级 `showProgress`
- `params.reading.backToTop`（默认 `true`，保持现状）→ 文章级 `showBackToTop`
- `params.reading.focusMode`（默认 `false`）→ 文章级 `showFocusMode`
- `params.reading.printStyle`（默认 `true`，纯 CSS 无副作用）

**验收标准**：
1. 进度条按**正文阅读区**（`.post-content` 起止）计算；文章页顶部/底部达 0%/100%（断言）。
2. 返回顶部在合理滚动位置出现，**键盘可达**（Tab 聚焦 + Enter 触发）。
3. 专注模式：**不隐藏正文**、**不失去导航**（提供可见退出）、**不破坏焦点顺序**（断言退出按钮可聚焦且可见）。
4. 打印样式：`@media print` 移除导航/侧栏/浮层/进度条；正文按打印页面排版；链接 URL 可见。
5. 遵守 `prefers-reduced-motion`（断言：reduced 下无 transform/滚动动画）。
6. 不引入新的无障碍问题（`check_html_quality.py` + `verify_contrast.py` 通过）。
7. Chromium / Firefox / WebKit 三引擎验证通过。

### 5.3 功能三：技术内容组件（M6~M13）

**提示块（M6）**：
- 新增 **Render Hook**（`blockquote`），支持 `> [!NOTE]` / `> [!TIP]` / `> [!IMPORTANT]` / `> [!WARNING]` / `> [!CAUTION]`，**纯 CSS 不依赖 JS**。
- 保留现有 `notice` shortcode（向后兼容，且类型保持可用）。
- 支持正文/语义标记（`role="note"` 等）、三语言（标题文案走 i18n）、暗色模式。
- **未知/错误类型不得导致构建失败**（断言：未知类型降级为普通引用且构建成功）。

**Tabs / Steps / 文件树 / 徽标 / 画廊（M7~M11）**：
- 全部为 shortcode；`tabs` 支持嵌套代码块与 Markdown 解析（`.Inner` + markdownify 正确）。
- 文件树：文件名含空格/中文/引号等特殊字符安全（断言无 HTML 破坏）。
- 画廊：**复用**现有图片 Pipeline 与灯箱（不重复建设）；alt / 响应式排列 / page bundle + static + 外链三种来源 / 缺失回退 / 键盘与触摸 / 不横向溢出 / 不无节制加载 JS。

**Mermaid / KaTeX（M12/M13）**：
- **默认不新增任何第三方请求**；仅在显式启用时按需加载（仅含对应语法的页面）。
- CDN 需明确配置 + 支持 `integrity`（SRI）+ 安全限制；保留本地资源能力。
- 未启用时**不增加任何资源**。
- 渲染失败给提示或回退原始内容。
- 浅/深色下均可读。
- 测试无 JS / 慢速网络 / 资源失败 / 语法异常。
- 不要求引入构建工具链。

**验收标准**：上述每条均有**直接断言**（证明真实行为），而非"脚本没报错"。

### 5.4 功能四：编辑与作者工作流（M14/M15/M16/M17）

**编辑此页（M14）**：
- 配置 `params.editUrl`（仓库 URL）、可选分支、内容目录。
- 路径含中文/空格/特殊字符需正确 encode。
- 逐文章可禁用（`editUrl: false`）。
- 无配置时**不显示无效链接**。
- 根目录 + 子目录 baseURL、中英文均正确。

**多作者（M15/M16）**：
- Front Matter `authors` 列表；兼容单个 `author` 与站点级 `params.author` 回退。
- 正确展示；**空不虚构**（无作者不输出）；JSON-LD / RSS / 正文**一致**；安全转义。
- 不强制后端。
- 独立作者页优先用 Hugo 内容与分类机制（taxonomy 或 section）。

**外链文章（M17）**：
- 明确的 Front Matter 标记（如 `externalUrl`）。
- 首页卡片区分外链与本站正文。
- 使用**指定 URL 不信任任意输入**（scheme 白名单）。
- 直接外链卡片**不生成死链接**（首页卡片直连外链，不生成站内死页）。
- 处理 canonical / RSS / 搜索索引 / 新标签打开。
- **不破坏**普通文章 / 系列 / 相关 / 归档。

### 5.5 功能五：外观配置完善（M19/M20）

**配置**：`params.appearance.*`（新增）
- 内置强调色方案（多套预设名 + 自定义）。
- 正文宽度、阅读字体行高、卡片密度/布局、不同模式（浅/深）边距排版。

**验收标准**：
1. 保持当前外观为默认（默认值 = 现状）。
2. 颜色不降低对比度（`verify_contrast.py` 对**每套预设**在浅/深下均通过）。
3. 统一设计变量体系（`--*` token，不逐模板复制颜色）。
4. 缺失/非法配置**安全回退**（断言：非法 scheme / 非法值不产生破坏性输出）。
5. 配置参考文档 + 实际示例。

### 5.6 第九节：按需补齐

- **核对**：嵌套菜单（M18）、多作者档案页（M16）、面包屑（P5）、外链内容类型（M17）、文章元信息、编辑入口（M14）。已正常工作的**不重写**；缺失的按上文实现（嵌套菜单价值较低，见第 6 节暂缓）。
- **本轮明确不做**：PWA/离线缓存、内容加密、AI 聊天/搜索、新搜索后端、音乐播放器/地图、依赖后台服务的点赞/阅读量、大型图表系统。

### 5.7 exampleSite 演示站

为**所有新增功能**提供真实演示页（中英文），且**不依赖实际生成的网站**即可用：

| 演示项 | exampleSite 路径（拟） |
| --- | --- |
| 各首页布局 | `content/layouts-demo/cards|profile|hero|landing.md`（多 `outputs`/`layout` 演示） |
| 提示块 / Tabs / Steps | `content/posts/<新增演示文>.md` |
| 文件树 / 画廊 | 同上（画廊用 page bundle） |
| Mermaid / 数学 | 同上（启用配置的示例） |
| 多作者 / 外链 | 同上 |
| 编辑入口 / 阅读进度·专注·打印 | 同上 |
| 配色排版 | `params.appearance` 示例配置 |

> 硬性要求：**不得**只加 README 截图或样例而无实现代码。

### 5.8 开发质量要求（第十一节）

- 所有新增功能有明确配置 / 默认值 / 文档 / 测试。
- 自测覆盖：Hugo `0.128.0 / 0.148.0 / 0.162.0 / 0.166.0 / 0.167.0`；三浏览器；根 + 子目录 baseURL；中英及缺配置；正常 + 极端内容；无 JS；安全 scheme 校验；搜索 / JSON-LD / RSS / 图片 Pipeline；临时文件清理与退出码；生产构建与 `--minify`；新功能故障注入。
- **不破坏** BUG-R2-003/001/002/004/005 与测试假绿修复。
- **不得以"测试未报错"代替功能验收**，必须有直接证明真实行为的断言。

---

## 6. 暂缓及原因

| 功能/项 | 暂缓原因 |
| --- | --- |
| M18 嵌套（多级）菜单 | 价值相对低；当前平铺一级已满足技术博客导航；移动端下拉 + 无障碍成本不成比例。**本轮仅核对现状，不改动**。 |
| PWA / 离线缓存 | 用户第九节明确本轮不做；会引入 service worker 生命周期、缓存失效与更新语义等新的失败面。 |
| 内容加密 | 明确不做；需后端/密钥管理，与"零运行时依赖"定位冲突。 |
| AI 聊天 / AI 搜索 | 明确不做；依赖外部服务与密钥，且与隐私定位冲突。 |
| 新搜索后端（倒排索引 / 渐进加载） | 明确不做；现有 `auto/single/shard` 已满足，改动搜索契约风险高（`稳定基线.md` §5.1 有硬契约）。 |
| 音乐播放器 / 地图 | 明确不做；与技术博客定位无关。 |
| 依赖后台服务的点赞 / 阅读量 | 明确不做；`views`/`busuanzi` 已提供可选统计，新增会引入后端依赖。 |
| 大型图表系统 | 明确不做；Mermaid 已覆盖流程图/时序图等常用需求。 |
| 真实屏幕阅读器（NVDA/VoiceOver）验证 | 环境限制，仅能做属性与焦点级验证（沿用 `稳定基线.md` §6 既有声明）。 |
| 第三方评论真实账号联调 | 同上，需外部账号。 |
| 移动端真机测试 | 环境限制，仅在 WebKit 引擎模拟（沿用既有声明）。 |

---

## 7. 兼容性红线（实施期间不得触碰）

1. `theme.toml` `min_version = "0.128.0"` **不变**。
2. 现有配置键（`homePostCount`、`params.images.*`、`params.search.*`、`params.content.sections`、
   `params.share.*`、`params.comments.*`、`params.socials.*`、`params.profile.*`、`params.sidebar.*`、
   `params.views.enable`、`params.busuanzi.enable`、`params.rss.*`、`params.license`、
   `params.footerText`、`params.icp`、`params.avatar`、`params.logo`、`params.logoText`、
   `params.favicon`）**保持有效且语义不变**。
3. 文章级开关（`toc`/`comments`/`showDate`/…/`lightbox`）保持缺省值不变。
4. `index.json` 现有字段（`title/url/date/dateDisplay/summary/content/key/tags/categories/series`）
   **一个不少**；新增字段只能追加。
5. `v1.0.9` 标签不移动；不建正式 Release；不邀请第三方测试 AI 提前测试；不宣布可发布。
6. 每个逻辑完整功能组**单独提交**。