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
const offHours = {
  start:offStart.toISOString(), end:offEnd.toISOString(), category:'off_hours', confidence:'Medium', confidence_score:64,
};
const family = {
  start:familyStart.toISOString(), end:familyEnd.toISOString(), category:'family', family_tier:'standard', confidence:'High', confidence_score:88,
};
const payloads = {
  'status.json': {generated_at:generated, cadence_minutes:60},
  'windows.json': {generated_at:generated, windows:[{
    dest_slug:'gammarth-port.json', dest_name:'Gammarth', required_hours:4, windows:[offHours, family],
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
  tabs:document.querySelectorAll('.simple-day[role="tab"]').length,
  selectedTab:document.querySelector('.simple-day[aria-selected="true"]')?.dataset.simpleDay,
  selectorBeforeDecision:Boolean(document.querySelector('#simple-three-days')?.compareDocumentPosition(document.querySelector('#simple-decision')) & Node.DOCUMENT_POSITION_FOLLOWING),
  navVisible:getComputedStyle(document.querySelector('.simple-bottom-nav')).display !== 'none',
  overflow:document.documentElement.scrollWidth - document.documentElement.clientWidth,
}));
if (!/hors horaires/i.test(initial.title || '')) throw new Error(`unexpected title: ${initial.title}`);
if (initial.rows !== 1) throw new Error(`expected 1 selected-day row, got ${initial.rows}`);
if (initial.tabs !== 3) throw new Error(`expected 3 day tabs, got ${initial.tabs}`);
if (initial.selectedTab !== String(offOffset)) throw new Error(`unexpected initial selected tab: ${initial.selectedTab}`);
if (!initial.selectorBeforeDecision) throw new Error('three-day selector must precede the decision');
if (!initial.navVisible) throw new Error('bottom navigation is hidden');
if (initial.overflow > 2) throw new Error(`horizontal overflow: ${initial.overflow}px`);

await page.locator(`[data-simple-day="${familyOffset}"]`).click();
await page.waitForSelector('.simple-hero[data-verdict-state="GO_FAMILY"]');
await page.waitForSelector(`[data-simple-day="${familyOffset}"][aria-selected="true"]`);
const tomorrowRows = await page.locator('.simple-window-card').count();
if (tomorrowRows !== 1) throw new Error(`tomorrow should have one row, got ${tomorrowRows}`);
if (errors.length) throw new Error(errors.join('; '));
await page.screenshot({path:OUT, fullPage:true});
await browser.close();
console.log(`PASS mobile-v2 — ${OUT}`);
