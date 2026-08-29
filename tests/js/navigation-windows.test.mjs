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
    watch:0,
    family:2,
    longTrip:1,
    total:4,
  });
  assert.equal(getDisplayedNavigationWindows(sunday, {windows:[
    {dest_slug:'sidi-bou-said.json', windows:[standard, offHours]},
  ]}).length, 1);
});

test('les trois vues comptent la meme chose pour une journee mixte', () => {
  // Lundi reel : 4 fenetres famille, une hors horaires, et un aller-retour
  // long trajet propose a plusieurs heures de depart.
  const longTrip = (start, direction) => ({
    start, end:'2026-08-31T04:00:00+01:00', hours:3,
    trip_mode:'one_way_multi_day', direction,
  });
  const windows = {windows:[
    {dest_slug:'gammarth-port.json', dest_name:'Gammarth', windows:[
      {start:'2026-08-31T08:00:00+01:00', end:'2026-08-31T13:00:00+01:00', category:'family'},
    ]},
    {dest_slug:'ghar-el-melh.json', dest_name:'Ghar el Melh', windows:[
      {start:'2026-08-31T08:00:00+01:00', end:'2026-08-31T13:00:00+01:00', category:'family'},
    ]},
    {dest_slug:'el-haouaria.json', dest_name:'El Haouaria', windows:[
      {start:'2026-08-31T02:00:00+01:00', end:'2026-08-31T08:00:00+01:00', category:'off_hours'},
    ]},
    {dest_slug:'pantelleria.json', dest_name:'Pantelleria', windows:[
      longTrip('2026-08-31T01:00:00+01:00', 'outbound'),
      longTrip('2026-08-31T02:00:00+01:00', 'outbound'),
      longTrip('2026-08-31T03:00:00+01:00', 'outbound'),
      longTrip('2026-08-31T01:30:00+01:00', 'return'),
    ]},
  ]};
  const day = '2026-08-31';
  const displayed = getDisplayedNavigationWindows(day, windows);
  const all = getNavigationWindowsForDay(day, windows, {categories:['family', 'off_hours', 'watch']});

  const familyView = navigationWindowCounts(displayed);
  const simpleView = navigationWindowBreakdown(all);

  // Deux fenetres famille, quelle que soit la vue qui pose la question.
  assert.equal(familyView.family, 2);
  assert.equal(simpleView.family, 2);
  // Un aller et un retour, pas quatre creneaux.
  assert.equal(familyView.longTrip, 2);
  assert.equal(simpleView.longTrip, 2);
  // La fenetre hors horaires reste comptee a part, jamais dans les options.
  assert.equal(simpleView.offHours, 1);
});
