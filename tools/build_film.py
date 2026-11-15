#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""行迹 · GitHub Pages 版 —— 静态成品构建器（只在 GitHub Actions / 本机跑）

输入：media/source/project.json（工作台「↓ 制作包 JSON」导出）
      media/source/frames/0001.png …（可选，工作台「PNG 分镜包」导出）
输出：media/latest/
        broadcast.mp3   完整人声 + 配乐（或纯人声）
        captions.srt    按真实音频时长生成
        film.mp4        H.264 + AAC + mov_text 三轨（有帧图时）
        manifest.json   页面按相对路径读取，刷新不丢
        BUILD_STATUS.json

模型与 daily-news-studio 一致：先逐句得到确定音频 → ffprobe 读 durs[]
→ 同一个 durs[] 同时生成 SRT / 卡片时长 / 音轨位置 → ffmpeg 封装。
网页从头到尾不合成一帧、不念一句话，只播放已编码好的静态文件。

    python tools/build_film.py --endpoint https://libretts.is-an.org
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.parse
import urllib.request
import wave

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, 'media', 'source')
OUT = os.path.join(ROOT, 'media', 'latest')


def log(s):
    print(s, flush=True)


def run(cmd, timeout=600):
    p = subprocess.run(cmd, capture_output=True, timeout=timeout)
    if p.returncode != 0:
        raise RuntimeError('%s\n%s' % (' '.join(cmd[:6]), p.stderr.decode('utf-8', 'ignore')[-600:]))
    return p


def ffprobe_duration(path):
    p = run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
             '-of', 'default=nw=1:nk=1', path])
    return float(p.stdout.decode().strip())


def fetch_tts(endpoint, text, voice, rate, pitch, fmt, dest):
    q = urllib.parse.urlencode({'t': text, 'v': voice, 'r': rate, 'p': pitch, 'o': fmt})
    url = endpoint.rstrip('/') + '/api/tts?' + q
    req = urllib.request.Request(url, headers={'User-Agent': 'xingji-pages-builder/1.0'})
    with urllib.request.urlopen(req, timeout=90) as r:
        data = r.read()
    if len(data) < 800:
        raise RuntimeError('第 %d 句音频过短 (%d B)' % (len(data), len(data)))
    open(dest, 'wb').write(data)
    return dest


def srt_time(t):
    h = int(t // 3600); t -= h * 3600
    m = int(t // 60); t -= m * 60
    s = int(t); ms = int(round((t - s) * 1000))
    if ms == 1000: s += 1; ms = 0
    return '%02d:%02d:%02d,%03d' % (h, m, s, ms)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--endpoint', default=os.environ.get('LIBRETTS_ENDPOINT', 'https://libretts.is-an.org'))
    ap.add_argument('--project', default=os.path.join(SRC, 'project.json'))
    ap.add_argument('--frames', default=os.path.join(SRC, 'frames'))
    ap.add_argument('--skip-tts', action='store_true', help='用 audio/ 里已有的逐句 wav 重建')
    a = ap.parse_args()

    if not os.path.isfile(a.project):
        log('[FATAL] 缺少 %s' % a.project)
        log('        把工作台导出的「制作包 JSON」放到 media/source/project.json')
        return 1
    proj = json.load(open(a.project, encoding='utf-8'))
    scenes = proj.get('scenes') or []
    if not scenes:
        log('[FATAL] 制作包里没有 scenes')
        return 1
    tts = proj.get('tts') or {}
    voice = tts.get('voice') or 'zh-CN-XiaoxiaoNeural'
    rate = tts.get('rate', 0); pitch = tts.get('pitch', 0)
    fmt = tts.get('format') or 'mp3'

    tmp = os.path.join(ROOT, 'media', '_build_tmp')
    shutil.rmtree(tmp, ignore_errors=True)
    os.makedirs(tmp, exist_ok=True)
    audio_dir = os.path.join(tmp, 'audio'); os.makedirs(audio_dir, exist_ok=True)

    log('=== 1/%d 逐句合成（LibreTTS） ===' % 4)
    wavs = []
    for i, sc in enumerate(scenes):
        text = sc.get('text') or ''
        wav = os.path.join(audio_dir, '%04d.wav' % (i + 1))
        if a.skip_tts and os.path.isfile(wav):
            pass
        else:
            raw = os.path.join(audio_dir, '%04d.raw' % (i + 1))
            fetch_tts(a.endpoint, text, voice, rate, pitch, fmt, raw)
            # 统一成 44100 单声道 WAV，后续时长与拼接才确定
            run(['ffmpeg', '-y', '-loglevel', 'error', '-i', raw,
                 '-ar', '44100', '-ac', '1', '-c:a', 'pcm_s16le', wav])
        wavs.append(wav)
        log('  %2d/%d  %s' % (i + 1, len(scenes), text[:28]))

    log('=== 2/4 读取真实时长 durs[] ===')
    durs = [ffprobe_duration(w) for w in wavs]
    total = sum(durs)
    log('  durs = %s' % [round(x, 3) for x in durs])
    log('  合计 %.3fs' % total)

    log('=== 3/4 生成 SRT / 音轨 /（可选）MP4 ===')
    os.makedirs(OUT, exist_ok=True)
    lines, t = [], 0.0
    for i, (sc, d) in enumerate(zip(scenes, durs)):
        lines += [str(i + 1), '%s --> %s' % (srt_time(t), srt_time(t + d)), sc.get('text') or '', '']
        t += d
    open(os.path.join(OUT, 'captions.srt'), 'w', encoding='utf-8').write('\n'.join(lines))

    concat_txt = os.path.join(tmp, 'concat.txt')
    open(concat_txt, 'w', encoding='utf-8').write(''.join("file '%s'\n" % w.replace("'", "'\\''") for w in wavs))
    run(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'concat', '-safe', '0',
         '-i', concat_txt, '-c:a', 'libmp3lame', '-b:a', '192k', os.path.join(OUT, 'broadcast.mp3')])

    frames = []
    if os.path.isdir(a.frames):
        frames = sorted(f for f in os.listdir(a.frames) if f.lower().endswith(('.png', '.jpg', '.jpeg')))
    film = None
    if len(frames) == len(scenes):
        fc = os.path.join(tmp, 'frames.txt')
        with open(fc, 'w', encoding='utf-8') as f:
            for i, (fr, d) in enumerate(zip(frames, durs)):
                f.write("file '%s'\nduration %.4f\n" % (os.path.join(a.frames, fr).replace("'", "'\\''"), d))
            f.write("file '%s'\n" % os.path.join(a.frames, frames[-1]).replace("'", "'\\''"))
        film = os.path.join(OUT, 'film.mp4')
        run(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'concat', '-safe', '0', '-i', fc,
             '-i', os.path.join(OUT, 'broadcast.mp3'),
             '-i', os.path.join(OUT, 'captions.srt'),
             '-map', '0:v:0', '-map', '1:a:0', '-map', '2:s:0',
             '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-r', '24', '-crf', '18',
             '-c:a', 'aac', '-b:a', '192k', '-c:s', 'mov_text',
             '-shortest', '-movflags', '+faststart', film])
        log('  已封装三轨 MP4')
    else:
        log('  （未提供 %d 张帧图，跳过 MP4；页面仍可播放成品 MP3 + SRT）' % len(scenes))

    log('=== 4/4 硬校验 ===')
    checks = {
        'srt_count': len(re.findall(r'^\d+$', open(os.path.join(OUT, 'captions.srt'), encoding='utf-8').read(), re.M)) == len(scenes),
        'durs_positive': all(d > .1 for d in durs),
        'mp3_exists': os.path.getsize(os.path.join(OUT, 'broadcast.mp3')) > 5000,
        'duration_matches': abs(ffprobe_duration(os.path.join(OUT, 'broadcast.mp3')) - total) < 1.5,
        'non_silent': True,
        'film_tracks': True,
        'manifest': True
    }
    if film:
        p = run(['ffprobe', '-v', 'error', '-show_entries', 'stream=codec_type,codec_name',
                 '-of', 'csv=p=0', film])
        kinds = p.stdout.decode().strip().splitlines()
        checks['film_tracks'] = any('h264' in x for x in kinds) and any('aac' in x for x in kinds) and any('subtitle' in x for x in kinds)
        checks['duration_matches'] = checks['duration_matches'] and abs(ffprobe_duration(film) - total) < 1.5
    # 非静音
    p = run(['ffmpeg', '-hide_banner', '-i', os.path.join(OUT, 'broadcast.mp3'),
             '-af', 'volumedetect', '-f', 'null', '-'], timeout=180)
    m = re.search(r'max_volume: ([-\d.]+) dB', p.stderr.decode('utf-8', 'ignore'))
    checks['non_silent'] = bool(m and float(m.group(1)) > -35)

    manifest = {
        'city': (proj.get('city') or {}).get('name', ''),
        'scenes': len(scenes), 'duration': round(total, 3),
        'durs': [round(x, 3) for x in durs],
        'voice': voice, 'endpoint': a.endpoint,
        'provider': 'LibreTTS / Microsoft Edge Neural',
        'mp3': 'broadcast.mp3', 'srt': 'captions.srt',
        'film': 'film.mp4' if film else None,
        'built_at': __import__('datetime').datetime.utcnow().isoformat(timespec='seconds') + 'Z'
    }
    ok = all(checks.values())
    status = {'ok': ok, 'checks': checks, 'duration': round(total, 3),
              'manifest': manifest, 'engine': 'libretts', 'built_at': manifest['built_at']}
    if not ok:
        log('[FATAL] 硬校验未通过：%s' % {k: v for k, v in checks.items() if not v})
        log('        不发布半成品，media/latest/ 保持上一版')
        return 1
    open(os.path.join(OUT, 'manifest.json'), 'w', encoding='utf-8').write(json.dumps(manifest, ensure_ascii=False, indent=2))
    open(os.path.join(OUT, 'BUILD_STATUS.json'), 'w', encoding='utf-8').write(json.dumps(status, ensure_ascii=False, indent=2))
    log('✓ 全部硬校验通过，静态成品已发布到 media/latest/')
    log('  %s 镜 / %.3fs / 音色 %s' % (len(scenes), total, voice))
    shutil.rmtree(tmp, ignore_errors=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
