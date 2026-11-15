#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""行迹 · AI 采编本机转发桥

用途：浏览器直连魔塔 / 自定义 OpenAI 兼容端点被 CORS 拦时，在本机跑这个小服务，
后台「连接方式」切到「本机桥」即可。它只做转发，不存 Token、不落盘、不上传任何数据。

    python3 tools/ai_bridge.py            # 默认 127.0.0.1:8791
    python3 tools/ai_bridge.py 9001       # 换端口（同步改 config.js 的 bridge）

转发规则：
    GET  /wiki?name=泉州        → 维基百科 REST 摘要（带 CORS）
    GET  /v1/models             → 转发上游当前可用模型列表（带 CORS）
    POST /v1/chat/completions   → 转发到请求头 X-Target-Base 指定的 /v1，
                                  没给就用魔塔 https://api-inference.modelscope.cn/v1
                                  Authorization 原样透传，本机不保存
"""
import json, sys, urllib.request, urllib.parse, urllib.error
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8791
DEFAULT_BASE = 'https://api-inference.modelscope.cn/v1'
WIKI = 'https://zh.wikipedia.org/w/api.php'


class H(BaseHTTPRequestHandler):
    def _cors(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization, X-Target-Base')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Cache-Control', 'no-store')

    def do_OPTIONS(self):
        self.send_response(204); self._cors(); self.end_headers()

    def _json(self, obj, code=200):
        body = json.dumps(obj, ensure_ascii=False).encode('utf-8')
        self.send_response(code); self._cors()
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers(); self.wfile.write(body)

    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        if u.path.startswith('/v1/models'):
            # OpenAI 兼容模型列表，原样透传 Authorization 与上游响应
            base = (self.headers.get('X-Target-Base') or DEFAULT_BASE).rstrip('/')
            req = urllib.request.Request(base + '/models', method='GET', headers={
                'Authorization': self.headers.get('Authorization') or ''})
            try:
                with urllib.request.urlopen(req, timeout=20) as r:
                    raw = r.read().decode('utf-8')
                self.send_response(200); self._cors()
                self.send_header('Content-Type', 'application/json; charset=utf-8')
                self.send_header('Content-Length', str(len(raw.encode('utf-8'))))
                self.end_headers(); self.wfile.write(raw.encode('utf-8'))
            except urllib.error.HTTPError as e:
                self._json({'error': 'upstream HTTP %s' % e.code,
                            'detail': e.read().decode('utf-8', 'ignore')[:400]}, e.code)
            except Exception as e:
                self._json({'error': str(e)}, 502)
            return
        if not u.path.startswith('/wiki'):
            return self._json({'error': 'only /wiki and /v1/models are supported'}, 404)
        q = urllib.parse.parse_qs(u.query)
        name = (q.get('name') or [''])[0]
        url = WIKI + '?' + urllib.parse.urlencode({
            'action': 'query', 'prop': 'extracts', 'exintro': '1', 'explaintext': '1',
            'format': 'json', 'origin': '*', 'titles': name})
        try:
            with urllib.request.urlopen(url, timeout=10) as r:
                data = json.loads(r.read().decode('utf-8'))
            pages = (data.get('query') or {}).get('pages') or {}
            extract = ''
            for v in pages.values():
                extract = v.get('extract') or ''
                break
            return self._json({'extract': extract, 'source': WIKI})
        except Exception as e:
            return self._json({'extract': '', 'error': str(e)}, 200)

    def do_POST(self):
        if not self.path.startswith('/v1/chat/completions'):
            return self._json({'error': 'unsupported path'}, 404)
        n = int(self.headers.get('Content-Length') or 0)
        body = self.rfile.read(n)
        base = (self.headers.get('X-Target-Base') or DEFAULT_BASE).rstrip('/')
        req = urllib.request.Request(base + '/chat/completions', data=body, method='POST',
                                     headers={'Content-Type': 'application/json',
                                              'Authorization': self.headers.get('Authorization') or ''})
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                raw = r.read().decode('utf-8')
            self.send_response(200); self._cors()
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Content-Length', str(len(raw.encode('utf-8'))))
            self.end_headers(); self.wfile.write(raw.encode('utf-8'))
        except urllib.error.HTTPError as e:
            self._json({'error': 'upstream HTTP %s' % e.code, 'detail': e.read().decode('utf-8', 'ignore')[:400]}, e.code)
        except Exception as e:
            self._json({'error': str(e)}, 502)

    def log_message(self, *a):
        pass


if __name__ == '__main__':
    print('行迹 AI 桥已启动： http://127.0.0.1:%d' % PORT)
    print('  后台把「连接方式」切到「本机桥」，Token 仍由你在页面里填，本机不保存。')
    ThreadingHTTPServer(('127.0.0.1', PORT), H).serve_forever()
