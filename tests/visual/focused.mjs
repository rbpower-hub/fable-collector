import {chromium} from 'playwright';
import fs from 'node:fs/promises';
import path from 'node:path';

const BASE = process.env.FABLE_VISUAL_URL || 'http://127.0.0.1:4173/';
const OUT = path.resolve('visual-artifacts');
const SHOTS = path.join(OUT, 'screenshots');

const devices = {
  mobile: {id: 'mobile-390', width: 390, height: 844, isMobile: true, hasTouch: true},
  tablet: {id: 'tablet-768', width: 768, height: 1024, isMobile: true, hasTouch: true},
  desktop: {id: 'desktop-1440', width: 1440, height: 900, isMobile: false, hasTouch: false},
};

const scenarios = [
  {device: 'mobile', state: 'fresh-windows', locale: 'fr', theme: 'nautical'},
  {device: 'mobile', state: 'missing-windows', locale: 'ar', theme: 'nautical'},
  {device: 'tablet', state: 'stale', locale: 'en', theme: 'dark'},
  {device: 'tablet', state: 'fresh-empty', locale: 'fr', theme: 'dark'},
  {device: 'desktop', state: 'marine-error', locale: 'ar', theme: 'nautical'},
  {device: 'desktop', state: 'fresh-windows', locale: 'fr', theme: 'dark'},
];

const tunisDateKey = (value) => {
  const date = value instanceof Date ? value : new Date(value);
  const parts = new Intl.DateTimeFormat('en-CA', {
    timeZone: 'Africa/Tunis', year: 'numeric', month: '2-digit', day: '2-digit',
  }).formatToParts(date).reduce((result, part) => {
    if (part.type !== 'literal') result[part.type] = part.value;
    return result;
  }, {});
  return `${parts.year}-${parts.month}-${parts.day}`;
};

const expectedState = (state) => {
  if (state === 'missing-windows') return 'NO_DATA';
  if (state === 'stale') return 'STALE';
  if (state === 'fresh-empty') return 'NO_GO';
  if (state === 'fresh-windows' || state === 'marine-error') {
    const today = tunisDateKey(new Date());
    const windowStart = tunisDateKey(new Date(Date.now() + 60 * 60_000));
    return windowStart === today ? 'GO_TODAY' : 'GO_SOON';
  }
  return 'NO_GO';
};

const sites = {
  version: 2, tz: 'Africa/Tunis', home: 'gammarth-port',
  sites: [
    {name: 'Port de Gammarth', slug: 'gammarth-port', path: 'gammarth-port.json', lat: 36.921, lon: 10.31, map_lat: 36.921, map_lon: 10.31, route_kind: 'standard', route_points: [], onshore_sectors: [[30, 150]], transit_speed_kts: {min: 18, max: 24}},
    {name: 'Sidi Bou Saïd', slug: 'sidi-bou-said', path: 'sidi-bou-said.json', lat: 36.865, lon: 10.351, map_lat: 36.865, map_lon: 10.351, route_kind: 'standard', route_points: [], onshore_sectors: [[30, 150]], transit_speed_kts: {min: 18, max: 24}},
    {name: 'Ghar El Melh', slug: 'ghar-el-melh', path: 'ghar-el-melh.json', lat: 37.177, lon: 10.28, map_lat: 37.177, map_lon: 10.28, route_kind: 'standard', route_points: [], onshore_sectors: [[10, 130]], transit_speed_kts: {min: 18, max: 24}},
    {name: 'Kélibia', slug: 'kelibia', path: 'kelibia.json', lat: 36.8473, lon: 11.0934, map_lat: 36.8473, map_lon: 11.0934, route_kind: 'long_trip_one_way', route_points: [], onshore_sectors: [[330, 360], [0, 70]], transit_speed_kts: {min: 18, max: 24}},
    {name: 'Pantelleria', slug: 'pantelleria', path: 'pantelleria.json', lat: 36.8333, lon: 11.95, map_lat: 36.8333, map_lon: 11.95, route_kind: 'offshore_one_way_beta', route_origin: 'kelibia', beta: true, route_points: [], onshore_sectors: [[20, 160]], transit_speed_kts: {min: 18, max: 24}},
  ],
};
const sitePaths = new Set(sites.sites.map((site) => site.path));
const iso = (minutes) => new Date(Date.now() + minutes * 60_000).toISOString();

function blocker(fr, en, reason) {
  return {
    status: 'blocked', summary_fr: fr, summary_en: en,
    first_blocker: {stage: 'transit_out', phase: 'transit', location: 'destination', time: iso(120), reasons: [reason], reason_fr: fr, reason_en: en, metrics: {wind_kmh: 27, gust_kmh: 34, hs_m: 0.6, tp_s: 4.2}},
  };
}

function payloadsFor(state) {
  const generated = state === 'stale' ? iso(-360) : iso(-20);
  const windowItem = {
    start: iso(60), end: iso(360), category: 'family', confidence: 'High', confidence_score: 92,
    family_tier: 'standard', models: ['ICON', 'GFS'], spreads: {wind_kmh: 2.5, hs_m: 0.08},
    confidence_details: {min_wind_models_per_hour: 3, min_wave_sources_per_hour: 2, max_hs_spread_m: 0.08},
  };
  const empty = state === 'fresh-empty';
  const marine = state === 'marine-error';
  return {
    'status.json': {generated_at: generated, cadence_minutes: 60, files: sites.sites.map((site) => ({path: site.path, modified: generated, fresh: state !== 'stale'}))},
    'windows.json': {
      version: 5, generated_at: generated,
      windows: [
        {dest_slug: 'sidi-bou-said.json', dest_name: 'Sidi Bou Saïd', required_hours: 4, windows: empty ? [] : [windowItem], diagnostics: empty ? blocker('Rafales trop fortes', 'Gusts too strong', 'gust') : null},
        {dest_slug: 'ghar-el-melh.json', dest_name: 'Ghar El Melh', required_hours: 4, windows: [], diagnostics: marine ? blocker('Données de vagues manquantes — fenêtres non confirmées', 'Wave data unavailable — windows are not confirmed', 'marine_error') : blocker('Mer trop agitée', 'Sea too rough', 'sea')},
        {dest_slug: 'kelibia.json', dest_name: 'Kélibia', trip_mode: 'one_way_multi_day', route_kind: 'long_trip_one_way', windows: [{...windowItem, start: iso(1440), end: iso(1860), trip_mode: 'one_way_multi_day'}]},
        {dest_slug: 'pantelleria.json', dest_name: 'Pantelleria', beta: true, trip_mode: 'one_way_multi_day', route_kind: 'offshore_one_way_beta', windows: [{...windowItem, start: iso(1500), end: iso(1920), trip_mode: 'one_way_multi_day', beta: true}]},
      ],
    },
    'rules.normalized.json': {window_hours: {min: 4, max: 6}, family: {window_hours: {min: 4, max: 6}, hours_local: {start: 8, end: 21}, corridor: {validate_departure_and_return: true}}, confidence: {high: {min_wave_sources: 2}}},
    'sites.normalized.json': sites,
    'recommendations.json': {version: 3, generated_at: generated, recommendations: [], navigation_only: []},
    'port-knowledge.json': {version: 1, ports: []},
    'catalog.json': {files: sites.sites.map((site) => site.path)},
    'index.json': {generated_at: generated, files: sites.sites.map((site) => site.path)},
  };
}

function spot(file, state) {
  const marine = state === 'marine-error' && file === 'ghar-el-melh.json';
  return {
    meta: {generated_at: iso(-20), sources: {ecmwf_open_meteo: {model_used: 'ECMWF IFS'}, marine_open_meteo: {model_used: 'Météo-France Wave'}}, debug: marine ? {marine_error: 'marine model timeout'} : {}},
    hourly: {time: [iso(0), iso(180), iso(360)], wind_speed_10m: [10, 13, 15], wind_gusts_10m: [15, 19, 22], wind_direction_10m: [310, 320, 330], wave_height: marine ? [null, null, null] : [0.2, 0.25, 0.3], wave_period: marine ? [null, null, null] : [5.2, 5.0, 4.8], visibility: [10000, 10000, 10000], weather_code: [0, 1, 1]},
  };
}

function rgb(value) {
  const text = String(value || '').trim();
  if (text.startsWith('#')) {
    let hex = text.slice(1);
    if (hex.length === 3) hex = [...hex].map((item) => item + item).join('');
    return [0, 2, 4].map((index) => parseInt(hex.slice(index, index + 2), 16));
  }
  const match = text.match(/rgba?\(([^)]+)\)/i);
  if (!match) return null;
  const values = match[1].split(/[, ]+/).filter(Boolean).slice(0, 3).map(Number);
  return values.length === 3 && values.every(Number.isFinite) ? values : null;
}

function contrast(foreground, background) {
  const fg = rgb(foreground); const bg = rgb(background);
  if (!fg || !bg) return 0;
  const lum = (values) => {
    const linear = values.map((value) => {
      const x = value / 255;
      return x <= 0.03928 ? x / 12.92 : ((x + 0.055) / 1.055) ** 2.4;
    });
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2];
  };
  const values = [lum(fg), lum(bg)].sort((a, b) => b - a);
  return (values[0] + 0.05) / (values[1] + 0.05);
}

async function execute(browser, scenario) {
  const device = devices[scenario.device];
  const key = `${device.id}__${scenario.state}__${scenario.locale}__${scenario.theme}`;
  const context = await browser.newContext({viewport: {width: device.width, height: device.height}, isMobile: device.isMobile, hasTouch: device.hasTouch, timezoneId: 'Africa/Tunis'});
  const page = await context.newPage();
  page.setDefaultTimeout(8000);
  const errors = [];
  page.on('pageerror', (error) => errors.push(`pageerror: ${error.message}`));
  page.on('console', (message) => { if (message.type() === 'error') errors.push(`console: ${message.text()}`); });
  await page.addInitScript(({locale, theme}) => {
    localStorage.setItem('lang', locale);
    localStorage.setItem('theme', theme);
    localStorage.setItem('fable_board_mode', 'family');
    localStorage.setItem('fable_family_tab', 'today');
  }, {locale: scenario.locale, theme: scenario.theme});

  const payloads = payloadsFor(scenario.state);
  await page.route('**/*.json', async (route) => {
    const file = new URL(route.request().url()).pathname.split('/').pop();
    if (file === 'windows.json' && scenario.state === 'missing-windows') {
      await route.fulfill({status: 404, contentType: 'application/json', body: '{"error":"missing"}'});
      return;
    }
    await route.fulfill({status: 200, contentType: 'application/json', body: JSON.stringify(payloads[file] ?? (sitePaths.has(file) ? spot(file, scenario.state) : {}))});
  });
  await page.route(/https:\/\/[a-c]\.tile\.openstreetmap\.org\/.*/, (route) => route.fulfill({status: 200, contentType: 'image/svg+xml', body: '<svg xmlns="http://www.w3.org/2000/svg" width="256" height="256"><rect width="256" height="256" fill="#dceef6"/><path d="M0 90 Q64 60 128 90 T256 90" fill="none" stroke="#9fc6d8" stroke-width="2"/></svg>'}));

  const failures = [];
  let values = null;
  try {
    await page.goto(BASE, {waitUntil: 'commit', timeout: 10000});
    await page.waitForSelector('#family-verdict-hero[data-state]', {state: 'visible'});
    await page.waitForTimeout(700);
    values = await page.evaluate(() => {
      const root = getComputedStyle(document.documentElement);
      const hero = document.getElementById('family-verdict-hero');
      const title = hero?.querySelector('h2');
      const badge = hero?.querySelector('.verdict-badge');
      return {
        state: hero?.dataset.state || '',
        title: title?.textContent?.trim() || '',
        lang: document.documentElement.lang,
        dir: document.documentElement.dir,
        theme: document.documentElement.dataset.theme,
        scrollWidth: document.documentElement.scrollWidth,
        clientWidth: document.documentElement.clientWidth,
        titleColor: title ? getComputedStyle(title).color : '',
        cardColor: root.getPropertyValue('--card').trim(),
        badgeColor: badge ? getComputedStyle(badge).color : '',
        badgeBackground: badge ? getComputedStyle(badge).backgroundColor : '',
        mobileSettings: Boolean(document.getElementById('mobileSettingsBtn') && getComputedStyle(document.getElementById('mobileSettingsBtn')).display !== 'none'),
        marineMessage: /Données de vagues|Wave data|بيانات الأمواج/.test(document.body.innerText),
      };
    });
    values.titleContrast = contrast(values.titleColor, values.cardColor);
    values.badgeContrast = contrast(values.badgeColor, values.badgeBackground);

    const expected = expectedState(scenario.state);
    if (values.state !== expected) failures.push(`verdict ${values.state} != ${expected}`);
    if (values.scrollWidth > values.clientWidth + 2) failures.push(`horizontal overflow ${values.scrollWidth - values.clientWidth}px`);
    if (values.theme !== scenario.theme) failures.push(`theme ${values.theme} != ${scenario.theme}`);
    if (scenario.locale === 'ar') {
      if (values.lang !== 'ar' || values.dir !== 'rtl') failures.push(`Arabic RTL missing (${values.lang}/${values.dir})`);
    } else if (values.lang !== scenario.locale || values.dir === 'rtl') failures.push(`locale mismatch (${values.lang}/${values.dir})`);
    if (values.titleContrast < 4.5) failures.push(`title contrast ${values.titleContrast.toFixed(2)} < 4.5`);
    if (values.badgeContrast < 4.5) failures.push(`badge contrast ${values.badgeContrast.toFixed(2)} < 4.5`);
    if (scenario.device === 'mobile' && !values.mobileSettings) failures.push('mobile settings button missing');
    if (scenario.state === 'marine-error' && !values.marineMessage) failures.push('marine data error not visible');
    if (errors.length) failures.push(...errors);
    await page.screenshot({path: path.join(SHOTS, `${key}.png`), fullPage: false});
  } catch (error) {
    failures.push(error.message);
  }
  await context.close();
  return {key, scenario, device, values, failures, passed: failures.length === 0};
}

await fs.mkdir(SHOTS, {recursive: true});
const browser = await chromium.launch({headless: true, args: ['--no-sandbox']});
const results = [];
for (const scenario of scenarios) results.push(await execute(browser, scenario));
await browser.close();

const failed = results.filter((result) => !result.passed);
const report = {
  generated_at: new Date().toISOString(), strategy: 'six representative visual scenarios',
  totals: {scenarios: results.length, passed: results.length - failed.length, failed: failed.length},
  scenarios, results,
};
await fs.writeFile(path.join(OUT, 'report.json'), `${JSON.stringify(report, null, 2)}\n`);
await fs.writeFile(path.join(OUT, 'SUMMARY.md'), `# FABLE visual recipe\n\n- Scenarios: ${results.length}\n- Passed: ${results.length - failed.length}\n- Failed: ${failed.length}\n${failed.length ? `\n## Failures\n\n${failed.map((item) => `- **${item.key}** — ${item.failures.join('; ')}`).join('\n')}\n` : ''}`);
results.forEach((result) => console.log(`${result.passed ? 'PASS' : 'FAIL'} ${result.key}${result.failures.length ? ` — ${result.failures.join('; ')}` : ''}`));
if (failed.length) process.exitCode = 1;
