/**
 * Frise 72 h : bande de verdict, vent et rafales en ruban, houle en aire.
 *
 * Deux tracés empilés partagent l'axe des heures ; il n'y a jamais deux
 * échelles verticales sur un même tracé.
 */

import { hourLabel, num } from './format.js';

const NS = 'http://www.w3.org/2000/svg';

const W = 334;
const H = 166;
const GX = 24;
const PW = W - GX - 4;
const WIND_BASE = 106;
const WIND_HEIGHT = 88;
const SWELL_BASE = 160;
const SWELL_HEIGHT = 44;
const STRIP_HEIGHT = 9;

const STATE_FILL = {
  go: 'var(--go)',
  prudent: 'url(#fbPrudence)',
  nogo: 'url(#fbNogo)',
};

function el(name, attrs = {}) {
  const node = document.createElementNS(NS, name);
  for (const [key, value] of Object.entries(attrs)) {
    if (value !== null && value !== undefined) node.setAttribute(key, String(value));
  }
  return node;
}

function defs() {
  const node = el('defs');
  const prudence = el('pattern', {
    id: 'fbPrudence', width: 5, height: 5, patternUnits: 'userSpaceOnUse', patternTransform: 'rotate(45)',
  });
  prudence.append(
    el('rect', { width: 5, height: 5, fill: 'var(--prudent-wash)' }),
    el('rect', { width: 2.2, height: 5, fill: 'var(--prudent)' }),
  );
  const nogo = el('pattern', {
    id: 'fbNogo', width: 4, height: 4, patternUnits: 'userSpaceOnUse', patternTransform: 'rotate(135)',
  });
  nogo.append(
    el('rect', { width: 4, height: 4, fill: 'var(--nogo-wash)' }),
    el('rect', { width: 2, height: 4, fill: 'var(--nogo)' }),
  );
  node.append(prudence, nogo);
  return node;
}

function niceWindMax(rows) {
  const peak = rows.reduce((acc, row) => Math.max(acc, row.gust ?? 0, row.wind ?? 0), 0);
  return Math.max(40, Math.ceil((peak + 4) / 10) * 10);
}

function niceSwellMax(rows, th) {
  const peak = rows.reduce((acc, row) => Math.max(acc, row.hs ?? 0), 0);
  return Math.max(th.hsFamilyMax * 1.6, Math.ceil((peak + 0.1) * 10) / 10);
}

/**
 * @param {HTMLElement} host
 * @param {{rows: Array, th: object, selected: number, onSelect: (i:number)=>void}} options
 */
export function renderTimeline(host, { rows, th, selected = 0, onSelect }) {
  host.textContent = '';
  if (!rows.length) return;

  const count = rows.length;
  const cellWidth = PW / count;
  const windMax = niceWindMax(rows);
  const swellMax = niceSwellMax(rows, th);
  const cx = (i) => GX + (i + 0.5) * cellWidth;
  const wy = (v) => WIND_BASE - Math.min(Math.max(v, 0), windMax) / windMax * WIND_HEIGHT;
  const sy = (v) => SWELL_BASE - Math.min(Math.max(v, 0), swellMax) / swellMax * SWELL_HEIGHT;

  const svg = el('svg', {
    viewBox: `0 0 ${W} ${H}`,
    class: 'fb-chart',
    role: 'img',
    'aria-label': `Vent, rafales et houle sur ${count} heures`,
  });
  svg.append(defs());

  // Bandes de nuit
  let nightStart = -1;
  rows.forEach((row, i) => {
    if (!row.daylight && nightStart < 0) nightStart = i;
    const closing = row.daylight || i === count - 1;
    if (closing && nightStart >= 0) {
      const end = row.daylight ? i : i + 1;
      svg.append(el('rect', {
        x: GX + nightStart * cellWidth,
        y: STRIP_HEIGHT + 9,
        width: (end - nightStart) * cellWidth,
        height: SWELL_BASE - STRIP_HEIGHT - 9,
        class: 'fb-night',
      }));
      nightStart = -1;
    }
  });

  // Bande de verdict
  rows.forEach((row, i) => {
    svg.append(el('rect', {
      x: GX + i * cellWidth,
      y: 0,
      width: cellWidth + 0.4,
      height: STRIP_HEIGHT,
      fill: STATE_FILL[row.state] ?? STATE_FILL.nogo,
    }));
  });

  // Grille et seuils du tracé vent
  svg.append(el('line', { x1: GX, y1: WIND_BASE, x2: W - 4, y2: WIND_BASE, class: 'fb-axis' }));
  svg.append(el('line', { x1: GX, y1: wy(windMax / 2), x2: W - 4, y2: wy(windMax / 2), class: 'fb-grid' }));
  svg.append(el('line', { x1: GX, y1: wy(windMax), x2: W - 4, y2: wy(windMax), class: 'fb-grid' }));
  svg.append(el('line', {
    x1: GX, y1: wy(th.windFamilyMax), x2: W - 4, y2: wy(th.windFamilyMax), class: 'fb-limit fb-limit--family',
  }));
  svg.append(el('line', {
    x1: GX, y1: wy(th.gustNoGoMin), x2: W - 4, y2: wy(th.gustNoGoMin), class: 'fb-limit fb-limit--veto',
  }));

  // Ruban vent -> rafales
  const windPath = rows.map((r, i) => `${i ? 'L' : 'M'}${cx(i).toFixed(1)} ${wy(r.wind).toFixed(1)}`).join('');
  const gustPath = rows.map((r, i) => `${i ? 'L' : 'M'}${cx(i).toFixed(1)} ${wy(r.gust).toFixed(1)}`).join('');
  const back = rows
    .map((r, i) => ({ i, r }))
    .reverse()
    .map(({ i, r }) => `L${cx(i).toFixed(1)} ${wy(r.wind).toFixed(1)}`)
    .join('');
  svg.append(el('path', { d: `${gustPath}${back}Z`, class: 'fb-ribbon' }));
  svg.append(el('path', { d: gustPath, class: 'fb-line fb-line--gust' }));
  svg.append(el('path', { d: windPath, class: 'fb-line fb-line--wind' }));

  const zeroLabel = el('text', { x: GX - 4, y: WIND_BASE + 3, class: 'fb-tick' });
  zeroLabel.textContent = '0';
  const halfLabel = el('text', { x: GX - 4, y: wy(windMax / 2) + 3, class: 'fb-tick' });
  halfLabel.textContent = String(windMax / 2);
  const fullLabel = el('text', { x: GX - 4, y: wy(windMax) + 4, class: 'fb-tick' });
  fullLabel.textContent = String(windMax);
  svg.append(zeroLabel, halfLabel, fullLabel);

  // Séparateurs de jour
  let previousDay = null;
  rows.forEach((row, i) => {
    if (row.day !== previousDay) {
      previousDay = row.day;
      if (i > 0) {
        svg.append(el('line', {
          x1: GX + i * cellWidth, y1: 0, x2: GX + i * cellWidth, y2: SWELL_BASE, class: 'fb-day-sep',
        }));
      }
    }
  });

  // Tracé houle
  const swellPath = rows.map((r, i) => `${i ? 'L' : 'M'}${cx(i).toFixed(1)} ${sy(r.hs).toFixed(1)}`).join('');
  svg.append(el('line', { x1: GX, y1: SWELL_BASE, x2: W - 4, y2: SWELL_BASE, class: 'fb-axis' }));
  svg.append(el('line', {
    x1: GX, y1: sy(th.hsFamilyMax), x2: W - 4, y2: sy(th.hsFamilyMax), class: 'fb-limit fb-limit--family',
  }));
  svg.append(el('path', {
    d: `${swellPath}L${cx(count - 1).toFixed(1)} ${SWELL_BASE}L${cx(0).toFixed(1)} ${SWELL_BASE}Z`,
    class: 'fb-swell-area',
  }));
  svg.append(el('path', { d: swellPath, class: 'fb-line fb-line--swell' }));
  const swellZero = el('text', { x: GX - 4, y: SWELL_BASE + 3, class: 'fb-tick' });
  swellZero.textContent = '0';
  const swellLimit = el('text', { x: GX - 4, y: sy(th.hsFamilyMax) + 3, class: 'fb-tick' });
  swellLimit.textContent = num(th.hsFamilyMax, 2);
  svg.append(swellZero, swellLimit);

  // Curseur
  const index = Math.max(0, Math.min(count - 1, selected));
  const row = rows[index];
  svg.append(el('line', { x1: cx(index), y1: 0, x2: cx(index), y2: SWELL_BASE, class: 'fb-cursor' }));
  svg.append(el('circle', { cx: cx(index), cy: wy(row.gust), r: 4, class: 'fb-dot fb-dot--gust' }));
  svg.append(el('circle', { cx: cx(index), cy: wy(row.wind), r: 4, class: 'fb-dot fb-dot--wind' }));
  svg.append(el('circle', { cx: cx(index), cy: sy(row.hs), r: 4, class: 'fb-dot fb-dot--swell' }));

  // Couche de saisie : le lecteur vise une heure, pas une courbe de 2 px.
  const surface = el('rect', { x: GX, y: 0, width: PW, height: H, class: 'fb-surface' });
  const pick = (event) => {
    const rect = surface.getBoundingClientRect();
    if (!rect.width) return;
    const ratio = (event.clientX - rect.left) / rect.width;
    const next = Math.max(0, Math.min(count - 1, Math.floor(ratio * count)));
    if (next !== index) onSelect?.(next);
  };
  surface.addEventListener('pointerdown', (event) => {
    surface.setPointerCapture?.(event.pointerId);
    pick(event);
  });
  surface.addEventListener('pointermove', (event) => {
    if (event.buttons) pick(event);
  });
  svg.append(surface);

  host.append(svg);

  // Étiquettes de jour en HTML : le texte SVG ne se remplace pas proprement.
  const axis = document.createElement('div');
  axis.className = 'fb-day-axis';
  axis.style.marginLeft = `${(GX / W) * 100}%`;
  axis.style.width = `${(PW / W) * 100}%`;
  let cursorDay = null;
  let span = null;
  rows.forEach((r) => {
    if (r.day !== cursorDay) {
      cursorDay = r.day;
      span = document.createElement('span');
      span.dataset.count = '0';
      span.textContent = r.dayLabel;
      axis.append(span);
    }
    span.dataset.count = String(Number(span.dataset.count) + 1);
  });
  for (const child of axis.children) {
    child.style.width = `${(Number(child.dataset.count) / count) * 100}%`;
  }
  host.append(axis);
}

/** Tableau equivalent : aucune valeur n'est accessible uniquement au survol. */
export function renderTable(host, rows) {
  host.textContent = '';
  const table = document.createElement('table');
  table.className = 'fb-table';
  table.innerHTML =
    '<thead><tr><th scope="col">Heure</th><th scope="col">Vent</th><th scope="col">Raf.</th>'
    + '<th scope="col">Hs</th><th scope="col">État</th></tr></thead>';
  const body = document.createElement('tbody');
  const labels = { go: 'GO', prudent: 'Prudence', nogo: 'No-go' };
  for (const row of rows) {
    const tr = document.createElement('tr');
    const cells = [
      `${row.dayLabel} ${hourLabel(row.time)}`,
      num(row.wind, 1),
      num(row.gust, 1),
      num(row.hs, 2),
      labels[row.state],
    ];
    cells.forEach((value, i) => {
      const td = document.createElement('td');
      td.textContent = value;
      if (i > 0 && i < 4) td.className = 'fb-num';
      if (i === 4) td.className = `fb-state fb-state--${row.state}`;
      tr.append(td);
    });
    body.append(tr);
  }
  table.append(body);
  host.append(table);
}
