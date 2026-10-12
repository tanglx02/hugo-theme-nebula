#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""用 Playwright 对本地 Hugo 站点截图，用于主题 README 配图。

用法：
    # 1) 先起一个静态服务（本仓库 tools/serve.py 或任意 http server）
    python tools/serve.py public 8080
    # 2) 再截图
    BASE_URL=http://127.0.0.1:8080 python tools/screenshot.py

环境变量：
    BASE_URL   站点根地址（默认 http://localhost:1313，即 hugo server 默认端口）
    OUT_DIR    输出目录（默认 docs/screenshots）
    FORMAT     png | jpg（默认 jpg —— README 内嵌图用 JPEG 体积可控）
    QUALITY    JPEG 质量（默认 82）

体积约定：全部截图合计目标 **2–3 MB**（第九节要求）。JPEG + device_scale_factor=1
是该体积下的清晰度/体积折中；如需更高保真可 FORMAT=png（会显著变大）。
"""
import io
import os
import socket
import sys
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

from playwright.sync_api import sync_playwright

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = os.environ.get("BASE_URL", "").rstrip("/")
OUT = os.path.abspath(os.environ.get("OUT_DIR") or os.path.join(ROOT, "docs", "screenshots"))
SERVE_DIR = os.path.abspath(os.environ.get("SERVE_DIR") or os.path.join(ROOT, "public"))
FMT = (os.environ.get("FORMAT") or "jpg").lower()
QUALITY = int(os.environ.get("QUALITY") or "82")
EXT = "png" if FMT == "png" else "jpg"
os.makedirs(OUT, exist_ok=True)


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class _Quiet(SimpleHTTPRequestHandler):
    def log_message(self, *a):     # 静默：截图过程不需要访问日志
        pass


def start_server():
    """自起临时静态服务。

    为什么内置：外部 `nohup ... &` 起的服务在本环境里可能在父命令结束后被回收，
    导致 `ERR_CONNECTION_REFUSED`。把服务生命周期绑在截图脚本自身最可靠。
    指定 BASE_URL 时可跳过自起（用于已有服务/hugo server 的场景）。
    """
    if BASE:
        return None, None
    port = free_port()
    handler = lambda *a, **kw: _Quiet(*a, directory=SERVE_DIR, **kw)   # noqa: E731
    srv = ThreadingHTTPServer(("127.0.0.1", port), handler)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    return srv, f"http://127.0.0.1:{port}"


def shot(page, name, full_page=False, quality=None):
    path = os.path.join(OUT, f"{name}.{EXT}")
    kw = {"path": path, "full_page": full_page}
    if EXT == "jpg":
        kw["type"] = "jpeg"
        kw["quality"] = quality if quality is not None else QUALITY
    page.screenshot(**kw)
    print(f"  {name}.{EXT}  {os.path.getsize(path) // 1024} KB")


def main():
    srv, auto_base = start_server()
    global BASE
    if auto_base:
        BASE = auto_base
        print(f"自起静态服务: {BASE}  (root={SERVE_DIR})")
    try:
        return _run()
    finally:
        if srv:
            srv.shutdown()


def _run():
    with sync_playwright() as p:
        b = p.chromium.launch()

        # ---------- 桌面端（scale=1：README 显示宽度下足够清晰，体积可控）----------
        ctx = b.new_context(viewport={"width": 1440, "height": 950},
                            device_scale_factor=1, locale="zh-CN")
        page = ctx.new_page()

        # 1. 首页（亮色）—— cards 布局
        page.goto(BASE, wait_until="networkidle")
        page.wait_for_timeout(400)
        shot(page, "01-home-light", full_page=True)

        # 2. 首页（暗色）
        page.click("#themeToggle")
        page.wait_for_timeout(600)
        shot(page, "02-home-dark", full_page=True)
        page.click("#themeToggle")          # 切回亮色
        page.wait_for_timeout(400)

        # 3. 全文搜索（含结果高亮与本地化日期）
        page.click("#searchTrigger")
        page.wait_for_timeout(400)
        page.fill("#search-input", "应急响应")
        page.wait_for_timeout(800)
        shot(page, "03-search")
        page.keyboard.press("Escape")
        page.wait_for_timeout(300)

        # 4. 文章页（亮色，含目录 / 代码块 / 提示块）
        page.goto(f"{BASE}/posts/03-incident-response/", wait_until="networkidle")
        page.wait_for_timeout(400)
        shot(page, "04-post-light", full_page=True)

        # 5. 文章页（暗色）
        page.click("#themeToggle")
        page.wait_for_timeout(600)
        shot(page, "05-post-dark", full_page=True)
        page.click("#themeToggle")
        page.wait_for_timeout(300)

        # 6. 媒体与图表页（画廊 + Mermaid + KaTeX）——本轮新功能
        page.goto(f"{BASE}/posts/media-and-diagrams/", wait_until="networkidle")
        page.wait_for_timeout(1500)          # 等 Mermaid / KaTeX 渲染完成
        shot(page, "06-media-diagrams", full_page=True)

        # 7. 作者与外观页（多作者 / 编辑入口）
        page.goto(f"{BASE}/posts/authors-and-appearance/", wait_until="networkidle")
        page.wait_for_timeout(400)
        shot(page, "07-authors-appearance", full_page=True)

        # 8. 内容组件页（提示块 / 标签页 / 文件树 / 徽标 / 按钮）
        page.goto(f"{BASE}/posts/content-components/", wait_until="networkidle")
        page.wait_for_timeout(400)
        shot(page, "08-content-components", full_page=True)

        # 9. 归档页
        page.goto(f"{BASE}/archives/", wait_until="networkidle")
        page.wait_for_timeout(400)
        shot(page, "09-archive")

        ctx.close()

        # ---------- 移动端 ----------
        m = b.new_context(viewport={"width": 390, "height": 844},
                          device_scale_factor=2, locale="zh-CN",
                          is_mobile=True, has_touch=True)
        mp = m.new_page()
        mp.goto(BASE, wait_until="networkidle")
        mp.wait_for_timeout(400)
        shot(mp, "10-mobile", quality=80)
        m.close()

        b.close()

    total = sum(os.path.getsize(os.path.join(OUT, f))
                for f in os.listdir(OUT) if f.endswith((".png", ".jpg")))
    print(f"\nscreenshots -> {OUT}")
    print(f"合计 {total / 1024 / 1024:.2f} MB（目标 2–3 MB）")
    if total > 3 * 1024 * 1024 + 1024:
        print("[WARN] 超过 3 MB，请调低 QUALITY 或减少 full_page 截图")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())