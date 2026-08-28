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
const now = new Date();
const inOneHour = new Date(now.getTime() + 60 * 60_000);
// Garder les fenêtres off-hours et en cours sur le même jour tunisien, même
// quand la recette démarre dans la dernière heure avant minuit.
const offStart = dateKey(inOneHour) === dateKey(now) ? inOneHour : now;
const offEnd = new Date(offStart.getTime() + 5 * 60 * 60_000);
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
  start:new Date(Math.max(
    new Date(`${day(0)}T00:00:00+01:00`).getTime(),
    Date.now()-30*60_000,
  )).toISOString(), end:new Date(Date.now()+150*60_000).toISOString(),
  category:'family', family_tier:'standard', confidence:'Medium', confidence_score:70,
};
const forecastTimes = [offStart.toISOString(),new Date(offStart.getTime()+2*60*60_000).toISOString(),offEnd.toISOString(),familyStart.toISOString(),new Date(familyStart.getTime()+3*60*60_000).toISOString(),familyEnd.toISOString()];
const hourlyStates = ['family','prudent','no_go','family','watch','no_go'];
const hourlyAssessment = forecastTimes.map((time,index) => ({
  time, scope:'single_hour_conditions', phase:'transit', condition_state:hourlyStates[index],
  is_window_decision:false, hard_veto:hourlyStates[index] === 'no_go', operating_light:index > 0 && index < 5,
  confidence:index === 2 ? 'Medium' : 'High',
  reasons:hourlyStates[index] === 'no_go' ? [{code:'rafales>=30',severity:'hard_veto',reason_fr:'rafales 32 km/h ≥ 30',reason_en:'gusts 32 km/h ≥ 30'}] : [],
  margins:[], metrics:{
    wind:{display_source:'icon_seamless',display_speed_kmh:[11,15,20,9,12,16][index],display_gust_kmh:[18,22,32,15,19,31][index],display_gust_delta_kmh:[7,7,12,6,7,15][index],display_direction_deg:310,display_onshore:false},
    wave:{display_source:'meteofrance_wave',display_hs_m:[.25,.35,.45,.2,.3,.4][index],display_tp_s:5},
  },
}));
const payloads = {
  'status.json': {generated_at:generated, cadence_minutes:60},
  'windows.json': {generated_at:generated, windows:[{
    dest_slug:'gammarth-port.json', dest_name:'Gammarth', required_hours:4, windows:[offHours, family],
    daily_diagnostics:{[day(noGoOffset)]:{status:'blocked',summary_fr:'Rafales et durée insuffisante',near_miss:{validated_hours:0},first_blocker:{time:`${day(noGoOffset)}T12:00:00+01:00`,reason_fr:'Rafales trop fortes',metrics:{wind_kmh:27,gust_kmh:34,hs_m:.6,visibility_km:8}}}},
    hourly_assessment:{path:'hourly/gammarth-port.json',count:hourlyAssessment.length,scope:'single_hour_conditions',phase:'transit',is_window_decision:false},
  },{
    dest_slug:'sidi-bou-said.json', dest_name:'Sidi Bou Saïd', required_hours:3, windows:[lateFamily],
  }]},
  'rules.normalized.json': {window_hours:{min:4}, wind:{family_max_kmh:22}, sea:{family_max_hs_m:.5}},
  'recommendations.json': {generated_at:generated, recommendations:[]},
  'sites.normalized.json': {home:'gammarth-port', sites:[
    {name:'Gammarth', slug:'gammarth-port', path:'gammarth-port.json', lat:36.92, lon:10.31, map_lat:36.92, map_lon:10.31, route_kind:'standard', route_points:[]},
    {name:'Sidi Bou Saïd', slug:'sidi-bou-said', path:'sidi-bou-said.json', lat:36.865, lon:10.351, map_lat:36.865, map_lon:10.351, route_kind:'standard', route_points:[]},
  ]},
  'catalog.json': {files:[{path:'gammarth-port.json'}]},
  'index.json': {generated_at:generated, files:['gammarth-port.json']},
  'port-knowledge.json': {ports:[]},
  'gammarth-port.json': {
    meta:{generated_at:generated, rules:{wind:{family_max_kmh:22}, sea:{family_max_hs_m:.5}}},
    hourly:{
      time:forecastTimes,
      wind_speed_10m:[11,15,20,9,12,16], hs:[.25,.35,.45,.2,.3,.4], precipitation:[0,0,0,0,0,0],
      temperature_2m:[25,27,29,24,26,28], apparent_temperature:[26,29,31,25,28,30],
      relative_humidity_2m:[65,60,55,70,64,58], cloud_cover:[10,20,35,5,15,25], uv_index:[1,4,7,0,3,6],
      wind_gusts_10m:[18,22,28,15,19,24], wind_direction_10m:[310,320,330,300,310,320],
      wave_height:[.25,.35,.45,.2,.3,.4], wave_period:[5,5,4.8,5.5,5.2,5], visibility:[10000,10000,10000,10000,10000,10000], weather_code:[0,0,1,0,0,1],
    },
  },
  'hourly/gammarth-port.json': {generated_at:generated,version:1,rules_digest:'visual-fixture',dest_slug:'gammarth-port.json',dest_name:'Gammarth',scope:'single_hour_conditions',phase:'transit',is_window_decision:false,hours:hourlyAssessment},
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
  const pathname = new URL(route.request().url()).pathname;
  const basename = pathname.split('/').pop();
  const file = pathname.includes('/hourly/') ? `hourly/${basename}` : basename;
  await route.fulfill({status:200, contentType:'application/json', body:JSON.stringify(payloads[file] || {})});
});
await page.goto(BASE, {waitUntil:'domcontentloaded'});
await page.waitForSelector('.simple-hero[data-verdict-state="OFF_HOURS"]', {state:'visible'}).catch(async (error) => {
  const state = await page.evaluate(() => ({
    body:document.body.className,
    text:document.body.innerText.slice(0,1000),
  }));
  throw new Error(`${error.message}; page errors=${errors.join(' | ')}; state=${JSON.stringify(state)}`);
});
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
  confidenceBelowVerdict:(() => {
    const verdict = document.querySelector('.simple-verdict')?.getBoundingClientRect();
    const confidence = document.querySelector('.simple-confidence')?.getBoundingClientRect();
    return Boolean(verdict && confidence && confidence.top >= verdict.bottom);
  })(),
  legacyFamilyHidden:['family-verdict-hero','family-planning-host'].every((id) => {
    const node = document.getElementById(id);
    return !node || getComputedStyle(node).display === 'none';
  }),
  hourlyChart:Boolean(document.querySelector('.hourly-chart-svg')),
  hourlyRibbon:Boolean(document.querySelector('.hourly-ribbon')),
  hourlyStates:document.querySelectorAll('.hourly-state').length,
  hourlySafety:document.querySelector('.hourly-safety-note')?.textContent?.trim(),
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
if (!initial.confidenceVisible || !initial.confidenceBelowVerdict) throw new Error(`forecast quality must remain readable below the verdict on mobile: ${JSON.stringify(initial)}`);
if (initial.qualityHasPercent) throw new Error(`forecast quality must not be shown as a percentage: ${initial.qualityText}`);
if (!/Qualité des prévisions.*Moyenne/i.test(initial.qualityText || '')) throw new Error(`unexpected forecast quality: ${initial.qualityText}`);
if (!initial.legacyFamilyHidden) throw new Error('legacy Family verdict or planning is visible in Simple View');
if (!initial.hourlyChart || !initial.hourlyRibbon || initial.hourlyStates !== hourlyAssessment.length) throw new Error(`engine-owned hourly chart is incomplete: ${JSON.stringify(initial)}`);
if (!/heure favorable.*sortie complète/i.test(initial.hourlySafety || '')) throw new Error(`hourly safety boundary is missing: ${initial.hourlySafety}`);
if (initial.overflow > 2) throw new Error(`horizontal overflow: ${initial.overflow}px`);

await page.locator('[data-hourly-mode="table"]').click();
await page.waitForSelector('.hourly-table');
const hourlyTableRows = await page.locator('.hourly-table tbody tr').count();
if (hourlyTableRows !== hourlyAssessment.length) throw new Error(`hourly table should have ${hourlyAssessment.length} rows, got ${hourlyTableRows}`);
await page.locator('[data-hourly-mode="curves"]').click();
await page.waitForSelector('.hourly-chart-svg');
await page.locator('.hourly-chart-svg').focus();
await page.keyboard.press('End');
const selectedHour = await page.locator('.hourly-selected time').getAttribute('datetime');
if (selectedHour !== hourlyAssessment.at(-1).time) throw new Error(`keyboard cursor did not reach last hour: ${selectedHour}`);

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
await page.locator('[data-simple-action="reasons"]').click();
await page.waitForSelector('#simple-reasons:not([hidden])');
const reasonChecks = await page.locator('#simple-reasons .decision-check').count();
if (reasonChecks < 3) throw new Error(`structured NO-GO checks are missing: ${reasonChecks}`);
await page.locator('.simple-bottom-nav [data-simple-action="map"]').click();
await page.waitForSelector('body.simple-map-open #map-card', {state:'visible'});
await page.waitForTimeout(180);
const mapView = await page.evaluate(() => {
  const map = document.getElementById('map');
  const back = document.getElementById('simpleMapBackBtn');
  return {
    simple:document.body.classList.contains('simple-board-mode'),
    family:document.body.classList.contains('family-board-mode'),
    destinations:document.querySelectorAll('.map-destination').length,
    mapHeight:map?.getBoundingClientRect().height || 0,
    backWidth:back?.getBoundingClientRect().width || 0,
    backHeight:back?.getBoundingClientRect().height || 0,
    overflow:document.documentElement.scrollWidth-document.documentElement.clientWidth,
  };
});
if (!mapView.simple || mapView.family) throw new Error(`map left Simple View: ${JSON.stringify(mapView)}`);
if (mapView.destinations < 1 || mapView.mapHeight < 300) throw new Error(`map is incomplete: ${JSON.stringify(mapView)}`);
if (mapView.backWidth < 44 || mapView.backHeight < 44) throw new Error(`map back target is too small: ${JSON.stringify(mapView)}`);
if (mapView.overflow > 2) throw new Error(`map horizontal overflow: ${mapView.overflow}px`);
await page.screenshot({path:OUT.replace(/\.png$/, '-map.png'), fullPage:false});
await page.locator('#simpleMapBackBtn').click();
await page.waitForSelector('#simple-view', {state:'visible'});
if (errors.length) throw new Error(errors.join('; '));
await page.screenshot({path:OUT, fullPage:true});
await browser.close();
console.log(`PASS mobile-v2 — ${OUT}`);
