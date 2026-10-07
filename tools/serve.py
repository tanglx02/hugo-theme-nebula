#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""多线程静态服务器，用于验收测试（支持子目录部署测试）。"""
import functools
import os
import sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

root = sys.argv[1] if len(sys.argv) > 1 else "public"
port = int(sys.argv[2]) if len(sys.argv) > 2 else 8088

handler = functools.partial(SimpleHTTPRequestHandler, directory=os.path.abspath(root))
handler.log_message = lambda *a, **k: None
srv = ThreadingHTTPServer(("127.0.0.1", port), handler)
print(f"serving {os.path.abspath(root)} at http://127.0.0.1:{port}", flush=True)
srv.serve_forever()
