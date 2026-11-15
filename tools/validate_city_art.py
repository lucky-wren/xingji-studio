#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""410 城分镜配图硬闸门：6 类题材 PNG 落盘 / 索引一致 / 构图互异 / 零外链。

用法：python3 tools/validate_city_art.py   （exit 0 通过，exit 1 拦截）
部署前由 .github/workflows/pages.yml 调用。
"""
import hashlib
import json
import pathlib
import re
import struct
import sys
import xml.etree.ElementTree as ET

ROOT = pathlib.Path(__file__).resolve().parent.parent
KINDS = ['cover', 'wear', 'food', 'stay', 'route', 'day']
errs = []


def ck(cond, msg):
    if not cond:
        errs.append(msg)


def png_info(p):
    """不依赖 PIL：读 PNG 签名与 IHDR，返回 (宽, 高)。"""
    b = p.read_bytes()
    if b[:8] != b'\x89PNG\r\n\x1a\n' or len(b) < 33 or b[12:16] != b'IHDR':
        return None
    return struct.unpack('>II', b[16:24])


def main():
    js = ROOT / 'data' / 'city-media.js'
    ck(js.exists(), '缺少 data/city-media.js')
    if not js.exists():
        return
    s = js.read_text(encoding='utf-8')
    ck(not re.search(r'https?://', s), 'city-media.js 含明文外链 URL')
    # 侧栏 410 城缩略图刻意内联 SVG：若改成 410 个 PNG 请求，会抢占分镜图
    # 的加载队列，首帧 XJ.hero 取不到已解码图片就会回落成淡底纹。
    # 因此只准 thumb 用内联 SVG；六类分镜图必须全部落盘 PNG（下方逐条校验）。
    inline_svg = s.count('data:image/svg+xml;base64,')
    ck(inline_svg == 410, '内联 SVG 缩略图不是 410 个（只允许 thumb 使用）：%d' % inline_svg)
    ck('data:image/png;base64,' not in s,
       '工程版索引里混入了单文件专用的内联 PNG（应由构建脚本生成）')

    # 逐行解析每城的 JSON 条目
    entries = {}
    for line in s.splitlines():
        m = re.match(r'\s*"([^"]+)":\s*(\{.*\}),\s*(?:/\*.*\*/)?\s*$', line)
        if m:
            try:
                entries[m.group(1)] = json.loads(m.group(2))
            except Exception as e:
                errs.append('%s 条目 JSON 解析失败：%s' % (m.group(1), e))
    ck(len(entries) == 410, 'city-media 城市数不是 410：%d' % len(entries))

    full = json.loads((ROOT / 'data' / 'cities.full.json').read_text(encoding='utf-8'))
    real_ids = [str(c['id']) for c in full['cities']]
    ck(len(real_ids) == 410, 'cities.full.json 不是 410 城')
    ck(set(entries) == set(real_ids), '图像 id 与城市数据 id 不一致')

    scene_dir = ROOT / 'assets' / 'img' / 'scenes'
    pngs = list(scene_dir.glob('*.png'))
    ck(len(pngs) == 410 * 6, '落盘 PNG 不是 410×6=2460 张：%d' % len(pngs))

    # 索引路径 ↔ 真实文件；六类构图必须互不相同
    checked = 0
    for cid, it in entries.items():
        scn = it.get('scenes') or {}
        for k in KINDS:
            expect = 'assets/img/scenes/%s_%s.png' % (cid, k)
            ck(scn.get(k) == expect, '%s 的 %s 路径不是 %s' % (cid, k, expect))
            ck(not str(scn.get(k) or '').startswith('data:'),
               '%s 的 %s 是内联图，分镜必须落盘 PNG' % (cid, k))
        hs = []
        for k in KINDS:
            rel = scn.get(k) or ''
            f = ROOT / rel
            if not f.exists():
                errs.append('缺文件 ' + rel)
                continue
            info = png_info(f)
            ck(info == (720, 480), '%s 不是 720×480 PNG：%s' % (rel, info))
            hs.append(hashlib.sha256(f.read_bytes()).hexdigest())
            checked += 1
        ck(len(set(hs)) == 6, '%s 的 6 类题材图有重复（构图未区分）' % cid)

    # 清单
    man_path = ROOT / 'data' / 'scene-images.json'
    ck(man_path.exists(), '缺 data/scene-images.json')
    if man_path.exists():
        man = json.loads(man_path.read_text(encoding='utf-8'))
        ck(man.get('total') == 410 and len(man.get('cities', [])) == 410, '清单不是 410 城')
        ck(man.get('kinds') == KINDS, '清单题材种类不对')
        bad = [x['id'] for x in man.get('cities', [])
               if x.get('files') != ['assets/img/scenes/%s_%s.png' % (x['id'], k) for k in KINDS]]
        ck(not bad, '清单里路径不齐的城市：%s' % bad[:5])

    # 410 张 SVG 原图 + 图库仍在，且无外链
    svg_dir = ROOT / 'assets' / 'img' / 'cities'
    svgs = list(svg_dir.glob('*.svg'))
    ck(len(svgs) == 410, 'assets/img/cities 下 SVG 不是 410 个：%d' % len(svgs))
    for f in svgs:
        raw = f.read_text(encoding='utf-8')
        try:
            ET.fromstring(raw)
        except Exception as e:
            errs.append('%s XML 解析失败：%s' % (f.name, e))
        if re.search(r'(?:href|src)\s*=\s*["\']https?:|<image\b|@import|url\(\s*["\']?https?:', raw):
            errs.append('%s 含外部资源引用' % f.name)
    gal = ROOT / 'assets' / 'img' / 'city-gallery.html'
    ck(gal.exists(), '缺 city-gallery.html')
    if gal.exists():
        g = gal.read_text(encoding='utf-8')
        ck(g.count('<figure data-k=') == 410, '图库卡片不是 410 个：%d' % g.count('<figure data-k='))

    print('410 城分镜配图校验：%s' % ('通过' if not errs else '失败 %d 项' % len(errs)))
    print('  城市 %d / 6 类题材 / PNG %d 张 / 已校验 %d 条 / SVG %d 张'
          % (len(entries), len(pngs), checked, len(svgs)))
    for e in errs[:20]:
        print('  ✗', e)
    if len(errs) > 20:
        print('  ... 另有 %d 项' % (len(errs) - 20))
    sys.exit(1 if errs else 0)


if __name__ == '__main__':
    main()
