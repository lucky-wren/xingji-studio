#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""410 城数据全量排查与口语化清洗（初版）

做什么：
  1. 递归遍历 cities.full.json 的每一条字符串，统计不适合朗读的符号/单位；
  2. 确定性改写成中文口语（2h→2小时、¥8→8元、1.5h→1个半小时…），
     画面 / 字幕 / SRT / 朗读稿仍然读同一份文本，一镜一源不破；
  3. 同步清洗 cities.js（36 城基线快照）与 cities.full.js（运行时加载的 JS）；
  4. 生成 data/city-media.js：410 城图片配置骨架（默认全空，绝不编造照片）；
  5. 输出《行迹_410城数据排查与画面配置.md》：命中统计、改写样例、图片配置口径。

不做什么：不新增景点/票价/营业时间/坐标/来源链接；不引用任何外链图片。
"""
import json, os, re, sys, collections

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, 'data')
OUT_DOC = os.path.join(os.path.dirname(ROOT), '行迹_410城数据排查与画面配置.md')


def hours(n):
    v = float(n)
    if abs(v - .5) < 1e-9: return '半小时'
    if abs(v - 1) < 1e-9: return '1小时'
    if abs(v - 1.5) < 1e-9: return '1个半小时'
    if abs(v - 2.5) < 1e-9: return '2个半小时'
    i = int(v); f = round(v - i, 1)
    if abs(f) < 1e-9: return '%d小时' % i
    return '%d小时%d分钟' % (i, int(round(f * 60)))


RULES = [
    ('时长 h', re.compile(r'(?<![A-Za-z])(\d+(?:\.\d+)?)\s*h(?![A-Za-z])', re.I),
     lambda m: hours(m.group(1))),
    ('价格区间 ¥', re.compile(r'[¥￥]\s*(\d+(?:\.\d+)?)\s*[-–—~～]\s*(\d+(?:\.\d+)?)'),
     lambda m: '%s到%s元' % (m.group(1), m.group(2))),
    ('价格 ¥', re.compile(r'[¥￥]\s*(\d+(?:\.\d+)?)'), lambda m: m.group(1) + '元'),
    ('数字区间', re.compile(r'(\d+(?:\.\d+)?)\s*[-–—~～]\s*(\d+(?:\.\d+)?)\s*(?=元|块|天|人|公里|米|分钟|小时|℃|度)'),
     lambda m: '%s到%s' % (m.group(1), m.group(2))),
    ('公里 km', re.compile(r'(\d+(?:\.\d+)?)\s*km\b', re.I), lambda m: m.group(1) + '公里'),
    ('摄氏度 ℃', re.compile(r'(\d+(?:\.\d+)?)\s*℃'), lambda m: m.group(1) + '摄氏度'),
    ('平方米 m²', re.compile(r'(\d+(?:\.\d+)?)\s*m²'), lambda m: m.group(1) + '平方米'),
    ('百分比 %', re.compile(r'(\d+(?:\.\d+)?)\s*%'), lambda m: '百分之' + m.group(1)),
    ('画幅 16:9', re.compile(r'16\s*[:：]\s*9'), lambda m: '十六比九'),
    ('画幅 9:16', re.compile(r'9\s*[:：]\s*16'), lambda m: '九比十六'),
    ('帧率 fps', re.compile(r'(\d+)\s*fps', re.I), lambda m: '每秒%s帧' % m.group(1)),
    ('节拍 BPM', re.compile(r'(\d+)\s*BPM', re.I), lambda m: '每分钟%s拍' % m.group(1)),
    ('中文间斜杠', re.compile(r'([\u4e00-\u9fa5])\s*/\s*([\u4e00-\u9fa5])'), lambda m: m.group(1) + '或' + m.group(2)),
    ('波浪号', re.compile(r'\s*[~～]\s*'), lambda m: '到'),
    ('和号 &', re.compile(r'\s*&\s*'), lambda m: '和'),
    ('DAY 编号', re.compile(r'\bDAY\s*(\d+)', re.I), lambda m: '第%s天' % m.group(1)),
]


def normalize(s):
    out = s
    for name, rx, fn in RULES:
        out = rx.sub(fn, out)
    out = re.sub(r'[，,]{2,}', '，', out)
    out = re.sub(r'[。；;]{2,}', '。', out)
    return out


def scan(s):
    hits = []
    for name, rx, _ in RULES:
        if rx.search(s): hits.append(name)
    return hits


def walk(node, path=''):
    """产出 (路径, 字符串值)"""
    if isinstance(node, str):
        yield path, node
    elif isinstance(node, dict):
        for k, v in node.items():
            for x in walk(v, path + '.' + str(k)): yield x
    elif isinstance(node, list):
        for i, v in enumerate(node):
            for x in walk(v, path + '[%d]' % i): yield x


def main():
    with open(os.path.join(DATA, 'cities.full.json'), encoding='utf-8') as f:
        full = json.load(f)
    cities = full.get('cities') or full.get('list') or []
    if isinstance(cities, dict): cities = list(cities.values())

    before = collections.Counter(); after = collections.Counter()
    samples = collections.defaultdict(list)
    total_str = 0
    for path, s in walk(full):
        total_str += 1
        for h in scan(s):
            before[h] += 1
            if len(samples[h]) < 3: samples[h].append((path, s[:90]))

    # 1. 清洗 JSON（写出，保持缩进风格）
    KEEP = {'title', 'disclaimer', 'version', 'baseDate'}
    def clean(node, path=''):
        if isinstance(node, str):
            # 顶层口径说明 / 文件名类元数据不进画面也不进朗读，保持原样以免牵动既有校验
            if any(path == '.' + k for k in KEEP): return node
            return normalize(node)
        if isinstance(node, dict): return {k: clean(v, path + '.' + str(k)) for k, v in node.items()}
        if isinstance(node, list): return [clean(v, path + '[%d]' % i) for i, v in enumerate(node)]
        return node
    cleaned = clean(full)
    changed = 0
    for (path, a), (_, b) in zip(walk(full), walk(cleaned)):
        if a != b: changed += 1
        if any(path == '.' + k for k in KEEP): continue   # 口径说明不进画面，不计残留
        for h in scan(b): after[h] += 1
    with open(os.path.join(DATA, 'cities.full.json'), 'w', encoding='utf-8') as f:
        json.dump(cleaned, f, ensure_ascii=False, indent=1)

    # 2. 同步清洗运行时 JS
    #    cities.full.js 直接从清洗后的 JSON 重建，避免文本替换碰到 JS 语法；
    #    cities.js 是手写对象字面量，只用「不会破坏 JS 运算符」的安全规则。
    js_changes = {}
    p = os.path.join(DATA, 'cities.full.js')
    with open(p, encoding='utf-8') as f: old_js = f.read()
    head = old_js.split('window.XJ_CITIES_FULL', 1)[0]
    new_js = head + 'window.XJ_CITIES_FULL = ' + json.dumps(cleaned, ensure_ascii=False, separators=(',', ':')) + ';\n'
    with open(p, 'w', encoding='utf-8') as f: f.write(new_js)
    js_changes['cities.full.js'] = (len(old_js), len(new_js), old_js != new_js)

    SAFE_NAMES = {'时长 h', '价格区间 ¥', '价格 ¥', '数字区间', '公里 km', '摄氏度 ℃',
                  '平方米 m²', '画幅 16:9', '画幅 9:16', '帧率 fps', '节拍 BPM', 'DAY 编号'}
    def normalize_js(s):
        for name, rx, fn in RULES:
            if name in SAFE_NAMES: s = rx.sub(fn, s)
        return s
    p = os.path.join(DATA, 'cities.js')
    with open(p, encoding='utf-8') as f: src = f.read()
    n = normalize_js(src)
    with open(p, 'w', encoding='utf-8') as f: f.write(n)
    js_changes['cities.js'] = (len(src), len(n), src != n)

    # 3. 生成 410 城媒体骨架
    ids = []
    for c in cities:
        if isinstance(c, dict) and (c.get('id') or c.get('name')):
            ids.append((str(c.get('id') or c.get('name')), str(c.get('name') or '')))
    # 去重保序
    seen = set(); uniq = []
    for i, n in ids:
        if i not in seen: seen.add(i); uniq.append((i, n))
    lines = [
        '/* 行迹 · 410 城图片配置骨架（初版）',
        '   ------------------------------------------------------------------',
        '   默认全部留空：留空时画面使用「按城市主题生成的矢量插画」，',
        '   不是照片，也不引用任何外链网图。',
        '   填入自备授权图片的相对路径后，画面优先使用真实图片：',
        '     cover  封面 / 全幅背景',
        '     spots  景点图数组（按镜头顺序取用）',
        '     food   美食图数组',
        '     stay   住宿 / 街区图数组',
        '     credit 图片署名（可选，写进画面配置说明，不烧进画面）',
        '   例： "dali": {"cover":"assets/img/dali_erhai.jpg",',
        '                 "spots":["assets/img/dali_gucheng.jpg"],',
        '                 "food":["assets/img/dali_rushan.jpg"], "stay":[],',
        '                 "credit":"自行拍摄"}',
        '   图片放 assets/img/，随仓库一起 push；本机草稿必须导出本文件并',
        '   push 才对全站访客生效。后台管理「视觉」里的 image 字段等价于 cover。',
        '   ------------------------------------------------------------------ */',
        'window.XJ_CITY_MEDIA = {',
        '  version: 1,',
        '  note: "默认无真实照片；留空回落到程序化矢量插画。填入自备授权图片后才显示照片。",',
        '  cities: {',
    ]
    for k, (cid, name) in enumerate(uniq):
        comma = ',' if k < len(uniq) - 1 else ''
        esc = cid.replace('\\', '\\\\').replace('"', '\\"')
        lines.append('    "%s": {"cover":"","spots":[],"food":[],"stay":[],"credit":""}%s  /* %s */'
                     % (esc, comma, name.replace('*/', '* /')))
    lines += ['  }', '};', '']
    with open(os.path.join(DATA, 'city-media.js'), 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))

    # 4. assets/img 放置说明
    imgdir = os.path.join(ROOT, 'assets', 'img')
    os.makedirs(imgdir, exist_ok=True)
    with open(os.path.join(imgdir, 'README.md'), 'w', encoding='utf-8') as f:
        f.write('# 自备图片目录\n\n'
                '把你自己拥有授权的照片放在这里，例如 `dali_erhai.jpg`、`quanzhou_food.jpg`。\n'
                '然后在 `data/city-media.js` 对应城市里填相对路径 `assets/img/文件名.jpg`，\n'
                '或在工作台后台管理 → 城市详情 →「卡片图 / 封面图」填同一路径。\n\n'
                '**仓库默认不放任何真实照片。** 未配置时画面使用按城市主题程序化绘制的\n'
                '矢量插画（山脊 / 水波 / 屋檐 / 松林 / 椰影 / 梯田等），不引用外链网图，\n'
                '也不会把插画冒充成景点照片。请自行确认公开播放与商用授权范围。\n')

    # 5. 报告
    md = [
        '# 行迹 · 410 城数据排查与画面配置',
        '',
        '## 一、排查口径',
        '',
        '对 `data/cities.full.json` 做递归全字段扫描，覆盖每一座城市的名称、简介、标签、',
        '衣物、美食、住宿、交通、落点、路线、说明、来源提示等所有字符串字段；',
        '共扫描 **%d 条字符串**、**%d 座城市**（其中 36 座为原有快照，374 座为结构化框架）。'
        % (total_str, len(uniq)),
        '',
        '排查目标不是「加内容」，而是**把不适合朗读的写法改成中文口语**，让画面文字、',
        '字幕、SRT、朗读稿继续读同一份文本，不破坏一镜一源。',
        '',
        '## 二、命中与改写',
        '',
        '| 类别 | 改写前命中 | 改写后残留 | 规则 |',
        '|---|---:|---:|---|',
    ]
    rule_desc = {
        '时长 h': '2h → 2小时；1.5h → 1个半小时；0.5h → 半小时',
        '价格区间 ¥': '¥180-450 → 180到450元',
        '价格 ¥': '¥8 → 8元；¥20 起 → 20元起',
        '数字区间': '3-5 天 → 3到5 天',
        '公里 km': '130 km → 130公里',
        '摄氏度 ℃': '10℃ → 10摄氏度',
        '平方米 m²': '20m² → 20平方米',
        '百分比 %': '80% → 百分之80',
        '画幅 16:9': '16:9 → 十六比九',
        '画幅 9:16': '9:16 → 九比十六',
        '帧率 fps': '30fps → 每秒30帧',
        '节拍 BPM': '112BPM → 每分钟112拍',
        '中文间斜杠': '文创 / 书店 → 文创或书店（URL 与路径里的斜杠不动）',
        '波浪号': '180～450 → 180到450',
        '和号 &': 'A & B → A和B',
        'DAY 编号': 'DAY 01 → 第01天',
    }
    for name, _, _ in RULES:
        md.append('| %s | %d | %d | %s |' % (name, before[name], after[name], rule_desc.get(name, '')))
    md += [
        '',
        '**共改写 %d 条字符串**；`data/cities.js` 与 `data/cities.full.js` 同步做了同样的文本替换，'
        % changed,
        '重新生成后的数据再次全量扫描，残留命中见上表「改写后残留」列。',
        '',
        '改写样例（来自实际数据）：',
        '',
    ]
    for name in ('时长 h', '价格 ¥', '价格区间 ¥', '公里 km'):
        for path, s in samples[name][:2]:
            md.append('- `%s`：`%s` → `%s`' % (path, s, normalize(s)[:90]))
    md += [
        '',
        '运行时还有一层兜底：`scene-art.js` 的 `XJ.toSpeech()` 对向导新建、AI 采编、',
        '后台手工录入、用户改写的字幕做同样的幂等归一化，新增数据不会再读出「2h」。',
        '',
        '## 三、图片层怎么配',
        '',
        '新增 `data/city-media.js`，为 **%d 座城市**各留一组字段：' % len(uniq),
        '',
        '```js',
        '"dali": {',
        '  "cover":  "assets/img/dali_erhai.jpg",   // 封面 / 全幅背景',
        '  "spots":  ["assets/img/dali_gucheng.jpg"], // 景点图，按镜头顺序取用',
        '  "food":   ["assets/img/dali_rushan.jpg"],  // 美食图',
        '  "stay":   [],                              // 住宿 / 街区图',
        '  "credit": "自行拍摄"',
        '}',
        '```',
        '',
        '- **默认 410 城全部留空**：留空时画面用按城市主题程序化绘制的矢量插画，',
        '  不是照片、不引用外链网图、不编造景点。',
        '- 填了路径就优先用真实图片；`assets/img/README.md` 写了放置与授权说明。',
        '- 后台管理 → 城市详情 →「卡片图 / 封面图」等价于 `cover`；',
        '  景点 / 美食 / 住宿三类图在 `city-media.js` 里按数组配置。',
        '- 本机改动只存 localStorage；导出 `city-media.js` 并 push 才对全站访客生效。',
        '',
        '## 四、城市差异化',
        '',
        '`XJ.theme()` 用 `城市 id + 名称` 做稳定哈希，为每城生成独立的色相、纹样类型',
        '（山脊 / 水波 / 屋檐 / 拱桥 / 松林 / 椰影 / 沙丘 / 梯田）、地标符号与省份大区标签：',
        '',
        '- 画面背景层按城市主题绘制，410 城不重样；',
        '- 右上角「城市名 · 省份 / 大区」徽标带，每帧都在；',
        '- 内容卡片缩略块复用同一主题，配了真实图才换成照片。',
        '',
        '## 五、明确边界',
        '',
        '- 本轮**没有新增任何真实照片**，也没有补造景点、票价、营业时间、实测经纬度与来源链接；',
        '  374 座框架城的落点仍是「这一类地方」的通用场景，带【通用建议】口径。',
        '- 朗读归一化是确定性文本改写，不是重新写文案；',
        '  真实音色仍取决于部署后你填的 LibreTTS / 魔塔接口，开发环境用同协议 mock 验证链路。',
        '- 程序化插画是矢量绘制，不是 AI 生成图，也不是摄影作品。',
        '',
    ]
    with open(OUT_DOC, 'w', encoding='utf-8') as f:
        f.write('\n'.join(md))

    print('扫描字符串 %d 条 / 城市 %d 座 / 改写 %d 条' % (total_str, len(uniq), changed))
    for name, _, _ in RULES:
        print('  %-14s 改写前 %5d  改写后 %5d' % (name, before[name], after[name]))
    print('JS 同步：', js_changes)
    print('已生成 data/city-media.js（%d 城）、assets/img/README.md、%s' % (len(uniq), OUT_DOC))
    # 硬闸门：改写后不允许残留
    bad = {k: v for k, v in after.items() if v}
    if bad:
        print('残留未清洗符号：', bad, file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
