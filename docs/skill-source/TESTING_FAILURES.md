# TESTING_FAILURES — 测试失效案例集（假绿 / 假红 / 环境陷阱）

> 资料性质：用于通用 Hugo 主题开发 Skill 的经验沉淀。
> 事实标注：**【已证实】**＝有真实代码/CI/运行记录；**【结论】**＝开发方判断；**【待验证】**＝未经独立第三方确认。
>
> 本文件记录本项目**真实发生过**的测试失效，每类给出：现象 → 根因 → 如何识别 → 如何预防。
> 这是全项目最有复用价值的一节：**测试体系的缺陷比产品缺陷更隐蔽，因为它会让产品缺陷蒙混过关。**

---

## 0. 分类速查

| 类别 | 危害 | 典型编号 |
| --- | --- | --- |
| A. 假绿（false green） | 最危险：坏了还报绿 | TEST-DEFECT-005/007/008/010/019、R2-001/002、R3-001/002、R4-006、check_index contentLimit |
| B. 假红（false red / flaky） | 浪费信任：好也报坏 | R4-008、TEST-DEFECT-R2-009 |
| C. 残留/陈旧产物 | 把上一次的产物当本次结果 | TEST-DEFECT-R2-006、R4-003、verify_baseurl 残留产物 |
| D. 夹具污染 | 状态跨用例泄漏 | TEST-DEFECT-R2-004/005、2026 注记 |
| E. 环境缺失被静默跳过 | "没装就没测"伪装成"测了且过" | 浏览器未安装、Pillow 缺失 |
| F. CI 步骤被静默关闭 | 门禁形同虚设 | TEST-DEFECT-020、R2-002 系列 |
| G. 忽略退出码 | 失败被吞 | TEST-DEFECT-R2-008 |
| H. 固定 sleep 判时序 | 必然偶发 | TEST-DEFECT-R2-009 |

---

## A. 假绿（false green）——最高优先级

### A1. 恒真断言（断言实际上什么都没检查）

**现象**：门禁永远 PASS，无论实现怎么改。

**真实案例【已证实】**：

- **TEST-DEFECT-005**：`verify_multisection.py` 源码扫描"扫不到模板"时**恒真通过**——路径写错/文件缺失时，0 个匹配反而算通过。
- **TEST-DEFECT-007**：`check_seo.py` 在没有 `posts` 产物时**真空通过**（循环体一次都不执行）。
- **TEST-DEFECT-010**：多处正则/包含断言缺**非空断言**，匹配 0 项即通过。
- **TEST-DEFECT-008**：安全基线门禁在 `public/` 有 0 个 HTML 时仍 PASS。

**根因**：断言写成"对集合中每一项都成立"，而集合为空时**空洞真（vacuous truth）**。

**如何识别**：
- 问自己："如果要让这条断言失败，需要存在什么？如果那个东西不存在会怎样？"
- 如果答案是"不存在也算通过"，就是假绿。

**如何预防（本项目已落地）**：
1. **先断言输入非空**：`assert files, "未扫到任何文件——路径或产物缺失"`。
2. **零用例即失败**：`Harness` 在"断言数为 0"时 `fatal_error`。
3. **故障注入自证**：删掉被检查的东西，门禁必须红。

---

### A2. 正则只认一种写法（被 minify / 单引号 / 无引号绕过）

**现象**：检查 URL/事件属性的正则只匹配双引号，而 Hugo `--minify` 会去掉引号，导致断言恒不命中。

**真实案例【已证实】**：

- **TEST-DEFECT-001**：JSON-LD 校验因 `--minify` 去掉引号而**恒真**。
- **TEST-DEFECT-002**：`security_baseline.py` 的 URL/事件正则只认双引号，单引号/无引号写法绕过（且需同源豁免避免误判）。

**如何预防**：断言前**规范化**（如去引号、压缩空白），或让正则容忍 `["']?`。更稳的做法是**解析产物结构**而非字符串匹配。

---

### A3. 变量被覆盖 / 作用域错误

**真实案例【已证实】**：

- **TEST-DEFECT-R3-002**：`check_features.py` 的变量 `m` 被前面的段覆盖，导致地区后缀判定**恒走错误分支**。
- **TEST-DEFECT-R3-003**：`check_lang_config.py` 的 L8 反证因**同名键遮蔽**而无效。

**如何预防**：反证用例必须**独立变量**；反证本身也要注入证明有效。

---

### A4. "条件式守护"给错值：把配置感知做成了放水

**真实案例【已证实·本轮修复】**：`check_index.py` 的 contentLimit 逻辑在扫描"构建源根"的 `*.toml` 时，**无条件扫描 `<BUILD_DIR>` 上一层目录**。于是一个**残留的、未被本次构建使用的 TOML**（只要恰好含 `[params.search].contentLimit`）就会让**被截断的索引**进入"配置模式"，从而按"有界性"放行 → **假绿**。

**修复**：新增 `_looks_like_build_source(d)`，只有该目录**确实是 Hugo 源根**（含 `hugo.toml`/`config.toml`/`content/`）时才扫描其中的 TOML。

**如何预防**：
- 配置来源必须**绑定到本次构建实际使用的源根**，而不是"目录里碰巧有个配置文件"。
- 配套 `tools/test_check_index.py` 固化 5 种行为（默认完整绿 / 默认截断红 / 配置下合法截断绿 / 超上限红 / 整段丢失红）。

---

### A5. 通过 `--config` 叠加层的配置感知不到 → 假红

**真实案例【已证实】**：**TEST-DEFECT-R3-011**：构建用 `--config hugo.toml,overlay.toml` 设置 `contentLimit` 时，检查脚本感知不到该配置，把**合法截断**按"未配置"严格校验 → **假红**。

**如何预防**：配置感知必须覆盖**叠加层**（`<源根>/*.toml` 与 `exampleSite/*.toml`），跳过 `_` 前缀的临时文件。

---

## B. 假红 / flaky —— 第二优先级（会侵蚀信任）

### B1. 双读 DOM 造成自相矛盾

**现象**：断言判定时读一次 DOM、拼错误详情时又读一次，异步状态在两次读取之间变化 → **假红**，且详情"看起来完全正常"。

**真实案例【已证实】**：**R4-008**：`verify_search_shard.py` 每个断言 lambda 把 `count_items(pg)` / `status_text(pg)` **各自读两次**。firefox 上约 1/几 概率出现：判定时 status 为"部分失败"→判红；打印详情时已恢复 `""`，显示 `1 条, status=""`。

**修复**：改为**一次快照** `read_state(pg)` 一次性读全；判定与详情取自同一时刻；`run_case` 首判失败后**等 UI 稳定再判**（最多 3 次）。真实缺陷是**稳定地坏**的，重试仍会红 → **断言强度不变**，只消除"读得太早"。

**如何预防**：**异步页面上，一次操作一次快照**；永远不要在"判定"和"报错信息"里各读一次。

---

### B2. CSS 过渡 / 平滑滚动造成读数失真

**真实案例【已证实】**：

- **BUG-P2-003 复验**：主题带 `transition: all .2s`，切换主题后**立刻取色**会读到**过渡中间值**（把 dark 的 5.19:1 读成 1.1:1 的假故障）。修复：**度量前禁用过渡**。
- **TEST-DEFECT-R2-009**：滚动断言因 `html{scroll-behavior:smooth}` + 绝对阈值偶发假红。修复：回顶统一 `behavior:'instant'`，判定改用**相对位移**（`y > y0+50`）；`repeat_check.py` 固化连跑复现。

**如何预防**：涉及动画/过渡的度量，**先关闭动画**再测；涉及时序的断言用**相对**判据 + 有界等待，不用固定 sleep。

---

### B3. 溢出比较用错对象（inline 元素 `min-height` 无效）

**真实案例【已证实】**：**R5-001**：M16 新增 `.author-link` 只写了 `color`/`text-decoration`，`<a>` 仍是 **inline** 元素 —— 而 **`min-height` 对 inline 元素无效**。真实浏览器实测渲染为 40×24px，被 `audit.py` 在 4 个窄视口各报 6 处（共 24 处）。**该缺陷由真实浏览器审计发现，静态字符串断言（只断言"链接存在"）抓不到**。

**修复**：`.author-link` 显式 `display:inline-flex; align-items:center; min-height:26px`；并在 `check_author_pages.py` 新增 ON22–ON24，**直接断言构建产物打包 CSS** 中的规则必须含 `display:inline-flex/inline-block` 且 `min-height≥24px`。

> 同根因先例：**R4-007**（`.article-external-notice a` 被 flex 块级化 → 98×23px）。

**如何预防**：**触控目标/尺寸类断言必须落到构建产物 CSS 的规则级**，不能只断言"元素存在"。

---

## C. 残留 / 陈旧产物

### C1. 复用上次构建目录 → 实测假绿

**真实案例【已证实】**：**TEST-DEFECT-R2-006**：`subdir_test.py` 复用 `tmp/public-blog`，上次残留 HTML 被当成本次结果 → **实测假绿**。修复：构建前清空（`safe_rmtree` 边界校验）。

### C2. Hugo 非零退出但留下上次 HTML

**真实案例【已证实】**：`verify_baseurl.py` 的 `--selftest-exitcode` 用一个"**残留产物 + 非零退出码**的假 hugo"自证：绝**不**把上次残留 HTML 当本次有效产物。**TEST-DEFECT-R2-008**：`build()` 曾忽略 Hugo 退出码。

**如何预防**：
1. **构建前清空目标目录**（边界校验后 `rmtree`）。
2. **看真实 `returncode`**，非零即失败。
3. **inventory 绑定构建指纹**（`build_id`），跨次复用即报错。

---

## D. 夹具 / 临时文件污染

**真实案例【已证实】**：

- **TEST-DEFECT-R2-004**：`verify_multisection` / `gen_testdata` 异常路径不清理 → 用 `finally` 清理 + 边界校验。
- **TEST-DEFECT-R2-005**：`check_comments` 失败时泄漏 `tools/_ml-giscus.toml` → `.gitignore` 显式加入 + `finally` 清理。
- **R4-003**：`exampleSite/_ms-verify-multisec-*.toml` 因上次被 SIGTERM 打断 `finally` 而残留。

**如何预防**：
- 所有临时文件走 `TempWorkspace`（退出即清）。
- 异常路径也必须清理（`try/finally`）。
- 临时文件统一 `_` 前缀，被配置扫描显式跳过。
- `.gitignore` 显式登记可能泄漏的夹具名。

---

## E. 环境缺失被静默跳过

### E1. 浏览器未安装 → 闸门"通过"

**真实案例【已证实】**：`static-checks` job 曾**从未安装 Playwright 浏览器**，导致 `check_reading_experience.py` 的 B 小节仅在**浏览器启动处失败**（静态部分 48/48 通过、3 条启动失败）。表面上"静态全过"，实际真实行为断言根本没跑。

> `_testlib.launch` 的契约是：**依赖缺失即致命错误，不静默跳过**——所以它至少会失败；但如果脚本写成"启动失败就 skip"，就会变成假绿。

**如何预防**：
- 依赖缺失 = **致命错误**（`exit 1`），不是 skip。
- CI 中显式 `playwright install --with-deps <engine>`。
- 若某断言子集需要浏览器，job 必须装浏览器（或在门禁登记中注明）。

### E2. Pillow 缺失 → 图片管线分支永不被构建到

**真实案例【已证实】**：`.github/workflows/ci.yml` 注释明确记录：**没有 Pillow 时 `gen_testdata` 会跳过 `zz-images-bundle`，于是 `render-image` 的图片处理分支永远不会被构建到 —— 这正是 Hugo 0.128 上 `reflect.IsImageResourceProcessable` 不兼容长期未被发现的原因**（只在装了 Pillow 的浏览器 job 才触发）。

**如何预防**：**构建（含生成夹具）所需依赖必须在所有相关 job 中安装**；并在构建后**断言关键产物存在**（CI 里有 `Check boundary fixtures are present` 步骤，`grep -q 'srcset=' ...`）。

---

## F. CI 步骤被静默关闭

**真实案例【已证实】**：**TEST-DEFECT-020 / R2-002**：CI 中 chromium 专属步骤**可能静默消失（实为 7 个）**。修复：`check_ci_jobs.py --selftest` 覆盖 8 类注入——`delete-step` / `step-if-false` / `job-if-false` / `continue-on-error` / `echo-skipped`（`run` 换成 `echo skipped`）/ `单引擎`（三引擎检查改单引擎）/ `换矩阵` / `drop-search-langs`。

此外新增：
- **job 级恒假条件**校验；
- **matrix 条件步骤取值存在性**校验；
- **关键步骤环境变量契约**（`REQUIRED_STEP_ENV`，如搜索弹窗步骤必须登记 `SEARCH_MODAL_URLS` 与 `REQUIRE_SEARCH_LANGS='1'`）。

**如何预防**：**把"门禁结构"本身当成被测对象**。任何"加/删/禁用步骤、改矩阵、加 `if: false`、加 `continue-on-error`"都必须让 CI 变红，除非同步更新登记。

---

## G. 忽略退出码

**真实案例【已证实】**：**TEST-DEFECT-R2-008**（`verify_baseurl.build()` 忽略 Hugo 退出码）、**TEST-DEFECT-009**（`subdir_test` 无退出码）、**TEST-DEFECT-018**（`compat_matrix`/`repro_search` 无断言）。

**如何预防**：所有子进程调用**必须检查 `returncode`**；统一走 `Harness`，不允许裸 `subprocess.run()` 不看返回。

---

## H. 固定 sleep 判时序

**现象**：用 `sleep(2)` 等异步完成 → 慢机器偶发假红、快机器掩盖竞态。

**如何预防**：
- 使用**有界轮询/重试**（如 `run_case` 最多 3 次，每次等 UI 稳定）。
- 判定用**相对**条件（`y > y0+50`）而非绝对阈值。
- 用 `repeat_check.py` 连跑暴露 flaky，再针对性修。

---

## 9. 通用检查清单（每次新增/修改门禁时逐条过）

1. [ ] 断言**输入非空**？零用例会失败吗？
2. [ ] 有没有**恒真分支**（空集合、`if not found: pass`）？
3. [ ] 正则**容忍 minify**（去引号）、单引号、无引号写法了吗？
4. [ ] 配置感知**绑定到本次构建源根**了吗？覆盖 `--config` 叠加层了吗？
5. [ ] 异步页面**一次快照**了吗？判定与报错信息取自同一时刻吗？
6. [ ] 涉及动画/过渡的度量**先禁用动画**了吗？
7. [ ] 尺寸/触控目标断言**落到构建产物 CSS 规则**，而不是"元素存在"吗？
8. [ ] 构建前**清空**目标目录了吗？看 `returncode` 了吗？
9. [ ] 临时文件**异常路径也清理**了吗？`.gitignore` 覆盖了吗？
10. [ ] 依赖缺失是**致命错误**还是被 skip 了？
11. [ ] 这条门禁**做过故障注入自证**吗？注入够强吗？
12. [ ] 若改动了 CI 结构，`check_ci_jobs.py` / `check_workflow_policy.py` 登记同步了吗？

> **第 11 条是最重要的**：本项目所有重大假绿/假红，最终都是靠"必须能失败"这条硬要求暴露并修掉的。

---

## 10. 迁移到通用主题 Skill 的建议

| 可直接复用 | Nebula 专有（不硬编码进通用 Skill） |
| --- | --- |
| 上述 A–H 分类与检查清单 | 具体 issue 编号 |
| "零用例即失败""输入非空断言"原则 | `TEST-RESULT` JSON 字段名 |
| "配置感知绑定本次构建源根" | `contentLimit` 这一具体配置键 |
| "注入必须强"的教训 | `home-profile-BROKEN` 这一具体案例 |
| "异步一次快照"原则 | 具体脚本 `verify_search_shard.py` |
| "门禁结构也是被测对象" | 具体的 8 类注入编号 |

**【结论】** 通用 Skill 应传递**失败模式与预防原则**，而不是"本项目在某个脚本里踩过某个具体的坑"。踩坑案例适合作为**教学素材**，不适合作为**规则文本**。
