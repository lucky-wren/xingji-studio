#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""行迹 · GitHub Pages 版 —— 本机 LibreTTS 转发桥（解决 CORS）

用途：GitHub Pages 是 https 静态站，公共 LibreTTS 实例若没给
`Access-Control-Allow-Origin`，浏览器 fetch 会被拦。这个小脚本在你本机
跑一个带 CORS 头的转发，页面「接口地址」填 http://127.0.0.1:8790 即可。

    python tools/bridge.py
    python tools/bridge.py --port 8790 --upstream https://libretts.is-an.org

纯 Python 标准库，零依赖。localhost 属于可信来源，https 页面也能请求它。
只做转发，不存文案、不落盘、不记录日志内容。
"""
import argparse
import json
import os
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

UPSTREAM = 'https://libretts.is-an.org'
CERT = os.environ.get('SSL_CERT_FILE') or os.environ.get('REQUESTS_CA_BUNDLE')


def ssl_ctx():
    try:
        return ssl.create_default_context(cafile=CERT) if CERT else ssl.create_default_context()
    except Exception:
        return ssl.create_default_context()


class Handler(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'

    def log_message(self, fmt, *args):
        # 不打印 URL（里面可能有文案），只打印方法和状态码
        sys.stderr.write('  %s %s\n' % (self.command, args[1] if len(args) > 1 else ''))

    def _cors(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, X-TTS-Text')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Max-Age', '86400')
        self.send_header('Cache-Control', 'no-store')

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.send_header('Content-Length', '0')
        self.end_headers()

    def _proxy(self, method):
        p = urllib.parse.urlsplit(self.path)
        if not p.path.startswith('/api/'):
            self.send_error(404, 'only /api/* is proxied')
            return
        target = UPSTREAM.rstrip('/') + p.path + (('?' + p.query) if p.query else '')
        body = None
        headers = {'User-Agent': 'xingji-pages-bridge/1.0', 'Accept': '*/*'}
        if method == 'POST':
            n = int(self.headers.get('Content-Length') or 0)
            body = self.rfile.read(n) if n else b'{}'
            headers['Content-Type'] = self.headers.get('Content-Type', 'application/json')
        # 上游若要求鉴权，可在这里透传（默认公共实例免密钥）
        if self.headers.get('X-TTS-Text'):
            headers['X-TTS-Text'] = self.headers.get('X-TTS-Text')
        req = urllib.request.Request(target, data=body, headers=headers, method=method)
        try:
            r = urllib.request.urlopen(req, timeout=90, context=ssl_ctx())
            data = r.read()
            ct = r.headers.get('Content-Type', 'application/octet-stream')
            code = r.status
        except urllib.error.HTTPError as e:
            data, ct, code = e.read(), e.headers.get('Content-Type', 'text/plain'), e.code
        except Exception as e:
            data = json.dumps({'error': str(e)[:200]}).encode()
            ct, code = 'application/json', 502
        self.send_response(code)
        self._cors()
        self.send_header('Content-Type', ct)
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        try:
            self.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def do_GET(self):
        self._proxy('GET')

    def do_POST(self):
        self._proxy('POST')


def main():
    global UPSTREAM
    ap = argparse.ArgumentParser()
    ap.add_argument('--port', type=int, default=8790)
    ap.add_argument('--upstream', default=UPSTREAM)
    ap.add_argument('--host', default='127.0.0.1')
    a = ap.parse_args()
    UPSTREAM = a.upstream
    print('=' * 62)
    print('  行迹 · LibreTTS 本机转发桥')
    print('  上游 : %s' % UPSTREAM)
    print('  地址 : http://%s:%d' % (a.host, a.port))
    print('  页面「接口地址」填上面这个地址；Ctrl+C 停止')
    print('  只转发、不存文案；不打印 URL 内容')
    print('=' * 62)
    srv = ThreadingHTTPServer((a.host, a.port), Handler)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print('\n已停止')
    return 0


if __name__ == '__main__':
    sys.exit(main())
