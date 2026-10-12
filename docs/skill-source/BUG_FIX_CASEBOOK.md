# BUG_FIX_CASEBOOK — 真实缺陷案例集

> 本文收集 Nebula 项目**真实遇到并修复**的缺陷（产品 Bug + 测试缺陷），按主题归类。
> 每条给出：**触发条件 / 根因 / 修复 / 回归测试 / 经验教训**。
> 证据来源：`docs/final-cleanup-issue-tracker.md`、`docs/第三方测试修复交接报告-第二轮.md`、
> `docs/测试交接报告-功能完善阶段.md`、`README`/`CHANGELOG`、真实代码。
>
> 标注：【已证实】= 有代码/门禁/报告佐证；【开发方自测】= 开发方验证、未经独立第三方复验。

---

## A. 模板空值与字符长度（最致命的一类）

### A1. `slicestr` 越界导致**整站构建失败**（BUG-P1-003）

- **触发**：文章标题/站点标题为 空 / 单字符 / 单 CJK / 单 emoji / 纯空白；或站点无头像且 `author` 为空。
- **根因**：模板用 `slicestr .Title 0 40` 之类做截断。`slicestr` 按 **rune** 计数，
  长度不足会 **panic 并终止整站构建**。更隐蔽的是：判定长度时用了 `len`，而 `len` 返回**字节数**
  （"中" 的 `len` = 3），于是「字节够但 rune 不够」时仍越界。
- **修复**：抽 `partials/util/slice-runes.html`（内部用 `countrunes` 判断，绝不越界），
  所有截断点改走它（`post-card.html`、`header.html`）。
- **回归**：`gen_testdata.py` 固化 `zz-21-empty-title` / `zz-22-one-char` / `zz-23-one-cjk` /
  `zz-24-one-emoji` / `zz-25-blank-title` / `zz-27-no-author` 等边界夹具；CI build job 断言这些产物目录存在。
- **教训**：**「rune 长度」与「字节长度」必须分清，且截断只能有一个实现点。**

### A2. 同类缺陷的「清扫遗漏」（BUG-R2-001）

- **触发**：`contentLimit` 生效 + 中文正文 → 整站构建失败。
- **根因**：BUG-P1-003 的修复**没有清扫干净**——`layouts/_default/index.json` 第 65 行
  仍用裸 `slicestr`。第一轮只修了「看得到的地方」。
- **修复**：`index.json` 第 73 行改走 `partial "util/slice-runes.html"`。
- **教训**：**修复一类根因时，必须全仓搜索同一模式，而不是只修当前报错点。**
  （这也是后来 `check_index.py` 增加 contentLimit 覆盖的动机之一。）

### A3. 空/纯空白标题仍拼出前导连字符（OBS-R3-002）

- **触发**：文章 `title` 为空或纯空白 → `<title>` 变成 `"- 星云技术笔记"`。
- **根因**：`<title>{{ .Title }} - {{ .Site.Title }}</title>` 未处理空标题。
- **修复**：`head.html` 改为 `{{ with trim .Title " \t\r\n" }}{{ . }} - {{ end }}{{ .Site.Title }}`
  —— 空标题时省略「标题 - 」，只留站点名。
- **回归**：`check_html_quality.py` 新增 `title-leading-dash` 规则（`<title>` 以 `- ` 开头即判红）；
  对注入的旧缺陷可稳定判红（`title-leading-dash x1`）。
- **教训**：**空值分支必须显式处理**；SEO 元信息（`og:title` / JSON-LD `headline`）与 `<title>` 要口径一致。

---

## B. 布尔值 `false` 与「未设置」的区分

### B1. 写 `false` 不生效（阅读体验 Front Matter 覆盖）【已证实】

- **触发**：站点级开启某功能，文章级想用 `false` 关掉，却关不掉。
- **根因**：模板用真值判断（`{{ if .Params.x }}`），无法区分「未设置」与「显式 `false`」；
  或用了会吞掉 `false` 的取值方式。
- **修复**：新增 `util/bool-param.html`，显式区分「未设置 → 回退上层」与「显式 false → 真关」。
- **回归**：`check_reading_experience.py` A 小节断言「文章级 Front Matter 覆盖站点级」，
  含**「写 `false` 必须真生效」**的专门回归。
- **教训**：**布尔开关必须有「三态」语义**（未设置 / true / false），不能只做真值判断。

### B2. `params.authors.pages=false` 不等于「关闭作者页」（DOC-R3-005）

- **现象**：文档把 `pages=false` 说成能关掉 `/authors/`，实际 Hugo 仍生成该页。
- **根因**：把「主题是否渲染作者资料结构」与「Hugo 是否生成 taxonomy 页」混为一谈。
- **真相**（【已证实】，§8.1 对照）：只有**不注册 `authors` taxonomy** 才不生成 `/authors/`（产物 286）；
  仅 `pages=false` 而 taxonomy 仍注册时产物仍为 **291**。
- **修复**：README 改为三场景对照表；`docs/稳定基线.md §5.11` 补 `pages` 语义；`check_docs.py` 增结构级断言。
- **教训**：**「主题开关」与「Hugo 机制」的边界要在文档里写清**，否则会给人错误预期。

---

## C. URL 编码与特殊字符

### C1. 字面 `+` 被误编码 → 全站审计假差异（TEST-DEFECT-R3-010）

- **触发**：作者名 `C++ 工程师` → taxonomy 目录 `authors/c++-工程师/`；
  inventory 的 `normalize_url()` 把 `+` 编码成 `%2B`，与 Hugo 产物 / sitemap / 浏览器实际 URL 不一致
  → 全站审计出现**假差异**（MISSING/UNEXPECTED）。
- **根因**：`quote()` 的 `safe` 未包含 `+`。
- **修复**：把 `+` 加入 safe；同时用回归确保：
  - 字面 `+` **不被**改成 `%2B`；
  - 已编码的 `%2B` **不被二次编码、也不被解码**；
  - `c++/` 与 `c%2B%2B/` **不被折叠**为同一 URL。
- **回归**：`test_inventory.py`（**17/17**）新增加号相关 4 组。
- **教训**：**URL 规范化必须与「Hugo 真实产出 + 浏览器真实请求」一致**，不能想当然套通用 `quote`。
  路径段中的 `+` 是字面量（`+`=空格只在 query）。

### C2. CJK 作者名用 `urlize` 拼路径得到 `NONE`（M16 相关）【已证实】

- **根因**：`urlize "张伟"` → `%E5%BC%A0%E4%BC%9F`；`GetPage "/authors/<urlize>"` 返回 `NONE`；
  且 `+` 会被转义为 `&#43;`。
- **修复**：遍历 `site.Taxonomies` 按 `Page.Title` **大小写不敏感**匹配 RelPermalink，**不用 `urlize`**。
- **教训**：**CJK / 特殊字符路径不要靠 `urlize` 猜**，要用 taxonomies 的真实 Page 反查。

---

## D. 多语言 / i18n

| ID | 触发 | 根因 | 修复 | 回归 |
| --- | --- | --- | --- | --- |
| BUG-R3-001 | 0.128/0.148 全站 UI 文案空串 | 语言键与 `i18n/` 文件名不匹配 | 显式 `defaultContentLanguage="zh-CN"` + `[languages.zh-CN]` | `check_features.py` 8a/8b 双层 + 反证 |
| BUG-R3-002 | deprecated WARN | `[languages.*]` 顶层 `label`(0.112)/`languageCode`(0.158) | 根 `locale` + `params.label` 零告警形态 | `check_lang_config.py`（60 项） |
| BUG-R3-003 | 0.128 `og:locale = zh_cn` | 未规范化 | `util/locale.html` BCP47（`zh_CN`） | 同上 |
| （经验） | 英文构建实际仍是中文 | `--config` 相对 `--source` 找不到文件被静默忽略 | overlay 复制进站点目录再用相对路径 | `verify_multilingual.py` |

- **教训**：**i18n 是「模板不得写死文案」的强约束**（`check_i18n_hardcode.py`：layouts/assets 中出现硬编码 UI 文案即失败，且**扫到 0 个文件也算失败**）；**UI 日期走 i18n，机器格式走白名单**。

---

## E. 搜索索引

### E1. `auto` 在旧 Hugo 上整站构建失败（BUG-P1-002）

见 `HUGO_COMPATIBILITY.md §4`。根因：分片依赖 `resources.Publish`（0.166+）而旧版本无此 API。
修复：能力探测 + 旧版本回退（auto）/ 明确报错（显式 shard）。

### E2. 索引正文被截断却「真空通过」（TEST-DEFECT-R2-001）

- **触发**：索引正文被截断到 10 个字符，`check_index.py` 仍 PASS。
- **根因**：旧实现只检查 title/url 是否存在，**正文为空或截断仅 WARN**。
- **修复**：压力数据在长文末尾埋唯一标记 `TAILMARKER_9Z8Y7X` / `TAILMARKER_50K_END`，
  **未配置 contentLimit 时末尾标记必须存在**；并加 `MIN_BYTES_PER_ENTRY` 体积下限。
- **教训**：**「字段存在」≠「内容完整」**；完整性要用**可证伪的哨兵**（末尾唯一标记），而不是长度阈值猜。

### E3. series 写入索引却不参与匹配（BUG-P2-005）

- **触发**：搜索系列名搜不到。
- **根因**：索引写了 `series` 字段，但前端 `score()` 未纳入。
- **修复**：`main.js` 的 `score()` 纳入 `series`（权重 6）。

### E4. contentLimit 配置感知的「假绿」与「假红」（TEST-DEFECT-R3-011 + 本轮修复）

- **假红**（R3-011）：用 `--config` 叠加层设置 `contentLimit` 时配置感知不到 →
  合法截断被按「未配置」严格校验 → 假红。修复：配置扫描扩展到 `<BUILD_DIR 上一层>/*.toml` 与 `exampleSite/*.toml`。
- **假绿**（本轮新发现，【已证实】）：把**未参与本次构建**的孤立 TOML（写了 `contentLimit`）
  放在输出目录上一层，会让「正文被意外截断」的索引被判成「合法配置截断」→ **PASS（假绿）**。
  修复：新增 `_looks_like_build_source()`，**仅当该目录确实像 Hugo 源根**
  （存在 `hugo.toml`/`config.toml` 或 `content/`）时才采信其 `*.toml`。
- **验证三条件（同时成立）**：正常完整索引 PASS / 意外截断 FAIL / 合法配置截断 PASS。
- **教训**：**「发现配置」类门禁必须把配置「绑定到本次构建」**，否则会被无关文件欺骗。

---

## F. JSON-LD

### F1. 全站 JSON-LD 双重编码（BUG-P2-004 / SEC-04）

- **触发**：JSON-LD 输出被编码两次，形如 `"\"标题\""`，语义损坏。
- **根因**：模板对字段先 `jsonify` 再整体 `jsonify`；且 `</script>` 未转义。
- **修复**：`head.html` 改为**整体 `dict` + `jsonify | safeJS` 一次输出**；`</script>` 转义为 `\u003c/script\u003e`。
- **回归**：`check_html_quality.py` 检测双重编码（「字符串本身以引号开头结尾，且能再 `json.loads`」）
  + **与 `og:title` / `og:site_name` 交叉校验**。
- **隐藏陷阱**：校验正则**必须容忍无引号属性**——CI 一律 `--minify`，Hugo 会输出
  `<script type=application/ld+json>`（去引号），旧正则写死 `type="application/ld+json"` 会 **0 匹配 → 校验恒真**（TEST-DEFECT-001）。
  因此还必须有**「全站至少解析到 1 个 JSON-LD 块」的兜底断言**。

### F2. 未配置作者时输出 `author.name: null`（BUG-R2-005）

- **修复**：`head.html` 无作者即**省略** `author` 字段（而不是输出 null）。
- **教训**：**JSON-LD 里「缺字段」应是省略，而不是 null**。

### F3. 缺 `date` 的文章泄漏 `0001-01-01`（BUG-P3-001）

- **触发**：文章无 `date` → 页面/归档出现 `0001年1月1日` / `0001`；JSON-LD 输出零值日期。
- **修复**：页面侧走本地化「未标注日期」或省略；JSON-LD 零值**不输出日期字段**；归档无日期单独成组。
- **回归**：`check_html_quality.py` 的 `zero-date` 规则（出现 `0001-01-01`/`0001年1月1日` 即红）。

---

## G. 分页与 URL 分类

| 问题 | 根因 | 修复 |
| --- | --- | --- |
| 文章页误判（BUG 相关） | 旧 `is_article_page()` 用 `/[^/]+/[^/]+/`，把 `/categories/<term>/`、`/tags/<term>/`、`/archives/`、`/page/N/` 都当成文章页，并从 crawl 种子里剔除 | 基于 `params.content.sections`（回退链）判定；`check_article_classification.py`（39 项） |
| 分页 token 写死 `page` | 忽略 `[pagination] path` 可配 | crawler **先反推产物 → 再读配置 → 最后默认 `page`** |
| 分页页进 crawl 种子 | 分页页是 BFS 产物，进 visited 会让交叉验证退化 | crawl 种子排除文章页、alias 页、分页页 |

- **别名分页页**（`/page/1/`）按设计**不被链接**，由 inventory 直接覆盖并**单独计数**；
  alias 页的 meta-refresh 结构必须**静态**验证（浏览器打开会重定向，观察到的是目标页）。

---

## H. 无作者 / 无头像 / 空资源

### H1. 未配置或空 `params.avatar` → 渲染 `<img src="/">` 破损图（BUG-R2-003，**回归**）

- **根因**：`<img src="{{ .Site.Params.avatar }}">` 在空值时变成 `src="/"`。
- **修复**：新增 `util/avatar-url.html`（空/空白/危险 scheme/站根 → 返回空串），
  `post-card.html`、`sidebar.html` 改走它。
- **教训**：**所有来自配置的 URL 都要经校验 partial**，不能直接拼进 `src`/`href`。

### H2. 空正文显示「约 0 分钟 / 0 字」（BUG-P3-007）

- 修复：正文为空时隐藏阅读统计。教训：**统计类 UI 要处理 0 值/空值**。

### H3. 无 `<noscript>` 回退（BUG-P3-002）

- 修复：新增 `.noscript-hint`（三语言 `common.noScript`）。

---

## I. 滚动锁定与焦点恢复（Modal 无障碍）

### I1. 关闭搜索弹窗后页面永久不可滚动（BUG-P1-001，P1）

- **触发**：遮罩点击 / Escape 关闭搜索弹窗后，`body.overflow` **停在 `hidden`**，页面滚不动。
- **根因**：`body.overflow` 的加锁/解锁散落在各关闭路径里，**某条路径漏了解锁**；
  且恢复时**无条件置空**，而不是恢复打开前的真实值。
- **修复**：把滚动锁**下沉到 `createModalA11y` 工厂**（`assets/js/main.js`）：
  引用计数 + 恢复打开前的真实 `body.style.overflow` + 多模态互斥。
- **回归**：`verify_modal_scroll.py`（三引擎）覆盖：遮罩 / Escape / 深链 / 快速开关 /
  键盘风暴 / 非默认 overflow / 双模态互不干扰 / 关闭按钮；
  并可用 `SCROLL_LOCK_BUG=1` 注入「锁失效」自证断言会变红。
- **关键教训**：**判定「能否滚动」必须用真实用户输入（滚轮 / PageDown）——
  `overflow: hidden` 仍允许 `window.scrollTo` 程序化滚动，用 `scrollTo` 判定会得到假结论。**

### I2. 关闭弹窗焦点归还把页面位置拉走（BUG-R2-004）

- **根因**：`focus()` 未用 `preventScroll`，浏览器为滚动到焦点元素而移动页面。
- **修复**：`main.js` 改 `focus({ preventScroll: true })`。
- **回归**：`verify_modal_scroll.py` 新增 2d「关闭弹窗不得改变页面滚动位置」；
  `SCROLL_FOCUS_BUG=1` 可注入自证会变红。

### I3. 焦点管理整体契约

`createModalA11y` 为搜索弹窗与灯箱提供同一套行为：焦点移入 → Tab/Shift+Tab 循环 →
背景 `inert`+`aria-hidden` → Escape 关闭 → 关闭后焦点归还触发元素（无触发元素时退化为 dialog 自身）→ 快速开关幂等。
由 `verify_search_modal.py`（**19 项**）在**三语言 × 三引擎**下验证。

---

## J. 可访问性（真实浏览器审计发现的「像素级」缺陷）

### J1. `.article-external-notice a` 触控目标 98×23px（R4-007）

- **根因**：容器 `display:flex` 把内联链接**块级化**，失去「正文内联链接」的 WCAG 豁免，
  实测 98×23px < 24px 阈值。
- **修复**：`.article-external-notice a { display:inline-flex; align-items:center; min-height:26px }`。
- **复验**：审计由 `3/7 PASSED（4 处问题）` → `4/4 PASSED, TOTAL PROBLEMS: 0`。

### J2. `.author-link` 40×24 / 69×24px（R5-001）——**与 J1 同根因**

- **根因**：`.author-link` 只写了 `color`/`text-decoration`，`<a>` 仍是 **inline**；
  **`min-height` 对 inline 元素无效**。
- **修复**：`display:inline-flex; align-items:center; min-height:26px`；
  并在 `check_author_pages.py` 新增 **ON22–ON24**：直接断言**构建产物打包 CSS**
  中 `.author-link` 必须含 `display:inline-flex/inline-block` 且 `min-height ≥ 24px`。
- **复验**：审计由 `3/7 PASSED（24 处）` → `7/7 PASSED, TOTAL PROBLEMS: 0`。
- **教训**：**「元素存在 / href 正确」的字符串断言抓不到像素高度**——
  可访问性缺陷必须由**真实浏览器审计**发现；静态门禁只能防回归。

### J3. 对比度不达标（BUG-P2-003）与断点溢出（BUG-P2-002）

- 对比度：颜色 token 按用途拆分（`--brand-solid`/`--brand-ink`/`--accent-ink`），
  `--text-muted` 加深；由 `verify_contrast.py` 取 computed style（含 alpha 合成）逐元素算，
  且要求**受检选择器不得空转**。**度量前必须禁用 CSS 过渡**，否则读到过渡中间值（会把 5.19:1 读成 1.1:1 的假故障）。
- 断点：头部导航断点 **900px**（有意高于内容断点 768px），因英文导航更长，
  769–869px 下 `nav`+`header-actions` 会撑破布局。

---

## K. 安全（scheme / 逃逸）

| ID | 问题 | 修复 |
| --- | --- | --- |
| SEC-01 | 搜索结果链接缺 scheme 白名单 | `main.js safeHref()`：只放行 `http(s)`/`/`/`.`/`#`；Enter 同判 |
| SEC-03 | `rel-url.html` 允许任意 scheme | 源头拒绝 `javascript:`/`vbscript:`/`data:`(非 image)，先剥空白与控制字符 |
| SEC-04 | JSON-LD `</script>` 逃逸 | 转义为 `\u003c/script\u003e` |

- **教训**：**校验必须在「源头 partial」做**——调用方普遍 `| safeURL`，等于信任返回值；
  若源头不拒绝，下游无法补救。搜索高亮必须**先 `esc` 再正则替换**，`<mark>` 不嵌套、文本不丢失、查询串不产生 XSS。

---

## L. 全局教训速查

1. **空值 / 0 值 / false 是 Bug 高发区**：标题、作者、头像、日期、正文、布尔开关都要显式处理。
2. **长度要分清 rune 与 byte**；截断/复制的实现必须唯一。
3. **凡「来自配置的 URL」都要过校验 partial**（scheme 白名单 + 空值处理）。
4. **修复一类根因要全仓清扫**，不能只修报错点。
5. **「字段存在」≠「内容完整」**，完整性要用哨兵。
6. **可访问性的像素问题只能靠真实浏览器审计**。
7. **门禁的「配置发现」必须绑定到本次构建**，否则会被无关文件欺骗（假绿）。
8. **同一语义只有一个实现点**（单点 partial / 单点配置入口）。
