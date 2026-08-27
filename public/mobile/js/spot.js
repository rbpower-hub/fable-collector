/** Ecran Spot : detail d'une journee, trace des regles, accord des modeles. */

import { renderTimeline } from './chart.js';
import { dailyBest } from './runs.js';
import {
  dayLong, firstReasonText, hourLabel, num,
} from './format.js';
import {
  card, checkRow, h, icon, stateBadge, tile,
} from './ui.js';

function dayState(dayRows) {
  if (dayRows.some((row) => row.state === 'go' && row.daylight)) {
    return dayRows.filter((row) => row.daylight).every((row) => row.state === 'go') ? 'go' : 'prudent';
  }
  if (dayRows.some((row) => row.state === 'prudent' && row.daylight)) return 'prudent';
  return 'nogo';
}

function extremes(dayRows, key) {
  const values = dayRows.map((row) => row[key]).filter(Number.isFinite);
  if (!values.length) return { min: null, max: null };
  return { min: Math.min(...values), max: Math.max(...values) };
}

function ruleChecks(dayRows, th) {
  const daylight = dayRows.filter((row) => row.daylight);
  const scope = daylight.length ? daylight : dayRows;
  const gust = extremes(scope, 'gust');
  const wind = extremes(scope, 'wind');
  const hs = extremes(scope, 'hs');
  const vis = scope
    .map((row) => row.metrics.minVis)
    .filter(Number.isFinite);
  const minVis = vis.length ? Math.min(...vis) : null;
  const runs = dailyBest(dayRows)[0]?.best;
  const continuous = runs ? runs.hours : 0;
  const onshore = scope.some((row) => row.metrics.anyOnshore);

  const checks = [
    {
      label: `Rafales max · veto ${num(th.gustNoGoMin, 0)} km/h`,
      value: `${num(gust.max, 1)} km/h`,
      ratio: gust.max / th.gustNoGoMin,
      exceeded: gust.max >= th.gustNoGoMin,
    },
    {
      label: `Durée famille continue · min ${th.windowMinHours} h`,
      value: `${continuous} h`,
      ratio: continuous / th.windowMinHours,
      exceeded: continuous < th.windowMinHours,
    },
    {
      label: `Vent soutenu max · limite ${num(th.windFamilyMax, 0)} km/h`,
      value: `${num(wind.max, 1)} km/h`,
      ratio: wind.max / th.windFamilyMax,
      exceeded: wind.max >= th.windFamilyMax,
    },
    {
      label: `Houle Hs max · limite ${num(th.hsFamilyMax, 2)} m`,
      value: `${num(hs.max, 2)} m`,
      ratio: hs.max / th.hsFamilyMax,
      exceeded: hs.max >= th.hsFamilyMax,
    },
  ];

  if (onshore) {
    checks.splice(2, 0, {
      label: `Secteur onshore · dégrade au-dessus de ${num(th.onshoreMaxOk, 0)} km/h`,
      value: `${num(wind.max, 1)} km/h`,
      ratio: wind.max / th.onshoreMaxOk,
      exceeded: wind.max > th.onshoreMaxOk,
    });
  }

  if (Number.isFinite(minVis)) {
    checks.push({
      label: `Visibilité min · seuil ${num(th.visMinKm, 0)} km`,
      value: `${num(minVis, 1)} km`,
      ratio: Math.min(1, minVis / th.visMinKm),
      exceeded: minVis < th.visMinKm,
    });
  }

  return checks;
}

function modelAgreement(dayRows) {
  const spreads = dayRows.map((row) => row.spreadSpeed).filter(Number.isFinite);
  if (!spreads.length) return null;
  const maxSpread = Math.max(...spreads);
  const sources = new Set();
  for (const row of dayRows) {
    for (const scenario of row.metrics.windScenarios) sources.add(scenario.source);
  }
  const waveSources = new Set();
  for (const row of dayRows) {
    for (const scenario of row.metrics.waveScenarios) waveSources.add(scenario.source);
  }
  const hsSpread = Math.max(...dayRows.map((row) => row.spreadHs).filter(Number.isFinite), 0);
  return { maxSpread, sources: [...sources], waveSources: [...waveSources], hsSpread };
}

export function renderSpot(host, ctx) {
  const { rows, th, spot, dayKey: requestedDay } = ctx;
  host.textContent = '';

  const days = dailyBest(rows);
  const day = days.find((entry) => entry.key === requestedDay) ?? days[0];
  const dayRows = day.rows;
  const state = dayState(dayRows);

  host.append(h('div', { class: 'fb-topbar', style: 'padding-left:0;padding-right:0' }, [
    h('button', {
      type: 'button',
      class: 'fb-iconbtn',
      'aria-label': 'Retour à la décision',
      onClick: () => ctx.onBack?.(),
    }, [icon('back', { size: 17, stroke: 'var(--ink-2)', width: 2 })]),
    h('div', { class: 'fb-topbar__meta' }, [
      h('span', {
        class: 'fb-topbar__title',
        style: 'font-size:15px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis',
        text: `${spot.name.replace(/\s*\(.*\)$/, '')} · ${dayLong(dayRows[0].time)}`,
      }),
      h('span', { class: 'fb-topbar__sub', text: 'Détail heure par heure' }),
    ]),
    stateBadge(state),
  ]));

  // Selecteur de jour
  const chipRow = h('div', { class: 'fb-chip-row' });
  for (const entry of days) {
    chipRow.append(h('button', {
      type: 'button',
      class: 'fb-chip',
      'aria-pressed': String(entry.key === day.key),
      text: entry.label,
      onClick: () => ctx.onDay?.(entry.key),
    }));
  }
  host.append(chipRow);

  // Frise du jour
  const chartHost = h('div');
  const chartCard = h('div', { class: 'fb-card' }, [
    h('div', { class: 'fb-card__head' }, [
      h('span', { class: 'fb-card__title', text: 'Vent, rafales et houle' }),
      h('span', { class: 'fb-card__note', text: `${hourLabel(dayRows[0].time)} → ${hourLabel(dayRows.at(-1).time)}` }),
    ]),
    chartHost,
  ]);
  host.append(chartCard);
  renderTimeline(chartHost, { rows: dayRows, th, selected: 0, onSelect: () => {} });

  // Trace des regles
  const checks = ruleChecks(dayRows, th);
  const failing = checks.filter((check) => check.exceeded);
  const title = failing.length ? `Pourquoi ${state === 'nogo' ? 'NO-GO' : 'pas GO plein'}` : 'Contrôles de la journée';
  const digest = ctx.rulesDigest ? `rules ${ctx.rulesDigest}` : null;
  host.append(card(title, digest, [
    h('div', { class: 'fb-checks' }, checks.map(checkRow)),
  ]));

  // Accord des modeles
  const agreement = modelAgreement(dayRows);
  if (agreement) {
    host.append(card('Accord des modèles', `écart max ${num(agreement.maxSpread, 0)} km/h`, [
      h('div', {
        class: 'fb-muted',
        text: `Vent : ${agreement.sources.join(', ')}.`,
      }),
      h('div', {
        class: 'fb-muted',
        text: `Vagues : ${agreement.waveSources.join(', ')} — écart Hs jusqu’à ${num(agreement.hsSpread, 2)} m.`,
      }),
    ]));
  }

  // Conditions de la journee
  const temps = dayRows.map((row) => row.temperature).filter(Number.isFinite);
  const uv = dayRows.map((row) => row.uv).filter(Number.isFinite);
  const tps = dayRows.map((row) => row.tp).filter(Number.isFinite);
  const viss = dayRows.map((row) => row.metrics.minVis).filter(Number.isFinite);
  const tiles = [];
  if (temps.length) tiles.push(tile('TEMP.', `${num(Math.min(...temps), 0)}–${num(Math.max(...temps), 0)}°`, 'sur la journée'));
  if (uv.length) tiles.push(tile('UV MAX', num(Math.max(...uv), 1), 'indice'));
  if (viss.length) tiles.push(tile('VISIB.', `${num(Math.min(...viss), 0)} km`, 'minimum'));
  if (tps.length) tiles.push(tile('PÉRIODE', `${num(Math.min(...tps), 1)} s`, 'Tp minimum'));
  if (tiles.length) {
    host.append(card('Conditions de la journée', null, [h('div', { class: 'fb-tiles' }, tiles)]));
  }

  const worst = dayRows.find((row) => row.daylight && row.state !== 'go');
  if (worst) {
    host.append(h('div', {
      class: 'fb-muted',
      style: 'padding:0 4px 4px',
      text: `Première heure non GO : ${hourLabel(worst.time)} — ${firstReasonText(worst.reasons, worst.metrics)}.`,
    }));
  }
}
