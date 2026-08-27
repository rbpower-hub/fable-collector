/**
 * Plages continues derivees du verdict horaire.
 *
 * Ceci n'est PAS le detecteur de fenetres du moteur (fable/window_detect.py) :
 * il valide en plus le corridor, le mouillage, la lumiere du jour astronomique
 * et la confiance. On s'en sert uniquement pour dire au lecteur ou se situent
 * les heures exploitables ; le verdict de fenetre publie dans windows.json
 * reste la reference et est affiche tel quel quand il existe.
 */

import { dayKey } from './format.js';

/** @returns {Array<{start:number,end:number,hours:number,state:string,day:string}>} */
export function runsOfState(rows, state, { familyHoursOnly = true } = {}) {
  const runs = [];
  let start = -1;
  const eligible = (row) => row.state === state && (!familyHoursOnly || row.daylight);
  rows.forEach((row, index) => {
    if (eligible(row)) {
      if (start < 0) start = index;
      return;
    }
    if (start >= 0) {
      runs.push({ start, end: index, hours: index - start, state, day: rows[start].day });
      start = -1;
    }
  });
  if (start >= 0) {
    runs.push({ start, end: rows.length, hours: rows.length - start, state, day: rows[start].day });
  }
  return runs;
}

/** La plus longue plage GO de chaque journee, plus le premier bloqueur qui la referme. */
export function dailyBest(rows) {
  const byDay = new Map();
  for (const row of rows) {
    const key = dayKey(row.time);
    if (!byDay.has(key)) byDay.set(key, []);
    byDay.get(key).push(row);
  }
  const out = [];
  for (const [key, dayRows] of byDay) {
    const runs = runsOfState(dayRows, 'go');
    const best = runs.sort((a, b) => b.hours - a.hours)[0] ?? null;
    let closer = null;
    if (best && best.end < dayRows.length) closer = dayRows[best.end];
    out.push({
      key,
      label: dayRows[0].dayLabel,
      rows: dayRows,
      best: best ? {
        ...best,
        from: dayRows[best.start],
        to: dayRows[best.end - 1],
        after: dayRows[best.end] ?? null,
      } : null,
      closer,
    });
  }
  return out;
}

/** Plage GO en cours ou a venir, a partir de l'index courant. */
export function currentOrNextRun(rows, fromIndex = 0) {
  const runs = runsOfState(rows, 'go');
  return runs.find((run) => run.end > fromIndex) ?? null;
}
