#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""功能断言（CI 用）：图片 Pipeline / Series / RSS / SEO / 分享 / 代码块 / i18n。

用法：python tools/check_features.py [public 目录]
"""
import json
import os
import re
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PUBLIC = sys.argv[1] if len(sys.argv) > 1 else os.path.join(REPO, "public")
PUBLIC = os.path.normpath(PUBLIC)

errors = []
checks = []


def ok(name, detail=""):
    checks.append((name, True, detail))
    print(f"PASS  {name}" + (f" :: {detail}" if detail else ""))


def bad(name, detail=""):
    errors.append(name)
    checks.append((name, False, detail))
    print(f"FAIL  {name}" + (f" :: {detail}" if detail else ""))


def read(path):
    p = os.path.join(PUBLIC, path)
    if not os.path.exists(p):
        return None
    return open(p, encoding="utf-8", errors="ignore").read()


def _read_switchers():
    """把 tools/lang-*.toml（语言切换配置）拼成一个字符串，供语言键一致性检查引用。"""
    out = []
    tdir = os.path.dirname(os.path.abspath(__file__))
    for n in sorted(os.listdir(tdir)):
        if n.startswith("lang-") and n.endswith(".toml"):
            try:
                out.append(open(os.path.join(tdir, n), encoding="utf-8",
                                errors="ignore").read())
            except OSError:
                pass
    return "\n".join(out)


# ---------- 1. 图片 Pipeline ----------
html = read("posts/zz-images-bundle/index.html")
if html is None:
    bad("图片 bundle 页面存在", "未找到 posts/zz-images-bundle/index.html")
else:
    imgs = re.findall(r"<img[^>]*>", html)
    srcset_imgs = [i for i in imgs if "srcset" in i]
    wh_imgs = [i for i in imgs if "width" in i and "height" in i]
    svg_imgs = [i for i in imgs if re.search(r"src=[\"']?[^ \"'>]*\.svg", i)]
    ok("图片 bundle 渲染", f"{len(imgs)} 张图")
    ok("可处理图片有 srcset", f"{len(srcset_imgs)} 张") if srcset_imgs else bad("可处理图片有 srcset")
    ok("可处理图片有 width/height（防 CLS）", f"{len(wh_imgs)} 张") if wh_imgs else bad("图片 width/height")
    ok("SVG 未被错误处理", f"{len(svg_imgs)} 张（无 srcset）") if all("srcset" not in i for i in svg_imgs) else bad("SVG 不应有 srcset")
    ok("灯箱原图属性 data-zoom-src", "存在") if "data-zoom-src" in html else bad("data-zoom-src")
    webp = [f for f in os.listdir(os.path.join(PUBLIC, "posts", "zz-images-bundle"))
            if f.endswith(".webp")] if os.path.isdir(os.path.join(PUBLIC, "posts", "zz-images-bundle")) else []
    ok("生成了 WebP 变体", f"{len(webp)} 个") if len(webp) > 1 else bad("WebP 变体", str(webp))
    ok("缺失图片优雅降级", "not-exist.png 未崩溃") if "not-exist.png" in html else bad("缺失图片降级")

# ---------- 2. Series ----------
html = read("posts/zz-series-2/index.html")
if html is None:
    bad("Series 页面存在")
else:
    ok("Series 卡片渲染") if "series-card" in html else bad("Series 卡片")
    ok("Series 进度（第 N 篇 / 共 M 篇）") if re.search(r"第\s*2\s*篇", html) and "共" in html else bad("Series 进度")
    ok("Series 上一篇/下一篇") if "series-prev" in html and "series-next" in html else bad("Series 导航")
no_series = read("posts/zz-01-short/index.html")
if no_series is not None:
    ok("无 series 配置时不输出") if "series-card" not in no_series else bad("无 series 的文章不应显示系列卡片")

# ---------- 3. RSS ----------
rss = read("index.xml")
if rss is None:
    bad("RSS 存在")
else:
    items = rss.count("<item>")
    ok("RSS 条目数合理", f"{items} 条") if items > 5 else bad("RSS 条目数", str(items))
    ok("RSS 含 category") if "<category>" in rss else bad("RSS category")
    ok("RSS 含 author/creator") if ("<author>" in rss or "dc:creator" in rss) else bad("RSS author")
    ok("RSS 含 pubDate") if "<pubDate>" in rss else bad("RSS pubDate")

# ---------- 4. SEO ----------
home = read("index.html")
if home is None:
    bad("首页存在")
else:
    ok("首页含 WebSite JSON-LD") if '"@type": "WebSite"' in home or '"@type":"WebSite"' in home else bad("WebSite JSON-LD")
    ok("首页含 SearchAction") if "SearchAction" in home else bad("SearchAction")
post = read("posts/01-home-lab-proxmox/index.html")
if post is not None:
    ok("文章含 BlogPosting JSON-LD") if "BlogPosting" in post else bad("BlogPosting JSON-LD")
    ok("og:image:alt") if "og:image:alt" in post else bad("og:image:alt")
    ok("canonical 存在") if 'rel=canonical' in post or 'rel="canonical"' in post else bad("canonical")
    # JSON-LD 合法性
    ld_ok = True
    for m in re.finditer(r'application/ld\+json"?>(.*?)</script>', post, re.S):
        try:
            json.loads(m.group(1))
        except Exception as e:
            ld_ok = False
            bad("JSON-LD 合法", str(e)[:60])
    if ld_ok:
        ok("JSON-LD 合法")

# ---------- 5. 代码块（filename / 行号） ----------
code = read("posts/zz-10-codeblocks/index.html")
if code is not None:
    ok("代码块携带 filename") if "app.js" in code or "utils.py" in code else bad("代码块 filename")
    ok("未知语言不崩溃") if "unknownlang123" in code else bad("未知语言")

# ---------- 6. i18n 注入 ----------
if home is not None:
    ok("i18n 文案注入 JS") if "NEBULA_I18N" in home else bad("NEBULA_I18N 注入")

# ---------- 7. 草稿/未来排除 ----------
for slug, label in (("zz-14-draft", "草稿"), ("zz-15-future", "未来文章")):
    ok(f"{label}未出现在产物中") if not os.path.isdir(os.path.join(PUBLIC, "posts", slug)) else bad(f"{label}泄漏")


# ---------- 8. i18n 语言键 ↔ 文件名一致性（回归：BUG-R3-001） ----------
# 背景：exampleSite 曾把 defaultContentLanguage 写成 'zh'，而主题只提供
# i18n/zh-CN.yaml。实测（Hugo 0.128.0 / 0.148.0，见 tmp 探针记录）：
#   * i18n 语言的**大小写不敏感精确匹配**发生在「语言键 vs 文件名去扩展名」之间，
#     且**不做别名扩展**（zh → zh-CN / zh-Hans 都不会命中）；
#   * `locale` 在 0.162+ 会作为 i18n 语言覆盖语言键，于是 `zh` 也能"碰巧"命中
#     `zh-CN.yaml` —— 但在 0.128.0 / 0.148.0 上不生效；
#   * 结果是全部 UI 文案变成**空字符串**，而构建**成功且不报错**，静默退化。
# CI 的 build 矩阵虽然覆盖 0.128.0，但此前 static-checks 只在 0.167.0 上跑
# verify_i18n，所以这个缺陷长期没被发现。本小节把它钉死在**静态 + 行为**两层：
#   8a 静态：exampleSite 的语言键必须与 i18n/*.yaml 文件名（不分大小写）一致；
#   8b 行为：真实构建产物里 NEBULA_I18N 的每个值都必须非空。
cfg_path = os.path.join(REPO, "exampleSite", "hugo.toml")
i18n_dir = os.path.join(REPO, "i18n")
if not os.path.isfile(cfg_path):
    bad("exampleSite/hugo.toml 存在", cfg_path)
else:
    cfg = open(cfg_path, encoding="utf-8", errors="ignore").read()
    m = re.search(r"^\s*defaultContentLanguage\s*=\s*['\"]([^'\"]+)['\"]", cfg, re.M)
    if not m:
        bad("exampleSite 声明了 defaultContentLanguage")
    else:
        dcl = m.group(1)
        stems = set()
        if os.path.isdir(i18n_dir):
            stems = {f.rsplit(".", 1)[0].lower()
                     for f in os.listdir(i18n_dir) if f.endswith(".yaml")}
        # 主语言键必须能命中一个 i18n 文件（否则 0.128/0.148 上全站文案为空）
        ok("8a exampleSite 语言键 '" + dcl + "' 命中 i18n 文件") \
            if dcl.lower() in stems else bad(
                "8a exampleSite 语言键 '" + dcl + "' 命中 i18n 文件",
                "i18n 文件: " + ", ".join(sorted(stems)) + "（大小写不敏感；zh 不会展开成 zh-CN）")
        # 反向：每个 i18n 文件都应能在某个语言键下被用到（避免新增了文件却忘记接线）
        lang_keys = set(re.findall(r"^\s*\[languages\.([^\]]+)\]", cfg, re.M))
        lang_keys.add(dcl)
        unused = sorted(s for s in stems if s not in {k.lower() for k in lang_keys})
        # 允许"供语言切换配置 tools/lang-*.toml 使用"的文件（en / zh-TW）
        switcher_keys = set()
        for sw in re.findall(r"defaultContentLanguage\s*=\s*[\"']([^\"']+)[\"']",
                             _read_switchers(), re.M):
            switcher_keys.add(sw.lower())
        unused = [s for s in unused if s not in switcher_keys]
        ok("8a 每个 i18n 文件都有语言接线（无孤儿文件）") \
            if not unused else bad("8a 每个 i18n 文件都有语言接线（无孤儿文件）", str(unused))

# 8b 行为层：NEBULA_I18N 注入的**每个值**都必须非空。
# 语言键不匹配时，i18n 全部返回空串，注入块会变成 {"copied":"","copy":""...}——
# 这正是静默退化的指纹。用真实产物断言，比只读配置更接近"用户看到的东西"。
#
# 注意：不能直接 json.loads —— `--minify` 会去掉合法 JS 标识符键的引号
# （`copied:"已复制"`），那是**合法 JS 但不是合法 JSON**。因此这里用容错解析：
# 同时接受带引号与裸标识符两种键形态，只关心"值是否为空"。
if home is not None:
    m = re.search(r"NEBULA_I18N\s*=\s*(\{.*?\})\s*[;<]", home, re.S)
    if not m:
        bad("8b NEBULA_I18N 注入块可解析")
    else:
        blob = m.group(1)
        pairs = re.findall(
            r'(?:"([^"]+)"|([A-Za-z_$][\w$]*))\s*:\s*"((?:[^"\\]|\\.)*)"', blob)
        items = {(a or b): c for a, b, c in pairs}
        ok("8b NEBULA_I18N 注入块可解析（兼容 --minify 裸键）") \
            if items else bad("8b NEBULA_I18N 注入块可解析（兼容 --minify 裸键）", blob[:120])
        if items:
            empties = sorted(k for k, v in items.items() if not v.strip())
            ok("8b NEBULA_I18N 无空值（语言键与 i18n 文件名匹配）") \
                if not empties else bad(
                    "8b NEBULA_I18N 无空值（语言键与 i18n 文件名匹配）",
                    "空值键: " + ", ".join(empties[:8]) + f"（共 {len(empties)} 个）")
            ok("8b NEBULA_I18N 键数量合理（>=10）") \
                if len(items) >= 10 else bad("8b NEBULA_I18N 键数量合理（>=10）", str(len(items)))

print()
if not checks:
    print("FAIL 未执行到任何功能断言（按失败处理）")
    sys.exit(1)
if errors:
    print(f"FAIL: {len(errors)} 项功能断言未通过")
    for e in errors:
        print("  -", e)
    print("TEST-RESULT: " + json.dumps(
        {"suite": "check-features", "status": "FAIL",
         "passed": len(checks) - len(errors), "failed": len(errors), "total": len(checks)},
        ensure_ascii=False))
    sys.exit(1)
print(f"PASS 全部功能断言通过（{len(checks)} 项）")
print("TEST-RESULT: " + json.dumps(
    {"suite": "check-features", "status": "PASS",
     "passed": len(checks), "failed": 0, "total": len(checks)}, ensure_ascii=False))
