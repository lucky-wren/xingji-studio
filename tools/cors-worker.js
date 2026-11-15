/* 行迹 · GitHub Pages 版 —— Cloudflare Worker 版 CORS 转发（可选）
 *
 * 不想在本机跑 tools/bridge.py 时，用这个 Worker 做同源代理：
 *   1) Cloudflare Dashboard → Workers & Pages → Create Worker
 *   2) 把本文件整段粘进编辑器 → Deploy
 *   3) 拿到 https://xxx.workers.dev
 *   4) 工作台「接口地址」填 https://xxx.workers.dev
 *
 * 只转发 /api/tts 与 /api/voices，不存文案、不写日志。
 * 上游默认 LibreTTS 公共实例；改 UPSTREAM 常量可指向自建实例。
 */

const UPSTREAM = 'https://libretts.is-an.org';

const CORS = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
  'Access-Control-Allow-Headers': 'Content-Type, X-TTS-Text',
  'Access-Control-Max-Age': '86400',
  'Cache-Control': 'no-store'
};

export default {
  async fetch(request, env, ctx) {
    const u = new URL(request.url);
    if (request.method === 'OPTIONS') {
      return new Response(null, { status: 204, headers: CORS });
    }
    if (!u.pathname.startsWith('/api/')) {
      return new Response('only /api/* is proxied', { status: 404, headers: CORS });
    }
    const target = UPSTREAM.replace(/\/$/, '') + u.pathname + u.search;
    const init = {
      method: request.method,
      headers: { 'User-Agent': 'xingji-pages-worker/1.0', 'Accept': '*/*' }
    };
    if (request.method === 'POST') {
      init.body = await request.arrayBuffer();
      init.headers['Content-Type'] = request.headers.get('Content-Type') || 'application/json';
    }
    const t = request.headers.get('X-TTS-Text');
    if (t) init.headers['X-TTS-Text'] = t;
    try {
      const r = await fetch(target, init);
      const h = new Headers(r.headers);
      Object.entries(CORS).forEach(([k, v]) => h.set(k, v));
      return new Response(r.body, { status: r.status, headers: h });
    } catch (e) {
      return new Response(JSON.stringify({ error: String(e) }), {
        status: 502, headers: { ...CORS, 'Content-Type': 'application/json' }
      });
    }
  }
};
