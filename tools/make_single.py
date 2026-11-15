#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从 Pages 工程生成「双击即用」的单文件版。

用法：
    python3 tools/make_single.py [输出.html]

只产出一个文件：旅行灵感工作台.html

为什么后台不再做成第二个文件：
    上一版把后台做成「行迹_后台管理.html」，工作台点后台管理用 location.href
    跳过去。但在只托管单个 HTML 的预览 / 网盘 / 邮件附件环境里，第二个文件
    根本不存在，服务端直接返回 NoSuchKey —— 用户看到的就是「点后台管理报错」。

    现在把后台完整 HTML（含四份内联数据）用 base64 编进同一个文件，
    点「后台管理」时写进一个全屏 iframe 的 srcdoc：
      · URL 始终不变，绝不请求第二个文件
      · iframe 有独立 window / 全局词法环境，工作台的 const S 与后台的 var S
        不会撞车（document.write 整页替换会保留父全局词法环境，实测会报
        "Identifier 'S' has already been declared"，所以不能用 document.write）
      · srcdoc 继承父页 origin，localStorage 草稿照常互通；后台保存时还会
        postMessage 回传一份草稿双保险
      · 后台「↗ 返回工作台」用 postMessage 通知父页隐藏 iframe 并刷新

    base64 而不是直接塞 HTML 字符串：base64 字符集不含 '<'，
    不会出现 </script> 提前闭合外层脚本的经典坑。

注意：不改工程版任何代码，只做文本替换；每次改完工程重跑一次即可。
"""
import sys, pathlib, base64, re

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = pathlib.Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else ROOT.parent / "旅行灵感工作台.html"

WORK_EXTERNALS = [
    ('data/city-media.js',       '<script src="data/city-media.js"></script>'),
    ('scene-art.js',             '<script src="scene-art.js"></script>'),
    ('data/cities.js',           '<script src="data/cities.js"></script>'),
    ('data/cities.full.js',      '<script src="data/cities.full.js"></script>'),
    ('data/national-cities.js',  '<script src="data/national-cities.js"></script>'),
    ('data/plan-config.js',      '<script src="data/plan-config.js"></script>'),
    ('config.js',                '<script src="config.js"></script>'),
    ('libretts-bridge.js',       '<script src="libretts-bridge.js"></script>'),
]
ADMIN_EXTERNALS = [
    ('data/city-media.js',       '<script src="data/city-media.js"></script>'),
    ('data/cities.full.js',      '<script src="data/cities.full.js"></script>'),
    ('data/plan-config.js',      '<script src="data/plan-config.js"></script>'),
    ('data/national-cities.js',  '<script src="data/national-cities.js"></script>'),
    ('config.js',                '<script src="config.js"></script>'),
]
FILM_EXTERNALS = [
    ('data/city-media.js',       '<script src="data/city-media.js"></script>'),
    ('scene-art.js',             '<script src="scene-art.js"></script>'),
    ('data/cities.js',           '<script src="data/cities.js"></script>'),
    ('data/plan-config.js',      '<script src="data/plan-config.js"></script>'),
    ('data/national-cities.js',  '<script src="data/national-cities.js"></script>'),
    ('data/cities.full.js',      '<script src="data/cities.full.js"></script>'),
    ('config.js',                '<script src="config.js"></script>'),
    ('vendor/mp4-muxer.js',      '<script src="vendor/mp4-muxer.js"></script>'),
]


def inline(html, externals, label, overrides=None):
    overrides = overrides or {}
    for rel, tag in externals:
        if tag not in html:
            raise SystemExit('%s 找不到引用：%s（结构变了，请同步本脚本）' % (label, tag))
        src = overrides[rel] if rel in overrides else (ROOT / rel).read_text(encoding='utf-8')
        src = src.replace('</script', '<\\/script')
        html = html.replace(tag, '<script>\n/* ==== inline: %s ==== */\n%s\n</script>' % (rel, src), 1)
    left = [t for _, t in externals if t in html]
    if left:
        raise SystemExit('%s 仍有未内联的外部脚本引用：%s' % (label, ', '.join(left)))
    return html


def media_for_single():
    """工程版按相对路径读 assets/img/scenes/*.png；单文件没有同目录资源，
    把 2460 张题材图内联成 data URI，双击 file:// 也能立刻显示每一帧的配图。"""
    js = (ROOT / 'data' / 'city-media.js').read_text(encoding='utf-8')
    cache = {}

    def repl(m):
        rel = m.group(0)
        if rel not in cache:
            b = base64.b64encode((ROOT / rel).read_bytes()).decode('ascii')
            cache[rel] = 'data:image/png;base64,' + b
        return cache[rel]

    out = re.sub(r'assets/img/scenes/[A-Za-z0-9_\-]+\.png', repl, js)
    print('  单文件内联题材图：%d 张 → city-media.js %d 字节' % (len(cache), len(out.encode('utf-8'))))
    return out


# ---------- 1. 工作台：内联外部脚本 + 题材图 ----------
html = inline((ROOT / 'index.html').read_text(encoding='utf-8'), WORK_EXTERNALS, '工作台',
              overrides={'data/city-media.js': media_for_single()})

# ---------- 2. 后台：内联四份数据 + 把「返回工作台」改成通知父页 ----------
ADMIN_MEDIA_SHIM = ("/* 图像数据与工作台同源：从父页读取，避免单文件内重复内联 5 MB */\n"
                    "window.XJ_CITY_MEDIA = (window.parent && window.parent.XJ_CITY_MEDIA) "
                    "|| window.XJ_CITY_MEDIA || {cities:{}};")
admin = inline((ROOT / 'admin.html').read_text(encoding='utf-8'), ADMIN_EXTERNALS, '后台',
               overrides={'data/city-media.js': ADMIN_MEDIA_SHIM})
# 后台里定义一个「返回工作台」函数，iframe 内通知父页；顶层打开时直接 reload
back_fn = """<script>
function xjAdminBack(){
  try{if(window.parent!==window){parent.postMessage('xj_admin_back','*');}else{location.reload();}}
  catch(e){location.reload();}
}
</script>
</head>"""
if '</head>' not in admin:
    raise SystemExit('后台找不到 </head>')
admin = admin.replace('</head>', back_fn, 1)
for old, new in (
    ('href="index.html"', 'href="javascript:xjAdminBack()"'),
    ("location.href='index.html';", "xjAdminBack();"),
):
    if old not in admin:
        raise SystemExit('后台找不到返回工作台入口：' + old)
    admin = admin.replace(old, new, 1)
b64 = base64.b64encode(admin.encode('utf-8')).decode('ascii')

old_go = "function goAdmin(){location.href='admin.html';}"
if old_go not in html:
    raise SystemExit('找不到 goAdmin 定义（index.html 结构变了，请同步本脚本）')
new_go = """function goAdmin(){
  /* 后台整页内嵌进 iframe.srcdoc：URL 不变、不请求第二个文件、全局环境隔离 */
  var f=document.getElementById('xjAdminFrame');
  if(!f){
    f=document.createElement('iframe');f.id='xjAdminFrame';f.title='行迹 · 城市数据后台';
    f.setAttribute('style','position:fixed;inset:0;width:100vw;height:100vh;border:0;'
      +'z-index:2147483647;background:#f4f6f9;display:block');
    document.body.appendChild(f);
  }
  var b64="%s";
  var bin=atob(b64),u=new Uint8Array(bin.length);
  for(var i=0;i<bin.length;i++)u[i]=bin.charCodeAt(i);
  /* 与工程版一致：把当前城市与逐镜文案带进编译工作台，不两处各写一份数据。 */
  try{
    var tl=videoTimeline(),lines=tl.map(function(x){return sceneText(x);});
    var v=(window.__LIBRETTS&&window.__LIBRETTS.state)?window.__LIBRETTS.state.voice:'';
    var payload=JSON.stringify({cityId:(S.dest&&S.dest.id)||'',cityName:(S.dest&&S.dest.name)||'',
      lines:lines,voice:v,ratio:S.video.ratio,res:S.video.res,fps:+S.video.fps||24,
      format:S.video.format,ts:Date.now()});
    sessionStorage.setItem('xj_film_payload',payload);
    f.addEventListener('load',function(){
      try{f.contentWindow.sessionStorage.setItem('xj_film_payload',payload);
          f.contentWindow.postMessage({xj_film_payload:payload},'*');}catch(e){}
    },{once:true});
  }catch(e){}
  f.srcdoc=new TextDecoder('utf-8').decode(u);
  f.style.display='block';document.body.style.overflow='hidden';
}
window.addEventListener('message',function(ev){
  var d=ev.data;
  if(d==='xj_admin_back'){
    var f=document.getElementById('xjAdminFrame');
    if(f){f.style.display='none';f.srcdoc='';}
    document.body.style.overflow='';
    try{location.reload();}catch(e){}
  }else if(d&&d.type==='xj_draft'&&d.raw){
    try{localStorage.setItem('xj_admin_draft_v1',d.raw);}catch(e){}
  }
});""" % b64
html = html.replace(old_go, new_go, 1)

# ---------- 3. 逐帧成片工作台：同样整页内嵌，不请求第二个文件 ----------
# 成片工作台是工作台的 srcdoc iframe，同源：图像数据直接读父页，
# 不在单文件里重复内联第二份 5 MB 数据（工程版 film.html 仍读自己的文件）。
FILM_MEDIA_SHIM = ("/* 图像数据与工作台同源：从父页读取，避免单文件内重复内联 5 MB */\n"
                   "window.XJ_CITY_MEDIA = (window.parent && window.parent.XJ_CITY_MEDIA) "
                   "|| window.XJ_CITY_MEDIA || {cities:{}};")
film = inline((ROOT / 'film.html').read_text(encoding='utf-8'), FILM_EXTERNALS, '成片工作台',
              overrides={'data/city-media.js': FILM_MEDIA_SHIM})
film_b64 = base64.b64encode(film.encode('utf-8')).decode('ascii')
import re
m = re.search(r'function goFilm\(\)\{[\s\S]*?\n\}', html)
if not m:
    raise SystemExit('找不到 goFilm 定义（index.html 结构变了，请同步本脚本）')
old_film_go = m.group(0)
new_film_go = """function goFilm(){
  var payload=xjFilmPayload();
  try{sessionStorage.setItem('xj_film_payload',payload);}catch(e){}
  xjFilmUI('busy','准备导出…');
  var old=$('xjFilmFrame');if(old&&old.parentNode)old.parentNode.removeChild(old);
  var f=document.createElement('iframe');f.id='xjFilmFrame';f.title='行迹 · 成片导出';
  f.setAttribute('style','position:fixed;left:-9999px;top:0;width:2px;height:2px;opacity:0;border:0;pointer-events:none');
  document.body.appendChild(f);
  xjFilmWire(f,payload);
  var b64="%s";
  var bin=atob(b64),u=new Uint8Array(bin.length);
  for(var i=0;i<bin.length;i++)u[i]=bin.charCodeAt(i);
  f.srcdoc=new TextDecoder('utf-8').decode(u);
}
function xjFilmBack(){
  var f=document.getElementById('xjFilmFrame');
  if(f&&f.parentNode)f.parentNode.removeChild(f);
}
window.addEventListener('message',function(ev){
  if(ev.data==='xj_film_back') xjFilmBack();
});""" % film_b64
html = html.replace(old_film_go, new_film_go, 1)
OUT.write_text(html, encoding='utf-8')
print('已生成 %s  (%d 字节)' % (OUT, OUT.stat().st_size))
print('  工作台内联：' + '、'.join(x[0] for x in WORK_EXTERNALS))
print('  后台整页内嵌：%d 字节 → base64 %d 字符' % (len(admin.encode('utf-8')), len(b64)))
print('  成片工作台内嵌：%d 字节 → base64 %d 字符' % (len(film.encode('utf-8')), len(film_b64)))
print('  后台管理 = 全屏 iframe.srcdoc；导出成片 = 离屏 iframe 直接编译下载，不跳页')
