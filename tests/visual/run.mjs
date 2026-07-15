import { chromium } from 'playwright';
import fs from 'node:fs/promises';
import path from 'node:path';

const BASE_URL = process.env.FABLE_VISUAL_URL || 'http://127.0.0.1:4173/';
const OUTPUT = path.resolve('visual-artifacts');
const SCREENSHOTS = path.join(OUTPUT, 'screenshots');
const FIXED_NOW = '2026-07-16T07:00:00.000Z'; // 08:00 Africa/Tunis
const FIXED_NOW_MS = new Date(FIXED_NOW).getTime();

const VIEWPORTS = [
  {id: 'mobile-390', width: 390, height: 844, isMobile: true, hasTouch: true},
  {id: 'tablet-768', width: 768, height: 1024, isMobile: true, hasTouch: true},
  {id: 'desktop-1440', width: 1440, height: 900, isMobile: false, hasTouch: false},
];
const STATES = ['fresh-windows', 'fresh-empty', 'stale', 'missing-windows', 'marine-error'];
const LOCALES = ['fr', 'en', 'ar'];
const THEMES = ['nautical', 'dark'];

const CAPTURE = new Set([
  'mobile-390__fresh-windows__fr__nautical',
  'mobile-390__stale__fr__nautical',
  'mobile-390__missing-windows__ar__nautical',
  'mobile-390__marine-error__en__dark',
  'tablet-768__fresh-windows__ar__nautical',
  'tablet-768__fresh-empty__fr__dark',
  'desktop-1440__fresh-windows__fr__nautical',
  'desktop-1440__stale__en__dark',
  'desktop-1440__marine-error__ar__nautical',
]);

const SITES = [
  ['Port de Gammarth', 'gammarth-port', 36.921, 10.310, 'standard', false],
  ['Sidi Bou Saïd', 'sidi-bou-said', 36.865, 10.351, 'standard', false],
  ['Ghar El Melh', 'ghar-el-melh', 37.177, 10.280, 'standard', false],
  ['Ras Fartass', 'ras-fartass', 36.877, 10.613, 'standard', false],
  ['El Haouaria', 'el-haouaria', 37.063, 11.008, 'standard', false],
  ['Kélibia', 'kelibia', 36.8473, 11.0934, 'long_trip_one_way', false],
  ['Pantelleria', 'pantelleria', 36.8333, 11.95, 'offshore_one_way_beta', true],
].map(([name, slug, lat, lon, route_kind, beta]) => ({
  name, slug, path: `${slug}.json`, lat, lon, map_lat: lat, map_lon: lon,
  transit_speed_kts: {min: 18, max: 24}, route_origin: slug === 'pantelleria' ? 'kelibia' : null,
  route_points: [], windows_enabled: true, beta, route_kind, route_note: null,
  country: slug === 'pantelleria' ? 'Italy' : 'Tunisia', shelter_bonus_radius_km: 0,
  onshore_sectors: [[30, 150]],
}));
const SITE_PATHS = new Set(SITES.map((site) => site.path));

function statusPayload(state) {
  const generated_at = state === 'stale' ? '2026-07-16T01:00:00.000Z' : '2026-07-16T06:30:00.000Z';
  return {
    generated_at,
    cadence_minutes: 60,
    files: SITES.map((site) => ({path: site.path, modified: generated_at, fresh: state !== 'stale'})),
  };
}

function rulesPayload() {
  return {
    window_hours: {min: 4, max: 6},
    family: {
      hours_local: {start: 8, end: 21},
      window_hours: {min: 4, max: 6},
      corridor: {validate_departure_and_return: true},
    },
    confidence: {high: {min_wave_sources: 2}},
  };
}

function diagnostic(summaryFr, summaryEn, reason = 'wind') {
  return {
    status: 'blocked', summary_fr: summaryFr, summary_en: summaryEn,
    first_blocker: {
      stage: 'transit_out', location: 'destination', phase: 'transit',
      time: '2026-07-16T09:00:00.000Z', reasons: [reason],
      reason_fr: summaryFr, reason_en: summaryEn,
      metrics: {wind_kmh: 27, gust_kmh: 34, hs_m: 0.6, tp_s: 4.2},
    },
  };
}

function windowsPayload(state) {
  const safeWindow = {
    start: '2026-07-16T07:30:00.000Z', end: '2026-07-16T13:30:00.000Z',
    category: 'family', confidence: 'High', confidence_score: 92, family_tier: 'standard',
    models: ['ICON', 'GFS'], spreads: {wind_kmh: 2.5, hs_m: 0.08},
    confidence_details: {min_wind_models_per_hour: 3, min_wave_sources_per_hour: 2, max_hs_spread_m: 0.08},
  };
  const prudentWindow = {
    start: '2026-07-16T09:00:00.000Z', end: '2026-07-16T14:00:00.000Z',
    category: 'family', confidence: 'Medium', confidence_score: 78, family_tier: 'prudent',
    models: ['ICON', 'GFS'], spreads: {wind_kmh: 4.2, hs_m: 0.12},
    confidence_details: {min_wind_models_per_hour: 2, min_wave_sources_per_hour: 2, max_hs_spread_m: 0.12},
  };
  const empty = state === 'fresh-empty';
  const marine = state === 'marine-error';
  return {
    version: 5,
    generated_at: '2026-07-16T06:30:00.000Z',
    windows: [
      {
        dest_slug: 'sidi-bou-said.json', dest_name: 'Sidi Bou Saïd', required_hours: 4,
        windows: empty ? [] : [safeWindow],
        diagnostics: empty ? diagnostic('Rafales trop fortes', 'Gusts too strong', 'gust') : null,
      },
      {
        dest_slug: 'ghar-el-melh.json', dest_name: 'Ghar El Melh', required_hours: 4,
        windows: empty || marine ? [] : [prudentWindow],
        diagnostics: marine
          ? diagnostic('Données de vagues manquantes — fenêtres non confirmées', 'Wave data unavailable — windows are not confirmed', 'marine_error')
          : empty ? diagnostic('Mer trop agitée', 'Sea too rough', 'sea') : null,
      },
      {
        dest_slug: 'ras-fartass.json', dest_name: 'Ras Fartass', required_hours: 4,
        windows: [], diagnostics: diagnostic('Vent de mer défavorable', 'Unfavourable onshore wind', 'onshore'),
      },
      {
        dest_slug: 'kelibia.json', dest_name: 'Kélibia', required_hours: 6,
        trip_mode: 'one_way_multi_day', route_kind: 'long_trip_one_way',
        windows: [{...safeWindow, start: '2026-07-17T06:00:00.000Z', end: '2026-07-17T13:00:00.000Z', trip_mode: 'one_way_multi_day'}],
      },
      {
        dest_slug: 'pantelleria.json', dest_name: 'Pantelleria', beta: true,
        trip_mode: 'one_way_multi_day', route_kind: 'offshore_one_way_beta',
        windows: [{...safeWindow, start: '2026-07-17T07:00:00.000Z', end: '2026-07-17T14:00:00.000Z', trip_mode: 'one_way_multi_day', beta: true}],
      },
    ],
  };
}

function spotPayload(file, state) {
  const marineError = state === 'marine-error' && file === 'ghar-el-melh.json';
  return {
    meta: {
      generated_at: '2026-07-16T06:30:00.000Z',
      sources: {
        ecmwf_open_meteo: {model_used: 'ECMWF IFS'},
        marine_open_meteo: {model_used: 'Météo-France Wave'},
      },
      debug: marineError ? {marine_error: 'marine model timeout'} : {},
    },
    hourly: {
      time: ['2026-07-16T07:00:00.000Z', '2026-07-16T10:00:00.000Z', '2026-07-16T13:00:00.000Z'],
      wind_speed_10m: [11, 14, 16], wind_gusts_10m: [17, 20, 23], wind_direction_10m: [310, 320, 330],
      wave_height: marineError ? [null, null, null] : [0.2, 0.25, 0.3],
      wave_period: marineError ? [null, null, null] : [5.2, 5.0, 4.8],
      visibility: [10000, 10000, 10000], weather_code: [0, 1, 1],
    },
  };
}

function payloadFor(file, state) {
  if (file === 'status.json') return statusPayload(state);
  if (file === 'windows.json') return windowsPayload(state);
  if (file === 'rules.normalized.json') return rulesPayload();
  if (file === 'sites.normalized.json') return {version: 2, tz: 'Africa/Tunis', home: 'gammarth-port', sites: SITES};
  if (file === 'recommendations.json') return {version: 3, generated_at: FIXED_NOW, recommendations: [], navigation_only: []};
  if (file === 'port-knowledge.json') return {version: 1, ports: []};
  if (file === 'catalog.json') return {files: SITES.map((site) => site.path)};
  if (file === 'index.json') return {generated_at: FIXED_NOW, files: SITES.map((site) => site.path)};
  if (SITE_PATHS.has(file)) return spotPayload(file, state);
  return {};
}

function tileSvg(theme) {
  const sea = theme === 'dark' ? '#132238' : '#dceef6';
  const line = theme === 'dark' ? '#28445f' : '#b7d7e6';
  return `<svg xmlns="http://www.w3.org/2000/svg" width="256" height="256"><rect width="256" height="256" fill="${sea}"/><path d="M0 55 Q64 35 128 55 T256 55 M0 130 Q64 110 128 130 T256 130 M0 205 Q64 185 128 205 T256 205" fill="none" stroke="${line}" stroke-width="2" opacity=".65"/></svg>`;
}

function parseColor(value) {
  const v = String(value || '').trim();
  if (v.startsWith('#')) {
    const hex = v.slice(1);
    const full = hex.length === 3 ? [...hex].map((x) => x + x).join('') : hex.slice(0, 6);
    return [0, 2, 4].map((i) => parseInt(full.slice(i, i + 2), 16));
  }
  const match = v.match(/rgba?\(([^)]+)\)/i);
  if (!match) return null;
  return match[1].split(',').slice(0, 3).map((item) => Number(item.trim()));
}

function contrastRatio(fg, bg) {
  const a = parseColor(fg); const b = parseColor(bg);
  if (!a || !b || [...a, ...b].some((x) => !Number.isFinite(x))) return 0;
  const luminance = (rgb) => {
    const values = rgb.map((x) => {
      const c = x / 255;
      return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
    });
    return 0.2126 * values[0] + 0.7152 * values[1] + 0.0722 * values[2];
  };
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (hi + 0.05) / (lo + 0.05);
}

async function configurePage(page, {state, locale, theme}) {
  await page.addInitScript(({locale, theme, fixedNow}) => {
    try {
      localStorage.setItem('lang', locale);
      localStorage.setItem('theme', theme);
      localStorage.setItem('fable_board_mode', 'family');
      localStorage.setItem('fable_family_tab', 'today');
      localStorage.removeItem('fable_selected_window');
    } catch {}
    const NativeDate = Date;
    class FixedDate extends NativeDate {
      constructor(...args) { super(...(args.length ? args : [fixedNow])); }
      static now() { return fixedNow; }
    }
    window.Date = FixedDate;
  }, {locale, theme, fixedNow: FIXED_NOW_MS});

  await page.route(/https:\/\/[a-c]\.tile\.openstreetmap\.org\/.*/, (route) => route.fulfill({
    status: 200, contentType: 'image/svg+xml', body: tileSvg(theme),
  }));
  await page.route('**/*.json', async (route) => {
    const file = new URL(route.request().url()).pathname.split('/').pop();
    if (file === 'windows.json' && state === 'missing-windows') {
      await route.fulfill({status: 404, contentType: 'application/json', body: '{"error":"missing"}'});
      return;
    }
    await route.fulfill({status: 200, contentType: 'application/json', body: JSON.stringify(payloadFor(file, state))});
  });
}

async function inspectScenario(page, scenario) {
  const errors = [];
  page.on('pageerror', (error) => errors.push(`pageerror: ${error.message}`));
  page.on('console', (message) => {
    if (message.type() === 'error') errors.push(`console: ${message.text()}`);
  });

  await configurePage(page, scenario);
  await page.goto(BASE_URL, {waitUntil: 'domcontentloaded'});
  await page.waitForSelector('#family-verdict-hero[data-state]', {state: 'visible', timeout: 15000});
  await page.waitForTimeout(700);

  const expectedState = {
    'fresh-windows': 'GO_TODAY', 'fresh-empty': 'NO_GO', stale: 'STALE',
    'missing-windows': 'NO_DATA', 'marine-error': 'GO_TODAY',
  }[scenario.state];
  const metrics = await page.evaluate(() => {
    const hero = document.getElementById('family-verdict-hero');
    const title = hero?.querySelector('h2');
    const badge = hero?.querySelector('.verdict-badge');
    const root = getComputedStyle(document.documentElement);
    return {
      state: hero?.dataset.state || '',
      lang: document.documentElement.lang,
      dir: document.documentElement.dir,
      theme: document.documentElement.dataset.theme,
      scrollWidth: document.documentElement.scrollWidth,
      clientWidth: document.documentElement.clientWidth,
      heroVisible: Boolean(hero && hero.getBoundingClientRect().height > 0),
      heroText: title?.textContent?.trim() || '',
      bodyMode: document.body.className,
      heroTextColor: title ? getComputedStyle(title).color : '',
      cardColor: root.getPropertyValue('--card').trim(),
      badgeTextColor: badge ? getComputedStyle(badge).color : '',
      badgeBgColor: badge ? getComputedStyle(badge).backgroundColor : '',
      marineText: document.body.textContent.includes('Données de vagues') || document.body.textContent.includes('Wave data') || document.body.textContent.includes('بيانات الأمواج'),
      mobileSettingsVisible: Boolean(document.getElementById('mobileSettingsBtn') && getComputedStyle(document.getElementById('mobileSettingsBtn')).display !== 'none'),
    };
  });
  metrics.heroContrast = contrastRatio(metrics.heroTextColor, metrics.cardColor);
  metrics.badgeContrast = contrastRatio(metrics.badgeTextColor, metrics.badgeBgColor);

  const failures = [];
  if (metrics.state !== expectedState) failures.push(`verdict ${metrics.state || 'missing'} != ${expectedState}`);
  if (!metrics.heroVisible) failures.push('hero not visible');
  if (metrics.scrollWidth > metrics.clientWidth + 2) failures.push(`horizontal overflow ${metrics.scrollWidth - metrics.clientWidth}px`);
  if (metrics.theme !== scenario.theme) failures.push(`theme ${metrics.theme} != ${scenario.theme}`);
  if (scenario.locale === 'ar') {
    if (metrics.lang !== 'ar' || metrics.dir !== 'rtl') failures.push(`Arabic locale/RTL missing (${metrics.lang}/${metrics.dir})`);
  } else if (metrics.lang !== scenario.locale || metrics.dir === 'rtl') {
    failures.push(`locale/direction mismatch (${metrics.lang}/${metrics.dir})`);
  }
  if (metrics.heroContrast < 4.5) failures.push(`hero contrast ${metrics.heroContrast.toFixed(2)} < 4.5`);
  if (metrics.badgeContrast < 4.5) failures.push(`badge contrast ${metrics.badgeContrast.toFixed(2)} < 4.5`);
  if (scenario.state === 'marine-error' && !metrics.marineText) failures.push('marine error message not visible');
  if (scenario.viewport.id === 'mobile-390' && !metrics.mobileSettingsVisible) failures.push('mobile settings button not visible');
  failures.push(...errors);

  const key = `${scenario.viewport.id}__${scenario.state}__${scenario.locale}__${scenario.theme}`;
  const screenshots = [];
  if (CAPTURE.has(key)) {
    const file = `${key}.png`;
    await page.screenshot({path: path.join(SCREENSHOTS, file), fullPage: true});
    screenshots.push(file);
  }

  if (key === 'mobile-390__fresh-windows__fr__nautical') {
    await page.locator('#mobileSettingsBtn').click();
    await page.waitForTimeout(150);
    const file = `${key}__settings.png`;
    await page.screenshot({path: path.join(SCREENSHOTS, file), fullPage: true});
    screenshots.push(file);
  }
  if (key === 'desktop-1440__fresh-windows__fr__nautical') {
    await page.locator('[data-family-tab="map"]').click();
    await page.waitForTimeout(300);
    let file = `${key}__map.png`;
    await page.screenshot({path: path.join(SCREENSHOTS, file), fullPage: true});
    screenshots.push(file);
    await page.locator('#viewToggleBtn').click();
    await page.waitForTimeout(250);
    file = `${key}__expert.png`;
    await page.screenshot({path: path.join(SCREENSHOTS, file), fullPage: true});
    screenshots.push(file);
    const expert = await page.evaluate(() => ({
      mode: document.body.className,
      radarVisible: Boolean(document.querySelector('.card.radar')?.getBoundingClientRect().height),
      rawVisible: Boolean(document.querySelector('#raw-links-list')?.closest('details')?.getBoundingClientRect().height),
    }));
    if (!expert.mode.includes('expert-board-mode')) failures.push('expert mode did not activate');
    if (!expert.radarVisible) failures.push('radar not visible in expert mode');
  }

  return {key, viewport: scenario.viewport, state: scenario.state, locale: scenario.locale, theme: scenario.theme, metrics, screenshots, failures, passed: failures.length === 0};
}

await fs.rm(OUTPUT, {recursive: true, force: true});
await fs.mkdir(SCREENSHOTS, {recursive: true});
const browser = await chromium.launch({headless: true});
const results = [];
try {
  for (const viewport of VIEWPORTS) {
    const context = await browser.newContext({
      viewport: {width: viewport.width, height: viewport.height},
      isMobile: viewport.isMobile,
      hasTouch: viewport.hasTouch,
      timezoneId: 'Africa/Tunis',
      deviceScaleFactor: 1,
    });
    for (const state of STATES) {
      for (const locale of LOCALES) {
        for (const theme of THEMES) {
          const page = await context.newPage();
          const result = await inspectScenario(page, {viewport, state, locale, theme});
          results.push(result);
          console.log(`${result.passed ? 'PASS' : 'FAIL'} ${result.key}${result.failures.length ? ` — ${result.failures.join(' | ')}` : ''}`);
          await page.close();
        }
      }
    }
    await context.close();
  }
} finally {
  await browser.close();
}

const failed = results.filter((item) => !item.passed);
const report = {
  generated_at: new Date().toISOString(), fixed_now: FIXED_NOW, base_url: BASE_URL,
  matrix: {viewports: VIEWPORTS, states: STATES, locales: LOCALES, themes: THEMES},
  totals: {scenarios: results.length, passed: results.length - failed.length, failed: failed.length},
  screenshots: results.flatMap((item) => item.screenshots), results,
};
await fs.writeFile(path.join(OUTPUT, 'report.json'), JSON.stringify(report, null, 2));
await fs.writeFile(path.join(OUTPUT, 'SUMMARY.md'), [
  '# FABLE visual recipe', '',
  `- Scenarios: ${report.totals.scenarios}`,
  `- Passed: ${report.totals.passed}`,
  `- Failed: ${report.totals.failed}`,
  `- Screenshots: ${report.screenshots.length}`,
  '',
  ...(failed.length ? ['## Failures', '', ...failed.map((item) => `- **${item.key}** — ${item.failures.join('; ')}`)] : ['All automated visual checks passed.']),
  '',
].join('\n'));

if (failed.length) process.exitCode = 1;
