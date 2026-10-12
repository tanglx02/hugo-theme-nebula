# PROJECT_OVERVIEW — Nebula 主题总览

> 本目录（`docs/skill-source/`）只用于**沉淀经验、供后续制作通用 Hugo 主题开发 Skill**，
> 不参与主题构建、不被主题运行依赖。所有内容以仓库真实代码、Git 历史、CI 配置与既有报告为依据。
>
> **证据标注约定**（全文通用）：
> - 【已证实】= 有可复现的命令 / 产物 / CI 日志支撑的事实。
> - 【开发方结论】= 开发方基于自测给出的判断，尚未经独立第三方复验。
> - 【待独立验证】= 明确尚未验证的路径。

---

## 1. 主题定位

**Nebula** 是一款清爽、现代的 Hugo 博客主题，面向中文技术博客场景，强调：

- **零第三方默认请求**：默认不加载任何外部 CDN / 统计 / 评论脚本（Mermaid、KaTeX 本体自托管）。
- **可选启用**：评论、外部文章、作者档案页、外观配置等均为可选，**默认不改变任何站点 URL 结构**。
- **可验证**：主题自带一整套「失败即非零退出」的门禁脚本与 GitHub Actions，**门禁本身也经过故障注入自证**。

来源：`theme.toml`（`name`/`description`/`features`/`tags`）、`README.md`。

---

## 2. 功能清单

### 2.1 六大功能域（【已证实】，README + theme.toml + 门禁）

| 编号 | 功能域 | 内容 | 主要门禁 |
| --- | --- | --- | --- |
| 功能一 | 首页布局 | `cards` / `profile` / `hero` / `landing` 四种布局，可配置、非法值安全回退 `cards`，切换布局不改 `index.json` / `index.xml` | `check_home_layouts.py` |
| 功能二 | 阅读体验 | 进度条（按正文阅读区映射）/ 返回顶部 / 专注模式 / 打印样式 / `prefers-reduced-motion` | `check_reading_experience.py` |
| 功能三 | 技术内容组件 | 提示块(callout) / 标签页 tabs / 步骤 steps / 文件树 filetree / 徽标 badge / 按钮 button / 折叠块 details；画廊 gallery | `check_content_components.py`、`check_new_features.py` |
| 功能四 | 编辑与作者工作流 | 编辑此页(editURL) / 多作者 / 外链文章 / **作者档案页 M16（可选启用）** | `check_new_features.py`、`check_author_pages.py` |
| 功能五 | 外观配置 | 强调色 / 正文宽度 / 行高 / 字体 / 卡片密度，`util/appearance.html` 单一生效链 | `check_new_features.py` |
| 功能六 | Mermaid / KaTeX | 按需加载、自托管、SRI 可选 | `check_new_features.py`、`detect-math.html` |

### 2.2 基础能力（【已证实】）

全文搜索（完整全文 / 可分片 / `auto` 按体积自动选择）、暗色模式、响应式布局、
代码高亮与一键复制、文章 TOC、侧边栏组件、灯箱（键盘与焦点无障碍）、
i18n（zh-CN / zh-TW / en）、SEO、RSS / sitemap / robots。

### 2.3 功能缺口口径（【已证实】）

历史功能缺口清单 M1–M20：**19 项实现 + 1 项接受限制（M18 嵌套菜单）**。
其中 **M16 作者档案页**由「曾登记为限制」升级为**可选启用完整实现**（不注册 `authors`
taxonomy 时产物与「无本功能」基线主题规范化后逐字节一致）。
详见 `OPEN_LIMITATIONS.md`、`docs/final-cleanup-issue-tracker.md §11`。

---

## 3. 技术架构

### 3.1 技术栈（【已证实】）

| 层 | 选型 | 说明 |
| --- | --- | --- |
| 站点生成 | **Hugo extended ≥ 0.128.0** | `theme.toml` 的 `min_version`；分片搜索需 0.166+ |
| 模板 | Go template（`layouts/`） | 无外部前端框架 |
| 样式 | 单一 `assets/css/main.css`（Hugo Pipes 打包 + 可选 SRI） | 颜色用 CSS 变量 token |
| 脚本 | 原生 JS（`assets/js/main.js` 等），无框架 | 搜索 / 主题切换 / Modal / 复制 / TOC |
| 资源管线 | Hugo Pipes（`resources.*`） | 图片 `render-image` 钩子；JS/CSS 指纹化 |
| 测试 | Python 3.12（CI）+ Playwright | `tools/` 下门禁脚本 |
| CI | GitHub Actions（`ubuntu-24.04` 固定） | 14 job（含 tag 专属 Release 审计） |

### 3.2 目录说明（【已证实】）

```
hugo-theme-nebula/
├─ archetypes/                # 新建内容模板
├─ assets/
│  ├─ css/main.css            # 全站样式（Hugo Pipes 打包）
│  └─ js/{main,kaTeX-init,mermaid-init,tabs}.js
├─ i18n/{zh-CN,zh-TW,en}.yaml # UI 文案（模板不得写死）
├─ layouts/
│  ├─ _default/
│  │  ├─ baseof.html          # 基础骨架
│  │  ├─ home-showcase.html   # 首页
│  │  ├─ list.html / single.html / term.html / terms.html / archive.html
│  │  ├─ index.json           # 搜索索引输出（分片/单文件）
│  │  └─ _markup/             # render-image / render-codeblock / render-heading / render-blockquote
│  ├─ partials/               # head / header / footer / post-card / sidebar / search-modal …
│  │  ├─ components/          # tabs / steps
│  │  ├─ home/                # cards / profile / hero / landing / latest
│  │  ├─ util/                # 单点工具 partial（见 3.3）
│  │  └─ widget/
│  ├─ shortcodes/             # notice/tab/tabs/step/steps/filetree/badge/button/details/gallery
│  ├─ index.html / index.xml / 404.html / alias.html / robots.txt
├─ exampleSite/               # 完整功能展示站（zh-CN + content-en）
├─ docs/                      # 设计与验收文档（含本 skill-source/）
├─ tools/                     # 54 个 Python 门禁/工具脚本 + requirements.txt
├─ theme.toml                 # 主题元数据（min_version 等）
├─ README.md / CHANGELOG.md / LICENSE
└─ .github/workflows/{ci,compat-latest}.yml
```

### 3.3 关键「单点工具」partial（【已证实】）

这些 partial 是主题里被反复调用的**收口点**，多个真实 Bug 的根因都出在「绕过收口、就地实现」上：

| partial | 职责 | 相关 Bug |
| --- | --- | --- |
| `util/slice-runes.html` | 按 **rune** 安全截断，绝不越界 | BUG-P1-003、BUG-R2-001 |
| `util/avatar-url.html` | 头像 URL 校验（空/空白/危险 scheme → 空串） | BUG-R2-003 |
| `util/rel-url.html` | 源头拒绝 `javascript:`/`vbscript:`/`data:`(非 image) | SEC-03 |
| `util/locale.html` | `og:locale` BCP47 规范化 + 跨版本 `.Locale`/`.LanguageCode` 回退 | BUG-P3-005、BUG-R3-003 |
| `util/author-config.html` | 作者档案页唯一配置入口 `{enabled,taxonomy,profiles}` | M16 |
| `util/bool-param.html` | 布尔参数解析（区分「未设置」与「显式 false」） | 阅读体验 Front Matter 覆盖 |
| `util/appearance.html` | 外观变量单一输出链 | 功能五 |
| `util/external-url.html` | 外链 scheme 白名单 | SEC-01 |
| `util/detect-math.html` | 探测页面是否含数学公式（决定是否加载 KaTeX） | 功能六 |
| `util/uid.html` / `util/nested-block.html` / `util/resolve-nested.html` | 嵌套组件（tabs/steps 交叉嵌套） | 功能三 |

> 经验：**同一语义必须只有一个实现点**。Bug 高发区几乎都在「本该调用收口 partial，
> 却在新代码里又就地写了一遍」的位置。

---

## 4. 支持的 Hugo 版本与最低运行要求

| 项 | 值 | 证据 |
| --- | --- | --- |
| 最低 Hugo 版本 | **0.128.0（extended）** | `theme.toml` 的 `min_version` |
| CI 构建矩阵 | 0.128.0 / 0.148.0 / 0.162.0 / 0.166.0 / 0.167.0 / `latest` | `.github/workflows/ci.yml` `build.matrix.hugo-version` |
| 分片搜索最低版本 | **0.166.0**（依赖 `resources.Publish`） | `check_search_modes.py` |
| 本地固定复现矩阵 | 5 版本（0.128.0 / 0.148.0 / 0.162.0 / 0.166.0 / 0.167.0） | `check_content_components.py` / `check_author_pages.py` |
| 测试用 Python | **3.12**（CI 基准，`PYTHON_VERSION`） | `.github/workflows/ci.yml` |
| 测试依赖 | `playwright>=1.44`、`Pillow>=10.0`、`PyYAML>=6.0` | `tools/requirements.txt` |
| 浏览器 | Chromium / Firefox / WebKit（Playwright） | browser-tests + Release audit |

> 细节见 `HUGO_COMPATIBILITY.md`。

---

## 5. 项目状态快照（写本文档时，【已证实】）

> **SHA 口径（重要）**：本项目的"主题代码"与"文档沉淀"是两个不同的提交，
> **各自的 CI 结果只能绑定各自的 SHA，不得互相套用**。

| 项 | 值 | 说明 |
| --- | --- | --- |
| **主题代码基线** | **`8363d4b89193a7dfa22bc1569918a4eb666865cd`** | 含全部主题运行时文件（`layouts/ assets/ i18n/ …`） |
| 主题代码基线的 CI | PR `38171213190`；dispatch `38171253788`（**14/14**） | 两项均绑定 `8363d4b` |
| **文档沉淀提交（skill-source 首版，docs-only）** | **`e03a6c801090aeaa682a2e55d671acd3578c2e17`** | `8363d4b` + 1 个仅新增 `docs/skill-source/*.md` 的提交 |
| 文档沉淀提交的 CI | PR `38188954023`；dispatch `38189345376`（**14/14**） | 两项均绑定 `e03a6c8` |
| 候选分支 | `feat/theme-feature-completion` | 远端 tip 以 `git ls-remote` 实时结果为准 |
| 最终 PR | **#6**（`feat/theme-feature-completion` → `main`），唯一开放、MERGEABLE / CLEAN | — |
| 旧 PR | **#5**（`fix/third-party-audit-v1.0.9-r2`）**已关闭**（`2026-10-12T00:33:29Z`），其修复已被 `#6` 完整覆盖 | 实时核对 |
| `main` | `21745162da343f2a0809516148b1a5680893390e`（未改动） | — |
| `v1.0.9` 标签 | `6168bb13b68014ea18953df6c7dc40078d581868`（未移动） | — |
| Release | 无 | — |

> - 后续**纯文档**一致性修订会继续以新的 docs-only SHA 出现在候选分支上；
>   它们同样只改 `docs/`，不触碰主题运行时文件。
> - 状态随开发推进变化，**以 GitHub / git 实时结果为准**；本文件不重复维护实时数字，
>   也**不得**把某个 SHA 的 CI 结论复制到另一个 SHA 名下。

---

## 6. 与主题运行无关的部分（重要边界）

- `tools/` 下的 54 个 Python 脚本是**开发与 CI 的辅助测试工具**，**不是**主题部署依赖。
  用户部署主题只需 Hugo extended；不需要 Python / Playwright / Node。
- `docs/` 与 `docs/skill-source/` 是**文档沉淀**，不参与构建。
- `exampleSite/` 是演示站，主题被其他站点引用时**不包含**它。
