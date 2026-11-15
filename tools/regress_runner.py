#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""行迹 · 串行回归 runner：进程内起静态服务 + mock，逐套跑 node 测试。

不依赖后台任务、不占 shell fd；一条命令跑完并汇总。
用法：python3 tools/regress_runner.py [测试脚本名 ...]
     不传参数则跑 DEFAULT 列表。
"""
import functools
import http.server
import os
import pathlib
import re
import socket
import subprocess
import sys
import threading
import time

ROOT = pathlib.Path(__file__).resolve().parent.parent
BASE = 'http://127.0.0.1:8803'
SHOTS = pathlib.Path('/data/workspace/_regress_shots')
SHOTS.mkdir(exist_ok=True)

DEFAULT = [
    'smoke_v2.mjs', 'smoke_plan.mjs', 'smoke_admin.mjs', 'smoke_entry.mjs',
    'smoke_locate.mjs', 'smoke_typewriter.mjs', 'smoke_av.mjs',
    'smoke_art.mjs', 'smoke_city_art.mjs', 'smoke_admin_art.mjs',
    'smoke_scene_art.mjs', 'smoke_visual.mjs', 'smoke_speed.mjs',
    'smoke_four.mjs', 'e2e.mjs', 'smoke_ai.mjs', 'smoke_ai_fallback.mjs',
]


def port_ready(port, timeout=8):
    end = time.time() + timeout
    while time.time() < end:
        try:
            with socket.create_connection(('127.0.0.1', port), .2):
                return True
        except OSError:
            time.sleep(.15)
    return False


def main(argv):
    tests = argv or DEFAULT
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(ROOT))
    srv = http.server.ThreadingHTTPServer(('127.0.0.1', 8803), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    procs = []
    for cmd in (['python3', 'tools/mock_libretts.py', '--port', '8790'],
                ['python3', 'tools/mock_ai.py', '8792']):
        procs.append(subprocess.Popen(cmd, cwd=str(ROOT),
                                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
    for pno in (8803, 8790, 8792):
        if not port_ready(pno):
            print('服务未就绪：', pno)
    time.sleep(.4)

    env = dict(os.environ)
    env.update({'BASE_URL': BASE, 'ROOT': str(ROOT), 'SHOT_DIR': str(SHOTS)})
    summary = []
    for name in tests:
        t0 = time.time()
        try:
            r = subprocess.run(['node', 'tests/' + name], cwd=str(ROOT), env=env,
                               capture_output=True, text=True, timeout=240)
            out = (r.stdout or '') + (r.stderr or '')
        except subprocess.TimeoutExpired:
            out, r = '[TIMEOUT 240s]', None
        lines = out.strip().splitlines()
        res = next((l for l in lines if '结果：' in l or re.search(r'\b\d+/\d+\b.*(通过|PASS)', l)), '')
        fails = [l for l in lines if re.search(r'\bFAIL\b|✗|AssertionError', l)]
        rc = r.returncode if r is not None else 124
        summary.append((name, rc, res, fails[:6], round(time.time() - t0, 1)))
        print('\n== %s  rc=%d  %ss ==' % (name, rc, round(time.time() - t0, 1)))
        if res:
            print('  ', res.strip())
        for l in fails[:6]:
            print('   ', l.strip()[:200])
        if rc != 0 and not fails:
            print('   (末尾输出)', ' | '.join(lines[-4:])[:400])

    print('\n================ 汇总 ================')
    ok = sum(1 for s in summary if s[1] == 0)
    for name, rc, res, _, sec in summary:
        print('  %s  %-28s %s' % ('PASS' if rc == 0 else 'FAIL', name, res.strip()[:70]))
    print('  %d/%d 套通过' % (ok, len(summary)))
    srv.shutdown()
    for p in procs:
        p.terminate()
    return 0 if ok == len(summary) else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
