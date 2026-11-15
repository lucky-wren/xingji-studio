/* 生成后台 / 工作台界面截图（验收用） */
import { createRequire } from 'module';
const require = createRequire('/usr/local/lib/node_modules/');
const { chromium } = require('playwright');
const BASE = process.env.BASE_URL || 'http://127.0.0.1:8810';
const OUT = process.env.OUT_DIR || '/data/workspace';

(async () => {
  const browser = await chromium.launch({ headless: true,
    executablePath: process.env.CHROME_PATH || '/usr/local/bin/chromium',
    args: ['--no-sandbox', '--autoplay-policy=no-user-gesture-required'] });
  const ctx = await browser.newContext({ viewport: { width: 1500, height: 1000 } });
  const page = await ctx.newPage();
  page.on('dialog', d => d.accept());

  await page.goto(BASE + '/admin.html', { waitUntil: 'domcontentloaded' });
  await page.evaluate(() => { localStorage.removeItem('xj_admin_v1');
    localStorage.removeItem('xj_admin_draft_v1'); localStorage.removeItem('xj_plan_draft_v1'); });
  await page.reload({ waitUntil: 'domcontentloaded' }); await page.waitForTimeout(400);
  await page.screenshot({ path: OUT + '/_shot_admin_overview.png' });

  await page.evaluate(() => XJ_ADMIN.go('cities')); await page.waitForTimeout(250);
  await page.screenshot({ path: OUT + '/_shot_admin_list.png' });

  await page.evaluate(() => XJ_ADMIN.openEdit('nat_003')); await page.waitForTimeout(250);
  await page.screenshot({ path: OUT + '/_shot_admin_edit.png' });
  await page.evaluate(() => closeDrawer());

  await page.evaluate(() => { XJ_ADMIN.go('publish'); XJ_ADMIN.runCheck(); });
  await page.waitForTimeout(200);
  await page.screenshot({ path: OUT + '/_shot_admin_publish.png' });

  const w = await ctx.newPage();
  await w.goto(BASE + '/index.html', { waitUntil: 'domcontentloaded' });
  await w.waitForTimeout(900);
  await w.screenshot({ path: OUT + '/_shot_work_overview.png' });
  await w.evaluate(() => { pickDest('nat_003'); rebuildTrip(); renderAll(); switchTab('route'); });
  await w.waitForTimeout(400);
  await w.screenshot({ path: OUT + '/_shot_work_route.png' });

  console.log('shots done');
  await browser.close();
})().catch(e => { console.error(e); process.exit(1); });
