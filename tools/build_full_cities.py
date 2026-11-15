#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""行迹 · 全国城市完整规划数据生成器

输入：data/national-cities.json（410 城行政区划事实层）
输出：data/cities.full.json / data/cities.full.js

【口径，务必保留】
  * 行政区划名称 / 省份 / 大区 = 公开事实层，可列全。
  * 行程内容按「地域类型 × 城市」生成结构化行程：落点是「这一类地方」的
    场景类别，不是具体景点名；票价写「请核对」；坐标是示意点位。
  * 不编造具体景点名称、票价、营业时间、实测经纬度、来源链接。
  * 口径声明放在城市级 note / dataNote / source 字段，供「灵感来源」页与
    后台管理系统显示一次；不再把免责文字写进 tag / intro / 落点说明，
    因为那些字段会直接烧进视频画面，用户看到的应是正常行程。

【为什么这样设计】
  旧版 374 城是同一套 12 个场景复制粘贴、每条说明都挂【通用建议】，
  intro 里还写「本页是通用框架…」，视频封面直接把这段免责烧上去。
  这不是「准备好」，是把元信息当成内容。本版按气候带 / 大区 / 城市层级
  生成差异化的落点顺序、时长、时段建议、饮食与交通口径，并让 intro
  成为可直接朗读的口播文案。

【真实内容的唯一诚实路径】
  本仓库不预置真实 POI。后台管理系统「AI 采编」支持批量把框架城逐城
  升级为带公开资料检索的真实内容（用户本机调魔塔），导出并 push 后
  全站生效；也可逐城人工编辑或导入已核实数据。

【可配置】改本脚本的 PROFILE 模板或直接改 data/cities.full.json，重新执行：
        python3 tools/build_full_cities.py
        再把生成物 push 到仓库即全站生效。
"""
import json, os, hashlib, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, 'data', 'national-cities.json')
OUT_JSON = os.path.join(ROOT, 'data', 'cities.full.json')
OUT_JS = os.path.join(ROOT, 'data', 'cities.full.js')

# 城市级口径声明：只在这里出现，不进画面
DATA_NOTE = (
    '结构化行程：落点为场景类别而非具体景点名，票价与营业时间请出行前核对；'
    '坐标为示意点位（省级中心 + 稳定偏移），不是实测经纬度。'
    '可在后台管理系统逐城补真实内容，或用「AI 采编 · 批量补齐」升级后导出。'
)

# ---------------------------------------------------------------------------
# 地域画像：按气候带给出差异化的「这一类地方」。
# 不写具体景点名，只写场景类别 + 时段/季节建议。
# ---------------------------------------------------------------------------
PROFILES = {
    'north': {
        'label': '华北 / 中原',
        'tag': '3 天慢旅行 · 古城与面食',
        'scenes': [
            ('老城街巷', '老城区', '1.5h', 'culture|walk|photo', '从老城门一带起步，先把街巷格局走顺'),
            ('城市博物馆', '市中心', '1.5h', 'museum|history|rain', '用一小时把这座城的来龙去脉捋清楚'),
            ('钟鼓楼周边', '老城区', '1h', 'culture|photo', '看中轴对称的老城肌理，顺路找早午饭'),
            ('城墙与遗址公园', '老城区', '1.5h', 'history|walk|view', '沿旧城边界走一段，傍晚光线最稳'),
            ('本地早市', '市集周边', '1h', 'food|local', '早点趁热吃，比榜单更接近日常'),
            ('面食小馆', '老城区', '1h', 'food|local', '点一份本地做法的主食，看浇头与配菜'),
            ('园林或城市公园', '市中心', '1h', 'nature|walk|kid', '午后留白，节奏慢下来'),
            ('文创书店街区', '历史街区', '1.5h', 'culture|shop|rain', '适合避晒或躲雨的室内段'),
            ('近郊山水段', '近郊', '半天', 'nature|view|dayTrip', '留半天给城外，注意往返班次'),
            ('非遗与手作铺', '历史街区', '1.5h', 'culture|shop', '看本地手艺，问清是否可拍照'),
            ('夜间食街', '老城区', '2h', 'food|local|night', '把没吃到的那几样集中在夜里补齐'),
            ('夜景广场', '新城片区', '1h', 'night|view|photo', '收尾一晚，看灯光与人流'),
        ],
        'food': ['本地面食小馆', '街边早点', '家常炖菜', '夜市小食', '老字号点心', '茶饮与甜品'],
        'food_note': '北方以面食与炖煮为主，按当季点，别只照榜单',
        'season_tip': '春秋最舒服，夏天把户外段放到清晨与傍晚',
        'transport': '市内以地铁 + 步行为主；近郊段建议高铁或正规一日游',
    },
    'northeast': {
        'label': '东北',
        'tag': '3 天慢旅行 · 江畔与暖屋',
        'scenes': [
            ('老城街区', '老城区', '1.5h', 'culture|walk|photo', '从老街起步，看近代建筑与街巷尺度'),
            ('江畔步道', '滨水一带', '1.5h', 'view|walk|photo', '沿水一侧慢走，风大记得加一件'),
            ('城市博物馆', '市中心', '1.5h', 'museum|history|rain', '先从展陈里把城市脉络理清'),
            ('本地早市', '市集周边', '1h', 'food|local', '早市最见本地生活，趁热吃'),
            ('暖屋茶点', '老城区', '1h', 'food|local|rain', '冷天留一段室内，坐下来歇脚'),
            ('老工业街区', '老城区', '1.5h', 'culture|photo', '看厂房与铁路遗存，注意开放区域'),
            ('城市公园', '市中心', '1h', 'nature|walk|kid', '午后留白，冬季改室内'),
            ('森林或近郊自然', '近郊', '半天', 'nature|view|dayTrip', '留半天给城外，冬季确认路况'),
            ('文创书店街区', '历史街区', '1.5h', 'culture|shop|rain', '适合长冬里的室内段'),
            ('夜间食街', '老城区', '2h', 'food|local|night', '夜里补齐没吃到的几样'),
            ('观景高处', '近郊', '1h', 'view|photo', '找一处能俯瞰全城的开放视角'),
            ('夜景广场', '新城片区', '1h', 'night|view|photo', '收尾一晚，看灯光与人流'),
        ],
        'food': ['炖菜与锅物', '街边早点', '本地烧烤', '夜市小食', '冻品与甜点', '热饮与茶点'],
        'food_note': '分量偏大，建议两人点一份再追加；冬季以热食为主',
        'season_tip': '6–9 月最宜，冬季把户外段压缩到正午前后',
        'transport': '市内打车 + 步行；冬季近郊段务必确认班次与路况',
    },
    'south': {
        'label': '江南 / 华中',
        'tag': '3 天慢旅行 · 水巷与茶点',
        'scenes': [
            ('老城水巷', '老城区', '1.5h', 'culture|walk|photo', '沿旧街与水巷慢走，早上人最少'),
            ('园林或老宅', '历史街区', '1.5h', 'culture|history|photo', '看院落层次，避开正午强光'),
            ('城市博物馆', '市中心', '1.5h', 'museum|history|rain', '先把地方史理清，再看街巷'),
            ('茶楼与早点', '老城区', '1h', 'food|local', '坐下来吃一顿慢早点'),
            ('本地市集', '市集周边', '1h', 'food|local|walk', '看当季食材与本地买菜节奏'),
            ('书店与文创街', '历史街区', '1.5h', 'culture|shop|rain', '梅雨或暑热时的室内段'),
            ('滨水步道', '滨水一带', '1.5h', 'view|walk|photo', '傍晚沿水走，光线最软'),
            ('近郊古镇或山水', '近郊', '半天', 'nature|view|dayTrip', '留半天给城外，注意往返'),
            ('老字号点心', '老城区', '1h', 'food|local', '带一份路上吃'),
            ('夜间食街', '老城区', '2h', 'food|local|night', '把小吃分散到夜里'),
            ('夜游河段', '滨水一带', '1h', 'night|view|photo', '看灯光与倒影'),
            ('城市公园', '市中心', '1h', 'nature|walk|kid', '收尾留白'),
        ],
        'food': ['本地河鲜小馆', '茶点与早点', '时令家常菜', '夜市小食', '老字号糕点', '茶饮与甜品'],
        'food_note': '口味偏清鲜，按当季食材点；梅雨季留意食材供应',
        'season_tip': '3–5 月 / 9–11 月最宜，梅雨与夏热把户外挪到早晚',
        'transport': '老城以步行 + 公交为主；近郊段可高铁或城际',
    },
    'coastal': {
        'label': '沿海',
        'tag': '3 天慢旅行 · 水岸与市集',
        'scenes': [
            ('老城街巷', '老城区', '1.5h', 'culture|walk|photo', '从老城起步，先看街巷与骑楼'),
            ('滨水步道', '滨水一带', '1.5h', 'view|walk|photo', '沿水一侧慢走，日落前光线最好'),
            ('本地市集', '市集周边', '1h', 'food|local|walk', '早市看当季食材，趁热吃一顿'),
            ('城市博物馆', '市中心', '1.5h', 'museum|history|rain', '把开埠与地方史先理清'),
            ('观景高处', '近郊', '1h', 'view|photo', '找一处开阔视角看城与水'),
            ('文创书店街区', '历史街区', '1.5h', 'culture|shop|rain', '午后避晒的室内段'),
            ('老字号茶点', '老城区', '1h', 'food|local', '坐下来吃本地做法的点心'),
            ('近郊自然段', '近郊', '半天', 'nature|view|dayTrip', '留半天给城外，注意往返班次'),
            ('历史建筑街区', '历史街区', '1.5h', 'culture|history|photo', '看本地建筑与街巷格局'),
            ('夜间食街', '老城区', '2h', 'food|local|night', '夜里补齐没吃到的几样'),
            ('城市公园', '市中心', '1h', 'nature|walk|kid', '午后留白'),
            ('夜景广场', '新城片区', '1h', 'night|view|photo', '收尾一晚'),
        ],
        'food': ['当季水产小馆', '街边早点', '时令家常菜', '夜市小食', '老字号点心', '茶饮与甜品'],
        'food_note': '按当季水产点，问清时价；海风大，户外段带件薄外套',
        'season_tip': '4–6 月 / 9–11 月最宜，夏秋留意台风与强对流',
        'transport': '市内步行 + 公交 / 打车；滨海段留意末班车与天气',
    },
    'plateau': {
        'label': '高原 / 山地',
        'tag': '3 天慢旅行 · 山谷与慢节奏',
        'scenes': [
            ('老城街巷', '老城区', '1.5h', 'culture|walk|photo', '第一天先慢走适应节奏，别排太满'),
            ('城市博物馆', '市中心', '1.5h', 'museum|history|rain', '从展陈里理清地方与族群脉络'),
            ('本地市集', '市集周边', '1h', 'food|local|walk', '看当季物产与本地生活'),
            ('近郊观景段', '近郊', '半天', 'nature|view|dayTrip', '留半天给城外，注意往返与高差'),
            ('老字号茶点', '老城区', '1h', 'food|local', '坐下来喝一杯，放慢'),
            ('手作与非遗铺', '历史街区', '1.5h', 'culture|shop', '看本地手艺，问清是否可拍照'),
            ('城市公园', '市中心', '1h', 'nature|walk|kid', '午后留白，别连续赶点'),
            ('滨水步道', '滨水一带', '1.5h', 'view|walk|photo', '傍晚沿水走，光线最软'),
            ('观景高处', '近郊', '1h', 'view|photo', '找一处开阔视角，量力而行'),
            ('书店与文创街', '历史街区', '1.5h', 'culture|shop|rain', '天气变化时的室内段'),
            ('夜间食街', '老城区', '2h', 'food|local|night', '夜里补齐没吃到的几样'),
            ('夜景广场', '新城片区', '1h', 'night|view|photo', '收尾一晚'),
        ],
        'food': ['本地风味小馆', '街边早点', '牛羊肉与乳制品', '夜市小食', '老字号点心', '热茶与甜品'],
        'food_note': '高原昼夜温差大，以热食为主，第一天别吃太撑',
        'season_tip': '3–5 月 / 9–11 月最宜，紫外线强、早晚温差大',
        'transport': '市内打车 + 步行；近郊段建议包车或正规一日游，确认海拔与路况',
    },
    'tropical': {
        'label': '热带',
        'tag': '3 天慢旅行 · 绿荫与夜市',
        'scenes': [
            ('老城街巷', '老城区', '1.5h', 'culture|walk|photo', '清晨先走老街，避开正午日晒'),
            ('绿荫步道', '滨水一带', '1.5h', 'nature|walk|photo', '沿有遮阴的一段慢走'),
            ('本地市集', '市集周边', '1h', 'food|local|walk', '看热带水果与当季物产'),
            ('城市博物馆', '市中心', '1.5h', 'museum|history|rain', '午后避晒的室内段'),
            ('老字号茶点', '老城区', '1h', 'food|local', '坐下来吃本地做法的甜点'),
            ('文创书店街区', '历史街区', '1.5h', 'culture|shop|rain', '阵雨时的室内段'),
            ('滨水黄昏段', '滨水一带', '1.5h', 'view|photo', '傍晚出门，光线与温度都舒服'),
            ('近郊自然段', '近郊', '半天', 'nature|view|dayTrip', '留半天给城外，带足饮水'),
            ('历史建筑街区', '历史街区', '1.5h', 'culture|history|photo', '看本地建筑与街巷格局'),
            ('夜间食街', '老城区', '2h', 'food|local|night', '夜里最热闹，把小吃分散吃'),
            ('城市公园', '市中心', '1h', 'nature|walk|kid', '清晨或傍晚留白'),
            ('夜景广场', '新城片区', '1h', 'night|view|photo', '收尾一晚'),
        ],
        'food': ['当季水果与甜品', '街边早点', '清鲜家常菜', '夜市小食', '老字号点心', '冰饮与茶饮'],
        'food_note': '全年湿热，吃当季水果；正午尽量安排室内',
        'season_tip': '11–4 月最舒服，雨季随身带伞、留室内备选',
        'transport': '市内打车 + 步行；阵雨频繁，近郊段留机动时间',
    },
    'northwest': {
        'label': '西北',
        'tag': '3 天慢旅行 · 长日与夜市',
        'scenes': [
            ('老城街巷', '老城区', '1.5h', 'culture|walk|photo', '从老城起步，看街巷与院落'),
            ('城市博物馆', '市中心', '1.5h', 'museum|history|rain', '先把丝路与地方史理清'),
            ('本地市集', '市集周边', '1h', 'food|local|walk', '看干果、香料与当季物产'),
            ('历史遗存街区', '历史街区', '1.5h', 'culture|history|photo', '看旧城格局，注意参观礼仪'),
            ('老字号面食', '老城区', '1h', 'food|local', '坐下来吃一顿本地做法的主食'),
            ('观景高处', '近郊', '1h', 'view|photo', '找一处开阔视角，日落偏晚'),
            ('近郊自然与绿洲', '近郊', '半天', 'nature|view|dayTrip', '留半天给城外，带足饮水'),
            ('文创书店街区', '历史街区', '1.5h', 'culture|shop|rain', '风沙或强光时的室内段'),
            ('滨水步道', '滨水一带', '1.5h', 'view|walk|photo', '傍晚沿水走，日夜温差开始明显'),
            ('手作与非遗铺', '历史街区', '1.5h', 'culture|shop', '看本地手艺'),
            ('夜间食街', '老城区', '2h', 'food|local|night', '夜市是重头，慢慢吃'),
            ('夜景广场', '新城片区', '1h', 'night|view|photo', '收尾一晚'),
        ],
        'food': ['牛羊肉小馆', '面食与馕点', '当季瓜果', '夜市小食', '老字号点心', '热茶与甜品'],
        'food_note': '昼夜温差大，白天清淡、夜里热食；当季瓜果值得留一段',
        'season_tip': '5–10 月最宜，干燥少雨、紫外线强，日落比东部晚',
        'transport': '市内打车 + 步行；近郊段距离长，建议包车并确认返程',
    },
}

ZONE_BY_PROV = {
    '北京': 'north', '天津': 'north', '河北': 'north', '山西': 'north', '内蒙古': 'north',
    '辽宁': 'northeast', '吉林': 'northeast', '黑龙江': 'northeast',
    '上海': 'south', '江苏': 'south', '浙江': 'coastal', '安徽': 'south',
    '福建': 'coastal', '江西': 'south', '山东': 'coastal',
    '河南': 'north', '湖北': 'south', '湖南': 'south',
    '广东': 'coastal', '广西': 'coastal', '海南': 'tropical',
    '重庆': 'south', '四川': 'plateau', '贵州': 'south', '云南': 'plateau', '西藏': 'plateau',
    '陕西': 'northwest', '甘肃': 'northwest', '青海': 'plateau', '宁夏': 'northwest',
    '新疆': 'northwest', '台湾': 'coastal', '香港': 'coastal', '澳门': 'coastal',
}

ZONE_META = {
    'north':     ([180, 320, 620], '4–5 月 / 9–10 月', '温带季风气候，四季分明', '华北 / 中原 · 四季分明'),
    'northeast': ([190, 330, 640], '6–9 月', '温带季风气候，冬季漫长寒冷', '东北 · 冬长夏凉'),
    'south':     ([170, 300, 580], '3–5 月 / 9–11 月', '亚热带季风气候，梅雨与夏热明显', '江南 / 华中 · 湿润多雨'),
    'coastal':   ([200, 350, 680], '4–6 月 / 9–11 月', '海洋性气候，海风大、夏秋留意台风', '沿海 · 海风与台风'),
    'plateau':   ([180, 320, 620], '3–5 月 / 9–11 月', '高原气候，昼夜温差大、紫外线强', '高原 · 昼夜温差大'),
    'tropical':  ([210, 360, 720], '11–4 月', '热带季风气候，全年湿热多雨', '热带 · 全年夏装'),
    'northwest': ([160, 290, 560], '5–10 月', '温带大陆性气候，干燥少雨、昼夜温差大', '西北 · 干燥温差大'),
}

# 省级行政中心示意坐标（仅用于生成地图上的示意点位，不是实测景区坐标）
PROV_CENTER = {
    '北京': [39.90, 116.40], '天津': [39.12, 117.20], '河北': [38.04, 114.51],
    '山西': [37.87, 112.55], '内蒙古': [40.84, 111.75],
    '辽宁': [41.80, 123.43], '吉林': [43.88, 125.32], '黑龙江': [45.80, 126.53],
    '上海': [31.23, 121.47], '江苏': [32.06, 118.80], '浙江': [30.27, 120.15],
    '安徽': [31.86, 117.28], '福建': [26.07, 119.30], '江西': [28.68, 115.86],
    '山东': [36.65, 117.12], '河南': [34.75, 113.63], '湖北': [30.59, 114.30],
    '湖南': [28.23, 112.94], '广东': [23.13, 113.26], '广西': [22.82, 108.32],
    '海南': [20.04, 110.20], '重庆': [29.56, 106.55], '四川': [30.66, 104.06],
    '贵州': [26.65, 106.63], '云南': [25.04, 102.71], '西藏': [29.65, 91.13],
    '陕西': [34.34, 108.94], '甘肃': [36.06, 103.83], '青海': [36.62, 101.78],
    '宁夏': [38.49, 106.23], '新疆': [43.83, 87.62],
    '台湾': [25.03, 121.56], '香港': [22.32, 114.17], '澳门': [22.20, 113.54],
}

DAY_THEMES = [
    '第 1 天 · 老城与人文：街巷、博物馆、早点，先把节奏放慢',
    '第 2 天 · 自然与市集：本地市集、近郊半日、傍晚沿水慢走',
    '第 3 天 · 味道与收尾：手作街区、夜市、夜景，留一点空白',
]


def stable_offset(name, prov):
    """按城市名生成稳定偏移，保证每次生成坐标一致，且不会两城重合"""
    h = hashlib.md5((prov + '|' + name).encode('utf-8')).hexdigest()
    a = int(h[:8], 16) / 0xffffffff
    b = int(h[8:16], 16) / 0xffffffff
    return ((a - 0.5) * 1.6, (b - 0.5) * 2.0)


def city_seed(name, prov):
    return int(hashlib.md5((prov + '|' + name).encode('utf-8')).hexdigest()[:8], 16)


def build_city(n, baseline_ids):
    """baseline_ids: {名称|省份 -> cities.js 中的真实 id}
    基线 36 城必须复用 cities.js 的 id，否则后台导出的 cityOverrides / hiddenCityIds
    用 nat_xxx 做键，工作台 BASE_CITIES 用 beijing/dali 做键，覆盖层永远匹配不上。
    """
    name, prov, region = n['name'], n['prov'], n['region']
    zone = ZONE_BY_PROV.get(prov, 'north')
    budget, best, climate, zone_label = ZONE_META[zone]
    profile = PROFILES[zone]
    seed = city_seed(name, prov)
    base = PROV_CENTER.get(prov, [34.0, 108.0])
    dx, dy = stable_offset(name, prov)
    center = [round(base[0] + dx, 4), round(base[1] + dy, 4)]
    is_baseline = (name + '|' + prov) in baseline_ids

    # 按城市做稳定轮转：同类城市也不会是同一套顺序 / 同一批时段
    rot = seed % len(profile['scenes'])
    scenes = profile['scenes'][rot:] + profile['scenes'][:rot]
    spots = []
    for i, (sname, szone, dur, tags, desc) in enumerate(scenes):
        t = tags + ('|rain' if i % 7 == 3 else '')
        # 名称是「这一类地方」的场景类别，不是具体景点名
        spots.append([name + ' · ' + sname, szone, dur, '请核对', t, desc + '。'])

    food = []
    for i, f in enumerate(profile['food']):
        food.append([name + ' · ' + f, profile['food_note'] + '（' + ['早餐', '正餐', '时令', '夜宵', '伴手礼', '歇脚'][i] + '）',
                     ['早市 / 老街', '老城 / 本地小馆', '本地小馆', '夜市 / 食街', '老字号铺子', '街边茶铺'][i], '请核对'])
    stay = [
        [name + ' · 老城 / 历史街区', '景点与老店步行可达，晚上最方便', '请核对', '首次到访 · 慢游'],
        [name + ' · 交通枢纽周边', '抵达与次日出发省事，连锁选择多', '请核对', '换乘 · 预算'],
        [name + ' · 新城 / 商圈', '住宿较新、选择多，适合亲子与连住', '请核对', '舒适 · 亲子'],
    ]
    transport = [
        '🚄 抵达：' + name + '站 / 高铁站或机场，具体班次出行前核对',
        '🚗 ' + profile['transport'],
        '🕐 博物馆与热门馆常需提前 1–3 天预约，节假日排队明显',
        '☀️ ' + profile['season_tip'] + '；门票、营业与预约请按「灵感来源」页核对',
    ]

    # intro 是可以直接朗读的口播 / 封面文案，不写任何元说明
    intro = (
        '把' + name + '排成 3 天，不赶路。'
        + '第一天走' + spots[0][0] + '与' + spots[1][0] + '，'
        + '第二天留给' + spots[3][0] + '和近郊半日，'
        + '第三天以' + spots[9][0] + '收尾。'
        + profile['season_tip'] + '，' + profile['food_note'] + '。'
    )
    return {
        'id': baseline_ids.get(name + '|' + prov) or n['id'],
        'name': name,
        'prov': prov,
        'region': region,
        'en': name.upper() + ' · ' + prov.upper(),
        'emoji': n.get('emoji') or '📍',
        'g': n.get('g') or ['#3f6f63', '#8fb3a1'],
        'a': n.get('a') or '#3f6f63',
        'image': '',
        'tag': profile['tag'],
        'seasons': best,
        'days': '3 – 4 天',
        'climate': climate,
        'climateZone': zone,
        'climateZoneLabel': zone_label,
        'budget': list(budget),
        'center': center,
        'intro': intro,
        'tags': [name, '慢旅行', profile['label'], '3 天路线', '本地味道'],
        'spots': spots,
        'food': food,
        'stay': stay,
        'transport': transport,
        'dayThemes': list(DAY_THEMES),
        'sceneProfile': zone,
        'level': n.get('level', 'prefecture'),
        'tier': n.get('tier', 'index'),
        'contentStatus': 'generated',
        'confidence': 'generated',
        'baseline': is_baseline,
        'source': '行政区划事实层 + 按地域类型生成的结构化行程（非实测 POI）',
        'note': '坐标为示意点位（省级中心 + 稳定偏移），不是实测经纬度；内容均为通用场景类别',
        'dataNote': DATA_NOTE,
        'updated': '',
    }


def main():
    with open(SRC, encoding='utf-8') as f:
        nat = json.load(f)

    # 读取 cities.js 基线城名单（按 名称|省份 匹配），这些城在运行时仍用基线真实内容。
    baseline_ids = {}
    cities_js = os.path.join(ROOT, 'data', 'cities.js')
    if os.path.exists(cities_js):
        import re
        txt = open(cities_js, encoding='utf-8').read()
        for m in re.finditer(r"id:'([^']+)',\s*name:'([^']+)',\s*prov:'([^']+)'", txt):
            baseline_ids[m.group(2) + '|' + m.group(3)] = m.group(1)

    cities = [build_city(n, baseline_ids) for n in nat['cities']]

    # 唯一性硬校验
    ids, keys = set(), set()
    for c in cities:
        assert c['id'] not in ids, 'duplicate id: ' + c['id']
        assert c['name'] + '|' + c['prov'] not in keys, 'duplicate name+prov: ' + c['name']
        ids.add(c['id']); keys.add(c['name'] + '|' + c['prov'])
    # 差异化硬校验：不能所有城共用同一套落点顺序
    orders = {tuple(s[0].split(' · ')[1] for s in c['spots']) for c in cities}
    assert len(orders) >= 5, 'scene profiles not differentiated: %d orders' % len(orders)

    out = {
        'title': '行迹 · 全国 410 城完整规划数据（按地域类型生成的结构化行程）',
        'version': 2,
        'baseDate': nat.get('baseDate', '2026-11-09'),
        'total': len(cities),
        'baselineCount': len(baseline_ids),
        'generatedCount': len(cities) - len(baseline_ids),
        'profiles': {k: v['label'] for k, v in PROFILES.items()},
        'disclaimer': (
            '本文件为 410 城提供可直接生成行程 / 路线 / 衣食住行 / 地图 / 视频分镜的完整字段。'
            '其中 36 城（baseline=true）运行时仍优先使用 data/cities.js 的抓取快照与真实景点坐标；'
            '其余城按地域类型生成差异化行程：落点是「这一类地方」的场景类别而非具体景点名，'
            '票价写「请核对」，坐标是示意点位，不编造真实景点、票价、营业时间、实测经纬度与来源链接。'
            '口径声明只在城市级 note / dataNote / source 中，不写入会烧进画面的 tag / intro / 落点说明。'
            '真实内容请在后台管理系统逐城录入、导入已核实数据，或用「AI 采编 · 批量补齐」升级后导出覆盖。'
        ),
        'regions': nat['regions'],
        'provinces': nat['provinces'],
        'cities': cities,
    }
    with open(OUT_JSON, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=1)

    js = (
        '/* 行迹 · 全国 410 城完整规划数据 —— 由 tools/build_full_cities.py 生成\n'
        '   不要手工编辑；改 data/cities.full.json 或后台管理系统导出后覆盖本文件。\n'
        '   口径：按地域类型生成的结构化行程，不编造真实景点 / 票价 / 营业时间 / 实测坐标。 */\n'
        'window.XJ_CITIES_FULL = ' + json.dumps(out, ensure_ascii=False, separators=(',', ':')) + ';\n'
    )
    with open(OUT_JS, 'w', encoding='utf-8') as f:
        f.write(js)

    print('OK  total=%d baseline=%d generated=%d profiles=%d orders=%d json=%d KB js=%d KB' % (
        out['total'], out['baselineCount'], out['generatedCount'],
        len(PROFILES), len(orders),
        os.path.getsize(OUT_JSON) // 1024, os.path.getsize(OUT_JS) // 1024))
    return 0


if __name__ == '__main__':
    sys.exit(main())
