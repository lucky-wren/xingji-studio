/* 行迹 · GitHub Pages 静态版 —— LibreTTS 神经人声桥接层
 *
 * 架构（与 daily-news-studio / B 站一致）：
 *   字幕逐句 → LibreTTS /api/tts 逐句合成真实音频
 *   → AudioBuffer.duration = durs[]（唯一事实来源）
 *   → 帧长 / 字幕窗口 / SRT / 音轨起点全部由 durs[] 生成
 *   → OfflineAudioContext 预混音，播放与导出只读一个主时钟
 *
 * 网页不跑 Python、不跑 ffmpeg、不跑本地服务，可直接托管在 GitHub Pages。
 */
(function () {
  'use strict';

  var CFG = window.LIBRETTS_CONFIG || {};
  var ST = {
    active: (CFG.instances && CFG.instances[0] && CFG.instances[0].url) || '',
    custom: '', bridge: CFG.bridge || 'http://127.0.0.1:8790',
    voice: CFG.voice || 'zh-CN-XiaoxiaoNeural',
    rate: typeof CFG.rate === 'number' ? CFG.rate : 0,
    pitch: typeof CFG.pitch === 'number' ? CFG.pitch : 0,
    format: CFG.format || 'mp3',
    voices: (CFG.builtinVoices || []).map(function (x) { return [x[0], x[1]]; }),
    probe: [], busy: false, tryBusy: false, tryMsg: '', clips: 0,
    seconds: 0, msg: '', lastUrl: '',
    source: '', dirty: false, probeDone: false
  };
  var LT = window.__LIBRETTS = { state: ST };

  /* ---------------------------------------------------------------- 小工具 */
  function $(id) { return document.getElementById(id); }
  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }
  function toast(t) { try { window.toast(t); } catch (e) { } }
  function g(name, fallback) {
    try { return typeof window[name] !== 'undefined' ? window[name] : fallback; }
    catch (e) { return fallback; }
  }
  function cleanBase(u) { return String(u || '').trim().replace(/\/+$/, ''); }
  function currentBase() { return cleanBase(ST.custom || ST.active); }
  function withTimeout(ms) {
    var c = new AbortController();
    var t = setTimeout(function () { c.abort(); }, ms);
    return { signal: c.signal, done: function () { clearTimeout(t); } };
  }
  function isCorsError(e) {
    return !!(e && (e.name === 'TypeError' || /Failed to fetch|NetworkError|Load failed/i.test(String(e.message || e))));
  }

  /* ------------------------------------------------------- LibreTTS 请求 */
  /* 官方参数（LibreSpark/LibreTTS README）：
   *   GET  /api/tts?t=文本&v=音色&r=语速&p=语调&o=mp3|opus|wav|pcm
   *   POST /api/tts  {"text","voice","rate","pitch","format"}
   *   GET  /api/voices?l=zh&f=1
   * 先走 GET：它是 simple request，不触发 CORS preflight，公共实例成功率更高。
   * POST 作为回退（文本不落 URL 日志）。 */
  function ttsGetUrl(text, o) {
    var b = currentBase();
    var q = new URLSearchParams();
    q.set('t', text);
    q.set('v', ST.voice);
    q.set('r', String(ST.rate));
    q.set('p', String(ST.pitch));
    q.set('o', ST.format);
    return b + '/api/tts?' + q.toString();
  }
  async function fetchAudio(text, ms) {
    var tmo = ms || CFG.timeoutMs || 20000, isProbe = !!ms;
    var to = withTimeout(tmo);
    var url = ttsGetUrl(text);
    ST.lastUrl = url;
    var lastErr = null, netFail = false;
    try {
      var r = await fetch(url, { method: 'GET', signal: to.signal });
      if (r.ok) {
        var ct = r.headers.get('content-type') || '';
        var ab = await r.arrayBuffer();
        if (ab.byteLength > 800 && !/^application\/json|^text\//i.test(ct)) return ab;
        lastErr = new Error('返回不是音频：' + ct.slice(0, 60));
      } else lastErr = new Error('HTTP ' + r.status + ' ' + (await r.text()).slice(0, 100));
    } catch (e) { lastErr = e; netFail = true; }
    finally { to.done(); }
    /* 快速探测时，GET 超时/被 CORS 拦 = 整条链路不通，
       POST 同样要等一次超时；直接判定，不再白等第二遍。
       仅当 GET 收到明确 HTTP 拒绝（如只开 POST 的 405）才继续试 POST。 */
    if (isProbe && netFail) throw lastErr || new Error('链路不可达');

    /* GET 失败再试 POST（有些部署只开 POST，或 GET 被 CDN 缓存规则挡住） */
    var to2 = withTimeout(tmo);
    try {
      var r2 = await fetch(currentBase() + '/api/tts', {
        method: 'POST', signal: to2.signal,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: text, voice: ST.voice, rate: ST.rate, pitch: ST.pitch, format: ST.format })
      });
      if (r2.ok) {
        var ab2 = await r2.arrayBuffer();
        if (ab2.byteLength > 800) return ab2;
        lastErr = new Error('POST 返回空音频');
      } else lastErr = new Error('POST HTTP ' + r2.status);
    } catch (e) { lastErr = e; }
    finally { to2.done(); }
    throw lastErr || new Error('未知错误');
  }
  async function decodeToBuffer(ab, text) {
    /* actx 在 index.html 里是 `let`（全局词法绑定），不是 window 属性，
       但同一页面的 classic script 可以直接用标识符访问。 */
    if (!window.ensureAudio || !window.ensureAudio()) throw new Error('浏览器不支持 Web Audio');
    if (typeof actx === 'undefined' || !actx) throw new Error('AudioContext 未就绪');
    try { return await actx.decodeAudioData(ab.slice(0)); }
    catch (e) {
      /* mp3 解不了时再取一次 wav 格式 */
      var old = ST.format; ST.format = 'wav';
      try {
        var to = withTimeout(CFG.timeoutMs || 20000);
        var r = await fetch(ttsGetUrl(text), { signal: to.signal });
        to.done();
        if (r.ok) return await actx.decodeAudioData(await r.arrayBuffer());
      } catch (e2) { }
      finally { ST.format = old; }
      throw e;
    }
  }

  /* ----------------------------------------------------------- 音色列表 */
  function parseVoices(j) {
    var arr = Array.isArray(j) ? j :
      (j && (j.voices || j.data || j.list || j.result || j.items)) || [];
    if (!Array.isArray(arr) && arr && typeof arr === 'object') arr = Object.values(arr);
    if (!Array.isArray(arr)) return [];
    var out = [], seen = {};
    arr.forEach(function (x) {
      var id, label;
      if (typeof x === 'string') { id = x; label = x; }
      else if (x && typeof x === 'object') {
        id = x.ShortName || x.shortName || x.name || x.id || x.value || x.voice || '';
        label = x.FriendlyName || x.friendlyName || x.label || x.displayName || x.LocalName || id;
      }
      id = String(id || '').trim();
      if (!id || seen[id]) return;
      if (!/^zh[-_]/i.test(id)) return;   /* 只要中文音色 */
      seen[id] = 1;
      out.push([id, String(label || id).replace(/\s*-\s*Chinese.*$/i, '').slice(0, 60)]);
    });
    return out;
  }
  async function fetchVoices(base) {
    var to = withTimeout(9000);
    try {
      var r = await fetch(cleanBase(base) + '/api/voices?l=zh&f=1', { signal: to.signal });
      if (!r.ok) return { ok: false, reason: 'HTTP ' + r.status, voices: [] };
      var j = await r.json();
      var v = parseVoices(j);
      return { ok: true, voices: v.length ? v : [], reason: v.length ? '' : '接口返回了空音色列表' };
    } catch (e) {
      return { ok: false, voices: [], reason: isCorsError(e) ? 'CORS 被拦 / 网络不可达' : String(e.message || e).slice(0, 70) };
    } finally { to.done(); }
  }

  /* ------------------------------------------------------------- 探测 */
  async function probeAll(silent) {
    if (ST.busy || ST.probeRunning) return;
    ST.probeRunning = true;          /* 探测与合成互不占用状态，避免状态行误报 */
    var list = [];
    (CFG.instances || []).forEach(function (x) { if (x.url) list.push([x.name, x.url]); });
    if (ST.bridge) list.push(['本机转发桥', ST.bridge]);
    if (ST.custom && ST.custom !== ST.bridge) list.push(['自定义地址', ST.custom]);
    var seen = {}, uniq = [];
    list.forEach(function (x) { if (!seen[x[1]]) { seen[x[1]] = 1; uniq.push(x); } });
    var results = [];
    for (var i = 0; i < uniq.length; i++) {
      var r = await fetchVoices(uniq[i][1]);
      results.push({ name: uniq[i][0], url: uniq[i][1], ok: r.ok, reason: r.reason, voices: r.voices.length });
      if (r.ok && r.voices.length) ST.voices = r.voices;
      if (r.ok && !ST.active) ST.active = uniq[i][1];
    }
    ST.probe = results; ST.probeDone = true; ST.probeRunning = false;
    var first = results.filter(function (x) { return x.ok; })[0];
    if (first && !ST.custom) ST.active = first.url;
    if (first && first.voices) {
      var rr = await fetchVoices(first.url);
      if (rr.ok && rr.voices.length) ST.voices = rr.voices;
    }
    renderCard();
    if (!silent) toast(first ? '✓ 找到可用接口：' + first.name : '⚠ 没有可用接口，请填本机桥或自建实例');
    return first || null;
  }
  async function useFirst() {
    if (!ST.probeDone) await probeAll(true);
    var f = ST.probe.filter(function (x) { return x.ok; })[0];
    if (!f) { toast('没有可用接口：请启动 tools/bridge.py 或填自建 LibreTTS 地址'); return null; }
    ST.active = f.url; ST.custom = '';
    var r = await fetchVoices(f.url);
    if (r.ok && r.voices.length) ST.voices = r.voices;
    markDirty(); renderCard(); toast('已切到：' + f.name);
    return f;
  }

  /* ------------------------------------------------------------- 试听 */
  async function tryOne() {
    /* 试听与「逐句合成」是两条完全独立的链路：
       只发 1 个 /api/tts 请求、只播一次、不写 AS.voices、不改 BAKE、
       不触碰时间轴。之前共用 ST.busy 导致状态行误显示「正在逐句合成」。 */
    if (ST.busy || ST.tryBusy) return;
    ST.tryBusy = true; ST.tryMsg = ''; renderCard();
    try {
      var txt = '这是一句成片人声试听，用来提前确认音色。';
      try {
        var tl = window.videoTimeline ? window.videoTimeline() : [];
        if (tl.length && window.sceneText) txt = String(window.sceneText(tl[0])).slice(0, 60);
      } catch (e) { }
      var ab = await fetchAudio(txt);
      var b = new Blob([ab], { type: ST.format === 'wav' ? 'audio/wav' : 'audio/mpeg' });
      var a = new Audio(URL.createObjectURL(b));
      await a.play();
      ST.tryMsg = '♪ 已试听：' + voiceLabel(ST.voice) + '（未写入音轨）';
      toast(ST.tryMsg);
    } catch (e) {
      var why = isCorsError(e)
        ? '连不上 LibreTTS 实例（跨域或不可达），按「查看解决办法」配置可用接口'
        : String(e.message || e).slice(0, 90);
      ST.tryMsg = '试听失败：' + why;
      toast(ST.tryMsg);
    } finally { ST.tryBusy = false; renderCard(); }
  }
  function voiceLabel(v) {
    var hit = ST.voices.filter(function (x) { return x[0] === v; })[0];
    return hit ? hit[1] : String(v || '默认');
  }
  function showUrl() {
    var txt = '大理，风花雪月。';
    try {
      var tl = window.videoTimeline ? window.videoTimeline() : [];
      if (tl.length && window.sceneText) txt = String(window.sceneText(tl[0])).slice(0, 40);
    } catch (e) { }
    var u = ttsGetUrl(txt);
    ST.msg = '当前请求：' + u;
    renderCard();
    try { window.prompt('当前 LibreTTS 请求 URL（可复制到 curl 测试）', u); } catch (e) { }
  }

  /* ------------------------------------------------ 逐句合成到人声轨 */
  function markDirty() {
    ST.dirty = true;
    try {
      if (typeof BAKE !== 'undefined') { BAKE.state = 'none'; BAKE.clips = 0; }
      if (typeof AS !== 'undefined') { AS.voices = {}; AS.voiceTrack = null; }
      if (window.invalidateMix) window.invalidateMix();
    } catch (e) { }
  }
  function bakeSig() {
    var texts = [];
    try { texts = (window.videoTimeline ? window.videoTimeline() : []).map(function (s) { return window.sceneText(s); }); }
    catch (e) { }
    return JSON.stringify({ v: 3, texts: texts, ep: currentBase(), voice: ST.voice, rate: ST.rate, pitch: ST.pitch, fmt: ST.format });
  }
  function estBakeSeconds() {
    var n = 0;
    try { n = (window.videoTimeline ? window.videoTimeline() : []).length; } catch (e) { }
    return Math.max(3, Math.round(n * 1.4 / Math.max(1, CFG.concurrency || 3)));
  }
  function bakeStatusText() {
    if (window.bakeReady && window.bakeReady())
      return '✅ LibreTTS 神经人声已生成 · ' + ST.clips + ' 段 / ' + ST.seconds.toFixed(1) + 's · 之后导出秒级且带人声';
    if (ST.busy) return '🎙 正在逐句合成 ' + ST.clips + ' 段…';
    if (ST.msg) return '⚠ ' + ST.msg;
    return '🎙 尚未合成 · ' + (window.videoTimeline ? window.videoTimeline().length : 0) +
      ' 句，预计 ' + estBakeSeconds() + 's（网络请求，非实时朗读）；合成后按真实时长重排全部时间码。';
  }
  /* 同页合成结果缓存：bakeSig() 命中时 0 请求直接复用，
     避免每次点「导出成片」都把 12 句重跑一遍。 */
  var LAST_BAKE = { sig: '', out: null, at: 0 };
  async function bakeAll() {
    if (ST.busy) return false;
    if (typeof S !== 'undefined' && S.video && S.video.playing && window.stopVideo) window.stopVideo(false);
    if (window.rebuildTimeline) window.rebuildTimeline();
    var tl = window.videoTimeline ? window.videoTimeline() : [];
    if (!tl.length) { ST.msg = '没有启用任何镜头'; renderCard(); return false; }
    if (!currentBase()) { ST.msg = '还没有可用的接口地址'; renderCard(); return false; }

    ST.busy = true; ST.clips = 0; ST.seconds = 0; ST.msg = ''; ST.tryMsg = '';
    try { if (typeof BAKE !== 'undefined') { BAKE.busy = true; BAKE.state = 'none'; } } catch (e) { }
    renderCard();

    var jobs = tl.map(function (sc, i) {
      return { i: i, key: sc.key, text: String(window.sceneText(sc) || '') };
    });
    var out = new Array(jobs.length), err = null, reused = false;
    var sig = bakeSig(), conc = Math.max(1, Math.min(6, CFG.concurrency || 4));
    if (LAST_BAKE.out && LAST_BAKE.sig === sig && LAST_BAKE.out.length === jobs.length) {
      out = LAST_BAKE.out.map(function (x) { return { key: x.key, buf: x.buf }; });
      reused = true; ST.clips = jobs.length;
      try { if (window.setFastProgress) window.setFastProgress(1, '♻ 复用上次合成结果 · 0 次网络请求'); } catch (e) { }
    } else {
      /* ① 快速探测：第一句短超时判定整条链路，不通立即整体停止，
         不再让各 worker 各等 20s + 重试。 */
      var pm = CFG.probeMs || 2500, probeErr = null;
      try {
        var ab0 = await window.__LIBRETTS.fetchAudio(jobs[0].text, pm);
        var pb = await decodeToBuffer(ab0, jobs[0].text);
        if (!(pb.duration > .12)) throw new Error('音频时长异常');
        out[0] = { key: jobs[0].key, buf: pb };
        ST.clips = 1;
      } catch (e) { probeErr = e; }
      if (probeErr) {
        ST.busy = false;
        var pe = String(probeErr && (probeErr.message || probeErr));
        ST.msg = '接口快速探测 ' + pm + 'ms 内不通（' +
          (isCorsError(probeErr) ? 'CORS 被拦' : /abort|timeout/i.test(pe) ? '连接超时或被网络策略拦截' : pe.slice(0, 80)) +
          '）：已整体停止，未逐句干等超时';
        try { if (typeof BAKE !== 'undefined') { BAKE.busy = false; BAKE.state = 'failed'; BAKE.msg = ST.msg; } } catch (e2) { }
        try { if (window.setFastProgress) window.setFastProgress(0, ''); } catch (e2) { }
        renderCard(); toast('配音失败：' + ST.msg);
        return false;
      }
      /* ② 其余句子受控并发；探测句不重复请求 */
      var cur = 1;
      async function worker() {
        while (true) {
          var j = jobs[cur++];
          if (!j) return;
          if (err) return;
          var ok = false, last = null;
          for (var a = 0; a <= (CFG.retries || 1); a++) {
            try {
              var ab = await window.__LIBRETTS.fetchAudio(j.text);
              var buf = await decodeToBuffer(ab, j.text);
              if (!(buf.duration > .12)) throw new Error('音频时长异常 ' + buf.duration.toFixed(2) + 's');
              out[j.i] = { key: j.key, buf: buf };
              ok = true; break;
            } catch (e) { last = e; }
          }
          if (!ok) { err = '第 ' + (j.i + 1) + ' 句失败：' + (isCorsError(last) ? 'CORS 被拦' : String(last && (last.message || last)).slice(0, 80)); return; }
          ST.clips++;
          try { if (window.setFastProgress) window.setFastProgress(ST.clips / jobs.length, '🎙 LibreTTS 并发 ' + conc + ' · ' + ST.clips + '/' + jobs.length + ' 句'); } catch (e) { }
        }
      }
      try {
        var ws = []; for (var w = 0; w < Math.min(conc, jobs.length - 1); w++) ws.push(worker());
        await Promise.all(ws);
      } catch (e) { err = String(e.message || e); }
    }

    try { if (window.setFastProgress) window.setFastProgress(0, ''); } catch (e) { }
    if (err || out.some(function (x) { return !x; })) {
      ST.busy = false; ST.msg = err || '有句子没有合成成功';
      try { if (typeof BAKE !== 'undefined') { BAKE.busy = false; BAKE.state = 'failed'; BAKE.msg = ST.msg; } } catch (e) { }
      renderCard();
      toast('配音失败，已停止导出（不会给你无声片子）：' + ST.msg);
      return false;
    }

    /* 关键：把真实音频写进逐镜音轨；rebuildTimeline 会用 buf.duration
       同时决定帧长 / 字幕窗口 / SRT / 音轨起点 —— 这就是平台级同源时间码。 */
    try {
      if (typeof AS === 'undefined') throw new Error('音频状态未就绪');
      AS.voices = {};
      out.forEach(function (x) {
        AS.voices[x.key] = { buf: x.buf, name: ST.voice, source: 'libretts' };
      });
      AS.voiceMode = 'scenes'; AS.voiceTrack = null; AS.voiceTrackName = '';
      if (typeof AUD !== 'undefined') AUD.trimmed = null;
      if (typeof S !== 'undefined' && S.video && S.video.scenes)
        S.video.scenes.forEach(function (s) { s.manualDur = false; });
      if (window.rebuildTimeline) window.rebuildTimeline();
      if (window.invalidateMix) window.invalidateMix();
      if (window.renderTrack) window.renderTrack();
      if (window.refreshVideoUi) window.refreshVideoUi();
      var tl2 = window.videoTimeline();
      if (typeof S !== 'undefined' && S.video) S.video.sec = tl2.length ? tl2[0].dur : 3;
      ST.seconds = out.reduce(function (a, x) { return a + x.buf.duration; }, 0);
      ST.source = currentBase();
      LAST_BAKE = { sig: sig, out: out.map(function (x) { return { key: x.key, buf: x.buf }; }), at: Date.now() };
      ST.dirty = false;
      if (typeof BAKE !== 'undefined') {
        BAKE.busy = false; BAKE.state = 'ready'; BAKE.sig = bakeSig();
        BAKE.clips = out.length; BAKE.seconds = ST.seconds; BAKE.msg = '';
      }
      if (window.renderVideoPanel) window.renderVideoPanel();
      toast((reused ? '♻ 复用上次合成（0 次网络请求）' : '✅ LibreTTS 神经人声 ' + out.length + ' 段') +
        ' / ' + ST.seconds.toFixed(1) + 's，已按真实时长重排帧长 / 字幕 / SRT / 音轨');
    } catch (e) {
      ST.busy = false; ST.msg = String(e.message || e);
      try { if (typeof BAKE !== 'undefined') { BAKE.busy = false; BAKE.state = 'failed'; } } catch (e2) { }
      renderCard(); return false;
    }
    ST.busy = false; renderCard();
    return true;
  }
  LT.fetchAudio = fetchAudio;
  LT.bakeAll = bakeAll;

  /* ------------------------------------------------------------- 配置存档 */
  function projectPack() {
    var tl = [];
    try { tl = window.videoTimeline ? window.videoTimeline() : []; } catch (e) { }
    return {
      format: 'xingji-pages-project', version: 1,
      generated_at: new Date().toISOString(),
      site: { kind: 'github-pages-static', note: '纯静态站点；所有合成在浏览器完成，Actions 只负责发布' },
      city: (typeof S !== 'undefined' && S.dest) ? { name: S.dest.name, id: S.dest.id } : null,
      config: (typeof S !== 'undefined') ? {
        days: S.days, month: S.month, style: S.style, budget: S.budget,
        ratio: S.video && S.video.ratio, fps: S.video && S.video.fps,
        res: S.video && S.video.res
      } : {},
      tts: { endpoint: currentBase(), voice: ST.voice, rate: ST.rate, pitch: ST.pitch,
             format: ST.format, provider: 'LibreTTS / Microsoft Edge Neural' },
      watermark: (typeof WM !== 'undefined') ? {
        enabled: WM.on, type: WM.type, text: WM.text, sub: WM.sub,
        color: WM.color, stroke: WM.stroke, size: WM.size, opacity: WM.opacity,
        pos: WM.pos, margin: WM.margin, tile: WM.tile,
        imageName: WM.imgName || null, imageScale: WM.imgScale,
        imageData: (WM.type === 'image' && WM.imgData) ? WM.imgData : null,
        scope: WM.scope
      } : null,
      audio: (typeof S !== 'undefined' && typeof SFX !== 'undefined') ? {
        score: S.video.score, scoreGain: AS.musicGain,
        sfxMode: SFX.mode, sfxPick: SFX.pick, sfxGain: SFX.gain, sfxBindings: SFX.bind
      } : null,
      subtitles: (typeof AS !== 'undefined' && AS.sub) ? {
        on: AS.sub.on, size: AS.sub.size, font: AS.sub.font, color: AS.sub.color,
        bg: AS.sub.bg, bgAlpha: AS.sub.bgAlpha, charsPerLine: AS.sub.charsPerLine,
        posX: AS.sub.posX, posY: AS.sub.posY
      } : null,
      font: (typeof WM !== 'undefined') ? { size: WM.size, family: WM.font, color: WM.color } : null,
      gains: (typeof AS !== 'undefined') ? {
        master: AS.masterGain, voice: AS.voiceGain, music: AS.musicGain
      } : null,
      scenes: tl.map(function (s) {
        return {
          key: s.key, text: window.sceneText(s),
          start: s.start, dur: s.dur, subStart: s.subStart, subEnd: s.subEnd,
          audioStart: s.audioStart, audioDur: s.audioDur, speak: s.speak
        };
      }),
      durs: tl.map(function (s) { return s.speak; })
    };
  }
  function exportProjectPack() {
    var j = projectPack();
    window.download(new Blob([JSON.stringify(j, null, 2)], { type: 'application/json' }),
      '行迹_配置存档_' + ((j.city && j.city.name) || '行程') + '.json');
    toast('配置存档已导出：可在本工作台载入回填文案、水印与音频配置');
  }
  async function importProjectPack(file) {
    if (!file) return;
    try {
      var j = JSON.parse(await file.text());
      if (j.tts) {
        if (j.tts.endpoint) ST.custom = j.tts.endpoint;
        if (j.tts.voice) ST.voice = j.tts.voice;
        if (typeof j.tts.rate === 'number') ST.rate = j.tts.rate;
      }
      if (j.scenes && typeof AS !== 'undefined' && AS.scripts) {
        j.scenes.forEach(function (s) { AS.scripts[s.key] = s.text; });
      }
      var extra = 0;
      if (j.watermark && typeof WM !== 'undefined') {
        var keys = { enabled: 'on', type: 'type', text: 'text', sub: 'sub', color: 'color',
                     stroke: 'stroke', size: 'size', opacity: 'opacity', pos: 'pos',
                     margin: 'margin', tile: 'tile', imageName: 'imgName',
                     imageScale: 'imgScale', scope: 'scope' };
        Object.keys(keys).forEach(function (k) {
          if (j.watermark[k] !== undefined) WM[keys[k]] = j.watermark[k];
        });
        if (j.watermark.imageData && window.restoreWMImage) {
          window.restoreWMImage(j.watermark.imageData, j.watermark.imageName || '水印.png');
        }
        extra++;
      }
      if (j.audio && typeof S !== 'undefined' && typeof SFX !== 'undefined') {
        if (j.audio.score) S.video.score = j.audio.score;
        if (typeof j.audio.scoreGain === 'number') AS.musicGain = j.audio.scoreGain;
        ['sfxMode', 'sfxPick', 'sfxGain', 'sfxBindings'].forEach(function (k) {
          var map = { sfxMode: 'mode', sfxPick: 'pick', sfxGain: 'gain', sfxBindings: 'bind' };
          if (j.audio[k] !== undefined) SFX[map[k]] = j.audio[k];
        });
        if (window.invalidateMix) window.invalidateMix();
        extra++;
      }
      markDirty(); renderCard();
      if (window.renderVideoPanel) window.renderVideoPanel();
      toast('配置存档已载入：文案、接口、水印与音频配置已回填' + (extra ? '（含扩展配置）' : ''));
    } catch (e) { toast('配置存档解析失败：' + String(e.message || e).slice(0, 60)); }
  }

  /* ------------------------------------------- 静态成品（同目录相对路径） */
  var LATEST_DATA = undefined;   // undefined=未加载 / null=无成品 / object=manifest
  function renderLatest() {
    var box = $('ltLatest'); if (!box) return;
    var m = LATEST_DATA;
    if (!m) {
      box.innerHTML = '<div class="lt-latest lt-latest-mini">☁ ' +
        (m === null ? '暂无站点静态成品 · 本地一键成片照常可用'
          : '正在检查站点静态成品…') + '</div>';
      return;
    }
    var base = 'media/latest/';
    var mp4 = m.film_h || m.film || m.mp4 || 'film.mp4';
    var mp3 = m.mp3 || 'broadcast.mp3';
    var srt = m.srt || 'captions.srt';
    box.innerHTML =
      '<div class="lt-latest ok"><b>☁ 站点静态成品已就绪 · 刷新页面也能直接播放</b>' +
      '<div class="lt-sub">' + esc(m.city || '') + ' · ' + (m.scenes || '—') + ' 镜 · ' +
      (m.duration || 0).toFixed(1) + 's · 构建于 ' + esc(m.built_at || '—') + '</div>' +
      '<video id="ltVideo" controls playsinline preload="none" style="width:100%;max-width:720px;border-radius:10px;margin-top:8px">' +
      '<source src="' + esc(base + mp4) + '" type="video/mp4"></video>' +
      '<div class="lt-links">' +
      '<a href="' + esc(base + mp4) + '" download>↓ 成片 MP4（自带人声）</a>' +
      '<a href="' + esc(base + mp3) + '" download>↓ 成品 MP3</a>' +
      '<a href="' + esc(base + srt) + '" download>↓ 字幕 SRT</a>' +
      '<label><input type="checkbox" id="ltSubOn" checked> 显示字幕</label></div></div>';
    var v = $('ltVideo'), sub = $('ltSubOn');
    if (v && sub) {
      var tr = null;
      try { tr = v.addTextTrack('subtitles', '中文', 'zh'); } catch (e) { }
      fetch(base + srt).then(function (x) { return x.text(); }).then(function (txt) {
        if (!tr || !document.body.contains(v)) return;
        txt.replace(/\r/g, '').split(/\n\s*\n/).forEach(function (b) {
          var L = b.trim().split('\n'); if (L.length < 3) return;
          var m2 = /(\d\d):(\d\d):(\d\d),(\d\d\d)\s*-->\s*(\d\d):(\d\d):(\d\d),(\d\d\d)/.exec(L[1]);
          if (!m2) return;
          var f = function (h, mi, s, ms) { return (+h) * 3600 + (+mi) * 60 + (+s) + (+ms) / 1000; };
          try {
            var c = tr.addCue(new VTTCue(f(m2[1], m2[2], m2[3], m2[4]),
              f(m2[5], m2[6], m2[7], m2[8]), L.slice(2).join(' ')));
            c.line = -2;
          } catch (e) { }
        });
        tr.mode = sub.checked ? 'showing' : 'hidden';
      }).catch(function () { });
      sub.onchange = function () { try { tr.mode = sub.checked ? 'showing' : 'hidden'; } catch (e) { } };
    }
  }
  async function restoreLatest(force) {
    if (LATEST_DATA !== undefined && !force) { renderLatest(); return; }
    var url = (CFG.latestManifest || 'media/latest/manifest.json') + '?t=' + Date.now();
    try {
      var r = await fetch(url, { cache: 'no-store' });
      if (!r.ok) throw new Error('HTTP ' + r.status);
      LATEST_DATA = await r.json();
    } catch (e) { LATEST_DATA = null; }
    renderLatest();
  }

  /* --------------------------------------------------------------- 样式 */
  var CSS_INJECTED = false;
  function injectCss() {
    if (CSS_INJECTED || document.getElementById('ltCss')) return;
    CSS_INJECTED = true;
    var s = document.createElement('style'); s.id = 'ltCss';
    s.textContent = [
      '.lt-card{background:linear-gradient(160deg,#eef6f2,#e7f1ec);border:1px solid #cfe3d8;',
      '  border-radius:14px;padding:16px 18px;margin:2px 0 14px;box-shadow:0 2px 10px rgba(24,52,40,.05)}',
      '.lt-head h3{margin:0 0 4px;font-size:17px;color:#18241e;letter-spacing:.2px}',
      '.lt-rec{display:inline-block;font-size:11px;background:#2f6b53;color:#fff;border-radius:20px;',
      '  padding:2px 9px;margin-left:8px;vertical-align:middle;font-weight:600}',
      '.lt-tag{display:inline-block;font-size:11.5px;color:#3b6553;background:#dcece4;',
      '  border-radius:6px;padding:3px 9px;margin-bottom:8px}',
      '.lt-desc{font-size:12.5px;line-height:1.75;color:#4a6257;margin:6px 0 14px}',
      '.lt-desc code{background:#d7e9df;padding:1px 5px;border-radius:4px;font-size:11.5px}',
      '.lt-row{display:grid;grid-template-columns:152px 1fr;gap:10px;align-items:center;margin:9px 0}',
      '.lt-row>label{font-size:12.5px;color:#26382f;font-weight:600;line-height:1.45}',
      '.lt-row .lt-hint{display:block;font-weight:400;color:#77918a;font-size:11px;line-height:1.4;margin-top:2px}',
      '.lt-row input[type=text],.lt-row select{width:100%;padding:9px 11px;border:1px solid #c8dcd2;',
      '  border-radius:9px;background:#fff;font-size:13px;color:#1d2f26;box-sizing:border-box}',
      '.lt-row input[type=range]{width:100%;accent-color:#2f6b53}',
      '.lt-btns{display:flex;flex-wrap:wrap;gap:8px;margin:14px 0 8px}',
      '.lt-btns2{margin-top:2px}',
      '.lt-btns .soft-btn{border:1px solid #bcd6c8;background:#fff;color:#26483a;font-size:12.5px;',
      '  padding:8px 13px;border-radius:9px;cursor:pointer}',
      '.lt-btns .soft-btn:hover{border-color:#2f6b53;background:#f4faf7}',
      '.lt-btns .lt-primary{background:#2f6b53;color:#fff;border-color:#2f6b53;font-weight:700}',
      '.lt-btns .lt-primary:hover{background:#255942}',
      '.lt-inline{font-size:11.5px;color:#4a6257;display:flex;align-items:center}',
      '.lt-probe{display:flex;flex-wrap:wrap;gap:6px;margin:10px 0 4px}',
      '.lt-chip{font-size:11px;padding:3px 8px;border-radius:20px;background:#eef2ef;color:#5b6f65}',
      '.lt-chip.ok{background:#d9efe1;color:#1f6b47}.lt-chip.bad{background:#f6e6e2;color:#a04430}',
      '.lt-status{font-size:12px;color:#2c4b3c;background:#fff;border:1px dashed #c8dcd2;',
      '  border-radius:8px;padding:9px 11px;margin-top:8px;line-height:1.6}',
      '.lt-msg{font-size:12px;color:#a04430;background:#fff4f0;border-radius:8px;',
      '  padding:8px 11px;margin-top:8px;word-break:break-all;line-height:1.6}',
      '.lt-try{font-size:12px;color:#2c4b3c;background:#f4faf7;border:1px solid #d6e9de;',
      '  border-radius:8px;padding:8px 11px;margin-top:8px;line-height:1.6}',
      '.lt-try.bad{color:#a04430;background:#fff4f0;border-color:#efd5cd}',
      '.lt-help{font-size:12px;color:#7a5238;background:#fff8ec;border:1px solid #ecdcbf;',
      '  border-radius:8px;padding:10px 12px;margin-top:8px;line-height:1.7}',
      '.lt-help a{color:#2f6b53;font-weight:700;text-decoration:none}',
      '.lt-help a:hover{text-decoration:underline}',
      '.lt-btns-main{margin:14px 0 10px}',
      '.lt-btns-main .soft-btn{font-size:13px;padding:10px 18px}',
      '.lt-go{background:#fff;border:1px solid #d9e5de;border-radius:14px;padding:14px 18px;',
      '  margin:0 0 14px;box-shadow:0 2px 10px rgba(28,43,36,.04)}',
      '.lt-go .one-btn{margin-top:0}',
      '.lt-go-hint{font-size:11.5px;color:#7b8f86;line-height:1.6;margin-top:8px}',
      '.lt-note{font-size:11.5px;color:#7b8f86;margin-top:12px;line-height:1.7}',
      '.lt-fold{margin-top:10px;border-top:1px solid #d3e5db;padding-top:9px}',
      '.lt-fold>button{background:none;border:0;color:#3b6553;font-size:12px;cursor:pointer;padding:0}',
      '.lt-fold .hidden{display:none}',
      '.lt-latest{border:1px solid #d9e5de;background:#f8fbf9;border-radius:12px;padding:14px 16px;',
      '  font-size:12.5px;color:#4a6257;margin:0 0 14px}',
      '.lt-latest.ok{border-color:#bcdcc8;background:#f2faf5}',
      '.lt-latest-mini{padding:8px 12px;font-size:11.5px;color:#7b8f86;background:transparent;border-style:dashed}',
      '.lt-latest b{color:#1f3d2e;font-size:13px}',
      '.lt-sub{margin-top:5px;line-height:1.7}',
      '.lt-links{display:flex;flex-wrap:wrap;gap:12px;align-items:center;margin-top:10px}',
      '.lt-links a{color:#2f6b53;text-decoration:none;font-weight:600}',
      '.lt-links a:hover{text-decoration:underline}',
      '@media(max-width:720px){.lt-row{grid-template-columns:1fr}}'
    ].join('\n');
    document.head.appendChild(s);
  }

  /* --------------------------------------------------------------- 界面 */
  function voiceOptions() {
    var seen = {}, list = [];
    ST.voices.forEach(function (x) { if (!seen[x[0]]) { seen[x[0]] = 1; list.push(x); } });
    if (!seen[ST.voice]) list.unshift([ST.voice, ST.voice + '（当前）']);
    return list.map(function (x) {
      return '<option value="' + esc(x[0]) + '"' + (x[0] === ST.voice ? ' selected' : '') + '>' + esc(x[1]) + '</option>';
    }).join('');
  }
  function renderCard() {
    injectCss();
    var host = $('studioMount'); if (!host) return;
    var status = '';
    try { status = bakeStatusText(); } catch (e) { status = ''; }
    /* 全失败时给一句人话 + 一个「怎么办」链接，不再堆一排调试按钮 */
    var help = '';
    if (ST.probeDone && !ST.probe.some(function (x) { return x.ok; })) {
      help = '<div class="lt-help">当前网络连不上 LibreTTS 实例（跨域或不可达）。' +
        '<a href="使用说明.html#cors" target="_blank">查看解决办法 →</a>' +
        '（在 <code>config.js</code> 里填一个可用实例 / 跑本机桥 / 部署 Worker，界面无需填地址）</div>';
    }
    var msg = ST.msg && !ST.busy ? '<div class="lt-msg">' + esc(ST.msg) + '</div>' : '';
    var tryLine = ST.tryBusy ? '<div class="lt-try">🔊 正在试听一句…（不会写入音轨）</div>'
      : (ST.tryMsg ? '<div class="lt-try' + (/失败/.test(ST.tryMsg) ? ' bad' : '') + '">' + esc(ST.tryMsg) + '</div>' : '');

    host.innerHTML =
      '<div class="lt-card" id="ltCard">' +
      '<div class="lt-head"><h3>LibreTTS · 微软神经音色 <span class="lt-rec">推荐</span></h3></div>' +
      '<p class="lt-desc">开源 LibreTTS 转调微软 Edge 在线朗读。逐句合成真实音频后，' +
      '由音频时长统一排布画面、字幕与音轨。</p>' +
      '<div class="lt-row"><label>音色</label>' +
      '<select id="ltVoice" class="vsel">' + voiceOptions() + '</select></div>' +
      '<div class="lt-btns lt-btns-main">' +
      '<button class="soft-btn" id="ltTry">🔊 试听一句</button>' +
      '<button class="soft-btn lt-primary" id="ltBake">⬆ 逐句合成到人声轨</button>' +
      '</div>' +
      '<div class="lt-status">' + esc(status) + '</div>' + tryLine + msg + help +
      '<div class="lt-note">文案会经由第三方实例转发到微软；隐私内容请用自建实例，商用前确认条款。</div>' +
      '</div>' +
      '';

    var bind = function (id, ev, fn) { var e = $(id); if (e) e.addEventListener(ev, fn); };
    bind('ltVoice', 'change', function () { ST.voice = this.value; markDirty(); renderCard(); });
    bind('ltTry', 'click', tryOne);       /* 只发 1 个请求，绝不调 bakeAll */
    bind('ltBake', 'click', function () { bakeAll(); });
    /* 面板重绘后恢复步骤条状态，不丢「第几步」 */
    try { if (window.setOneStep && typeof UI !== 'undefined') window.setOneStep(UI.step, UI.stepText); }
    catch (e) { }
    restoreLatest();
  }

  /* ------------------------------------------------------ 折叠 / 直达 */
  function jumpTo(key) {
    /* 之前只在 180ms 后 scrollIntoView 一次：切主标签 / 切模块会重建 DOM，
       旧节点已被换掉，滚动常常落空，看起来就是「点了没定位」。 */
    var want = { config: 'voice', captions: 'captions', scenes: 'timing', result: 'voice' }[key];
    if (window.switchTab) window.switchTab('video');   /* 含滚到视频面板顶部 */
    else { var tab = document.querySelector('[data-tab="video"]'); if (tab) tab.click(); }
    if (want && window.setVTab && window.UI && window.UI.vtab !== want) window.setVTab(want);
    var tries = 0;
    var go = function () {
      var target = null;
      if (key === 'config') target = $('ltCard');
      else if (key === 'captions') target = document.querySelector('.cap-card') || $('capList');
      else if (key === 'scenes') { var sl = $('sceneList'); target = sl ? sl.closest('.card') : null; }
      else if (key === 'result') target = $('ltLatest') || $('ltGo');
      /* 面板可能仍在异步重建，重试到节点真正出现 */
      if (!target && tries++ < 12) { setTimeout(go, 80); return; }
      /* 明确跳到某段时展开该段：不要让用户点「字幕」却看到被折叠/隐藏的面板 */
      try {
        if (window.panelState && window.savePanelState && window.syncPanelState) {
          var ps = window.panelState(), dirty = false;
          if (ps.off) { ps.off = false; dirty = true; }
          if (want && ps['fold_' + want]) { ps['fold_' + want] = false; dirty = true; }
          if (dirty) { window.savePanelState(ps); window.syncPanelState(); }
        }
      } catch (e) { }
      if (target) {
        if (window.navLocate) window.navLocate(target);
        else target.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }
      try { if (window.closeDrops) window.closeDrops(); } catch (e) { }
    };
    setTimeout(go, 160);
  }

  /* ------------------------------------------------------------- 挂载 */
  function hook() {
    if (typeof window.renderVideoPanel !== 'function') return;
    var orig = window.renderVideoPanel;
    if (orig.__ltHooked) return;
    function wrapped() {
      var ret = orig.apply(this, arguments);
      try { renderCard(); } catch (e) { }
      return ret;
    }
    wrapped.__ltHooked = true;
    window.renderVideoPanel = wrapped;
  }
  function boot() {
    /* 覆盖「录系统嗓音」那套：改成 LibreTTS 逐句 HTTP 合成。
       其余一键成片 / 时间轴 / 混音 / 快速导出全部复用原工作台。 */
    window.bakeVoice = bakeAll;
    window.captureSystemVoice = bakeAll;
    window.bakeSig = bakeSig;
    window.bakeReady = function () {
      try {
        return typeof BAKE !== 'undefined' && BAKE.state === 'ready' &&
          BAKE.sig === bakeSig() && window.hasVoiceClips && window.hasVoiceClips();
      } catch (e) { return false; }
    };
    window.bakeStatusText = bakeStatusText;
    window.estBakeSeconds = estBakeSeconds;
    window.jumpTo = jumpTo;
    window.__LIBRETTS.exportProjectPack = exportProjectPack;
    window.__LIBRETTS.importProjectPack = importProjectPack;
    window.__LIBRETTS.probeAll = probeAll;
    window.__LIBRETTS.bakeAll = bakeAll;
    window.__LIBRETTS.projectPack = projectPack;
    window.__LIBRETTS.showUrl = showUrl;

    hook();
    document.addEventListener('click', function (e) {
      var t = e.target && e.target.closest && e.target.closest('[data-tab]');
      if (t && t.getAttribute('data-tab') === 'video') setTimeout(renderCard, 80);
    }, true);
    /* 字幕改了 → 配音缓存必须失效，否则会拿旧音频配新字幕 */
    document.addEventListener('input', function (e) {
      var t = e.target;
      if (t && t.tagName === 'TEXTAREA' && t.closest && (t.closest('.cap-card') || t.closest('#capList'))) markDirty();
    }, true);
    try {
      if (typeof S !== 'undefined' && S.tab === 'video' && window.renderVideoPanel) window.renderVideoPanel();
      else renderCard();
    } catch (e) { }
    /* 静默探测一次；公共实例不通时不会弹错，用户点「一键探测」才看结果 */
    setTimeout(function () { probeAll(true).catch(function () { }); }, 700);
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
  else boot();
})();
