#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""三种 baseURL 部署验证（P6）：根 / /blog/ /blog/sub/

每种部署：独立生产构建 -> 独立静态服务器 -> 浏览器检查
  - CSS/JS/图片/favicon 可访问且路径带 basePath
  - RSS / sitemap / robots / index.json 正确
  - 页面内所有站内链接不得跳出 basePath
  - canonical / og:url / 面包屑 / 菜单 / 分类 / 标签 / 分页 正确
"""
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.request
import shlex

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _testlib import (  # noqa: E402
    EXIT_FAIL, EXIT_PASS, Harness, TempWorkspace, fresh_dir, safe_rmtree,
    launch as _launch, reachable, guard,
)

from playwright.sync_api import sync_playwright  # noqa: E402


ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))


def _resolve_site():
    """站点目录：显式 SITE_DIR 优先，其次仓库自带 exampleSite，最后兼容旧的 myblog。

    与 verify_multisection / subdir_test 同一处理 —— 旧默认写死 `<repo>/myblog`，
    该目录早已移出仓库，**裸跑必然失败**（CI 因显式传 SITE_DIR 侥幸通过）。
    """
    env = os.environ.get("SITE_DIR")
    if env:
        return os.path.abspath(env)
    for cand in (os.path.join(ROOT, "exampleSite"),
                 os.path.join(ROOT, "myblog")):
        if os.path.isdir(cand):
            return os.path.abspath(cand)
    return os.path.abspath(os.path.join(ROOT, "exampleSite"))


SITE = _resolve_site()
HUGO_ARGS = shlex.split(os.environ.get("HUGO_ARGS", ""))
# 用仓库自带 exampleSite 时须显式给出主题目录（不经 themes/ 子目录引用主题）。
if not HUGO_ARGS and os.path.basename(SITE) == "exampleSite":
    HUGO_ARGS = ["--source", ".", "--themesDir", "../.."]
HUGO = os.environ.get("HUGO_BIN", "hugo")   # CI 中 hugo 已在 PATH；本地可用 HUGO_BIN 指定
# 引擎参数（TEST-DEFECT-R2-002）：baseURL 路径解析在不同引擎下有差异，
# 支持在 chromium / firefox / webkit 上运行（默认 chromium 保持向后兼容）。
BROWSER = os.environ.get("PW_BROWSERS") or (sys.argv[1] if len(sys.argv) > 1 else "chromium")
import time as _time
# TEST-DEFECT-R2-004：deploy 目录必须**并发安全**。
# 旧实现只用 %H%M%S，同一秒内并行跑多个引擎（chromium/firefox/webkit）会撞同一目录，
# 互相删除/覆盖对方正在构建的产物 -> 误报"构建失败"。加入 PID 保证唯一。
DEPLOY = os.path.join(
    ROOT, "tmp",
    "deploy-" + (os.environ.get("BASEURL_RUN_ID")
                 or f"{_time.strftime('%H%M%S')}-{os.getpid()}"))
PY = sys.executable

CASES = [
    # (名称, baseURL, 构建输出目录, 服务器根, 访问 URL)
    ("root", "https://example.com/", "root", "root", "http://127.0.0.1:8101/"),
    ("blog", "https://example.com/blog/", "blog", ".", "http://127.0.0.1:8102/blog/"),
    ("blog-sub", "https://example.com/blog/sub/", "blog/sub", ".", "http://127.0.0.1:8102/blog/sub/"),
]

H = Harness("baseurl")


def rec(case, name, ok, detail=""):
    return H.record(f"[{case}] {name}", ok, detail)


def build(base_url, out_dir):
    # 每次构建前清空目标目录（边界约束在 DEPLOY 内），绝不复用上次残留产物。
    # TEST-DEFECT-R2-004/R2-008：旧实现只 makedirs(exist_ok=True)，残留 HTML 会被
    # 当作本次有效产物 —— 正是"读旧产物得 PASS"的假绿来源。
    dest = os.path.join(DEPLOY, out_dir)
    fresh_dir(dest, boundary=DEPLOY)
    # Hugo 构建锁：异常中断/外部干扰后会残留，导致后续构建 "Access is denied"。
    # --noBuildLock 从根上避免该文件产生（测试构建不需要锁语义）。
    try:
        lk = os.path.join(SITE, ".hugo_build.lock")
        if os.path.exists(lk):
            os.remove(lk)
    except OSError:
        pass
    cmd = [HUGO] + HUGO_ARGS + ["--noBuildLock", "--gc", "--minify",
                                "--baseURL", base_url, "-d", dest]
    p = subprocess.run(cmd, cwd=SITE, capture_output=True, text=True, encoding="utf-8", errors="ignore")
    # TEST-DEFECT-R2-008：必须看**真实退出码**，不能只匹配 stdout 里以 ERROR 开头的行。
    # Hugo 可能以非零码失败却不打印 "ERROR" 前缀（或在被截断的日志里被漏掉），
    # 旧实现会把这种失败当成功，进而把上一次残留的 HTML 当有效产物。
    errs = [l for l in (p.stderr + p.stdout).splitlines() if l.strip().upper().startswith("ERROR")]
    if p.returncode != 0:
        tail = (p.stderr or p.stdout or "").strip().splitlines()
        errs = [f"hugo 退出码 {p.returncode}"] + errs + tail[-3:]
    return dest, errs


def check(case, base):
    path = base.replace("http://127.0.0.1:8101", "").replace("http://127.0.0.1:8102", "")
    path = path if path != "/" else "/"
    print(f"\n=== [{case}] base={base} (basePath={path}) ===")

    with sync_playwright() as p:
        launcher = {"chromium": p.chromium, "firefox": p.firefox,
                    "webkit": p.webkit}.get(BROWSER, p.chromium)
        b = _launch(launcher)
        ctx = b.new_context(viewport={"width": 1440, "height": 900}, locale="zh-CN")
        page = ctx.new_page()
        bad = []
        page.on("response", lambda r: bad.append(f"{r.status} {r.url}") if r.status >= 400 else None)

        # 首页
        r = page.goto(base, wait_until="load")
        rec(case, "首页可达", r and r.status == 200, str(r and r.status))
        page.wait_for_timeout(700)
        rec(case, "首页无失败请求", not bad, bad[:3])

        # CSS / JS / 图片 / favicon
        assets = page.evaluate("""() => ({
            css: Array.from(document.querySelectorAll('link[rel=stylesheet]')).map(l => l.href),
            js: Array.from(document.querySelectorAll('script[src]')).map(s => s.src),
            img: Array.from(document.images).map(i => i.currentSrc).filter(Boolean)
        })""")
        for kind, urls in assets.items():
            if not urls:
                rec(case, f"{kind} 存在", False, "无")
                continue
            # 只校验真正的"路径"：data: / blob: / 锚点不是站内资源，
            # 它们天然不存在 basePath 前缀问题（灯箱占位图就是 1x1 data URI）。
            real = [u for u in urls
                    if not u.startswith(("data:", "blob:", "about:", "#"))]
            wrong = [u for u in real if not u.startswith(base)]
            rec(case, f"{kind} 路径在 basePath 内", not wrong,
                f"{len(real)} 个可校验"
                + (f"，已跳过 {len(urls) - len(real)} 个 data/blob URL" if len(urls) != len(real) else "")
                + (f"，异常 {wrong[:2]}" if wrong else ""))

        fav = page.evaluate("""async () => {
            const links = Array.from(document.querySelectorAll('link[rel*=icon]'));
            const out = [];
            for (const l of links) {
                try { const r = await fetch(l.href, {method:'HEAD'}); out.push(r.status); }
                catch(e) { out.push('ERR'); }
            }
            return out;
        }""")
        rec(case, "favicon 可访问", all(s == 200 for s in fav) and len(fav) > 0, fav)

        # 站内链接不跳出 basePath
        internal = page.evaluate("""() => Array.from(document.querySelectorAll('a[href]'))
            .map(a => a.getAttribute('href'))
            .filter(h => h && h.startsWith('/'))""")
        outside = sorted(set(h for h in internal if not h.startswith(path)))
        rec(case, "首页站内链接不跳出 basePath", not outside,
            f"{len(internal)} 条内部链接，越界 {outside[:3]}")

        # canonical / og:url
        canon = page.evaluate("""() => {
            const c = document.querySelector('link[rel=canonical]');
            const o = document.querySelector('meta[property="og:url"]');
            return { canonical: c ? c.href : null, ogurl: o ? o.content : null };
        }""")
        rec(case, "canonical 指向本站", bool(canon["canonical"]) and path in canon["canonical"], canon["canonical"])
        rec(case, "og:url 指向本站", bool(canon["ogurl"]) and path in canon["ogurl"], canon["ogurl"])

        # 搜索
        page.click("#searchTrigger")
        page.wait_for_timeout(400)
        page.fill("#search-input", "应急响应")
        page.wait_for_timeout(1200)
        rec(case, "子目录搜索可用", page.locator(".search-item").count() > 0,
            f'{page.locator(".search-item").count()} 条')
        page.keyboard.press("Escape")

        # 文章页（含面包屑 / 分类 / 标签链接）
        page.goto(base + "posts/03-incident-response/", wait_until="load")
        page.wait_for_timeout(500)
        crumb = page.evaluate("""() => Array.from(document.querySelectorAll('.breadcrumb a')).map(a => a.getAttribute('href'))""")
        rec(case, "面包屑链接在 basePath 内",
            all(h and h.startswith(path) for h in crumb) and len(crumb) > 0, crumb)
        brand = page.evaluate("""() => document.querySelector('.brand').getAttribute('href')""")
        rec(case, "Logo 链接在 basePath 内", bool(brand) and brand.startswith(path), brand)
        menu = page.evaluate("""() => Array.from(document.querySelectorAll('#mainNav a')).map(a => a.getAttribute('href')).filter(h => h && h.startsWith('/'))""")
        rec(case, "菜单链接在 basePath 内",
            all(h.startswith(path) for h in menu) and len(menu) > 0, menu[:4])
        dup_menu = [] if path == "/" else [h for h in menu if h.count(path) > 1]
        rec(case, "菜单链接无 basePath 重复", not dup_menu, f"{menu[:4]} 重复 {dup_menu[:3]}")

        # 内部链接实际可达（抽样，防止链接指向 404）
        origin = re.match(r"(https?://[^/]+)", base).group(1)
        broken = []
        for h in sorted(set(internal))[:40]:
            try:
                with urllib.request.urlopen(origin + h, timeout=10) as rr:
                    if rr.status != 200:
                        broken.append((h, rr.status))
            except Exception as e:
                broken.append((h, str(e)[:40]))
        rec(case, "首页内部链接实际可达（抽样 40 条）", not broken, broken[:3])

        # 分类页 / 标签页 / 分页
        for name, url in (("分类页", base + "categories/"), ("标签页", base + "tags/"),
                          ("归档页", base + "archives/"), ("文章列表", base + "posts/")):
            rr = page.goto(url, wait_until="load")
            page.wait_for_timeout(400)
            rec(case, f"{name} 可达", rr and rr.status == 200, str(rr and rr.status))

        # 分页可达
        page.goto(base + "posts/", wait_until="load")
        page.wait_for_timeout(400)
        has_page2 = os.path.exists(os.path.join(DEPLOY, "root" if case == "root" else ("blog" if case == "blog" else "blog/sub"), "posts", "page", "2", "index.html"))
        if has_page2:
            rr = page.goto(base + "posts/page/2/", wait_until="load")
            rec(case, "分页第 2 页可达", rr and rr.status == 200, str(rr and rr.status))

        # RSS / sitemap / robots
        for name, rel, checker in (
            ("RSS", "index.xml", lambda t: "<link>" in t and path in t),
            ("sitemap", "sitemap.xml", lambda t: t.count("<loc>") > 0),
            ("robots", "robots.txt", lambda t: "Sitemap:" in t),
            ("index.json", "index.json", lambda t: t.strip().startswith("[")),
        ):
            try:
                with urllib.request.urlopen(base + rel, timeout=20) as resp:
                    txt = resp.read().decode("utf-8", "ignore")
                rec(case, f"{name} 可访问且内容正确", checker(txt), f"{len(txt)} 字节")
                if name == "sitemap":
                    # sitemap 使用绝对 URL，判定"是否包含正确的 basePath"
                    locs = re.findall(r"<loc>(.*?)</loc>", txt)
                    bad_loc = [l for l in locs if path not in l]
                    dup = [] if path == "/" else [l for l in locs if l.count(path) > 1]
                    rec(case, "sitemap 全部 loc 在 basePath 内", not bad_loc,
                        f"{len(locs)} 条，越界 {bad_loc[:2]}")
                    rec(case, "sitemap loc 无 basePath 重复", not dup, f"重复 {dup[:2]}")
                if name == "robots":
                    sm = re.search(r"Sitemap:\s*(\S+)", txt)
                    rec(case, "robots Sitemap 指向 basePath", bool(sm) and path in sm.group(1), sm and sm.group(1))
            except Exception as e:
                rec(case, f"{name} 可访问且内容正确", False, str(e)[:80])

        ctx.close()
        b.close()


def _run_all():
    os.makedirs(DEPLOY, exist_ok=True)
    # TEST-DEFECT-R2-004：Hugo 构建锁（<site>/.hugo_build.lock）在异常中断后会残留，
    # 后续构建报 "failed to acquire a build lock ... Access is denied"。
    # 这是**运行期清理**问题（.gitignore 只影响 git 上报，无法阻止残留）。
    # 前置清理本工具可能留下的锁，保证"失败不污染下次运行"。
    lock = os.path.join(SITE, ".hugo_build.lock")
    try:
        if os.path.exists(lock):
            os.remove(lock)
    except OSError:
        pass
    try:
        _run_all_inner()
    finally:
        # TEST-DEFECT-R2-003/004：本次运行的 deploy 目录必须清理，
        # 既不污染下次运行，也不在仓库留下构建产物。
        try:
            safe_rmtree(DEPLOY)
        except Exception as e:      # pragma: no cover
            print(f"[WARN] 清理 deploy 目录失败 {DEPLOY}: {e}")


def _run_all_inner():
    for name, base_url, out_dir, _, _ in CASES:
        dest, errs = build(base_url, out_dir)
        print(f"构建 {name} -> {dest} : {'OK' if not errs else 'ERROR'}")
        for e in errs[:3]:
            print("   ", e[:150])
        if errs:
            H.fatal_error(f"构建失败 [{name}] {base_url}", errs[0][:160])
        elif not os.path.exists(os.path.join(dest, "index.html")):
            H.fatal_error(f"构建产物缺失 [{name}]", f"{dest}/index.html 不存在")
    if H.fatal:
        return   # 构建失败时后续浏览器检查无意义

    # 启动两个静态服务器
    # 先探一次端口：被残留进程占用时，子进程会静默 bind 失败，表现为
    # "30s 后仍未就绪"这类难以定位的 FATAL。这里提前给出明确原因。
    for _port in (8101, 8102):
        if reachable(f"http://127.0.0.1:{_port}/"):
            H.fatal_error(
                f"端口 {_port} 已被占用",
                f"请先关闭残留在 {_port} 上的静态服务器（重复运行本工具可能留下 serve.py）")
            return
    srv1 = subprocess.Popen([PY, os.path.join(ROOT, "tools", "serve.py"), os.path.join(DEPLOY, "root"), "8101"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    srv2 = subprocess.Popen([PY, os.path.join(ROOT, "tools", "serve.py"), DEPLOY, "8102"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        ready = False
        for _ in range(30):
            if reachable("http://127.0.0.1:8101/") and reachable("http://127.0.0.1:8102/blog/"):
                ready = True
                break
            time.sleep(1)
        if not ready:
            H.fatal_error("静态服务器启动失败", "8101 / 8102 未就绪")
            return

        for name, base_url, out_dir, _, url in CASES:
            check(name, url)
    finally:
        srv1.terminate()
        srv2.terminate()


def selftest_exitcode():
    """故障注入自证（TEST-DEFECT-R2-008）：证明本工具**看真实退出码**，
    绝不把上一次残留的 HTML 当成本次有效产物。

    做法：用一个假 hugo 包装器——它**先写出一个"看起来正常"的 index.html**（模拟
    上一次构建的残留），再以**非零退出码**结束。若门禁只看 stdout 的 "ERROR" 前缀
    或只看产物是否存在，就会把这份残留当成成功产物 -> 假绿。
    正确行为：构建阶段必须因非零退出码触发 FATAL，整体 exit != 0。
    """
    print("=== verify_baseurl 退出码注入自证（残留产物 + 非零退出码必须判失败）===")
    h = Harness("baseurl-selftest")

    src_site = os.environ.get("SITE_DIR") or os.path.join(ROOT, "exampleSite")
    if not os.path.isdir(src_site):
        print(f"[FATAL] 找不到站点目录用于注入: {src_site}")
        sys.exit(EXIT_FAIL)

    with TempWorkspace("baseurl-selftest") as ws:
        # 假 hugo：把 stale 产物写进 -d 目录，然后以退出码 1 结束。
        # 为绕开 Windows 下 .cmd 包装器的中文路径编码问题，这里**不经 shell**：
        #   HUGO_BIN   = 当前 Python 解释器
        #   HUGO_ARGS  = "<fake_hugo.py>"（shlex 解析后成为第一个参数）
        # build() 会拼成 [python, <fake_hugo.py>, ...hugo args]，等价于直接执行脚本。
        fake_py = ws.path("fake_hugo.py")
        # 假 hugo 除写出 STALE 产物外，再向 marker 记一行"我确实写了产物"。
        # 为什么需要 marker：本工具**修复后**会在失败路径正确清理 deploy 目录
        # （TEST-DEFECT-R2-003/004），因此父进程再去 stat 残留 index.html 时它已被
        # 自己的清理删掉——那是"清理生效"的正确表现，不能据此判注入失败。
        # marker 写在 ws（唯一临时目录）里，与产物清理互不干扰，作为注入生效的真实证据。
        marker = ws.path("stale_marker.txt")
        with open(fake_py, "w", encoding="utf-8") as f:
            f.write(
                "import os, sys\n"
                "args = sys.argv[1:]\n"
                "dest = None\n"
                "if '-d' in args:\n"
                "    dest = args[args.index('-d') + 1]\n"
                "if dest:\n"
                "    os.makedirs(dest, exist_ok=True)\n"
                "    with open(os.path.join(dest, 'index.html'), 'w', encoding='utf-8') as g:\n"
                "        g.write('<!doctype html><title>STALE</title>')\n"
                "mk = os.environ.get('BASEURL_SELFTEST_MARKER')\n"
                "if mk:\n"
                "    with open(mk, 'w', encoding='utf-8') as g:\n"
                "        g.write('wrote-stale:' + (dest or ''))\n"
                "sys.stderr.write('injected build failure (stale artifact left behind)\\n')\n"
                "sys.exit(1)\n")

        env = dict(os.environ)
        env["HUGO_BIN"] = sys.executable            # 直接执行解释器，不经 shell
        env["HUGO_ARGS"] = f'"{fake_py}"'          # shlex -> [fake_py]
        env["SITE_DIR"] = os.path.abspath(src_site)
        run_id = f"inj{os.getpid()}"
        env["BASEURL_RUN_ID"] = run_id
        env["BASEURL_SELFTEST_MARKER"] = marker     # 传给假 hugo（经子进程 env 继承）
        env.pop("PW_BROWSERS", None)       # 构建阶段就会失败，到不了浏览器
        deploy_dir = os.path.join(ROOT, "tmp", "deploy-" + run_id)

        try:
            p = subprocess.run([sys.executable, os.path.abspath(__file__)],
                               capture_output=True, text=True, encoding="utf-8",
                               errors="ignore", env=env)
            out = p.stdout + p.stderr
            # 关键证据：注入确实写出了 STALE 产物（否则注入没有意义）。
            # 用 marker 判断而非直接 stat 产物——本工具修复后会在失败路径清理产物，
            # 产物消失恰恰是"运行期清理生效"的正确行为（TEST-DEFECT-R2-003/004）。
            injected = os.path.isfile(marker) and "wrote-stale" in open(
                marker, encoding="utf-8").read()
            h.record("注入确实写出了 STALE 产物（证明'读残留得 PASS'是真实风险）",
                     injected, "假 hugo 写产物并留下 marker 证据")
            # 附加证据：修复后的成功/失败路径都应把产物清掉（不留残骸）
            leftover = os.path.isfile(os.path.join(deploy_dir, "root", "index.html"))
            h.record("失败路径已清理本次残留产物（运行期清理生效）", not leftover,
                     f"deploy 目录残留={leftover}")
            h.record("非零退出码使整体判失败（exit!=0）", p.returncode != 0,
                     f"rc={p.returncode}")
            h.record("失败原因指向构建退出码而非产物缺失",
                     ("退出码" in out) or ("构建失败" in out),
                     next((l for l in out.splitlines() if "构建失败" in l or "退出码" in l), "未命中")[:120])

            # 反向再验一次：仅凭 stdout 里是否出现 ERROR 前缀不足以判定（假 hugo 不打印 ERROR）
            h.record("假 hugo 未打印 ERROR 前缀（证明不能只靠 stdout 前缀判断）",
                     "ERROR" not in out.upper().split("HUGO")[0],
                     "stderr 仅有 injected build failure 一行")
        finally:
            # 清理本注入留下的 deploy 目录（边界约束在 ROOT/tmp 内）
            from _testlib import safe_rmtree
            try:
                safe_rmtree(deploy_dir)
            except Exception as e:      # pragma: no cover
                print(f"[WARN] 清理注入目录失败 {deploy_dir}: {e}")

    h.finish()


def main():
    if "--selftest-exitcode" in sys.argv[1:]:
        selftest_exitcode()
        return
    guard(H, _run_all)
    H.finish()


if __name__ == "__main__":
    main()
