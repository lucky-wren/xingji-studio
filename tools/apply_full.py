#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把「全国 410 城完整规划数据」接入工作台（一次性补丁，逐项幂等）

从干净的 index.html 执行：python3 tools/apply_full.py
每一项都用「新内容特征」判断是否已应用，避免二次执行重复插入。
"""
import os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(ROOT, 'index.html')
s = open(P, encoding='utf-8').read()
orig_len = len(s.encode())


def rep(old, new, label, marker):
    """marker 出现在结果里即视为已应用"""
    global s
    if marker in s:
        print('SKIP  ' + label + ' (already applied)')
        return
    n = s.count(old)
    if n != 1:
        print('ERROR ' + label + ' anchor count=' + str(n)); sys.exit(1)
    s = s.replace(old, new, 1)
    print('OK    ' + label)


# 1) 加载全量数据文件
rep('<script src="data/national-cities.js"></script>',
    '<script src="data/national-cities.js"></script>\n'
    '<script src="data/cities.full.js"></script>',
    '加载 data/cities.full.js',
    '<script src="data/cities.full.js"></script>')

# 2) 在 36 城基线之后合并 374 城完整规划 + 后台草稿钩子
anchor = 'D2.forEach(function(c){D.push(normalizeCity(c));});'
block = anchor + r'''

/* ============================================================
   全国 410 城完整规划数据（data/cities.full.js）
   ------------------------------------------------------------
   36 城基线来自 data/cities.js（抓取快照 + 真实景点坐标）；其余 374 城
   来自 cities.full.js，是「结构化通用行程框架」：落点名称是这一类地方、
   票价写「请核对」、坐标为示意点位，不编造真实景点 / 票价 / 营业时间 /
   实测经纬度 / 来源链接。后台管理系统 admin.html 可逐城增删改查，
   导出后覆盖本文件 → git push → 全站生效。
   ============================================================ */
var XJ_FULL_DATA = window.XJ_CITIES_FULL || { cities: [] };
var XJ_FULL_CITIES = XJ_FULL_DATA.cities || [];
var XJ_ADMIN_KEY = 'xj_admin_draft_v1';
(function () {
  var have = {};
  D.forEach(function (d) { have[String(d.name) + '|' + String(d.prov)] = 1; });
  XJ_FULL_CITIES.forEach(function (c) {
    if (c.baseline) return;                 /* 基线 36 城仍用 cities.js 真实内容 */
    var k = String(c.name) + '|' + String(c.prov);
    if (have[k]) return;
    have[k] = 1;
    try {
      D.push(Object.assign(normalizeCity(c), {
        fromFull: true, generated: true, confidence: 'generated',
        contentStatus: 'generated', fullNote: c.note || ''
      }));
    } catch (e) { /* 单城数据异常不阻断整站 */ }
  });
})();

/* 后台草稿：admin.html 的每次编辑同时写 localStorage（同源实时预览），
   导出文件并 push 后才对所有访客生效。草稿在 PlanConfig.apply() 末尾应用，
   因此刷新 / 删除 / 恢复 / 去重之后都不会被重建覆盖。 */
function xjAdminDraft() {
  try {
    var raw = localStorage.getItem(XJ_ADMIN_KEY);
    var o = raw ? JSON.parse(raw) : {};
    return (o && typeof o === 'object') ? o : {};
  } catch (e) { return {}; }
}
function xjAdminCity(c) {
  if (!c || !c.id) return null;
  try {
    if (Array.isArray(c.spots) && c.spots[0] && c.spots[0].length <= 6)
      return Object.assign(normalizeCity(c), { fromAdmin: true });
    return Object.assign({}, c, { fromAdmin: true });
  } catch (e) { return null; }
}
function xjApplyAdminDraft() {
  var d = xjAdminDraft(), removed = {};
  (d.removed || []).forEach(function (id) { removed[id] = 1; });
  if (Object.keys(removed).length) {
    for (var i = D.length - 1; i >= 0; i--) if (removed[D[i].id]) D.splice(i, 1);
  }
  Object.keys(d.overrides || {}).forEach(function (id) {
    var o = xjAdminCity(d.overrides[id]); if (!o) return;
    var idx = -1;
    for (var j = 0; j < D.length; j++) if (D[j].id === id) { idx = j; break; }
    if (idx >= 0) D[idx] = Object.assign({}, D[idx], o); else D.push(o);
  });
  (d.added || []).forEach(function (c) {
    var o = xjAdminCity(c); if (!o) return;
    var exists = false;
    for (var j = 0; j < D.length; j++) if (D[j].id === o.id) { exists = true; break; }
    if (!exists) D.push(o);
  });
}'''
rep(anchor, block, '合并 410 城 + 后台草稿钩子', 'var XJ_FULL_DATA = window.XJ_CITIES_FULL')

# 3) PlanConfig.apply() 末尾应用草稿
rep('    CityStore.apply();\n\n    /* 4) 大区顺序 / 主题 */',
    '    CityStore.apply();\n'
    '    if (typeof xjApplyAdminDraft === \'function\') xjApplyAdminDraft();\n\n'
    '    /* 4) 大区顺序 / 主题 */',
    'PlanConfig.apply 挂接后台草稿',
    "if (typeof xjApplyAdminDraft === 'function') xjApplyAdminDraft();")

# 4) 城市库：已内置的城直接切过去，不再走向导复制一份
old_add = r'''function xjLibAddSelected(){
 var keys=Object.keys(XJ_LIB.sel);
 if(!keys.length){var m=document.getElementById('xjLibMsg');if(m)m.textContent='✖ 请先点左侧城市 chip 选中一座';return;}
 var k=decodeURIComponent(keys[0]),parts=k.split('|'),all=xjLibAll();
 var c=all.filter(function(x){return x.name+'|'+x.province===k;})[0]||{name:parts[0],province:parts[1]||'',region:''};
 if(typeof WIZ==='undefined'){return;}
 WIZ.name=c.name;WIZ.code='';WIZ.prov=c.province||'';
 WIZ.region=(c.region&&c.region!=='全部')?c.region:'华东';
 WIZ.impression='';WIZ.spots='';WIZ.food='';WIZ.stay='';WIZ.days=3;WIZ.tab='wizard';
 xjCloseLib();
 if(typeof wizardAdd==='function')wizardAdd();   /* 内部已 pickDest / rebuildTrip / switchTab('route') */
}'''
new_add = r'''function xjLibAddSelected(){
 var keys=Object.keys(XJ_LIB.sel);
 if(!keys.length){var m=document.getElementById('xjLibMsg');if(m)m.textContent='✖ 请先点左侧城市 chip 选中一座';return;}
 var k=decodeURIComponent(keys[0]),parts=k.split('|'),all=xjLibAll();
 var c=all.filter(function(x){return x.name+'|'+x.province===k;})[0]||{name:parts[0],province:parts[1]||'',region:''};
 /* 410 城已在启动时内置完整规划：直接切换，不再走向导复制出一条重复城市 */
 var hit=D.filter(function(d){return d.name===c.name&&(!c.province||d.prov===c.province);})[0];
 xjCloseLib();
 if(hit){
  try{pickDest(hit.id);switchTab('route');navFlash('p-route');}catch(e){}
  var txt='✓ 「'+c.name+'」已内置完整规划（'+hit.spots.length+' 个落点 / '
   +hit.food.length+' 组美食 / '+hit.stay.length+' 个住宿区）。可直接查看行程与成片；'
   +'要替换成真实景点与票价，请到「⚙ 后台管理」逐城编辑。';
  CITY_MSG={text:txt,ok:true};
  if(typeof renderCityModal==='function')renderCityModal();
  var m2=$('cityMsg');if(m2)m2.textContent=txt;
  toast('已切到 '+c.name+' · 完整行程已就绪');
  return;
 }
 /* 兜底：仅当库里出现尚未内置的新城时，才走已验证的向导生成路径 */
 if(typeof WIZ==='undefined'){return;}
 WIZ.name=c.name;WIZ.code='';WIZ.prov=c.province||'';
 WIZ.region=(c.region&&c.region!=='全部')?c.region:'华东';
 WIZ.impression='';WIZ.spots='';WIZ.food='';WIZ.stay='';WIZ.days=3;WIZ.tab='wizard';
 if(typeof wizardAdd==='function')wizardAdd();
}'''
rep(old_add, new_add, '城市库改为直接切到已内置城', '已内置完整规划（')

# 5) 顶栏：后台管理入口
rep('<button onclick="openCityModal();closeDrops()">＋ 城市数据</button>',
    '<button onclick="openCityModal();closeDrops()">＋ 城市数据</button>\n'
    '        <button onclick="window.open(\'admin.html\',\'_blank\');closeDrops()">⚙ 后台管理 · 城市 CRUD</button>',
    '顶栏加入后台管理入口',
    "⚙ 后台管理 · 城市 CRUD")

# 6) 数量文案（只在未改过时替换）
if '<span id="topCityCount">410 城</span>' not in s:
    s = s.replace('<span id="topCityCount">36 城</span>', '<span id="topCityCount">410 城</span>', 1)
if '· 410 座目的地' not in s:
    s = s.replace('· 36 座目的地', '· 410 座目的地', 1)
s = s.replace('/* 36 城基线快照，删除/恢复都靠它 */', '/* 410 城基线快照，删除/恢复都靠它 */', 1)
if 'data/cities.full.js</code>（全国 410 城完整规划）' not in s:
    s = s.replace(
        '城市素材在 <code>data/cities.js</code>，栏目结构在 <code>config.js</code>',
        '城市素材在 <code>data/cities.js</code>（36 城快照）与 '
        '<code>data/cities.full.js</code>（全国 410 城完整规划），栏目结构在 <code>config.js</code>', 1)
    s = s.replace('导出 <code>cities.js</code> 再 push',
                  '导出 <code>cities.full.js</code> / <code>plan-config.js</code> 再 push（或去「⚙ 后台管理」编辑）', 1)
s = s.replace('410 城 · 索引 / 导入 / 导出配置', '410 城 · 已内置完整行程', 1)

open(P, 'w', encoding='utf-8').write(s)
print('\nindex.html %d -> %d bytes (%+d)' % (orig_len, len(s.encode()),
                                            len(s.encode()) - orig_len))
