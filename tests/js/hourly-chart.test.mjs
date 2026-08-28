import assert from 'node:assert/strict';
import test from 'node:test';

import {mainReason, recordsForRange, renderHourlyExplorer, tunisDateKey} from '../../public/js/hourly-chart.js';

const hours = [
  {
    time:'2026-08-27T12:00:00+01:00', condition_state:'family', is_window_decision:false,
    operating_light:true, confidence:'High', reasons:[],
    metrics:{wind:{display_source:'icon',display_speed_kmh:8,display_gust_kmh:18,model_spread_kmh:2.1},wave:{display_source:'ecmwf',display_hs_m:.12,display_tp_s:5.1}},
  },
  {
    time:'2026-08-27T13:00:00+01:00', condition_state:'no_go', is_window_decision:false,
    operating_light:true, confidence:'Medium', reasons:[
      {code:'rafales>=30',severity:'hard_veto',reason_fr:'rafales 34 km/h ≥ 30',reason_en:'gusts 34 km/h ≥ 30'},
      {code:'Tp<3.0@Hs<0.4',severity:'family_limit',reason_fr:'période trop courte 2,4 s',reason_en:'wave period too short 2.4 s'},
    ],
    metrics:{wind:{display_source:'gfs',display_speed_kmh:12,display_gust_kmh:34,model_spread_kmh:7.0},wave:{display_source:'ecmwf',display_hs_m:.16,display_tp_s:2.4}},
  },
  {
    time:'2026-08-28T00:00:00+01:00', condition_state:'watch', is_window_decision:false,
    operating_light:false, confidence:'Medium', reasons:[{reason_fr:'conditions proches du seuil',reason_en:'near threshold'}],
    metrics:{wind:{display_source:'icon',display_speed_kmh:18,display_gust_kmh:24},wave:{display_source:'ecmwf',display_hs_m:.3}},
  },
];
const payload={dest_name:'Gammarth',is_window_decision:false,hours};

test('range filtering uses Tunisia calendar dates', () => {
  assert.equal(tunisDateKey(hours[0].time),'2026-08-27');
  assert.equal(recordsForRange(payload,'72h').length,3);
  assert.equal(recordsForRange(payload,'2026-08-27').length,2);
});

test('hard veto is the primary explanation while all causes remain rendered', () => {
  assert.match(mainReason(hours[1],'fr'),/rafales 34/);
  const html=renderHourlyExplorer({
    payload,destinations:[{dest_slug:'gammarth-port.json',dest_name:'Gammarth'}],
    selectedSlug:'gammarth-port.json',rules:{family:{thresholds:{wind:{family_max_kmh:22},gusts:{no_go_min_kmh:30},waves:{hs_family_max_m:.5}}}},
    mode:'curves',range:'2026-08-27',cursorTime:hours[1].time,language:'fr',
  });
  assert.match(html,/hourly-ribbon/);
  assert.match(html,/url\(#hourly-no_go\)/);
  assert.match(html,/période trop courte 2,4 s/);
  assert.match(html,/0.16 m · 2.4 s/);
  assert.match(html,/Écart modèles vent 7.0 km\/h/);
  assert.match(html,/Une heure favorable ne valide pas une sortie complète/);
  assert.doesNotMatch(html,/Family GO/);
});

test('table mode exposes values, state and cause without colour-only meaning', () => {
  const html=renderHourlyExplorer({payload,mode:'table',range:'72h',language:'fr'});
  assert.match(html,/<table class="hourly-table">/);
  assert.match(html,/34 km\/h/);
  assert.match(html,/NO-GO/);
  assert.match(html,/rafales 34 km\/h/);
});
