import test from 'node:test';
import assert from 'node:assert/strict';

import {
  normalizeSelectedDay,
  planningDayKeys,
  recommendationsForDay,
  tunisDateKey,
} from '../../public/js/day-selection.js';

test('tunisDateKey uses Africa/Tunis', () => {
  assert.equal(tunisDateKey('2026-07-16T23:30:00Z'), '2026-07-17');
});

test('planningDayKeys returns three consecutive days', () => {
  assert.deepEqual(
    planningDayKeys(new Date('2026-07-16T12:00:00Z')),
    ['2026-07-16', '2026-07-17', '2026-07-18'],
  );
});

test('normalizeSelectedDay falls back to today outside the visible horizon', () => {
  const now = new Date('2026-07-16T12:00:00Z');
  assert.equal(normalizeSelectedDay('2026-07-17', now), '2026-07-17');
  assert.equal(normalizeSelectedDay('2026-07-22', now), '2026-07-16');
});

test('recommendationsForDay keeps only the selected day', () => {
  const recommendations = [
    {dest_name: 'Sidi Bou Saïd', start: '2026-07-16T08:00:00+01:00'},
    {dest_name: 'Ghar el Melh', start: '2026-07-17T09:00:00+01:00'},
    {dest_name: 'Ras Fartass', start: '2026-07-17T12:00:00+01:00'},
  ];
  assert.deepEqual(
    recommendationsForDay(recommendations, '2026-07-17').map((item) => item.dest_name),
    ['Ghar el Melh', 'Ras Fartass'],
  );
});
