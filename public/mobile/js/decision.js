/** Ecran Decision : verdict, frise 72 h, jours suivants. */

import { renderTimeline, renderTable } from './chart.js';
import { dailyBest, currentOrNextRun } from './runs.js';
import {
  dayShort, firstReasonText, hourLabel, num, relativeAge,
} from './format.js';
import {
  card, h, icon, metric, stateBadge, STATE_VAR,
} from './ui.js';

const RANGE_ALL = 'all';

function confidenceLevel(rows) {
  const spreads = rows.map((row) => row.spreadSpeed).filter(Number.isFinite);
  if (!spreads.length) return { level: 'low', label: 'faible', mean: null };
  const mean = spreads.reduce((a, b) => a + b, 0) / spreads.length;
  if (mean < 5) return { level: 'high', label: 'haute', mean };
  if (mean < 8) return { level: 'medium', label: 'moyenne', mean };
  return { level: 'low', label: 'faible', mean };
}

function verdictHero(state, ctx) {
  const { rows, th, freshness, confidence, engineWindow } = ctx;
  const run = currentOrNextRun(rows);
  let title;
  let detail;

  if (engineWindow) {
    title = `Fenêtre ${hourLabel(engineWindow.start)} → ${hourLabel(engineWindow.end)} · ${num(engineWindow.hours, 0)} h`;
    detail = engineWindow.note ?? 'Fenêtre validée par le moteur.';
  } else if (run) {
    const from = rows[run.start];
    // La borne haute est l'heure qui suit la derniere heure GO, comme le
    // moteur : 12:00 -> 15:00 designe trois heures pleines.
    const to = rows[run.end] ?? rows[run.end - 1];
    title = `Fenêtre ${hourLabel(from.time)} → ${hourLabel(to.time)} · ${run.hours} h`;
    const closer = rows[run.end];
    const short = run.hours < th.windowMinHours;
    detail = [
      closer ? `Se referme sur ${firstReasonText(closer.familyReasons, closer.metrics)}.` : 'Fin de l’horizon.',
      short ? `Le minimum famille est de ${th.windowMinHours} h.` : null,
    ].filter(Boolean).join(' ');
  } else {
    title = 'Aucune heure GO sur l’horizon';
    const worst = rows.find((row) => row.state === 'nogo') ?? rows[0];
    detail = worst ? `Premier blocage : ${firstReasonText(worst.reasons, worst.metrics)}` : '';
  }

  const head = h('div', { class: 'fb-verdict__head' }, [
    stateBadge(state),
    h('div', { style: 'flex:1 1 auto' }),
    h('div', { class: 'fb-confidence', dataset: { level: confidence.level } }, [
      h('span'), h('span'), h('span'),
    ]),
    h('span', { class: 'fb-card__note', text: `confiance ${confidence.label}` }),
  ]);

  const spreadLine = Number.isFinite(confidence.mean)
    ? h('div', { style: 'display:flex;align-items:center;gap:6px' }, [
      icon('clock', { size: 13, stroke: 'var(--ink-3)', width: 2 }),
      h('span', {
        class: 'fb-card__note',
        text: `Écart entre modèles de vent : ${num(confidence.mean, 0)} km/h en moyenne`,
      }),
    ])
    : null;

  return h('div', { class: 'fb-card' }, [
    head,
    h('div', { class: 'fb-verdict__title', text: title }),
    h('div', { class: 'fb-body', text: detail }),
    spreadLine ? h('div', { class: 'fb-rule' }) : null,
    spreadLine,
    freshness,
  ]);
}

function patternSwatch(fill) {
  const ns = 'http://www.w3.org/2000/svg';
  const svg = document.createElementNS(ns, 'svg');
  svg.setAttribute('width', '14');
  svg.setAttribute('height', '8');
  svg.setAttribute('viewBox', '0 0 14 8');
  svg.setAttribute('aria-hidden', 'true');
  const rect = document.createElementNS(ns, 'rect');
  rect.setAttribute('width', '14');
  rect.setAttribute('height', '8');
  rect.setAttribute('fill', fill);
  svg.append(rect);
  return h('span', { class: 'fb-key__swatch' }, [svg]);
}

function legend() {
  const key = (label, style, cls = 'fb-key__line') => h('span', { class: 'fb-key' }, [
    h('span', { class: cls, style }),
    h('span', { text: label }),
  ]);
  const patternKey = (label, fill) => h('span', { class: 'fb-key' }, [
    patternSwatch(fill),
    h('span', { text: label }),
  ]);
  return h('div', { class: 'fb-legend' }, [
    h('div', { class: 'fb-legend__row' }, [
      key('Vent soutenu', 'background:var(--wind)'),
      key('Rafales', 'background:var(--gust)'),
      key('Houle Hs', 'background:var(--swell)'),
    ]),
    h('div', { class: 'fb-legend__row' }, [
      patternKey('GO', 'var(--go)'),
      patternKey('Prudence', 'url(#fbPrudence)'),
      patternKey('No-go', 'url(#fbNogo)'),
      h('span', { class: 'fb-key' }, [
        h('span', { class: 'fb-key__swatch fb-key__swatch--night' }),
        h('span', { text: 'nuit' }),
      ]),
    ]),
  ]);
}

function readout(row, th) {
  const dot = h('span', { class: 'fb-reason__dot' });
  dot.style.background = STATE_VAR[row.state];
  return h('div', {}, [
    h('div', { class: 'fb-readout' }, [
      h('div', { class: 'fb-readout__when' }, [
        h('span', { class: 'fb-readout__hour', text: hourLabel(row.time) }),
        h('span', { class: 'fb-readout__day', text: row.dayLabel }),
      ]),
      h('div', { class: 'fb-readout__sep' }),
      h('div', { class: 'fb-readout__grid' }, [
        metric('VENT', num(row.wind, 0), 'km/h'),
        metric('RAFALE', num(row.gust, 0), 'km/h'),
        metric('HOULE', num(row.hs, 2), 'm'),
      ]),
      h('span', { class: `fb-tag fb-tag--${row.state}`, text: { go: 'GO', prudent: 'PRUD.', nogo: 'NO-GO' }[row.state] }),
    ]),
    h('div', { class: 'fb-reason', style: 'margin-top:6px' }, [
      dot,
      h('span', {
        text: row.state === 'go'
          ? `Dans les limites famille : vent < ${num(th.windFamilyMax, 0)} km/h, houle < ${num(th.hsFamilyMax, 2)} m.`
          : `${firstReasonText(row.familyReasons ?? row.reasons, row.metrics)}.`,
      }),
    ]),
  ]);
}

export function renderDecision(host, ctx) {
  const { rows, th, spot, state } = ctx;
  host.textContent = '';

  const confidence = confidenceLevel(rows);
  const freshness = h('div', { style: 'display:flex;align-items:center;gap:6px' }, [
    icon('clock', { size: 13, stroke: 'var(--ink-3)', width: 2 }),
    h('span', {
      class: 'fb-card__note',
      text: `Relevé ${hourLabel(ctx.generatedAt)} · ${relativeAge(ctx.generatedAt)}`,
    }),
  ]);

  const nowRow = rows[0];
  host.append(verdictHero(nowRow.state, { rows, th, freshness, confidence, engineWindow: ctx.engineWindow }));

  // ---- carte frise ----
  const chartHost = h('div');
  const tableHost = h('div', { class: 'fb-table-wrap' });
  const readoutHost = h('div');

  const chartBtn = h('button', { type: 'button', 'aria-pressed': 'true', text: 'Courbes' });
  const tableBtn = h('button', { type: 'button', 'aria-pressed': 'false', text: 'Tableau' });
  const toggle = h('div', { class: 'fb-toggle' }, [chartBtn, tableBtn]);

  const days = dailyBest(rows);
  const chips = [{ id: RANGE_ALL, label: `${rows.length} h` }]
    .concat(days.map((day) => ({ id: day.key, label: day.label.split(' ')[0] })));
  const chipRow = h('div', { class: 'fb-chip-row' });

  const view = { range: RANGE_ALL, selected: 0, mode: 'chart' };

  const visibleRows = () => (view.range === RANGE_ALL
    ? rows
    : rows.filter((row) => row.time.startsWith(view.range)));

  function paint() {
    const subset = visibleRows();
    view.selected = Math.max(0, Math.min(subset.length - 1, view.selected));
    chartHost.hidden = view.mode !== 'chart';
    tableHost.hidden = view.mode !== 'table';
    readoutHost.hidden = view.mode !== 'chart';
    chartBtn.setAttribute('aria-pressed', String(view.mode === 'chart'));
    tableBtn.setAttribute('aria-pressed', String(view.mode === 'table'));
    for (const button of chipRow.children) {
      button.setAttribute('aria-pressed', String(button.dataset.range === view.range));
    }
    if (view.mode === 'chart') {
      renderTimeline(chartHost, {
        rows: subset,
        th,
        selected: view.selected,
        onSelect: (index) => { view.selected = index; paint(); },
      });
      readoutHost.textContent = '';
      readoutHost.append(readout(subset[view.selected], th));
    } else {
      renderTable(tableHost, subset);
    }
  }

  for (const chip of chips) {
    const button = h('button', {
      type: 'button',
      class: 'fb-chip',
      dataset: { range: chip.id },
      'aria-pressed': 'false',
      text: chip.label,
      onClick: () => { view.range = chip.id; view.selected = 0; paint(); },
    });
    chipRow.append(button);
  }

  chartBtn.addEventListener('click', () => { view.mode = 'chart'; paint(); });
  tableBtn.addEventListener('click', () => { view.mode = 'table'; paint(); });

  const timelineCard = h('div', { class: 'fb-card' }, [
    h('div', { class: 'fb-card__head' }, [
      h('span', { class: 'fb-card__title', text: `Vent et mer sur ${rows.length} h` }),
      toggle,
    ]),
    chipRow,
    chartHost,
    legend(),
    readoutHost,
    tableHost,
  ]);
  host.append(timelineCard);

  // ---- jours suivants ----
  const list = h('div', { class: 'fb-list' });
  const upcoming = days.slice(1, 4);
  for (const day of upcoming) {
    const rail = h('span', { class: 'fb-row__rail' });
    const best = day.best;
    rail.style.background = best
      ? (best.hours >= th.windowMinHours ? 'var(--go)' : 'var(--prudent)')
      : 'var(--nogo)';
    const title = best
      ? `${day.label} · ${hourLabel(best.from.time)} → ${hourLabel(best.after?.time ?? best.to.time)}`
      : `${day.label} · aucune heure GO`;
    const sub = best
      ? `${best.hours} h${day.closer ? `, puis ${firstReasonText(day.closer.familyReasons, day.closer.metrics)}` : ''}`
      : firstReasonText(day.rows.find((row) => row.daylight)?.familyReasons ?? [], day.rows[0]?.metrics);
    list.append(h('button', {
      type: 'button',
      class: 'fb-row',
      onClick: () => { view.range = day.key; view.selected = 0; paint(); timelineCard.scrollIntoView({ block: 'nearest', behavior: 'smooth' }); },
    }, [
      rail,
      h('div', { class: 'fb-row__body' }, [
        h('span', { class: 'fb-row__title', text: title }),
        h('span', { class: 'fb-row__sub', text: sub }),
      ]),
      icon('chevronRight', { size: 15, stroke: 'var(--ink-3)', width: 2 }),
    ]));
  }

  const anyLongEnough = days.some((day) => day.best && day.best.hours >= th.windowMinHours);
  host.append(card(
    'Jours suivants',
    anyLongEnough ? null : `aucune fenêtre ≥ ${th.windowMinHours} h`,
    [list],
  ));

  paint();
  state.decision = view;
}

export { confidenceLevel };
