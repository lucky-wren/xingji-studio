/* 行迹 · 全站规划配置
   规划层唯一的配置文件，与视频合成无关。
   改这个文件 → git push → 所有访客生效；本机改动导出后才全站生效。
   三层优先级：data/cities.js 基线（只读） < 本文件 < localStorage 本机草稿。
   图片字段留空即回到第一版视觉；填 assets/xxx.jpg 使用自备授权图片。
   校验：python3 tools/validate_plan_config.py data/plan-config.js
   ------------------------------------------------------------ */
window.XJ_PLAN_CONFIG = {
  "version": 2,
  "baseDate": "2026-11-09",
  "theme": {
    "brandName": "",
    "brandSub": "",
    "brandIcon": "",
    "brandImage": "",
    "paper": "",
    "card": "",
    "ink": "",
    "ink2": "",
    "mute": "",
    "line": "",
    "accent": "",
    "accent2": "",
    "accentSoft": "",
    "bgImage": "",
    "bgOverlay": 0,
    "radius": "",
    "font": ""
  },
  "cityOverrides": {},
  "hiddenCityIds": [],
  "customCities": [],
  "regions": [
    "华北",
    "东北",
    "华东",
    "华中",
    "华南",
    "西南",
    "西北"
  ],
  "sections": {},
  "texts": {
    "genericNote": "【通用建议】不是具体景点名称，出行前请换成当地实际地点",
    "verifyNote": "票价、营业时间、预约状态请按「灵感来源」页出行前核对",
    "footerNote": ""
  }
};
