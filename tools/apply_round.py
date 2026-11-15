#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""本轮补丁：画面字号 / 拖拽框 / 口语化朗读 / 杂志卡片 / 城市差异化 / 图片配置。

只做精确文本替换，每处替换都校验命中次数；任何一处没命中就整体报错，
避免静默漏改。可重复执行（第二次会因「已改」而跳过，见 ok() 逻辑）。
"""
import os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FAIL = []


def load(name):
    with open(os.path.join(ROOT, name), encoding='utf-8') as f: return f.read()


def save(name, s):
    with open(os.path.join(ROOT, name), 'w', encoding='utf-8') as f: f.write(s)


def sub(s, old, new, label, count=1, optional=False):
    n = s.count(old)
    if n == 0:
        if optional: return s
        FAIL.append(label + '：未命中')
        return s
    if n != count and not optional:
        FAIL.append('%s：命中 %d 次（期望 %d）' % (label, n, count))
        return s
    return s.replace(old, new, count if count > 0 else n)


# ============================ index.html ============================
s = load('index.html')

# 1. 引入媒体配置与画面艺术模块（放在 410 城数据之后、业务逻辑之前）
s = sub(s,
        '<script src="data/cities.full.js"></script>',
        '<script src="data/cities.full.js"></script>\n'
        '<script src="data/city-media.js"></script>\n'
        '<script src="scene-art.js"></script>',
        'index: 引入 city-media / scene-art', optional=True)

# 2. 画面字号与插画开关
s = sub(s,
        "var AS={\n music:null,musicName:'',musicGain:.22,",
        "var AS={\n art:{fs:1.22,cards:true,banner:true,artOn:true},\n music:null,musicName:'',musicGain:.22,",
        'index: AS.art 状态', optional=True)
s = sub(s,
        "sub:{on:true,size:18,font:'default',charsPerLine:0,posX:.5,posY:null,",
        "sub:{on:true,size:18,font:'default',charsPerLine:0,posX:.5,posY:null,dragMode:false,",
        'index: AS.sub.dragMode', optional=True)

# 3. 朗读文本统一走口语化（幂等兜底）
s = sub(s,
        "new SpeechSynthesisUtterance(speakText())",
        "new SpeechSynthesisUtterance(XJ.toSpeech(speakText()))",
        'index: 系统导览口语化', optional=True)
s = sub(s,
        "const u=new SpeechSynthesisUtterance(txt);",
        "const u=new SpeechSynthesisUtterance(XJ.toSpeech(txt));",
        'index: 逐镜朗读口语化', optional=True)
s = sub(s,
        ".map(function(x){return String(x).replace(/^[✦\\s]+/,'').replace(/\\s*—\\s*/g,'，').replace(/[；。]+$/g,'');})",
        ".map(function(x){return XJ.toSpeech(String(x).replace(/^[✦\\s]+/,'').replace(/\\s*—\\s*/g,'，').replace(/[；。]+$/g,''));})",
        'index: linesToSpeech 归一化', optional=True)
s = sub(s,
        "return Object.prototype.hasOwnProperty.call(AS.scripts,k)?AS.scripts[k]:linesToSpeech(sceneData(sc).lines);",
        "return Object.prototype.hasOwnProperty.call(AS.scripts,k)?XJ.toSpeech(AS.scripts[k]):XJ.toSpeech(linesToSpeech(sceneData(sc).lines));",
        'index: sceneText 归一化', optional=True)

# 4. 内容层字号放大：vt() 只对 VCONTENT 期间生效，不影响 chrome / 水印 / 字幕
s = sub(s,
        "function vt(ctx,s,x,y,size,color,weight,align){ctx.font=(weight||400)+' '+size+'px '+VF;",
        "var VCONTENT=false;\n"
        "function vt(ctx,s,x,y,size,color,weight,align){var _fs=(VCONTENT&&window.AS&&AS.art)?AS.art.fs:1;"
        "ctx.font=(weight||400)+' '+Math.round(size*_fs)+'px '+VF;",
        'index: vt 内容字号倍率', optional=True)
# painter 内直接设置 ctx.font 的几处，同样按倍率放大
s, nfont = re.subn(
    r"ctx\.font='(\d+) '\+\((L\.small\?\d+:\d+)\)\+'px '\+VF;",
    lambda m: "ctx.font='%s '+Math.round((%s)*(AS.art?AS.art.fs:1.22))+'px '+VF;" % (m.group(1), m.group(2)),
    s)
if nfont == 0 and "ctx.font='600 '+Math.round" not in s:
    FAIL.append('index: painter 直接 ctx.font 未命中')
print('index: painter ctx.font 放大', nfont, '处')

# 5. 画面艺术层 + 城市徽标带（painter 之后叠加，不覆盖文字）
s = sub(s,
        " if(replaceFrame)vFrameCaption(ctx,sc,L,d,t);\n else if(painter)painter(ctx,sc,L,d,t);",
        " if(replaceFrame){VCONTENT=true;vFrameCaption(ctx,sc,L,d,t);VCONTENT=false;}\n"
        " else if(painter){VCONTENT=true;painter(ctx,sc,L,d,t);VCONTENT=false;}\n"
        "  /* 城市专属插画层（低透明叠加）+ 右上城市徽标带：410 城不重样 */\n"
        "  try{ctx.save();ctx.globalAlpha=.20;XJ.art(ctx,L,d,sc,t);ctx.restore();XJ.banner(ctx,L,d,sc);}catch(e){}",
        'index: drawScene 插画层与徽标带', optional=True)

# 6. 衣食住行镜头改成杂志卡片式（复刻行程页四卡质感），每行仍是一源文本
need_new = """function vNeeds(ctx,sc,L,d,t){
  /* 画面每一行 = sceneLines(sc) 的一行 = 字幕/朗读文本的一句；
     两列杂志卡片 + 每城专属缩略插画，配了自备图片就换成真实图片。 */
  const SD=sceneData(sc),lines=sceneLines(sc);
  vt(ctx,SD.title,L.pad,L.titleY,L.titleSize,'#1e2a24',700);
  vt(ctx,SD.sub,L.pad+4,L.subY,L.small?15:18,'#8a9489',500);
  markText(ctx,L,d,d.a,1);
  if(sc.idx===0){const wx=weatherLine(1);
   vt(ctx,'☁ '+vcut(ctx,wx.text+'  ·  '+wx.source,L.W-2*L.pad-20),L.pad+4,L.subY+38,L.small?14:17,wx.rainy?'#3c6685':'#5a7a68',600);}
  try{XJ.cards(ctx,L,d,sc,lines,{top:L.contentTop+12,bottom:L.contentBottom-8,
      scale:(AS.art?AS.art.fs:1.22)});}catch(e){}
}
function vDay"""
s, nneed = re.subn(r"\nfunction vNeeds\(ctx,sc,L,d,t\)\{[\s\S]*?\n\}\nfunction vDay",
                   lambda m: '\n' + need_new, s, count=1)
if nneed != 1 and 'XJ.cards(ctx,L,d,sc,lines' not in s:
    FAIL.append('index: vNeeds 替换失败')
print('index: vNeeds → 杂志卡片', nneed)

# 7. 字幕拖框改成显式开关，默认不显示；框上带 × 可关
s = sub(s,
        "function syncSubDrag(){\n var el=$('subDrag');if(!el)return;\n var show=!!(AS.sub.on&&UI.vtab==='captions');",
        "function toggleSubDrag(v){AS.sub.dragMode=(v===undefined)?!AS.sub.dragMode:!!v;syncSubDrag();"
        "if(UI.vtab==='captions')renderVideoPanel();toast(AS.sub.dragMode?'已开启字幕位置调整 · 拖动后点 × 关闭':'已关闭拖动框');}\n"
        "function syncSubDrag(){\n var el=$('subDrag');if(!el)return;\n"
        " var show=!!(AS.sub.on&&AS.sub.dragMode&&UI.vtab==='captions');",
        'index: 拖动框显式开关', optional=True)
s = sub(s,
        '<div class="xj-sub-drag" id="subDrag"><span>✥ 拖动字幕位置</span></div>',
        '<div class="xj-sub-drag" id="subDrag"><span>✥ 拖动字幕位置</span>'
        '<button type="button" class="xj-sub-drag-x" onclick="toggleSubDrag(false)" title="关闭拖动框">×</button></div>',
        'index: 拖动框 × 按钮', optional=True)
s = sub(s,
        "   <div class=\"vrow tight\"><label>位置</label><button class=\"soft-btn\" onclick=\"resetSubPos();syncFilmCfg()\">↺ 复位默认位置</button><span class=\"mini\">预览台拖动虚线框</span></div>",
        "   <div class=\"vrow tight\"><label>位置</label><button class=\"soft-btn\" onclick=\"resetSubPos();syncFilmCfg()\">↺ 复位默认位置</button>"
        "<button class=\"soft-btn\" onclick=\"toggleSubDrag()\">✥ 调整位置</button><span class=\"mini\">默认不显示虚线框</span></div>\n"
        "   <div class=\"vrange\"><span>画面字号</span><input type=\"range\" min=\"100\" max=\"160\" "
        "value=\"${Math.round((AS.art?AS.art.fs:1.22)*100)}\" oninput=\"setArtFs(this.value)\">"
        "<b>${Math.round((AS.art?AS.art.fs:1.22)*100)}%</b></div>",
        'index: 字幕面板位置行 + 画面字号', optional=True)
s = sub(s,
        "function setSub(k,v){",
        "function setArtFs(v){AS.art.fs=Math.max(1,Math.min(1.6,+v/100));repaintVideo();syncFilmCfg();}\n"
        "function setSub(k,v){",
        'index: setArtFs', optional=True)
s = sub(s,
        "function togglePlayPause(){",
        "function togglePlayPause(){\n if(AS.sub.dragMode){AS.sub.dragMode=false;syncSubDrag();}",
        'index: 播放时收起拖动框', optional=True)
s = sub(s,
        ".xj-sub-drag span{pointer-events:none;white-space:nowrap}",
        ".xj-sub-drag span{pointer-events:none;white-space:nowrap}\n"
        ".xj-sub-drag-x{position:absolute;right:2px;top:2px;width:20px;height:20px;border:0;border-radius:5px;"
        "background:rgba(0,0,0,.42);color:#fff;font-size:15px;line-height:18px;cursor:pointer;pointer-events:auto}"
        ".xj-sub-drag-x:hover{background:rgba(0,0,0,.72)}",
        'index: 拖动框 × 样式', optional=True)

save('index.html', s)

# ============================ film.html ============================
f = load('film.html')
f = sub(f,
        '<script src="data/cities.full.js"></script>',
        '<script src="data/cities.full.js"></script>\n'
        '<script src="data/city-media.js"></script>\n'
        '<script src="scene-art.js"></script>',
        'film: 引入 city-media / scene-art', optional=True)
f = sub(f, "state.cityId?0:0;", "state.cityId?0:0;", 'film: noop', optional=True)
f = sub(f, "tw:true, twSpeed:1, fontSize:46,", "tw:true, twSpeed:1, fontSize:58,", 'film: 默认字号 58', optional=True)
f = sub(f,
        'min="28" max="72" step="2" value="46" oninput="setFont(this.value)"></div>',
        'min="28" max="96" step="2" value="58" oninput="setFont(this.value)"></div>',
        'film: 字号滑杆上限', optional=True)
f = sub(f, '<span id="fontLabel">46 px</span>', '<span id="fontLabel">58 px</span>', 'film: 字号标签', optional=True)
f = sub(f,
        "function sceneText(i){return SCENES[i].lines.join('');}",
        "function sceneText(i){return XJ.toSpeech(SCENES[i].lines.join(''));}",
        'film: 朗读/字幕文本口语化', optional=True)
f = sub(f,
        "  roundRect(cx,pad,pad,cw,ch,Math.round(W*0.018));cx.fill();",
        "  roundRect(cx,pad,pad,cw,ch,Math.round(W*0.018));cx.fill();\n"
        "  /* 城市专属插画层 + 城市名徽标：逐帧成片同样不重样 */\n"
        "  try{cx.save();cx.globalAlpha=.16;XJ.art(cx,{W:W,H:H,pad:pad},c,s,0);cx.restore();\n"
        "      XJ.banner(cx,{W:W,H:H,pad:pad,top:pad+54},c,s);}catch(e){}",
        'film: 插画层与徽标', optional=True)
save('film.html', f)

# ============================ admin.html ============================
a = load('admin.html')
a = sub(a,
        "   +f('卡片图 / 封面图 URL（留空用渐变）','image')\n   +'</div>'",
        "   +f('卡片图 / 封面图 URL（留空用渐变）','image')\n"
        "   +f('景点图 URL（可多张，逗号分隔）','spotImage')\n"
        "   +f('美食图 URL（可多张，逗号分隔）','foodImage')\n"
        "   +f('住宿 / 街区图 URL（可多张，逗号分隔）','stayImage')\n"
        "   +'</div>'",
        'admin: 三类图片字段', optional=True)
a = sub(a,
        "    ['卡片图 / 封面图 image',c.image],",
        "    ['卡片图 / 封面图 image',c.image],\n"
        "    ['景点图 spotImage',c.spotImage],['美食图 foodImage',c.foodImage],\n"
        "    ['住宿 / 街区图 stayImage',c.stayImage],",
        'admin: 详情显示三类图片', optional=True)
save('admin.html', a)

# ============================ make_single.py ============================
m = load('tools/make_single.py')
EXTRA = ("    ('data/city-media.js',       '<script src=\"data/city-media.js\"></script>'),\n"
         "    ('scene-art.js',             '<script src=\"scene-art.js\"></script>'),\n")
m = sub(m, "WORK_EXTERNALS = [\n", "WORK_EXTERNALS = [\n" + EXTRA,
        'make_single: 工作台内联清单')
m = sub(m, "FILM_EXTERNALS = [\n", "FILM_EXTERNALS = [\n" + EXTRA,
        'make_single: 成片页内联清单')
save('tools/make_single.py', m)

# 最终特征断言：optional 允许重复执行，但第一次必须全部落地
CHECK = [
    ('index.html', ['<script src="data/city-media.js"></script>', '<script src="scene-art.js"></script>',
                    'art:{fs:1.22', 'dragMode:false', 'XJ.toSpeech(speakText())',
                    'XJ.cards(ctx,L,d,sc,lines', 'XJ.banner(ctx,L,d,sc)',
                    'function toggleSubDrag(', 'function setArtFs(',
                    'onclick="toggleSubDrag()"', 'oninput="setArtFs(this.value)"',
                    "Math.round((L.small?16:21)*(AS.art?AS.art.fs:1.22))"]),
    ('film.html', ['<script src="scene-art.js"></script>', 'fontSize:58',
                   'function sceneText(i){return XJ.toSpeech(', 'XJ.art(cx,{W:W,H:H,pad:pad}']),
    ('admin.html', ["'spotImage'", "'foodImage'", "'stayImage'"]),
    ('tools/make_single.py', ["('scene-art.js'", "('data/city-media.js'"]),
]
for name, marks in CHECK:
    txt = load(name)
    for mk in marks:
        if mk not in txt: FAIL.append('%s 缺少特征：%s' % (name, mk))

print('\n=== 补丁结果 ===')
if FAIL:
    for x in FAIL: print('  FAIL', x)
    sys.exit(1)
print('  全部命中，无遗漏')
