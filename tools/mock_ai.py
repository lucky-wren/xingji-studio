#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""行迹 · AI 采编同协议 mock（只用于回归测试）

沙盒出口对魔塔 / 维基百科不可达，用这个服务按**完全相同的协议**验证全链路：
    GET  /wiki?name=xxx            → {"extract": "..."}
    GET  /v1/models                → 当前可用模型列表（旧模型不在其中）
    POST /v1/chat/completions      → OpenAI 兼容响应，content 是严格 JSON 城市数据
                                     下线模型返回 400 has no provider supported

    python3 tools/mock_ai.py 8792

它不产生真人语音、不联网、不写文件；产物明确标注「mock」。
"""
import json, re, sys, urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8792
# 模拟「旧模型已下线」：Qwen2.5-7B 不再在支持列表里，调用它会返回和用户截图一样的 400
SUPPORTED = ['Qwen/Qwen3-8B', 'Qwen/Qwen3.5-35B-A3B',
             'Qwen/Qwen2.5-Coder-32B-Instruct', 'ZhipuAI/GLM-5.2']
DEPRECATED_MSG = ('{"error":{"message":"Model id : Qwen/Qwen2.5-7B-Instruct, '
                  'has no provider supported","request_id":"mock-400"}}')


def city_json(name, prov):
    spots = [[f'{name} · 实测老街{i+1}', '老城区', '1.5h', '请核对', 'culture|walk',
              f'【通用建议】{name}第{i+1}处步行段，出行前核对开放信息。'] for i in range(12)]
    food = [[f'{name}本地小馆{i+1}', '两道本地做法的家常菜', '老城 / 小馆', '请核对'] for i in range(6)]
    stay = [[f'{name}老城 / 历史街区', '步行可达', '请核对', '首次到访'],
            [f'{name}交通枢纽周边', '抵达省事', '请核对', '换乘'],
            [f'{name}新城 / 商圈', '酒店较新', '请核对', '舒适']]
    return {
        'name': name, 'prov': prov, 'region': '华东', 'en': name + ' · ' + prov,
        'emoji': '🏙', 'tag': f'{name} · 慢旅行', 'seasons': '4–5 月 / 9–10 月',
        'days': '3 – 4 天', 'climate': '亚热带季风气候，春秋最宜',
        'climateZone': 'south', 'climateZoneLabel': '江南 / 华南 · 湿热多雨',
        'budget': [180, 320, 620], 'center': [24.8, 118.6],
        'intro': f'把{name}排成 3 天，不赶路；本条由 mock 模型生成，票价需核对。',
        'tags': [name, '慢旅行', 'AI 采编'], 'spots': spots, 'food': food, 'stay': stay,
        'transport': [f'🚄 抵达：{name}站 / 高铁站，班次出行前核对',
                      '🚗 市内以步行 + 打车为主', '🕐 热门馆常需预约',
                      '☀️ 门票与营业状态请按「灵感来源」页核对'],
        'level': 'prefecture', 'tier': 'index',
        'source': 'mock 检索摘要 + mock 模型', 'note': '通用建议框架，不编造真实票价'
    }


class H(BaseHTTPRequestHandler):
    def _cors(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization, X-Target-Base')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Cache-Control', 'no-store')

    def do_OPTIONS(self):
        self.send_response(204); self._cors(); self.end_headers()

    def _json(self, obj, code=200):
        raw = json.dumps(obj, ensure_ascii=False).encode('utf-8')
        self.send_response(code); self._cors()
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(raw)))
        self.end_headers(); self.wfile.write(raw)

    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        q = urllib.parse.parse_qs(u.query)
        name = (q.get('name') or q.get('titles') or ['测试城'])[0]
        if u.path.startswith('/wiki') or u.path.startswith('/w/api.php'):
            return self._json({'extract': f'{name}位于中国，是一座具有地方特色的城市，'
                                          '老城街区、滨水步道与本地市集适合慢旅行。（mock 公开摘要，非真实条目）',
                               'source': 'mock-wiki'})
        if u.path.startswith('/v1/models'):
            if self.headers.get('Authorization') == 'Bearer MOCK_401':
                return self._json({'error': 'invalid token'}, 401)
            if self.headers.get('Authorization') == 'Bearer MOCK_MODELS_404':
                return self._json({'error': 'models endpoint not implemented'}, 404)
            return self._json({'object': 'list',
                               'data': [{'id': x, 'object': 'model', 'owned_by': 'mock'} for x in SUPPORTED]})
        return self._json({'error': 'unsupported'}, 404)

    def do_POST(self):
        n = int(self.headers.get('Content-Length') or 0)
        body = self.rfile.read(n).decode('utf-8', 'ignore')
        # 故意模拟 CORS 失败：Token 写成 MOCK_401 时返回 401
        if self.headers.get('Authorization') == 'Bearer MOCK_401':
            return self._json({'error': 'invalid token'}, 401)
        # ① 连接测试的最小推理
        if '只回复两个字' in body:
            try:
                model = (json.loads(body).get('model') or '')
            except Exception:
                model = ''
            if model not in SUPPORTED:
                return self._json(json.loads(DEPRECATED_MSG), 400)
            return self._json({'id': 'chatcmpl-ping', 'object': 'chat.completion',
                               'model': model, 'choices': [{
                                   'index': 0, 'message': {'role': 'assistant', 'content': '可用'},
                                   'finish_reason': 'stop'}]})
        # ② 旧模型 ID → 复现用户截图里的真实 400
        try:
            req_model = (json.loads(body).get('model') or '')
        except Exception:
            req_model = ''
        if req_model and req_model not in SUPPORTED:
            self.send_response(400); self._cors()
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            raw = DEPRECATED_MSG.encode('utf-8')
            self.send_header('Content-Length', str(len(raw)))
            self.end_headers(); self.wfile.write(raw)
            return
        # ③ 正常生成
        m = re.search(r'请为「([^」]+)（([^）]+)）」', body)
        name, prov = (m.group(1), m.group(2)) if m else ('测试城', '浙江')
        content = json.dumps(city_json(name, prov), ensure_ascii=False)
        return self._json({
            'id': 'chatcmpl-mock', 'object': 'chat.completion', 'created': 0,
            'model': req_model or 'mock-qwen', 'choices': [{
                'index': 0, 'message': {'role': 'assistant', 'content': '```json\n' + content + '\n```'},
                'finish_reason': 'stop'}],
            'usage': {'prompt_tokens': 0, 'completion_tokens': 0, 'total_tokens': 0}
        })

    def log_message(self, *a):
        pass


if __name__ == '__main__':
    print('行迹 AI mock 已启动： http://127.0.0.1:%d （仅测试用，不联网）' % PORT)
    ThreadingHTTPServer(('127.0.0.1', PORT), H).serve_forever()
