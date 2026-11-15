#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 Pages 工程打成可直接 push 的交付 zip（排除缓存 / 临时文件）"""
import os, zipfile, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(ROOT), '行迹_GitHubPages静态版.zip')

SKIP_DIR = {'__pycache__', '.git', '.pytest_cache'}
SKIP_EXT = {'.pyc', '.pyo', '.log', '.tmp'}
# 本机凭据：deploy.py 会读它们，但绝不能打进交付包 / 上传 GitHub
SKIP_NAMES = {'token.txt', 'repo.txt', 'deploy.log'}
# 后台已整页内嵌进工作台单文件，不再有第二个 HTML 需要一起分发
SINGLE = '旅行灵感工作台.html'
files = []
for base, dirs, names in os.walk(ROOT):
    dirs[:] = [d for d in dirs if d not in SKIP_DIR]
    for n in sorted(names):
        p = os.path.join(base, n)
        if n in SKIP_NAMES or os.path.splitext(n)[1] in SKIP_EXT:
            continue
        # 回归测试生成的临时媒体 / 截图（_av_film_*.mp4、_diag_*.png …）不进交付包
        if n.startswith('_') and os.path.splitext(n)[1].lower() in {'.png', '.mp4', '.webm', '.wav', '.log', '.json'}:
            continue
        files.append(p)

files.sort()
# 单文件产物放在工程目录外，避免 Pages 发布多余的大文件，
# 但必须放进交付包：用户只解压 zip 双击这一个文件，工作台与后台都能用。
extras = [os.path.join(os.path.dirname(ROOT), SINGLE)]
with zipfile.ZipFile(OUT, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as z:
    for p in files:
        z.write(p, os.path.relpath(p, ROOT))
    for p in extras:
        if os.path.exists(p):
            z.write(p, os.path.basename(p))

print('打包 %d 文件 → %s (%d KB)' % (len(files) + sum(1 for p in extras if os.path.exists(p)),
                                     OUT, os.path.getsize(OUT) // 1024))
for p in files:
    print('  ', os.path.relpath(p, ROOT), os.path.getsize(p))
