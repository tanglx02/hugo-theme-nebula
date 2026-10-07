#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把主题源码中的文本文件行尾统一为 LF（避免 CRLF 混入仓库）。

用法：python tools/normalize_eol.py <目录...>
"""
import os
import sys

EXTS = (".yaml", ".yml", ".html", ".toml", ".json", ".xml", ".txt", ".css", ".js", ".md")
SKIP_DIRS = {".git", "node_modules", "public", "public-shard", "resources", "tmp"}


def main():
    roots = sys.argv[1:]
    if not roots:
        print("用法: python tools/normalize_eol.py <目录...>")
        return 1
    changed = 0
    for root in roots:
        for dirpath, dirnames, files in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
            for f in files:
                if not f.endswith(EXTS):
                    continue
                p = os.path.join(dirpath, f)
                with open(p, "rb") as fh:
                    data = fh.read()
                if b"\r\n" not in data:
                    continue
                with open(p, "wb") as fh:
                    fh.write(data.replace(b"\r\n", b"\n"))
                changed += 1
    print(f"已统一行尾为 LF: {changed} 个文件")
    return 0


if __name__ == "__main__":
    sys.exit(main())
