#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成博客封面 SVG —— 统一风格：深色渐变 + 网格 + 抽象几何 + 光晕。"""
import os

W, H = 1200, 675
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                   "..", "myblog", "static", "img", "cover")
OUT = os.path.normpath(OUT)


def grid(color, step=60, op=0.06):
    p = []
    for x in range(0, W + 1, step):
        p.append(f'<line x1="{x}" y1="0" x2="{x}" y2="{H}"/>')
    for y in range(0, H + 1, step):
        p.append(f'<line x1="0" y1="{y}" x2="{W}" y2="{y}"/>')
    return f'<g stroke="{color}" stroke-width="1" opacity="{op}">{"".join(p)}</g>'


def glow(cx, cy, r, color, op=0.35):
    return (f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{color}" opacity="{op}" '
            f'filter="url(#blur)"/>')


def shell(uid, c1, c2, accent, body):
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}">
<defs>
  <linearGradient id="bg{uid}" x1="0" y1="0" x2="1" y2="1">
    <stop offset="0%" stop-color="{c1}"/><stop offset="100%" stop-color="{c2}"/>
  </linearGradient>
  <radialGradient id="rg{uid}" cx="50%" cy="45%" r="60%">
    <stop offset="0%" stop-color="{accent}" stop-opacity="0.28"/>
    <stop offset="100%" stop-color="{accent}" stop-opacity="0"/>
  </radialGradient>
  <filter id="blur"><feGaussianBlur stdDeviation="70"/></filter>
  <filter id="soft"><feGaussianBlur stdDeviation="18"/></filter>
</defs>
<rect width="{W}" height="{H}" fill="url(#bg{uid})"/>
<rect width="{W}" height="{H}" fill="url(#rg{uid})"/>
{grid(accent)}
{body}
<rect width="{W}" height="{H}" fill="none" stroke="{accent}" stroke-opacity="0.18" stroke-width="2"/>
</svg>'''


# ---------- 1. 实验室 / 服务器机架 ----------
def lab():
    b = [glow(880, 180, 260, "#00b4d8", 0.30)]
    for i in range(3):
        x, y = 120 + i * 250, 200
        b.append(f'<g opacity="0.92"><rect x="{x}" y="{y}" width="150" height="230" rx="12" '
                 f'fill="#0a1a2f" stroke="#00b4d8" stroke-opacity="0.55" stroke-width="2"/>')
        for j in range(5):
            yy = y + 24 + j * 40
            b.append(f'<rect x="{x+18}" y="{yy}" width="114" height="22" rx="5" fill="#12314f"/>'
                     f'<circle cx="{x+30}" cy="{yy+11}" r="4" fill="#00b4d8"/>')
        b.append('</g>')
    b.append('<path d="M120 470 H1080" stroke="#00b4d8" stroke-opacity="0.5" stroke-width="2"/>')
    b.append('<text x="120" y="560" font-family="monospace" font-size="46" fill="#8fd6ff" '
             'opacity="0.9">HOME-LAB / ISOLATED</text>')
    return shell("1", "#0b2545", "#102a43", "#00b4d8", "".join(b))


# ---------- 2. WAF / 盾牌 ----------
def waf():
    b = [glow(240, 200, 300, "#ff5c8a", 0.28), glow(980, 480, 240, "#ff5c8a", 0.2)]
    b.append('<path d="M600 130 L820 210 V400 C820 520 720 590 600 630 C480 590 380 520 380 400 '
             'V210 Z" fill="#2a1030" stroke="#ff5c8a" stroke-opacity="0.75" stroke-width="4"/>')
    b.append('<path d="M600 200 L750 255 V400 C750 480 680 530 600 560 C520 530 450 480 450 400 '
             'V255 Z" fill="none" stroke="#ff9fbe" stroke-opacity="0.4" stroke-width="2"/>')
    for i, y in enumerate(range(300, 470, 55)):
        b.append(f'<rect x="520" y="{y}" width="{160 - i * 12}" height="14" rx="7" '
                 f'fill="#ff5c8a" opacity="{0.85 - i * 0.15}"/>')
    for i, x in enumerate(range(150, 400, 60)):
        b.append(f'<circle cx="{x}" cy="{180 + i * 70}" r="7" fill="#ff9fbe" opacity="0.8"/>')
        b.append(f'<path d="M{x} {180 + i * 70} L370 400" stroke="#ff9fbe" stroke-opacity="0.25" stroke-width="2"/>')
    b.append('<text x="600" y="470" text-anchor="middle" font-family="monospace" font-size="44" '
             'fill="#ffd0de" opacity="0.92">WAF BYPASS</text>')
    return shell("2", "#180a2a", "#3d1235", "#ff5c8a", "".join(b))


# ---------- 3. 应急响应 / 终端 ----------
def ir():
    b = [glow(600, 320, 300, "#ff9f1c", 0.22)]
    b.append('<rect x="140" y="140" width="920" height="420" rx="16" fill="#08151f" '
             'stroke="#ff9f1c" stroke-opacity="0.5" stroke-width="3"/>')
    b.append('<rect x="140" y="140" width="920" height="52" rx="16" fill="#0f2233"/>')
    for i, c in enumerate(["#ff5f57", "#febc2e", "#28c840"]):
        b.append(f'<circle cx="{176 + i * 28}" cy="166" r="8" fill="{c}"/>')
    lines = [
        ("$ ps auxf | grep -i miner", "#7dd3fc"),
        ("$ ss -tunap > /tmp/ir_ss.txt", "#7dd3fc"),
        ("$ awk -F: '$3==0' /etc/passwd", "#7dd3fc"),
        ("root  x  0  0  /bin/bash", "#ffb703"),
        ("ops   x  0  0  /bin/sh   &lt;-- 异常 UID", "#ff5c5c"),
        ("$ find /tmp -perm -u+x -type f", "#7dd3fc"),
        ("/tmp/.x11-unix/kworkerds  &lt;-- 可疑", "#ff5c5c"),
        ("$ journalctl -u sshd --since '3 days ago'", "#7dd3fc"),
    ]
    for i, (t, c) in enumerate(lines):
        b.append(f'<text x="180" y="{238 + i * 44}" font-family="monospace" font-size="26" '
                 f'fill="{c}" opacity="0.95">{t}</text>')
    return shell("3", "#0d1b2a", "#16324a", "#ff9f1c", "".join(b))


# ---------- 4. 流量监测 / SOC ----------
def soc():
    b = [glow(600, 300, 320, "#00f5d4", 0.22)]
    pts = [(120, 520), (250, 430), (380, 470), (510, 330), (640, 380), (770, 240), (900, 290), (1040, 170)]
    path = " ".join(f'{"M" if i == 0 else "L"}{x} {y}' for i, (x, y) in enumerate(pts))
    b.append(f'<path d="{path}" fill="none" stroke="#00f5d4" stroke-opacity="0.35" stroke-width="26" filter="url(#soft)"/>')
    b.append(f'<path d="{path}" fill="none" stroke="#00f5d4" stroke-width="4"/>')
    for x, y in pts:
        b.append(f'<circle cx="{x}" cy="{y}" r="9" fill="#04222b" stroke="#00f5d4" stroke-width="3"/>')
    for i in range(6):
        x = 120 + i * 184
        b.append(f'<rect x="{x}" y="560" width="120" height="14" rx="7" fill="#00f5d4" opacity="{0.7 - i * 0.08}"/>')
    b.append('<text x="120" y="120" font-family="monospace" font-size="42" fill="#9ff9e8" '
             'opacity="0.9">SURICATA · EVE · KIBANA</text>')
    return shell("4", "#07213d", "#0b3b47", "#00f5d4", "".join(b))


# ---------- 5. 容器 ----------
def container():
    b = [glow(600, 300, 300, "#58a6ff", 0.22)]
    boxes = [(300, 250), (500, 250), (700, 250), (400, 400), (600, 400)]
    for i, (x, y) in enumerate(boxes):
        b.append(f'<g><path d="M{x} {y} l95 -55 l95 55 l-95 55 z" fill="#132b47" '
                 f'stroke="#58a6ff" stroke-opacity="0.75" stroke-width="3"/>'
                 f'<path d="M{x} {y} l95 55 l95 -55" fill="none" stroke="#58a6ff" stroke-opacity="0.35" stroke-width="2"/>'
                 f'<path d="M{x} {y} v55" stroke="#58a6ff" stroke-opacity="0.5" stroke-width="3"/></g>')
    b.append('<path d="M300 250 L200 195" stroke="#58a6ff" stroke-opacity="0.4" stroke-width="3"/>')
    b.append('<path d="M700 250 L800 195" stroke="#58a6ff" stroke-opacity="0.4" stroke-width="3"/>')
    b.append('<path d="M600 470 L600 560" stroke="#ff7b72" stroke-opacity="0.8" stroke-width="4" '
             'stroke-dasharray="10 8"/>')
    b.append('<text x="600" y="620" text-anchor="middle" font-family="monospace" font-size="40" '
             'fill="#ffb3ae" opacity="0.9">ESCAPE</text>')
    return shell("5", "#101d2b", "#12325c", "#58a6ff", "".join(b))


# ---------- 6. SSH ----------
def ssh():
    b = [glow(600, 320, 280, "#a78bfa", 0.25)]
    for i, r in enumerate([230, 170, 110]):
        b.append(f'<circle cx="600" cy="330" r="{r}" fill="none" stroke="#a78bfa" '
                 f'stroke-opacity="{0.45 - i * 0.1}" stroke-width="{3 - i * 0.5}" '
                 f'stroke-dasharray="{12 + i * 8} {8 + i * 4}"/>')
    b.append('<rect x="545" y="330" width="110" height="86" rx="12" fill="#221740" '
             'stroke="#a78bfa" stroke-width="4"/>')
    b.append('<path d="M575 330 v-30 a25 25 0 0 1 50 0 v30" fill="none" stroke="#a78bfa" stroke-width="5"/>')
    b.append('<circle cx="600" cy="372" r="10" fill="#a78bfa"/>')
    b.append('<text x="600" y="560" text-anchor="middle" font-family="monospace" font-size="44" '
             'fill="#d6ccff" opacity="0.92">SSH HARDENING</text>')
    return shell("6", "#161a2b", "#2d1b4e", "#a78bfa", "".join(b))


# ---------- 7. Hugo ----------
def hugo():
    b = [glow(700, 260, 300, "#7c5cff", 0.28), glow(300, 480, 220, "#409eff", 0.25)]
    import math
    for k in range(3):
        pts = []
        for i in range(80):
            t = i / 79.0
            ang = t * math.pi * 3.2 + k * 2.1
            r = 40 + t * (230 - k * 45)
            x = 600 + r * math.cos(ang)
            y = 330 + r * math.sin(ang) * 0.55
            pts.append(f'{"M" if i == 0 else "L"}{x:.1f} {y:.1f}')
        b.append(f'<path d="{"".join(pts)}" fill="none" stroke="'
                 f'{"#7c5cff" if k % 2 == 0 else "#409eff"}" stroke-opacity="{0.55 - k * 0.12}" stroke-width="{3 - k * 0.6}"/>')
    b.append('<circle cx="600" cy="330" r="34" fill="#0e1430" stroke="#7c5cff" stroke-width="4"/>')
    b.append('<text x="600" y="345" text-anchor="middle" font-family="monospace" font-size="30" '
             'fill="#c3b6ff">HUGO</text>')
    return shell("7", "#0f2027", "#203a43", "#7c5cff", "".join(b))


def avatar():
    return '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 200" width="200" height="200">
<defs>
  <linearGradient id="ag" x1="0" y1="0" x2="1" y2="1">
    <stop offset="0%" stop-color="#409eff"/><stop offset="100%" stop-color="#7c5cff"/>
  </linearGradient>
  <clipPath id="ac"><circle cx="100" cy="100" r="100"/></clipPath>
</defs>
<g clip-path="url(#ac)">
  <rect width="200" height="200" fill="url(#ag)"/>
  <circle cx="150" cy="52" r="60" fill="#ffffff" opacity="0.10"/>
  <circle cx="34" cy="164" r="52" fill="#ffffff" opacity="0.08"/>
  <circle cx="100" cy="76" r="34" fill="#ffffff" opacity="0.92"/>
  <path d="M28 200c0-40 32-64 72-64s72 24 72 64z" fill="#ffffff" opacity="0.92"/>
</g>
</svg>'''


def main():
    os.makedirs(OUT, exist_ok=True)
    covers = {
        "lab.svg": lab(), "waf.svg": waf(), "ir.svg": ir(), "soc.svg": soc(),
        "container.svg": container(), "ssh.svg": ssh(), "hugo.svg": hugo(),
    }
    for name, svg in covers.items():
        with open(os.path.join(OUT, name), "w", encoding="utf-8") as f:
            f.write(svg)
        print("generated", name)
    with open(os.path.join(os.path.dirname(OUT), "avatar.svg"), "w", encoding="utf-8") as f:
        f.write(avatar())
    print("generated avatar.svg ->", OUT)


if __name__ == "__main__":
    main()
