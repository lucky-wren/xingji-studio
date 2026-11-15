#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""全国 410 城内置后，同步更新回归断言（基线 36 → 410）

所有替换都是「精确字符串 → 精确字符串」，脚本会校验每处命中数，
不做模糊替换，避免为了通过而放宽检查。
"""
import os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

E2E = os.path.join(ROOT, 'tests', 'e2e.mjs')
PLAN = os.path.join(ROOT, 'tests', 'smoke_plan.mjs')
V2 = os.path.join(ROOT, 'tests', 'smoke_v2.mjs')


def patch(path, pairs):
    s = open(path, encoding='utf-8').read()
    for old, new in pairs:
        n = s.count(old)
        if n != 1:
            print('ERROR in %s: count=%d for %r' % (os.path.basename(path), n, old[:70]))
            sys.exit(1)
        s = s.replace(old, new, 1)
    open(path, 'w', encoding='utf-8').write(s)
    print('patched %s (%d replacements)' % (os.path.basename(path), len(pairs)))


patch(E2E, [
    ("assert('36 座目的地', await page.locator('.dest').count() === 36, await page.locator('.dest').count());",
     "assert('410 座目的地（36 城快照 + 374 城完整规划）', await page.locator('.dest').count() === 410, await page.locator('.dest').count());"),
    ("assert('城市数据来自独立配置文件 data/cities.js（页面不再内嵌 36 城）',\n    cityBase.loaded && cityBase.builtin === 36 && cityBase.total === 36 && cityBase.custom === 0,\n    JSON.stringify(cityBase));",
     "assert('城市数据来自独立配置文件（36 城快照 + 374 城完整规划内置）',\n    cityBase.loaded && cityBase.builtin === 410 && cityBase.total === 410 && cityBase.custom === 0,\n    JSON.stringify(cityBase));\n"
     "  assert('全国 410 城完整规划数据已加载且每城都有 12 个落点',\n"
     "    await page.evaluate(() => !!(window.XJ_CITIES_FULL && window.XJ_CITIES_FULL.total === 410 &&\n"
     "      window.XJ_CITIES_FULL.cities.every(c => c.spots.length === 12 && c.food.length === 6 &&\n"
     "        c.stay.length === 3 && c.transport.length === 4))),\n"
     "    await page.evaluate(() => window.XJ_CITIES_FULL && window.XJ_CITIES_FULL.total));\n"
     "  assert('374 城为结构化通用建议，不编造票价与真实景点',\n"
     "    await page.evaluate(() => {\n"
     "      const g = window.XJ_CITIES_FULL.cities.filter(c => !c.baseline);\n"
     "      return g.length === 374 && g.every(c => c.confidence === 'generated' &&\n"
     "        c.spots.every(s => s[3] === '请核对' && s[5].includes('【通用建议】')));\n"
     "    })), 'generated / 请核对 / 通用建议');"),
    ("/内置 36 城/.test(statText) &&", "/内置 410 城/.test(statText) &&"),
    ("assert('导入一座城市后立刻进入目的地列表（37 城）',\n    afterAdd.total === 37 && afterAdd.custom === 1 && afterAdd.inList && /37/.test(afterAdd.count),",
     "assert('导入一座城市后立刻进入目的地列表（411 城）',\n    afterAdd.total === 411 && afterAdd.custom === 1 && afterAdd.inList && /411/.test(afterAdd.count),"),
    ("newRegion.ok && newRegion.regions.includes('港澳台') && newRegion.total === 38 &&",
     "newRegion.ok && newRegion.regions.includes('港澳台') && newRegion.total === 412 &&"),
    ("/已存在/.test(rejects.dup) && rejects.total === 38,",
     "/已存在/.test(rejects.dup) && rejects.total === 412,"),
    ("persisted.total === 38 && persisted.custom === 2 && /38/.test(persisted.count) &&\n    persisted.top === '38 城',",
     "persisted.total === 412 && persisted.custom === 2 && /412/.test(persisted.count) &&\n    persisted.top === '412 城',"),
    ("assert('一键恢复默认城市后回到 36 城 / 7 大区',\n    cleaned.total === 36 && cleaned.custom === 0 && cleaned.regions === 8,",
     "assert('一键恢复默认城市后回到 410 城 / 7 大区',\n    cleaned.total === 410 && cleaned.custom === 0 && cleaned.regions === 8,"),
    ("wizMin.total === 38 && wizMin.hero === '只填名字城'", "wizMin.total === 412 && wizMin.hero === '只填名字城'"),
    ("/✖/.test(wizFail.msg) && /城市名/.test(wizFail.msg) && wizFail.total === 38,",
     "/✖/.test(wizFail.msg) && /城市名/.test(wizFail.msg) && wizFail.total === 412,"),
])

patch(PLAN, [
    ("A('默认仍是 36 城 / 0 隐藏 / 0 视觉覆盖',\n    base.total === 36 && base.builtin === 36 && base.hidden === 0 && base.overrides === 0,",
     "A('默认是 410 城内置 / 0 隐藏 / 0 视觉覆盖',\n    base.total === 410 && base.builtin === 410 && base.hidden === 0 && base.overrides === 0,"),
    ("A('基线快照已保存（删除/恢复靠它）', base.baseSaved === 36, base.baseSaved);",
     "A('基线快照已保存（删除/恢复靠它）', base.baseSaved === 410, base.baseSaved);"),
    ("A('第一次新增成功（37 城）', dup1.total === 37 && dup1.custom === 1, JSON.stringify(dup1));",
     "A('第一次新增成功（411 城）', dup1.total === 411 && dup1.custom === 1, JSON.stringify(dup1));"),
    ("dup2.total === 37 && dup2.custom === 1", "dup2.total === 411 && dup2.custom === 1"),
    ("builtinSame.total === 39 && builtinSame.hasBuiltin", "builtinSame.total === 413 && builtinSame.hasBuiltin"),
    ("A('一键去重后重复组清零', dedup.dups === 0 && dedup.total === 38, JSON.stringify(dedup));",
     "A('一键去重后重复组清零', dedup.dups === 0 && dedup.total === 412, JSON.stringify(dedup));"),
    ("A('内置城「大理」删除后从 D 与侧栏消失', hide1.total === 35 &&",
     "A('内置城「大理」删除后从 D 与侧栏消失', hide1.total === 409 &&"),
    ("A('批量隐藏 3 城 → 33 城', hideMore.total === 33 && hideMore.hidden === 3, JSON.stringify(hideMore));",
     "A('批量隐藏 3 城 → 407 城', hideMore.total === 407 && hideMore.hidden === 3, JSON.stringify(hideMore));"),
    ("A('单城恢复生效', unhide.total === 34 && unhide.hidden === 2, JSON.stringify(unhide));",
     "A('单城恢复生效', unhide.total === 408 && unhide.hidden === 2, JSON.stringify(unhide));"),
    ("A('恢复全部 → 回到 36 城基线', unhideAll.total === 36 && unhideAll.hidden === 0 && unhideAll.builtin === 36,",
     "A('恢复全部 → 回到 410 城基线', unhideAll.total === 410 && unhideAll.hidden === 0 && unhideAll.builtin === 410,"),
    ("A('自定义城单删 / 清空全部都生效', customDel.before === 38 && customDel.afterOne === 37 &&\n    customDel.end === 36 && customDel.custom === 0, JSON.stringify(customDel));",
     "A('自定义城单删 / 清空全部都生效', customDel.before === 412 && customDel.afterOne === 411 &&\n    customDel.end === 410 && customDel.custom === 0, JSON.stringify(customDel));"),
    ("A('数据管理：36 行 / 每行可删 / 批量工具栏 / 底栏动作切换',\n    manageUI.rows === 36 && manageUI.hasDel === 36 &&",
     "A('数据管理：410 行 / 每行可删 / 批量工具栏 / 底栏动作切换',\n    manageUI.rows === 410 && manageUI.hasDel === 410 &&"),
    ("persist.accent === '#00aa88' && persist.hidden.includes('xiamen') && persist.total === 35,",
     "persist.accent === '#00aa88' && persist.hidden.includes('xiamen') && persist.total === 409,"),
])

patch(V2, [
    ("  A('城市总数 +1', added.total === before + 1, before + '→' + added.total);",
     "  A('全国城已内置，点选直接切换、不再复制出重复城', added.total === before, before + '→' + added.total);\n"
     "  A('完整行程来自 cities.full.js（12 落点 / 6 美食 / 3 住宿）',\n"
     "    await page.evaluate(() => { const d = S.dest; return !!(d && d.fromFull && d.generated &&\n"
     "      d.spots.length === 12 && d.food.length === 6 && d.stay.length === 3 && d.clothes && d.sources.length > 0); }),\n"
     "    await page.evaluate(() => S.dest && S.dest.name));"),
    ("  A('成功提示写明生成统计', /已生成/.test(added.msg), added.msg.slice(0, 60));",
     "  A('成功提示写明「已内置完整规划」与落点统计', /已内置完整规划/.test(added.msg) && /落点/.test(added.msg), added.msg.slice(0, 60));"),
])
