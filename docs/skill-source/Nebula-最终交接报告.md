# Nebula 主题 —— 最终交接报告

> 本报告为一次性的最终交接交付物。事实分为 **【已证实】**（有实时 git/GitHub/CI 证据）、
> **【结论】**（基于证据的判断）、**【待独立验证】**（尚未经独立第三方验收）三层。

---

## 1. main / 候选分支 / PR 的真实状态

**【已证实】**（实时 `git ls-remote` / `gh` 核对，未抄旧报告）

| 对象 | 值 |
| --- | --- |
| 候选分支 | `feat/theme-feature-completion` |
| **主题代码基线** | **`8363d4b89193a7dfa22bc1569918a4eb666865cd`**（含全部主题运行时文件） |
| **文档沉淀提交（skill-source 首版，docs-only）** | **`e03a6c801090aeaa682a2e55d671acd3578c2e17`**（`8363d4b` + 1 个仅新增 `docs/skill-source/*.md` 的提交） |
| 候选分支 tip | 以 `git ls-remote origin refs/heads/feat/theme-feature-completion` **实时结果为准**（本报告定稿后又追加了 docs-only 的一致性修订提交，故 tip 会继续前移，但性质不变） |
| `main` | `21745162da343f2a0809516148b1a5680893390e`（**未改动**） |
| `v1.0.9` tag | `6168bb13b68014ea18953df6c7dc40078d581868`（**未移动**） |
| Releases | **无** |
| 开放 PR | **仅 PR #6**（base `main` / head `feat/theme-feature-completion`，状态 **MERGEABLE / CLEAN**） |
| 已关闭 PR | **PR #5**（`fix/third-party-audit-v1.0.9-r2`）—— 状态 **CLOSED**，关闭时间 `2026-10-12T00:33:29Z`；其修复已被 PR #6 完整覆盖 |
| 工作区 | 已跟踪文件在提交后干净；仅一个**未纳入版本控制**的打包件 `docs/skill-source/skill-source.zip`（旧快照，未提交）为未跟踪 |

**说明【已证实】**：`git diff 8363d4b..e03a6c8 --name-only` 的全部条目均位于 `docs/skill-source/`，
**未触碰** `layouts/`、`assets/`、`i18n/`、`static/`、`theme.toml` 等主题运行时文件。

> **SHA 口径（重要）**：**主题代码**与**文档沉淀**是不同的提交。
> **CI 结果只能绑定到它实际运行的那个 SHA，不得互相套用**；详见 §2。

---

## 2. 最终候选 SHA 与其 CI 证据

**【已证实】**

| SHA（角色） | CI run | 结论 |
| --- | --- | --- |
| `8363d4b`（**主题代码基线**） | pull_request `38171213190` | 11 success + 1 skipped（Release job 按 `if` 跳过） |
| `8363d4b`（**主题代码基线**） | workflow_dispatch `38171253788` | **14/14 success**（含 `Release full-site audit` chromium/firefox/webkit） |
| **`e03a6c8`（文档沉淀提交，docs-only）** | pull_request `38188954023` | **success**（11 pass + Release skipped，5m46s） |
| **`e03a6c8`（文档沉淀提交，docs-only）** | workflow_dispatch `38189345376` | **14/14 success**（39m31s，含三引擎全站审计） |

**【已证实】`e03a6c8` 的 14 个 job 全部 success：**

- Build ×6：Hugo `0.128.0` / `0.148.0` / `0.162.0` / `0.166.0` / `0.167.0` / `latest`
- `Sub-directory baseURL`
- `Static checks (links / index / features / i18n / sections)`
- `Browser tests` ×3：chromium / firefox / webkit
- **`Release full-site audit` ×3：chromium / firefox / webkit**

链接：
- PR CI：`https://github.com/tanglx02/hugo-theme-nebula/actions/runs/38188954023`
- dispatch CI：`https://github.com/tanglx02/hugo-theme-nebula/actions/runs/38189345376`

CI 契约（`.github/workflows/ci.yml`）：5 个顶层 job 展开为 **14**（build 6 / subdir 1 / static-checks 1 / browser-tests 3 / release-full-audit 3）；
非 tag 推送时 Release job 跳过 → **11**。`CI-JOBS-TOTAL: 14`、`CI-JOBS-PUSH-TOTAL: 11` 由 `check_ci_jobs.py` 校验，禁止手写。

> 历史澄清【已证实】：CI #112（`38145051430`, 14/14）实际跑在 `4a4ea01`，**不是**新 SHA，
> 因此已在 `8363d4b` 上重新取得同 footprint 的 CI 证据（上表前两行）。

---

## 3. 是否存在合并阻断项

**【结论】无合并阻断项。** 逐条对照：

| 阻断项定义 | 核查结果 |
| --- | --- |
| 主题代码基线 `8363d4b` 缺乏完整 CI 证据 | 否（`38171253788` = 14/14，含三引擎全站审计） |
| 文档沉淀提交 `e03a6c8` 缺乏完整 CI 证据 | 否（`38188954023` success + `38189345376` = **14/14**） |
| 构建 / 核心功能 / 兼容测试失败 | 否（全绿；0.128–0.167 六版本矩阵 + 三引擎） |
| 历史高优先级产品缺陷复现 | 否（P1×3 / P2×5 全部复核 FIXED） |
| PR 有真实合并冲突或必需检查失败 | 否（PR #6 = MERGEABLE / CLEAN） |
| 存在影响交付判断的严重假绿门禁 | 否（本轮唯一假绿 `check_index` contentLimit 已修复并故障注入自证） |

---

## 4. 旧 PR 是否已关闭

**【已证实】**（实时 `gh pr view 5` 核对）PR #5（`fix/third-party-audit-v1.0.9-r2`）
状态为 **CLOSED**，关闭时间 `2026-10-12T00:33:29Z`；此前已在其上评论说明"被 PR #6 取代"。
**当前仅 PR #6 处于 OPEN**。本次核对时该 PR 已处于关闭状态，故未再执行关闭操作，仅记录实时状态。

---

## 5. 是否已合并

**【已证实】未合并。** 依据约束"**未经 owner 授权不自合并**"，仅给出合并建议：
**PR #6 → base `main`，建议以 Squash and merge 合并**（把 `8363d4b` 起的全部提交压成单个进入 `main`）。

合并后建议核对：`main` 最新 SHA、其 CI 结果、主题关键文件完整性（`theme.toml` / `layouts/` / `assets/` / `i18n/`）。

---

## 6. Skill 资料文件与路径

**【已证实】** 目录 `docs/skill-source/` 含 **13** 份 Skill 源资料（首版 11 份提交于 `e03a6c8`；
本节所述的 `SOURCE_EVIDENCE_INDEX.md` / `GENERALIZATION_MATRIX.md` 为随后追加的一致性修订资料）：

| 文件 | 内容 |
| --- | --- |
| `PROJECT_OVERVIEW.md` | 定位 / 功能清单 / 架构 / 目录 / 版本要求 / 状态快照 |
| `DEVELOPMENT_WORKFLOW.md` | 需求→架构→编码→构建→测试→文档→PR 全流程 + 故障注入方法论 + 冻结规则 |
| `HUGO_COMPATIBILITY.md` | 0.128/0.148/0.162/0.166/0.167/latest 兼容要点、能力阈值、反模式 |
| `BUG_FIX_CASEBOOK.md` | 真实 bug 案例（触发/根因/修复/回归/教训），覆盖模板 null、boolean false、slice vs char、URL 编码、i18n、搜索索引、JSON-LD、分页、无作者/头像、滚动锁、焦点恢复 |
| `TESTING_STRATEGY.md` | 测试分层 L0–L7、MUST-RUN vs OPTIONAL、故障注入、第三方验收 |
| `TESTING_FAILURES.md` | 假绿/假红/陈旧产物/夹具污染/环境缺失/CI 静默/退出码/固定 sleep 八类失效 |
| `FEATURE_IMPLEMENTATION_PATTERNS.md` | 13 个实现模式（首页布局/阅读体验/i18n/短代码/render hooks/图片管线/作者档案/搜索/SEO） |
| `RELEASE_CHECKLIST.md` | 功能冻结→代码核对→全量构建→浏览器全测→独立验收→合并→tag→发布 |
| `PROMPT_TEMPLATES.md` | 需求澄清/功能开发/Bug 修复/测试评审/跨 AI 交接/冻结/最终验收 可复用提示词 |
| `OPEN_LIMITATIONS.md` | 接受为限制 / 未验证 / 计划内未做，逐项写明影响与变通 |
| `SKILL_HANDOFF.md` | **Skill 制作主交接报告**（含下方 §8 全部问题） |
| `SOURCE_EVIDENCE_INDEX.md` | **新增**：经验 → 代码路径 / 问题编号 / 提交 SHA / 测试 / 独立验收覆盖 的证据映射 |
| `GENERALIZATION_MATRIX.md` | **新增**：经验三分法（普遍适用 / 结构相关 / Nebula 专属） |

> 另：本报告同时以 `docs/skill-source/Nebula-最终交接报告.md` 与工作区根目录同名文件存在，内容一致。

---

## 7. 尚未独立验证的内容 与 接受为限制的项

### 7.1 独立第三方验收的真实覆盖范围（**不得混淆**）

**【已证实】** 必须区分"某个 SHA 上的专项验证"与"整个新候选的完整验收"：

| 事实 | 状态 |
| --- | --- |
| 独立第三方验收（PASS WITH LIMITATIONS）针对的候选 SHA | **`f3549a5dacb503bc4cdf99556a5d04b51e753911`** |
| **M16 作者档案页**曾在该 SHA 上接受独立第三方**专项验证** | **是** |
| **当前最新候选的整个提交 SHA**（`8363d4b` 及其后 docs-only `e03a6c8`）是否重跑**完整独立第三方验收** | **否** |
| M16 相关实现文件在 `f3549a5..8363d4b` 是否变动 | **否**（差异为空） |
| `f3549a5` 之后实际有改动的部分（举例） | `4a4ea01`：`head.html`（空标题修复）、`ci.yml`、多个 `tools/*`；`8363d4b`：`tools/check_index.py` |

> **可以**说：M16 实现文件自 `f3549a5` 起未变，故该 SHA 上对 M16 的专项验证**结论对当前文件仍然相关**。
> **不得**说：整个新候选已被独立第三方验收——`head.html`（同时承载作者 meta / JSON-LD）已在 `4a4ea01` 改动。
>
> **通用规则**：验收结论绑定它当时验证的那个 SHA；换 SHA 必须重新界定覆盖范围，不能自动继承。

### 7.2 其余尚未独立验证的路径（**【待独立验证】**）

- 本轮**新增门禁**（`check_home_layouts` / `check_reading_experience` / `check_new_features` / `check_author_pages`）的故障注入自证——开发方执行。
- 本轮修复的假绿（`check_index` contentLimit）与假红（`verify_search_shard`）——开发方自测暴露。
- 真实第三方服务连通性（giscus/Waline/Twikoo/Disqus/busuanzi）——只验渲染与关闭态零请求，未连真实后端。
- 真实屏幕阅读器（NVDA/VoiceOver）——只做属性与焦点级验证。
- `hugo server` 实时预览长时会话——只验生产产物不含 livereload。
- 超大规模站点（>2000 篇）——压测到 2000 篇。

> 注：CI 证据（`8363d4b` → `38171253788` 14/14；`e03a6c8` → `38189345376` 14/14）**不等于**独立第三方验收，
> 二者是不同层级、不同 SHA 上取得的证据。

### 7.3 接受为限制（**【已证实】**）

| 项 | 原因 | 用户影响 |
| --- | --- | --- |
| M18 嵌套菜单 | 价值较低，显著增加复杂度与回归面 | 两级以内菜单可用 |
| 第三方 SRI/CSP（BUG-P3-003 / SEC-02） | 不预置哈希（随上游漂移会失效误伤）、不写死 CSP（需按启用服务定制）；默认全部第三方功能关闭 | 启用者需自行配置，README 已给模板 |
| 正文外链图无尺寸（BUG-P3-004） | 外链图尺寸构建期不可知 | 有 CLS 风险，README 已提示 |
| 弹窗无关闭按钮（OBS-R2-001） | 界面已有 Esc 提示，加按钮与极简设计冲突 | 非缺陷 |

> **保留的历史记录**：M16 作者档案页曾登记为 ACCEPTED-LIMITATION（怕新增 taxonomy 破坏默认 URL 结构），
> 后经"默认关闭的可选启用"设计完全化解，已转为**已实现**。结论：并非所有"限制"都真正无法解决。

---

## 8. 后续通用 Hugo 主题开发 Skill 的建议结构

（详见 `docs/skill-source/SKILL_HANDOFF.md`，此处为摘要）

```
hugo-theme-dev/
├── SKILL.md                    # 触发条件 + 总流程 + 硬约束 + 停止条件
├── workflows/ 01-requirements / 02-architecture / 03-coding-rules /
│              04-build / 05-testing / 06-docs / 07-release / 08-handoff
├── references/ hugo-compat / i18n / template-pitfalls /
│               test-failure-modes / a11y-and-security
├── templates/  stable-baseline / test-plan / issue-tracker /
│               open-limitations / handoff-report
└── checklists/ release / anti-drift
```

**必须保留的规则**：功能冻结 + 阻断项白名单 + 停止条件；区分事实/结论/待验证；
故障注入自证；退出码约定（失败/依赖缺失/零用例=非零）；SHA 固定 + 证据绑定；
三层证据链；布尔 `false` 不被吞；rune 安全截断；能力探测禁 `cond`；安全校验在源头；
独立测试只测不改；未授权不自合并；未验证项必须登记。

**不应硬编码**：具体 SHA/PR/CI run id/版本号；具体脚本名/夹具名/issue 编号；
具体页面数/体积数值；Nebula 的品牌与布局名；特定配置键；具体 Hugo 版本列表（应表述为
"最低支持 + 中间 + 当前稳定 + latest"）。

**MVP 构建顺序**：①`SKILL.md` → ②`references/template-pitfalls.md` → ③`references/test-failure-modes.md`+退出码约定
→ ④`workflows/07-release.md` → ⑤`03-coding-rules.md`+`05-testing.md` → ⑥`templates/*` → ⑦其余。
**最小闭环**：能阻止"加功能失控 / 假绿通过 / 无授权合并"三件事即有价值。

---

## 9. 最终状态

**【结论】`READY_TO_MERGE`**

- 无合并阻断项；
- 交接资料（`docs/skill-source/` **13 份** Skill 源资料 + 本报告）已整理并提交、推送；
- 未合并、未移动 tag、未打新 tag、未发 Release（均按约束执行）；
- **等待所有者授权后合并 PR #6**。

---

## 附：CI 运行结果（`e03a6c8`，docs-only 提交）

**【已证实】**

| run | 事件 | headSha | 结果 |
| --- | --- | --- | --- |
| `38188954023` | pull_request | `e03a6c8` | **success**，11 pass + 1 skipped（Release），5m46s |
| `38189345376` | workflow_dispatch | `e03a6c8` | **14/14 success**，39m31s |

14 个 job 明细（dispatch run 全部 `success`）：

```
Build (Hugo 0.128.0)        success
Build (Hugo 0.148.0)        success
Build (Hugo 0.162.0)        success
Build (Hugo 0.166.0)        success
Build (Hugo 0.167.0)        success
Build (Hugo latest)         success
Sub-directory baseURL       success
Static checks               success
Browser tests (chromium)    success
Browser tests (firefox)     success
Browser tests (webkit)      success
Release full-site audit (chromium)  success
Release full-site audit (firefox)   success
Release full-site audit (webkit)    success
```

**核对说明**：这是一次**同 fingerprint 复核**——`e03a6c8 = 8363d4b + 1 个 docs-only 提交`，
主题运行时文件零改动（`git diff 8363d4b..e03a6c8` 仅 `docs/skill-source/`），
故 14/14 与 `8363d4b` 上的历史结果一致，亦与"docs-only 不影响任何门禁"的预期相符。

> 本报告定稿后，又在候选分支上追加了 **docs-only 的资料一致性修订**
> （新增 `SOURCE_EVIDENCE_INDEX.md` / `GENERALIZATION_MATRIX.md`，并修正本文各节的状态与 M16 验收口径）。
> 该修订同样只改 `docs/`，按 PR 工作流验证；主题代码基线仍是 `8363d4b`。
