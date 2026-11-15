# media/source/ · 放你自己的构建输入

这个目录**默认空**。想让 GitHub Actions 重建「打开就有」的静态成品时，放两样东西：

```text
media/source/
├── project.json        ← 工作台「↓ 制作包 JSON」导出，重命名即可
└── frames/
    ├── 0001.png        ← 工作台「PNG 分镜包」里的逐镜帧图
    ├── 0002.png
    └── …
```

然后到 GitHub Actions 手动跑 **「重建静态成品（LibreTTS 神经人声）」**。

构建器会逐句调 LibreTTS → ffprobe 读每句真实时长 `durs[]` → 用同一份 `durs[]`
生成 SRT、逐镜停留、音轨位置 → 产出 `media/latest/` 下的
`broadcast.mp3` / `captions.srt` / `film.mp4` / `manifest.json`。

**7 项硬校验全过才发布**，失败保留上一版成品，不出半成品。

> 没有 project.json 时，工作台与本地一键成片照常可用，只是站点首页的
> 「☁ 站点静态成品」区会显示「暂无」。
