import assert from 'node:assert/strict';
import test from 'node:test';

import {friendlyReason} from '../../public/js/reasons-i18n.js';

const cases = [
  ['orages (code 95) à 2026-07-15T11:00:00+01:00', '⛈️ Orages prévus — sortie impossible'],
  ['vis<5km à 2026-07-15T11:00:00+01:00', '🌫️ Visibilité insuffisante'],
  ['rafales 35 km/h ≥ 30 à 2026-07-15T11:00:00+01:00', '💨 Rafales trop fortes (35 km/h)'],
  ['squalls Δ≥17 à 2026-07-15T11:00:00+01:00', '💨 Vent instable (risque de grains)'],
  ['vent onshore 24 km/h', '🌊 Vent vers la côte trop fort'],
  ['vent 28 km/h ≥ 25', '💨 Vent trop fort (28 km/h)'],
  ['vagues 0.9 m > 0.8', '🌊 Mer trop agitée (0.9 m)'],
  ['Tp 3.8 < 4.5 s', '🌊 Vagues courtes et inconfortables'],
  ['vagues_inconnues', '❓ Données de vagues manquantes'],
  ['aucune fenêtre de 4h', '📅 Pas de créneau assez long en journée'],
];

for (const [raw, expected] of cases) {
  test(`friendly FR: ${raw}`, () => {
    assert.ok(friendlyReason(raw, 'fr').startsWith(expected));
  });
}

test('English reason is complete', () => {
  assert.equal(friendlyReason('Tp 3.8 < 4.5 s', 'en'), '🌊 Short, uncomfortable waves');
});

test('unknown reason remains visible', () => {
  assert.equal(friendlyReason('configuration spéciale', 'fr'), 'configuration spéciale');
});
