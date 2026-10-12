# RELEASE_CHECKLIST — 发布检查清单

> 资料性质：用于通用 Hugo 主题开发 Skill 的经验沉淀。
> 事实标注：**【已证实】**＝有真实 CI/记录支撑；**【结论】**＝开发方判断；**【待验证】**＝未经独立确认。
>
> 本清单描述 Nebula 从**功能冻结**到**发布**的完整闸门。核心思想：**每一步都有可执行的证据，不靠"我觉得应该没问题"。**

---

## 阶段总览

```
0. 功能冻结 → 1. 代码核对 → 2. 全量构建 → 3. 浏览器全测
   → 4. 独立第三方验收 → 5. 合并 main → 6. 打 tag → 7. 发布
```

**停止条件**：一旦成为"功能冻结候选"，**不得再扩展范围**；新问题只在"真正的合并阻断项"范围内修，且必须说明复现/影响/根因/最小修复/验证。

---

## 阶段 0 — 功能冻结

- [ ] 明确"冻结"：不再新增功能、不重构测试框架、不为凑数加用例、不做无关重构。
- [ ] 冻结产出一个**固定候选 SHA**（例如 `8363d4b89193a7dfa22bc1569918a4eb666865cd`），后续所有证据**绑定这个 SHA**，防止漂移。
- [ ] 记录分支与远端对应：`HEAD == origin/<branch>`（**已证实**本项目为 `feat/theme-feature-completion`）。
- [ ] `git status` 干净（除**有意保留**的未跟踪资料目录）。
- [ ] **不动**稳定 tag、**不动** main、**不做**破坏性 git 操作（`reset --hard` / `clean -fdx` / force push）。

**【结论】** 冻结的意义是：让"经过验证的代码"与"后续证据"一一对应。没有冻结 SHA，"验证通过"就是一句空话。

---

## 阶段 1 — 代码核对

- [ ] `fetch` 远端最新，确认 `main` / 候选分支 / 相关 PR 的真实状态（**以 `git ls-remote` / GitHub 实时结果为准，不抄旧报告**）。
- [ ] 确认候选 SHA 与报告一致，工作区干净。
- [ ] 确认 **CI 证据绑定的是候选 SHA**（不是更早的 SHA —— 本项目曾出现"CI 跑在 `4a4ea01` 而非新 `8363d4b`"，因此**重跑**取得同 footprint 证据）。
- [ ] 确认 `v*` tag **未移动**、**无 Release**（除非本阶段明确要发布）。
- [ ] 若真实状态 ≠ 报告 → **用实时结果，不复制旧报告**。

---

## 阶段 2 — 全量构建

- [ ] 多 Hugo 版本矩阵构建成功（0.128.0 / 0.148.0 / 0.162.0 / 0.166.0 / 0.167.0 / latest）。
- [ ] 子目录 baseURL（`/blog/`）构建成功、路径带前缀无重复。
- [ ] 必需产物齐全：`index.html`、`index.json`、`sitemap.xml`、`robots.txt`、`404.html`、`index.xml`、favicon。
- [ ] 边界夹具齐全（空标题/单字符/单 CJK/单 emoji/空正文/无作者/BOM/page bundle）+ **图片管线 `srcset=` 确实产出**。
- [ ] 草稿/未来文章被排除；生产产物**无 livereload**。
- [ ] 全部静态门禁（`link_check` / `check_index` / `check_features` / `check_html_quality` / `check_seo` / `check_i18n_hardcode` / `security_baseline` / `check_alias_pages` / `check_home_layouts` / `check_new_features` / `check_author_pages` / `check_content_components` / `check_lang_config` / …）全部 `exit 0`。
- [ ] 多语言构建（zh-CN / en / zh-TW）+ 真实 multilingual 构建通过。
- [ ] 搜索模式与 auto 阈值边界通过；旧版本回退 / 显式 shard 报错符合预期。
- [ ] CI 结构门禁本身通过：`check_ci_jobs.py`、`check_workflow_policy.py`。

> **反模式**：只跑"最新 Hugo + 单语言 + 不装 Pillow"。**已证实**这种跑法会漏掉图片管线分支与旧版本不兼容。

---

## 阶段 3 — 浏览器全测（三引擎）

- [ ] 安装三引擎：`playwright install --with-deps chromium firefox webkit`。
- [ ] 启动**静态服务器**（`tools/serve.py`），**不要用 `hugo server` 的产物**（含 livereload）。
- [ ] 抽样审计 `audit.py`（溢出/控制台/404/破图/懒加载/点击区）通过。
- [ ] 交互 `interactions.py`、复制 `verify_copy.py`、灯箱 `verify_lightbox.py` 通过。
- [ ] 搜索：`verify_search_modal.py`（19 项）、`verify_search_edge.py`（含竞态与日期本地化）、`verify_search_highlight.py`、`verify_search_shard.py` 通过。
- [ ] modal 滚动锁生命周期 `verify_modal_scroll.py`（三引擎）通过。
- [ ] 对比度 `verify_contrast.py`（浅色 + 深色）通过；响应式 `check_responsive_overflow.py`（含英文站）通过。
- [ ] 三种 baseURL 部署 `verify_baseurl.py` 通过。
- [ ] 阅读体验 `check_reading_experience.py` 的真实浏览器断言通过。

---

## 阶段 4 — Release 全站审计（发布门禁）

仅在 tag 推送或手动触发时运行（`AUDIT_FULL=1`）。

- [ ] `AUDIT_REQUIRE_INVENTORY=1`：inventory 存在且**绑定本次构建指纹**。
- [ ] `EXPECTED == AUDITED`（构建产物 100% 被审计）。
- [ ] `MISSING URLS = 0`、`UNEXPECTED URLS = 0`、`DISCOVERY FAILURES = 0`。
- [ ] 分页交叉验证：`PAGINATION MISSING/UNEXPECTED = 0`、`PAGINATION EXHAUSTED = YES`（未达安全上限）。
- [ ] 8 类必需页面齐全（分类 term / 标签 term / `/page/2/` / `/page/3/` / 分类首页 / 标签首页 / 归档页 / 文章页）。
- [ ] alias 页静态结构单独通过（浏览器会重定向，不能靠浏览器验）。
- [ ] **sitemap 只作 SEO 索引检查，不作全站真值**。

---

## 阶段 5 — 独立第三方验收

- [ ] 交付**固定 SHA** 的产物 + 复现命令 + 文档，不做口头说明。
- [ ] 第三方**只测不改**；问题以"编号 + 复现方式 + 实测证据"返回。
- [ ] 开发方逐条处理：`FIXED` / `PARTIALLY-FIXED` / `NOT-FIXED` / `ACCEPTED-LIMITATION` / `NOT-VERIFIED`，**历史宣称"已修复"不直接采信，回代码复核**。
- [ ] 遗留项单独编号、逐条收尾、再复验。
- [ ] 明确列出**未验证路径**（真实第三方服务连通性、真实屏幕阅读器、超大规模站点等），**不冒充已验**。

**【已证实】** 本项目第三方验收结论为 PASS WITH LIMITATIONS；遗留项以 R2/R3 系列收尾，全部 `FIXED` 或明确 `ACCEPTED-LIMITATION`。

---

## 阶段 6 — 合并 main

- [ ] PR：`base = main`、`head = feat/theme-feature-completion`、**无冲突**、必需检查通过。
- [ ] 旧 PR 若被取代 → 评论说明后**关闭**（本项目 PR #5 已关闭）。
- [ ] 确认**只有一个**目标 PR 开放（MERGEABLE / CLEAN）。
- [ ] **给出合并建议（推荐 Squash and merge）→ 由仓库所有者授权后合并**；**无授权不自合并**。
- [ ] 合并后核对 `main` 最新 SHA、CI 结果、主题文件完整性。

---

## 阶段 7 — 打 tag / 发布

- [ ] 合并 main **之后**再决定版本号（**不提前移动旧 tag**）。
- [ ] tag 格式与历史一致（`v*`）；tag 推送会触发 Release 全站审计（14 个 job）。
- [ ] 确认 `v1.0.9` 等历史 tag **未被动过**。
- [ ] CHANGELOG 已更新（`check_docs.py` 校验）。
- [ ] 发布后再次确认 Release 审计通过。

> **本项目当前状态**：`v1.0.9` tag 未移动、无 Release（**已证实**）。是否打新 tag 由所有者在合并后决定。

---

## 附录 A — 阻断项判定（什么才值得在冻结后动手）

**只有**满足以下之一才在冻结后修改：

1. 候选 SHA **缺乏完整 CI 证据**；
2. 构建 / 核心功能 / 兼容测试**失败**；
3. 历史报告中的**高优先级产品缺陷复现**；
4. PR 存在**真实合并冲突**或必需的检查失败；
5. 有证据表明存在**影响最终交付判断的严重假绿门禁**。

每处修复都必须写明：**复现步骤 → 实际影响 → 根因 → 最小修复 → 验证**。
非以上情形 → **立即停止开发，不顺手改**。

---

## 附录 B — 本项目本轮实际执行的完整链路（证据）

> **SHA 口径**：主题代码与文档沉淀是**不同的提交**，CI 结果**按 SHA 一一绑定**，不得混用。

**B.1 主题代码基线 `8363d4b89193a7dfa22bc1569918a4eb666865cd`（含全部运行时文件）**

| 步骤 | 实际结果 | 证据 |
| --- | --- | --- |
| 冻结候选 SHA | `8363d4b89193a7dfa22bc1569918a4eb666865cd` | `git rev-parse HEAD` |
| 该 SHA 的 PR CI | `38171213190`（11 success + 1 skipped Release） | GitHub Actions |
| 该 SHA 的 dispatch CI | `38171253788`（**14/14**，含 Release 三引擎） | GitHub Actions |
| 合并阻断项 | **无** | 见 `SKILL_HANDOFF.md` |
| 最终状态 | **READY_TO_MERGE**（不自行合并） | — |

**B.2 文档沉淀提交 `e03a6c801090aeaa682a2e55d671acd3578c2e17`（docs-only，`8363d4b` + 1 提交）**

| 步骤 | 实际结果 | 证据 |
| --- | --- | --- |
| 变更范围 | 仅 `docs/skill-source/*.md`（`git diff 8363d4b..e03a6c8 --name-only`） | git |
| 该 SHA 的 PR CI | `38188954023`（**success**，11 pass + Release skipped） | GitHub Actions |
| 该 SHA 的 dispatch CI | `38189345376`（**14/14**，含 Release 三引擎全站审计） | GitHub Actions |

**B.3 实时仓库状态（核对时间：本轮文档修订时）**

| 项 | 值 | 证据 |
| --- | --- | --- |
| 候选分支 tip | 以 `git ls-remote origin refs/heads/feat/theme-feature-completion` 为准 | git |
| 开放 PR | **仅 #6**（MERGEABLE / CLEAN） | `gh pr list --state open` |
| 旧 PR #5 | **已关闭**（`2026-10-12T00:33:29Z`），修复已被 #6 覆盖 | `gh pr view 5` |
| `main` | `21745162da343f2a0809516148b1a5680893390e`（未改动） | `git ls-remote` |
| `v1.0.9` tag | `6168bb13b68014ea18953df6c7dc40078d581868`（未移动） | `git ls-remote --tags` |
| Release | 无 | `gh release list` |
| 合并状态 | **未合并**（需所有者授权） | — |

> **反例警示**：CI #112（`38145051430`, 14/14）实际跑在 `4a4ea01`，**不是** `8363d4b`；
> 因此 `8363d4b` 的 14/14 是**重新执行**取得的，而不是沿用更早 SHA 的结果。
> 这正是"**不得把旧 SHA 的 CI 套用到新提交**"的真实教训。

---

## 附录 C — 迁移到通用主题 Skill 的建议

| 可固化 | 不硬编码 |
| --- | --- |
| 0–7 阶段骨架 | 具体 SHA、PR 号 |
| "冻结 SHA 绑定证据"原则 | 具体 CI run id |
| "只修真正阻断项"判定表 | Nebula 的 issue 编号 |
| "Release 审计 = inventory 真值" | 页面数（212/291/122） |
| "合并需所有者授权" | 具体 PR 标题/分支名 |
| "tag 在合并后决定" | 具体版本号 |
