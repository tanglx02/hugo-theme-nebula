# Changelog

本文件记录 Nebula 主题的版本变更。格式参考 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，
版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

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

[1.0.7]: https://github.com/tanglx02/hugo-theme-nebula/compare/v1.0.6...v1.0.7
[1.0.6]: https://github.com/tanglx02/hugo-theme-nebula/compare/v1.0.5...v1.0.6
[1.0.5]: https://github.com/tanglx02/hugo-theme-nebula/compare/v1.0.4...v1.0.5
[1.0.4]: https://github.com/tanglx02/hugo-theme-nebula/compare/v1.0.3...v1.0.4
[1.0.3]: https://github.com/tanglx02/hugo-theme-nebula/compare/v1.0.2...v1.0.3
[1.0.2]: https://github.com/tanglx02/hugo-theme-nebula/compare/v1.0.1...v1.0.2
[1.0.1]: https://github.com/tanglx02/hugo-theme-nebula/releases/tag/v1.0.1
