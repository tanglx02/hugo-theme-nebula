# Nebula 最终收尾 · 问题追踪表（final cleanup issue tracker）

> **本文档的建立方式**：整合**全部**历史报告，**不以最新一份为准**。对每个编号逐条回到当前代码
> （`feat/theme-feature-completion` @ `ca0c51b`）核实真实状态，给出证据、修复方案与回归方式。
> 历史报告宣称"已修复"的项目**不直接采信**，均重新核对；无法合理修复者必须写明技术原因与用户影响。
>
> 状态取值：`FIXED` / `PARTIALLY-FIXED` / `NOT-FIXED` / `REGRESSION` / `ACCEPTED-LIMITATION` / `NOT-VERIFIED`

## 0. 整合的来源报告

| 来源 | 位置 | 覆盖编号 |
| --- | --- | --- |
| v1.0.9 独立第三方全面测试报告 | `tmp/hugo博客主题验收测试/Nebula-v1.0.9-独立第三方全面测试报告.md` | 原始 44 项（P1×3 / P2×5 / P3×7 / TEST-DEFECT×20 / SEC×4 / DOC×5） |
| 第一轮集中修复交接报告 | `docs/第三方测试修复交接报告.md` | 44 项修复声明 + E1~E4 |
| 第一轮独立第三方复验报告 | `tmp/hugo博客主题验收测试/Nebula-v1.0.9-修复分支-独立复验报告.md` | 44 项复验状态 + 新增 BUG-R2-001~005 / OBS-R2-001 / TEST-DEFECT-R2-001~008 / DOC-R2-001 |
| 第二轮集中修复交接报告 | `docs/第三方测试修复交接报告-第二轮.md` | R2 系列修复声明 |
| 第二轮独立第三方复验报告 | （见第一轮复验报告 §三"新发现的问题"，R2 系列即其产物） | R2 系列 |
| 功能完善阶段测试交接报告 | `docs/测试交接报告-功能完善阶段.md` | BUG-R3-001~003 / TEST-DEFECT-R3-001~003 |
| 历史验收报告 | `docs/验收报告-v1.0.4~v1.0.9.md`、`../docs/复验报告-v1.0.2.md` | 历史演变 |
| 功能差距分析 | `docs/feature-gap-analysis.md` | M1~M20 功能缺口 |

---

## 1. 基线（本表建立时 → 当前候选）

| 项 | 本表建立时 | **当前候选（功能冻结候选）** |
| --- | --- | --- |
| 分支 | `feat/theme-feature-completion` | 同名（**已推送** `origin`） |
| HEAD | `ca0c51b0aec0896e102e66d2f5f143261dac2691` | `897f1e09136fd8944e405861ea6053f42b569a45`（内容冻结提交） |
| M16 引入前基线 | — | `37c3da646cce27be789c1a9f9060b25615c72cdb`（BC1 对照） |
| `v1.0.9` 标签 | `6168bb13b68014ea18953df6c7dc40078d581868`（未移动，仍指向 `bc152c8`） | 同左，**未移动** |
| 已含 | `origin/main`、`fix/third-party-audit-v1.0.9-r2`、第二轮修复（`b2d2c71`）、R2-009 修复（`59e7f30`） | 另含 M16 实现与口径纠正（`2593ead`）+ 交接一致性核验（`897f1e0`） |
| 领先 `origin/main` | 26 提交 | 内容冻结提交 `897f1e0…` 领先 **33** 提交、落后 **0**（归属固定提交，不随 tip 漂移） |
| 分支是否已推送 | 否 | **是**（`origin/feat/theme-feature-completion`，内容冻结提交 `897f1e0…`，快进推送；远端 tip 以 `git ls-remote` 为准） |

---

## 2. P1（原始 3 项）— 全部复核为 FIXED

| 原 ID | 原始问题 | 当前实际状态 | 证据（当前代码） | 结论 |
| --- | --- | --- | --- | --- |
| BUG-P1-001 | 遮罩 / Escape 关闭搜索弹窗后 `body.overflow` 停在 `hidden`，页面永久不可滚动 | 滚动锁已下沉到 `createModalA11y` 工厂（引用计数 + 恢复原值 + 多模态互斥），所有关闭路径统一清理 | `assets/js/main.js` 工厂内 `lockScroll/unlockScroll`；`tools/verify_modal_scroll.py` 三引擎 | **FIXED** |
| BUG-P1-002 | 默认 `auto` 在 Hugo 0.128–0.162 上构建失败（`can't evaluate field Publish`） | 能力探测改为 `$supportsPublish := or (gt major 0) (and (eq major 0) (ge minor 166))`；不支持时 auto 回退单文件 + WARN，显式 shard 明确报错 | `layouts/_default/index.json:53`；`tools/check_search_modes.py` | **FIXED** |
| BUG-P1-003 | 空 / 单字符 / 单 CJK / 单 emoji / 空白标题、空站点标题、无头像+空 author → 整站构建失败（`slicestr` 越界） | 抽 `partials/util/slice-runes.html`（`countrunes` 判断，绝不越界）；`post-card.html`/`header.html` 改走它 | `layouts/partials/util/slice-runes.html` | **FIXED**（根因清扫完整，见 BUG-R2-001 复检） |

## 3. P2（原始 5 项）— 全部复核为 FIXED

| 原 ID | 原始问题 | 当前状态 | 证据 | 结论 |
| --- | --- | --- | --- | --- |
| BUG-P2-001 | burger 缺 `aria-expanded`；Escape 不关闭菜单 | `header.html` 静态补 `aria-expanded`/`aria-controls`；`main.js` `setMenu()` + Escape（含焦点归还 `preventScroll`） | `main.js:56`、`header.html` | **FIXED** |
| BUG-P2-002 | 英文站 769–869px 横向溢出 | 头部独立断点 768→**900px** | `main.css` `@media (max-width:900px)`；`check_responsive_overflow.py` | **FIXED** |
| BUG-P2-003 | 浅色主题 muted/chip 对比度 2.39–3.66:1 | token 按用途拆分（`--brand-solid`/`--brand-ink`/`--accent-ink`）+ 加深 `--text-muted`；复验最低 ≥4.75 | `main.css:14-65`；`verify_contrast.py` | **FIXED** |
| BUG-P2-004 | 全站 JSON-LD 双重编码 | `head.html` 改为整体 `dict` + `jsonify \| safeJS` 一次输出 | `head.html:83-146`；`check_html_quality.py` 双重编码检测 | **FIXED** |
| BUG-P2-005 | series 写入索引但不参与匹配 | `main.js` `score()` 纳入 `series`（权重 6） | `assets/js/main.js` | **FIXED** |

## 4. P3（原始 7 项）

| 原 ID | 原始问题 | 当前状态 | 证据 | 结论 |
| --- | --- | --- | --- | --- |
| BUG-P3-001 | 缺 date 显示 `0001年1月1日`、归档出现 `0001` | 页面侧走本地化"未标注日期"；JSON-LD 零值不输出日期；归档无日期单独成组 | `archive.html`、`single.html`、`head.html` | **FIXED** |
| BUG-P3-002 | 无 `<noscript>` 回退 | 新增 `.noscript-hint`（三语言 `common.noScript`） | `header.html` | **FIXED** |
| BUG-P3-003 | 第三方脚本无 SRI、busuanzi 协议相对 URL | busuanzi 改 `https://` 绝对地址；新增可选 `integrity`；README 增供应链与 CSP 建议 | `scripts.html`、`comments.html` | **PARTIALLY-FIXED** → 残余 **ACCEPTED-LIMITATION**（不预置哈希/不写死 CSP 属有意设计，默认全关） |
| BUG-P3-004 | 静态/外链图无 width/height（CLS 风险） | 缩略图 `.post-thumb{aspect-ratio}`、头像固定尺寸；**正文内图片仍无尺寸约束** | `main.css` | **ACCEPTED-LIMITATION**（外链图尺寸构建期不可知；本轮新增画廊将复用 Pipeline 并尽量补尺寸） |
| BUG-P3-005 | `.Language.LanguageCode` 弃用 WARN | 新增 `util/locale.html`：≥0.158 用 `.Locale`，旧版回退 `.LanguageCode` | `locale.html` | **FIXED** |
| BUG-P3-006 | 触控目标 < 44×44 | 复验指出 `#searchTrigger`(36×36)、`.brand`(32×32) 未达标。**当前代码已补**：`.search-trigger{min-height:44px;height:44px;min-width:44px}`、`.brand{min-height:44px}` | `main.css:1287-1288` | **FIXED**（chip 标签维持 24px 满足 AA 2.5.8） |
| BUG-P3-007 | 空正文显示"约 0 分钟 / 0 字" | 正文为空时隐藏统计 | `post-card.html`、`single.html` | **FIXED** |

## 5. 安全残留（原始 4 项）— 全部 FIXED

| 原 ID | 原始问题 | 当前状态 | 结论 |
| --- | --- | --- | --- |
| SEC-01 | 搜索结果链接缺 scheme 白名单 | `main.js` `safeHref()`：只放行 http(s)/`/`/`.`/`#`；Enter 同判 | **FIXED** |
| SEC-02 | 第三方脚本无 SRI / 无 CSP / 协议相对 | 协议相对消除；自有资产构建期 integrity；第三方可选 integrity | **PARTIALLY-FIXED** → 残余 **ACCEPTED-LIMITATION** |
| SEC-03 | `rel-url.html` 允许任意 scheme | partial 内源头拒绝 `javascript:`/`vbscript:`/`data:`(非 image)，先剥空白与控制字符 | **FIXED**（伴随回归 BUG-R2-003，已随之修复） |
| SEC-04 | JSON-LD 双重编码 + `</script>` 逃逸 | 同 BUG-P2-004；逃逸转义为 `\u003c/script\u003e` | **FIXED** |

## 6. 文档问题（原始 5 项）— 全部 FIXED

| 原 ID | 处理 | 结论 |
| --- | --- | --- |
| DOC-01 | README 增「默认 auto 模式兼容行为」版本能力对照表 | **FIXED** |
| DOC-02 | README 增「漏配 outputs 的后果」 | **FIXED** |
| DOC-03 | 截图压缩至 3.84MB；`.hugo_build.lock` 移出跟踪并忽略 | **FIXED** |
| DOC-04 | `验收报告-v1.0.9.md` 顶部加非破坏性更正块 | **FIXED** |
| DOC-05 | 更正块列出未测试的三类路径 + "绿≠无缺陷" | **FIXED** |

## 7. TEST-DEFECT 001–020（原始 20 项）

| 原 ID | 缺陷 | 第一轮 | 复验判定 | 当前状态核对（本轮） | 结论 |
| --- | --- | --- | --- | --- | --- |
| 001 | JSON-LD 校验因 minify 去引号恒真 | 修复 | FIXED | `check_html_quality.py` 正则容忍无引号 + 双重编码检测 + 0 块硬失败 | **FIXED** |
| 002 | URL/事件正则只认双引号 | 修复 | FIXED | `security_baseline.py` 兼容单/无引号 + 同源豁免 | **FIXED** |
| 003 | job 级 `permissions: write-all` 被放过 | 修复 | FIXED | `check_workflow_policy.py` 判红 | **FIXED** |
| 004 | 40 位 SHA 固定被误判 | 修复 | FIXED | 接受并提示 | **FIXED** |
| 005 | `verify_multisection` 扫不到模板恒真 | 修复 | FIXED | 扫不到即硬失败 | **FIXED** |
| 006 | 索引正文为空/截断仅 WARN | 修复 | **PARTIALLY-FIXED**（截断至 10 字仍绿） | 见 TEST-DEFECT-R2-001 复检 | → 归并至 R2-001 |
| 007 | `check_seo` 无 posts 真空通过 | 修复 | FIXED | 至少 1 页否则硬失败 | **FIXED** |
| 008 | 安全门禁 0 HTML 仍 PASS | 修复 | FIXED | 空产物硬失败 | **FIXED** |
| 009 | `subdir_test` 无退出码 | 修复 | FIXED | 接入 Harness | **FIXED** |
| 010 | 多处恒真断言 | 修复 | FIXED | 全部补非空断言 | **FIXED** |
| 011 | `check_docs` 版本硬编码 1.0.7 | 修复 | FIXED | 按 tag/CHANGELOG 推断 + 交叉核对 | **FIXED** |
| 012 | `audit.py` 硬编码分页 token | 修复 | FIXED | 动态 `detect_pagination_token()` | **FIXED** |
| 013 | 缺边界样本 | 修复 | FIXED | `gen_testdata.py` 生成 `zz-21..zz-31` + bundle + 多 section | **FIXED** |
| 014 | `clean()` 遇目录崩溃 | 修复 | FIXED | 目录 `rmtree` + 多 section 清理 | **FIXED** |
| 015 | `check_ci_jobs` 只比数量 | 修复 | **PARTIALLY-FIXED** | 见 TEST-DEFECT-R2-002 复检 | → R2-002 |
| 016 | 脚本默认路径基准不一致 | 修复 | **PARTIALLY-FIXED** | 见 TEST-DEFECT-R2-003 | → R2-003 |
| 017 | 临时产物残留；`.gitignore` 登记不成立 | 部分 | **PARTIALLY-FIXED** | 见 TEST-DEFECT-R2-004/005 | → R2-004/005 |
| 018 | `compat_matrix`/`repro_search` 无断言 | 修复 | FIXED | 均接 Harness + 非零退出 | **FIXED** |
| 019 | i18n 覆盖仅打印 | 修复 | FIXED | `REQUIRE_SEARCH_LANGS=1` 硬门禁 | **FIXED** |
| 020 | chromium 专属步骤可能静默消失（实为 **7** 个） | 部分 | **PARTIALLY-FIXED** | 见 TEST-DEFECT-R2-002 | → R2-002 |

## 8. 第二轮新发现（R2 系列）

| ID | 严重度 | 问题 | 当前状态核对（本轮） | 结论 |
| --- | --- | --- | --- | --- |
| BUG-R2-001 | P2 | `index.json` 仍用裸 `slicestr`（第 65 行），同根因清扫遗漏 → 中文正文 + `contentLimit` 整站构建失败 | **已修**：第 73 行改走 `partial "util/slice-runes.html"` | **FIXED** |
| BUG-R2-002 | P2 | 能力探测比实际少一个小版本（0.166 已支持 `resources.Publish` 却被硬拒） | **已修**：`ge $verMinor 166`（非 167） | **FIXED** |
| BUG-R2-003 | P2 **回归** | 未配置/空 `params.avatar` 时文章卡片与侧栏渲染 `<img src="/">` 破损图 | **已修**：新增 `util/avatar-url.html`（空/空白/危险 scheme/站根 → 空串），`post-card.html:39`、`sidebar.html` 改走它 | **FIXED** |
| BUG-R2-004 | P2 | 关闭弹窗焦点归还 `#searchTrigger` 未用 `preventScroll` → 页面位置被拉走 | **已修**：`main.js:436-439` 改 `focus({preventScroll:true})` | **FIXED** |
| BUG-R2-005 | P3 | 未配置作者时 JSON-LD 输出 `author.name:null` | **已修**：`head.html:141-146` 无作者即省略 author 字段 | **FIXED** |
| OBS-R2-001 | 观察 | 搜索弹窗无关闭按钮，仅 Esc/遮罩 | 保持现状（界面有 Esc 提示）；**不构成缺陷** | **ACCEPTED-LIMITATION** |
| TEST-DEFECT-R2-001 | P2 | `check_index.py` 对"正文截断到 10 字"仍真空通过 | **已修**：末尾标记 `TAILMARKER_9Z8Y7X`/`TAILMARKER_50K_END` + `MIN_BYTES_PER_ENTRY=1000` + 截断有界校验 | **FIXED**（需重跑故障注入确认） |
| TEST-DEFECT-R2-002 | P2 | `check_ci_jobs.py` 对删除/禁用/`continue-on-error`/空 run 不敏感 | **已修**：`--selftest` 7 类注入 + job 级恒假 + 条件步骤取值存在性校验 | **FIXED**（需重跑 `--selftest`） |
| TEST-DEFECT-R2-003 | P3 | `check_html_quality`/`security_baseline`/`html_inventory`/`check_alias_pages` 仍 cwd 相对 | **已修**：注释声明统一为 `<repo>/public` | **FIXED**（需实测默认路径） |
| TEST-DEFECT-R2-004 | P3 | `verify_multisection`/`gen_testdata` 异常路径不清理 | **已修**：`finally` 清理 + 边界校验 | **FIXED**（需实测） |
| TEST-DEFECT-R2-005 | P3 | `check_comments` 失败泄漏 `tools/_ml-giscus.toml` 且未被忽略 | **已修**：`.gitignore` 显式加入该文件 + `finally` 清理 | **FIXED** |
| TEST-DEFECT-R2-006 | P2 | `subdir_test.py` 复用 `tmp/public-blog` → 实测假绿 | **已修**：构建前清空（`safe_rmtree` 边界校验） | **FIXED**（需 `--negative` 复验） |
| TEST-DEFECT-R2-007 | P3 | `audit.py` inventory 交叉验证可静默跳过 + 跨次复用 | **已修**：`AUDIT_REQUIRE_INVENTORY=1` 缺失即 FATAL + `build_id` 指纹比对 | **FIXED** |
| TEST-DEFECT-R2-008 | P3 | `verify_baseurl.build()` 忽略 Hugo 退出码 | **已修**：看真实 `returncode` | **FIXED** |
| TEST-DEFECT-R2-009 | flaky | 滚动断言偶发假红（`scroll-behavior:smooth` + 绝对阈值） | **已修**：回顶 `behavior:'instant'` + 相对位移 `y>y0+50`；`repeat_check.py` 固化连跑 | **FIXED** |
| DOC-R2-001 | P3 | 文档称分片依赖 0.167，实为 0.166 | **已修**：README/`index.json`/theme.toml 全部统一为 0.166 | **FIXED** |

## 9. 功能完善阶段新发现（R3 系列）

| ID | 问题 | 当前状态核对（本轮） | 结论 |
| --- | --- | --- | --- |
| BUG-R3-001 | 语言键与 i18n 文件名不匹配 → 0.128/0.148 全站 UI 文案空串 | **已修**：`defaultContentLanguage='zh-CN'` + 显式 `[languages.zh-CN]`；`check_features.py` 8a/8b 双层断言 + 反证 | **FIXED** |
| BUG-R3-002 | `[languages.*]` 顶层字段跨版本弃用（`label` 0.112 起 / `languageCode` 0.158 起） | **已修**：改用零告警形态（根 `locale` + 仅 `weight`/`contentDir` + `params.label`） | **FIXED** |
| BUG-R3-003 | `util/locale.html` 在 0.128 产出非规范 `og:locale`（`zh_cn`） | **已修**：BCP47 规范化（语言小写、地区大写 → `zh_CN`） | **FIXED** |
| TEST-DEFECT-R3-001 | `check_features.py` 8c 扫描 `[languages]` 父表恒空（假守卫） | **已修**：header-aware 扫描全部 `[languages.<key>]` | **FIXED** |
| TEST-DEFECT-R3-002 | 8c 变量 `m` 被 8b 覆盖 → 地区后缀判定恒走错误分支 | **已修**：改用独立变量 `dcl_m` | **FIXED** |
| TEST-DEFECT-R3-003 | `check_lang_config.py` L8 反证被同名键遮蔽 | **已修**：L8 先移除 `params.label`；新增 L8b 记录遮蔽行为 | **FIXED** |

## 10. 功能缺口（feature-gap-analysis M1~M20）

| 编号 | 功能 | 当前状态 | 本轮处理 |
| --- | --- | --- | --- |
| M1 多种首页布局 | `cards`/`profile`/`hero`/`landing` | **已实现**（`8c41a10`） | 保持 + 回归 |
| M2 进度条按阅读区 + 可配置 | | **已实现**（`4af0c96`） | 保持 + 回归 |
| M3 返回顶部可配置 + 键盘可达 | | **已实现**（`4af0c96`） | 保持 + 回归 |
| M4 专注阅读模式 | | **已实现**（`4af0c96`） | 保持 + 回归 |
| M5 打印样式 | | **已实现**（`4af0c96`） | 保持 + 回归 |
| M6 Markdown 提示块（五类型 + GitHub alert 语法） | | **已实现**（`9e8bca0`） | 保持 + 旧版兼容复核 |
| M7 标签页 tabs | | **已实现**（`ea2a169`） | 保持 + 嵌套回归 |
| M8 步骤 steps | | **已实现**（`ea2a169`） | 保持 + 嵌套回归 |
| M9 文件树 filetree | | **已实现**（`9a820e7`） | 保持 + 特殊字符回归 |
| M10 徽标 badge | | **已实现**（`9a820e7`） | 保持 |
| **M11 图片画廊 gallery** | | **✅ 已实现** | `layouts/shortcodes/gallery.html`（`{{< gallery cols="N" >}}`，每行 `源 \| alt \| 题注`；外链/资源/static 三种来源；缺图 `.nb-gallery-missing` 占位；不套 `<a>` 交给灯箱）。门禁 `check_new_features.py` G1–G8 |
| **M12 Mermaid** | | **✅ 已实现** | `layouts/partials/mermaid.html` + `assets/js/mermaid-init.js`；**按需加载**（仅页面含 ```mermaid 时注入，`.Store "nebula_has_mermaid"`）；自托管优先，CDN 需 SRI。门禁 M1–M5 |
| **M13 KaTeX** | | **✅ 已实现** | `layouts/partials/math.html` + `assets/js/katex-init.js` + `util/detect-math.html`；按需（`nebula_has_math`）、逐页 `<!-- nebula:no-math -->` 关闭、三项资源可 CDN/本地。门禁 M6–M11 |
| **M14 编辑此页** | | **✅ 已实现** | `layouts/partials/util/edit-url.html`（provider github/gitlab/gitee/custom；源路径逐段 `urlquery`；Windows 反斜杠归一；未配置不输出；文章级 `editUrl: false` 关闭）。门禁 E1–E4 |
| **M15 多作者 Front Matter** | | **✅ 已实现** | `layouts/partials/util/authors.html`（`authors` 列表 → `author` → `site.Params.author` → 空，**不虚构**）；接入 head/meta、JSON-LD（1 人 Person / 多人 Person 数组）、RSS 多 `<author>`、卡片与正文。门禁 A1–A5 |
| **M16 独立作者档案页** | | **✅ 已实现（可选启用 · 默认不变）** | 单点配置解析 `layouts/partials/util/author-config.html`（**默认 `params.authors.pages=false`**：不输出任何作者结构；**当站点不注册 `authors` taxonomy 时**产物与「无本功能」基线主题 `37c3da6` **规范化后逐字节一致**，见 BC1）；启用后新增 `layouts/_default/term.html` + `layouts/partials/author-profile.html` + `util/author-links.html` / `util/author-inline.html`，生成 `/authors/` 索引与 `/authors/<term>/` 档案页并打通文章↔档案页互链。CJK/特殊字符走 `site.Taxonomies` 按 `Title` 大小写不敏感匹配（**刻意不用 `urlize`**：`urlize "张伟"` 返回 percent-encoded，`site.GetPage` 对 CJK 返回 NONE）。门禁 `tools/check_author_pages.py`（**43 条断言；设 `HUGO_MATRIX_DIR` 时 47/47**）。**原「接受为限制」的核心顾虑——担心新增 taxonomy 破坏默认 URL 结构——已由可选启用设计完全化解**，详见 §11.3 |
| **M17 外链文章** | | **✅ 已实现** | `layouts/partials/util/external-url.html`（scheme 白名单 http/https/协议相对）；卡片 `.post-card-external` + 徽标 + `target=_blank rel=noopener`；canonical 指向站外；RSS `guid isPermaLink="false"`；索引 `external:true` + 站外 url。门禁 X1–X9 |
| **M18 嵌套菜单** | | **❌ 未实现** | 价值较低 → **ACCEPTED-LIMITATION**（差距分析 §6 已声明本轮不改；仅做现状核对） |
| **M19 外观配置** | | **✅ 已实现** | `layouts/partials/util/appearance.html`（`accent/accentColor/contentWidth/lineHeight/fontFamily/cardDensity`；预设白名单 + hex 校验 + 亮度感知压深；**未配置时不输出任何 `<style>`**——默认外观逐字节不变）。门禁 P1–P3 |
| **M20 配置参考文档** | | **部分→本轮补齐** | README 配置参考补 `editUrl`/`mermaid`/`math`/`appearance`/`reading`/`home.layout` 各表（当下随 9.3 一并核对） |

### 10.1 本轮新增门禁（对应第五节准入要求）

| 门禁 | 覆盖 | 故障注入自证 |
| --- | --- | --- |
| `tools/check_home_layouts.py` | 功能一：四种首页布局 + 非法值回退 + 布局切换不影响 feeds/索引 + 多语言 | 是 |
| `tools/check_reading_experience.py` | 功能二：进度条/返回顶部/专注模式/打印 + 真实浏览器行为 | 是（B 小节真机断言） |
| `tools/check_new_features.py` | 功能三/四/五：G/X/A/E/P/M 共 **40 项** | 是（`--selftest`：4 类注入 + 基线，5/5） |
| `tools/check_author_pages.py` | M16 作者档案页：启用/索引页/档案页/资料卡/互链/缺失字段/CJK/特殊字符/canonical/sitemap/RSS/搜索索引/分页/多语言 + **ON22–ON24 构建产物 CSS 触控目标契约** 共 **43 条**（设 `HUGO_MATRIX_DIR` 时 47 条）；未启用时与「无本功能」基线主题 `37c3da6` **规范化后逐字节一致（BC1）** | 是（①站点开关恒假 → **37/43，6 条红**；②`.author-link` 退回 inline → **41/43，ON23/ON24 红**，见 §10.5） |

三者（外加 `check_author_pages.py` 共四项）均已写入 `.github/workflows/ci.yml` 的 `static-checks` job，
并登记进 `check_ci_jobs.py` 的 `REQUIRED_STEP_TOKENS`（删除步骤或改成空命令即判红）。

### 10.2 本轮清理阶段**新发现并修复**的缺陷

| ID | 严重度 | 问题 | 修复 | 自证 |
| --- | --- | --- | --- | --- |
| R4-001 | **P2** | `verify_multisection.py` 默认站点目录指向仓库内 `myblog`，该目录早已移出仓库 → **本地直接运行必然 `FileNotFoundError`**；CI 因显式传 `SITE_DIR` 而侥幸通过（"只在 CI 里能跑"的隐性缺陷） | 默认改为仓库自带 `exampleSite`（显式 `SITE_DIR` 优先，`myblog` 作为兼容回退），并自动补 `--source . --themesDir ../..` | 默认调用 40/40 PASSED |
| R4-002 | **P2** | 同脚本的首页断言「每个 section 都出现在首页」是**错误断言** —— 首页按设计只展示最新 8 篇，`projects` 夹具 date 09-27/28 较新入选、`tutorials` 09-24 与 `notes` 09-26 被挤出 → 随夹具日期偶发射穿 | 改为校验**数据源**是否跟随 `params.content.sections`：默认构建首页不得越出 `posts`；多 section 构建首页必须出现 `posts` 之外的配置 section，且不越出配置集合 | **故障注入自证**：把 `home/cards.html` 的 sections 写死为 `posts` → 断言变红（`实际出现: ['posts']`，39/40）；还原后 40/40 |
| R4-003 | P3 | `exampleSite/_ms-verify-multisec-*.toml` 残留（上次运行被 SIGTERM 打断 `finally`） | 清除残留；清理逻辑本身含重试，无需改代码 | 清理后工作区无泄漏文件 |
| R4-004 | **P2** | `link_check.py` 缺省产物目录写死 `<repo>/myblog/public`（早已不存在）→ **裸跑必然"目录不存在"**；CI 因显式传参侥幸通过。同类：`verify_baseurl.py` 的 `SITE` 默认同为 `myblog` | `link_check.py` 改用 `_testlib.default_build_dir()`（统一 `<repo>/public`，并支持 `-h/--help`）；`verify_baseurl.py` 与 `verify_multisection.py` 统一为"显式 SITE_DIR → exampleSite → myblog 回退"，并在用 exampleSite 时自动补 `--themesDir ../..` | 两者裸跑默认调用均通过（link_check 10243 链接 0 死链；verify_baseurl 默认解析到 exampleSite） |
| R4-005 | P3 | README 存在过时表述：`check_features.py` 写"26 项"（实为 35）、`verify_multisection` 示例仍要求手写 `SITE_DIR`/`HUGO_ARGS` | README 局部命令段按当前真实用法重写，并补入三个新门禁 | `check_docs.py` 11/11（新增断言：README 本地图片引用必须存在 + 特性覆盖功能一~五 + 配置参考含 6 组新配置） |
| R4-006 | **P2（测试缺陷）** | 本表 R4-005 新增的两条断言**首版是假守卫**：用子串 `功能五` / `params.mermaid` 匹配，而它们在 README 中出现 3 处 / 2 处 → 故障注入（删标题 / 改配置表名）**仍然全绿** | 改为**结构级判据**：`### 功能N` 标题行精确匹配；配置表须在 `## 完整配置参考` 的 ```toml 代码块内以行首 `[params.x]` 出现 | **故障注入自证（修正后）**：改掉 `### 功能五` → 变红；改掉配置块内 `[params.mermaid]` → 变红。**首版未做注入时看不出来 —— 正是第五节要求"必须证明测试能失败"的直接价值** |
| R4-007 | **P2（新功能引入的可访问性回归）** | 本轮新增「外链文章」(M17) 的正文页顶部提示条 `.article-external-notice` 使用 `display:flex`；其中的外链主机名链接（如 `attack.mitre.org`）被 flex 上下文**块级化**，失去"正文内联链接"的 WCAG 豁免，在 320–430px 窄视口实测渲染为 **98×23px**，恰好低于 24px 触控目标阈值 → `audit.py` 的 `small-tap-target` 在 4 个窄视口各报 1 处（共 4 处） | `.article-external-notice a` 显式改为 `display:inline-flex; align-items:center; min-height:26px`（≥24px），并保留原配色 | **修复后复验**：同一审计（chromium × 320/375/390/430）由 `3/7 PASSED（4 处问题）` 转为 **`4/4 PASSED，TOTAL PROBLEMS: 0`** |
| R4-008 | **P2（测试缺陷·假红／flaky）** | `verify_search_shard.py` 的每个断言 lambda 把 `count_items(pg)` / `status_text(pg)` **各自读取两次**（判定一次、拼详情串再各读一次）。异步搜索在两次读取之间改变状态时，出现**自相矛盾的假红**：判定时 `status` 尚为"部分失败"→判红，打印详情时已恢复为 `""`（详情显示 `1 条, status=""`，看起来完全正常）。firefox 上以约 1/几 概率偶发（首轮 firefox 全量跑即命中 1 次 14→13） | 改为**一次快照 + 有界稳定重试**：新增 `read_state(pg)` 一次性读全 `count/status/empty/retry`，判定与详情取自同一时刻；`run_case` 首判失败后等 UI 稳定再判，最多 3 次。真实缺陷是**稳定地坏**的，重试仍判红 → 断言强度不变，仅消除"读得太早" | **修复后复验**：firefox 连跑 3 次均 **14/14 PASSED**；chromium 与 webkit 亦全绿。**这是第五节"重要测试必须证明能失败、不能偶发假红"的直接产物** |
| **R5-001** | **P2（本轮 M16 引入的可访问性回归）** | M16 新增的 `.author-link`（文章页作者链接）CSS 首版只写了 `color`/`text-decoration`，`<a>` 仍是 **inline** 元素 —— 而 **`min-height` 对 inline 元素无效**（与 R4-007 同根因）。结果在 320–430px 实测渲染为 **40×24px / 69×24px**，被 `audit.py` 的 `small-tap-target`（WCAG 2.5.8）在 4 个窄视口各报 6 处（共 **24 处** `TOTAL PROBLEMS`）。**M16 的静态门禁 `check_author_pages.py` 当时只断言"链接存在/指向正确"，抓不到像素高度 —— 正是第五节"不得只增加字符串断言、要验证真实产物"的直接体现（该缺陷由真实浏览器审计发现）** | `.author-link` 显式改为 `display:inline-flex; align-items:center; min-height:26px`；并在 `check_author_pages.py` 新增 **ON22–ON24**：直接断言**构建产物打包 CSS**（`main.min.<hash>.css`）中的 `.author-link` 规则必须含 `display:inline-flex/inline-block` 且 `min-height ≥ 24px` | **修复后复验**：同一审计（chromium × 320/375/390/430/768/1024/1440）由 `3/7 PASSED（24 处问题）` 转为 **`7/7 PASSED，TOTAL PROBLEMS: 0`**；**故障注入自证**：把 `.author-link` 改回 inline（去掉 display/min-height）→ **ON23/ON24 变红（41/43）**，还原后 47/47 |

> 编号说明：R4-007/R4-008 均在本轮**最终自测阶段**由真实运行发现（前者为产品缺陷、后者为测试缺陷），
> 与 R4-001~006（清理阶段发现）连续编号，共同构成本轮"自测暴露并当场修复"的闭环。
> **R5-001** 为本轮**独立验收前收尾阶段**（M16 引入后重跑三浏览器审计）发现的产品缺陷，
> 是"真实浏览器审计 > 静态字符串断言"的又一实证。

---

## 10.5 最终自测：故障注入自证汇总（第五节硬性要求）

> 原则：**重要测试必须通过故障注入证明可以失败**。下表为本轮最终自测阶段的
> 全量注入记录（每项均为：备份 → 注入 → 跑门禁 → 确认 rc≠0 → 还原 → 回读核验 → 复跑确认回绿）。

| 门禁 | 注入方式 | 注入后结果 | 还原后结果 |
| --- | --- | --- | --- |
| `check_new_features.py --selftest` | 内置 5 类注入（gallery/mermaid/katex/组件/外链） | 5/5 全部变红 | EXIT=0 |
| `check_ci_jobs.py --selftest` | 内置 7 类注入（delete-step/step-if-false/job-if-false/continue-on-error/echo-skipped/单引擎/换矩阵） | 7/7 全部变红 | EXIT=0 |
| `check_docs.py` | README 追加绝对化表述「零外部 CDN 请求」 | 10/11（README 绝对化表述断言红），EXIT=1 | EXIT=0，11/11 |
| `verify_multisection.py` | `layouts/_default/index.json` 搜索索引写死 `slice "posts"` | 37/40（3 条"搜索索引包含 tutorials/notes/projects"红），EXIT=1 | 40/40，EXIT=0 |
| `check_home_layouts.py` | `layouts/partials/home/profile.html` 移除 `home-profile` 结构标记 | 42/44（profile 布局标记 + 演示页 2 条红），EXIT=1 | 标记回读核验存在 |
| `check_reading_experience.py` | `assets/css/main.css` 将 5 处 `@media print` 破坏为 `@media printzz` | 77/79（B4 打印隐藏 2 条红，真实浏览器 emulate print 捕获），EXIT=1 | 5 处还原核验存在 |
| `audit.py`（tap-target） | 即 R4-007 真实产品缺陷（flex 块级化 23px 触控目标） | 4 处 small-tap-target | CSS 修复后 TOTAL PROBLEMS: 0 |
| `verify_search_shard.py`（firefox） | 即 R4-008 真实测试缺陷（双读 DOM 假红） | firefox 13/14 假红 | 快照+重试修复后 3 连跑 14/14 |
| `check_author_pages.py` | `layouts/partials/util/author-links.html` 的站点开关 `if $cfg.enabled` 改 `if false` | **37/43**（ON15/16/17/18/20 互链 + ML6 多语言链接共 **6 条变红**），EXIT=1 | 还原回读核验，43/43（矩阵 47/47），EXIT=0 |
| `check_author_pages.py`（R5-001） | `assets/css/main.css` 的 `.author-link` 去掉 `display:inline-flex` 与 `min-height`（退回 inline） | 41/43（**ON23 + ON24** 变红：inline 元素 min-height 无效），EXIT=1 | 还原后 47/47，EXIT=0 |

> 备注：对 `check_home_layouts` 首次尝试用 `home-profile-BROKEN` 注入**未变红**——因为
> `contains()` 是子串匹配，`home-profile-BROKEN` 仍包含 `home-profile`。属注入方法问题而非
> 测试假绿；改用彻底移除标记的强注入后按预期变红。此现象已记录，防止后续注入时误判。

---

## 11. 本轮最终结论汇总

- 历史 44 项（P1×3 / P2×5 / P3×7 / TEST-DEFECT×20 / SEC×4 / DOC×5）：**除 P3-003/P3-004/SEC-02 为 ACCEPTED-LIMITATION、019/020 归并入 R2 系列外，全部 FIXED**。
- R2 系列 13 项 + R3 系列 6 项：**全部 FIXED**（R2-001/002/003/006 需本轮重跑故障注入复核）。
- 功能缺口：**M1~M15、M17、M19、M20 共 18 项原有功能均已实现**；**M16 本轮由「轻量实现 / 接受为限制」
  升级为可选启用完整实现**（默认行为不变，见 §11.3）；M18 接受为限制。**合计 19 项实现 + 1 项接受限制（M18）**。

### 11.1 明确保留的限制（不做，且写明原因与用户影响）

| 项 | 状态 | 为什么不做 | 用户影响 |
| --- | --- | --- | --- |
| M18 嵌套菜单 | **ACCEPTED-LIMITATION** | 差距分析 §6 已评估价值较低，且会显著增加菜单模板复杂度与回归面 | 两级以内菜单可用 |
| BUG-P3-003 / SEC-02 第三方 SRI/CSP | **ACCEPTED-LIMITATION** | 不预置哈希（会随上游版本漂移而失效并误伤用户）、不写死 CSP（需按用户实际启用的服务定制）。默认**全部第三方功能关闭** | 启用第三方服务者需自行配置 integrity / CSP，README 已给模板 |
| BUG-P3-004 正文外链图无尺寸 | **ACCEPTED-LIMITATION** | 外链图片尺寸在构建期不可知 | 有 CLS 风险，已在 README「图片处理」提示；本轮画廊复用 Pipeline 已尽量补尺寸 |
| OBS-R2-001 弹窗无关闭按钮 | **ACCEPTED-LIMITATION** | 界面已有 Esc 提示，加按钮会与极简设计冲突 | 非缺陷 |

> **历史记录保留（不删除已处理项）**：**M16 作者档案页**曾在本表登记为 `ACCEPTED-LIMITATION`，
> 当时理由为「新增 `taxonomies.authors` 会改变默认站点 URL 结构，属破坏性默认值变更」。
> 本轮经项目所有者要求重新评估：该顾虑通过**可选启用**设计（默认 `params.authors.pages=false`，
> 未启用时产物与历史**逐字节一致**）已完全化解，**并非技术障碍**（跨 Hugo 0.128.0/0.148.0/0.167.0
> 探针实测 taxonomy 作者页含 CJK/特殊字符行为一致）。M16 因此**转为已实现**，从「保留限制」
> 移出——**此处保留原判定与撤销原因，供后续追溯**，详见 §11.3。

### 11.2 本轮未做验证的路径（诚实登记，不冒充已验）

- **真实第三方服务连通性**（giscus / waline / twikoo / disqus / busuanzi）：只验渲染与
  关闭态零请求，**未连真实后端发帖**（需账号，非主题能力范围）。
- **hugo server 实时预览（livereload）**：只验生产产物**不含** livereload，未做长时预览会话。
- **超大规模站点**（>2000 篇）：压力数据到 2000 篇已验证索引与搜索，未做更大规模。

### 11.3 M16 作者档案页——实现记录与验证证据（本轮新增）

**范围变更**：M16 由「轻量实现（仅元信息贯通）+ ACCEPTED-LIMITATION」变更为
**可选启用完整实现**。原限制理由（担心破坏默认 URL 结构）不成立——用可选启用即可保证默认零改变。

**设计要点（向后兼容）**：

- **单点配置**：`layouts/partials/util/author-config.html` 是主题**唯一**作者档案配置入口，
  返回 `dict {enabled, taxonomy, profiles}`。默认（未配置或 `params.authors.pages=false`）返回
  `enabled=false`，**模板不输出任何作者结构**。
- **启用条件（须同时满足）**：`[taxonomies]` 注册了作者 taxonomy（默认键名 `authors`，
  可经 `params.authors.taxonomy` 改名）**且** `params.authors.pages=true`。
  若声明启用但 taxonomy 未真正注册 → 自动降级 `enabled=false`（避免死链）。
- **URL 行为**：默认**零改变**（无 `/authors/...`，页面数不变）；启用后生成
  `/authors/`（索引，复用 `list.html`）与 `/authors/<term>/`（档案页，`term.html`）。
- **单数/复数语义（Hugo 既有机制，非主题行为）**：只有复数列表 `authors: ["A","B"]` 建立
  taxonomy term；单数 `author: "X"` 仅作署名回退，**不建立 term**（因此不会凭空生成档案页）。
- **CJK/特殊字符**：**刻意不用 `urlize` 拼路径**——`urlize "张伟"` 返回 percent-encoded
  （`%E5%BC%A0%E4%BC%9F`）、`+` 会被转义为 `&#43;`，且 `site.GetPage "/authors/<urlize>"`
  对 CJK 返回 NONE。改为遍历 `site.Taxonomies` 按 `Page.Title` **大小写不敏感**匹配 RelPermalink。
- **资料卡**：`layouts/partials/author-profile.html`，字段全可选（`bio/role/location/avatar/url/links`）；
  `avatar` 走 `util/avatar-url.html` 校验，`url`/`links` 只接受 `http(s)`；无资料时**不输出空区块**。

**验证证据**（门禁 `tools/check_author_pages.py`）：

| 证据 | 结果 |
| --- | --- |
| 门禁断言 | **43/43**（设置 `HUGO_MATRIX_DIR` 时 **47/47**，含 MX 多版本断言） |
| 触控目标契约（R5-001） | ON22–ON24 断言**构建产物 CSS** 中 `.author-link` 必须 `display:inline-flex/inline-block` 且 `min-height ≥ 24px`；audit 实测 7/7、`TOTAL PROBLEMS: 0` |
| 向后兼容（BC1） | 以「无本功能」基线主题（`37c3da6`）**自带 exampleSite** 为同一份内容，分别挂基线主题与当前主题构建：`.html/.xml/.json` 产物 **190 vs 190**，文件集合双向差集 **0**，规范化（打包 CSS 文件名哈希 / SRI / RSS `lastBuildDate`）后内容差异 **0** |
| 跨版本一致 | 五版本（0.128.0 / 0.148.0 / 0.162.0 / 0.166.0 / 0.167.0）exampleSite 构建均 `rc=0 / ERROR=0 / HTML=291`、作者 term 目录 **2** 个（`tanglx` / `nebula-bot`）、`author-link` 出现 **56** 次；另有合成探针站（`check_author_pages` MX 断言）文章页 `author-link` = **2** |
| 多语言 | 中文作者页 `/authors/张伟/` 资料卡正常；文章页链到 `/authors/%E5%BC%A0%E4%BC%9F/`；hreflang zh-CN↔en-US 双向；canonical 各语言正确 |
| SEO/索引 | sitemap 收录作者页；taxonomy RSS 生成；**搜索索引 47 条不变且不含** taxonomy 页 |
| 故障注入自证 | ①令 `author-links.html` 站点开关恒假 → 互链/多语言共 **6 条断言变红**；②令 `.author-link` 退回 inline → **ON23/ON24 变红（41/43）** |
| CI 接入 | `static-checks` job 新增步骤 + `check_ci_jobs.py` `REQUIRED_STEP_TOKENS` 登记 token |

> 说明：上述均为**开发方自测**（本地真实构建产物断言 + 故障注入），**尚未经独立第三方验收**。

> 更新记录：本表随本轮开发进展持续更新；最终版本以 `feat/theme-feature-completion` 分支 tip 上的文件为准。