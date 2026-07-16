import test from 'node:test';
import assert from 'node:assert/strict';

import {
  normalizeSelectedDay,
  planningDayKeys,
  recommendationsForDay,
  tunisDateKey,
} from '../../public/js/day-selection.js';

test('Tunisia date key is stable across UTC midnight', () => {
  assert.equal(tunisDateKey('2026-07-17T22:30:00Z'), '2026-07-17');
  assert.equal(tunisDateKey('2026-07-17T23:30:00Z'), '2026-07-18');
});

test('planning horizon contains today and the following two Tunisia days', () => {
  const now = new Date('2026-07-16T10:00:00Z');
  assert.deepEqual(planningDayKeys(now), ['2026-07-16', '2026-07-17', '2026-07-18']);
  assert.equal(normalizeSelectedDay('2026-07-18', now), '2026-07-18');
  assert.equal(normalizeSelectedDay('2026-07-19', now), '2026-07-16');
});

test('activities are filtered by their start day in Africa/Tunis', () => {
  const recommendations = [
    {dest_slug: 'gammarth-port.json', start: '2026-07-18T09:00:00+01:00'},
    {dest_slug: 'ghar-el-melh.json', start: '2026-07-19T06:00:00+01:00'},
  ];
  assert.deepEqual(
    recommendationsForDay(recommendations, '2026-07-18').map((item) => item.dest_slug),
    ['gammarth-port.json'],
  );
});
