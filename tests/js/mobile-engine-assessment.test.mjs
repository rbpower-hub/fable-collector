import test from 'node:test';
import assert from 'node:assert/strict';

import {
  applyEngineAssessment, assessmentsByTime, currentEngineWindow,
} from '../../public/mobile/js/engine-assessment.js';

const fallback = {
  state: 'go', hard: false, reasons: [], family: [], daylight: true,
  metrics: {
    maxSpeed: 10, maxGust: 16, spreadSpeed: 2, nModels: 2,
    hsSpread: 0.1, nWaveSources: 2, minVis: 20, codes: [1],
    windScenarios: [], waveScenarios: [],
  },
};

test('les évaluations du moteur sont alignées avec les heures locales du spot', () => {
  const record = { time: '2026-08-27T12:00:00+01:00' };
  const indexed = assessmentsByTime({ hours: [record] });
  assert.equal(indexed.get('2026-08-27T12:00'), record);
});

test('le verdict et les métriques du moteur priment sur le portage JS', () => {
  const result = applyEngineAssessment(fallback, {
    condition_state: 'prudent', hard_veto: false, operating_light: false,
    reasons: [{ code: 'vent>=22', reason_fr: 'vent trop fort' }],
    metrics: {
      wind: { max_speed_kmh: 24, max_gust_kmh: 28, model_spread_kmh: 6, model_count: 3, display_speed_kmh: 23, display_gust_kmh: 27 },
      wave: { hs_spread_m: 0.2, source_count: 3, display_hs_m: 0.42, display_tp_s: 4.1 },
      visibility_min_km: 12, weather_codes: [2],
    },
  });
  assert.equal(result.state, 'prudent');
  assert.equal(result.metrics.maxSpeed, 24);
  assert.equal(result.display.hs, 0.42);
  assert.equal(result.daylight, false);
  assert.equal(result.reasons[0].reason_fr, 'vent trop fort');
});

test('WATCH reste non-GO dans la vue à trois états', () => {
  assert.equal(applyEngineAssessment(fallback, {
    condition_state: 'watch', reasons: [], metrics: {},
  }).state, 'nogo');
});

test('une fenêtre validée en cours ou future est choisie avant le repère client', () => {
  const now = new Date('2026-08-27T10:00:00+01:00');
  const future = { start: '2026-08-27T12:00:00+01:00', end: '2026-08-27T16:00:00+01:00' };
  const ended = { start: '2026-08-27T05:00:00+01:00', end: '2026-08-27T09:00:00+01:00' };
  assert.equal(currentEngineWindow({ windows: [future, ended] }, now), future);
});
