#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""子目录部署路径验证：baseURL = https://example.com/blog/ 时，资源、链接、搜索是否全部正确。

⚠ 本脚本此前**没有任何退出码**（既无 sys.exit 也无 TEST-RESULT），
   一旦失败 CI 仍视为通过 —— 是仓库里唯一"任何失败退出码都不变"的验证脚本
   （TEST-DEFECT-009）。现在统一接入 tools/_testlib.py 的 Harness：
   失败 / 空用例 / 环境问题一律 exit 1。

⚠ TEST-DEFECT-R2-006（实测假绿）：构建输出目录 `tmp/public-blog` 与静态服务目录
   `tmp/serve/blog` **跨次复用且从不清理**。删掉源文章 `03-incident-response.md`
   后再跑，旧 HTML 仍同时留在构建目录与服务目录里，脚本照样 10/10 PASSED ——
   假绿（子代理 A 独立复现）。
   现在的做法：
     * 构建目录 = `tmp/<唯一 run-id>/build`，服务目录 = `tmp/<唯一 run-id>/serve/blog`；
       二者**互不重叠**，不再互相覆盖；
     * 构建**之前**清空构建目录（fresh_dir），保证断言看到的一定是本次产物；
     * 整个临时工作区用 `with TempWorkspace(...)` 包裹 —— 成功 / 失败 / 异常 / 中断
       都会清理（不再依赖 `.gitignore` 打掩护）；
     * 删除动作全部经 `safe_rmtree` 的**项目目录边界**校验，绝不越界。

   负向自证（必须能红）：见文件末尾 `negative_selftest()` —— 删源文章 -> 期望脚本失败。
   手动验证命令：`python tools/subdir_test.py`（正常应全绿）。

用法：
    python3 tools/subdir_test.py
环境变量：
    HUGO_BIN     hugo 可执行文件（默认 PATH 中的 hugo）
    SUBDIR_SITE  站点目录（默认 <repo>/myblog）
    KEEP_TMP=1   保留本次临时目录以便排查（默认不保留）
退出码约定（见 tools/_testlib.py）：任一断言失败 -> exit 1。
"""
import os
import shutil
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _testlib import Harness, guard, launch, reachable  # noqa: E402
from _testlib import TempWorkspace, fresh_dir  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))


def _resolve_site():
    """站点目录解析（TEST-DEFECT-R2-003 同族：默认基准必须明确且一致）。

    优先 SUBDIR_SITE；否则 exampleSite（仓库自带的真实示例站，有 content/posts）；
    最后才回退到 myblog。旧实现硬编码 `<repo>/myblog`，而该目录在仓库里并不存在，
    从仓库外调用会直接 FATAL，或用错站点仍"看起来通过"。
    """
    env = os.environ.get("SUBDIR_SITE")
    if env:
        return os.path.abspath(env)
    for cand in (os.path.join(ROOT, "exampleSite"), os.path.join(ROOT, "myblog")):
        if os.path.isdir(os.path.join(cand, "content", "posts")):
            return cand
    return os.path.join(ROOT, "exampleSite")


SITE = _resolve_site()
# exampleSite 是主题仓库内的站点，需要 --themesDir 指到仓库上一级；
# myblog 这类独立站点不需要。这里按需自动附加，避免"能构建但找不到主题"。
SITE_IS_EXAMPLESITE = os.path.basename(SITE) == "exampleSite"
HUGO = os.environ.get("HUGO_BIN", "hugo")
PORT = 8089
BASE = f"http://127.0.0.1:{PORT}/blog/"


def _hugo_args():
    # --noBuildLock：避免 .hugo_build.lock 残留导致后续构建被拒
    # （"failed to acquire a build lock ... Access is denied"）。
    # 多个测试/引擎并发或异常中断后，该锁常残留；测试构建不需要锁语义。
    args = [HUGO, "--noBuildLock", "--gc", "--minify",
            "--baseURL", "https://example.com/blog/"]
    if SITE_IS_EXAMPLESITE:
        args += ["--source", SITE, "--themesDir", os.path.dirname(ROOT)]
    return args


def run(h):
    if not os.path.isdir(SITE):
        h.fatal_error("站点目录不存在", SITE)
        return

    # 唯一临时工作区：构建目录与服务目录分离，且成功/失败/异常都会清理
    with TempWorkspace("subdir") as ws:
        build = ws.path("build")
        serve_root = ws.path("serve")
        mount = os.path.join(serve_root, "blog")

        # 关键：构建前从空目录开始 —— 绝不让上一次的 HTML 冒充本次产物
        fresh_dir(build, boundary=ws.path_root)

        cmd = _hugo_args() + ["-d", build]
        r = subprocess.run(cmd, cwd=SITE, capture_output=True, text=True,
                           encoding="utf-8", errors="ignore")
        errs = [ln for ln in (r.stdout + r.stderr).splitlines()
                if ln.strip().upper().startswith("ERROR")]
        # 真实退出码优先（TEST-DEFECT-R2-008 同类问题）：非零即失败
        if r.returncode != 0 or errs:
            h.fatal_error("子目录 baseURL 构建失败",
                          (f"rc={r.returncode}; " if r.returncode != 0 else "")
                          + (errs[0] if errs else "")[:160])
            return
        # 构建成功但产物缺失，同样是失败（防止 -d 指向别处时的假通过）
        if not os.path.isfile(os.path.join(build, "index.html")):
            h.fatal_error("子目录构建产物缺失", f"{build}/index.html 不存在")
            return

        os.makedirs(serve_root, exist_ok=True)
        shutil.copytree(build, mount)

        srv = subprocess.Popen([sys.executable, os.path.join(ROOT, "tools", "serve.py"),
                                serve_root, str(PORT)],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            for _ in range(20):
                if reachable(BASE, timeout=2):
                    break
                time.sleep(0.5)
            else:
                h.fatal_error("子目录静态服务器不可达", BASE)
                return

            _browser_checks(h, BASE)
        finally:
            srv.terminate()
            try:
                srv.wait(timeout=5)
            except Exception:
                srv.kill()


def _browser_checks(h, base):
    with sync_playwright() as p:
        b = launch(p.chromium)
        ctx = b.new_context(viewport={"width": 1440, "height": 900}, locale="zh-CN")
        page = ctx.new_page()
        bad = []
        page.on("response", lambda r: bad.append(f"{r.status} {r.url}")
                if r.status >= 400 else None)

        page.goto(base, wait_until="load")
        page.wait_for_timeout(400)
        h.record("子目录首页可达", page.locator(".post-card").count() > 0)
        h.record("子目录无失败请求", not bad, bad[:5])

        css = page.evaluate(
            "() => Array.from(document.querySelectorAll('link[rel=stylesheet]')).map(l => l.href)")
        js = page.evaluate(
            "() => Array.from(document.querySelectorAll('script[src]')).map(s => s.src)")
        h.record("CSS 路径包含 /blog/", bool(css) and all("/blog/" in c for c in css), css)
        h.record("JS 路径包含 /blog/",
                 all("/blog/" in s for s in js if "127.0.0.1" in s), js)

        idx_path = page.evaluate("""async () => {
            const el = document.querySelector('script[src*="main"]');
            if (!el) return 'no-main-script';
            const r = await fetch(el.src);
            const t = await r.text();
            const m = t.match(/(\\/blog\\/index\\.json|index\\.json)/);
            return m ? m[1] : 'none';
        }""")
        h.record("搜索索引路径正确", "index.json" in str(idx_path), idx_path)

        page.click("#searchTrigger")
        page.wait_for_timeout(300)
        page.fill("#search-input", "应急响应")
        page.wait_for_timeout(800)
        n = page.locator(".search-item").count()
        h.record("子目录下搜索可用", n > 0, f"{n} 条")
        page.keyboard.press("Escape")
        page.wait_for_timeout(200)

        page.goto(base + "posts/03-incident-response/", wait_until="load")
        # 用安全读取（元素缺失时返回空串）而不是直接 inner_text —— 元素不存在会抛异常，
        # 那样负向场景只能报"脚本异常"，看不出究竟哪条断言失败。
        body_text = page.evaluate(
            "() => { const el = document.querySelector('.post-content');"
            " return el ? el.innerText : ''; }")
        h.record(
            "子目录文章页可达",
            "排查" in body_text,
            "该断言依赖 exampleSite/content/posts/03-incident-response.md 存在；"
            "若源文章被删除，本次干净构建里不会有该页面（这正是 TEST-DEFECT-R2-006 "
            "负向自证所验证的点）",
        )
        imgs = page.evaluate("""() => Array.from(
            document.querySelectorAll('.post-content img, .article-cover img'))
            .map(i => ({src: i.currentSrc,
                        ok: i.naturalWidth > 0 || (i.loading === 'lazy' && !i.complete)}))""")
        h.record("文章页图片全部加载", all(i["ok"] for i in imgs),
                 [i["src"] for i in imgs if not i["ok"]][:3])
        h.record("子目录无失败请求(文章页)", not bad, bad[:5])

        try:
            page.click(".brand", timeout=5000)
            page.wait_for_load_state("load")
            h.record("品牌链接回到子目录首页", page.url == base, page.url)
        except Exception as e:      # 缺失文章时的 404 页可能没有 .brand
            h.record("品牌链接回到子目录首页", False,
                     f"点击 .brand 失败（可能当前页为 404）: {str(e)[:120]}")

        b.close()


def negative_selftest():
    """负向自证：临时删除源文章后，本脚本**必须失败**。

    TEST-DEFECT-R2-006 的验收方式就是这个 —— 不是"看起来改了"，而是
    "删掉源文章后再跑确实变红"。默认不执行（会临时改动站点内容），
    通过 `python tools/subdir_test.py --negative` 触发，结束后自动还原。
    """
    target = os.path.join(SITE, "content", "posts", "03-incident-response.md")
    backup = os.path.join(SITE, "content", "posts", "_03-incident-response.md.bak")
    if not os.path.isfile(target):
        print(f"[negative] 找不到源文章，跳过: {target}")
        return 2
    shutil.move(target, backup)
    print("[negative] 已临时移除源文章，期望本脚本失败 …")
    try:
        rc = subprocess.call([sys.executable, os.path.abspath(__file__)], cwd=ROOT)
    finally:
        shutil.move(backup, target)
        print("[negative] 已还原源文章")
    print(f"[negative] 结果 exit={rc}（期望非 0，即确实变红 —— 假绿已消除）")
    return 0 if rc != 0 else 1


if __name__ == "__main__":
    if "--negative" in sys.argv:
        sys.exit(negative_selftest())
    main_h = Harness("subdir")
    guard(main_h, run, main_h)
    main_h.finish()
