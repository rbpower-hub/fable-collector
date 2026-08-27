import test from 'node:test';
import assert from 'node:assert/strict';

import {navigationVerdictForDay} from '../../public/js/navigation-verdicts.js';

const now = new Date('2026-08-02T05:00:00Z');
const fresh = {generated_at:'2026-08-02T04:30:00Z', cadence_minutes:60};
const stale = {generated_at:'2026-08-01T22:00:00Z', cadence_minutes:60};
const rules = {window_hours:{min:4}};
const strict = {
  start:'2026-08-02T09:00:00+01:00', end:'2026-08-02T14:00:00+01:00',
  category:'family', family_tier:'standard', confidence:'Medium',
};
const prudent = {
  ...strict, start:'2026-08-02T07:00:00+01:00', end:'2026-08-02T13:00:00+01:00',
  family_tier:'prudent', confidence:'High',
};

function verdict(windows, status = fresh, selectedDay = '2026-08-02') {
  return navigationVerdictForDay({windows, status, selectedDay, rules, now});
}

test('stale data has priority and neutralizes navigation rows', () => {
  const result = verdict({windows:[{dest_slug:'gammarth.json', windows:[strict]}]}, stale);
  assert.equal(result.state, 'STALE');
  assert.equal(result.rows.length, 0);
});

test('strict family GO wins over an earlier prudent slot', () => {
  const result = verdict({windows:[{dest_slug:'gammarth.json', windows:[prudent, strict]}]});
  assert.equal(result.state, 'GO_FAMILY');
  assert.equal(result.window, strict);
  assert.deepEqual(result.counts, {strict:1, prudent:1, offHours:0, watch:0, family:2, longTrip:0, total:2});
});

test('review-only candidate is WATCH and never becomes a Family GO', () => {
  const watch = {
    ...strict,
    category:'watch',
    family_tier:undefined,
    technical_tier:'expert_review',
    family_go:false,
    review_required:true,
  };
  const result = verdict({windows:[{dest_slug:'gammarth.json', windows:[], watch_windows:[watch]}]});
  assert.equal(result.state, 'WATCH');
  assert.equal(result.counts.family, 0);
  assert.equal(result.counts.watch, 1);
  assert.equal(result.window.family_go, false);
});

test('a validated Family GO always has priority over WATCH', () => {
  const watch = {...strict, category:'watch', family_go:false, review_required:true};
  const result = verdict({windows:[{
    dest_slug:'gammarth.json', windows:[strict], watch_windows:[watch],
  }]});
  assert.equal(result.state, 'GO_FAMILY');
  assert.equal(result.window, strict);
});

test('untrusted watch-shaped data cannot activate WATCH', () => {
  const untrusted = {...strict, category:'watch'};
  const result = verdict({windows:[{
    dest_slug:'gammarth.json', windows:[], watch_windows:[untrusted],
  }]});
  assert.equal(result.state, 'NO_GO');
});

test('off-hours weather is explicit and never becomes a Family GO', () => {
  const offHours = {...strict, category:'off_hours'};
  const result = verdict({windows:[{dest_slug:'gammarth.json', windows:[offHours]}]});
  assert.equal(result.state, 'OFF_HOURS');
  assert.equal(result.counts.family, 0);
  assert.equal(result.counts.offHours, 1);
});

test('a long-trip-only day is distinguished without becoming a family outing', () => {
  const outbound = {...strict, trip_mode:'one_way_multi_day', route_kind:'long_trip_one_way'};
  const result = verdict({windows:[{
    dest_slug:'kelibia.json', trip_mode:'one_way_multi_day', route_kind:'long_trip_one_way', windows:[outbound],
  }]});
  assert.equal(result.state, 'TRAVEL_ONLY');
  assert.equal(result.counts.family, 0);
  assert.equal(result.counts.longTrip, 1);
});

test('selected-day verdict never falls back to a window from another day', () => {
  const tomorrow = {...strict, start:'2026-08-03T09:00:00+01:00', end:'2026-08-03T14:00:00+01:00'};
  const result = verdict({windows:[{dest_slug:'sidi-bou-said.json', windows:[tomorrow]}]});
  assert.equal(result.state, 'NO_GO');
  assert.equal(result.window, null);
  assert.equal(result.counts.family, 0);
});

test('beta or composite local rows never appear as actionable family options', () => {
  const result = verdict({windows:[{
    dest_slug:'prototype.json', beta:true, route_kind:'composite_beta', windows:[strict],
  }]});
  assert.equal(result.state, 'NO_GO');
  assert.equal(result.rows.length, 0);
  assert.equal(result.counts.family, 0);
});

test('missing payload and fresh empty payload remain distinct', () => {
  assert.equal(verdict(null).state, 'NO_DATA');
  assert.equal(verdict({windows:[]}).state, 'NO_GO');
});

test('an upcoming adaptive three-hour window is not removed by the global four-hour rule', () => {
  const current = new Date('2026-08-02T10:13:00Z');
  const adaptive = {
    start:'2026-08-02T12:00:00+01:00', end:'2026-08-02T15:00:00+01:00',
    category:'family', family_tier:'standard', confidence:'Medium',
  };
  const result = navigationVerdictForDay({
    windows:{windows:[{dest_slug:'sidi-bou-said.json', required_hours:3, windows:[adaptive]}]},
    status:{generated_at:'2026-08-02T10:00:00Z', cadence_minutes:60},
    selectedDay:'2026-08-02', rules, now:current,
  });
  assert.equal(result.state, 'GO_FAMILY');
  assert.equal(result.rows.length, 1);
});

test('a started window disappears when its destination duration no longer fits', () => {
  const current = new Date('2026-08-02T11:15:00Z');
  const adaptive = {
    start:'2026-08-02T12:00:00+01:00', end:'2026-08-02T15:00:00+01:00',
    category:'family', family_tier:'standard', confidence:'Medium',
  };
  const result = navigationVerdictForDay({
    windows:{windows:[{dest_slug:'sidi-bou-said.json', required_hours:3, windows:[adaptive]}]},
    status:{generated_at:'2026-08-02T11:00:00Z', cadence_minutes:60},
    selectedDay:'2026-08-02', rules, now:current,
  });
  assert.equal(result.state, 'NO_GO');
  assert.equal(result.rows.length, 0);
});
