# FEATURE_IMPLEMENTATION_PATTERNS — 功能实现模式库

> 资料性质：用于通用 Hugo 主题开发 Skill 的经验沉淀。
> 事实标注：**【已证实】**＝有真实模板代码/CI 支撑；**【结论】**＝开发方判断；**【待验证】**＝未经独立第三方确认。
>
> 本文档提炼 Nebula 主题在实现功能时**反复使用的实现模式**。模式的价值在于：**同类问题在下一个主题里会以同样形态重现**，而解决它的模板写法是可以迁移的。

---

## 0. 模式总览

| # | 模式 | 解决的问题 | 关键文件 |
| --- | --- | --- | --- |
| P1 | 单点配置 partial | 同一配置在多处散读，口径不一致 | `util/author-config.html`、`util/edit-url.html`、`util/external-url.html`、`util/appearance.html` |
| P2 | 布尔参数解析器 | `default` 吞掉显式 `false`；partial 返回 bool 被包成字符串 | `util/bool-param.html` |
| P3 | rune 安全截断 | `slicestr` 越界 panic 终止整站构建 | `util/slice-runes.html` |
| P4 | 能力探测 + 形态规范化 | 跨 Hugo 版本 API 差异 | `util/locale.html` |
| P5 | URL 规范化 + 源头 scheme 拒绝 | 子目录部署 404；危险 scheme | `util/rel-url.html` |
| P6 | 空值 vs 站点根语义区分 | 头像 `src="/"` 破损图 | `util/avatar-url.html` |
| P7 | i18n 全量外置 + 构建期本地化 | 硬编码文案；前端猜语言 | `i18n/*.yaml`、`index.json` |
| P8 | Markdown render hooks | 图片管线、标题锚点、代码块 | `layouts/_default/_markup/*` |
| P9 | 首页布局可切换 | 多首页样式 | `partials/home/*.html` |
| P10 | 短代码组件 | 内容组件（提示块/tabs/steps/…） | `layouts/shortcodes/*` |
| P11 | 可选启用 + 向后兼容 | 新功能改变默认 URL 结构 | `util/author-config.html` |
| P12 | JSON-LD 结构化数据 | 双重编码、`</script>` 逃逸、零值 | `partials/head.html` |
| P13 | 搜索索引契约 | 索引字段、模式、竞态、失败语义 | `layouts/_default/index.json`、`assets/js/main.js` |

---

## P1. 单点配置 partial（唯一配置入口）

**【已证实】** 主题里凡是"多个模板都要读同一份复杂配置"的场景，都抽成一个 partial 作为**唯一入口**，返回一个 `dict`。

案例：`util/author-config.html` 返回 `{enabled, taxonomy, profiles}`；`util/edit-url.html` 返回 `{enabled, url}`；`util/external-url.html` 返回 `{isExternal, url, host}`。

**为什么**：
- 口径一致：启用条件、降级规则只写一次，改一处即可。
- 可测试：门禁可以直接对 partial 的**产物**断言，而不是猜模板在哪里判断。
- 防死链：如 `author-config` 在"声明启用但 taxonomy 未真正注册"时自动降级 `enabled=false`。

**调用约定**：
```
{{ $cfg := partial "util/author-config.html" . }}
{{ if $cfg.enabled }} ... {{ end }}
```

---

## P2. 布尔参数解析器（最重要的一个模式）

**【已证实】** `util/bool-param.html`。踩了两个 Go 模板的坑：

### 坑一：`default` 吞掉显式 `false`

```gotemplate
{{ .Params.flag | default true }}   {{/* flag: false 时返回 true！ */}}
```
Go 模板的 `default` 只判断"空值/零值"，而 `false` 恰好是 bool 的零值 → 被当成"未设置"替换成默认值。后果：文章级 `toc: false`、`comments: false`、`showDate: false`、`lightbox: false`、站点级 `search.enable=false` 全部**被静默忽略**。已在 0.128.0 / 0.148.0 / 0.162.0 / 0.166.0 / 0.167.0 复现。

### 坑二：partial 返回 bool 会被包成 `template.HTML`

```
partial 内 {{- $out -}}   -> 调用方拿到 template.HTML（字符串 "false"）
{{ if $x }}               -> 恒为真（哪怕内容是 "false"）
```
所以 partial **不能直接 `return $out`（bool）**，否则 `false` 变字符串 `"false"`，在任何 `{{ if }}` 里都是真——反而更隐蔽。

**结论**：`bool-param.html` 返回 `{{ dict "value" $out }}`，调用方取 `.value` 拿到**真 bool**。已验证 5 个版本行为一致。

### 取值语义（完整）

| 输入 | 结果 |
| --- | --- |
| 未设置 | `default` |
| bool `true/false` | **原值**（修复重点：`false` 不被吞） |
| string `"false"/"0"/"no"/"off"` | `false`（大小写、首尾空白不敏感） |
| string `""` | `default`（视为未设置） |
| string 其它非空 | `true` |
| int `0` | `false`，其它 `true` |
| 其它类型（表/切片） | `default` |

**附带收益**：用"遍历键 + 小写比较"而非 `isset .Params "showDate"`——后者在 0.167.0 上对 camelCase 键失效。

> **通用结论**：**任何"显式 false 必须生效"的开关配置，都不能用 `default`**。这是通用主题开发必须内建的规则。

---

## P3. rune 安全截断

**【已证实】** `util/slice-runes.html`。

- Go 的 `slicestr` **按 rune 计数**，长度不足会 panic `slice bounds out of range`，**终止整站构建**（一个空标题就能让整个站点构建失败 → BUG-P1-003）。
- `len` 返回**字节数**，不能判 rune 长度（`"中"` 的 `len=3`，`countrunes=1`）。

**模式**：
```gotemplate
{{- $text := .text | default "" -}}
{{- $n := int (.n | default 0) -}}
{{- if and (gt $n 0) (gt (countrunes $text) $n) -}}
  {{- slicestr $text 0 $n -}}
{{- else -}}
  {{- $text -}}   {{/* 不足则原样返回，绝不越界 */}}
{{- end -}}
```

**必须复用的地方**：任何"取标题前 N 个字符做摘要/卡片标题"的地方。**已证实**漏改一处（`index.json` 第 65 行裸 `slicestr`）就导致"中文正文 + contentLimit 整站构建失败"（BUG-R2-001）。

---

## P4. 能力探测 + 形态规范化

**【已证实】** `util/locale.html`。

1. **先探测再用**：解析 `hugo.Version` 的 major/minor，按能力分支。
   - `.Language.LanguageCode` 在 0.158 起弃用（打 WARN），替代 `.Language.Locale` 旧版本不存在。
   - 探测写法：`split (index (split hugo.Version "-") 0) "."` 取 major/minor。
2. **禁止 `cond` 做能力分支**：Go 模板的 `cond` **先求值两个分支**，会触发旧版本上不存在的字段访问错误。必须用 `if/else`。
3. **形态规范化**：不同版本给出的形态不一致（`zh-cn` vs `zh-CN`），统一输出 **BCP47**：语言子标签小写、地区子标签大写（`zh-CN`）——否则会出现 `og:locale="zh_cn"` 这类只在旧版本暴露的脏数据（BUG-R3-003）。

> **通用结论**：跨版本差异**一律先探测再用**，且探测**不能用 cond**；能力差异带来的输出形态不一致，必须在 helper 内**归一**，不能交给消费者。

---

## P5. URL 规范化 + 源头 scheme 拒绝

**【已证实】** `util/rel-url.html`。

- **子目录部署**：Hugo 的 `relURL` 对以 `/` 开头的路径**原样返回**（不补 baseURL 子目录）→ 资源 404。模式：先 `strings.TrimPrefix "/"` 再 `relURL`。
- **防重复**：菜单 URL 已被 Hugo 预解析为带 basePath 的路径，再转换会出现 `/blog/blog/...` → 先判断 `hasPrefix $u $home`。
- **源头安全**：调用方普遍 `| safeURL`，等于**信任**该 partial 的返回值。因此必须**在这里**拒绝 `javascript:` / `vbscript:` / `data:`(非 image)，否则配置里一个写坏的 cover/avatar/favicon 就变成可执行链接（SEC-03）。判定前先 `replaceRE `[\x00-\x20]+` ""`（浏览器会忽略 `"java\nscript:"` 里的换行）。
- **输出用 partial 内容而非 `return`**：部分 Hugo 版本（如 0.162）对 partial `return` 有兼容差异。

> **通用结论**：安全校验要在**被信任的源头**做，不要依赖每个调用方自觉；`safeURL` 的调用方越多，源头校验越关键。

---

## P6. 空值 vs 站点根语义区分

**【已证实】** `util/avatar-url.html`。

`rel-url.html` 把空串 / `/` 视为"站点根"——对菜单 `href="/"` 是**正确**语义，但对头像就是**破损图** `<img src="/">`。

**模式**：单独一个 helper，用 `site.Home.RelPermalink`（`baseURL=/`→`/`，`/blog/`→`/blog/`）判定，凡是"解析结果等于站点根"或"空白/危险 scheme"一律输出**空串**，调用方据此回退到字母头像/占位。

> **通用结论**：**同一个"规范化器"在不同语义下有不同正确结果**。共享逻辑要实现共享，但**语义边界要单独一层 helper 表达**，不要硬塞进通用工具。

---

## P7. i18n 全量外置 + 构建期本地化

**【已证实】** `i18n/{en,zh-CN,zh-TW}.yaml`；`check_i18n_hardcode.py`（扫到 0 个文件也失败）。

规则：
1. **UI 文案一律来自 `i18n/*.yaml`**，模板不得写死中文/英文。
2. **UI 日期一律 `i18n "common.dateFormat"`**；机器格式（RSS / JSON-LD / `<time datetime>` / 索引 `date`）走白名单。
3. **搜索索引同时存 `date`（机器 `YYYY-MM-DD`）与 `dateDisplay`（构建期 i18n 结果）**；前端**只负责原样输出 `dateDisplay`**，不得在 JS 里猜语言或再格式化一次（`check_date_format.py` 拒绝 `toLocaleDateString` / `Intl.DateTimeFormat`）。
4. **JS 也用 i18n**：把文案注入 `NEBULA_I18N`，不硬编码。

**跨版本陷阱【已证实】**：语言键与 i18n 文件名不匹配 → 0.128/0.148 全站 UI 文案**空串**（BUG-R3-001）。修复：`defaultContentLanguage='zh-CN'` + 显式 `[languages.zh-CN]`。另有 `[languages.*]` 顶层字段跨版本弃用（`label` 0.112 起 / `languageCode` 0.158 起）→ 改用零告警形态（根 `locale` + 仅 `weight`/`contentDir` + `params.label`）。

> **通用结论**：i18n 的"文案外置"只是第一步；**日期的本地化必须在构建期完成**，因为前端无法可靠判断站点语言集合。

---

## P8. Markdown render hooks

**【已证实】** `layouts/_default/_markup/` 下有 `render-image.html`、`render-heading.html`、`render-codeblock.html`、`render-blockquote.html`。

模式：
- `render-image`：走图片 Pipeline（`resources` 处理 + `srcset` + 尺寸占位 + `loading="lazy"`）；**检测能力**用 **MediaType 白名单**，不用 `reflect.IsImageResourceProcessable`（0.128 不存在）。
- `render-heading`：锚点 id 与 TOC 对齐。
- `render-codeblock`：代码高亮、复制按钮、语言标签。

**构建覆盖陷阱【已证实】**：`render-image` 的"图片处理分支"只有在**夹具含真实可处理图片**时才被构建到。`gen_testdata` 缺 Pillow 会跳过 `zz-images-bundle` → 整个分支**永不进入构建** → 0.128 上的不兼容长期未被发现。因此 CI 有"边界夹具存在性 + `grep -q 'srcset='`"步骤。

> **通用结论**：render hook 的**分支覆盖依赖夹具**。必须构造能触发每个分支的夹具，并在 CI 里断言"该分支确实产出了特征产物"（如 `srcset=`）。

---

## P9. 首页布局可切换

**【已证实】** `partials/home/{cards,profile,hero,landing,latest}.html` + `_default/home-showcase.html`。

模式：
- 站点级 `params.home.layout` 选择；**非法/空值安全回退 `cards`**。
- **布局切换不得影响 feeds / 索引**：`check_home_layouts.py` 断言切换布局后 `index.json` 与 `index.xml`（去 `lastBuildDate`）**逐字节一致**。
- 每种布局有**可区分结构标记**（如 `home-profile`），供门禁断言。

> **通用结论**：任何"展示层可切换"的功能，都必须断言**它对数据/索引层零影响**——否则容易出现"换了个布局，RSS 内容悄悄变了"。

---

## P10. 短代码组件

**【已证实】** `layouts/shortcodes/{notice,badge,button,details,filetree,gallery,steps,step,tabs,tab}.html`，配套 `partials/components/{tabs,steps}.html` + `assets/js/tabs.js`。

模式要点：
- **提示块 5 类型 + GitHub alert 语法**；未知类型安全回退。
- **零 JS 优先**：tabs/steps 尽量纯 CSS/HTML，可交互部分收敛到最小 JS。
- **短代码参数要转义**：filetree/badge/button/details 的路径特殊字符转义、变体白名单、**URL scheme 校验含空白绕过**。
- **禁止混用短代码参数 / 换行绕过不可构造**（回归断言）。
- **跨版本**：0.128–0.167 矩阵 + 反证。

`check_content_components.py` 有 **213 项**断言，覆盖上述全部。

> **通用结论**：内容组件的真正难点不是"渲染出来"，而是**极端输入下的转义、非法参数回退、以及旧版本兼容**。

---

## P11. 可选启用 + 向后兼容（新功能不改默认）

**【已证实】** `util/author-config.html` + `layouts/_default/term.html` + `partials/author-profile.html`。

作者档案页（M16）最初被列为"接受为限制"，理由是"新增 taxonomy 会改变默认 URL 结构"。**该顾虑通过可选启用设计完全化解**：

- 默认 `params.authors.pages=false` 且**站点不注册 `authors` taxonomy** → 主题**不输出任何作者结构**，产物与"无本功能"基线主题 `37c3da6` **规范化后逐字节一致**（BC1）。
- 启用需**同时**满足：注册了 taxonomy **且** `pages=true`；缺一即降级 `enabled=false`（防死链）。
- **口径澄清【已证实】**：`pages` 只控制"主题是否渲染资料结构"，**不控制** Hugo 是否为已注册 taxonomy 生成 `/authors/` 页面。**不产生 `/authors/` 的唯一方法是不注册 taxonomy**（exampleSite 启用→291 页，不注册→286 页，差 5 个作者页）。

> **通用结论**：想加"可能改变 URL 结构"的功能，正确做法不是"接受限制"，而是**把它做成默认关闭的可选层**，并用"与基线主题逐字节一致"作为回归门禁。

---

## P12. JSON-LD 结构化数据

**【已证实】** `partials/head.html`（`dict` + `jsonify | safeJS` 一次输出）。

历史问题：
- **双重编码**（BUG-P2-004 / SEC-04）：逐字段编码再整体编码 → 修复为整体 `dict` 一次 `jsonify`。
- **`</script>` 逃逸**：转义为 `\u003c/script\u003e`。
- **零值日期泄漏**：缺 `date` 的文章 JSON-LD **不输出**日期字段，绝不出现 `0001-01-01`（BUG-P3-001）。
- **空作者**：未配置作者时**省略** `author` 字段，不输出 `author.name:null`（BUG-R2-005）。
- 与 `og:title` **交叉校验**。

> **通用结论**：JSON-LD 要**整体构造再一次性序列化**；空值/零值字段宁可省略也不输出 null/零日期。

---

## P13. 搜索索引契约

**【已证实】** `layouts/_default/index.json` + `assets/js/main.js`。

契约（不可回退）：索引含 `date`（机器）+ `dateDisplay`（构建期 i18n）+ 旧字段（title/url/summary/content/key/tags/categories/series）一个不少；三种模式 `auto`/`single`/`shard`；`chunk` 按体积分块。

模式要点：
- **能力探测**：分片依赖 `resources.Publish`（0.166+）；低版本 auto **回退单文件** + WARN，显式 `shard` **明确报错**（不静默降级）。
- **竞态**：先 await 索引再渲染，用 token 丢弃过期渲染；索引未就绪显示加载态，**不误报"无结果"**。
- **失败语义**：主索引失败明确报错 + 重试；分片部分失败提示"结果可能不完整"，**不伪装成"没有找到"**。
- **高亮安全**：`esc` **之后**再做正则替换；`<mark>` 不嵌套；场景串不能产生 XSS。
- **scheme 白名单**：搜索结果链接只放行同源相对路径与 http(s)，非法项渲染为不可点击文本（SEC-01）。
- **series 参与评分**（BUG-P2-005）。

> **通用结论**：搜索是"索引构建 + 前端消费"的跨端契约。**日期本地化在构建端完成**、**失败要区分"没找到"与"没加载成功"**、**高亮必须先转义后替换**——这三条是通用规则。

---

## 10. 迁移到通用主题 Skill 的建议

| 可固化为通用规则 | Nebula 专有（作教学案例，不作规则） |
| --- | --- |
| "显式 false 不能用 `default`"（P2） | `bool-param.html` 的具体实现 |
| "`slicestr` 按 rune，`len` 是字节"（P3） | `slice-runes.html` 文件名 |
| "能力探测不能用 `cond`"（P4） | `locale.html` 的具体版本阈值 |
| "安全校验在被信任的源头做"（P5） | `rel-url.html` 的具体 scheme 列表 |
| "同规范器不同语义要分层"（P6） | 头像这一具体场景 |
| "日期本地化在构建期完成"（P7） | `dateDisplay` 字段名 |
| "render hook 分支依赖夹具"（P8） | `zz-images-bundle` 夹具名 |
| "新功能做成默认关闭的可选层"（P11） | `params.authors.pages` |
| "JSON-LD 整体构造再序列化"（P12） | Nebula 的具体 schema 字段 |
| "索引/搜索是跨端契约"（P13） | 三种模式的具体阈值 |

**【结论】** 通用 Skill 应写成**模式 + 反例 + 规则**，而不是"照抄 Nebula 的 partial"。
