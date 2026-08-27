/** Mobile_view — point d'entree. Trois ecrans, un seul jeu de donnees. */

import { loadCatalog, loadHourlyAssessment, loadSpot } from './data.js';
import { parseThresholds } from './thresholds.js';
import { classifySeries } from './hour-verdict.js';
import {
  applyEngineAssessment, assessmentsByTime, currentEngineWindow,
} from './engine-assessment.js';
import { renderDecision } from './decision.js';
import { renderSpot } from './spot.js';
import { renderCarte, destroyMap } from './carte.js';
import { dayKey, dayShort } from './format.js';
import { h, icon } from './ui.js';

const state = {
  catalog: null,
  th: null,
  spotSlug: null,
  rowsBySlug: new Map(),
  verdicts: new Map(),
  view: 'decision',
  dayKey: null,
  destSlug: null,
};

const app = document.getElementById('fb-app');
const viewHost = document.getElementById('fb-view');
const navHost = document.getElementById('fb-nav');

function buildRows(spot, config, th, assessmentPayload) {
  const hourly = spot?.hourly ?? {};
  const times = hourly.time ?? [];
  const classified = classifySeries(spot, config?.onshore_sectors ?? [], th);
  const assessments = assessmentsByTime(assessmentPayload);
  return times.map((time, index) => {
    const verdict = applyEngineAssessment(classified[index], assessments.get(String(time).slice(0, 16)));
    const display = verdict.display ?? {};
    return {
      index,
      time,
      day: dayKey(time),
      dayLabel: dayShort(time),
      wind: display.wind ?? Number(hourly.wind_speed_10m?.[index]),
      gust: display.gust ?? Number(hourly.wind_gusts_10m?.[index]),
      hs: display.hs ?? Number(hourly.hs?.[index] ?? hourly.wave_height?.[index]),
      tp: display.tp ?? Number(hourly.tp?.[index] ?? hourly.wave_period?.[index]),
      direction: display.direction ?? Number(hourly.wind_direction_10m?.[index]),
      temperature: Number(hourly.temperature_2m?.[index]),
      uv: Number(hourly.uv_index?.[index]),
      state: verdict.state,
      hard: verdict.hard,
      reasons: verdict.reasons,
      familyReasons: verdict.family,
      metrics: verdict.metrics,
      daylight: verdict.daylight,
      spreadSpeed: verdict.metrics.spreadSpeed,
      spreadHs: verdict.metrics.spreadHs,
    };
  });
}

async function rowsFor(slug) {
  if (state.rowsBySlug.has(slug)) return state.rowsBySlug.get(slug);
  const entry = state.catalog.spots.find((item) => item.slug === slug);
  if (!entry) return [];
  const [spot, assessment] = await Promise.all([
    loadSpot(entry.path),
    loadHourlyAssessment(entry.engine?.hourly_assessment),
  ]);
  // Les seuils viennent du schema plat republie par le collecteur, complete
  // par rules.normalized.json pour prudent / short_steep / adaptive_window.
  if (!state.th) state.th = parseThresholds(spot?.meta?.rules, state.catalog.rules);
  const rows = buildRows(spot, entry.config, state.th, assessment);
  state.rowsBySlug.set(slug, rows);
  return rows;
}

function navButton(id, label, iconName) {
  return h('button', {
    type: 'button',
    dataset: { view: id },
    'aria-current': state.view === id ? 'page' : 'false',
    onClick: () => navigate(id),
  }, [icon(iconName, { size: 20, stroke: 'currentColor' }), h('span', { text: label })]);
}

function paintNav() {
  navHost.textContent = '';
  navHost.append(
    navButton('decision', 'Décision', 'compass'),
    navButton('spot', 'Détail', 'chart'),
    navButton('carte', 'Carte', 'map'),
  );
}

function writeHash() {
  const parts = [state.view, state.spotSlug];
  if (state.view === 'spot' && state.dayKey) parts.push(state.dayKey);
  if (state.view === 'carte' && state.destSlug) parts.push(state.destSlug);
  const next = `#/${parts.filter(Boolean).join('/')}`;
  if (window.location.hash !== next) {
    window.history.replaceState(null, '', next);
  }
}

function readHash() {
  const [, view, slug, extra] = (window.location.hash || '').split('/');
  if (view) state.view = ['decision', 'spot', 'carte'].includes(view) ? view : 'decision';
  if (slug && state.catalog?.spots.some((item) => item.slug === slug)) state.spotSlug = slug;
  if (extra) {
    if (state.view === 'spot') state.dayKey = extra;
    if (state.view === 'carte') state.destSlug = extra;
  }
}

async function navigate(view, options = {}) {
  state.view = view;
  Object.assign(state, options);
  writeHash();
  paintNav();
  await paint();
}

async function paint() {
  app.dataset.busy = 'true';
  try {
    const rows = await rowsFor(state.spotSlug);
    const entry = state.catalog.spots.find((item) => item.slug === state.spotSlug);
    viewHost.textContent = '';
    if (!rows.length) {
      viewHost.append(h('div', { class: 'fb-error', text: 'Aucune donnée horaire pour ce spot.' }));
      return;
    }

    if (state.view === 'decision') {
      destroyMap();
      renderDecision(viewHost, {
        rows,
        th: state.th,
        spot: entry,
        generatedAt: state.catalog.generatedAt,
        engineWindow: currentEngineWindow(entry.engine),
        state,
      });
    } else if (state.view === 'spot') {
      destroyMap();
      renderSpot(viewHost, {
        rows,
        th: state.th,
        spot: entry,
        dayKey: state.dayKey ?? rows[0].day,
        rulesDigest: state.th?.digest ?? null,
        onBack: () => navigate('decision'),
        onDay: (key) => navigate('spot', { dayKey: key }),
      });
    } else {
      renderCarte(viewHost, {
        sites: state.catalog.spots.map((item) => item.config).filter(Boolean),
        homeSlug: state.catalog.homeSlug,
        verdicts: state.verdicts,
        windows: state.catalog.windows,
        destSlug: state.destSlug,
        onDest: (slug) => navigate('carte', { destSlug: slug }),
      });
    }
  } catch (error) {
    viewHost.textContent = '';
    viewHost.append(h('div', { class: 'fb-error', text: `Chargement impossible : ${error.message}` }));
  } finally {
    app.dataset.busy = 'false';
  }
}

async function computeVerdicts() {
  await Promise.all(state.catalog.spots.map(async (entry) => {
    const rows = await rowsFor(entry.slug);
    state.verdicts.set(entry.slug, rows[0]?.state ?? 'nogo');
  }));
}

function renderTopbar() {
  const home = state.catalog.spots.find((item) => item.slug === state.spotSlug);
  const bar = document.getElementById('fb-topbar');
  bar.textContent = '';

  const select = h('select', {
    class: 'fb-topbar__title fb-spot-select',
    style: 'background:transparent;border:0;color:inherit;font:inherit;padding:0',
    'aria-label': 'Choisir un spot',
    onChange: (event) => {
      state.spotSlug = event.target.value;
      state.dayKey = null;
      writeHash();
      paint();
      renderTopbar();
    },
  }, state.catalog.spots.map((item) => h('option', {
    value: item.slug,
    selected: item.slug === state.spotSlug,
    text: item.name,
  })));

  const config = home?.config;
  bar.append(
    h('div', { class: 'fb-topbar__meta' }, [
      h('div', { style: 'display:flex;align-items:center;gap:4px' }, [
        select,
        icon('chevronDown', { size: 16, stroke: 'var(--ink-3)', width: 2 }),
      ]),
      h('span', {
        class: 'fb-topbar__sub',
        text: config
          ? `${config.lat.toFixed(3)} N / ${config.lon.toFixed(3)} E · ${state.catalog.tz}`
          : state.catalog.tz,
      }),
    ]),
    h('span', { class: 'fb-freshness' }, [
      h('span', { class: 'fb-freshness__dot' }),
      h('span', { text: `v${state.catalog.collectorVersion ?? '—'}` }),
    ]),
  );
}

async function boot() {
  try {
    state.catalog = await loadCatalog();
    state.spotSlug = state.catalog.homeSlug ?? state.catalog.spots[0]?.slug ?? null;
    readHash();
    if (!state.spotSlug) throw new Error('aucun spot publié');
    renderTopbar();
    paintNav();
    await paint();
    await computeVerdicts();
    if (state.view === 'carte') await paint();
  } catch (error) {
    viewHost.textContent = '';
    viewHost.append(h('div', { class: 'fb-error', text: `Chargement impossible : ${error.message}` }));
  }
}

window.addEventListener('hashchange', () => {
  readHash();
  paintNav();
  paint();
});

boot();
