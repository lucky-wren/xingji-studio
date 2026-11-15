/* 行迹 · GitHub Pages 静态版配置
 * 只放「可改的配置」，不放任何密钥。改完刷新页面即可生效。
 * LibreTTS 为第三方公共实例（转调微软 Edge 在线朗读），商用前请自行确认条款。
 */
window.LIBRETTS_CONFIG = {
  /* 候选实例：页面启动会静默探测，第一个可用就自动使用。
   * 界面上不放地址输入框 —— 要换/加实例，直接改这里（把自建 Vercel、
   * Docker 或 Cloudflare Worker 地址加进数组即可），刷新页面生效。
   * 官方实例若在你的网络里不给 CORS，会提示按「使用说明.html#cors」处理。 */
  instances: [
    { name: 'LibreTTS 官方公共实例', url: 'https://libretts.is-an.org',
      note: 'MIT 开源项目 LibreSpark/LibreTTS 的公共站，免密钥' },
    { name: '自定义实例 / 自建', url: '', note: '把你的 Worker / Vercel / Docker 地址填在这里' }
  ],

  /* 接口不给 CORS 时用的本机转发桥（tools/bridge.py）。
   * localhost 属于可信来源，https 页面也可以请求它。 */
  bridge: 'http://127.0.0.1:8790',

  /* 默认合成参数，对应 LibreTTS /api/tts：
   *   t/text, v/voice, r/rate(-100~100), p/pitch, o/format(mp3|opus|wav|pcm) */
  voice: 'zh-CN-XiaoxiaoNeural',
  rate: 0,
  pitch: 0,
  format: 'mp3',
  concurrency: 4,       // 逐句并发数，别打爆公共实例
  timeoutMs: 20000,     // 单句正式请求超时
  probeMs: 2500,        // 链路快速探测：第一句不通就整体降级，不逐句干等
  retries: 1,

  /* /api/voices 拉取失败时的内置中文音色兜底（接口正常时可列出中文 91 种） */
  builtinVoices: [
    ['zh-CN-XiaoxiaoNeural', '晓晓 · 温柔女声（通用）'],
    ['zh-CN-XiaoyiNeural', '晓伊 · 知性女声'],
    ['zh-CN-YunxiNeural', '云希 · 活泼男声'],
    ['zh-CN-YunyangNeural', '云扬 · 播音男声'],
    ['zh-CN-YunjianNeural', '云健 · 厚实男声'],
    ['zh-CN-YunxiaNeural', '云夏 · 自然男声'],
    ['zh-CN-XiaochenNeural', '晓辰 · 自然女声'],
    ['zh-CN-XiaohanNeural', '晓涵 · 沉稳女声'],
    ['zh-CN-XiaomengNeural', '晓梦 · 清亮女声'],
    ['zh-CN-XiaomoNeural', '晓墨 · 柔和女声'],
    ['zh-CN-XiaoxuanNeural', '晓萱 · 明快女声'],
    ['zh-CN-XiaoruiNeural', '晓睿 · 少年女声'],
    ['zh-CN-XiaoshuangNeural', '晓双 · 童声'],
    ['zh-CN-YunfengNeural', '云枫 · 沉稳男声'],
    ['zh-CN-YunhaoNeural', '云皓 · 广告男声'],
    ['zh-CN-YunyeNeural', '云野 · 叙事男声'],
    ['zh-CN-YunzeNeural', '云泽 · 醇厚男声'],
    ['zh-CN-liaoning-XiaobeiNeural', '晓北 · 东北话'],
    ['zh-HK-HiuGaaiNeural', '曉佳 · 粤语'],
    ['zh-HK-HiuMaanNeural', '曉曼 · 粤语'],
    ['zh-TW-HsiaoChenNeural', '曉臻 · 台湾国语'],
    ['zh-TW-HsiaoYuNeural', '曉雨 · 台湾国语'],
    ['zh-CN-XiaoxiaoMultilingualNeural', '晓晓 · 多语版（接口默认值）']
  ],

  /* 静态成品：GitHub Actions 构建后发布到同目录，页面按相对路径读取，永不过期 */
  latestManifest: 'media/latest/manifest.json'
};

/* ============================================================
   成片栏目配置 PLAN_CONFIG —— 「每一镜长什么样、念什么」的数据契约
   ------------------------------------------------------------
   城市素材在 data/cities.js；这里决定素材怎么被排成画面行 / 字幕 / 朗读。
   每一行都由 cities.js 的字段拼出，改这里不需要动 index.html 的渲染代码。
   fields 语法：
     'food.name'      取数组每项第 0 列
     'food.0'         同样按列索引
     'clothes.spring' 取对象字段
     '$text(...)'     固定文案，{name} 等占位会替换
   sep：同一项多列之间的连接符；prefix：每行前缀。
   ============================================================ */
window.XINGJI_PLAN_CONFIG = {
  version: 1,
  /* 衣食住行四栏：标题 + 取哪些字段。想加「夜生活」一栏就往这里加一项 */
  sections: [
    { key: 'clothes', title: '衣 / 分季穿搭', sub: '衣  /  THE FOUR ESSENTIALS',
      lead: '先说穿什么，按季节准备这几样',
      from: 'clothes', mode: 'seasons' },
    { key: 'food', title: '食 / 必吃榜', sub: '食  /  THE FOUR ESSENTIALS',
      lead: '再说吃什么，本地必吃榜是这几样',
      from: 'food', mode: 'rows', cols: [0, 1, 2, 3], sep: '  —  ', wrap: '（{2} · {3}）' },
    { key: 'stay', title: '住 / 区域建议', sub: '住  /  THE FOUR ESSENTIALS',
      lead: '住哪儿更省心，按区域来挑',
      from: 'stay', mode: 'rows', cols: [0, 1, 2], sep: '  —  ', wrap: '（{2}）' },
    { key: 'transport', title: '行 / 交通指南', sub: '行  /  THE FOUR ESSENTIALS',
      lead: '最后说行，交通这样安排',
      from: 'transport', mode: 'plain' }
  ],
  /* 总览镜的口播引导 */
  overview: { lead: '先看一下这趟旅行的整体安排' },
  /* 逐日路线镜：{day} 天数、{theme} 当日主题、{count} 实际落点数 */
  day: { cols: ['name', 'desc', 'dur', 'cost'], sep: '，', tail: '今日一味：{meal}',
         lead: '第{day}天，{theme}，安排{count}个落点' },
  /* 每镜朗读文本的拼接方式：引导语 + 画面行 → 一句口播。
     引导语同时进字幕、SRT、逐句合成与镜头时长，改这里不用动渲染代码。 */
  speech: { join: '；', end: '。', leadSep: '。' }
};

/* ============================================================
   AI 采编（后台「🤖 AI 采编」页用）
   ------------------------------------------------------------
   默认魔塔 ModelScope 的 OpenAI 兼容推理接口。

   模型清单完全由接口返回：后台点「🔌 连接测试」或「↻ 刷新可用模型」时
   调用 GET {base}/models，下拉只渲染接口真实返回的 ID，本项目不内置任何
   写死的模型表。模型会下线、会新增，写死就会失效。
   若服务商未实现 /models 或网络不通，页面明确提示，并允许手动填模型 ID，
   绝不用一份「内置候选列表」冒充接口返回。

   Token 在 https://modelscope.cn/my/myaccesstoken 免费获取，只存本机 localStorage。
   浏览器直连若被 CORS 拦，把 mode 改成 'bridge' 并跑 tools/ai_bridge.py。
   ============================================================ */
window.XJ_AI_CONFIG = {
  providers: [
    { name: '魔塔 ModelScope（默认）', base: 'https://api-inference.modelscope.cn/v1',
      tokenUrl: 'https://modelscope.cn/my/myaccesstoken',
      note: '免费额度 · OpenAI 兼容 · 无需自建服务' },
    { name: '自定义 OpenAI 兼容端点', base: '', tokenUrl: '',
      note: '填你自己的 base，例如自建 vLLM / Ollama / 云厂商' }
  ],

  /* 模型清单不写死：运行时调用 GET {base}/models 拉取，下拉只显示接口真实返回的 ID。
     接口不可达 / 未实现时不做「内置候选列表」伪装，页面会提示并允许手动填模型 ID。
     换服务商、换 base、换连接方式都会清空已拉取的列表，避免拿 A 家的模型去调 B 家。 */
  modelsPath: '/models',       // OpenAI 兼容 GET 模型列表端点
  /* 仅用于把接口返回的长列表排个序（不是写死模型，不含任何具体 ID） */
  prefer: ['qwen3.5', 'qwen3', 'qwen2.5', 'qwen', 'glm', 'deepseek'],

  /* 公开检索源：按顺序尝试，任一成功即停，并把实际命中的源名写进城市 source 字段。
     全部失败才降级为「模型自带知识」，状态里写明「N 个源全部不可用」，不假装检索成功。
     纯前端直连受各站 CORS 策略限制；「本机桥」模式下由 ai_bridge.py 代理，不受此限。
     想加源就往数组里加一项：kind 支持 mediawiki / rest / bridge / extract。
     注意：这里只放公开事实资料入口，不放需要密钥或违反 robots 的抓取地址。 */
  wiki: 'https://zh.wikipedia.org/w/api.php',   // 兼容旧配置（单源）
  wikiSources: [
    { name:'维基百科 API', kind:'mediawiki', base:'https://zh.wikipedia.org/w/api.php' },
    { name:'维基百科 REST 摘要', kind:'rest', base:'https://zh.wikipedia.org/api/rest_v1/page/summary/' }
  ],
  bridge: 'http://127.0.0.1:8791',
  mode: 'direct',          // 'direct' | 'bridge'

  /* 四类请求分开计时。连接测试只是「一句可用」的最小推理（约 3 秒），
     而「全网检索并生成」要让模型吐一整份城市 JSON，慢得多。
     以前两者都吃 30 秒，长输出被 abort，还被误报成 CORS。 */
  modelsTimeoutMs: 12000,   // GET /models
  pingTimeoutMs:   20000,   // 连接测试的最小推理
  wikiTimeoutMs:   8000,    // 全网检索（失败自动降级，不阻断生成）
  genTimeoutMs:    120000,  // 完整生成：2 分钟，可在 config.js 调大
  briefMaxTokens:  1200,    // 超时后自动用「精简提示」重试一次的输出上限
  temperature: 0.3
};
