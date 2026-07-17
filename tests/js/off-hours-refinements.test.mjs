import assert from 'node:assert/strict';
import test from 'node:test';

import {
  categoryOf,
  offHoursRowsForDay,
  tunisDateKey,
} from '../../public/js/off-hours-refinements.js';

test('Tunis date key keeps local calendar day around UTC midnight', () => {
  assert.equal(tunisDateKey('2026-07-18T23:30:00Z'), '2026-07-19');
  assert.equal(tunisDateKey('2026-07-18T03:00:00+01:00'), '2026-07-18');
});

test('category prefers explicit recommendation then source window', () => {
  assert.equal(categoryOf({category: 'off_hours'}, {category: 'family'}), 'off_hours');
  assert.equal(categoryOf({}, {category: 'off_hours'}), 'off_hours');
  assert.equal(categoryOf({}, {}), 'family');
});

test('off-hours rows are coastal, date-scoped, and not Family GO', () => {
  const windows = {
    windows: [
      {
        dest_slug: 'gammarth-port.json',
        dest_name: 'Gammarth (port)',
        windows: [
          {start: '2026-07-19T04:00:00+01:00', end: '2026-07-19T07:00:00+01:00', category: 'off_hours'},
          {start: '2026-07-19T09:00:00+01:00', end: '2026-07-19T12:00:00+01:00', category: 'family'},
          {start: '2026-07-20T04:00:00+01:00', end: '2026-07-20T07:00:00+01:00', category: 'off_hours'},
        ],
      },
      {
        dest_slug: 'pantelleria.json',
        trip_mode: 'one_way_multi_day',
        windows: [
          {start: '2026-07-19T05:00:00+01:00', end: '2026-07-19T10:00:00+01:00', category: 'off_hours'},
        ],
      },
    ],
  };

  const rows = offHoursRowsForDay(windows, '2026-07-19');
  assert.equal(rows.length, 1);
  assert.equal(rows[0].destination.dest_slug, 'gammarth-port.json');
  assert.equal(rows[0].windowItem.category, 'off_hours');
});
