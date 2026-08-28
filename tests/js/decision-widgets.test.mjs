import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import test from 'node:test';
import vm from 'node:vm';

const source = await readFile(new URL('../../public/decision-widgets.js', import.meta.url), 'utf8');
const sandbox = {window:{}, Intl};
vm.runInNewContext(source, sandbox);
const widgets = sandbox.window.FABLEDecisionWidgets;

const destination = {
  required_hours:4,
  diagnostics:{
    near_miss:{validated_hours:0},
    first_blocker:{metrics:{wind_kmh:27,gust_kmh:34,hs_m:.6,visibility_km:8}},
  },
};
const rules = {
  window_hours:{min:4},
  wind:{family_max_kmh:22},
  sea:{family_max_hs_m:.5},
  overrides:{gusts_hard_nogo_kmh:30,visibility_km_min:5},
};

test('structured NO-GO checks preserve engine values and explicit statuses', () => {
  const checks = widgets.checks(destination,rules,'fr');
  assert.deepEqual(Array.from(checks, ({key,passed}) => [key,passed]), [
    ['duration',false],['gust',false],['wind',false],['wave',false],['visibility',true],
  ]);
  const html = widgets.checksHtml(destination,rules,'fr');
  assert.match(html,/Durée famille continue/);
  assert.match(html,/DÉPASSÉ/);
  assert.match(html,/INSUFFISANT/);
  assert.match(html,/8,0 km/);
  assert.match(html,/decision-check-track/);
});

test('confidence bars never expose a numeric score', () => {
  const html = widgets.confidenceBarsHtml('medium','Moyenne');
  assert.match(html,/quality-bars/);
  assert.match(html,/Moyenne/);
  assert.doesNotMatch(html,/%/);
});

test('maximum thresholds keep the engine strict boundary', () => {
  const exactThreshold = {
    diagnostics:{first_blocker:{metrics:{gust_kmh:30,wind_kmh:22,hs_m:.5}}},
  };
  const checks = widgets.checks(exactThreshold,rules,'fr');
  assert.deepEqual(Array.from(checks, ({key,passed}) => [key,passed]), [
    ['gust',false],['wind',false],['wave',false],
  ]);
  assert.match(widgets.checksHtml(exactThreshold,rules,'fr'),/Rafales max · &lt; 30,0 km\/h/);
});
