import {chromium} from 'playwright';
import fs from 'node:fs/promises';
import path from 'node:path';

const output = path.resolve('visual-artifacts');
const screenshots = path.join(output, 'screenshots');
await fs.mkdir(screenshots, {recursive: true});

const now = new Date();
const generated = new Date(now.getTime() - 20 * 60_000).toISOString();
const start = new Date(now.getTime() + 60 * 60_000).toISOString();
const end = new Date(now.getTime() + 6 * 60 * 60_000).toISOString();
const sites = {
  version: 2, tz: 'Africa/Tunis', home: 'gammarth-port',
  sites: [
    {name: 'Port de Gammarth', slug: 'gammarth-port', path: 'gammarth-port.json', lat: 36.921, lon: 10.31, map_lat: 36.921, map_lon: 10.31, route_kind: 'standard', route_points: [], onshore_sectors: [[30,150]], transit_speed_kts: {min: 18, max: 24}},
    {name: 'Sidi Bou Saïd', slug: 'sidi-bou-said', path: 'sidi-bou-said.json', lat: 36.865, lon: 10.351, map_lat: 36.865, map_lon: 10.351, route_kind: 'standard', route_points: [], onshore_sectors: [[30,150]], transit_speed_kts: {min: 18, max: 24}},
  ],
};
const payloads = {
  'status.json': {generated_at: generated, cadence_minutes: 60, files: sites.sites.map((site) => ({path: site.path, modified: generated, fresh: true}))},
  'windows.json': {version: 5, generated_at: generated, windows: [{dest_slug: 'sidi-bou-said.json', dest_name: 'Sidi Bou Saïd', required_hours: 4, windows: [{start, end, category: 'family', confidence: 'High', family_tier: 'standard'}]}]},
  'rules.normalized.json': {window_hours: {min: 4, max: 6}, family: {window_hours: {min: 4, max: 6}, hours_local: {start: 8, end: 21}}},
  'sites.normalized.json': sites,
  'recommendations.json': {recommendations: [], navigation_only: []},
  'port-knowledge.json': {ports: []},
};

const errors = [];
const browser = await chromium.launch({headless: true});
const context = await browser.newContext({viewport: {width: 390, height: 844}, isMobile: true, hasTouch: true, timezoneId: 'Africa/Tunis'});
const page = await context.newPage();
page.on('pageerror', (error) => errors.push(`pageerror: ${error.message}`));
page.on('console', (message) => { if (message.type() === 'error') errors.push(`console: ${message.text()}`); });
await page.addInitScript(() => {
  localStorage.setItem('lang', 'fr');
  localStorage.setItem('theme', 'nautical');
  localStorage.setItem('fable_board_mode', 'family');
  localStorage.setItem('fable_family_tab', 'today');
});
await page.route('**/*.json', async (route) => {
  const file = new URL(route.request().url()).pathname.split('/').pop();
  const payload = payloads[file] || {meta: {generated_at: generated, debug: {}}, hourly: {time: [generated], wind_speed_10m: [10], wind_gusts_10m: [15], wind_direction_10m: [310]}};
  await route.fulfill({status: 200, contentType: 'application/json', body: JSON.stringify(payload)});
});
await page.route(/https:\/\/[a-c]\.tile\.openstreetmap\.org\/.*/, (route) => route.fulfill({status: 200, contentType: 'image/svg+xml', body: '<svg xmlns="http://www.w3.org/2000/svg" width="256" height="256"><rect width="256" height="256" fill="#dceef6"/></svg>'}));

await page.goto('http://127.0.0.1:4173/', {waitUntil: 'commit', timeout: 15000});
await page.waitForTimeout(5000);
const debug = await page.evaluate(() => ({
  readyState: document.readyState,
  title: document.title,
  bodyClass: document.body?.className || '',
  heroExists: Boolean(document.getElementById('family-verdict-hero')),
  heroState: document.getElementById('family-verdict-hero')?.dataset.state || '',
  heroDisplay: document.getElementById('family-verdict-hero') ? getComputedStyle(document.getElementById('family-verdict-hero')).display : '',
  familyNavExists: Boolean(document.getElementById('family-board-nav')),
  scripts: Array.from(document.scripts).map((node) => node.src || '[inline]'),
  text: document.body?.innerText?.slice(0, 3000) || '',
}));
await page.screenshot({path: path.join(screenshots, 'smoke-mobile.png'), fullPage: false});
await fs.writeFile(path.join(output, 'smoke.json'), JSON.stringify({debug, errors}, null, 2));
await fs.writeFile(path.join(output, 'smoke.html'), await page.content());
console.log(JSON.stringify({debug, errors}, null, 2));
await browser.close();
