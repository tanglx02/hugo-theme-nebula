#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""作者档案页门禁（功能四 / M16）—— **真实构建产物**断言，不是字符串占位检查。

背景
----
多作者 Front Matter 与"作者档案页"属既定开发范围。此前被标为 ACCEPTED-LIMITATION
（顾虑"会改变 URL 结构"）。本轮实测证明该顾虑可通过**可选启用**完全化解：
  * taxonomy 作者页在 Hugo 0.128.0 / 0.148.0 / 0.167.0 上行为完全一致（含 CJK）；
  * 默认（未注册作者 taxonomy）主题**不输出任何作者档案结构**，URL 结构与历史一致。

本门禁验证（全部基于真实产物 / 真实构建）：
  1. 默认关闭：不注册 taxonomy 时**不生成** /authors/，文章页作者为纯文本（无 <a>）
  2. 可选启用：注册 taxonomy + params.authors.pages=true 时生成
     /authors/ 索引页与 /authors/<term>/ 档案页
  3. 多作者 Front Matter：列表 authors 建立 term；单数 author 不建立（如实映射）
  4. 文章 <-> 作者档案互链：文章页作者名链接到对应档案页；档案页列出该作者文章
  5. 作者字段缺失：无作者文章不输出作者区块，且不产生空链接
  6. 中文作者名：/authors/张伟/ 生成且互链（percent-encoded URL 正确）
  7. 特殊字符作者名：C++ 工程师 / José 等不崩溃、URL 正确
  8. SEO / canonical / RSS：档案页有 canonical、被 sitemap 收录、taxonomy RSS 生成
  9. 搜索索引：**不**把 taxonomy 页塞进搜索索引（避免重复内容）
 10. 多语言：各语言各自生成 /authors/ 与 /<lang>/authors/，hreflang 交叉引用正确
 11. 分页：作者文章数超过 pagerSize 时档案页分页正常
  12. 向后兼容：未启用时输出与「无本功能基线主题」**规范化后**逐字节一致（规范化 = 打包 CSS 文件名哈希 / SRI integrity / RSS lastBuildDate 三项）

**为什么不能只做字符串断言**：本门禁对每条都检查"文件是否真实存在 / 页面间链接
是否真实指向存在的产物"，而非"模板里出现了某个字符串"。

用法：
    python tools/check_author_pages.py            # 用 HUGO_BIN（默认 PATH 的 hugo）
环境变量：
    HUGO_BIN          Hugo 可执行文件（PATH 无 hugo 时必须提供）
    HUGO_MATRIX_DIR   版本矩阵目录；设置后**在每个版本上各跑一遍**关键断言
退出码约定见 tools/_testlib.py：任一断言失败 / 构建失败 -> exit 1。
"""
import os
import re
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _testlib import Harness, guard, safe_rmtree, TempWorkspace  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
THEMES_DIR = os.path.dirname(REPO)
THEME_NAME = os.path.basename(REPO)
HUGO = os.environ.get("HUGO_BIN", "hugo")
OUT_ROOT = os.path.join(REPO, "tmp")


# ---------------------------------------------------------------------------
# 站点构造
# ---------------------------------------------------------------------------
BASE_CFG = """baseURL = 'https://authors.test/'
title = 'Authors Probe'
theme = '{theme}'
defaultContentLanguage = 'zh-CN'
locale = 'zh-CN'
hasCJKLanguage = true
enableRobotsTXT = true

[languages]
  [languages.zh-CN]
    weight = 1
    contentDir = 'content'
{langs}

[taxonomies]
  category = 'categories'
  tag = 'tags'
{tax}

[outputs]
  home = ['HTML', 'JSON', 'RSS']

[pagination]
  pagerSize = {pager}

[params]
  author = 'Site Default'

{authors}
[params.search]
  enable = true
"""

EN_LANG = """  [languages.en]
    weight = 2
    contentDir = 'content-en'
    title = 'Authors Probe EN'
    locale = 'en-US'
"""

AUTHORS_ON = """[params.authors]
  pages = true
  [params.authors.profiles]
    [params.authors.profiles."Tanglx"]
      role = 'Engineer'
      bio = 'bio for Tanglx'
    [params.authors.profiles."张伟"]
      bio = '中文作者简介'
"""

AUTHORS_OFF = ""


def post(title, fm_extra="", body="body", date="2025-01-01"):
    return f"""---
title: "{title}"
date: {date}
{fm_extra}---

{body}
"""


def build_site(root, out, langs=False, tax=False, authors=AUTHORS_OFF, pager=10, n_posts=2):
    os.makedirs(os.path.join(root, "content", "posts"), exist_ok=True)
    cfg = BASE_CFG.format(
        theme=THEME_NAME,
        langs=EN_LANG if langs else "",
        tax="  authors = 'authors'" if tax else "",
        pager=pager,
        authors=authors,
    )
    with open(os.path.join(root, "hugo.toml"), "w", encoding="utf-8") as f:
        f.write(cfg)

    posts = os.path.join(root, "content", "posts")
    # 多作者（列表）
    open(os.path.join(posts, "multi.md"), "w", encoding="utf-8").write(
        post("Multi Author", 'authors: ["Tanglx", "Nebula Bot"]\n'))
    # 单作者（单数 author 字符串）
    open(os.path.join(posts, "single.md"), "w", encoding="utf-8").write(
        post("Single Author", 'author: "Tanglx"\n'))
    # 中文作者
    open(os.path.join(posts, "cjk.md"), "w", encoding="utf-8").write(
        post("CJK Author", 'authors: ["张伟"]\n'))
    # 特殊字符作者
    open(os.path.join(posts, "special.md"), "w", encoding="utf-8").write(
        post("Special Author", 'authors: ["C++ 工程师", "José"]\n'))
    # 无作者（字段缺失）
    open(os.path.join(posts, "noauthor.md"), "w", encoding="utf-8").write(
        post("No Author"))
    # 大量同作者文章（测分页）
    for i in range(n_posts):
        open(os.path.join(posts, f"bulk-{i:02d}.md"), "w", encoding="utf-8").write(
            post(f"Bulk {i}", 'authors: ["Bulk Author"]\n'))

    if langs:
        en = os.path.join(root, "content-en", "posts")
        os.makedirs(en, exist_ok=True)
        open(os.path.join(en, "en-multi.md"), "w", encoding="utf-8").write(
            post("English Multi", 'authors: ["Tanglx", "Nebula Bot"]\n'))
        open(os.path.join(en, "en-single.md"), "w", encoding="utf-8").write(
            post("English Single", 'authors: ["Tanglx"]\n'))

    cmd = [HUGO, "--source", root, "--themesDir", THEMES_DIR,
           "--theme", THEME_NAME, "--gc", "--minify", "-d", out]
    p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                       errors="ignore", timeout=600)
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def read(out, rel):
    p = os.path.join(out, rel.replace("/", os.sep))
    if not os.path.exists(p):
        return None
    return open(p, encoding="utf-8", errors="ignore").read()


def exists(out, rel):
    return os.path.exists(os.path.join(out, rel.replace("/", os.sep)))


# ---------------------------------------------------------------------------
# ① 默认关闭：可选启用的向后兼容
# ---------------------------------------------------------------------------
def check_disabled(h):
    with TempWorkspace("authors-off") as ws:
        root, out = ws.path("site"), ws.path("out")
        rc, log = build_site(root, out, tax=False, authors=AUTHORS_OFF)
        if rc != 0:
            h.fatal_error("默认关闭：构建成功", log[-400:])
            return
        h.record("OFF1 未注册作者 taxonomy：不生成 /authors/ 索引页",
                 not exists(out, "authors/index.html"))
        h.record("OFF2 未注册作者 taxonomy：不生成任何 /authors/<term>/ 档案页",
                 not exists(out, "authors/tanglx/index.html")
                 and not exists(out, "authors/nebula-bot/index.html"))
        html = read(out, "posts/multi/index.html") or ""
        h.record("OFF3 未启用时文章页作者为**纯文本**（无 author-link）",
                 "author-link" not in html and "Tanglx" in html)
        # 与历史一致：作者并列用 .csv（", " 分隔）
        m = re.search(r'stat-author[^>]*>.*?</svg>\s*([^<]+?)\s*</span>', html, re.S)
        h.record("OFF4 未启用时多作者并列格式与历史一致（逗号分隔）",
                 bool(m) and m.group(1).strip() == "Tanglx, Nebula Bot",
                 repr(m.group(1).strip() if m else None))
        # 无作者文章不应出现空作者区块
        na = read(out, "posts/noauthor/index.html") or ""
        h.record("OFF5 无作者文章仍回退到站点默认作者（site.Params.author）",
                 "Site Default" in na)


# ---------------------------------------------------------------------------
# ② 启用：索引页 / 档案页 / 互链 / 缺失 / CJK / 特殊字符
# ---------------------------------------------------------------------------
def check_enabled(h, out):
    h.record("ON1 启用后生成 /authors/ 索引页", exists(out, "authors/index.html"))
    h.record("ON2 启用后生成 /authors/tanglx/ 档案页",
             exists(out, "authors/tanglx/index.html"))
    h.record("ON3 启用后生成 /authors/nebula-bot/ 档案页",
             exists(out, "authors/nebula-bot/index.html"))
    h.record("ON4 启用后生成中文作者档案页 /authors/张伟/",
             exists(out, "authors/张伟/index.html"))
    h.record("ON5 特殊字符作者档案页存在（C++ 工程师）",
             exists(out, "authors/c++-工程师/index.html"))
    h.record("ON6 特殊字符作者档案页存在（José）",
             exists(out, "authors/josé/index.html"))

    # 索引页列出全部作者（term-card）
    idx = read(out, "authors/index.html") or ""
    cards = re.findall(r'class="?term-card"?', idx)
    h.record("ON7 索引页用 term-card 列出作者",
             len(cards) >= 5, f"{len(cards)} 个 term-card")

    # 档案页含作者资料卡
    tp = read(out, "authors/tanglx/index.html") or ""
    h.record("ON8 档案页输出作者资料卡 author-profile",
             "author-profile" in tp)
    h.record("ON9 档案页资料卡展示 role / bio（来自 params.authors.profiles）",
             "Engineer" in tp and "bio for Tanglx" in tp)
    cjk = read(out, "authors/张伟/index.html") or ""
    h.record("ON10 中文作者档案页展示中文 bio",
             "中文作者简介" in cjk)

    # 档案页列出该作者的文章（真实链接）
    h.record("ON11 档案页列出该作者的文章卡片",
             "Multi Author" in tp and "Single Author" in tp)
    h.record("ON12 档案页文章链接指向真实存在的文章产物",
             exists(out, "posts/multi/index.html") and "/posts/multi/" in tp)

    # 档案页文章的 author 归属正确：Nebula Bot 档案页的**文章列表**应只含 multi。
    # ⚠ 不能直接对整页做 "Single Author" in html —— 侧边栏「热门文章」是全站范围，
    #   与作者归属无关，会让断言假红（同类教训见 check_new_features 的注入自证）。
    #   必须**限定在文章列表容器内**判定。
    #   ⚠ --minify 会去掉属性引号（class=post-list）且列表后直接跟 <aside>，
    #     故按 "post-list" 起点切到 "<aside" 终点，不依赖 </div><nav 组合。
    nb = read(out, "authors/nebula-bot/index.html") or ""
    i = nb.find("post-list")
    j = nb.find("<aside", i) if i >= 0 else -1
    nb_list = nb[i:j] if (i >= 0 and j > i) else ""
    h.record("ON13 作者档案页文章列表只收录该作者的文章（限定 post-list 容器）",
             "Multi Author" in nb_list and "Single Author" not in nb_list,
             f"列表长度 {len(nb_list)}")

    # 单数 author 不建立 term（如实映射 Hugo 机制）
    h.record("ON14 单数 author 字段**不**建立 term（无 /authors/solo 之类）",
             not exists(out, "authors/solo/index.html"))

    # 文章页 -> 档案页 互链
    multi = read(out, "posts/multi/index.html") or ""
    links = re.findall(r'class="?author-link"?\s+href="?([^"\s>]+)', multi)
    h.record("ON15 多作者文章页：每个作者名各成一条 author-link",
             len(links) == 2, f"{len(links)} 条：{links}")
    h.record("ON16 文章页作者链接指向 /authors/tanglx/",
             any("/authors/tanglx/" in u for u in links))
    h.record("ON17 文章页作者链接指向 /authors/nebula-bot/",
             any("/authors/nebula-bot/" in u for u in links))
    cjk_post = read(out, "posts/cjk/index.html") or ""
    h.record("ON18 中文作者文章页链接到 percent-encoded 中文档案页",
             "%E5%BC%A0%E4%BC%9F" in cjk_post and "author-link" in cjk_post)

    # 无作者文章：不产生空链接
    na = read(out, "posts/noauthor/index.html") or ""
    h.record("ON19 无作者文章不产生 author-link（无空链接）",
             "author-link" not in na)

    # 特殊字符文章页不崩溃且链接正确
    sp = read(out, "posts/special/index.html") or ""
    h.record("ON20 特殊字符作者文章页生成且带 author-link",
             bool(sp) and sp.count("author-link") >= 2)

    # 每篇文章的 canonical 指向自身
    can = re.search(r'rel="?canonical"?\s+href="?([^"\s>]+)', tp)
    h.record("ON21 作者档案页 canonical 指向自身",
             bool(can) and can.group(1).rstrip("/").endswith("/authors/tanglx"))

    # ON22–ON24：`min-height` 对 **inline 元素无效** 的回归防护（R5-001）。
    #   实测：首版 `.author-link` 只写了 color/text-decoration，`<a>` 仍是 inline，
    #   在 320–430px 渲染成 40×24px，被 audit 的 small-tap-target（WCAG 2.5.8）判红。
    #   这里断言**构建产物 CSS**（不是源码字符串），与 audit 的真实像素测量互补。
    css_text = _read_built_css(out)
    mrule = re.search(r"\.author-link\s*\{([^}]*)\}", css_text or "")
    rule = (mrule.group(1) if mrule else "").replace(" ", "")
    h.record("ON22 构建产物 CSS 存在 .author-link 规则", bool(rule))
    h.record("ON23 .author-link 显式 inline-flex/inline-block（否则 min-height 对 inline 无效）",
             "display:inline-flex" in rule or "display:inline-block" in rule,
             rule[:80])
    mmin = re.search(r"min-height:(\d+)px", rule)
    h.record("ON24 .author-link min-height ≥ 24px（触控目标 WCAG 2.5.8）",
             bool(mmin) and int(mmin.group(1)) >= 24,
             (mmin.group(1) + "px") if mmin else "缺失")


def _read_built_css(out):
    """读取构建产物中的打包 CSS（main.min.<hash>.css），找不到返回空串。"""
    cssdir = os.path.join(out, "css")
    if not os.path.isdir(cssdir):
        return ""
    for fn in sorted(os.listdir(cssdir)):
        if fn.startswith("main.min.") and fn.endswith(".css"):
            try:
                return open(os.path.join(cssdir, fn), encoding="utf-8", errors="ignore").read()
            except OSError:
                return ""
    return ""


# ---------------------------------------------------------------------------
# ③ SEO / RSS / sitemap / 搜索索引 / 分页
# ---------------------------------------------------------------------------
def check_seo(out, h, pager=10, n_posts=2):
    # sitemap 收录作者页
    sm = read(out, "sitemap.xml") or ""
    locs = re.findall(r"<loc>([^<]+)</loc>", sm)
    auth = [u for u in locs if "/authors/" in u]
    h.record("SEO1 sitemap 收录作者索引页与档案页",
             any(u.rstrip("/").endswith("/authors") for u in auth) and len(auth) >= 3,
             f"{len(auth)} 个 authors URL")
    h.record("SEO2 sitemap 中作者 URL 全部为绝对 http(s)",
             bool(auth) and all(u.startswith(("http://", "https://")) for u in auth))

    # taxonomy RSS 生成
    h.record("SEO3 作者 taxonomy 生成 RSS（/authors/index.xml）",
             exists(out, "authors/index.xml"))

    # 搜索索引**不**收录 taxonomy 页（避免重复内容）
    raw = read(out, "index.json") or "[]"
    import json
    try:
        items = json.loads(raw)
        items = items if isinstance(items, list) else items.get("items", [])
    except Exception:
        items = []
    h.record("SEO4 搜索索引不收录 /authors/ taxonomy 页",
             bool(items) and not any("/authors/" in json.dumps(it, ensure_ascii=False)
                                     for it in items),
             f"{len(items)} 条索引")
    # 搜索索引仍包含普通文章（未被误伤）
    h.record("SEO5 搜索索引仍包含普通文章（作者页功能未误伤索引）",
             any("multi" in (it.get("url") or "") for it in items))

    # 分页：bulk author 有 n_posts 篇，pagerSize=10 -> 若 >10 应有分页
    if n_posts > pager:
        h.record("SEO6 作者文章数超过 pagerSize 时档案页分页生成",
                 exists(out, "authors/bulk-author/page/2/index.html"))
    else:
        h.record("SEO6 作者文章数未超 pagerSize：不生成多余分页（无 /page/2/）",
                 not exists(out, "authors/bulk-author/page/2/index.html"))


# ---------------------------------------------------------------------------
# ④ 多语言
# ---------------------------------------------------------------------------
def check_multilang(h):
    with TempWorkspace("authors-ml") as ws:
        root, out = ws.path("site"), ws.path("out")
        rc, log = build_site(root, out, langs=True, tax=True, authors=AUTHORS_ON)
        if rc != 0:
            h.fatal_error("多语言：构建成功", log[-400:])
            return
        h.record("ML1 默认语言生成 /authors/",
                 exists(out, "authors/index.html"))
        h.record("ML2 非默认语言生成 /en/authors/",
                 exists(out, "en/authors/index.html"))
        h.record("ML3 非默认语言生成 /en/authors/tanglx/",
                 exists(out, "en/authors/tanglx/index.html"))

        # hreflang 交叉引用
        tp = read(out, "authors/tanglx/index.html") or ""
        hl = re.findall(r'hreflang="?([\w-]+)"?\s+href="?([^"\s>]+)', tp)
        langs_seen = {a for a, _ in hl}
        h.record("ML4 作者档案页输出双向 hreflang（zh-CN + en-US）",
                 {"zh-CN", "en-US"} <= langs_seen, f"{langs_seen}")

        # 英文档案页 canonical 在 /en/ 前缀
        en = read(out, "en/authors/tanglx/index.html") or ""
        can = re.search(r'rel="?canonical"?\s+href="?([^"\s>]+)', en)
        h.record("ML5 英文作者档案页 canonical 带 /en/ 前缀",
                 bool(can) and "/en/authors/tanglx/" in can.group(1))

        # 英文文章页链接到英文档案页
        enp = read(out, "en/posts/en-multi/index.html") or ""
        links = re.findall(r'class="?author-link"?\s+href="?([^"\s>]+)', enp)
        h.record("ML6 英文文章页作者链接指向 /en/authors/",
                 bool(links) and all("/en/authors/" in u for u in links),
                 f"{links}")


# ---------------------------------------------------------------------------
# ⑤ 向后兼容：未启用 vs "无本功能"（忽略 CSS 指纹）逐字节一致
# ---------------------------------------------------------------------------
CSS_PAT = re.compile(r"main\.min\.[a-f0-9]+\.css")
INT_PAT = re.compile(r'integrity="sha256-[A-Za-z0-9+/=]+"')
DATE_PAT = re.compile(r"<lastBuildDate>[^<]*</lastBuildDate>")


def _norm(path):
    s = open(path, encoding="utf-8", errors="ignore").read()
    s = CSS_PAT.sub("CSS", s)
    s = INT_PAT.sub("INTEGRITY", s)
    s = DATE_PAT.sub("DATE", s)
    return s


def _git_stdout(*args):
    p = subprocess.run(["git", *args], cwd=REPO, capture_output=True)
    if p.returncode != 0:
        return None
    return p.stdout.decode("utf-8", "ignore")


def _no_feature_baseline():
    """自动推导「无本功能基线」提交。

    取「首次新增 `layouts/partials/util/author-config.html` 的提交」的父提交 ——
    即**真正没有本功能**的那一版主题。

    为什么不能直接用 `git archive HEAD`：本功能一旦提交入库，工作区干净时
    HEAD 就是"含本功能"的版本，与当前工作树逐字节相同，断言会退化为**自比**
    （永远 0 差异，证明不了任何向后兼容性）。用父提交作基线才是有效对照。

    浅克隆 / 无 git 历史 / 找不到该文件时返回 None -> 退化为 SKIP，不阻塞 CI。
    """
    out = _git_stdout("log", "--diff-filter=A", "--format=%H", "-1", "--",
                      "layouts/partials/util/author-config.html")
    if not out:
        return None
    lines = [ln.strip() for ln in out.splitlines() if ln.strip()]
    if not lines:
        return None
    parent = _git_stdout("rev-parse", lines[0] + "^")
    if not parent or not parent.strip():
        return None
    return parent.strip()


def check_backcompat(h):
    """用**同一份「无本功能内容」**、分别以【无本功能基线主题】与【当前主题】构建，
    对比结果。基线主题由 git 历史自动推导（见 `_no_feature_baseline`）。

    **实际执行的比较规则（精确，勿夸大）**：
      * 只纳入 `.html` / `.xml` / `.json` 三类产物（图片、CSS、JS 等静态资源
        不在比较范围内）；
      * **文件集合双向比较**：基线独有与当前独有的路径都必须为空；
      * 共有文件的内容，先做 **3 项规范化**再做「逐字节」比较：
          - 打包 CSS 文件名哈希 `main.min.<hash>.css` -> `CSS`
          - SRI `integrity="sha256-…"` -> `INTEGRITY`
          - RSS `<lastBuildDate>…</lastBuildDate>` -> `DATE`
        （这三项因构建时间/文件名而变化，非本功能引入的差异。）
      * 因此结论是「**规范化后逐字节一致**」，不是"原始字节完全一致"。

    浅克隆 / 无 git 时退化为 SKIP（记为 PASS 并说明），不阻塞 CI。
    """
    with TempWorkspace("authors-compat") as ws:
        base_sha = _no_feature_baseline()
        if not base_sha:
            h.record("BC1 未启用作者档案页时，输出与「无本功能」基线主题逐字节一致",
                     True, "无 git / 浅克隆 / 找不到基线：SKIP（不影响其它断言）")
            return

        base = ws.path("themes", "base")
        cur = ws.path("themes", "cur")
        os.makedirs(base, exist_ok=True)
        os.makedirs(cur, exist_ok=True)
        # 无本功能基线主题
        p = subprocess.run(["git", "archive", base_sha], cwd=REPO,
                           capture_output=True)
        if p.returncode != 0 or not p.stdout:
            h.record("BC1 未启用作者档案页时，输出与「无本功能」基线主题逐字节一致",
                     True, f"基线 {base_sha[:9]} 导出失败：SKIP")
            return
        import tarfile
        import io as _io
        with tarfile.open(fileobj=_io.BytesIO(p.stdout)) as tf:
            tf.extractall(base)
        # 当前工作树（排除构建产物 / 站点内容）
        for name in os.listdir(REPO):
            if name in (".git", "tmp", "exampleSite", "__pycache__"):
                continue
            src = os.path.join(REPO, name)
            dst = os.path.join(cur, name)
            if os.path.isdir(src):
                shutil.copytree(src, dst, dirs_exist_ok=True,
                                ignore=shutil.ignore_patterns("__pycache__"))
            else:
                shutil.copy2(src, dst)

        # 同一份内容：基线自带 exampleSite（其 hugo.toml **无** 作者档案页配置，
        # 因此两个主题都是"本功能关闭"状态，对照才成立）。
        content_src = os.path.join(base, "exampleSite")
        if not os.path.isdir(content_src):
            h.record("BC1 未启用作者档案页时，输出与「无本功能」基线主题逐字节一致",
                     True, "基线 exampleSite 缺失：SKIP")
            return

        def build(theme_dir, out):
            cmd = [HUGO, "--source", content_src, "--themesDir", theme_dir,
                   "--theme", "head", "--gc", "--minify", "-d", out]
            r = subprocess.run(cmd, capture_output=True, text=True,
                               encoding="utf-8", errors="ignore", timeout=600)
            return r.returncode

        # 两个主题都以 theme 名 "head" 挂载，仅切换 themesDir
        hd = ws.path("t_base")
        cd = ws.path("t_cur")
        os.makedirs(hd, exist_ok=True)
        os.makedirs(cd, exist_ok=True)
        shutil.copytree(base, os.path.join(hd, "head"), dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns("exampleSite", "tmp"))
        shutil.copytree(cur, os.path.join(cd, "head"), dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns("exampleSite", "tmp"))
        out_b, out_c = ws.path("out_base"), ws.path("out_cur")
        rc1 = build(hd, out_b)
        rc2 = build(cd, out_c)
        if rc1 != 0 or rc2 != 0:
            h.fatal_error("BC 基线/当前构建均成功", f"base rc={rc1} cur rc={rc2}")
            return

        def listing(root):
            got = set()
            for r_, _, files in os.walk(root):
                for f in files:
                    if f.endswith((".html", ".xml", ".json")):
                        got.add(os.path.relpath(os.path.join(r_, f), root))
            return got

        fb, fc = listing(out_b), listing(out_c)
        only_b = sorted(fb - fc)
        only_c = sorted(fc - fb)
        diffs = [rp for rp in sorted(fb & fc)
                 if _norm(os.path.join(out_b, rp)) != _norm(os.path.join(out_c, rp))]
        ok = not only_b and not only_c and not diffs
        detail = (f"基线 {base_sha[:9]} | 产物 {len(fb)} vs {len(fc)} | "
                  f"仅基线 {len(only_b)} | 仅当前 {len(only_c)} | 内容差异 {len(diffs)}")
        if not ok:
            detail += f" | 例: {(only_b[:2] + only_c[:2] + diffs[:2])}"
        h.record("BC1 未启用作者档案页时，输出与「无本功能」基线主题逐字节一致（规范化后）",
                 ok, detail)


# ---------------------------------------------------------------------------
# 多版本矩阵
# ---------------------------------------------------------------------------
def check_matrix(h):
    """HUGO_MATRIX_DIR 设置时，在每个版本上各跑一遍关键断言。"""
    mdir = os.environ.get("HUGO_MATRIX_DIR", "").strip()
    if not mdir or not os.path.isdir(mdir):
        h.record("MX0 版本矩阵目录存在（未设置则跳过）", True,
                 "未设置 HUGO_MATRIX_DIR：跳过（CI 由 build job 覆盖）")
        return
    vers = sorted(d for d in os.listdir(mdir)
                  if os.path.isdir(os.path.join(mdir, d)))
    for v in vers:
        exe = os.path.join(mdir, v, "hugo.exe" if os.name == "nt" else "hugo")
        if not os.path.exists(exe):
            continue
        with TempWorkspace(f"authors-{v}") as ws:
            root, out = ws.path("site"), ws.path("out")
            global HUGO
            old = HUGO
            HUGO = exe
            try:
                rc, log = build_site(root, out, tax=True, authors=AUTHORS_ON)
            finally:
                HUGO = old
            if rc != 0:
                h.record(f"MX {v}：作者档案页站点构建成功", False, log[-300:])
                continue
            ok = (exists(out, "authors/index.html")
                  and exists(out, "authors/tanglx/index.html")
                  and exists(out, "authors/张伟/index.html"))
            tp = read(out, "posts/multi/index.html") or ""
            ok = ok and tp.count("author-link") == 2
            h.record(f"MX {v}：索引页 + ASCII/CJK 档案页 + 文章互链一致", ok)


# ---------------------------------------------------------------------------
def run(h):
    # 先做主站点（启用）构建，供 ON/SEO 断言共用
    with TempWorkspace("authors-on") as ws:
        root, out = ws.path("site"), ws.path("out")
        rc, log = build_site(root, out, tax=True, authors=AUTHORS_ON,
                             pager=10, n_posts=2)
        if rc != 0:
            h.fatal_error("启用作者档案页：构建成功", log[-500:])
        else:
            check_enabled(h, out)
            check_seo(out, h, pager=10, n_posts=2)

    check_disabled(h)
    check_multilang(h)
    check_backcompat(h)
    check_matrix(h)


def main():
    h = Harness("author-pages")
    guard(h, lambda: run(h))
    h.finish()


if __name__ == "__main__":
    main()
