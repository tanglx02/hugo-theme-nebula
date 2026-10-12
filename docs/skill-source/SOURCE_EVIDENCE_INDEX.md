# SOURCE_EVIDENCE_INDEX — 经验 → 代码 / 问题 / 提交 / 测试 / 验收 的证据索引

> **用途**：把 `docs/skill-source/` 中的关键结论，逐条映射到**可核对的证据**：
> 代码路径 · 问题编号 · 提交 SHA · 测试脚本/CI · 独立验收是否覆盖。
> **本文件只做索引，不重复论述**；每条结论的正文见对应文档。
>
> **事实标注**：**【已证实·实测】**＝本轮实际打开文件/跑命令核对；**【文档所载】**＝引自既有文档，本索引**未逐行复核**；**【未验证】**＝证据不足，明确标注。
>
> **红线**：**不编造行号、提交 SHA 或测试结果**。凡无法确证者一律标 `未验证`。

---

## 0. 全局 SHA 与 CI 坐标（本轮实测）

| 坐标 | 值 | 角色 |
| --- | --- | --- |
| `8363d4b89193a7dfa22bc1569918a4eb666865cd` | 主题代码基线 | 含全部运行时文件 |
| `e03a6c801090aeaa682a2e55d671acd3578c2e17` | 文档沉淀提交（docs-only） | `8363d4b` + 1 提交 |
| `f3549a5dacb503bc4cdf99556a5d04b51e753911` | 独立第三方验收针对的候选 SHA（历史） | 祖先提交 |
| `4a4ea01` | R3 独立验收遗留收尾 | 祖先提交 |
| `37c3da646cce27be789c1a9f9060b25615c72cdb` | M16 引入前基线（BC1 对照） | 祖先提交 |

| CI run | 事件 | 绑定 SHA | 结果 |
| --- | --- | --- | --- |
| `38171213190` | pull_request | `8363d4b` | 11 pass + 1 skipped |
| `38171253788` | workflow_dispatch | `8363d4b` | **14/14** |
| `38188954023` | pull_request | `e03a6c8` | success（11 pass + Release skipped） |
| `38189345376` | workflow_dispatch | `e03a6c8` | **14/14** |
| `38145051430` | workflow_dispatch | `4a4ea01` | 14/14（**历史**，勿套用其它 SHA） |

---

## 1. 代码证据索引（实测锚点）

> 下表的"文件:行"若标 **【已证实·实测】**，为本轮真实打开并 grep 到的行；否则为 **【文档所载】**。

| # | 结论 / 机制 | 代码路径（文件:行） | 状态 |
| --- | --- | --- | --- |
| E1 | 布尔参数必须避开 `default` 吞 `false`；partial 返回 bool 会被包成字符串，故返回 `dict` | `layouts/partials/util/bool-param.html` | 【已证实·实测】文件存在并含该逻辑 |
| E2 | 字符串截断按 rune，越界会 panic；统一走安全 partial | `layouts/partials/util/slice-runes.html`；调用点 `layouts/_default/index.json:73` | 【已证实·实测】`:73` 实测调用 slice-runes |
| E3 | 头像空值/站点根/危险 scheme → 空串 | `layouts/partials/util/avatar-url.html` | 【已证实·实测】文件存在 |
| E4 | URL 源头拒绝 `javascript:`/`vbscript:`/`data:`(非 image) | `layouts/partials/util/rel-url.html` | 【已证实·实测】文件存在 |
| E5 | `og:locale` BCP47 规范化 + 跨版本 `.Locale`/`.LanguageCode` 回退 | `layouts/partials/util/locale.html` | 【已证实·实测】文件存在 |
| E6 | 作者档案页唯一配置入口（返回 `{enabled,taxonomy,profiles}`） | `layouts/partials/util/author-config.html` | 【已证实·实测】文件存在 |
| E7 | 外链文章 scheme 白名单 | `layouts/partials/util/external-url.html` | 【已证实·实测】文件存在 |
| E8 | 编辑此页（源文件路径逐段编码、provider 分支） | `layouts/partials/util/edit-url.html` | 【已证实·实测】文件存在 |
| E9 | 空/纯空白标题不再输出前导 `- ` | `layouts/partials/head.html:6`（`trim .Title`） | 【已证实·实测】行 6 含该修复 |
| E10 | 关闭 modal 焦点归还用 `preventScroll` | `assets/js/main.js:436`（汉堡按钮同见 `:58`） | 【已证实·实测】行 436/58 命中 |
| E11 | 头部导航独立断点 900px | `assets/css/main.css:1347`（`@media (max-width: 900px)`） | 【已证实·实测】行 1347/1366 命中 |
| E12 | `.author-link` 触控目标（inline-flex + min-height） | `assets/css/main.css:1064` | 【已证实·实测】该选择器存在（是否含 inline-flex/min-height 由门禁 ON22–ON24 断言） |
| E13 | 搜索索引含 `date`(机器) 与 `dateDisplay`(构建期 i18n) | `layouts/_default/index.json` | 【文档所载】 |
| E14 | JSON-LD 整体 `dict` + `jsonify`，逃逸 `</script>` | `layouts/partials/head.html` | 【文档所载】 |
| E15 | modal 滚动锁引用计数、恢复原值 | `assets/js/main.js`（`createModalA11y`） | 【文档所载】 |
| E16 | 首页四布局 + 安全回退 | `layouts/partials/home/{cards,profile,hero,landing,latest}.html` | 【已证实·实测】目录存在 |

---

## 2. 问题编号 → 证据映射

> 编号释义见 `docs/final-cleanup-issue-tracker.md`。**本索引不重复其结论**，只标证据落点与覆盖状态。

| 问题编号 | 一句话 | 代码/工具落点 | 提交 SHA | 验证脚本 / CI | 独立验收覆盖 | 证据状态 |
| --- | --- | --- | --- | --- | --- | --- |
| BUG-P1-001 | 关闭弹窗后页面滚不动 | `assets/js/main.js`（滚动锁） | 未逐条定位 | `verify_modal_scroll.py`（三引擎） | `f3549a5` 轮 | 【文档所载】 |
| BUG-P1-002 | 旧 Hugo 上 `auto` 分片构建失败 | `layouts/_default/index.json` | 未逐条定位 | `check_search_modes.py` | `f3549a5` 轮 | 【文档所载】 |
| BUG-P1-003 | `slicestr` 越界终止整站构建 | `util/slice-runes.html` | 未逐条定位 | build 边界夹具步骤 | `f3549a5` 轮 | 【文档所载】 |
| BUG-R2-001 | `index.json` 仍用裸 `slicestr` | `layouts/_default/index.json:73` | 未逐条定位 | `check_index.py` | `f3549a5` 轮 | 【已证实·实测】`:73` 已走 slice-runes |
| BUG-R2-002 | 能力阈值 166 误判为 167 | `layouts/_default/index.json` | 未逐条定位 | `check_search_modes.py` | `f3549a5` 轮 | 【文档所载】 |
| BUG-R2-003 | 空头像渲染 `<img src="/">` | `util/avatar-url.html` | 未逐条定位 | `check_new_features.py` | `f3549a5` 轮 | 【已证实·实测】文件存在 |
| BUG-R2-004 | 焦点归还未 `preventScroll` | `assets/js/main.js:436` | 未逐条定位 | `verify_modal_scroll.py` | `f3549a5` 轮 | 【已证实·实测】行 436 命中 |
| BUG-R2-005 | 无作者时 JSON-LD `author.name:null` | `layouts/partials/head.html` | 未逐条定位 | `check_html_quality.py` | `f3549a5` 轮 | 【文档所载】 |
| BUG-P2-002 | 英文站 769–869px 横向溢出 | `assets/css/main.css`（900px 断点） | 未逐条定位 | `check_responsive_overflow.py` | `f3549a5` 轮 | 【已证实·实测】断点存在 |
| BUG-P2-003 | 浅色 muted/chip 对比度不足 | `assets/css/main.css`（token 拆分） | 未逐条定位 | `verify_contrast.py` | `f3549a5` 轮 | 【文档所载】 |
| BUG-P2-004 | 全站 JSON-LD 双重编码 | `layouts/partials/head.html` | 未逐条定位 | `check_html_quality.py` | `f3549a5` 轮 | 【文档所载】 |
| BUG-P2-005 | series 写索引但不参与匹配 | `assets/js/main.js`（`score()`） | 未逐条定位 | `verify_search_edge.py` | `f3549a5` 轮 | 【文档所载】 |
| BUG-R3-001 | 语言键与 i18n 文件名不匹配 → 旧版本 UI 空串 | `exampleSite/` 配置 + `i18n/*.yaml` | 未逐条定位 | `check_features.py` 8a/8b | **未覆盖** | 【文档所载】 |
| BUG-R3-002 | `[languages.*]` 顶层字段跨版本弃用 | 站点语言配置形态 | 未逐条定位 | `check_lang_config.py` | **未覆盖** | 【文档所载】 |
| BUG-R3-003 | 旧版本 `og:locale="zh_cn"` | `util/locale.html` | 未逐条定位 | `check_lang_config.py` L4 | **未覆盖** | 【已证实·实测】文件存在 |
| TEST-DEFECT-R3-010 | 路径字面 `+` 未列入 safe → 审计假差异 | `tools/html_inventory.py`（`normalize_url`） | 未逐条定位 | `tools/test_inventory.py`（17/17） | `f3549a5` 轮遗留 | 【文档所载】 |
| TEST-DEFECT-R3-011 | `--config` 叠加层 `contentLimit` 感知不到 → 假红 | `tools/check_index.py` | `4a4ea01` | `tools/test_check_index.py` | **未覆盖** | 【文档所载】 |
| OBS-R3-002 | 空标题 `<title>` 前导 `- ` | `layouts/partials/head.html:6` | `4a4ea01` | `check_html_quality.py`（`title-leading-dash`） | **未覆盖** | 【已证实·实测】行 6 含修复 |
| **假绿·contentLimit** | 孤立未参与构建的 TOML 让截断索引误判为合法 | `tools/check_index.py`（`_looks_like_build_source`） | **`8363d4b`** | `tools/test_check_index.py`（5/5） | **未覆盖** | 【已证实·实测】提交范围＝该 2 文件 |
| R4-008 | shard 测试双读 DOM → 假红 | `tools/verify_search_shard.py`（`read_state`） | 未逐条定位 | 自身（连跑 3 次） | **未覆盖** | 【文档所载】 |
| R5-001 | `.author-link` inline 元素 `min-height` 无效 | `assets/css/main.css:1064` | 未逐条定位 | `check_author_pages.py` ON22–ON24 | **未覆盖** | 【已证实·实测】选择器存在 |
| M16 | 作者档案页（可选启用） | `util/author-config.html`、`author-profile.html`、`_default/term.html` | 实现与口径纠正：`2593ead`（【文档所载】） | `tools/check_author_pages.py`（43/47 项） | **`f3549a5` 轮专项验证** | 【文档所载】 |

> **关于"独立验收覆盖"列**：`f3549a5` 轮的验收（PASS WITH LIMITATIONS）覆盖的是**该 SHA 当时的代码**。
> 之后 `4a4ea01` / `8363d4b` 的改动**未被新一轮完整独立验收覆盖**——详见 `OPEN_LIMITATIONS.md` §4。

---

## 3. 工具/门禁 → 证据映射（实测存在）

> 以下文件均已实测存在于 `tools/`；其"断言条数"为**文档所载**，本索引未逐条复算。

| 工具 | 职责 | 断言/结果来源 | 状态 |
| --- | --- | --- | --- |
| `tools/_testlib.py` | `Harness`（`record/fatal_error/finish`）、退出码约定 | 文件存在 | 【已证实·实测】 |
| `tools/check_index.py` | 搜索索引完整性 + `contentLimit` 配置感知 | 假绿修复见 `8363d4b` | 【已证实·实测】 |
| `tools/test_check_index.py` | `check_index` 两种模式 5 场景 | 5/5【文档所载】 | 【已证实·实测】文件存在 |
| `tools/check_ci_jobs.py` | CI job 数量由 matrix 计算 + 结构校验 + `--selftest` | 14/14、selftest 8/8【文档所载】 | 【已证实·实测】文件存在 |
| `tools/check_workflow_policy.py` | 最小权限 / runner 固定 / Node24 action | 【文档所载】 | 【已证实·实测】文件存在 |
| `tools/check_author_pages.py` | M16 作者档案页 | 43（矩阵 47）项【文档所载】 | 【已证实·实测】文件存在 |
| `tools/verify_modal_scroll.py` | 滚动锁生命周期 | 三引擎【文档所载】 | 【已证实·实测】文件存在 |
| `tools/verify_search_shard.py` | 分片失败语义 | R4-008 修复【文档所载】 | 【已证实·实测】文件存在 |
| `tools/html_inventory.py` | 产物 URL 规范化（全站真值） | safe 含 `+`【文档所载】 | 【已证实·实测】文件存在 |
| `tools/verify_multisection.py` | 多 section 回归 | R4-001/R4-002 修复【文档所载】 | 【已证实·实测】文件存在 |
| `tools/link_check.py` | 站内死链 | `_testlib.default_build_dir()`【文档所载】 | 【已证实·实测】文件存在 |
| `tools/check_docs.py` | README/CHANGELOG/稳定基线一致性 | 只读 README.md / CHANGELOG.md（本轮实测） | 【已证实·实测】 |
| `.github/workflows/ci.yml` | 生产门禁 14 job（tag/手动含 Release） | `CI-JOBS-TOTAL: 14`【实测读取】 | 【已证实·实测】 |

---

## 4. **未验证**清单（明确标注，不冒充已证）

| 项 | 为什么未验证 |
| --- | --- |
| 各问题的**精确行号**（除 E1–E12 已实测者） | 本索引未逐行复核，沿用 `final-cleanup-issue-tracker.md` 描述 |
| 各问题的**修复提交 SHA**（标"未逐条定位"者） | 未逐个 `git log -S` 定位，避免编造 |
| `f3549a5` 轮验收的**逐项结论细节** | 依据既有验收报告与追踪表，未重读原始报告逐条核对 |
| `e03a6c8` 之后的 docs-only 修订 SHA | 本文件写入时尚未提交；以 `git log` 实时结果为准 |
| 门禁**断言条数**（如 213/43/47 项） | 文档所载，未逐条复算 |
| 真实第三方服务连通性 / 真实屏幕阅读器 / >2000 篇 | 见 `OPEN_LIMITATIONS.md` §2 |

---

## 5. 使用建议

1. 引用本索引的条目时，**先看"证据状态"列**：带【已证实·实测】的可直接采信；【文档所载】需回原文档；【未验证】不得当作事实。
2. 任何"行号 / 提交 / 测试结果"若要写入通用 Skill，**必须现场复核**后再写。
3. 本索引的价值是**"知道去哪查"**，不是**"替代原始证据"**。
