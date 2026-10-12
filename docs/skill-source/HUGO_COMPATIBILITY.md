# HUGO_COMPATIBILITY — Hugo 版本兼容指南

> 主题声明 **`min_version = "0.128.0"`（extended）**。本文件记录各版本的真实差异、
> 主题的探测/降级策略，以及**为什么**要这样处理。证据：`theme.toml`、CI build 矩阵、
> `tools/check_search_modes.py`、`tools/check_lang_config.py`、`docs/稳定基线.md §5.10`。

---

## 1. 支持的版本矩阵

| 维度 | 覆盖 | 说明 |
| --- | --- | --- |
| CI 构建矩阵 | `0.128.0` `0.148.0` `0.162.0` `0.166.0` `0.167.0` `latest`（6） | `latest` 为运行期动态解析，**非固定版本号** |
| 本地固定矩阵 | `0.128.0` / `0.148.0` / `0.162.0` / `0.166.0` / `0.167.0`（5） | 由 `check_content_components.py`、`check_author_pages.py` 在 `HUGO_MATRIX_DIR` 下真实执行 |
| 最低版本 | `0.128.0` | `theme.toml` |

> ⚠ **口径陷阱**：CI 矩阵是 **6 条**（含动态 `latest`），本地可复现固定矩阵是 **5 个**。
> 早期文档把两者混写成「六版本构建全绿」造成数字矛盾；现统一为「五版本固定矩阵 +
> CI 另含 `latest` 动态条目」。

---

## 2. 关键能力版本门限

| 能力 | 引入版本 | 低版本行为 / 主题策略 |
| --- | --- | --- |
| **`resources.Publish`** | **0.166.0** | 搜索分片依赖它。**`auto` 在旧版本超阈值时回退单文件索引（打 WARN）**；显式 `mode="shard"` 在旧版本**明确报错**并给替代方案（不静默降级） |
| **`.Language.Locale`** | **0.158.0** | 经 `util/locale.html`：≥0.158 用 `.Locale`，旧版回退 `.LanguageCode` |
| **`reflect.IsImageResourceProcessable`** | 0.128 无 | **不用它**；改用 MediaType 白名单判断图片可处理性 |
| `[languages.*]` 顶层 `label` | 0.112 起弃用 | 改用 `params.label` |
| `[languages.*]` 顶层 `languageCode` | 0.158 起弃用 | 用根级 `locale`（零告警形态） |
| `[pagination] path` 配置 | 较新版本 | 分页 crawler **优先从构建产物反推 token**，再读配置，最后用默认 `page` |

---

## 3. 反模式：不要用 `cond` 做版本探测

Go 模板的 `cond` **会先求值两个分支**再返回。若其中一个分支访问了旧版本不存在的字段，
在旧 Hugo 上会直接报错。

```gotemplate
{{/* ❌ 错误：cond 两个分支都会求值，旧版本上 .Language.Locale 不存在 → 报错 */}}
{{ $loc := cond (ge $verMinor 158) .Language.Locale .Language.LanguageCode }}

{{/* ✅ 正确：解析 hugo.Version 的 major/minor，用 if/else 惰性分支 */}}
{{ $v := replaceRE `^v` "" hugo.Version }}
{{ $parts := split $v "." }}
{{ $minor := int (index $parts 1) }}
{{ $loc := "" }}
{{ if ge $minor 158 }}{{ $loc = .Language.Locale }}{{ else }}{{ $loc = .Language.LanguageCode }}{{ end }}
```

同类：能力探测一律**先解析版本号再用 `if`**。

---

## 4. 搜索索引与 `resources.Publish`（最典型的版本差异）

主题有三种搜索模式：`auto` / `single` / `shard`。

| 模式 | 0.166+ | 0.128–0.162 |
| --- | --- | --- |
| `auto`（默认）超 `autoThreshold` | 走**分片** | **自动回退单文件**索引 + WARN，**构建成功**，全文能力不变 |
| `auto` 未超阈值 | 单文件 | 单文件 |
| 显式 `single` | 单文件 | 单文件 |
| 显式 `shard` | 分片 | **明确报错**（提示需要 Hugo ≥ 0.166.0 并给替代方案），**不静默降级** |

真实缺陷起点：BUG-P1-002 —— 默认 `auto` 在 0.128–0.162 上因 `can't evaluate field Publish`
**整站构建失败**。修复：能力探测（`ge $verMinor 166`）。

> 边界验证方式：`check_search_modes.py` **按真实索引字节数**量出正文总字节数 `T`，
> 再用 `T-1 / T / T+1` 作阈值各构建一次，逐版本验证 below / equal / above 行为。
> 教训：**用「文章篇数」当阈值边界是不准的**，必须用真实字节数。

---

## 5. 多语言 / i18n 的兼容坑（真实 Bug）

| 版本相关坑 | 表现 | 处理 |
| --- | --- | --- |
| 语言键与 `i18n/` 文件名不匹配（BUG-R3-001） | 0.128/0.148 全站 UI 文案**空串** | 显式 `defaultContentLanguage = "zh-CN"` + `[languages.zh-CN]`；`check_features.py` 8a/8b 双层断言 |
| `[languages.*]` 顶层字段跨版本弃用（BUG-R3-002） | deprecated WARN | 零告警形态：根 `locale` + 仅 `weight`/`contentDir` + `params.label` |
| `util/locale.html` 在 0.128 产出 `zh_cn`（BUG-R3-003） | `og:locale` 非规范 | BCP47 规范化（语言小写 / 地区大写 → `zh_CN`） |
| 语言配置 `--config` 路径 | Hugo 静默忽略找不到的配置文件 → 「英文构建实际仍是中文」 | 必须把 overlay 复制到站点目录内再用相对路径引用 |

---

## 6. CJK / 特殊字符 / URL 编码

- **`urlize` 对 CJK 返回 percent-encoded**，且 `+` 会被转义；`site.GetPage "/authors/<urlize>"`
  对 CJK 返回 `NONE`。→ 作者档案页**刻意不用 `urlize` 拼路径**，改为遍历 `site.Taxonomies`
  按 `Page.Title` 大小写不敏感匹配。
- **字面 `+` 的语义边界**（BUG 相关）：Hugo 产物的 taxonomy 目录保留字面 `+`
  （如 `authors/c++-工程师/`），浏览器/服务端请求时 `+` 在路径段中**不再是空格**
  （`+`=空格仅在 query string）。因此 `html_inventory.normalize_url()` 将 `+` 列入 safe，
  避免被编码成 `%2B` 与真实 URL 不一致。
  - 但 `%2B` **已是**一种合法字面写法 → 必须保证「已编码的 `%2B` 不被二次编码、也不被解码」，
    且「`c++/` 与 `c%2B%2B/` 不被折叠」。
- **BOM front matter、非 ASCII slug、单 emoji、单 CJK** 都必须能构建（`gen_testdata.py` 固化）。

---

## 7. 资源管线 / 图片

- `render-image` 钩子用 **MediaType 白名单**判可处理性（不用 0.128 不存在的 `reflect.IsImageResourceProcessable`）。
- 未装 `Pillow` 时 `gen_testdata.py` 会跳过 `zz-images-bundle` → 图片处理分支**永不构建到**
  → 0.128 上的图片管线不兼容会长期潜伏。CI 的 build job 因此**必须装 Pillow**，
  并断言产物含 `srcset=`。

---

## 8. `latest` 与后续版本

- `latest` 由 `peaceiris/actions-hugo` 运行期解析，**无法给出具体版本号/日志**，不得当作
  「已验证某个具体版本」。
- 另有 `.github/workflows/compat-latest.yml`（每周 + 手动）在 `ubuntu-latest` 上做**非门禁**的
  前向兼容探测。
- **runner 有意固定 `ubuntu-24.04`**：GitHub 已宣布 `ubuntu-latest` 将迁移到 26.04，
  长期基线不应随平台迁移悄悄改变（由 `check_workflow_policy.py` 断言固定）。

---

## 9. 给其它 Hugo 主题的可移植建议

1. 在 `theme.toml` 声明**经真实构建验证过**的 `min_version`，不要凭猜。
2. **凡依赖某个版本的 API，都要在低版本上给明确行为**（回退 + WARN，或明确报错），
   **绝不静默降级**。
3. **版本探测用 `if/else`，不用 `cond`**（惰性求值差异）。
4. **API 能力探测优先于版本号比较**（若 API 自身可探测），但注意 `cond` 陷阱。
5. 把「版本 × 功能」的行为固化成**逐版本门禁**，而不是文档承诺。
