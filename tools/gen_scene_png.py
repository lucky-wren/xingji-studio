#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""行迹 · 分镜配图生成器（按题材落盘 PNG）

每座城市生成 6 张构图完全不同的题材插画，落盘为真实 PNG 文件：
  cover  城市地标全景（封面 / 总览 / 片尾）
  wear   街巷衣铺（衣 · 分季穿搭）
  food   餐桌菜品（食 · 必吃榜）
  stay   客栈院落（住 · 区域建议）
  route  路桥交通（行 · 交通指南）
  day    逐日动线地图（Day 1/2/3）

设计口径：
  · 六种题材一眼可分辨：底色、主体、视角、构图全部不同，
    不再像旧版那样五类图共用「日轮＋山脊＋水面」同一套底纹。
  · 城市差异来自 cities.full.json 的 g 主色 + 城名 + 稳定哈希细节，
    410 城互不相同，但题材识别不受影响。
  · 这些是本地绘制的插画，不是真实照片；图上只写城市名 / 省份等公开事实，
    不编造景点、票价、营业时间。
  · 产物是目录里能直接看见、双击能打开的一张张 .png；
    页面按相对路径 assets/img/scenes/<id>_<kind>.png 读取，零外链。

用法：python3 tools/gen_scene_png.py
"""
import hashlib
import json
import math
import pathlib
import random
import re
from PIL import Image, ImageDraw, ImageFont

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / 'data' / 'cities.full.json'
OUT_DIR = ROOT / 'assets' / 'img' / 'scenes'
MANIFEST = ROOT / 'data' / 'scene-images.json'

W, H = 720, 480
KINDS = ['cover', 'wear', 'food', 'stay', 'route', 'day']
KIND_CN = {'cover': '城市地标', 'wear': '街巷', 'food': '菜品',
           'stay': '院落', 'route': '路桥', 'day': '逐日动线'}

FONT_CANDIDATES = [
    '/usr/share/fonts/truetype/wqy/wqy-microhei.ttc',
    '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc',
    '/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc',
]


def font(sz, bold=False):
    for p in FONT_CANDIDATES:
        try:
            return ImageFont.truetype(p, sz)
        except Exception:
            pass
    return ImageFont.load_default()


def hexrgb(s):
    m = re.match(r'#([0-9a-fA-F]{6})', str(s or ''))
    if not m:
        return (63, 111, 99)
    v = m.group(1)
    return tuple(int(v[i:i + 2], 16) for i in (0, 2, 4))


def mix(c, k):
    """k>0 向白提亮，k<0 向黑压暗。"""
    if k > 0:
        return tuple(int(x + (255 - x) * k) for x in c)
    return tuple(int(x * (1 + k)) for x in c)


def blend(a, b, t):
    return tuple(int(a[i] * (1 - t) + b[i] * t) for i in range(3))


def palette(city):
    g = city.get('g') or ['#3f6f63', '#8fb6a4']
    c1, c2 = hexrgb(g[0]), hexrgb((g + ['#8fb6a4'])[1])
    return {
        'c1': c1, 'c2': c2,
        'sky1': mix(c1, .62), 'sky2': mix(c2, .34), 'sky3': (250, 233, 199),
        'far': mix(c1, -.08), 'mid': mix(c1, -.32), 'near': mix(c1, -.56),
        'ink': mix(c1, -.72), 'water': mix(c2, -.28),
        'gold': (233, 178, 88), 'paper': (255, 253, 248),
        'brick': mix(c2, -.10), 'wood': (92, 63, 46), 'wood2': (140, 96, 66),
        'leaf': mix(c1, -.18), 'warm': (238, 205, 158),
    }


def seed_of(cid, name, kind):
    return int(hashlib.sha256((str(cid) + '|' + str(name) + '|' + kind).encode('utf-8')).hexdigest()[:8], 16)


def rr(d, box, radius, fill, outline=None, width=1):
    try:
        d.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)
    except Exception:
        d.rectangle(box, fill=fill, outline=outline)


def gradient_top(d, w, h, top, bottom):
    for y in range(h):
        d.line([(0, y), (w, y)], fill=blend(top, bottom, y / max(1, h - 1)))


def sun(d, cx, cy, r, col=(255, 246, 214)):
    for k in range(6, 0, -1):
        a = int(18 + (6 - k) * 7)
        d.ellipse([cx - r * k * .55, cy - r * k * .55, cx + r * k * .55, cy + r * k * .55],
                  fill=blend(col, (255, 255, 255), .55) if k > 3 else None,
                  outline=None) if False else None
    d.ellipse([cx - r * 2.1, cy - r * 2.1, cx + r * 2.1, cy + r * 2.1], fill=None)
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=col)


def ridge(d, w, h, base, amp, fill, rnd, n=9):
    pts = [(0, h)]
    for i in range(n + 1):
        pts.append((w * i / n, h * base + (rnd() - .5) * h * amp))
    pts.append((w, h))
    d.polygon(pts, fill=fill)


def cloud(d, w, h, rnd, alpha=(255, 253, 248)):
    for q in range(3):
        cx = w * (.08 + q * .33 + rnd() * .06)
        cy = h * (.10 + rnd() * .16)
        cw, ch = w * (.09 + rnd() * .06), h * .022
        d.ellipse([cx - cw, cy - ch, cx + cw, cy + ch], fill=alpha)


def label(d, name, prov, kind, p, dark_bg=False):
    """底部城名牌：白底深字或深底白字，保证每张图都能认出是哪座城。"""
    bw, bh = W - 44, 46
    x, y = 22, H - bh - 20
    rr(d, [x, y, x + bw, y + bh], 10, (255, 253, 248) if not dark_bg else (24, 44, 35))
    d.rectangle([x, y, x + 6, y + bh], fill=p['gold'])
    fg = (30, 52, 42) if not dark_bg else (255, 253, 248)
    d.text((x + 18, y + 9), name, font=font(23), fill=fg)
    sub = (prov or '') + '   ·   ' + KIND_CN[kind] + '   ·   XINGJI'
    d.text((x + bw - 12, y + 14), sub, font=font(14), fill=blend(fg, (130, 140, 132), .35), anchor='ra')


# ---------------------------------------------------------------- 六种题材
def draw_cover(d, p, rnd, name, prov):
    """城市地标全景：天空 / 日轮 / 三层山脊 / 水面 / 城楼（宽幅远景）"""
    gradient_top(d, W, H, p['sky1'], p['sky3'])
    sx, sy, sr = W * (.63 + rnd() * .18), H * (.17 + rnd() * .08), H * .085
    d.ellipse([sx - sr * 2.4, sy - sr * 2.4, sx + sr * 2.4, sy + sr * 2.4],
              fill=blend(p['sky2'], (255, 248, 220), .55))
    d.ellipse([sx - sr, sy - sr, sx + sr, sy + sr], fill=(255, 246, 214))
    cloud(d, W, H, rnd)
    ridge(d, W, H, .46, .13, p['far'], rnd)
    ridge(d, W, H, .58, .10, p['mid'], rnd)
    # 城楼 / 塔：明显主体
    bx, by = W * .66, H * .70
    bw, bh = W * .17, H * .24
    d.rectangle([bx - bw / 2, by - bh, bx + bw / 2, by], fill=p['near'])
    for lv in range(2):
        ey = by - bh - lv * bh * .52
        d.polygon([(bx - bw * .78, ey), (bx, ey - bh * .30), (bx + bw * .78, ey),
                   (bx + bw * .62, ey + 9), (bx - bw * .62, ey + 9)], fill=p['ink'])
    for cx in (-.24, 0, .24):
        d.rectangle([bx + bw * cx - 7, by - bh * .70, bx + bw * cx + 7, by - bh * .48], fill=p['gold'])
    # 次景屋舍
    for k in range(4):
        hx = W * (.10 + k * .105)
        hh = H * (.07 + rnd() * .05)
        d.rectangle([hx, by - hh, hx + W * .07, by], fill=p['near'])
        d.polygon([(hx - 8, by - hh), (hx + W * .035, by - hh - H * .05),
                   (hx + W * .07 + 8, by - hh)], fill=p['ink'])
    ridge(d, W, H, .71, .05, p['near'], rnd)
    d.rectangle([0, H * .74, W, H], fill=p['water'])
    for q in range(6):
        yy = H * (.77 + q * .038)
        d.line([(W * .06, yy), (W * .48, yy - 5), (W * .94, yy)],
               fill=blend(p['water'], (255, 255, 255), .45), width=2)
    label(d, name, prov, 'cover', p)


def draw_wear(d, p, rnd, name, prov):
    """街巷衣铺：一点透视街道 / 两侧店铺 / 遮阳棚 / 挂着的布匹衣衫 / 灯笼"""
    d.rectangle([0, 0, W, H], fill=blend(p['sky1'], (220, 226, 220), .45))
    # 远处天空与街口
    d.polygon([(W * .34, 0), (W * .66, 0), (W * .62, H * .52), (W * .38, H * .52)], fill=p['sky2'])
    # 两侧建筑墙面（透视）
    d.polygon([(0, 0), (W * .38, H * .12), (W * .38, H * .80), (0, H)], fill=blend(p['brick'], (0, 0, 0), .12))
    d.polygon([(W, 0), (W * .62, H * .12), (W * .62, H * .80), (W, H)], fill=blend(p['brick'], (255, 255, 255), .06))
    # 地砖透视线
    for k in range(-5, 6):
        d.line([(W * .5 + k * W * .012, H * .52), (W * .5 + k * W * .15, H)],
               fill=blend(p['brick'], (255, 255, 255), .30), width=2)
    for j in range(1, 6):
        yy = H * (.55 + (j / 6) ** 1.7 * .44)
        d.line([(0, yy), (W, yy)], fill=blend(p['brick'], (255, 255, 255), .22), width=2)
    # 遮阳棚（左右各一，斜条纹）
    for side, x0, x1 in (('L', W * .03, W * .36), ('R', W * .64, W * .97)):
        ay = H * (.20 if side == 'L' else .23)
        d.polygon([(x0, ay), (x1, ay + H * .05), (x1, ay + H * .13), (x0, ay + H * .08)], fill=p['paper'])
        cols = [p['c1'], p['gold'], p['paper']]
        for q in range(7):
            xx = x0 + (x1 - x0) * q / 7
            d.polygon([(xx, ay + H * .03 * q / 7), (xx + (x1 - x0) / 7, ay + H * .03 * (q + 1) / 7),
                       (xx + (x1 - x0) / 7, ay + H * .12), (xx, ay + H * .11)], fill=cols[q % 3])
    # 挂杆 + 衣衫 / 布匹（一眼是「衣」）
    d.line([(W * .04, H * .38), (W * .36, H * .41)], fill=p['wood'], width=5)
    d.line([(W * .64, H * .41), (W * .96, H * .38)], fill=p['wood'], width=5)
    shades = [p['c1'], p['c2'], p['gold'], (213, 118, 96), (86, 122, 158), p['paper']]
    for side in ('L', 'R'):
        for q in range(5):
            cx = W * (.07 + q * .065) if side == 'L' else W * (.67 + q * .065)
            cy = H * (.39 if side == 'L' else .41) + (0 if side == 'L' else H * .005 * q)
            cw, ch = W * .043, H * (.14 + rnd() * .06)
            c = shades[(q + (0 if side == 'L' else 2)) % len(shades)]
            # 衣身 + 两袖 + 领口，明显是衣服
            d.polygon([(cx - cw * .5, cy + ch * .18), (cx + cw * .5, cy + ch * .18),
                       (cx + cw * .46, cy + ch), (cx - cw * .46, cy + ch)], fill=c)
            d.polygon([(cx - cw * .5, cy + ch * .18), (cx - cw * 1.05, cy + ch * .42),
                       (cx - cw * .72, cy + ch * .60), (cx - cw * .38, cy + ch * .36)], fill=c)
            d.polygon([(cx + cw * .5, cy + ch * .18), (cx + cw * 1.05, cy + ch * .42),
                       (cx + cw * .72, cy + ch * .60), (cx + cw * .38, cy + ch * .36)], fill=c)
            d.ellipse([cx - cw * .20, cy + ch * .10, cx + cw * .20, cy + ch * .26], fill=p['paper'])
    # 红灯笼
    for lx, ly, ls in ((W * .30, H * .16, 1.0), (W * .70, H * .18, .85)):
        d.line([(lx, ly - H * .08), (lx, ly - H * .02)], fill=p['wood'], width=2)
        d.ellipse([lx - 13 * ls, ly, lx + 13 * ls, ly + 24 * ls], fill=(198, 82, 66))
        d.rectangle([lx - 13 * ls, ly + 10 * ls, lx + 13 * ls, ly + 14 * ls], fill=p['gold'])
    label(d, name, prov, 'wear', p, dark_bg=True)


def draw_food(d, p, rnd, name, prov):
    """餐桌菜品俯拍：深色木桌 / 大白盘 / 菜块 / 筷子 / 小碟 / 茶杯 / 热气"""
    d.rectangle([0, 0, W, H], fill=p['wood'])
    for q in range(9):
        y = H * q / 9
        d.line([(0, y), (W, y)], fill=blend(p['wood'], (255, 255, 255), .06), width=3)
    # 桌面圆形餐垫
    cx, cy = W * .47, H * .50
    d.ellipse([cx - H * .46, cy - H * .46, cx + H * .46, cy + H * .46],
              fill=blend(p['wood'], (255, 255, 255), .10))
    # 大白盘 + 内圈
    R = H * .40
    d.ellipse([cx - R, cy - R, cx + R, cy + R], fill=(247, 244, 236))
    d.ellipse([cx - R * .80, cy - R * .80, cx + R * .80, cy + R * .80], fill=(228, 224, 212))
    d.ellipse([cx - R * .76, cy - R * .76, cx + R * .76, cy + R * .76], fill=(251, 249, 242))
    # 盘中菜：随机分布的色块 + 点缀（明显是「一盘菜」）
    veg = [(196, 108, 62), (108, 146, 78), (226, 178, 70), (172, 76, 64),
           (238, 214, 160), (74, 116, 82), (214, 148, 92)]
    for q in range(26):
        a = rnd() * math.tau
        rad = R * .66 * math.sqrt(rnd())
        px, py = cx + math.cos(a) * rad, cy + math.sin(a) * rad * .92
        sz = H * (.028 + rnd() * .035)
        c = veg[int(rnd() * len(veg))]
        d.ellipse([px - sz, py - sz * .62, px + sz, py + sz * .62], fill=c)
        d.ellipse([px - sz * .5, py - sz * .38, px + sz * .2, py - sz * .1],
                  fill=blend(c, (255, 255, 255), .35))
    # 葱花 / 芝麻
    for q in range(30):
        a, rad = rnd() * math.tau, R * .70 * math.sqrt(rnd())
        px, py = cx + math.cos(a) * rad, cy + math.sin(a) * rad * .92
        d.ellipse([px - 2, py - 2, px + 2, py + 2], fill=(250, 236, 170))
    # 筷子（斜放）
    d.line([(cx + R * .82, cy - R * .95), (cx + R * 1.28, cy + R * .55)], fill=p['wood2'], width=7)
    d.line([(cx + R * .92, cy - R * .98), (cx + R * 1.38, cy + R * .52)], fill=p['wood2'], width=7)
    # 小碟 + 茶杯
    sx, sy = W * .855, H * .28
    d.ellipse([sx - 46, sy - 30, sx + 46, sy + 30], fill=(240, 236, 226))
    d.ellipse([sx - 34, sy - 21, sx + 34, sy + 21], fill=(216, 148, 92))
    tx, ty = W * .865, H * .74
    d.ellipse([tx - 38, ty - 34, tx + 38, ty + 34], fill=(247, 244, 236))
    d.ellipse([tx - 27, ty - 24, tx + 27, ty + 24], fill=blend(p['c2'], (120, 90, 50), .35))
    # 热气
    for q in range(3):
        hx = cx + H * (-.10 + q * .10)
        for k in range(5):
            yy = cy - R * .80 - k * 13
            xx = hx + math.sin(k * .9 + q) * 7
            d.ellipse([xx - 2, yy - 2, xx + 2, yy + 2], fill=(255, 253, 248))
    label(d, name, prov, 'food', p, dark_bg=True)


def draw_stay(d, p, rnd, name, prov):
    """客栈院落：院墙 / 瓦顶 / 月亮门 / 窗格 / 台阶 / 树 / 灯笼（正面构图）"""
    d.rectangle([0, 0, W, H], fill=blend(p['warm'], (255, 255, 255), .30))
    # 天空与远树
    d.rectangle([0, 0, W, H * .30], fill=blend(p['sky1'], (255, 255, 255), .18))
    for q in range(7):
        tx = W * (.02 + q * .15)
        d.ellipse([tx - W * .075, H * .10, tx + W * .075, H * .36], fill=blend(p['leaf'], (255, 255, 255), .35))
    # 院墙主体
    wy = H * .30
    d.rectangle([W * .05, wy, W * .95, H * .88], fill=(248, 243, 232))
    # 瓦顶（一排弧瓦）
    d.polygon([(W * .02, wy), (W * .50, wy - H * .13), (W * .98, wy)], fill=p['ink'])
    for q in range(13):
        xx = W * (.045 + q * .073)
        d.arc([xx - 22, wy - 16, xx + 22, wy + 16], 180, 360, fill=blend(p['ink'], (255, 255, 255), .25), width=3)
    # 左右厢房窗格
    for side in (W * .13, W * .87):
        d.rectangle([side - W * .095, H * .40, side + W * .095, H * .68], fill=blend(p['wood'], (255, 255, 255), .18))
        for r in range(3):
            for c in range(4):
                gx = side - W * .075 + c * W * .047
                gy = H * .425 + r * H * .082
                d.rectangle([gx, gy, gx + W * .036, gy + H * .062], fill=p['gold'])
                d.rectangle([gx + 3, gy + 3, gx + W * .036 - 3, gy + H * .062 - 3],
                            fill=blend(p['wood'], (255, 255, 255), .30))
    # 中央月亮门 / 大门洞
    mx, my, mr = W * .50, H * .68, W * .155
    d.ellipse([mx - mr, my - mr * 1.55, mx + mr, my + mr * 1.05], fill=p['ink'])
    d.ellipse([mx - mr * .80, my - mr * 1.30, mx + mr * .80, my + mr * .95],
              fill=blend(p['sky2'], (40, 60, 50), .30))
    # 门内小景：远山 + 一盏灯
    d.polygon([(mx - mr * .78, my + mr * .10), (mx - mr * .2, my - mr * .32),
               (mx + mr * .25, my - mr * .05), (mx + mr * .78, my + mr * .18),
               (mx + mr * .78, my + mr * .95), (mx - mr * .78, my + mr * .95)], fill=p['leaf'])
    d.rectangle([mx - 4, my - mr * .62, mx + 4, my + mr * .92], fill=p['gold'])
    # 门楣匾额
    rr(d, [mx - W * .09, H * .315, mx + W * .09, H * .385], 6, p['wood'])
    d.text((mx, H * .336), '客 栈', font=font(19), fill=p['gold'], anchor='mm')
    # 台阶
    for q in range(3):
        yy = H * (.85 + q * .035)
        d.rectangle([mx - mr - 20 - q * 16, yy, mx + mr + 20 + q * 16, yy + 8],
                    fill=blend(p['brick'], (0, 0, 0), .12))
    # 灯笼两盏
    for lx in (W * .30, W * .70):
        d.line([(lx, H * .33), (lx, H * .40)], fill=p['wood'], width=3)
        d.ellipse([lx - 16, H * .40, lx + 16, H * .40 + 32], fill=(198, 82, 66))
        d.rectangle([lx - 16, H * .40 + 14, lx + 16, H * .40 + 18], fill=p['gold'])
        d.line([(lx, H * .40 + 32), (lx, H * .40 + 44)], fill=p['gold'], width=3)
    label(d, name, prov, 'stay', p)


def draw_route(d, p, rnd, name, prov):
    """路桥交通：远山 / S 形公路向远方收窄 / 拱桥 / 车 / 路标"""
    gradient_top(d, W, H, p['sky1'], blend(p['sky3'], (255, 255, 255), .40))
    sun(d, W * .76, H * .16, H * .055)
    cloud(d, W, H, rnd)
    ridge(d, W, H, .42, .14, p['far'], rnd)
    ridge(d, W, H, .54, .10, p['mid'], rnd)
    # 草地
    d.rectangle([0, H * .58, W, H], fill=blend(p['leaf'], (255, 255, 255), .18))
    # S 形公路：从底部宽到远处窄，明显是「路」
    def road(t):
        return (W * (.50 + .20 * math.sin(t * 3.1 + .4) * (1 - t) + .06 * t),
                H * (1.0 - t * .48))
    pts_l, pts_r = [], []
    for k in range(41):
        t = k / 40
        cx, cy = road(t)
        wdt = W * (.30 * (1 - t) + .012)
        pts_l.append((cx - wdt, cy))
        pts_r.append((cx + wdt, cy))
    d.polygon(pts_l + pts_r[::-1], fill=(74, 80, 82))
    # 路肩与中线
    d.line(pts_l, fill=(250, 246, 235), width=4)
    d.line(pts_r, fill=(250, 246, 235), width=4)
    mid = [(W * (.50 + .20 * math.sin(k / 40 * 3.1 + .4) * (1 - k / 40) + .06 * k / 40),
            H * (1.0 - k / 40 * .48)) for k in range(0, 41, 2)]
    for a, b in zip(mid[:-1], mid[1:]):
        d.line([a, b], fill=(250, 232, 160), width=3)
    # 拱桥横跨路面
    by = H * .70
    d.line([(W * .10, by + H * .10), (W * .34, by - H * .10), (W * .66, by - H * .10),
            (W * .90, by + H * .10)], fill=p['ink'], width=16)
    d.line([(W * .10, by + H * .10 - 8), (W * .34, by - H * .10 - 8), (W * .66, by - H * .10 - 8),
            (W * .90, by + H * .10 - 8)], fill=(238, 234, 224), width=5)
    # 车（明显主体）
    vx, vy = W * .50, H * .86
    rr(d, [vx - 48, vy - 26, vx + 48, vy + 6], 8, (206, 90, 70))
    rr(d, [vx - 30, vy - 44, vx + 26, vy - 22], 6, (235, 238, 236))
    d.rectangle([vx - 24, vy - 40, vx + 18, vy - 26], fill=blend(p['c1'], (120, 160, 190), .5))
    d.ellipse([vx - 34, vy + 2, vx - 14, vy + 22], fill=(40, 46, 46))
    d.ellipse([vx + 14, vy + 2, vx + 34, vy + 22], fill=(40, 46, 46))
    # 路标
    px, py = W * .15, H * .56
    d.rectangle([px - 3, py, px + 3, py + H * .30], fill=p['wood2'])
    rr(d, [px - 46, py - 4, px + 46, py + 26], 4, p['paper'])
    d.text((px, py + 11), name[:3], font=font(16), fill=(30, 52, 42), anchor='mm')
    label(d, name, prov, 'route', p, dark_bg=True)


def draw_day(d, p, rnd, name, prov):
    """逐日动线地图：米白纸底 / 网格 / 虚线路径串 3 个地标节点 / 指北针"""
    d.rectangle([0, 0, W, H], fill=(245, 241, 230))
    # 地图网格
    for x in range(0, W, 48):
        d.line([(x, 0), (x, H)], fill=(225, 220, 205), width=1)
    for y in range(0, H, 48):
        d.line([(0, y), (W, y)], fill=(225, 220, 205), width=1)
    # 淡色地块 / 水域
    d.ellipse([W * .62, H * .10, W * 1.05, H * .62], fill=blend(p['sky2'], (255, 255, 255), .45))
    d.polygon([(0, H * .66), (W * .22, H * .48), (W * .40, H * .70),
               (W * .18, H), (0, H)], fill=blend(p['leaf'], (255, 255, 255), .55))
    # 三个地标节点（圆点 + 建筑剪影 + 编号）
    nodes = [(W * .22, H * .34), (W * .52, H * .62), (W * .80, H * .30)]
    styles = ['tower', 'gate', 'bridge']
    for i, (nx, ny) in enumerate(nodes):
        # 虚线路径
        if i < len(nodes) - 1:
            ax, ay = nodes[i + 1]
            steps = 22
            for k in range(0, steps, 2):
                t0, t1 = k / steps, (k + 1) / steps
                d.line([(nx + (ax - nx) * t0, ny + (ay - ny) * t0),
                        (nx + (ax - nx) * t1, ny + (ay - ny) * t1)],
                       fill=(188, 106, 74), width=4)
        d.ellipse([nx - 34, ny - 34, nx + 34, ny + 34], fill=p['paper'])
        d.ellipse([nx - 30, ny - 30, nx + 30, ny + 30], outline=p['c1'], width=3)
        st = styles[i]
        if st == 'tower':
            d.rectangle([nx - 9, ny - 16, nx + 9, ny + 14], fill=p['ink'])
            d.polygon([(nx - 15, ny - 16), (nx, ny - 27), (nx + 15, ny - 16)], fill=p['ink'])
        elif st == 'gate':
            d.rectangle([nx - 15, ny - 8, nx + 15, ny + 16], fill=p['ink'])
            d.polygon([(nx - 21, ny - 8), (nx, ny - 20), (nx + 21, ny - 8)], fill=p['ink'])
            d.rectangle([nx - 5, ny + 2, nx + 5, ny + 16], fill=p['paper'])
        else:
            d.line([(nx - 20, ny + 12), (nx, ny - 12), (nx + 20, ny + 12)], fill=p['ink'], width=5)
            d.line([(nx - 20, ny + 16), (nx + 20, ny + 16)], fill=p['ink'], width=3)
        d.ellipse([nx + 18, ny - 34, nx + 42, ny - 10], fill=(198, 82, 66))
        d.text((nx + 30, ny - 22), str(i + 1), font=font(15), fill=(255, 255, 255), anchor='mm')
    # 指北针
    cx, cy = W * .90, H * .86
    d.ellipse([cx - 26, cy - 26, cx + 26, cy + 26], fill=p['paper'], outline=p['c1'], width=2)
    d.polygon([(cx, cy - 20), (cx - 8, cy + 8), (cx, cy + 2), (cx + 8, cy + 8)], fill=(198, 82, 66))
    d.text((cx, cy - 34), 'N', font=font(13), fill=p['ink'], anchor='mm')
    # DAY 角标
    rr(d, [22, 20, 176, 58], 8, p['c1'])
    d.text((99, 39), 'DAY  ROUTE', font=font(18), fill=p['paper'], anchor='mm')
    label(d, name, prov, 'day', p)


DRAW = {'cover': draw_cover, 'wear': draw_wear, 'food': draw_food,
        'stay': draw_stay, 'route': draw_route, 'day': draw_day}


def main(argv=None):
    argv = argv or []
    start = int(argv[0]) if len(argv) > 0 else 0
    end = int(argv[1]) if len(argv) > 1 else 10 ** 9
    doc = json.loads(SRC.read_text(encoding='utf-8'))
    cities = doc['cities']
    if len(cities) != 410:
        raise SystemExit('期望 410 城，实际 %d' % len(cities))
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    # 分批生成时绝不删除已有产物：多批之间互不干扰，也不怕中途被打断重跑。

    manifest = []
    total_bytes = 0
    for i, c in enumerate(cities, 1):
        if i - 1 < start or i - 1 >= end:
            continue
        cid, name = str(c['id']), str(c.get('name') or '行迹')
        prov = str(c.get('prov') or c.get('province') or '')
        p = palette(c)
        for kind in KINDS:
            rnd = random.Random(seed_of(cid, name, kind))
            im = Image.new('RGB', (W, H), p['paper'])
            d = ImageDraw.Draw(im)
            DRAW[kind](d, p, rnd.random, name, prov)
            # 量化到调色板 PNG：纯色插画压缩后极小，2460 张也能整体控制体积
            q = im.quantize(colors=96, method=Image.MEDIANCUT, dither=Image.NONE)
            out = OUT_DIR / ('%s_%s.png' % (cid, kind))
            q.save(out, format='PNG', optimize=True)
            total_bytes += out.stat().st_size
        manifest.append({'id': cid, 'name': name, 'prov': prov,
                         'files': ['assets/img/scenes/%s_%s.png' % (cid, k) for k in KINDS]})
    if start == 0 and end >= len(cities):
        MANIFEST.write_text(json.dumps({'total': len(cities), 'kinds': KINDS,
                                        'size': [W, H], 'cities': manifest},
                                       ensure_ascii=False, indent=1), encoding='utf-8')
    n = len(manifest) * len(KINDS)
    print('本批 %d 城 → %d 张 PNG，共 %.2f MB，平均 %.1f KB/张'
          % (len(manifest), n, total_bytes / 1048576,
             total_bytes / n / 1024 if n else 0))


if __name__ == '__main__':
    import sys
    main(sys.argv[1:])
