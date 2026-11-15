# 行迹 · 行程成片工作台

把**完整行程规划**和**行程成片**做成一个可直接部署到 GitHub Pages 的静态站点。选城市、天数、风格与月份，工作台生成逐日路线、衣食住行、地图与视频分镜；逐句合成人声后，由音频的真实时长统一决定帧长、字幕窗口、SRT 与音轨位置。

站点是纯静态的：没有服务端、没有本地数据库、不需要安装依赖。所有合成在浏览器完成；也可以选用 GitHub Actions 预先重建成品，让网站打开即可播放。

---

## 1 快速开始（免登录，只需要一个 Token）

```text
1) 把压缩包全部文件解压到一个空文件夹（index.html 与 deploy.bat 同一层）
2) 按 TOKEN_GUIDE.html 生成一次 GitHub Token，勾 repo + workflow
3) 双击 deploy.bat → 粘贴 Token → 回车
4) 等 1–3 分钟，打开脚本打印的网址并收藏
```

`deploy.bat` 调 `deploy.py`（仅 Python 3.8+ 标准库，不用 pip、不用装 git、不用 SSH、不用浏览器登录、不修改本机 git 配置）：校验身份 → 仓库不存在就自动建 `xingji-studio` → 逐文件比对 Git blob SHA、只上传变化的文件、合成**一次提交** → 自动把 Pages Source 设为 GitHub Actions → 触发一次部署。以后改完文件再双击一次即可，没有变化就不提交，不会触发空的 Actions。

想换仓库名：`set GITHUB_REPO=用户名/别的名字`，或 `python deploy.py --repo 用户名/别的名字`，或写进同目录 `repo.txt`。不想每次粘贴就把 Token 存成同目录 `token.txt`（已进 `.gitignore`，不会上传）。只想看会传哪些文件：`python deploy.py --dry-run`（不联网、不读 Token）。

**仍然可以用 git**（两条路结果一样）：

```text
git add . && git commit -m init && git push
# 仓库 Settings → Pages → Build and deployment → Source 选 GitHub Actions
```

打开 `https://<用户名>.github.io/<仓库名>/` 即可。也可以本地双击 `index.html` 或随包提供的 `旅行灵感工作台.html`，工作台与本地一键成片都可直接使用。

首次使用建议先看 `0_先看这个.html` 与 `TOKEN_GUIDE.html`，再打开「⚙ 后台管理」熟悉城市数据。

---

## 2 界面

工作台分两层导航：

- **顶层 6 个主标签**：总览 / 衣食住行 / 路线规划 / 游玩地图 / 灵感来源 / 视频合成。点主标签会定位到对应内容区。
- **视频合成页右侧栏顶部的 5 段工具栏**：内容 / 字幕 / 声音 / 时间轴 / 导出。预览台在左列，工具条与参数面板同在右侧一列；点哪段，右侧同一块参数面板就显示哪段内容，并滚动定位、回显「已定位」。画布与播放条始终留在原位，不重建、不打断播放。

右侧栏可折叠，预览台头部「⌗ 专注」只收起参数面板、保留窄工具条，让画面铺宽。面板顶部会回显当前定位的模块名。

模块功能：

| 模块 | 内容 |
|---|---|
| 内容 | 行程摘要、画幅、清晰度、节奏、一键生成并导出 |
| 字幕 | 逐句编辑清单、显示方式（打字机 / 逐字高亮 / 直接显示）；样式设置收进「更多」 |
| 声音 | 总音量、无配乐 / 上传自定义配乐；人声试听与逐句合成在常驻卡，人声 / 配乐音量、讲解文稿、水印收进「更多」 |
| 时间轴 | 逐镜阶段表、字幕编辑、分镜排序与勾选 |
| 导出 | 导出格式与各类素材导出 |

### 2.1 字幕显示方式

字幕条与画面大字共用同一份逐字揭示进度，按这一镜的讲解时间推进：

| 方式 | 效果 |
|---|---|
| 打字机 · 逐字出现（默认） | 字随讲解逐字出现，未出现的字不占位，可带打字光标 |
| 整句 · 逐字高亮 | 整句一直显示，已读部分变色 |
| 整句 · 直接显示 | 不做逐字效果 |

可选速度（慢 / 偏慢 / 标准 / 偏快 / 快）。进度由**这一帧的绝对时间**决定，预览与逐帧导出读同一个时间，成片里同样逐字推进。

### 2.2 音量

主输出默认 **100%**。「声音」页直接调总音量，人声与配乐音量收在「⚙ 更多」里；改任意一路会让混音缓存失效，预览试听与成片导出读同一组数值。默认无配乐，需要时上传自己的音频文件。

离线混音会做响度归一（默认目标 −11 LUFS）与软限幅，输入素材电平偏低时会按测得响度自动补足，避免成片整体偏小。归一增益上限 16 倍，软限幅把真峰值控制在约 −1 dBTP。

---

## 3 人声：LibreTTS 微软神经音色

接口来自开源项目 [LibreSpark/LibreTTS](https://github.com/LibreSpark/LibreTTS)（MIT）：

```text
GET  /api/tts?t=文本&v=音色&r=语速&p=语调&o=mp3|opus|wav|pcm
POST /api/tts  {"text","voice","rate","pitch","format"}
GET  /api/voices?l=zh&f=1
```

| 参数 | GET | 说明 |
|---|---|---|
| 文本 | `t` | 单次上限 10000 单位（中文算 2） |
| 音色 | `v` | 由 `/api/voices` 返回，项目不内置模型表 |
| 语速 | `r` | −100 ～ +100，默认 0 |
| 语调 | `p` | −100 ～ +100，默认 0 |
| 格式 | `o` | `mp3 / opus / wav / pcm` |

工作台先走 GET（simple request，不触发 CORS preflight），失败再试 POST。音色下拉优先读取 `/api/voices?l=zh&f=1`。实例地址、音色、语速、并发与超时都在 `config.js` 配置，页面启动静默探测并选用第一个可用实例。

**试听与合成是两条独立链路**：试听只发 1 个请求、只播一次，不写音轨、不改时间轴；点「逐句合成到人声轨」才进入成片链路。

**隐私与条款**：文案会经第三方实例服务器转发到微软，SSML 在站方服务器组装；商用前请自行确认微软与实例方条款。隐私内容请用自建实例或本机桥。公共实例可用性不由本站保证，界面会实测并明确提示。

### 3.1 CORS 三种解法

| 方案 | 怎么做 | 适合 |
|---|---|---|
| 公共实例直接可用 | 无需操作 | 最理想 |
| 本机转发桥 | `python tools/bridge.py`（默认 `127.0.0.1:8790`） | 本机使用；localhost 是可信来源，https 页面也能请求 |
| Cloudflare Worker | 部署 `tools/cors-worker.js`，把域名写进 `config.js` 的 `instances` 并 push | 让任何访客打开网页就能合成 |

`tools/bridge.py` 与 `tools/cors-worker.js` 都只做转发、不落盘，支持 GET / POST / OPTIONS。

---

## 4 同步模型

```text
字幕逐句 → LibreTTS 逐句合成 → AudioBuffer.duration = durs[]
        → 同一个 durs[] 同时生成：
            帧长       = head + durs[i] + 切镜余量
            字幕窗口   = [subStart, subStart + durs[i]]
            SRT        = 逐条起止
            音轨 clip  = OfflineAudioContext 里的采样位置
        → 播放 / 导出只读一个主时钟 AudioContext.currentTime
```

先得到确定的音频文件，再由它生成全部时间码；播放期间时间轴只读。这与 B 站 / YouTube / 剪映的播放器模型一致，区别只是音频来自逐句 HTTP 响应而不是服务端预合成。

浏览器系统嗓音（`speechSynthesis`）不进入时间轴：它不进网页音频图、不预先给出时长、不能写进录制文件。

### 4.1 一镜一源

每镜只产一份内容 `sceneData(sc) = {title, sub, lines[]}`：画面行、字幕条、SRT、朗读稿与帧长都读同一份 `lines`。改任意一句，画面文字、字幕、人声、SRT 与该帧时长一起变。

---

## 5 导出

| 出口 | 内容 |
|---|---|
| ⚡ 快速导出 WebM | WebCodecs 非实时编码 VP8/VP9 + Opus，本地 EBML 封装；耗时与片长无关 |
| ↓ 完整混音 WAV | 人声 + 配乐，OfflineAudioContext 预混 |
| ↓ 字幕 SRT / 文稿 | 按 `durs[]` 生成，逐字等于画面字幕 |
| ↓ PNG 分镜包 ZIP | 逐镜高清帧图 + 时间轴 JSON + SRT + 说明 |
| ↓ 制作包 JSON | 文案 + 接口 / 音色 / 语速 + 每镜真实时长，供 CI 重建 |
| 📺 仅字幕 | 明确无配音，秒级出片 |

浏览器 WebCodecs 在 Chromium 里产出 VP8/VP9 + Opus 的 WebM；要通用 H.264/AAC MP4，用「PNG 分镜包 + 制作包」交给 `tools/build_film.py`（本机或 Actions，需要 ffmpeg）。

水印烧录在 `drawScene()` 输出层最后一步，因此预览、快速导出 WebM、PNG 分镜包、无损工程包帧序列、GIF 与「分镜包 → CI 重建 MP4」链路全部自动带水印。图片水印以 Data URL 内嵌进制作包 JSON，载入时自动还原。

### 5.1 打开就有成品（可选）

```text
1) 工作台点「↓ 制作包 JSON」→ 存成 media/source/project.json
2) 工作台点「PNG 分镜包」→ 帧图放进 media/source/frames/0001.png …
3) GitHub Actions 手动跑「重建静态成品（LibreTTS 神经人声）」
4) 构建器逐句合成 → ffprobe 读 durs[] → SRT / MP3 / 三轨 MP4
   → 7 项硬校验全过才原子发布到 media/latest/
5) 页面按相对路径读 media/latest/manifest.json，刷新不丢、横竖切换秒开
```

硬校验不合格直接红灯、不发布半成品；软字幕轨可开关，不烧录。

---

## 6 城市数据与后台管理

`data/` 是内容层，`config.js` 是栏目与接口配置层，页面只读这两处：

| 文件 | 作用 |
|---|---|
| `data/cities.js` | 36 城基线快照（真实景点、坐标、来源） |
| `data/cities.full.js` | 全国 410 城完整规划（运行时真源） |
| `data/national-cities.js` / `.json` | 34 省级行政区 / 7 大区 / 410 城事实层 |
| `data/plan-config.js` | 全站视觉、栏目结构、城市覆盖与隐藏 |
| `data/cities.schema.md` | 字段说明与校验规则 |

410 城分三层，界面上明确区分：

| 层 | 数量 | 内容 |
|---|---|---|
| 实测快照 | 8 | 经纬度 / 景点 / 美食 / 住宿 / 预算 / 来源链接（基准 2026-11-09） |
| 结构化模板 | 28 | 名称 + 通用场景落点，带【通用建议】 |
| 结构化通用框架 | 374 | 名称 / 省份 / 大区 + 自动展开的完整行程框架 |

通用框架的落点是「老城街区 / 滨水步道 / 本地市集」这类场景，标注【通用建议】与「请核对」，**不编造真实景点、票价、营业时间**。

**后台管理**（工作台顶栏「⋯ 更多 → ⚙ 后台管理」，单文件版内嵌同一套后台）提供列表、搜索、筛选、排序、分页、详情（全字段）、新增、编辑、删除与恢复、批量操作、去重、CSV/JSON 导入、分类字典、全站视觉、导入导出、操作日志与上线前自检。新增城市只填名字即可得到 12 落点 / 6 美食 / 3 住宿 / 4 交通与逐日路线。

**AI 采编**：后台可接魔塔 ModelScope（或任意 OpenAI 兼容接口），模型清单由 `GET /v1/models` 返回，项目不内置任何模型 ID。填城市名 → 按 `config.js` 的 `wikiSources` 顺序尝试公开检索源 → 模型整合 → 严格 JSON 校验 → 一键入库。AI 不可用时可点「📄 本地框架」离线出一份明确标注「不是 AI 采编」的可编辑草稿。详见 `AI采编说明.md`。

**生效范围**：后台改动先写本机 localStorage，工作台刷新即可预览；要所有访客看到，需在后台「导入 / 导出」下载 `cities.full.js` / `plan-config.js` 覆盖仓库并 push。字段、三层数据、添加路径与上线闭环见 `数据配置说明.md`。

> `data/cities.full.js`、`data/national-cities.js`、`data/plan-config.js` 必须与 `index.html` 一起部署，并在页面脚本之前加载。

---

## 7 目录结构

```text
.
├── index.html                    完整工作台
├── admin.html                    城市数据管理后台
├── config.js                     LibreTTS 实例 / 检索源 / 成片栏目结构
├── libretts-bridge.js            逐句合成 → 时间轴 → 静态成品读取
├── data/                         城市数据与全站配置（见第 6 节）
├── .nojekyll                     Pages 必需
├── .github/workflows/
│   ├── pages.yml                 部署 + 数据硬校验
│   └── build-film.yml            可选：重建静态成品
├── media/latest/                 静态成品（Actions 产出，相对路径读取）
├── media/source/                 制作包与帧图
├── tools/                        转发桥 / mock / 构建器 / 校验器 / 打包与单文件生成
├── tests/                        浏览器端到端与冒烟回归
├── 0_先看这个.html               最短上手路径
├── 使用说明.html                 图文操作步骤
└── AI采编说明.md / 数据配置说明.md
```

上线前可跑 `python3 tools/validate_full_data.py` 与 `python3 tools/validate_plan_config.py`，两个校验器已接进 `pages.yml` 部署前步骤。

---

## 8 边界

1. 第三方公共实例的可用性、CORS 与限流不由本站保证；页面会实测并给出解法。
2. 浏览器快速导出是 WebM；通用 H.264/AAC MP4 走 `tools/build_film.py`。
3. 文案经第三方服务器，见第 3 节隐私说明。
4. 行程内容为 2026-11-09 的抓取快照与结构化攻略，票价、营业时间、预约状态请出行前核对。
5. 374 座通用框架城不是实测 POI，后台可逐城替换为真实内容。
6. `media/latest/` 的成品需手动跑一次 workflow 才会生成；默认站点打开是「暂无静态成品」，工作台与本地一键成片不受影响。

---

## 9 许可与致谢

- 工作台代码：本仓库，可自由使用。
- [LibreTTS](https://github.com/LibreSpark/LibreTTS)：MIT，公共实例由其维护者提供。
- 微软 Edge 神经音色：由微软提供，经 LibreTTS 转调；**非官方接口，商用前确认条款**。
- 静态成品架构参考 [lucky-wren/daily-news-studio](https://github.com/lucky-wren/daily-news-studio)。
