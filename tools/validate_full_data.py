#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""行迹 · 全国城市数据硬校验（CI 部署闸门 / 上线前自检）

用法：python3 tools/validate_full_data.py
失败 exit 1，绝不静默放过。

真源：data/cities.full.js —— 这是 index.html 实际 <script src> 加载的文件，
      也是后台管理系统导出后唯一覆盖的文件。校验必须针对它。
      data/cities.full.json 只是生成器的参考副本；后台导出后它与 JS 自然
      漂移（用户不会覆盖它），因此只做提醒，不阻断部署。

校验分两层，不要混为一谈：

  【硬错误】结构完整性 —— 坏数据一旦部署，页面会白屏或行程渲染异常。
    JS 可解析 / total 自洽 / 行政区划事实层完整覆盖 /
    基线城 id 与 cities.js 一致 / 必填字段 / id 唯一且合法 /
    同名同省唯一 / center 有效 / 落点·美食·住宿·交通条数 / 落点格式

  【提醒】内容口径 —— 后台逐城补真实内容后本来就该变化，不阻断部署。
    票价写「请核对」、标注【通用建议】、坐标示意声明、confidence=generated、
    cities.full.json 与 JS 不同源

历史教训：初版把「410 城 / 36 基线 / 票价必须请核对 / confidence 必须
generated / JS 必须与 JSON 逐字一致」写成硬错误，结果后台一新增城市、
补录真实票价或只导出 JS，CI 必红。上线闸门只该守运行时文件的结构，
不该守出厂默认值，也不该守一个页面根本不读的副本。
"""
import json, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JS = os.path.join(ROOT, 'data', 'cities.full.js')
J = os.path.join(ROOT, 'data', 'cities.full.json')
NAT = os.path.join(ROOT, 'data', 'national-cities.json')
BASE = os.path.join(ROOT, 'data', 'cities.js')

errs, warns = [], []


def chk(cond, msg):
    if not cond:
        errs.append(msg)


def note(msg):
    if msg not in warns:
        warns.append(msg)


def main():
    for p in (JS, NAT, BASE):
        chk(os.path.exists(p), '缺文件：' + p)
    if errs:
        print('\n'.join(errs))
        return 1

    js = open(JS, encoding='utf-8').read()
    nat = json.load(open(NAT, encoding='utf-8'))
    base_txt = open(BASE, encoding='utf-8').read()

    # 运行时真源：window.XJ_CITIES_FULL
    m = re.search(r'window\.XJ_CITIES_FULL\s*=\s*(\{.*\})\s*;', js, re.S)
    chk(bool(m), 'cities.full.js 未找到 window.XJ_CITIES_FULL')
    if not m:
        print('FAIL · ' + errs[-1])
        return 1
    try:
        data = json.loads(m.group(1))
    except Exception as e:
        print('FAIL · cities.full.js 解析失败：' + str(e))
        return 1

    # 参考副本只做提醒
    if os.path.exists(J):
        try:
            ref = json.load(open(J, encoding='utf-8'))
            if ref.get('cities') != data.get('cities'):
                note('cities.full.json 与运行时 JS 不同源（后台只导出 JS 属正常），页面以 JS 为准')
        except Exception:
            note('cities.full.json 无法解析，页面以 JS 为准')

    cities = data.get('cities', [])
    chk(isinstance(cities, list) and len(cities) >= 1, 'cities 不是非空数组')
    chk(data.get('total') == len(cities),
        'total(%s) 与 cities 长度(%d) 不一致' % (data.get('total'), len(cities)))
    chk(len(cities) >= len(nat['cities']),
        '城市数 %d 少于行政区划事实层 %d（全国数据被截断）' % (len(cities), len(nat['cities'])))

    # 行政区划事实层：410 城必须全部还在，允许后台在末尾追加自定义城
    nat_map = {(c['name'], c['prov']): c['region'] for c in nat['cities']}
    full_map = {(c['name'], c['prov']): c['region'] for c in cities}
    missing = [k for k in nat_map if k not in full_map]
    chk(not missing, '行政区划事实层缺城：' + ', '.join('%s(%s)' % k for k in missing[:8]))
    changed = [k for k in nat_map if k in full_map and full_map[k] != nat_map[k]]
    chk(not changed, '省份/大区与事实层不符：' + ', '.join('%s(%s)' % k for k in changed[:8]))

    # 基线城 id 必须与 cities.js 的真实 id 一致
    # 否则后台导出的 cityOverrides['nat_001'] 永远匹配不上工作台的 'beijing'
    base_ids = {}
    for mm in re.finditer(r"id:'([^']+)',\s*name:'([^']+)',\s*prov:'([^']+)'", base_txt):
        base_ids[mm.group(2) + '|' + mm.group(3)] = mm.group(1)
    for c in cities:
        if c.get('baseline'):
            expect = base_ids.get(c.get('name', '') + '|' + c.get('prov', ''))
            chk(expect is not None and c.get('id') == expect,
                '基线城 %s 的 id「%s」与 cities.js 的「%s」不一致（后台覆盖层会失效）'
                % (c.get('name'), c.get('id'), expect))

    ids, keys = set(), set()
    required = ['id', 'name', 'prov', 'region', 'center', 'intro', 'tags', 'spots',
                'food', 'stay', 'transport', 'climateZone', 'budget', 'emoji', 'g', 'a']
    n_real_price = 0
    for c in cities:
        nm = c.get('name', '?')
        for k in required:
            chk(k in c, '%s 缺字段 %s' % (nm, k))
        cid = c.get('id', '')
        chk(cid not in ids, 'id 重复：' + str(cid))
        ids.add(cid)
        key = str(c.get('name', '')) + '|' + str(c.get('prov', ''))
        chk(key not in keys, '同名同省重复：' + key)
        keys.add(key)
        chk(re.match(r'^[a-z0-9_-]{2,40}$', str(cid)) is not None, 'id 非法：' + str(cid))
        chk(isinstance(c.get('center'), list) and len(c['center']) == 2 and
            all(isinstance(x, (int, float)) for x in c['center']),
            nm + ' center 无效')
        for field, n in (('spots', 12), ('food', 6), ('stay', 3), ('transport', 4)):
            chk(isinstance(c.get(field), list) and len(c[field]) == n,
                '%s %s 数 %s != %d' % (nm, field, len(c.get(field) or []), n))
        for i, s in enumerate(c.get('spots') or []):
            chk(isinstance(s, list) and len(s) == 6,
                '%s spots[%d] 不是 6 项紧凑格式' % (nm, i))
            if isinstance(s, list) and len(s) == 6:
                chk(bool(s[0]), '%s spots[%d] 无名称' % (nm, i))
                if s[3] != '请核对':
                    n_real_price += 1
                # 口径声明不再写进落点说明：那些文案会直接烧进视频画面。
                # 逐条免责在旧版造成 9841 处「【通用建议】」糊在画面上，
                # 现在只保留在城市级 dataNote / note / source。
        visible = str(c.get('intro', '')) + str(c.get('tag', '')) + ' '.join(
            str(x[5]) for x in (c.get('spots') or []) if isinstance(x, list) and len(x) == 6)
        bad_words = ('【通用建议】', '待补真实内容', '本页是', '结构化通用行程框架')
        chk(not any(w in visible for w in bad_words),
            nm + ' 可见行程文案含数据口径免责文字（会烧进视频画面）')
        if not c.get('baseline'):
            if not c.get('dataNote'):
                note(nm + ' 缺城市级 dataNote 口径声明（后台导出可补）')
            if not c.get('sceneProfile'):
                note(nm + ' 缺地域画像 sceneProfile（建议补齐差异化行程）')
        conf = c.get('confidence')
        chk(conf in ('fact', 'generated', 'suggestion', 'edited', 'imported'),
            nm + ' confidence 非法：' + str(conf))
        if not c.get('baseline') and conf != 'generated':
            note('有生成城已在后台编辑（confidence=' + str(conf) + '），属正常内容维护')
        if not c.get('baseline') and c.get('contentStatus') != 'generated':
            note('有生成城 contentStatus 已变更，属正常内容维护')
        if 'note' not in c or '示意' not in str(c.get('note', '')):
            note('有城市未声明坐标为示意点位（若已填实测坐标请忽略）')

    if n_real_price:
        note('%d 条落点已补真实票价，请确认来源已核对' % n_real_price)

    for w in warns:
        print('  [提醒] ' + w)
    if errs:
        print('FAIL · %d 项错误' % len(errs))
        for e in errs[:40]:
            print('  - ' + e)
        if len(errs) > 40:
            print('  … 其余 %d 条省略' % (len(errs) - 40))
        return 1
    n_base = sum(1 for c in cities if c.get('baseline'))
    print('OK  · %d 城（基线 %d / 生成 %d）/ 事实层全覆盖 / 字段齐全 / 无重复 / 基线 id 一致 / 运行时 JS 可解析'
          % (len(cities), n_base, len(cities) - n_base))
    return 0


if __name__ == '__main__':
    sys.exit(main())
