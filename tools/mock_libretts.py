#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""行迹 · GitHub Pages 版 —— 本地 LibreTTS mock（验证 / 离线自测）

按 LibreSpark/LibreTTS 的官方接口实现，但用本地合成的 WAV 代替微软云端音频：
  GET  /api/tts?t=...&v=...&r=...&p=...&o=mp3
  POST /api/tts  {"text","voice","rate","pitch","format"}
  GET  /api/voices?l=zh&f=1

用途：在没有外网 / 公共实例不可达时，端到端验证「逐句合成 → 真实时长 →
时间轴 → 字幕 → 混音 → 导出」整条链路。产出的音频明确不是真人声。

    python tools/mock_libretts.py --port 8790
"""
import argparse
import json
import math
import struct
import sys
import urllib.parse
import wave
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

SR = 44100
VOICES = [
    ('zh-CN-XiaoxiaoNeural', '晓晓 · 温柔女声（通用）'),
    ('zh-CN-XiaoyiNeural', '晓伊 · 知性女声'),
    ('zh-CN-YunxiNeural', '云希 · 活泼男声'),
    ('zh-CN-YunyangNeural', '云扬 · 播音男声'),
    ('zh-CN-YunjianNeural', '云健 · 厚实男声'),
    ('zh-CN-YunxiaNeural', '云夏 · 自然男声'),
    ('zh-CN-liaoning-XiaobeiNeural', '晓北 · 东北话'),
    ('zh-HK-HiuGaaiNeural', '曉佳 · 粤语'),
    ('zh-TW-HsiaoChenNeural', '曉臻 · 台湾国语'),
]

_wav_cache = {}


def make_wav(text, voice, rate, pitch):
    """确定性合成：不同文本 → 不同时长 / 基频，便于验证 durs[] 真的来自音频。"""
    key = (text, voice, rate, pitch)
    if key in _wav_cache:
        return _wav_cache[key]
    n = max(1, len(text))
    dur = max(0.75, min(9.0, 0.55 + n * 0.155))
    dur *= max(0.5, min(2.0, 1.0 - rate / 200.0))
    frames = int(SR * dur)
    base = 165.0 + (sum(ord(c) for c in voice) % 60) + pitch * 0.35
    # 每个字一个小节：轻微变调 + 共振峰，尾部留 80ms 静音当作句间换气
    seg = frames / max(1, n)
    pcm = bytearray()
    for i in range(frames):
        k = min(n - 1, int(i / seg))
        t = i / SR
        f = base * (1.0 + 0.10 * math.sin(2 * math.pi * 0.7 * t + k * 0.8))
        env = min(1.0, (i % max(1, int(seg))) / (SR * 0.012) + 0.02)
        tail = 1.0 if i < frames - int(SR * 0.08) else 0.0
        v = (0.42 * math.sin(2 * math.pi * f * t)
             + 0.20 * math.sin(2 * math.pi * f * 2 * t)
             + 0.10 * math.sin(2 * math.pi * f * 3 * t)) * env * tail * 0.62
        pcm += struct.pack('<h', int(max(-1.0, min(1.0, v)) * 32767))
    _wav_cache[key] = bytes(pcm)
    return _wav_cache[key]


def wav_bytes(pcm):
    import io
    b = io.BytesIO()
    with wave.open(b, 'wb') as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes(pcm)
    return b.getvalue()


class Handler(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'

    def log_message(self, *a):
        pass

    def _cors(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, X-TTS-Text')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Cache-Control', 'no-store')

    def _send(self, code, ct, data):
        self.send_response(code)
        self._cors()
        self.send_header('Content-Type', ct)
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        try:
            self.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def do_OPTIONS(self):
        self._send(204, 'text/plain', b'')

    def do_GET(self):
        p = urllib.parse.urlsplit(self.path)
        q = dict(urllib.parse.parse_qsl(p.query, keep_blank_values=True))
        if p.path == '/api/voices':
            arr = [{'ShortName': v, 'FriendlyName': n, 'Locale': 'zh-CN'} for v, n in VOICES]
            self._send(200, 'application/json; charset=utf-8',
                       json.dumps(arr, ensure_ascii=False).encode())
            return
        if p.path == '/api/tts':
            text = q.get('t') or q.get('text') or ''
            if not text:
                self._send(400, 'text/plain', b'missing t/text')
                return
            self._tts(text, q.get('v') or q.get('voice') or VOICES[0][0],
                      int(q.get('r') or q.get('rate') or 0),
                      int(q.get('p') or q.get('pitch') or 0))
            return
        self._send(404, 'text/plain', b'not found')

    def do_POST(self):
        p = urllib.parse.urlsplit(self.path)
        n = int(self.headers.get('Content-Length') or 0)
        try:
            j = json.loads(self.rfile.read(n) or b'{}')
        except ValueError:
            j = {}
        if p.path != '/api/tts':
            self._send(404, 'text/plain', b'not found')
            return
        text = j.get('text') or j.get('t') or ''
        if not text:
            self._send(400, 'text/plain', b'missing text')
            return
        self._tts(text, j.get('voice') or j.get('v') or VOICES[0][0],
                  int(j.get('rate') or j.get('r') or 0),
                  int(j.get('pitch') or j.get('p') or 0))

    def _tts(self, text, voice, rate, pitch):
        data = wav_bytes(make_wav(text, voice, rate, pitch))
        # mock 返回 WAV（浏览器 decodeAudioData 可直接解）；真实实例按 o= 返回对应格式
        self._send(200, 'audio/wav', data)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--port', type=int, default=8790)
    ap.add_argument('--host', default='127.0.0.1')
    a = ap.parse_args()
    print('LibreTTS mock 已启动: http://%s:%d  (音频为本地合成占位，非真人声)' % (a.host, a.port))
    srv = ThreadingHTTPServer((a.host, a.port), Handler)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == '__main__':
    sys.exit(main())
