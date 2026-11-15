#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""行迹 · 410 城专属图像生成器（初版）

产物：
  1) data/city-media.js        —— 410 城 × 5 类图，全部内联为 data URI。
                                  页面 / 成片 / 单文件版零网络请求即可显示。
  2) assets/img/cities/*.svg —— 每城一张 cover 的真实图片文件，可查看 / 替换。
  3) assets/img/city-gallery.html —— 410 城图库，双击可看全部、逐城下载 SVG。
  4) data/city-art-manifest.json  —— 410 城清单，供校验与后台批量替换。

口径（重要）：
  · 这些是**按城市生成的矢量插画**，不是真实景点照片，不引用任何外链网图。
  · 图上只写「城市名 / 省份 / 大区 / 编号」这类公开事实，不编造景点、票价、
    营业时间、实测坐标，也不冒充摄影作品。
  · 地域纹样按大区 + profile + 城市 id 的稳定哈希差异化，410 城互不相同。
  · 需要真实照片时：把自备授权图片放进 assets/img/，在后台「详情 → 卡片图 /
    封面大图」填相对路径，或批量改 city-media.js 的 cover / spots / food / stay。
    用户显式填的路径优先于内置图。

用法：python3 tools/gen_city_art.py
"""
import base64
import hashlib
import html
import json
import math
import pathlib
import re

from city_art_scene import scene_svg

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / 'data' / 'cities.full.json'
OUT_JS = ROOT / 'data' / 'city-media.js'
OUT_DIR = ROOT / 'assets' / 'img' / 'cities'
OUT_GALLERY = ROOT / 'assets' / 'img' / 'city-gallery.html'
OUT_MANIFEST = ROOT / 'data' / 'city-art-manifest.json'

FONT = "'WenQuanYi Micro Hei','PingFang SC','Microsoft YaHei',sans-serif"


def esc(s):
    return html.escape(str(s or ''), quote=True)


def seed_of(s):
    return int(hashlib.sha256(str(s).encode('utf-8')).hexdigest()[:8], 16)


def shade(hex_color, k):
    """把 #rrggbb 按 k 提亮(k>0)/压暗(k<0)，保持低饱和。"""
    m = re.match(r'#([0-9a-fA-F]{6})', str(hex_color or ''))
    if not m:
        return '#3f6f63'
    r, g, b = (int(m.group(1)[i:i + 2], 16) for i in (0, 2, 4))
    f = (lambda v: max(0, min(255, int(v + (255 - v) * k)))) if k > 0 else (lambda v: max(0, min(255, int(v * (1 + k)))))
    return '#%02x%02x%02x' % (f(r), f(g), f(b))


def motif_for(city, s):
    """按大区 + 画像选地域纹样，返回 motif 名。"""
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


def motif_svg(kind, s, c1, c2, w=1280, h=720, compact=False):
    """纯矢量地域剪影，无外链、无 <image>、无字体 @import。"""
    out = []
    light = 'rgba(255,253,248,.30)'
    mid = 'rgba(255,253,248,.17)'
    deep = 'rgba(20,42,34,.13)'
    # 日轮 / 月轮，位置按种子浮动
    cx, cy = w * (0.68 + (s % 17) / 100), h * (0.20 + (s % 9) / 100)
    out.append('<circle cx="%.0f" cy="%.0f" r="%.0f" fill="%s"/>' % (cx, cy, min(w, h) * .095, light))

    def ridge(base, amp, fill, n=7):
        pts = ['M0 %.0f' % (h * base)]
        r = s
        for i in range(n + 1):
            r = (r * 1103515245 + 12345) & 0x7fffffff
            pts.append('L%.0f %.0f' % (w * i / n, h * base + ((r % 1000) / 1000 - .5) * h * amp))
        pts.append('L%.0f %.0f L0 %.0fZ' % (w, h, h))
        return '<path d="%s" fill="%s"/>' % (' '.join(pts), fill)

    if compact:
        out.append(ridge(.68, .16, mid, 4))
        out.append(ridge(.86, .10, deep, 4))
        return ''.join(out)

    if kind in ('mountain', 'terrace', 'desert'):
        out.append(ridge(.58, .22, mid))
        out.append(ridge(.72, .16, light))
        out.append(ridge(.86, .10, deep))
        if kind == 'desert':
            for q in range(4):
                y = h * (.70 + q * .055)
                out.append('<path d="M%.0f %.0f Q%.0f %.0f %.0f %.0f" stroke="%s" stroke-width="3" fill="none"/>'
                           % (w * .08, y, w * .5, y - h * .05, w * .96, y, light))
        elif kind == 'terrace':
            for q in range(5):
                y = h * (.60 + q * .07)
                out.append('<path d="M0 %.0f Q%.0f %.0f %.0f %.0f" stroke="%s" stroke-width="6" fill="none" opacity=".55"/>'
                           % (y, w * .5, y - h * (.10 - q * .012), w, y, light))
    elif kind in ('wave', 'palm'):
        for i in range(6):
            y = h * (.56 + i * .068)
            out.append('<path d="M0 %.0f Q%.0f %.0f %.0f %.0f Q%.0f %.0f %.0f %.0f" stroke="%s" stroke-width="3" fill="none"/>'
                       % (y, w * .25, y - 16, w * .5, y, w * .75, y + 16, w, y, light))
        if kind == 'palm':
            px, py = w * .16, h * .82
            out.append('<path d="M%.0f %.0f L%.0f %.0f" stroke="%s" stroke-width="9" stroke-linecap="round"/>'
                       % (px, py, px + 14, h * .52, deep))
            for k in range(7):
                a = -3.14 + k * .45
                ex, ey = px + 14 + 105 * math.cos(a), h * .52 + 44 * math.sin(a)
                out.append('<path d="M%.0f %.0f Q%.0f %.0f %.0f %.0f Q%.0f %.0f %.0f %.0fZ" fill="%s"/>'
                           % (px + 14, h * .52, (px + 14 + ex) / 2, h * .52 - 34, ex, ey,
                              (px + 14 + ex) / 2, h * .52 + 12, px + 14, h * .52, mid))
    elif kind in ('roof', 'bridge'):
        bx, by = w * .62, h * .72
        out.append('<path d="M%.0f %.0f Q%.0f %.0f %.0f %.0f L%.0f %.0f L%.0f %.0fZ" fill="%s"/>'
                   % (bx - 150, by, bx, by - h * .20, bx + 150, by, bx + 132, by + 14, bx - 132, by + 14, mid))
        out.append('<rect x="%.0f" y="%.0f" width="264" height="14" fill="%s"/>' % (bx - 132, by + 12, light))
        for c in range(4):
            out.append('<rect x="%.0f" y="%.0f" width="12" height="%.0f" fill="%s"/>'
                       % (bx - 100 + c * 62, by + 26, h * .13, mid))
        if kind == 'bridge':
            out.append('<path d="M0 %.0f Q%.0f %.0f %.0f %.0f" stroke="%s" stroke-width="14" fill="none"/>'
                       % (h * .92, w * .5, h * .70, w, h * .92, light))
    elif kind == 'pine':
        for p in range(9):
            tx, ty = w * (.04 + p * .115), h * (.86 + (p % 3) * .035)
            out.append('<path d="M%.0f %.0f L%.0f %.0f L%.0f %.0fZ" fill="%s"/>'
                       % (tx, ty - h * .30, tx - w * .034, ty, tx + w * .034, ty, mid))
            out.append('<rect x="%.0f" y="%.0f" width="6" height="%.0f" fill="%s"/>'
                       % (tx - 3, ty, h - ty, deep))
    return ''.join(out)


def subject_svg(kind, s, motif, name, w=640, h=480):
    """每城专属城市风物画。

    同一座城的 spots / food / stay 是同一片地域的三种视角（远景 / 街市 / 水岸），
    由 motif + 城市种子决定山形、水线、屋舍位置，410 城互不相同。
    这里画的是「这座城市的画面」，不再画碗 / 屋 / 塔这类通用栏目图标。
    图上只写城市名（公开事实），不编造景点、票价或营业时间。
    """
    white = '#fffdf8'
    light = 'rgba(255,253,248,.42)'
    mid = 'rgba(255,253,248,.24)'
    deep = 'rgba(20,42,34,.22)'
    gold = 'rgba(232,185,106,.85)'
    off = {'spot': 11, 'food': 29, 'stay': 47}.get(kind, 0)
    r = (s + off) & 0x7fffffff

    def rnd():
        nonlocal r
        r = (r * 1103515245 + 12345) & 0x7fffffff
        return (r % 1000) / 1000

    def ridge(base, amp, fill, n=7):
        pts = ['M0 %.0f' % (h * base)]
        for i in range(n + 1):
            pts.append('L%.0f %.0f' % (w * i / n, h * base + (rnd() - .5) * h * amp))
        pts.append('L%.0f %.0f L0 %.0fZ' % (w, h, h))
        return '<path d="%s" fill="%s"/>' % (' '.join(pts), fill)

    o = []
    # 日轮 / 月轮：三类视角位置不同
    sx, sy = w * (.58 + rnd() * .28), h * (.14 + rnd() * .16)
    o.append('<circle cx="%.0f" cy="%.0f" r="%.0f" fill="%s"/>'
             % (sx, sy, min(w, h) * (.075 + rnd() * .045), light))
    # 远景山脊 / 沙丘 / 水线
    o.append(ridge(.50 + (kind == 'stay') * .05, .20, mid))
    o.append(ridge(.66, .15, light))
    if motif in ('wave', 'palm', 'bridge', 'roof'):
        for i in range(5):
            y = h * (.70 + i * .055)
            o.append('<path d="M0 %.0f Q%.0f %.0f %.0f %.0f" stroke="%s" stroke-width="3" fill="none"/>'
                     % (y, w * .5, y - 12 - rnd() * 14, w, y, mid))
    if motif == 'terrace':
        for q in range(5):
            y = h * (.60 + q * .06)
            o.append('<path d="M0 %.0f Q%.0f %.0f %.0f %.0f" stroke="%s" stroke-width="5" fill="none" opacity=".5"/>'
                     % (y, w * .5, y - h * .07, w, y, light))
    if motif == 'desert':
        for q in range(3):
            y = h * (.68 + q * .05)
            o.append('<path d="M%.0f %.0f Q%.0f %.0f %.0f %.0f" stroke="%s" stroke-width="3" fill="none"/>'
                     % (w * .06, y, w * .5, y - h * .04, w * .94, y, light))
    o.append(ridge(.82, .09, deep))

    # 中景屋舍群：按视角错位，形成三张不同构图
    bx = w * (.14 + rnd() * .16)
    by = h * (.62 + (kind == 'food') * .06)
    bw = w * (.16 + rnd() * .07)
    for k in range(4):
        x = bx + k * (bw * .82)
        hh = h * (.12 + rnd() * .10)
        o.append('<rect x="%.0f" y="%.0f" width="%.0f" height="%.0f" rx="3" fill="%s"/>'
                 % (x, by - hh, bw * .68, hh, white))
        o.append('<path d="M%.0f %.0f Q%.0f %.0f %.0f %.0f L%.0f %.0f L%.0f %.0fZ" fill="%s"/>'
                 % (x - 10, by - hh, x + bw * .34, by - hh - h * .075, x + bw * .68 + 10, by - hh,
                    x + bw * .68 + 3, by - hh + 9, x - 3, by - hh + 9, deep))
        o.append('<rect x="%.0f" y="%.0f" width="%.0f" height="%.0f" fill="%s"/>'
                 % (x + bw * .20, by - hh * .55, bw * .22, hh * .26, gold))
    # 近景：桥 / 岸线 / 树影，按视角变化
    if kind == 'spot':
        o.append('<path d="M%.0f %.0f Q%.0f %.0f %.0f %.0f" stroke="%s" stroke-width="12" fill="none"/>'
                 % (w * .06, h * .90, w * .5, h * .74, w * .94, h * .90, white))
    elif kind == 'food':
        for q in range(6):
            x = w * (.10 + q * .145)
            o.append('<circle cx="%.0f" cy="%.0f" r="%.0f" fill="%s" opacity=".8"/>'
                     % (x, h * .52 + rnd() * h * .14, 7 + rnd() * 5, gold))
    else:
        for q in range(3):
            x = w * (.18 + q * .30)
            o.append('<rect x="%.0f" y="%.0f" width="%.0f" height="%.0f" fill="%s" opacity=".35"/>'
                     % (x, h * .78, w * .12, h * .16, white))
    # 三类视角的色调区分（很淡，不改变地域主色）
    tint = {'spot': 'rgba(255,253,248,0)', 'food': 'rgba(232,185,106,.11)',
            'stay': 'rgba(150,190,205,.11)'}.get(kind, 'rgba(255,253,248,0)')
    if tint != 'rgba(255,253,248,0)':
        o.append('<rect width="%d" height="%d" fill="%s"/>' % (w, h, tint))
    # 城市名：每张图都能看出属于哪座城，只写公开事实
    o.append('<rect x="22" y="%.0f" width="4" height="26" fill="%s"/>' % (h - 48, gold))
    o.append('<text x="36" y="%.0f" font-family="%s" font-size="23" letter-spacing="2" '
             'fill="%s" opacity=".92">%s</text>' % (h - 28, FONT, white, esc(name)))
    return ''.join(o)


def svg_city(city, kind, idx, total):
    return scene_svg(city, kind, idx, total)
    cid = str(city.get('id') or '')
    name = str(city.get('name') or '行迹')
    prov = str(city.get('prov') or city.get('province') or '')
    region = str(city.get('region') or '')
    g = city.get('g') or ['#3f6f63', '#8fb6a4']
    c1, c2 = (g + ['#8fb6a4'])[:2]
    s = seed_of(cid + '|' + name)
    m = motif_for(city, s)
    big = kind == 'cover'
    thumb = kind == 'thumb'
    w, h = (1280, 720) if big else ((96, 54) if thumb else (640, 480))
    uid = 'g%d' % (s % 100000)
    body = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" viewBox="0 0 %d %d">' % (w, h, w, h),
        '<title>%s</title>' % esc(name + ((' · ' + prov) if prov and prov != name else '') + ((' · ' + region) if region else '')),
        '<defs><linearGradient id="%s" x1="0" y1="0" x2="1" y2="1">'
        '<stop offset="0" stop-color="%s"/><stop offset="1" stop-color="%s"/></linearGradient>'
        '<linearGradient id="v%s" x1="0" y1="0" x2="0" y2="1">'
        '<stop offset="0" stop-color="#10271e" stop-opacity="0"/>'
        '<stop offset="1" stop-color="#10271e" stop-opacity=".22"/></linearGradient></defs>' % (uid, c1, shade(c2, -.12), uid),
        '<rect width="%d" height="%d" fill="url(#%s)"/>' % (w, h, uid),
        motif_svg(m, s + (0 if big else 37), c1, c2, w, h, compact=thumb),
    ]
    if not big and not thumb:
        body.append('<rect width="%d" height="%d" fill="rgba(16,39,30,.04)"/>' % (w, h))
        body.append(subject_svg(kind, s, m, name, w, h))
    body.append('<rect y="%.0f" width="%d" height="%.0f" fill="url(#v%s)"/>' % (h * .52, w, h * .48, uid))
    if big:
        # 背景图不放大城名：画面层自己会渲染标题，叠字会形成重影。
        # 城市身份写进 <title> 元数据，图库卡片下方另有城名 / 省份 / 大区。
        body.append('<text x="94" y="602" font-family="%s" font-size="18" letter-spacing="7" '
                    'fill="#ffffff" opacity=".34">XINGJI · CITY ATLAS</text>' % FONT)
        body.append('<text x="1192" y="664" text-anchor="end" font-family="%s" font-size="16" '
                    'fill="#ffffff" opacity=".40">No.%03d / %d · %s</text>' % (FONT, idx, total, esc(region)))
    elif thumb:
        body.append('<rect width="%d" height="%d" fill="rgba(16,39,30,.22)"/>' % (w, h))
    else:
        body.append('<text x="612" y="452" text-anchor="end" font-family="%s" font-size="14" '
                    'fill="#ffffff" opacity=".38">XINGJI / %03d</text>' % (FONT, idx))
    body.append('</svg>')
    return ''.join(body)


def data_uri(svg):
    return 'data:image/svg+xml;base64,' + base64.b64encode(svg.encode('utf-8')).decode('ascii')


def main():
    doc = json.loads(SRC.read_text(encoding='utf-8'))
    cities = doc['cities']
    if len(cities) != 410:
        raise SystemExit('期望 410 城，实际 %d' % len(cities))
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for old in OUT_DIR.glob('*.svg'):
        old.unlink()

    entries, manifest, covers = [], [], {}
    for i, c in enumerate(cities, 1):
        cid = str(c['id'])
        cover = svg_city(c, 'cover', i, 410)
        (OUT_DIR / (cid + '.svg')).write_text(cover, encoding='utf-8')
        covers[cid] = cover
        items = {
            'cover': data_uri(cover),
            'thumb': data_uri(svg_city(c, 'thumb', i, 410)),
            'spots': [data_uri(svg_city(c, 'spot', i, 410))],
            'food': [data_uri(svg_city(c, 'food', i, 410))],
            'stay': [data_uri(svg_city(c, 'stay', i, 410))],
            'credit': '行迹内置矢量插画（非照片）· 可在后台替换为自备授权图片',
            'file': 'assets/img/cities/%s.svg' % cid,
            'motif': motif_for(c, seed_of(cid + '|' + str(c.get('name') or ''))),
        }
        entries.append((cid, str(c.get('name') or ''), items))
        manifest.append({
            'id': cid, 'name': c.get('name'), 'prov': c.get('prov') or c.get('province') or '',
            'region': c.get('region'), 'tier': c.get('tier'), 'motif': items['motif'],
            'file': items['file'], 'kinds': ['cover', 'spot', 'food', 'stay'],
        })

    # 媒体索引改由 gen_city_media.py 生成：6 类题材 PNG 的相对路径，
    # 不再把五类共用同一套构图的 data URI 内联进 city-media.js。
    import gen_city_media
    gen_city_media.build()

    OUT_MANIFEST.write_text(json.dumps({'total': 410, 'cities': manifest}, ensure_ascii=False, indent=1), encoding='utf-8')

    # 图库：内嵌 cover 的 data URI，离线双击可用；可搜索、筛选、逐城下载 SVG
    cards = []
    for cid, name, it in entries:
        prov = next((x['prov'] for x in manifest if x['id'] == cid), '')
        region = next((x['region'] for x in manifest if x['id'] == cid), '')
        motif = next((x['motif'] for x in manifest if x['id'] == cid), '')
        cards.append('<figure data-k="%s"><img loading="lazy" src="%s" alt="%s">'
                     '<figcaption><b>%s</b><span>%s · %s · %s</span>'
                     '<button data-id="%s">下载 SVG</button></figcaption></figure>'
                     % (esc(name + prov + region), 'cities/%s.svg' % cid, esc(name), esc(name),
                        esc(prov), esc(region), esc(motif), esc(cid)))
    gallery = """<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<title>行迹 · 410 城图像库</title><style>
*{box-sizing:border-box}body{margin:0;padding:28px;background:#f5f2ea;color:#25352c;
 font-family:'WenQuanYi Micro Hei','Microsoft YaHei',sans-serif}
h1{font-size:24px;margin:0 0 6px}p{color:#6b7a70;font-size:13px;line-height:1.8;margin:0 0 18px}
.bar{position:sticky;top:0;background:#f5f2ea;padding:12px 0;display:flex;gap:10px;flex-wrap:wrap;z-index:2}
input,select{font:inherit;padding:8px 12px;border:1px solid #d9e2d8;border-radius:8px;background:#fff}
#grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:16px;margin-top:16px}
figure{margin:0;background:#fffdf8;border:1px solid #e6e9df;border-radius:12px;overflow:hidden}
figure img{width:100%;aspect-ratio:16/9;object-fit:cover;display:block;background:#dfe9e0}
figcaption{padding:9px 11px;font-size:12px;display:flex;flex-direction:column;gap:4px}
figcaption b{font-size:14px}figcaption span{color:#6b7a70;font-size:11px}
button{margin-top:5px;font:inherit;font-size:11px;cursor:pointer;border:1px solid #a9c9b2;
 background:#f0f7f2;color:#2f5c48;border-radius:6px;padding:5px 8px}
</style></head><body>
<h1>行迹 · 410 城图像库</h1>
<p>这里展示每城的 SVG 原图。视频分镜用的是 <b>6 类不同题材的 PNG</b>（城市地标 / 街巷 / 菜品 / 院落 / 路桥 / 逐日动线），在 assets/img/scenes/ 目录，按栏目自动取用，无需逐镜配置。<br><b>全部是本地绘制的插画，不是真实景点照片</b>，不引用外链网图。需要真实照片：把自备授权图片放进 assets/img/，在后台「详情 → 图像」填相对路径即可覆盖。</p>
<div class="bar"><input id="q" placeholder="搜城市 / 省份 / 大区" size="26">
<select id="r"><option value="">全部大区</option>__REGIONS__</select>
<span id="n" style="align-self:center;color:#6b7a70;font-size:12px"></span></div>
<div id="grid">__CARDS__</div>
<script>
var q=document.getElementById('q'),r=document.getElementById('r'),n=document.getElementById('n'),fs=[].slice.call(document.querySelectorAll('figure'));
function flt(){var a=q.value.trim(),b=r.value,c=0;fs.forEach(function(f){var ok=(!a||f.dataset.k.indexOf(a)>=0)&&(!b||f.dataset.k.indexOf(b)>=0);f.style.display=ok?'':'none';if(ok)c++;});n.textContent=c+' / 410 城';}
q.oninput=flt;r.onchange=flt;flt();
document.addEventListener('click',function(e){var b=e.target.closest('button[data-id]');if(!b)return;
 var id=b.dataset.id,l=document.createElement('a');
 l.href='cities/'+id+'.svg';l.download=id+'.svg';l.click();});
</script></body></html>"""
    regions = sorted(set(str(x['region']) for x in manifest if x['region']))
    gallery = gallery.replace('__REGIONS__', ''.join('<option value="%s">%s</option>' % (esc(x), esc(x)) for x in regions))
    gallery = gallery.replace('__CARDS__', ''.join(cards))
    OUT_GALLERY.write_text(gallery, encoding='utf-8')

    size = (ROOT / 'data' / 'city-media.js').stat().st_size
    print('410 城图像生成完成')
    print('  data/city-media.js  %d 字节（由 gen_city_media.py 生成）' % size)
    print('  %s  %d 个 SVG' % (OUT_DIR.relative_to(ROOT), len(list(OUT_DIR.glob('*.svg')))))
    print('  %s  %d 字节' % (OUT_GALLERY.relative_to(ROOT), OUT_GALLERY.stat().st_size))
    print('  %s' % OUT_MANIFEST.relative_to(ROOT))
    print('  地域纹样分布：', {k: sum(1 for x in manifest if x['motif'] == k) for k in sorted(set(x['motif'] for x in manifest))})


if __name__ == '__main__':
    main()
