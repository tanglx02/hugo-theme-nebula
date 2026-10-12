# TESTING_STRATEGY — 测试分层与执行策略

> 资料性质：可用于通用 Hugo 主题开发 Skill 的经验沉淀。
> 事实标注约定：**【已证实】**＝有真实代码/CI 记录/构建产物支撑；**【结论】**＝开发方基于证据的判断；**【待验证】**＝尚未经独立第三方验收。
> 本文档描述的是 Nebula 主题实际使用的测试体系，供后续主题复用其**分层思路**，而非照抄具体脚本名。

---

## 0. 一句话原则

**测试的目标不是"跑绿"，而是"坏了一定会变红，好了一定不冤枉"。**

因此本项目的测试体系有两条正交的轴：

1. **分层轴**：哪一类测试覆盖哪一类风险，哪些是合并门禁、哪些是发布门禁、哪些只是辅助。
2. **可信度轴**：每一条重要断言都必须能用**故意故障注入**证明它真的会失败。

只做了第一轴、没做第二轴，就会产生"假绿"（false green）——这是本项目历史缺陷中最严重、最反复的一类（20+ 条 TEST-DEFECT）。详见 `TESTING_FAILURES.md`。

---

## 1. 测试分层矩阵

| 层级 | 目的 | 判定对象 | 是否需要浏览器 | 执行时机 | 是否合并门禁 |
| --- | --- | --- | --- | --- | --- |
| L0 单元测试 | 校验测试工具自身的语义（URL 规范化、配置解码、重试逻辑） | Python 函数 | 否 | 每次提交 | 是 |
| L1 主题构建测试 | 主题在目标 Hugo 版本上**能否成功构建**、产物是否齐全 | Hugo 退出码 + `public/` 目录 | 否 | 每次提交（多版本矩阵） | 是 |
| L2 静态检查 | 源码/产物中不得出现的模式（硬编码文案、危险 scheme、重复 id、CI 结构回退） | `layouts/`、`assets/`、`public/`、workflow YAML | 否 | 每次提交 | 是 |
| L3 构建产物内容审计 | 对真实 HTML 产物断言功能语义（首页布局标记、组件结构、SEO 字段、搜索索引） | `public/**/*.html`、`index.json` | 否 | 每次提交 | 是 |
| L4 浏览器行为测试 | 真实浏览器里的交互、无障碍、视觉、懒加载、竞态 | 运行中的站点 | 是（Playwright） | 每次提交（三引擎矩阵） | 是 |
| L5 全站审计（Release） | 对**全部构建产物页面**做横向审计（溢出/控制台/404/破图/点击区） | inventory 真值 × 浏览器 | 是 | 仅 tag 或手动触发 | 发布门禁 |
| L6 版本兼容矩阵 | 主题在支持范围内的多个 Hugo 版本上行为一致 | 多版本构建产物 | 部分 | 每次提交（矩阵 job） | 是 |
| L7 独立第三方验收 | 由**不了解实现**的第三方独立复核，防止开发方自证偏差 | 交付物 + 文档 | 是 | 功能冻结后、合并前 | 交接门禁 | 

**【结论】** 分层的价值在于：**低层快速失败、高层慢速兜底**。L0–L3 在几十秒内给出信号；L4/L5 成本高但能发现静态断言看不见的真实缺陷。

---

## 2. 各层 MUST-RUN vs OPTIONAL

### 2.1 MUST-RUN（阻断合并）

以下门禁必须进入 CI 且**失败即阻断**（`exit≠0`，不是打印警告）：

- **L1**：`build` 矩阵（0.128.0 / 0.148.0 / 0.162.0 / 0.166.0 / 0.167.0 / latest）全部成功；`subdir`（`/blog/` baseURL）成功。
- **L2**：`check_i18n_hardcode.py`、`security_baseline.py`、`check_workflow_policy.py`、`check_ci_jobs.py`、`check_docs.py`。
- **L3**：`check_index.py`、`check_features.py`、`check_html_quality.py`、`check_seo.py`、`link_check.py`、`check_alias_pages.py`、`check_home_layouts.py`、`check_new_features.py`、`check_author_pages.py`、`check_content_components.py`、`check_lang_config.py`。
- **L4**：`audit.py`（抽样视口）、`interactions.py`、`verify_copy.py`、`verify_lightbox.py`、`verify_search_modal.py`、`verify_search_edge.py`、`verify_search_highlight.py`、`verify_search_shard.py`、`verify_modal_scroll.py`、`verify_contrast.py`、`check_responsive_overflow.py`、`check_reading_experience.py`（B 小节）。
- **L6**：`check_search_modes.py`、`check_lang_config.py`、`check_content_components.py` 的多版本断言。

**【已证实】** `.github/workflows/ci.yml` 中这些步骤均以 `run: python3 tools/xxx.py` 形式接入，任一非零退出即 job 失败。

### 2.2 OPTIONAL / 辅助（不阻断，按需运行）

- `repeat_check.py`：把某个浏览器脚本对同一 URL 连跑 N 次，专门暴露**flaky 脆弱断言**。排在排障阶段，不进主门禁。
- `bench_index.py` / `perf_baseline.py`：索引规模与首屏性能测量，只记录数值，不做阈值判定（阈值随机器波动，硬判会误红）。
- `compat-latest.yml`：`ubuntu-latest` + latest Hugo 的**前瞻**兼容检查，**故意不设为门禁**（平台迁移可能带来非主题问题），仅提供早期信号。

**【结论】** OPTIONAL 的判定标准是：**结论本身不稳定**（性能、平台前瞻）或**只在特定排障场景需要**（flaky 复现）。把它们设为门禁只会制造噪声。

---

## 3. 门禁可信度的核心方法：故障注入自证

### 3.1 原则

> **重要测试必须通过故意注入故障证明它可以失败。**

一个断言如果从来没红过，就不知道它是否真的在检查东西。本项目的做法：

1. 备份目标文件 → 2. 注入一个**必然破坏该契约**的改动 → 3. 跑门禁 → 4. **确认 `exit≠0` 且报错指向正确** → 5. 还原 → 6. 回读核验还原成功 → 7. 复跑确认回绿。

### 3.2 两种注入形态

| 形态 | 说明 | 例子 |
| --- | --- | --- |
| 内置 `--selftest` | 脚本自带注入逻辑，一条命令证明自己会红 | `check_new_features.py --selftest`（5 类注入）、`check_ci_jobs.py --selftest`（8 类） |
| 外部注入 | 手动改模板/CSS/配置后跑门禁 | 把 `.author-link` 退回 inline → `check_author_pages.py` ON23/ON24 变红 |

**【已证实】** 本项目在最终自测阶段对每个新门禁都做过注入自证，记录见 `docs/final-cleanup-issue-tracker.md` §10.5。

### 3.3 注入必须"强"

**【已证实·真实踩坑】** 对 `check_home_layouts.py` 首次用 `home-profile-BROKEN` 注入**没有变红**——因为断言的 `contains()` 是子串匹配，`home-profile-BROKEN` 仍包含 `home-profile`。这不是测试假绿，而是**注入方法太弱**。改用"彻底移除标记"的强注入后按预期变红。

> **教训**：注入要"实际上破坏契约"，不是"看起来像破坏"。子串匹配断言对应的注入必须改变子串本身，而不是在其周围加字。

---

## 4. 版本兼容矩阵策略（L6）

Hugo 版本升级频繁，跨版本差异是本项目缺陷高发区（`slicestr` rune 语义、`resources.Publish`、`.Language.Locale`、`reflect.IsImageResourceProcessable`、`[languages.*]` 顶层字段弃用）。

策略：

1. **固定一组版本坐标**：`0.128.0`（最低支持）/ `0.148.0`（中间）/ `0.162.0` / `0.166.0`（分片能力引入）/ `0.167.0`（当前稳定）/ `latest`（前瞻）。
2. **能力探测而非版本硬编码**：模板中用 `hugo.Version` 解析 major/minor，先探测再用；**禁止 `cond`**（Go 模板 `cond` 会先求值两个分支，触发旧版本不存在的字段访问错误）。
3. **每个版本真实构建**：不是"读文档判断"，而是 CI 里逐版本 `hugo` 真实构建 exampleSite，断言 `rc=0 / ERROR=0 / 页面数一致`。
4. **旧版本明确行为**：不支持的能力要么回退（打 WARN），要么**明确报错**，绝不静默降级。

---

## 5. 浏览器行为测试的引擎子集策略（L4）

不同浏览器引擎能跑的测试子集不同（成本和差异）：

| 脚本 | chromium | firefox | webkit | 理由 |
| --- | --- | --- | --- | --- |
| `interactions.py` | 10 个测试函数 | 4 个 | 2 个 | 交互面广、chromium 差异最全 |
| `verify_search_edge/highlight/shard` | ✅ | ✅ | ✅ | 搜索竞态存在真实引擎差异（TEST-DEFECT-R2-002） |
| `verify_modal_scroll.py` | ✅ | ✅ | ✅ | P1 回归在三大引擎都会复现 |
| `audit.py`（抽样视口） | 7 个视口 | 3 个 | 3 个 | 视觉/溢出差异 |

**【结论】** 三引擎"全跑同一套"既慢又无必要；对**已知存在引擎差异**的路径（搜索竞态、modal 滚动）三引擎全跑，对一般交互按成本取子集。**这是有依据的取舍，不是偷懒**——但它**必须显式登记**（`interactions.py` 注解、`check_ci_jobs.py` 的矩阵取值校验），否则会被误读为"漏跑"。

---

## 6. Release 全站审计：三条独立证据链（L5）

详见 `docs/稳定基线.md` §4。核心思想：

> **构建产物 inventory 是唯一真值；sitemap 不是。**

三条链互不冒充：

1. **inventory → 浏览器**：`public/**/*.html` 100% 被加载审计，硬断言 `EXPECTED == AUDITED`。
2. **pagination crawler**：所有可爬取分页页必须能从列表页走到（交叉验证）。
3. **alias 静态结构**：浏览器打开 alias 会重定向，观察到的是目标页，故 alias 必须**单独静态验证**。

**【已证实】** `AUDIT_REQUIRE_INVENTORY=1` 时 inventory 缺失即 FATAL；inventory 绑定本次构建指纹（`build_id`），防止跨次复用。

---

## 7. 独立第三方验收（L7）

### 7.1 为什么需要

开发方自测有**系统性偏差**：只测自己想到的场景，断言写得贴合自己的实现。第三方在**不知道实现**的前提下复核，能发现"开发方认为理所当然、其实有 bug"的地方。

### 7.2 怎么让第三方"只测不改"

- **固定候选 SHA**：第三方拿到的是某个**具体 commit SHA** 的产物，不是"当前分支"。防止测试期间代码漂移。
- **证据归档**：第三方报告必须给出可复现命令、实测数字、注入记录，而不是"我认为"。
- **职责隔离**：第三方只输出"问题清单 + 复现方式"，**不改代码**。修复由开发方按 min-imal fix 原则处理，再交第三方复验。
- **验收轮次的收尾**：第三方遗留问题单独编号（本项目为 R3 轮），逐条处理并回归。

**【结论】** 本项目的流程是"开发方自测 → 第三方独立验收 → 遗留项收尾 → 再验收"，每一轮都收敛，不无限循环。

---

## 8. 退出码约定：门禁可信的前提

**【已证实】** 所有脚本遵循 `tools/_testlib.py` 的约定：

| 情形 | 退出码 |
| --- | --- |
| 全部断言通过 | 0 |
| 断言失败 / 依赖缺失 / 浏览器启动失败 / 站点不可达 / 零用例执行 | 1（且不得静默跳过） |

**任何"打印 FAIL 但退出 0"都是不可接受的**——这是 CI 门禁失去意义的根因。`Harness` 统一 `record/fatal_error/finish`，最后一行为机器可解析的 `TEST-RESULT: {...}`。

> **关键推论**：`exit 0` 的同时若"零用例执行"，必须判**失败**，否则脚本路径写错/夹具缺失会静默变成"通过"。这是 TEST-DEFECT-019/005/007/008 的共同教训。

---

## 9. 测试的边界（不做什么）

- **不为凑数加用例**：断言的价值在于覆盖真实风险，不在于数量。
- **不改已通过的阈值来让它过**：阈值放宽等于删门禁。
- **不测不可控项**：真实第三方服务连通性（需账号）、真实屏幕阅读器（NVDA/VoiceOver）——如实登记为"未验证"，不冒充已验。
- **不用固定 sleep 判时序**：等待状态稳定（有界重试），否则必然 flaky（TEST-DEFECT-R2-009、R4-008）。

---

## 10. 迁移到通用主题 Skill 的建议

| 可直接复用 | Nebula 专有（不应硬编码进通用 Skill） |
| --- | --- |
| 分层思路（L0–L7） | 具体脚本名（`check_index.py` 等） |
| 故障注入自证方法论 | 具体注入类别编号（A–G） |
| 退出码约定 | `TEST-RESULT` JSON 的具体字段 |
| "inventory 是真值，sitemap 不是" | 具体页面数（212/291/122） |
| 能力探测 > 版本硬编码 | 具体 Hugo 版本号组合 |
| 第三方只测不改 + 固定 SHA | 具体 issue 编号（BUG-P1-001 等） |

**【结论】** 通用 Skill 应传递**方法**（怎么分层、怎么证明门禁有效、怎么约定退出码），而非**实例**（本项目恰好检查了哪些具体字符串）。
