#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""行迹 · 规划配置 CI 硬闸门

用法：
    python3 tools/validate_plan_config.py data/plan-config.js
    python3 tools/validate_plan_config.py data/plan-config.js --json

检查不通过 → exit 1，Actions 应据此中止部署。
只校验「配置层」，不碰 cities.js 基线、不碰视频合成。
"""
import sys, json, re, pathlib, argparse

ROOT = pathlib.Path(__file__).resolve().parent.parent
BASE_JS = ROOT / 'data/cities.js'


def extract(text):
    """从 window.XJ_PLAN_CONFIG = {...}; 里取出 JSON 对象。

    默认配置文件顶部有块注释；工作台导出的文件也带块注释头。
    对象本身要求严格 JSON（键与字符串都用双引号），这样 CI 校验与
    浏览器加载读的是同一份语法，不会出现「页面能跑、CI 解析不了」。"""
    text = re.sub(r'/\*.*?\*/', '', text, flags=re.S)          # 去块注释
    lines = [ln for ln in text.splitlines() if not ln.strip().startswith('//')]
    text = '\n'.join(lines)
    m = re.search(r'window\.XJ_PLAN_CONFIG\s*=\s*', text)
    if not m:
        raise ValueError('找不到 window.XJ_PLAN_CONFIG = ')
    body = text[m.end():].strip()
    if body.endswith(';'):
        body = body[:-1].strip()
    try:
        return json.loads(body)
    except json.JSONDecodeError:
        body2 = re.sub(r',\s*([}\]])', r'\1', body)             # 容错尾随逗号
        return json.loads(body2)


def base_ids():
    if not BASE_JS.exists():
        return None
    s = BASE_JS.read_text(encoding='utf-8')
    return set(re.findall(r'\bid\s*:\s*[\'"]([^\'"]+)[\'"]', s))


def city_key(c):
    return (str(c.get('name', '')).strip() + '|' + str(c.get('prov', '')).strip()).lower().replace(' ', '')


COLOR_RE = re.compile(r'^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$')
REQUIRED = ['id', 'name', 'prov', 'region', 'center', 'tag', 'intro', 'tags',
            'budget', 'climateZone', 'spots', 'food', 'stay', 'transport']


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('file', nargs='?', default=str(ROOT / 'data/plan-config.js'))
    ap.add_argument('--json', action='store_true')
    args = ap.parse_args()

    errs, warns, stats = [], [], {}
    p = pathlib.Path(args.file)
    try:
        cfg = extract(p.read_text(encoding='utf-8'))
    except Exception as e:
        errs.append('配置无法解析：%s' % e)
        cfg = {}

    if not isinstance(cfg, dict):
        errs.append('顶层必须是对象')
        cfg = {}

    # 顶层结构
    for k, t in [('theme', dict), ('cityOverrides', dict), ('hiddenCityIds', list),
                 ('customCities', list), ('regions', list), ('sections', dict), ('texts', dict)]:
        if k in cfg and not isinstance(cfg[k], t):
            errs.append('字段 %s 类型应为 %s' % (k, t.__name__))
            cfg[k] = t()

    theme = cfg.get('theme', {}) or {}
    overrides = cfg.get('cityOverrides', {}) or {}
    hidden = cfg.get('hiddenCityIds', []) or []
    customs = cfg.get('customCities', []) or []
    regions = cfg.get('regions', []) or []

    # 颜色值
    for k in ['paper', 'card', 'ink', 'ink2', 'mute', 'line', 'accent', 'accent2', 'accentSoft']:
        v = theme.get(k, '')
        if v and not COLOR_RE.match(str(v)):
            errs.append('theme.%s 不是合法颜色：%r（应为 #rgb / #rrggbb / 空）' % (k, v))

    ov = theme.get('bgOverlay', 0)
    try:
        if not 0 <= float(ov) <= .9:
            errs.append('theme.bgOverlay 必须在 0–0.9')
    except (TypeError, ValueError):
        errs.append('theme.bgOverlay 不是数字')

    # 引用完整性
    ids = base_ids()
    if ids:
        unknown_h = [x for x in hidden if x not in ids]
        unknown_o = [x for x in overrides if x not in ids and
                     not any(c.get('id') == x for c in customs)]
        if unknown_h:
            errs.append('hiddenCityIds 引用了不存在的基线 id：%s' % ', '.join(map(str, unknown_h[:5])))
        if unknown_o:
            errs.append('cityOverrides 引用了不存在的 id：%s' % ', '.join(map(str, unknown_o[:5])))
        if ids and len(hidden) >= len(ids):
            errs.append('hiddenCityIds 不能把全部基线城市都隐藏（%d/%d）' % (len(hidden), len(ids)))
    else:
        warns.append('找不到 data/cities.js，跳过 id 引用完整性检查')

    if len(set(hidden)) != len(hidden):
        errs.append('hiddenCityIds 有重复 id')

    # 自定义城 schema 与去重
    keys = {}
    for i, c in enumerate(customs):
        if not isinstance(c, dict):
            errs.append('customCities[%d] 不是对象' % i); continue
        miss = [k for k in REQUIRED if c.get(k) in (None, '', [])]
        if miss:
            errs.append('customCities[%d]（%s）缺字段：%s' % (i, c.get('name', '?'), '、'.join(miss)))
        if not re.match(r'^[a-z0-9_-]{2,32}$', str(c.get('id', ''))):
            errs.append('customCities[%d].id 非法：%r' % (i, c.get('id')))
        k = city_key(c)
        if k in keys:
            errs.append('customCities 重复：%s（索引 %d 与 %d）' % (k, keys[k], i))
        else:
            keys[k] = i
        for j, s in enumerate(c.get('spots', []) or []):
            if not isinstance(s, list) or len(s) < 6:
                errs.append('customCities[%d].spots[%d] 应为六项数组' % (i, j))

    # 大区
    if '全部' in regions:
        warns.append('regions 里不需要写「全部」，运行时会自动加')
    if len(set(regions)) != len(regions):
        errs.append('regions 有重复项')

    # 图片体积
    blob = p.read_text(encoding='utf-8')
    data_urls = re.findall(r'data:image/[^\'"]+', blob)
    stats['dataUrlImages'] = len(data_urls)
    if len(blob) > 2 * 1024 * 1024:
        warns.append('配置文件 %.1f MB，含内嵌图片；建议放 assets/ 并填相对路径' % (len(blob) / 1048576))

    stats.update({
        'file': str(p), 'bytes': len(blob.encode('utf-8')),
        'themeKeys': len([k for k, v in theme.items() if v not in ('', None, 0)]),
        'overrides': len(overrides), 'hidden': len(hidden),
        'customCities': len(customs), 'regions': len(regions),
        'errors': len(errs), 'warnings': len(warns),
    })

    if args.json:
        print(json.dumps({'ok': not errs, 'errors': errs, 'warnings': warns, 'stats': stats},
                         ensure_ascii=False, indent=2))
    else:
        print('行迹 · 规划配置校验：%s' % ('✓ 通过' if not errs else '✖ 未通过'))
        for k, v in stats.items():
            print('  %-16s %s' % (k, v))
        for w in warns:
            print('  [warn] ' + w)
        for e in errs:
            print('  [ERROR] ' + e)
    return 1 if errs else 0


if __name__ == '__main__':
    sys.exit(main())
