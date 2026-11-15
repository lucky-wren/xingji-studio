#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成 data/city-media.js —— 410 城 × 6 类分镜配图的索引。

与旧版的区别（重要）：
  · 旧版把 5 类图全部内联成 data URI，且五类共用同一套「日轮＋山脊＋水面」
    构图，只挪机位、盖淡色，肉眼看着就是一层底纹，等于没有配图。
  · 新版每城 6 类题材（cover / wear / food / stay / route / day）是六张
    构图完全不同的 PNG，落盘在 assets/img/scenes/，页面按相对路径读取，
    打开文件夹就能看见一张张图；按分镜栏目自动取，无需逐镜手动配置。
  · 这些是本地绘制的插画，不是真实照片。后台详情里填自备授权图片路径
    即可覆盖对应类别，清空则回落到内置图。

用法：python3 tools/gen_city_media.py
也可被 tools/gen_city_art.py 在生成 SVG / 图库后直接调用 build()。
"""
import json
import base64
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / 'data' / 'cities.full.json'
OUT_JS = ROOT / 'data' / 'city-media.js'
SCENE_DIR = ROOT / 'assets' / 'img' / 'scenes'
SVG_DIR = ROOT / 'assets' / 'img' / 'cities'

KINDS = ['cover', 'wear', 'food', 'stay', 'route', 'day']
KIND_CN = {'cover': '城市地标', 'wear': '街巷', 'food': '菜品',
           'stay': '院落', 'route': '路桥', 'day': '逐日动线'}
# 分镜栏目 → 题材，见 scene-art.js 的 XJ.sceneKind
SCENE_KIND = {
    'cover': '封面 / 总览', 'line': '线路总览', 'leg': '城际段', 'city': '城市',
    'overview': '行程速览', 'needs0': '衣 · 分季穿搭', 'needs1': '食 · 必吃榜',
    'needs2': '住 · 区域建议', 'needs3': '行 · 交通指南',
    'day': '逐日路线', 'map': '游玩地图', 'sources': '灵感来源', 'ending': '片尾',
}


def build():
    doc = json.loads(SRC.read_text(encoding='utf-8'))
    cities = doc['cities']
    if len(cities) != 410:
        raise SystemExit('期望 410 城，实际 %d' % len(cities))
    missing = []
    lines = [
        '/* 行迹 · 410 城分镜配图索引 —— 由 tools/gen_city_media.py 生成，不要手工编辑',
        '   ------------------------------------------------------------------',
        '   每城 6 类题材图，落盘在 assets/img/scenes/<id>_<kind>.png：',
        '     cover 城市地标 / wear 街巷 / food 菜品 / stay 院落 / route 路桥 / day 逐日动线',
        '   六类构图完全不同、不透明，按分镜栏目自动取用，无需逐镜手动配图。',
        '   这些是本地绘制的插画，不是真实照片；图上只写城市名 / 省份等公开事实。',
        '   替换真实照片：后台「详情 → 图像」填自备授权图片相对路径，或改本文件对应字段。',
        '   单文件预览版由 tools/make_single.py 把这些路径自动换成内联 data URI。',
        '   ------------------------------------------------------------------ */',
        'window.XJ_CITY_MEDIA = {',
        '  version: 3,',
        '  generated: true,',
        '  total: 410,',
        '  kinds: %s,' % json.dumps(KINDS),
        '  sceneKind: %s,' % json.dumps(SCENE_KIND, ensure_ascii=False),
        '  note: "410 城 × 6 类题材插画（非照片）。分镜按栏目自动取图，可后台替换。",',
        '  cities: {',
    ]
    for c in cities:
        cid = str(c['id'])
        name = str(c.get('name') or '')
        s = {k: 'assets/img/scenes/%s_%s.png' % (cid, k) for k in KINDS}
        for k in KINDS:
            if not (SCENE_DIR / ('%s_%s.png' % (cid, k))).exists():
                missing.append((cid, k))
        # 侧栏 410 城缩略图：内联 SVG，零网络请求。
        # 若这里用 scenes PNG 路径，renderDestList 会一次性发 410 个请求，
        # 把当前城市 6 类分镜图挤到 HTTP 队列末尾，首帧 hasImage=false，
        # XJ.hero 直接 return —— 画面就只剩一层淡底纹，等于没配图。
        svg_path = SVG_DIR / ('%s.svg' % cid)
        thumb = ('data:image/svg+xml;base64,' +
                 base64.b64encode(svg_path.read_bytes()).decode('ascii')) if svg_path.exists() else s['cover']
        items = {
            'cover': s['cover'],
            'thumb': thumb,
            'spots': [s['cover'], s['day']],
            'food': [s['food']],
            'stay': [s['stay']],
            'scenes': s,
            'credit': '行迹内置题材插画（非照片）· 可在后台替换为自备授权图片',
            'file': 'assets/img/cities/%s.svg' % cid,
        }
        lines.append('    %s: %s,  /* %s */'
                     % (json.dumps(cid, ensure_ascii=False),
                        json.dumps(items, ensure_ascii=False, separators=(',', ':')), name))
    lines += ['  }', '};', '']
    if missing:
        raise SystemExit('缺少 %d 张 PNG，先跑 tools/gen_scene_png.py：%s' % (len(missing), missing[:6]))
    OUT_JS.write_text('\n'.join(lines), encoding='utf-8')
    print('生成 %s (%d 字节)，%d 城 × %d 题材 = %d 张 PNG 索引'
          % (OUT_JS.name, OUT_JS.stat().st_size, len(cities), len(KINDS), len(cities) * len(KINDS)))
    return OUT_JS


if __name__ == '__main__':
    build()
