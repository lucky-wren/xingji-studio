#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""行迹 · 城市画面绘制（可辨识版）

每城 5 类图都是一张有主体、有明暗层次的城市风光插画：
天空 / 日轮 / 云 / 多层山脊 / 水面倒影 / 地标建筑群 / 前景 / 城名牌。
不是低对比几何底纹，也不是真实照片；图上只写城市名等公开事实。

由 tools/gen_city_art.py 调用，输出仍为内联 data URI + 本地 SVG 文件。
"""
import hashlib
import html
import math
import re

FONT = "'WenQuanYi Micro Hei','PingFang SC','Microsoft YaHei',sans-serif"


def esc(s):
    return html.escape(str(s or ''), quote=True)


def seed_of(s):
    return int(hashlib.sha256(str(s).encode('utf-8')).hexdigest()[:8], 16)


def mix(hex_color, k):
    """k>0 向白提亮，k<0 向黑压暗，返回不透明 #rrggbb。"""
    m = re.match(r'#([0-9a-fA-F]{6})', str(hex_color or ''))
    if not m:
        return '#3f6f63'
    r, g, b = (int(m.group(1)[i:i + 2], 16) for i in (0, 2, 4))
    f = (lambda v: int(v + (255 - v) * k)) if k > 0 else (lambda v: int(v * (1 + k)))
    return '#%02x%02x%02x' % (max(0, min(255, f(r))), max(0, min(255, f(g))), max(0, min(255, f(b))))


def palette(city):
    g = city.get('g') or ['#3f6f63', '#8fb6a4']
    c1, c2 = (g + ['#8fb6a4'])[:2]
    return {
        'sky1': mix(c1, .58),
        'sky2': mix(c2, .30),
        'sky3': '#f9e9c8',
        'far': mix(c1, -.16),
        'mid': mix(c1, -.36),
        'near': mix(c1, -.55),
        'ink': mix(c1, -.70),
        'water': mix(c2, -.30),
        'gold': '#e9b962',
        'white': '#fffdf8',
        'c1': c1,
        'c2': c2,
    }


def motif_for(city, s):
    region = str(city.get('region') or '')
    prof = str(city.get('profile') or '')
    name = region + prof + str(city.get('prov') or city.get('province') or '')
    if re.search(r'东北|黑龙江|吉林|辽宁', region):
        return 'pine'
    if re.search(r'西北|新疆|甘肃|青海|宁夏|内蒙古', name) or 'northwest' in prof:
        return 'desert' if s % 2 else 'terrace'
    if re.search(r'西藏|高原|plateau', name + prof):
        return 'mountain'
    if re.search(r'海南|热带|tropical|广西|广东|福建|浙江|江苏|山东|辽宁|沿海|coastal', name + prof):
        return 'wave' if s % 3 else 'palm'
    if re.search(r'西南|云南|贵州|四川|重庆', region):
        return 'terrace' if s % 2 else 'mountain'
    if re.search(r'江南|华中|安徽|江西|湖北|湖南|south', name + prof):
        return 'bridge' if s % 2 else 'roof'
    return ['mountain', 'roof', 'bridge', 'terrace', 'wave'][s % 5]


def rnd_gen(s):
    r = [s & 0x7fffffff]

    def nxt():
        r[0] = (r[0] * 1103515245 + 12345) & 0x7fffffff
        return (r[0] % 10000) / 10000

    return nxt


def ridge(w, h, base, amp, fill, nxt, n=8):
    pts = ['M0 %.1f' % (h * base)]
    for i in range(n + 1):
        pts.append('L%.1f %.1f' % (w * i / n, h * (base + (nxt() - .5) * amp)))
    pts.append('L%.1f %.1f L0 %.1fZ' % (w, h, h))
    return '<path d="%s" fill="%s"/>' % (' '.join(pts), fill)


def building(w, h, x, y, sc, style, p, nxt):
    """一组可辨识的地标剪影：城楼 / 塔 / 民居 / 圆顶 / 木屋。"""
    o = []
    ink, mid, gold, white = p['ink'], p['mid'], p['gold'], p['white']
    bw = 70 * sc
    bh = 78 * sc
    if style in ('roof', 'bridge', 'terrace'):
        # 两层飞檐城楼
        o.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" fill="%s"/>'
                 % (x - bw / 2, y - bh * .55, bw, bh * .55, mid))
        for lv in range(2):
            ey = y - bh * (.55 + lv * .52)
            o.append('<path d="M%.1f %.1f Q%.1f %.1f %.1f %.1f L%.1f %.1f L%.1f %.1fZ" fill="%s"/>'
                     % (x - bw * .78, ey, x, ey - bh * .28, x + bw * .78, ey,
                        x + bw * .62, ey + 7 * sc, x - bw * .62, ey + 7 * sc, ink))
        for cx in (-.24, 0, .24):
            o.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" fill="%s" opacity=".92"/>'
                     % (x + bw * cx - 4 * sc, y - bh * .40, 8 * sc, 12 * sc, gold))
        if style == 'bridge':
            o.append('<path d="M%.1f %.1f Q%.1f %.1f %.1f %.1f" stroke="%s" stroke-width="%.1f" fill="none" opacity=".9"/>'
                     % (x - bw * 2.4, y + bh * .06, x, y - bh * .34, x + bw * 2.4, y + bh * .06,
                        white, 7 * sc))
    elif style == 'mountain':
        # 多层塔
        for lv in range(5):
            ww = (bw * (1 - lv * .13))
            yy = y - bh * (.2 + lv * .20)
            o.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" fill="%s"/>'
                     % (x - ww / 2, yy, ww, bh * .19, mid if lv % 2 else ink))
            o.append('<path d="M%.1f %.1f Q%.1f %.1f %.1f %.1f L%.1f %.1fZ" fill="%s"/>'
                     % (x - ww * .72, yy, x, yy - 9 * sc, x + ww * .72, yy, x + ww * .55, yy + 3 * sc, ink))
        o.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" fill="%s"/>'
                 % (x - 2 * sc, y - bh * 1.28, 4 * sc, 14 * sc, gold))
    elif style == 'pine':
        # 木屋 + 松树
        o.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" fill="%s"/>'
                 % (x - bw * .6, y - bh * .42, bw * 1.2, bh * .42, mid))
        o.append('<path d="M%.1f %.1f L%.1f %.1f L%.1f %.1fZ" fill="%s"/>'
                 % (x - bw * .78, y - bh * .42, x, y - bh * .82, x + bw * .78, y - bh * .42, ink))
        o.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" fill="%s"/>'
                 % (x - bw * .12, y - bh * .28, bw * .24, bh * .14, gold))
        for t in (-1.5, 1.6):
            tx = x + bw * t
            for q in range(3):
                ty = y - bh * (.10 + q * .20)
                o.append('<path d="M%.1f %.1f L%.1f %.1f L%.1f %.1fZ" fill="%s"/>'
                         % (tx, ty - bh * .38, tx - 15 * sc, ty, tx + 15 * sc, ty, ink))
    elif style == 'desert':
        # 圆顶建筑 + 尖塔
        o.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" fill="%s"/>'
                 % (x - bw * .7, y - bh * .34, bw * 1.4, bh * .34, mid))
        o.append('<path d="M%.1f %.1f Q%.1f %.1f %.1f %.1fZ" fill="%s"/>'
                 % (x - bw * .72, y - bh * .34, x, y - bh * .82, x + bw * .72, y - bh * .34, ink))
        o.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" fill="%s"/>'
                 % (x - 3 * sc, y - bh * 1.00, 6 * sc, bh * .20, gold))
        o.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" fill="%s"/>'
                 % (x - bw * .12, y - bh * .22, bw * .24, bh * .22, gold))
    else:  # wave / palm：帆船 + 岸屋
        o.append('<path d="M%.1f %.1f L%.1f %.1f L%.1f %.1fZ" fill="%s"/>'
                 % (x - bw * .9, y, x + bw * .9, y, x, y - bh * .18, ink))
        o.append('<path d="M%.1f %.1f L%.1f %.1f L%.1f %.1fZ" fill="%s" opacity=".92"/>'
                 % (x - 2 * sc, y - bh * .16, x - bw * .62, y - bh * .02, x - 2 * sc, y - bh * .02, white))
        o.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" fill="%s"/>'
                 % (x - bw * 1.5, y - bh * .42, bw * .62, bh * .42, mid))
        o.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" fill="%s"/>'
                 % (x + bw * .95, y - bh * .34, bw * .55, bh * .34, mid))
        for wx in (-1.35, 1.10):
            o.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" fill="%s"/>'
                     % (x + bw * wx, y - bh * .28, 9 * sc, 10 * sc, gold))
    return ''.join(o)


def scene_svg(city, kind, idx, total):
    cid = str(city.get('id') or '')
    name = str(city.get('name') or '行迹')
    prov = str(city.get('prov') or city.get('province') or '')
    region = str(city.get('region') or '')
    s = seed_of(cid + '|' + name)
    motif = motif_for(city, s)
    p = palette(city)
    big = kind == 'cover'
    thumb = kind == 'thumb'
    w, h = (1280, 720) if big else ((96, 54) if thumb else (640, 480))
    nxt = rnd_gen(s + {'cover': 3, 'thumb': 17, 'spot': 31, 'food': 59, 'stay': 83}.get(kind, 0))
    uid = 'a%d' % (s % 100000)

    o = ['<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" viewBox="0 0 %d %d">'
         % (w, h, w, h)]
    o.append('<title>%s</title>' % esc(name + ((' · ' + prov) if prov and prov != name else '')
                                     + ((' · ' + region) if region else '')))
    o.append('<defs>'
             '<linearGradient id="sky%s" x1="0" y1="0" x2="0" y2="1">'
             '<stop offset="0" stop-color="%s"/><stop offset=".58" stop-color="%s"/>'
             '<stop offset="1" stop-color="%s"/></linearGradient>'
             '<radialGradient id="sun%s"><stop offset="0" stop-color="#fff6d8" stop-opacity=".95"/>'
             '<stop offset="1" stop-color="#fff6d8" stop-opacity="0"/></radialGradient>'
             '<linearGradient id="wat%s" x1="0" y1="0" x2="0" y2="1">'
             '<stop offset="0" stop-color="%s"/><stop offset="1" stop-color="%s"/></linearGradient>'
             '</defs>' % (uid, p['sky1'], p['sky2'], p['sky3'],
                          uid, uid, p['sky2'], p['water']))
    # 天空
    o.append('<rect width="%d" height="%.1f" fill="url(#sky%s)"/>' % (w, h * .74, uid))
    # 日轮 + 光晕
    sx, sy = w * (.62 + nxt() * .22), h * (.15 + nxt() * .12)
    sr = min(w, h) * (.075 + nxt() * .035)
    o.append('<circle cx="%.1f" cy="%.1f" r="%.1f" fill="url(#sun%s)"/>' % (sx, sy, sr * 2.5, uid))
    o.append('<circle cx="%.1f" cy="%.1f" r="%.1f" fill="#fff5d4" opacity=".95"/>'
             % (sx, sy, sr))
    # 云
    for q in range(3):
        cx = w * (.08 + q * .31 + nxt() * .08)
        cy = h * (.12 + nxt() * .20)
        cw = w * (.09 + nxt() * .06)
        o.append('<ellipse cx="%.1f" cy="%.1f" rx="%.1f" ry="%.1f" fill="#ffffff" opacity=".42"/>'
                 % (cx, cy, cw, h * .018))
        o.append('<ellipse cx="%.1f" cy="%.1f" rx="%.1f" ry="%.1f" fill="#ffffff" opacity=".32"/>'
                 % (cx + cw * .35, cy - h * .012, cw * .65, h * .014))
    # 远山三层（不透明实色，层次清晰）
    o.append(ridge(w, h, .46, .10, p['far'], nxt))
    o.append(ridge(w, h, .57, .085, p['mid'], nxt))
    o.append(ridge(w, h, .68, .06, p['near'], nxt))
    # 水面 / 地面
    o.append('<rect y="%.1f" width="%d" height="%.1f" fill="url(#wat%s)"/>'
             % (h * .72, w, h * .28, uid))
    for q in range(6):
        yy = h * (.755 + q * .038)
        o.append('<path d="M%.1f %.1f Q%.1f %.1f %.1f %.1f" stroke="#ffffff" stroke-width="%.1f" '
                 'fill="none" opacity=".30"/>'
                 % (w * .03, yy, w * .5, yy - h * .012, w * .97, yy, max(1, h * .004)))
    # 主体建筑群：按栏目取不同机位，每城种子不同
    if not thumb:
        off = {'cover': 0, 'spot': 1, 'food': 2, 'stay': 3}.get(kind, 0)
        bx = w * (.60 + (off % 3) * .06 + nxt() * .04)
        by = h * (.72 + (off % 2) * .015)
        sc = (w / 640) * (1.05 + nxt() * .18)
        o.append(building(w, h, bx, by, sc, motif, p, nxt))
        # 次景：左侧小屋舍 / 树影，形成完整画面构图
        o.append(building(w, h, w * (.19 + nxt() * .05), h * .735, sc * .62, motif, p, nxt))
    else:
        o.append(building(w, h, w * .68, h * .74, .42, motif, p, nxt))
    # 类别色调：街市暖光 / 客栈夜色，只淡淡一层，不掩盖画面
    if kind == 'food':
        o.append('<rect width="%d" height="%d" fill="#e9a94f" opacity=".13"/>' % (w, h))
    elif kind == 'stay':
        o.append('<rect width="%d" height="%d" fill="#4a76a8" opacity=".10"/>' % (w, h))
    # 前景暗角（只压底部，让图有纵深，不盖主体）
    o.append('<rect y="%.1f" width="%d" height="%.1f" fill="%s" opacity=".16"/>'
             % (h * .88, w, h * .12, p['ink']))
    # 城名牌：白底 + 深色字，肉眼明确可辨
    if not thumb:
        lw = min(w * .30, 210 * (w / 640))
        lh = h * .060
        lx, ly = w * .045, h * (.74 if big else .72)
        o.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" rx="%.1f" fill="#fffdf8" opacity=".96"/>'
                 % (lx, ly, lw, lh, h * .010))
        o.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" fill="%s"/>'
                 % (lx, ly, max(2, w * .004), lh, p['gold']))
        o.append('<text x="%.1f" y="%.1f" font-family="%s" font-size="%.1f" font-weight="700" '
                 'fill="#20342b">%s</text>'
                 % (lx + w * .016, ly + lh * .70, FONT, h * .036, esc(name)))
        o.append('<text x="%.1f" y="%.1f" font-family="%s" font-size="%.1f" fill="#6b7a70">%s</text>'
                 % (lx + w * .016 + min(lw * .52, 110 * (w / 640)), ly + lh * .68,
                    FONT, h * .019, esc(prov or region)))
        o.append('<text x="%.1f" y="%.1f" text-anchor="end" font-family="%s" font-size="%.1f" '
                 'fill="#ffffff" opacity=".85">XINGJI / No.%03d</text>'
                 % (w * .965, h * .945, FONT, h * .030, idx))
    else:
        o.append('<rect width="%d" height="%d" fill="%s" opacity=".14"/>' % (w, h, p['ink']))
    o.append('</svg>')
    return ''.join(o)
