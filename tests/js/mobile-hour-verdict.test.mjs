import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import { fileURLToPath } from 'node:url';

import { parseThresholds, THRESHOLD_FALLBACK } from '../../public/mobile/js/thresholds.js';
import { classifySeries, isOnshore, prudentReasons } from '../../public/mobile/js/hour-verdict.js';

const fixturePath = fileURLToPath(new URL('../fixtures/mobile_hours.json', import.meta.url));
const fixture = JSON.parse(fs.readFileSync(fixturePath, 'utf8'));

test('la vue mobile reproduit le verdict horaire du moteur', () => {
  const th = parseThresholds(fixture.meta.rules, null);
  const states = classifySeries(fixture, fixture.meta.onshore_sectors, th).map((v) => v.state);
  assert.deepEqual(states, fixture.expected_states);
});

test('chaque cas de la fixture est identifie par son libelle', () => {
  const th = parseThresholds(fixture.meta.rules, null);
  const verdicts = classifySeries(fixture, fixture.meta.onshore_sectors, th);
  fixture.case_labels.forEach((label, index) => {
    assert.equal(
      verdicts[index].state,
      fixture.expected_states[index],
      `cas « ${label} » (heure ${fixture.hourly.time[index]})`,
    );
  });
});

test('les seuils viennent du schema plat, pas des valeurs de repli', () => {
  const th = parseThresholds(fixture.meta.rules, null);
  assert.equal(th.windFamilyMax, 22);
  assert.equal(th.tpMinAtLt04, 3.0);
  assert.notEqual(th.windFamilyMax, THRESHOLD_FALLBACK.windFamilyMax);
  assert.notEqual(th.tpMinAtLt04, THRESHOLD_FALLBACK.tpMinAtLt04);
});

test('le schema v2 complete ce que meta.rules ne publie pas', () => {
  const normalized = {
    prudent: {
      enabled: true, wind_max_kmh: 23, gust_max_kmh: 28, hs_max_m: 0.4, tp_min_s: 3.3,
    },
    family: { window_hours: { min: 4, max: 6 } },
  };
  const th = parseThresholds(fixture.meta.rules, normalized);
  assert.equal(th.prudentWindMax, 23);
  assert.equal(th.prudentTpMin, 3.3);
  assert.equal(th.windowMinHours, 4);
});

test('le secteur onshore accepte les intervalles qui passent par le nord', () => {
  assert.equal(isOnshore(90, [[30, 150]]), true);
  assert.equal(isOnshore(200, [[30, 150]]), false);
  assert.equal(isOnshore(350, [[330, 360], [0, 70]]), true);
  assert.equal(isOnshore(10, [[330, 70]]), true);
  assert.equal(isOnshore(180, [[330, 70]]), false);
});

test('la plage horaire famille est appliquee sans changer le verdict', () => {
  const th = parseThresholds(fixture.meta.rules, null);
  const verdicts = classifySeries(fixture, fixture.meta.onshore_sectors, th);
  const night = verdicts.at(-1);
  assert.equal(night.state, 'go');
  assert.equal(night.daylight, false);
  assert.equal(verdicts[0].daylight, true);
});

test('le profil prudent ne contourne pas un refus mer family', () => {
  const th = parseThresholds(fixture.meta.rules, null);
  const metrics = {
    anyOnshore: false,
    maxSpeed: 10,
    maxGust: 18,
    // Hs reste sous le plafond prudent, mais Tp est trop court pour Family.
    waveScenarios: [{hs: 0.35, tp: th.tpMinAtLt04 - 0.1}],
  };
  assert.ok(prudentReasons(metrics, th).includes(`Tp<${th.tpMinAtLt04}@Hs<0.4`));
});
