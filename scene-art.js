/* 行迹 · 画面艺术与文本口语化（初版）
   ------------------------------------------------------------------
   1) XJ.toSpeech：把展示文本里不适合朗读的符号/单位改写成中文口语。
      数据层已全量清洗过一遍，这里是运行时兜底：向导新建、AI 采编、
      后台手工录入、用户改字幕，都不会再把「2h」念成「二 h」。
      幂等：对已经清洗过的文本再调一次不会产生二次改写。
   2) XJ.theme：按城市 id + 名称算稳定主题（色相 / 纹样 / 地标 / 大区），
      410 城各不相同，不依赖任何网络请求。
   3) XJ.art / XJ.banner / XJ.cards：程序化插画图片层、城市徽标带、
      杂志卡片式内容排版。图片优先读 data/city-media.js 里自备授权的路径；
      没配就画矢量插画，不引用外链网图、不冒充真实照片。
   ------------------------------------------------------------------ */
(function(){
  'use strict';
  var XJ = {};

  /* ---------------- 1. 口语化 ---------------- */
  function hours(n){
    var v = parseFloat(n);
    if(!isFinite(v)) return String(n);
    if(v === 0.5) return '半小时';
    if(v === 1) return '1小时';
    if(v === 1.5) return '1个半小时';
    if(v === 2.5) return '2个半小时';
    var i = Math.floor(v), f = +(v - i).toFixed(1);
    if(Math.abs(f) < 0.01) return i + '小时';
    return i + '小时' + Math.round(f * 60) + '分钟';
  }
  XJ.toSpeech = function(s){
    var t = String(s == null ? '' : s);
    if(!t) return t;
    /* 时长：2h / 1.5h / 半天（半天保持中文） */
    t = t.replace(/(\d+(?:\.\d+)?)\s*h(?=\b|[^\w]|$)/gi, function(_, n){ return hours(n); });
    /* 价格：¥8 / ¥180-450 / ¥20 起 / 8元 */
    t = t.replace(/[¥￥]\s*(\d+(?:\.\d+)?)\s*[-–—~～]\s*(\d+(?:\.\d+)?)/g, function(_, a, b){ return a + '到' + b + '元'; });
    t = t.replace(/[¥￥]\s*(\d+(?:\.\d+)?)/g, function(_, a){ return a + '元'; });
    /* 数字区间：180-450 元 / 3-5 天 */
    t = t.replace(/(\d+(?:\.\d+)?)\s*[-–—~～]\s*(\d+(?:\.\d+)?)\s*(?=元|块|天|人|公里|米|分钟|小时|℃|度)/g,
      function(_, a, b){ return a + '到' + b; });
    /* 距离 / 温度 / 面积 / 比例 */
    t = t.replace(/(\d+(?:\.\d+)?)\s*km\b/gi, function(_, n){ return n + '公里'; });
    t = t.replace(/(\d+(?:\.\d+)?)\s*℃/g, function(_, n){ return n + '摄氏度'; });
    t = t.replace(/(\d+(?:\.\d+)?)\s*m²|(\d+(?:\.\d+)?)\s*平方米/g, function(_, a, b){ return (a || b) + '平方米'; });
    t = t.replace(/(\d+(?:\.\d+)?)\s*%/g, function(_, n){ return '百分之' + n; });
    /* 画幅 / 帧率等固定写法 */
    t = t.replace(/16\s*[:：]\s*9/g, '十六比九').replace(/9\s*[:：]\s*16/g, '九比十六')
         .replace(/1\s*[:：]\s*1/g, '一比一');
    t = t.replace(/(\d+)\s*fps/gi, function(_, n){ return '每秒' + n + '帧'; });
    t = t.replace(/(\d+)\s*BPM/gi, function(_, n){ return '每分钟' + n + '拍'; });
    /* 中文之间的斜杠改「或」；URL / 路径 / 扩展名里的斜杠不动 */
    t = t.replace(/([\u4e00-\u9fa5])\s*\/\s*([\u4e00-\u9fa5])/g, '$1或$2');
    /* 波浪号 / 长破折号 / 英文连写单位 */
    t = t.replace(/\s*[~～]\s*/g, '到');
    t = t.replace(/\s*&\s*/g, '和');
    t = t.replace(/\bDAY\s*(\d+)/gi, '第$1天');
    /* 收尾：连续标点收敛，避免读出奇怪停顿 */
    t = t.replace(/[，,]{2,}/g, '，').replace(/[。；;]{2,}/g, '。');
    return t;
  };
  XJ.normalize = XJ.toSpeech;

  /* ---------------- 2. 城市主题（410 城稳定差异化） ---------------- */
  function hash(s){
    var h = 2166136261;
    s = String(s || '');
    for(var i = 0; i < s.length; i++){ h ^= s.charCodeAt(i); h = (h * 16777619) >>> 0; }
    return h >>> 0;
  }
  var MOTIFS = ['mountain','wave','roof','bridge','pine','palm','desert','terrace'];
  var GLYPHS = ['⛰','⛩','🌊','🏯','🌲','🌴','🏜','🏞','🛕','🏮','⛵','🗻'];
  XJ.theme = function(d){
    d = d || {};
    var id = d.id || d.name || 'xingji';
    var h = hash(id + '|' + (d.name || ''));
    var region = String(d.region || d.prov || '');
    var profile = String(d.profile || '');
    var motif;
    if(/沿海|海岛|海南|福建|广东|浙江|山东|辽宁|江苏|广西|coastal|tropical/.test(region + profile)) motif = h % 2 ? 'wave' : 'palm';
    else if(/西北|甘肃|青海|宁夏|新疆|内蒙古|西藏|plateau|northwest/.test(region + profile)) motif = h % 2 ? 'desert' : 'terrace';
    else if(/东北|黑龙江|吉林|辽宁/.test(region)) motif = 'pine';
    else if(/江南|华中|安徽|江西|湖北|湖南|south/.test(region + profile)) motif = h % 2 ? 'bridge' : 'wave';
    else if(/西南|云南|贵州|四川|重庆/.test(region)) motif = 'terrace';
    else motif = MOTIFS[h % MOTIFS.length];
    var hue = (h % 360 + 360) % 360;
    /* 主色永远压在低饱和区间，保证深色文字可读 */
    var sat = 24 + (h % 14), light = 34 + (h % 10);
    return {
      seed: h, motif: motif, glyph: GLYPHS[h % GLYPHS.length],
      hue: hue, sat: sat, light: light,
      ink: 'hsl(' + hue + ',' + sat + '%,' + light + '%)',
      soft: 'hsla(' + hue + ',' + sat + '%,' + light + '%,.10)',
      pale: 'hsla(' + ((hue + 28) % 360) + ',38%,72%,.16)',
      line: 'hsla(' + hue + ',' + sat + '%,' + light + '%,.32)',
      region: region, name: d.name || '行迹', prov: d.prov || d.province || '',
      en: d.en || '', emoji: d.emoji || GLYPHS[h % GLYPHS.length]
    };
  };

  /* ---------------- 3. 媒体配置（自备授权图片） ---------------- */
  function list(v){
    if(Array.isArray(v)) return v.filter(Boolean);
    if(typeof v === 'string' && v.trim()) return v.split(/[,，\n]/).map(function(x){return x.trim();}).filter(Boolean);
    return [];
  }
  XJ.media = function(d){
    var all = window.XJ_CITY_MEDIA || {};
    var m = (all.cities && d && all.cities[d.id]) || {};
    /* 内置图只作兜底；后台详情里用户显式填的自备授权图片路径一律优先。 */
    var builtin = /^(?:data:image\/(?:svg\+xml|png)|assets\/img\/(?:cities|scenes)\/)/;
    var raw = (d && d.image) || '';
    var userCover = raw && !builtin.test(raw) ? raw : '';
    var us = list(d && d.spotImage), uf = list(d && d.foodImage), ust = list(d && d.stayImage);
    var mcover = m.cover || raw || m.thumb || '';
    var scenes = {};
    ['cover','wear','food','stay','route','day'].forEach(function(k){
      scenes[k] = (m.scenes && m.scenes[k]) || '';
    });
    /* 自备授权图覆盖对应题材；用户没填时保持内置 PNG */
    if(userCover) scenes.cover = userCover;
    if(us.length){ scenes.cover = us[0]; scenes.day = us[us.length > 1 ? 1 : 0]; }
    if(uf.length) scenes.food = uf[0];
    if(ust.length) scenes.stay = ust[0];
    if(!scenes.cover) scenes.cover = mcover;
    return {
      cover: userCover || mcover,
      thumb: m.thumb || scenes.cover || '',
      spots: us.length ? us : list(m.spots),
      food:  uf.length ? uf : list(m.food),
      stay:  ust.length ? ust : list(m.stay),
      scenes: scenes,
      credit: m.credit || ''
    };
  };

  /* ---------------- 3.5 分镜图片自动映射（零手动配置） ----------------
     每城 6 类题材图（cover 城市地标 / wear 街巷 / food 菜品 / stay 院落 /
     route 路桥 / day 逐日动线）构图完全不同，按分镜栏目自动取用：
     封面与总览用城市地标、衣用街巷、食用菜品、住用院落、行用路桥、
     逐日与动线用逐日地图。任何一镜都不需要单独上传或指定图片。
     后台替换某城图像后，该城所有分镜与导出自动跟着变。 */
  XJ.sceneKind = function(d, sc){
    sc = sc || {};
    var t = sc.type || '';
    if(t === 'needs') return ['wear','food','stay','route'][sc.idx || 0] || 'cover';
    if(t === 'day' || t === 'map') return 'day';
    return 'cover';
  };
  XJ.sceneKindLabel = function(d, sc){
    var L = {cover:'城市地标', wear:'街巷', food:'菜品', stay:'院落', route:'路桥', day:'逐日动线'};
    return L[XJ.sceneKind(d, sc)] || '城市配图';
  };
  /* 只返回「本栏目该用的那张题材图」+ 一张城市地标作次图。
     旧版把五类图全部 concat 进池子，而五类图共用同一套构图，
     结果每一帧看起来都是同一层底纹 —— 这正是「哪有配图」的根子。 */
  XJ.sceneImages = function(d, sc){
    var m = XJ.media(d), kind = XJ.sceneKind(d, sc), scn = m.scenes || {};
    var out = [], seen = {};
    function push(u){
      if(!u || typeof u !== 'string') return;
      u = u.trim();
      if(u && !seen[u]){ seen[u] = 1; out.push(u); }
    }
    push(scn[kind]);
    push(kind === 'cover' ? scn.day : scn.cover);
    if(!out.length){
      [m.cover, m.thumb].concat(m.spots, m.food, m.stay).forEach(push);
      Object.keys(scn).forEach(function(k){ push(scn[k]); });
    }
    return out;
  };
  XJ.sceneCover = function(d, sc){
    var a = XJ.sceneImages(d, sc);
    return a.length ? a[0] : (XJ.media(d).cover || '');
  };
  var IMGS = {};
  XJ.img = function(url){
    if(!url) return null;
    if(IMGS[url]) return IMGS[url];
    var im = new Image();
    /* 内置图是 data URI，不需要也不能加匿名跨域；只有 http(s) 外部图才设 */
    if(/^https?:/i.test(url)) im.crossOrigin = 'anonymous';
    /* data URI / 本地图片解码是异步的：首次绘制时 hasImage 可能为 false，
       卡片与底纹会回落到矢量插画。加载完成后通知页面重绘一次，切城市、
       后台换图后也能自动切回该城真实素材，不用手动刷新。 */
    im.addEventListener('load', function(){
      try{ window.dispatchEvent(new CustomEvent('xj-art-loaded')); }catch(e){}
    }, {once:true});
    try{ im.src = url; }catch(e){}
    IMGS[url] = im;
    return im;
  };
  XJ.hasImage = function(url){
    var im = XJ.img(url);
    return !!(im && im.complete && im.naturalWidth > 0);
  };
  /* 把一张已配好的城市图按 cover 方式画进指定矩形，供封面图卡等复用 */
  XJ.drawImageCover = function(ctx, url, x, y, w, h){
    if(!url || !XJ.hasImage(url)) return false;
    var im = XJ.img(url), iw = im.naturalWidth, ih = im.naturalHeight;
    if(!iw || !ih) return false;
    var s = Math.max(w / iw, h / ih), dw = iw * s, dh = ih * s;
    try{ ctx.drawImage(im, x + (w - dw) / 2, y + (h - dh) / 2, dw, dh); }catch(e){ return false; }
    return true;
  };
  /* 城市素材是 1280×720 的整幅风景画。放进窄卡片时若按 cover 裁切，
     只剩中间一条深色山脊，肉眼看起来就是「一块绿」，等于没配图。
     这里按完整比例居中显示，天空 / 日轮 / 远山 / 水面都保留，
     让每一格缩略图都是一张能认出来的城市配图。 */
  XJ.drawImageContain = function(ctx, url, x, y, w, h, bg){
    if(!url || !XJ.hasImage(url)) return false;
    var im = XJ.img(url), iw = im.naturalWidth, ih = im.naturalHeight;
    if(!iw || !ih) return false;
    if(bg){ ctx.fillStyle = bg; ctx.fillRect(x, y, w, h); }
    var s = Math.min(w / iw, h / ih), dw = iw * s, dh = ih * s;
    try{ ctx.drawImage(im, x + (w - dw) / 2, y + (h - dh) / 2, dw, dh); }catch(e){ return false; }
    return true;
  };
  /* 6 类题材图（菜品 / 院落 / 路桥 / 街巷 / 动线 / 地标）的识别主体都落在
     画面中央，矮卡片按 cover 居中裁切正好取到主体；按上部取景只会截到
     一片浅色背景，看起来仍是「没配图」。此函数保留供外部自定义素材使用。 */
  XJ.drawImageTop = function(ctx, url, x, y, w, h, bg){
    if(!url || !XJ.hasImage(url)) return false;
    var im = XJ.img(url), iw = im.naturalWidth, ih = im.naturalHeight;
    if(!iw || !ih) return false;
    if(bg){ ctx.fillStyle = bg; ctx.fillRect(x, y, w, h); }
    var s = w / iw, dw = iw * s, dh = ih * s;
    var oy = Math.min(Math.max(0, dh - h), dh * .10);
    try{ ctx.drawImage(im, x, y - oy, dw, dh); }catch(e){ return false; }
    return true;
  };
  XJ.preload = function(d, cb){
    var m = XJ.media(d), scn = m.scenes || {}, urls = [];
    /* 6 类题材图全部预载：衣 / 食 / 住 / 行 / 逐日 首次绘制就有图，
       不会因 Image 异步解码出现空帧或回落到底纹。 */
    Object.keys(scn).forEach(function(k){ if(scn[k] && urls.indexOf(scn[k]) < 0) urls.push(scn[k]); });
    [m.cover].concat(m.spots, m.food, m.stay).forEach(function(u){
      if(u && urls.indexOf(u) < 0) urls.push(u);
    });
    var left = urls.length, done = false;
    if(!left){ if(cb) cb(0); return 0; }
    urls.forEach(function(u){
      var im = XJ.img(u);
      var fin = function(){ if(--left <= 0 && !done){ done = true; if(cb) cb(urls.length); } };
      if(im.complete) fin(); else { im.addEventListener('load', fin, {once:true}); im.addEventListener('error', fin, {once:true}); }
    });
    return urls.length;
  };

  /* ---------------- 4. 程序化插画（不是照片） ---------------- */
  function coverDraw(ctx, im, x, y, w, h){
    var iw = im.naturalWidth, ih = im.naturalHeight;
    if(!iw || !ih) return false;
    var s = Math.max(w / iw, h / ih), dw = iw * s, dh = ih * s;
    try{ ctx.drawImage(im, x + (w - dw) / 2, y + (h - dh) / 2, dw, dh); }catch(e){ return false; }
    return true;
  }
  function ridge(ctx, W, H, th, baseY, amp, fill){
    ctx.beginPath(); ctx.moveTo(0, H);
    ctx.lineTo(0, baseY);
    var n = 7, r = th.seed;
    for(var i = 0; i <= n; i++){
      r = (r * 1103515245 + 12345) & 0x7fffffff;
      var jitter = ((r % 1000) / 1000 - .5) * amp;
      ctx.lineTo(W * i / n, baseY + jitter);
    }
    ctx.lineTo(W, H); ctx.closePath(); ctx.fillStyle = fill; ctx.fill();
  }
  XJ.motif = function(ctx, W, H, th, t){
    var m = th.motif, s = th.seed;
    ctx.save();
    ctx.globalAlpha = .5;
    if(m === 'mountain' || m === 'terrace' || m === 'desert'){
      ridge(ctx, W, H, th, H * .70, H * .20, th.line);
      ridge(ctx, W, H, th, H * .82, H * .13, th.soft);
      if(m === 'desert'){
        ctx.globalAlpha = .35; ctx.strokeStyle = th.line; ctx.lineWidth = 2;
        for(var q = 0; q < 4; q++){
          ctx.beginPath();
          ctx.moveTo(W * .55, H * (.58 + q * .055));
          ctx.quadraticCurveTo(W * .78, H * (.54 + q * .055), W, H * (.60 + q * .055));
          ctx.stroke();
        }
      }
    }else if(m === 'wave' || m === 'palm'){
      ctx.strokeStyle = th.line; ctx.lineWidth = 2.2;
      for(var i = 0; i < 5; i++){
        ctx.beginPath();
        var y = H * (.62 + i * .07);
        ctx.moveTo(0, y);
        for(var x = 0; x <= W; x += W / 12){
          ctx.quadraticCurveTo(x + W / 24, y - 10 - (s % 7), x + W / 12, y);
        }
        ctx.stroke();
      }
      if(m === 'palm'){
        ctx.globalAlpha = .4; ctx.fillStyle = th.ink;
        var px = W * .86, py = H * .66;
        ctx.fillRect(px - 4, py, 8, H - py);
        for(var k = 0; k < 6; k++){
          ctx.save(); ctx.translate(px, py); ctx.rotate(-Math.PI / 2 + k * Math.PI / 6);
          ctx.beginPath(); ctx.ellipse(W * .055, 0, W * .055, 8, 0, 0, Math.PI * 2); ctx.fill(); ctx.restore();
        }
      }
    }else if(m === 'roof' || m === 'bridge'){
      ctx.fillStyle = th.line;
      var bx = W * .62, by = H * .74, bw = W * .30;
      ctx.beginPath(); ctx.moveTo(bx - 14, by); ctx.quadraticCurveTo(bx + bw / 2, by - H * .13, bx + bw + 14, by);
      ctx.lineTo(bx + bw, by + 8); ctx.lineTo(bx, by + 8); ctx.closePath(); ctx.fill();
      ctx.fillRect(bx + 8, by + 8, bw - 16, 10);
      for(var c = 0; c < 3; c++) ctx.fillRect(bx + 18 + c * (bw - 44) / 2, by + 18, 8, H * .12);
      if(m === 'bridge'){
        ctx.globalAlpha = .28; ctx.strokeStyle = th.ink; ctx.lineWidth = 6;
        ctx.beginPath(); ctx.moveTo(0, H * .88); ctx.quadraticCurveTo(W * .5, H * .72, W, H * .88); ctx.stroke();
      }
    }else if(m === 'pine'){
      ctx.fillStyle = th.line;
      for(var p = 0; p < 7; p++){
        var tx = W * (.06 + p * .14), ty = H * (.70 + (p % 3) * .05);
        ctx.beginPath(); ctx.moveTo(tx, ty - H * .22); ctx.lineTo(tx - W * .035, ty);
        ctx.lineTo(tx + W * .035, ty); ctx.closePath(); ctx.fill();
        ctx.fillRect(tx - 3, ty, 6, H - ty);
      }
    }
    ctx.restore();
  };
  XJ.art = function(ctx, L, d, sc, t, opt){
    opt = opt || {};
    var W = L.W || 1280, H = L.H || 720, th = XJ.theme(d);
    /* 只铺内容区的浅纸底：墨色标题与白卡片始终清楚。
       城市配图由 XJ.hero 在内容层之后、右侧整块不透明铺出，
       不再把同一张图铺满整幅再盖白渐变（那样看着就是一层底纹）。 */
    var g = ctx.createLinearGradient(0, 0, W * .60, H);
    g.addColorStop(0, '#faf7f0'); g.addColorStop(1, '#eef2ec');
    ctx.fillStyle = g; ctx.fillRect(0, 0, W, H);
    ctx.save();
    ctx.globalAlpha = .16;
    XJ.motif(ctx, W, H, th, t || 0);
    ctx.restore();
  };

  /* 每一帧右侧整块不透明铺题材大图，占横版约 41.5% 面积；
     画在内容层之后，不被白卡片、模板底色或整幅遮罩盖掉。 */
  XJ.hero = function(ctx, L, d, sc, label){
    var W = L.W || 1280, H = L.H || 720;
    var url = XJ.sceneCover(d, sc) || XJ.media(d).cover;
    if(!url || !XJ.hasImage(url)) return false;
    var portrait = !!L.portrait, bot = L.bot || 56, top = L.top || 76;
    var ix, iy, iw, ih;
    if(portrait){
      var split = Math.round(H * .56);
      ix = 0; iy = split; iw = W; ih = H - bot - split;
    }else{
      ix = Math.round(W * .585); iy = Math.round(top * .35); iw = W - ix;
      ih = H - iy - bot;
    }
    if(iw < 40 || ih < 40) return false;
    /* 不透明铺满整块右侧：按 cover 裁切填满，不留底纹、不叠白渐变。 */
    ctx.save();
    ctx.beginPath();
    if(ctx.roundRect) ctx.roundRect(ix, iy, iw, ih, 10); else ctx.rect(ix, iy, iw, ih);
    ctx.clip();
    ctx.fillStyle = '#e8f0e9'; ctx.fillRect(ix, iy, iw, ih);
    if(!XJ.drawImageCover(ctx, url, ix, iy, iw, ih)){
      ctx.fillStyle = '#9fb8a9'; ctx.fillRect(ix, iy, iw, ih);
    }
    ctx.restore();
    /* 白相框 + 底部城市 / 题材标签 */
    ctx.save();
    ctx.strokeStyle = 'rgba(255,253,248,.94)'; ctx.lineWidth = 5;
    ctx.beginPath();
    if(ctx.roundRect) ctx.roundRect(ix + 3, iy + 3, iw - 6, ih - 6, 9); else ctx.rect(ix + 3, iy + 3, iw - 6, ih - 6);
    ctx.stroke();
    var thh = Math.max(28, Math.round(H * .045));
    ctx.fillStyle = 'rgba(24,44,35,.84)';
    ctx.fillRect(ix, iy + ih - thh, iw, thh);
    ctx.fillStyle = '#fff'; ctx.textAlign = 'left'; ctx.textBaseline = 'middle';
    ctx.font = '600 ' + Math.round(Math.max(14, W * .013)) + 'px "PingFang SC","Microsoft YaHei",sans-serif';
    var nm = (d.name || '行迹') + (d.prov && d.prov !== d.name ? ' · ' + d.prov : '');
    ctx.fillText(nm + '  ·  ' + (label || XJ.sceneKindLabel(d, sc)), ix + 14, iy + ih - thh / 2);
    ctx.textAlign = 'left'; ctx.textBaseline = 'alphabetic';
    ctx.restore();
    return true;
  };

  XJ.banner = function(ctx, L, d, sc){
    var th = XJ.theme(d), W = L.W || 1280;
    var w = Math.min(Math.round(W * .30), 360), h = 38;
    var x = W - (L.pad || 90) - w, y = (L.top || 76) + 16;
    ctx.save();
    ctx.fillStyle = 'rgba(255,253,248,.88)';
    ctx.beginPath();
    if(ctx.roundRect) ctx.roundRect(x, y, w, h, 10); else ctx.rect(x, y, w, h);
    ctx.fill();
    ctx.fillStyle = th.ink; ctx.fillRect(x, y, 5, h);
    ctx.textAlign = 'left'; ctx.textBaseline = 'alphabetic';
    ctx.font = '700 17px "PingFang SC","Microsoft YaHei",sans-serif';
    ctx.fillStyle = '#1e2a24';
    var label = th.name + (th.prov && th.prov !== th.name ? ' · ' + th.prov : '');
    ctx.fillText(label, x + 16, y + 24);
    ctx.font = '500 11px sans-serif'; ctx.fillStyle = '#6b7a70'; ctx.textAlign = 'right';
    ctx.fillText((th.region || '行迹') + '  ' + th.glyph, x + w - 12, y + 24);
    ctx.restore();
  };

  /* ---------------- 4.5 卡片缩略插画（同步生成，不是照片） ----------------
     逐帧导出与预览读同一段程序化绘制，不依赖 Image.onload，不会出现
     「预览有图、成片没图」。配了自备授权照片时由 XJ.cards 优先画照片。 */
  XJ.thumb = function(ctx, x, y, w, h, kind, th, seed){
    ctx.save(); ctx.translate(x, y);
    var st = ((th.seed || 1) + (seed || 0) * 97) >>> 0;
    var rnd = function(){ st = (st * 1103515245 + 12345) & 0x7fffffff; return (st % 1000) / 1000; };
    var hue = th.hue || 160, ink = th.ink, u = Math.max(.7, Math.min(w, h) / 45);
    var sky = ctx.createLinearGradient(0, 0, 0, h);
    sky.addColorStop(0, 'hsl(' + hue + ',30%,89%)');
    sky.addColorStop(1, 'hsl(' + ((hue + 34) % 360) + ',38%,73%)');
    ctx.fillStyle = sky; ctx.fillRect(0, 0, w, h);
    ctx.globalAlpha = .75; ctx.fillStyle = '#fff8e6';
    ctx.beginPath(); ctx.arc(w * (.66 + rnd() * .14), h * .20, Math.max(4, w * .10), 0, Math.PI * 2); ctx.fill();
    ctx.globalAlpha = 1;
    /* 远山 / 近岸 / 水纹：每张按城市种子略有不同 */
    ctx.fillStyle = 'hsla(' + hue + ',26%,52%,.40)';
    ctx.beginPath(); ctx.moveTo(0, h); ctx.lineTo(0, h * .60);
    for(var i = 0; i <= 5; i++) ctx.lineTo(w * i / 5, h * (.48 + rnd() * .18));
    ctx.lineTo(w, h); ctx.closePath(); ctx.fill();
    ctx.fillStyle = 'hsla(' + ((hue + 18) % 360) + ',30%,43%,.52)';
    ctx.beginPath(); ctx.moveTo(0, h); ctx.lineTo(0, h * .78);
    for(var j = 0; j <= 4; j++) ctx.lineTo(w * j / 4, h * (.70 + rnd() * .12));
    ctx.lineTo(w, h); ctx.closePath(); ctx.fill();
    ctx.strokeStyle = 'rgba(255,255,255,.42)'; ctx.lineWidth = Math.max(1, u * .9);
    for(var k = 0; k < 3; k++){ var yy = h * (.80 + k * .06);
      ctx.beginPath(); ctx.moveTo(w * .05, yy); ctx.lineTo(w * .95, yy); ctx.stroke(); }
    /* 栏目主体 */
    ctx.save(); ctx.translate(w * .5, h * .70);
    if(kind === 'food'){
      ctx.fillStyle = '#fdfbf5'; ctx.beginPath(); ctx.ellipse(0, 0, 16 * u, 7 * u, 0, 0, Math.PI * 2); ctx.fill();
      ctx.fillStyle = ink; ctx.beginPath(); ctx.ellipse(0, -1 * u, 16 * u, 6 * u, 0, 0, Math.PI); ctx.fill();
      ctx.fillStyle = '#e8b96a';
      for(var q = 0; q < 4; q++){ ctx.beginPath(); ctx.arc((-9 + q * 6) * u, -3 * u, 2.2 * u, 0, Math.PI * 2); ctx.fill(); }
      ctx.strokeStyle = 'rgba(255,255,255,.9)'; ctx.lineWidth = 1.4 * u;
      for(var v = 0; v < 2; v++){ ctx.beginPath(); ctx.moveTo((-6 + v * 8) * u, -10 * u);
        ctx.quadraticCurveTo((-9 + v * 8) * u, -16 * u, (-4 + v * 8) * u, -21 * u); ctx.stroke(); }
      ctx.strokeStyle = '#6b5a42'; ctx.lineWidth = 1.6 * u;
      ctx.beginPath(); ctx.moveTo(14 * u, -14 * u); ctx.lineTo(24 * u, -24 * u); ctx.stroke();
      ctx.beginPath(); ctx.moveTo(17 * u, -12 * u); ctx.lineTo(27 * u, -22 * u); ctx.stroke();
    }else if(kind === 'stay'){
      ctx.fillStyle = '#fdfbf5'; ctx.fillRect(-14 * u, -4 * u, 28 * u, 20 * u);
      ctx.fillStyle = ink; ctx.beginPath(); ctx.moveTo(-19 * u, -4 * u); ctx.lineTo(0, -20 * u);
      ctx.lineTo(19 * u, -4 * u); ctx.closePath(); ctx.fill();
      ctx.fillStyle = 'rgba(255,255,255,.85)'; ctx.fillRect(-4 * u, 2 * u, 8 * u, 9 * u);
      ctx.fillStyle = '#e8b96a'; ctx.fillRect(-11 * u, 3 * u, 5 * u, 5 * u); ctx.fillRect(6 * u, 3 * u, 5 * u, 5 * u);
    }else if(kind === 'transit'){
      ctx.strokeStyle = 'rgba(255,255,255,.8)'; ctx.lineWidth = 3 * u;
      ctx.beginPath(); ctx.moveTo(-22 * u, 14 * u); ctx.lineTo(22 * u, 14 * u); ctx.stroke();
      ctx.setLineDash([4 * u, 4 * u]); ctx.strokeStyle = '#fff8e6'; ctx.lineWidth = 1.4 * u;
      ctx.beginPath(); ctx.moveTo(0, 14 * u); ctx.lineTo(0, -2 * u); ctx.stroke(); ctx.setLineDash([]);
      ctx.fillStyle = '#fdfbf5'; ctx.beginPath();
      if(ctx.roundRect) ctx.roundRect(-13 * u, -8 * u, 26 * u, 12 * u, 3 * u);
      else ctx.rect(-13 * u, -8 * u, 26 * u, 12 * u);
      ctx.fill();
      ctx.fillStyle = ink; ctx.fillRect(-9 * u, -5 * u, 18 * u, 5 * u);
      ctx.fillStyle = '#3a4a40';
      ctx.beginPath(); ctx.arc(-8 * u, 5 * u, 3 * u, 0, Math.PI * 2); ctx.fill();
      ctx.beginPath(); ctx.arc(8 * u, 5 * u, 3 * u, 0, Math.PI * 2); ctx.fill();
    }else if(kind === 'cloth'){
      ctx.strokeStyle = '#6b5a42'; ctx.lineWidth = 1.4 * u;
      ctx.beginPath(); ctx.moveTo(0, -20 * u); ctx.lineTo(0, -14 * u); ctx.stroke();
      ctx.beginPath(); ctx.arc(0, -22 * u, 2 * u, 0, Math.PI * 2); ctx.stroke();
      ctx.fillStyle = '#fdfbf5'; ctx.beginPath();
      ctx.moveTo(-6 * u, -13 * u); ctx.lineTo(6 * u, -13 * u); ctx.lineTo(15 * u, -6 * u);
      ctx.lineTo(11 * u, 2 * u); ctx.lineTo(-11 * u, 2 * u); ctx.lineTo(-15 * u, -6 * u); ctx.closePath(); ctx.fill();
      ctx.strokeStyle = ink; ctx.lineWidth = 1.2 * u; ctx.stroke();
      ctx.fillStyle = 'hsla(' + hue + ',40%,58%,.55)'; ctx.fillRect(-9 * u, -2 * u, 18 * u, 3 * u);
    }else{
      var sk = (seed || 0) % 3;
      if(sk === 0){                       /* 塔 */
        ctx.fillStyle = '#fdfbf5'; ctx.fillRect(-8 * u, -16 * u, 16 * u, 22 * u);
        ctx.fillStyle = ink;
        for(var lv = 0; lv < 3; lv++){
          var ww = (20 - lv * 4) * u, ty = (-16 + lv * 8) * u;
          ctx.beginPath(); ctx.moveTo(-ww / 2, ty); ctx.quadraticCurveTo(0, ty - 7 * u, ww / 2, ty);
          ctx.lineTo(ww / 2 - 2 * u, ty + 3 * u); ctx.lineTo(-ww / 2 + 2 * u, ty + 3 * u); ctx.closePath(); ctx.fill();
        }
        ctx.fillStyle = '#e8b96a'; ctx.fillRect(-2 * u, 0, 4 * u, 7 * u);
      }else if(sk === 1){                 /* 水边亭 */
        ctx.fillStyle = ink;
        ctx.beginPath(); ctx.moveTo(-17 * u, -8 * u); ctx.quadraticCurveTo(0, -22 * u, 17 * u, -8 * u);
        ctx.lineTo(13 * u, -6 * u); ctx.lineTo(-13 * u, -6 * u); ctx.closePath(); ctx.fill();
        ctx.fillStyle = '#fdfbf5'; ctx.fillRect(-11 * u, -6 * u, 4 * u, 16 * u); ctx.fillRect(7 * u, -6 * u, 4 * u, 16 * u);
        ctx.fillRect(-13 * u, 9 * u, 26 * u, 3 * u);
        ctx.fillStyle = '#e8b96a'; ctx.fillRect(-3 * u, 4 * u, 6 * u, 3 * u);
      }else{                             /* 拱桥 */
        ctx.strokeStyle = '#fdfbf5'; ctx.lineWidth = 5 * u;
        ctx.beginPath(); ctx.moveTo(-20 * u, 8 * u); ctx.quadraticCurveTo(0, -14 * u, 20 * u, 8 * u); ctx.stroke();
        ctx.strokeStyle = ink; ctx.lineWidth = 2 * u;
        ctx.beginPath(); ctx.moveTo(-20 * u, 8 * u); ctx.quadraticCurveTo(0, -14 * u, 20 * u, 8 * u); ctx.stroke();
        ctx.fillStyle = '#fdfbf5'; ctx.fillRect(-20 * u, 9 * u, 40 * u, 3 * u);
        ctx.globalAlpha = .5; ctx.strokeStyle = '#fff'; ctx.lineWidth = 1.2 * u;
        ctx.beginPath(); ctx.moveTo(-16 * u, 15 * u); ctx.lineTo(16 * u, 15 * u); ctx.stroke(); ctx.globalAlpha = 1;
      }
    }
    ctx.restore(); ctx.restore();
  };

  /* 逐日 / 景点逐格缩略图：同样自动取该城素材，取不到才回落程序化插画。
     预览与逐帧导出走同一函数，不会出现「预览有图、成片没图」。 */
  XJ.sceneThumb = function(ctx, x, y, w, h, kind, th, seed, d, sc, i){
    var imgs = XJ.sceneImages(d, sc), url = imgs.length ? imgs[i % imgs.length] : '';
    if(!url || !XJ.hasImage(url)){
      var cv = XJ.media(d).cover;
      url = (cv && XJ.hasImage(cv)) ? cv : '';
    }
    if(url){
      ctx.save();
      ctx.beginPath();
      if(ctx.roundRect) ctx.roundRect(x, y, w, h, 8); else ctx.rect(x, y, w, h);
      ctx.clip();
      XJ.drawImageCover(ctx, url, x, y, w, h, '#e8f0e9');
      ctx.restore();
      ctx.save();
      ctx.strokeStyle = 'rgba(255,253,248,.85)'; ctx.lineWidth = 1.5;
      ctx.beginPath();
      if(ctx.roundRect) ctx.roundRect(x, y, w, h, 8); else ctx.rect(x, y, w, h);
      ctx.stroke(); ctx.restore();
      return true;
    }
    /* 410 城全部已配图；真没图时留纯色块，不再画通用栏目图标 */
    ctx.save(); ctx.fillStyle = 'rgba(63,111,99,.14)';
    if(ctx.roundRect){ ctx.beginPath(); ctx.roundRect(x, y, w, h, 8); ctx.fill(); }
    else ctx.fillRect(x, y, w, h);
    ctx.restore();
    return false;
  };

  /* 杂志卡片式内容排版：每行仍是一镜一源的一句，2 列排布 + 缩略插画块 */
  XJ.cards = function(ctx, L, d, sc, lines, opt){
    opt = opt || {};
    var th = XJ.theme(d), W = L.W || 1280, H = L.H || 720;
    var pad = L.pad || 90, top = opt.top || (L.contentTop + 12);
    var bottom = opt.bottom || (L.contentBottom - 8);
    var cols = opt.cols || (L.portrait ? 1 : 2);
    var n = Math.max(1, lines.length), rows = Math.ceil(n / cols);
    var gap = n > 4 ? 10 : 16;
    var cw = (W - 2 * pad - gap * (cols - 1)) / cols;
    var ch = Math.min(150, Math.max(34, Math.floor((bottom - top - gap * (rows - 1)) / rows)));
    var fs = Math.round((opt.baseSize || (L.small ? 17 : 21)) * (opt.scale || 1));
    /* 卡片图 100% 自动取自该城素材：美食镜用美食图、住镜用住宿图、
       行镜用景点图，逐日/总览用景点图轮播。零逐镜手动配置。 */
    var imgs = XJ.sceneImages(d, sc), m = XJ.media(d);
    var kind = (sc && sc.type === 'needs') ? (['cloth','food','stay','transit'][sc.idx || 0] || 'scene') : 'scene';
    ctx.save();
    for(var i = 0; i < n; i++){
      var c = i % cols, r = Math.floor(i / cols);
      var x = pad + c * (cw + gap), y = top + r * (ch + gap);
      ctx.fillStyle = 'rgba(255,253,248,.95)';
      ctx.beginPath(); if(ctx.roundRect) ctx.roundRect(x, y, cw, ch, 14); else ctx.rect(x, y, cw, ch);
      ctx.fill(); ctx.strokeStyle = '#ece7dc'; ctx.lineWidth = 1; ctx.stroke();
      /* 缩略图 = 该城已配好的整幅风景画，按完整比例显示，不再裁成一条深绿山脊。 */
      var tw = Math.min(206, Math.round(cw * .38)), thh = ch - 18;
      var url = imgs.length ? imgs[i % imgs.length] : '';
      if(!url || !XJ.hasImage(url)) url = (m.cover && XJ.hasImage(m.cover)) ? m.cover : '';
      ctx.save();
      ctx.beginPath(); if(ctx.roundRect) ctx.roundRect(x + 9, y + 9, tw, thh, 9); else ctx.rect(x + 9, y + 9, tw, thh);
      ctx.clip();
      if(!XJ.drawImageCover(ctx, url, x + 9, y + 9, tw, thh, '#e8f0e9')){
        ctx.fillStyle = 'rgba(63,111,99,.14)'; ctx.fillRect(x + 9, y + 9, tw, thh);
      }
      ctx.restore();
      ctx.save();
      ctx.strokeStyle = 'rgba(255,253,248,.9)'; ctx.lineWidth = 2;
      ctx.beginPath(); if(ctx.roundRect) ctx.roundRect(x + 9, y + 9, tw, thh, 9); else ctx.rect(x + 9, y + 9, tw, thh);
      ctx.stroke(); ctx.restore();
      /* 编号 + 正文（放大后仍按卡片宽度截断，不溢出） */
      ctx.fillStyle = th.ink;
      ctx.beginPath(); ctx.arc(x + 9 + tw + 20, y + ch / 2 - 8, 11, 0, Math.PI * 2); ctx.fill();
      ctx.fillStyle = '#fff'; ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
      ctx.font = '700 12px sans-serif'; ctx.fillText(String(i + 1), x + 9 + tw + 20, y + ch / 2 - 8);
      ctx.textAlign = 'left'; ctx.textBaseline = 'alphabetic';
      ctx.font = '600 ' + fs + 'px "PingFang SC","Microsoft YaHei",sans-serif';
      ctx.fillStyle = '#25352c';
      var txt = String(lines[i] || '');
      /* 价格/时长小字与正文同一基线、右对齐，正文截断时先给它留位 */
      var mm = txt.match(/(\d+(?:\.\d+)?\s*(?:元|小时|分钟|公里|天))/);
      var reserve = mm ? Math.round(fs * 2.8) : 0;
      var maxW = cw - tw - 58 - reserve;
      var cut = txt;
      while(ctx.measureText(cut).width > maxW && cut.length > 4) cut = cut.slice(0, -2) + '…';
      ctx.fillText(cut, x + 9 + tw + 40, y + ch / 2 + fs * .32);
      if(mm){ ctx.font = '500 ' + Math.round(fs * .62) + 'px sans-serif'; ctx.fillStyle = '#8a9489';
              ctx.textAlign = 'right'; ctx.fillText(mm[1], x + cw - 12, y + ch / 2 + fs * .32);
              ctx.textAlign = 'left'; }
    }
    ctx.restore();
  };

  window.XJ = XJ;
})();
