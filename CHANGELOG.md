# Changelog

本文件记录 Nebula 主题的版本变更。格式参考 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，
版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

## [1.0.9] — 2026-10-09

最终封版：搜索日期 i18n、pagination crawler 判定、GitHub Actions 现代化。
v1.0.9 起作为长期稳定基线，后续按「开发 → 测试 → CI → Release」正常迭代
（契约清单见 `docs/稳定基线.md`）。

### 修复：搜索结果日期没有 i18n（最后一个真实 UI 国际化缺陷）

- `index.json` 新增 UI 字段 `dateDisplay`，由 Hugo **在构建期**用
  `i18n "common.dateFormat"` 生成；`date` 保留为机器字段 `YYYY-MM-DD`
- `assets/js/main.js` 搜索结果改为输出 `dateDisplay`：前端不再猜语言、
  也不再重复实现日期格式化（旧索引无该字段时才退回 `date`）
- 缺日期的文章两个字段均为空串，UI 省略日期片段，绝不显示 `0001-01-01` / `January 1`
- 新增 `tools/check_search_date.py`（30 项）：zh-CN / en / zh-TW 三语言真实构建 ×
  多篇文章 × 缺日期异常 × `date` 仍为机器格式 × JSON 结构向后兼容
  —— 期望值由测试自己按 i18n 布局重算，不复用被测逻辑
- `check_date_format.py` 增加索引日期契约断言（dateDisplay 必须走 i18n；
  JS 中禁止 `toLocaleDateString` / `Intl.DateTimeFormat`）
- 发现并修复测试侧隐患：语言切换配置必须复制到站点目录内再用相对路径 `--config`
  引用，否则 Hugo 会**静默忽略**它，表现为"英文构建实际仍是中文"

### 修复：pagination crawler 的 article 判断

- `is_article_page()` 改为基于 `params.content.sections`
  （回退 `params.content.section`，再回退 `posts/tutorials/notes/projects`）：
  `/categories/foo/`、`/tags/foo/`、`/archives/`、`/page/N/`、`/posts/page/2/`
  均不再被判成文章页（旧规则 `/[^/]+/[^/]+/` 会把两级 term 页误判为文章页）
- `pagination.path` 不再写死 `page`：优先从构建产物 URL 反推 token，
  再读 `[pagination] path`，最后才用默认值；新增 `detect_pagination_token()` /
  `is_pagination_page()`
- **种子排除分页页本身**：此前分页页也在种子里，新发现的分页全部命中 `visited`，
  `discovered` 恒为 0，交叉验证形同虚设（v1.0.8 Release 报告里的
  "DISCOVERED PAGINATION URLS = 0" 就是这个症状）。现在实测 6/6 全部发现
- 新增硬断言：构建产物中每个可爬取的分页页都必须能被 crawler 发现
  （`/page/1/` 别名分页页按设计不被链接，单独计数并由 inventory 覆盖）
- 新增 `tools/check_article_classification.py`（39 项）：判定表 + 旧规则误判回归证据 +
  `pagination.path = page` 与 `= p` 两种真实构建

### 新增：alias 页面专项静态检查

- 新增 `tools/check_alias_pages.py`（11 项）：文件存在 / meta refresh 唯一且带目标 /
  canonical 存在 / 目标为构建产物中的真实页面 / 无自引用 / 无 `<script>` 与 inline 事件 /
  本地资源完好 / `lang` 合法且与站点一致 / title 非空
- Release 报告现在区分「alias HTML 结构检查」与「普通 HTML 页面浏览器行为审计」：
  浏览器加载 alias 会被重定向到 canonical，观察到的其实是目标页
- 新增 `layouts/alias.html`：修正"站点页面 `lang=zh`、Hugo 内建 alias 模板 `lang=zh-CN`"
  的不一致；同时补上 `robots: noindex`，并保证 alias 页不含任何脚本

### 修正：CI job 数量报告（此前一直写成 13）

- v1.0.8 及之前的报告把 tag CI 写成 `13/13 job 全绿`，而 matrix 展开后实际是 **12**
  （build 4 + subdir 1 + static-checks 1 + browser-tests 3 + release-full-audit 3）
- 新增 `tools/check_ci_jobs.py`：按 GitHub matrix 展开规则计算每个 job 的实际数量，
  与 workflow 注释里的 `# CI-JOBS:` 清单比对；改 matrix 不更新清单即 CI 变红
- workflow 内登记：`CI-JOBS-TOTAL: 12`、`CI-JOBS-PUSH-TOTAL: 9`（非 tag 推送）
- 同步修正 `docs/验收报告-v1.0.5/6/7/8.md` 中的错误数字

### GitHub Actions 现代化

- Action 升级到 Node 24 兼容稳定版：`actions/checkout@v7.0.1`、
  `actions/setup-python@v7.0.0`、`actions/cache@v6.1.0`、
  `actions/upload-artifact@v7.0.2`
- `peaceiris/actions-hugo` 保持 v3 线（v3.1.0 起即为 node24），**不为版本号好看而升级**，
  现显式固定 `@v3.2.1` 以便静态校验
- 生产门禁 runner 固定 `ubuntu-24.04`（`ubuntu-latest` 将于 2026-10-19 迁到 Ubuntu 26.04）；
  最新环境兼容性另建 `.github/workflows/compat-latest.yml`（`ubuntu-latest`，每周 + 手动），
  不计入生产门禁
- 顶层 `permissions: contents: read`；无 `*: write`；仅检出源码的 `subdir` job
  进一步设 `permissions: {}`
- 新增 `tools/check_workflow_policy.py`（4 项）：最小权限 / runner 固定 /
  Action Node24 版本基线 / 登记未注册的新 action

### 新增：搜索高亮特殊字符安全回归

- 新增 `tools/verify_search_highlight.py`（17 项，拦截注入索引内容）：
  `A&B <hello>`、`foo&bar`、`REGEX.*+?^${}()|[]\`、双引号/单引号、字面 `<mark>`、
  XSS 载荷 `<img src=x onerror=...>`
- 断言：文本不丢字不变形、`<hello>` 不变成元素、无残缺实体、`<mark>` 不嵌套、
  结果中无 `<img>`/`<script>`、`window.__xss` 未定义、全过程无 console error

### 新增：`docs/稳定基线.md`

修改主题前必读：Hugo 最低版本、支持浏览器、CI runner、CI job 结构、测试工具清单、
Release 全站 inventory、pagination crawler、search / modal / i18n / image / security
契约，以及下一阶段未做项（10000+ 基准、倒排索引、渐进加载、gzip/Brotli、屏幕阅读器）。

---

## [1.0.8] — 2026-10-08

正式长期维护基线：无障碍一致性、多语言一致性、测试文档同步。

### 搜索弹窗补齐完整 Modal 无障碍

- 抽取 `createModalA11y` 轻量工厂（零依赖），**灯箱与搜索共用同一份交互契约**：
  焦点移入 / Tab·Shift+Tab 循环 / 背景 `inert`+`aria-hidden` / Escape /
  遮罩关闭 / 焦点恢复 / 幂等开关 / 深链无触发元素时退化为聚焦 dialog 自身
- 移除两个组件各自重复的键盘处理（避免双重触发），灯箱行为无回归（21/21）
- 新增 `tools/verify_search_modal.py`：14 类断言共 19 项，含 zh-CN / en / zh-TW
  可访问名称（en 站不得出现硬编码中文）
- 改进 `/` 快捷键：原先要求焦点**恰为** body，实际关闭搜索后焦点停在触发器上导致
  快捷键失效；改为「非输入上下文」判断

### 日期格式彻底统一到 i18n

- 修复 4 处 UI 硬编码 `2006-01-02`（侧栏热门文章、最后修改日期、相关文章、日期比较）
- RSS / JSON-LD / `<time datetime>` / 搜索索引属机器格式，保留并在行内标注
  `machine-format:`，形成人机可读的显式契约
- 新增 `tools/check_date_format.py`：禁止 layouts 把 `2006-01-02` 用作 UI 日期
- 三语言实测：zh-CN `2026年9月28日` / en `Sep 28, 2026` / zh-TW 本地化格式

### 修正过时的「sitemap 全站」描述

统一表述为：**Release 全站审计以构建产物 HTML inventory 为真值；sitemap 作为独立
SEO 索引质量检查；分页 crawler 用于交叉验证额外分页，不再作为全站真值。**

- 修正 `tools/audit.py` docstring、CI step 名与注释、README
- `tools/check_docs.py` 新增可执行断言：三处必须声明 inventory 真值，
  且不得出现「sitemap = 全站」类过时表述

### inventory 自身一致性保护

- 两个不同 HTML 文件 normalize 成同一 URL 时立即 `exit 1`，并输出冲突文件路径
- 修复真实缺陷：已 percent-encoded 的目录名会被二次编码（`quote` 的 safe 补 `%`）
- 新增 `tools/test_inventory.py`：13 项（中文 / 空格 / URL 编码 / index.html /
  404.html / page-N / 冲突构造），跨平台一致
- Release 报告补 `site / alias / error / other` 分类（alias 不排除）

### 浮层无障碍契约纳入门禁

`tools/security_baseline.py` 增加 dialog 语义检查（`role` / `aria-modal` /
可访问名称），当前 258 处合规。以后任何新增 modal 都必须满足同一标准。

### 门禁验证（五次故意故障注入）

| 注入 | 结果 | Run |
| --- | --- | --- |
| A 删除搜索 focus trap | browser-tests 变红（焦点逃逸到 body、inert 残留） | `37787599767` |
| B 删除焦点恢复 | browser-tests 变红（灯箱与搜索**同时**报警） | `37788388147` |
| C 相关文章日期硬编码 | static-checks / Date format 变红 | 见报告 |
| D audit docstring 回退 | static-checks / Documentation consistency 变红 | `37788388147` |
| E inventory URL 冲突 | static-checks / HTML inventory 变红（210 组冲突） | `37787599767` |

> B 的注入是**共享工厂级缺陷**，灯箱的「关闭后焦点归还」断言同时报警 ——
> 这正是把两个浮层收敛到同一份契约的价值。

### 未改动

搜索架构（`auto` / `single` / `shard`、chunk 策略、竞态保护、失败提示）保持原样。
10000+ 篇基准、倒排索引、渐进式加载、Brotli/gzip 列入下一阶段。

## [1.0.7] — 2026-10-08

长期质量基线：Release 全站覆盖盲区修复。

### Release 审计真值改为构建产物 inventory

此前"全站"由 `sitemap + pagination crawler` 推出，但 **sitemap 是 SEO 索引、不是构建产物清单** ——
Hugo 允许页面通过 `sitemap.disable` 把自己排除出去，这类页面真实存在却完全不在"全站"统计里。
v1.0.6 的实测数据正是这样：sitemap 122 / audit 125 / public **212**（87 个页面被漏掉）。

- 新增 `tools/html_inventory.py`：递归扫描 `public/**/*.html` 并规范化为 URL
  （`index.html → /`，`about/index.html → /about/`，`404.html → /404.html`）；
  URL 统一 percent-encode（中文路径直接交给 `urlopen` 会抛 `UnicodeEncodeError`）
- 页面分三类仅用于报告、**不排除任何页面**：`site` 128 / `alias` 83（`/page/1/` meta-refresh 别名页）
  / `error` 1（`/404.html`）
- `audit.py` FULL 模式的审计 URL = inventory 真值 + sitemap 独有 + 新发现分页，
  硬断言 `EXPECTED == AUDITED`，任一差集即 `exit 1`
- sitemap 降级为独立质量项（可解析 / URL 合法），不再充当全站真值
- 404 探针不参与 inventory 比对

### 分页发现失败不再静默

旧实现在抓取异常时 `continue`，可能出现"fetch failed + 队列空 + exhausted=True + PASS"。

- 每个 URL 至少重试 2 次（总计 3 次尝试），记录 `discovery_attempts` / `discovery_retries` /
  `discovery_failures`
- `exhausted` 仅在「队列耗尽 **且** failures == 0 **且** 未达安全上限」时为 `true`
- 重试逻辑置于 `discover_pagination` 层，注入的假 fetch 也被覆盖，语义可被真实验证
- 新增 `tools/test_pagination_retry.py`：正常 / 1 败 2 成 / 2 败 3 成 / 全败 四场景，13/13

### HTML quality 与 browser audit 交叉验证

两者共用同一 inventory 模块与 URL 规范化：任一套漏掉新产出的 HTML 模板，双方计数或路径不一致即
`exit 1`。

### 安全基线

新增 `tools/security_baseline.py`（仅标准库）：`javascript:` / `vbscript:` / `data:text/html`、
空 `href`、`target=_blank` 缺 `noopener`、inline event handler、非预期外部 script / iframe /
第三方域名、危险 JS API、`markup.goldmark.renderer.unsafe` 配置。白名单全部可见打印并附豁免理由。

修复一处真实加固点：搜索结果把 `it.url` 拼接进 `href` 前未转义，现已 `esc()`。

### 文档一致性门禁

新增 `tools/check_docs.py`：README 不得回退为"零外部 CDN 请求"这类绝对化表述，必须列出
giscus / Waline / Twikoo / Disqus / busuanzi 五个第三方服务并说明默认关闭。

### 门禁验证（六次故意故障注入）

| 注入 | 结果 | Run |
| --- | --- | --- |
| A 从 audit 漏掉一个产物页面 | Release audit ×3 变红（`MISSING URLS = 1 ['/about/']`） | `37768173524` |
| B 分页发现首次失败 | 重试救回，覆盖证明仍全绿（FAILURES=0 / EXHAUSTED=YES） | `37768906011` |
| C 分页发现所有重试失败 | Release audit ×3 变红 | `37768173524` |
| D 页面不进 sitemap | inventory 发现并覆盖（EXPECTED 213），覆盖证明全绿 | `37768906011` |
| E 插入 `javascript:` 链接 | static-checks / Security baseline 变红 | `37768906011` |
| F README 回退错误 CDN 表述 | `check_docs.py` 变红（CI 中因 Security 先失败被跳过，本地取证） | 本地 |

### 未改动

搜索架构（`auto` / `single` / `shard`、chunk 策略、失败提示、竞态保护）保持原样。
10000+ 篇基准、倒排索引、渐进式加载、gzip/brotli、keyword→chunk 路由列入下一阶段。

## [1.0.6] — 2026-10-08

长期开发基线版本：发布门禁完善、多语言修复、文档纠正。

### 修复（真实产品缺陷）

- **分页发现不再"抽样冒充全站"**：`audit.py` 的 `discover_pagination()` 由固定 `rounds=3` 改为
  队列耗尽式 BFS；安全上限 `AUDIT_PAGINATION_LIMIT`（默认 10000）仅用于防失控，
  **达到上限即判定"未完成全站审计"并 FAIL**，不再以固定轮数当完成条件
- **评论组件 locale 跟随站点语言**：`comments.html` 中 giscus / Waline / Twikoo 的语言参数
  原本硬编码 `zh-CN`，现按 Hugo 语言映射（`zh*` → `zh-CN` / `zh-TW`，`en*` → `en`，
  未命中映射原样传递），并支持 per-provider 覆盖（`giscus.lang` 等）
- **全站 `<button>` 补齐 `type="button"`**：此前 516 处按钮缺少 `type` 属性
- **heading 层级修正**：侧栏 widget、分类卡片、个人昵称标题由 `h3` 改为 `h2`，
  消除 `h1 → h3` 跳级（CSS 选择器同步更新）
- **hreflang 大小写**：改用 `LanguageCode`，不再输出 Hugo 小写化的 `zh-cn`
- **og:locale**：输出 `zh_CN` / `en_US` 规范格式，并在多语言站点补充 `og:locale:alternate`
- **`verify_i18n.py` 两处潜在假绿**：`NEBULA_I18N` 断言兼容 minify（去引号键）与
  非压缩（带引号键）两种产物形态；文章页检查从硬编码压测文件名改为动态选取第一篇

### 新增

- `tools/check_pagination.py`：分页发现规模自测（1 / 3 / 10 / 100 分页、分类 / 标签 /
  多 section 分页、上限语义），基于真实 Hugo 构建产物，19 项断言
- `tools/check_comments.py`：四种 provider 渲染、locale 跟随站点语言、关闭时零第三方资源，12 项断言
- `tools/verify_multilingual.py`：真实 Hugo multilingual 构建回归（URL / hreflang / canonical /
  og:locale / RSS / sitemapindex / 分类标签隔离 / 搜索索引隔离 / Series 隔离 / UI 文案），23 项断言
- `tools/check_html_quality.py`：轻量 HTML 静态检查（alt / button type / 重复 id / 非法嵌套 /
  h1 数量 / heading 跳级 / 空 href / dialog aria / 外链 noopener / inline handler /
  title / JSON-LD / canonical 与 og:url 一致性）
- `tools/check_seo.py`：robots / sitemap / RSS 可解析性、文章页 description、测试数据泄漏
- `tools/perf_baseline.py` 与 `docs/性能基线.md`：首屏、索引加载、搜索响应、JS heap、
  构建时间的实测基线（不含人为设定的 Lighthouse 分数目标）
- `exampleSite/content-en/`：真实多语言示例内容（zh-CN 根路径 + en `/en/` 子路径，
  独立 `contentDir`，不污染单语言构建）
- `tools/bench_index.py` 路径修正（仓库根即主题根）

### 文档

- README 更正 CDN 表述：**默认配置下无外部 CDN 请求**；启用评论 / 统计后加载对应第三方资源，
  并列出 giscus / Waline / Twikoo / Disqus / busuanzi 的具体请求行为
- README 新增第三方服务说明与多语言站点说明（含"无语言切换按钮"的设计取舍）

### 门禁验证

五次故意故障注入，全部使 CI 真实变红：

| 注入 | 变红的门禁 | Run |
| --- | --- | --- |
| A 分页爬取达到安全上限 | Release full-site audit ×3 浏览器 | 37753707374 |
| B 漏掉一个分页页 `/page/3/` | Release full-site audit ×3 浏览器 | 37753707374 |
| C 评论写死 `zh-CN` | static-checks / Comments | 37753033988 |
| D 重复 id | static-checks / HTML quality | 37752376410 |
| E 内容图片缺 alt | static-checks / HTML quality | 37752376410 |

## [1.0.5] — 2026-10-08

发布门禁与测试覆盖修复：复制超时不再伪装成功、Release 全站审计覆盖 sitemap 全部页面、
lazy image 判定顺序修正、灯箱占位图改用 data URI、`verify_copy.py` 与
`check_i18n_hardcode.py` 新增、四次故意注入验证。

## [1.0.4] — 2026-10-08

CI 可靠性终验：修复测试脚本"打印 FAIL 但 exit 0"的假绿，三次故意注入证明 GitHub Actions 真实变红。

## [1.0.3] — 稳定性、工程质量与产品完善

灯箱 Focus Trap、搜索分片失败提示、自动搜索模式、多 section、i18n 三语言、图片 Pipeline、
SEO/RSS、Series / 分享 / 代码块。

## [1.0.2] — 第三方复验修复

全文搜索截断、Hugo 版本声明、JSON-LD 时区、灯箱无障碍、搜索边界、三种 baseURL、压力数据与 CI。

## [1.0.1] — 发布前全面修复

首次正式发布前的全量验收修复。

[1.0.8]: https://github.com/tanglx02/hugo-theme-nebula/compare/v1.0.7...v1.0.8
[1.0.7]: https://github.com/tanglx02/hugo-theme-nebula/compare/v1.0.6...v1.0.7
[1.0.6]: https://github.com/tanglx02/hugo-theme-nebula/compare/v1.0.5...v1.0.6
[1.0.5]: https://github.com/tanglx02/hugo-theme-nebula/compare/v1.0.4...v1.0.5
[1.0.4]: https://github.com/tanglx02/hugo-theme-nebula/compare/v1.0.3...v1.0.4
[1.0.3]: https://github.com/tanglx02/hugo-theme-nebula/compare/v1.0.2...v1.0.3
[1.0.2]: https://github.com/tanglx02/hugo-theme-nebula/compare/v1.0.1...v1.0.2
[1.0.1]: https://github.com/tanglx02/hugo-theme-nebula/releases/tag/v1.0.1
