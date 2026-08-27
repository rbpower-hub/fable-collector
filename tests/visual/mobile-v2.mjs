import {chromium} from 'playwright';
import fs from 'node:fs/promises';
import path from 'node:path';

const BASE = process.env.FABLE_VISUAL_URL || 'http://127.0.0.1:4173/';
const OUT = path.resolve('visual-artifacts/screenshots/mobile-v2.png');
const dateKey = (date) => {
  const parts = new Intl.DateTimeFormat('en-CA', {
    timeZone:'Africa/Tunis', year:'numeric', month:'2-digit', day:'2-digit',
  }).formatToParts(date).reduce((result, part) => ({...result, [part.type]:part.value}), {});
  return `${parts.year}-${parts.month}-${parts.day}`;
};
const day = (offset) => dateKey(new Date(Date.now() + offset * 86400000));
const generated = new Date().toISOString();
const offStart = new Date(Date.now() + 60 * 60_000);
const offEnd = new Date(Date.now() + 6 * 60 * 60_000);
const familyStart = new Date(Date.now() + 25 * 60 * 60_000);
const familyEnd = new Date(Date.now() + 31 * 60 * 60_000);
const offDay = dateKey(offStart);
const familyDay = dateKey(familyStart);
const offOffset = [day(0), day(1), day(2)].indexOf(offDay);
const familyOffset = [day(0), day(1), day(2)].indexOf(familyDay);
const noGoOffset = [0, 1, 2].find((offset) => offset !== offOffset && offset !== familyOffset);
const offHours = {
  start:offStart.toISOString(), end:offEnd.toISOString(), category:'off_hours', confidence:'Medium', confidence_score:64,
};
const family = {
  start:familyStart.toISOString(), end:familyEnd.toISOString(), category:'family', family_tier:'standard', confidence:'High', confidence_score:88,
};
const lateFamily = {
  start:new Date(Date.now()-30*60_000).toISOString(), end:new Date(Date.now()+150*60_000).toISOString(),
  category:'family', family_tier:'standard', confidence:'Medium', confidence_score:70,
};
const payloads = {
  'status.json': {generated_at:generated, cadence_minutes:60},
  'windows.json': {generated_at:generated, windows:[{
    dest_slug:'gammarth-port.json', dest_name:'Gammarth', required_hours:4, windows:[offHours, family],
  },{
    dest_slug:'sidi-bou-said.json', dest_name:'Sidi Bou Saïd', required_hours:3, windows:[lateFamily],
  }]},
  'rules.normalized.json': {window_hours:{min:4}, wind:{family_max_kmh:22}, sea:{family_max_hs_m:.5}},
  'recommendations.json': {generated_at:generated, recommendations:[]},
  'sites.normalized.json': {home:'gammarth-port', sites:[{name:'Gammarth', slug:'gammarth-port', path:'gammarth-port.json', lat:36.92, lon:10.31, map_lat:36.92, map_lon:10.31, route_kind:'standard', route_points:[]}]},
  'catalog.json': {files:[{path:'gammarth-port.json'}]},
  'index.json': {generated_at:generated, files:['gammarth-port.json']},
  'port-knowledge.json': {ports:[]},
  'gammarth-port.json': {
    meta:{generated_at:generated, rules:{wind:{family_max_kmh:22}, sea:{family_max_hs_m:.5}}},
    hourly:{
      time:[offStart.toISOString(),new Date(offStart.getTime()+2*60*60_000).toISOString(),offEnd.toISOString(),familyStart.toISOString(),new Date(familyStart.getTime()+3*60*60_000).toISOString(),familyEnd.toISOString()],
      wind_speed_10m:[11,15,20,9,12,16], hs:[.25,.35,.45,.2,.3,.4], precipitation:[0,0,0,0,0,0],
      temperature_2m:[25,27,29,24,26,28], apparent_temperature:[26,29,31,25,28,30],
      relative_humidity_2m:[65,60,55,70,64,58], cloud_cover:[10,20,35,5,15,25], uv_index:[1,4,7,0,3,6],
      wind_gusts_10m:[18,22,28,15,19,24], wind_direction_10m:[310,320,330,300,310,320],
      wave_height:[.25,.35,.45,.2,.3,.4], wave_period:[5,5,4.8,5.5,5.2,5], visibility:[10000,10000,10000,10000,10000,10000], weather_code:[0,0,1,0,0,1],
    },
  },
};

await fs.mkdir(path.dirname(OUT), {recursive:true});
const browser = await chromium.launch({headless:true, args:['--no-sandbox']});
const context = await browser.newContext({viewport:{width:390,height:844}, isMobile:true, hasTouch:true, timezoneId:'Africa/Tunis'});
const page = await context.newPage();
const errors = [];
page.on('pageerror', (error) => errors.push(error.message));
await page.addInitScript(({selectedDay}) => {
  localStorage.setItem('lang', 'fr');
  localStorage.setItem('theme', 'nautical');
  localStorage.setItem('fable_board_mode', 'simple');
  localStorage.setItem('fable_simple_default_v1', '1');
  localStorage.setItem('fable_selected_day', selectedDay);
}, {selectedDay:offDay});
await page.route('**/*.json', async (route) => {
  const file = new URL(route.request().url()).pathname.split('/').pop();
  await route.fulfill({status:200, contentType:'application/json', body:JSON.stringify(payloads[file] || {})});
});
await page.goto(BASE, {waitUntil:'domcontentloaded'});
await page.waitForSelector('.simple-hero[data-verdict-state="OFF_HOURS"]', {state:'visible'});
await page.waitForTimeout(300);
const initial = await page.evaluate(() => ({
  title:document.querySelector('.simple-verdict')?.textContent?.trim(),
  rows:document.querySelectorAll('.simple-window-card').length,
  inProgressRows:document.querySelectorAll('.simple-window-item.in-progress').length,
  inProgressText:document.querySelector('.simple-window-item.in-progress')?.textContent?.replace(/\s+/g,' ').trim(),
  tabs:document.querySelectorAll('.simple-day[role="tab"]').length,
  selectedTab:document.querySelector('.simple-day[aria-selected="true"]')?.dataset.simpleDay,
  panelOwner:document.querySelector('#simple-selected-day-content')?.getAttribute('aria-labelledby'),
  panelTone:document.querySelector('.simple-day-context')?.dataset.selectedTone,
  connectorHeight:parseFloat(getComputedStyle(document.querySelector('.simple-day[aria-selected="true"]'),'::after').height),
  panelBorder:parseFloat(getComputedStyle(document.querySelector('#simple-selected-day-content')).borderTopWidth),
  selectorBeforeDecision:Boolean(document.querySelector('#simple-three-days')?.compareDocumentPosition(document.querySelector('#simple-decision')) & Node.DOCUMENT_POSITION_FOLLOWING),
  navVisible:getComputedStyle(document.querySelector('.simple-bottom-nav')).display !== 'none',
  weatherItems:document.querySelectorAll('.simple-weather-item').length,
  weatherIcons:Array.from(document.querySelectorAll('.simple-weather-icon svg')).map((icon) => icon.getBoundingClientRect().width),
  weatherKinds:Array.from(document.querySelectorAll('.simple-weather-item')).map((item) => item.dataset.weatherKind),
  weatherValueSize:parseFloat(getComputedStyle(document.querySelector('.simple-weather-value')).fontSize),
  overline:Boolean(document.querySelector('.simple-overline')),
  confidenceVisible:getComputedStyle(document.querySelector('.simple-confidence')).display !== 'none',
  qualityText:document.querySelector('.simple-confidence')?.textContent?.replace(/\s+/g,' ').trim(),
  qualityHasPercent:/\d+\s*%/.test(document.querySelector('.simple-confidence')?.textContent || ''),
  verdictRect:(() => { const box = document.querySelector('.simple-verdict')?.getBoundingClientRect(); return box ? {left:box.left,top:box.top,right:box.right,bottom:box.bottom} : null; })(),
  confidenceRect:(() => { const box = document.querySelector('.simple-confidence')?.getBoundingClientRect(); return box ? {left:box.left,top:box.top,right:box.right,bottom:box.bottom} : null; })(),
  confidenceBesideVerdict:(() => {
    const verdict = document.querySelector('.simple-verdict')?.getBoundingClientRect();
    const confidence = document.querySelector('.simple-confidence')?.getBoundingClientRect();
    return Boolean(verdict && confidence && confidence.left > verdict.left && Math.abs(confidence.top - verdict.top) < 80);
  })(),
  legacyFamilyHidden:['family-verdict-hero','family-planning-host'].every((id) => {
    const node = document.getElementById(id);
    return !node || getComputedStyle(node).display === 'none';
  }),
  overflow:document.documentElement.scrollWidth - document.documentElement.clientWidth,
}));
if (!/hors horaires/i.test(initial.title || '')) throw new Error(`unexpected title: ${initial.title}`);
if (initial.rows !== 2) throw new Error(`expected 2 visible selected-day rows, got ${initial.rows}`);
if (initial.inProgressRows !== 1 || !/En cours.*Temps restant.*durée familiale complète/is.test(initial.inProgressText || '')) throw new Error(`in-progress family window is not explained: ${initial.inProgressText}`);
if (initial.tabs !== 3) throw new Error(`expected 3 day tabs, got ${initial.tabs}`);
if (initial.selectedTab !== String(offOffset)) throw new Error(`unexpected initial selected tab: ${initial.selectedTab}`);
if (initial.panelOwner !== `simple-day-tab-${offOffset}`) throw new Error(`selected panel belongs to ${initial.panelOwner}`);
if (initial.panelTone !== 'off-hours') throw new Error(`unexpected selected panel tone: ${initial.panelTone}`);
if (initial.connectorHeight < 16 || initial.panelBorder < 2) throw new Error('selected day is not visually connected to its panel');
if (!initial.selectorBeforeDecision) throw new Error('three-day selector must precede the decision');
if (!initial.navVisible) throw new Error('bottom navigation is hidden');
if (initial.weatherItems < 4) throw new Error(`expected four weather context cards, got ${initial.weatherItems}`);
if (initial.weatherIcons.length < 4 || Math.min(...initial.weatherIcons) < 21) throw new Error(`weather icons are missing or too small: ${initial.weatherIcons}`);
if (!['temperature','uv','sky','rain'].every((kind) => initial.weatherKinds.includes(kind))) throw new Error(`weather icon kinds are incomplete: ${initial.weatherKinds}`);
if (initial.weatherValueSize < 16) throw new Error(`weather values are too small: ${initial.weatherValueSize}px`);
if (initial.overline) throw new Error('redundant decision overline is still visible');
if (!initial.confidenceVisible || !initial.confidenceBesideVerdict) throw new Error(`confidence must remain beside the verdict on mobile: ${JSON.stringify(initial)}`);
if (initial.qualityHasPercent) throw new Error(`forecast quality must not be shown as a percentage: ${initial.qualityText}`);
if (!/Qualité des prévisions.*Moyenne/i.test(initial.qualityText || '')) throw new Error(`unexpected forecast quality: ${initial.qualityText}`);
if (!initial.legacyFamilyHidden) throw new Error('legacy Family verdict or planning is visible in Simple View');
if (initial.overflow > 2) throw new Error(`horizontal overflow: ${initial.overflow}px`);

await page.locator(`[data-simple-day="${familyOffset}"]`).click();
await page.waitForSelector('.simple-hero[data-verdict-state="GO_FAMILY"]');
await page.waitForSelector(`[data-simple-day="${familyOffset}"][aria-selected="true"]`);
await page.waitForSelector('.simple-day-context[data-selected-tone="good"]');
const tomorrowRows = await page.locator('.simple-window-card').count();
if (tomorrowRows !== 1) throw new Error(`tomorrow should have one row, got ${tomorrowRows}`);
const tomorrowQuality = await page.locator('.simple-confidence').textContent();
if (!/Qualité des prévisions.*Élevée/is.test(tomorrowQuality || '')) throw new Error(`unexpected GO forecast quality: ${tomorrowQuality}`);
await page.locator('.simple-window-card').click();
await page.waitForSelector('.simple-window-details:not([hidden])');
const inlineWindow = await page.evaluate(() => ({
  simpleMode:document.body.classList.contains('simple-board-mode'),
  expanded:document.querySelector('.simple-window-card')?.getAttribute('aria-expanded'),
  details:document.querySelector('.simple-window-details')?.textContent?.replace(/\s+/g,' ').trim(),
}));
if (!inlineWindow.simpleMode || inlineWindow.expanded !== 'true') throw new Error(`window click left Simple View: ${JSON.stringify(inlineWindow)}`);
if (!/Durée disponible.*Durée minimale.*Qualité des prévisions/is.test(inlineWindow.details || '')) throw new Error(`inline window details are incomplete: ${inlineWindow.details}`);
await page.locator('[data-simple-action="more"]').click();
await page.waitForSelector('#simple-more-menu:not([hidden])');
const moreActions = await page.locator('#simple-more-menu .simple-more-action').count();
if (moreActions !== 3) throw new Error(`More menu should expose 3 actions, got ${moreActions}`);
await page.keyboard.press('Escape');
await page.waitForSelector('#simple-more-menu', {state:'hidden'});
await page.locator(`[data-simple-day="${noGoOffset}"]`).click();
await page.waitForSelector('.simple-hero[data-verdict-state="NO_GO"]');
const noGoQuality = await page.locator('.simple-confidence').textContent();
if (/\d+\s*%/.test(noGoQuality || '')) throw new Error(`NO-GO quality must not be a percentage: ${noGoQuality}`);
if (!/Qualité des prévisions.*Non évaluée/is.test(noGoQuality || '')) throw new Error(`unexpected NO-GO forecast quality: ${noGoQuality}`);
if (errors.length) throw new Error(errors.join('; '));
await page.screenshot({path:OUT, fullPage:true});
await browser.close();
console.log(`PASS mobile-v2 — ${OUT}`);
