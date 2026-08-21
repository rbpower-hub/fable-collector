import test from 'node:test';
import assert from 'node:assert/strict';

import {
  getDisplayedNavigationWindows,
  getNavigationWindowsForDay,
  isLongTripNavigationWindow,
  navigationWindowBreakdown,
  navigationWindowCounts,
  tunisNavigationDateKey,
} from '../../public/js/navigation-windows.js';

const sunday = '2026-08-02';
const standard = {
  start: '2026-08-02T08:00:00+01:00',
  end: '2026-08-02T12:00:00+01:00',
  category: 'family',
  confidence: 'High',
};
const outbound = {
  ...standard,
  start: '2026-08-02T09:00:00+01:00',
  end: '2026-08-02T16:00:00+01:00',
  trip_mode: 'one_way_multi_day',
  route_kind: 'long_trip_one_way',
  direction: 'outbound',
};
const returned = {
  ...outbound,
  direction: 'return',
};

test('standard, outbound and return windows are displayed and counted on Sunday', () => {
  const data = {windows: [
    {dest_slug:'sidi-bou-said.json', windows:[standard]},
    {
      dest_slug:'kelibia.json',
      trip_mode:'one_way_multi_day',
      route_kind:'long_trip_one_way',
      windows:[outbound, returned],
    },
  ]};
  const displayed = getDisplayedNavigationWindows(sunday, data);
  assert.equal(displayed.length, 3);
  assert.deepEqual(navigationWindowCounts(displayed), {family:1, longTrip:2, total:3});
  assert.equal(displayed.filter(isLongTripNavigationWindow).length, 2);
  assert.deepEqual(displayed.slice(1).map((row) => row.windowItem.direction), ['outbound', 'return']);
});

test('Africa/Tunis Sunday filtering does not use the raw UTC date', () => {
  const tunisSundayAfterUtcMidnight = {
    ...standard,
    start:'2026-08-01T23:30:00Z',
    end:'2026-08-02T02:30:00Z',
  };
  const monday = {...standard, start:'2026-08-03T08:00:00+01:00', end:'2026-08-03T12:00:00+01:00'};
  const displayed = getDisplayedNavigationWindows(sunday, {
    windows:[{dest_slug:'test.json', windows:[tunisSundayAfterUtcMidnight, monday]}],
  });
  assert.equal(tunisNavigationDateKey(tunisSundayAfterUtcMidnight.start), sunday);
  assert.deepEqual(displayed.map((row) => row.windowItem), [tunisSundayAfterUtcMidnight]);
});

test('legacy directional containers and Pantelleria beta are normalized without duplicates', () => {
  const pantelleriaOutbound = {...outbound, route_kind:'offshore_one_way_beta', beta:true};
  const data = {windows:[{
    dest_slug:'pantelleria.json',
    dest_name:'Pantelleria',
    beta:true,
    route_kind:'offshore_one_way_beta',
    outbound:[pantelleriaOutbound],
    offshore_one_way_beta:{outbound_windows:[pantelleriaOutbound], return:[returned]},
  }]};
  const displayed = getDisplayedNavigationWindows(sunday, data);
  assert.equal(displayed.length, 2);
  assert.equal(navigationWindowCounts(displayed).longTrip, 2);
  assert.equal(displayed[0].destination.beta, true);
  assert.equal(displayed[0].windowItem.route_kind, 'offshore_one_way_beta');
});

test('counted window total is exactly the displayed card input total', () => {
  const displayed = getDisplayedNavigationWindows(sunday, {
    windows:[{dest_slug:'kelibia.json', route_kind:'long_trip_one_way', windows:[outbound, returned]}],
  });
  const counts = navigationWindowCounts(displayed);
  assert.equal(counts.family + counts.longTrip, displayed.length);
});

test('unified navigation rows distinguish family, prudent, off-hours and long-trip slots', () => {
  const prudent = {...standard, start:'2026-08-02T13:00:00+01:00', end:'2026-08-02T17:00:00+01:00', family_tier:'prudent'};
  const offHours = {...standard, start:'2026-08-02T20:00:00+01:00', end:'2026-08-02T23:00:00+01:00', category:'off_hours'};
  const rows = getNavigationWindowsForDay(sunday, {windows:[
    {dest_slug:'sidi-bou-said.json', windows:[standard, prudent, offHours]},
    {dest_slug:'kelibia.json', trip_mode:'one_way_multi_day', route_kind:'long_trip_one_way', windows:[outbound]},
  ]}, {categories:['family', 'off_hours']});

  assert.deepEqual(navigationWindowBreakdown(rows), {
    strict:1,
    prudent:1,
    offHours:1,
    family:2,
    longTrip:1,
    total:4,
  });
  assert.equal(getDisplayedNavigationWindows(sunday, {windows:[
    {dest_slug:'sidi-bou-said.json', windows:[standard, offHours]},
  ]}).length, 1);
});
