/** Adaptation des évaluations horaires publiées par le moteur vers Mobile_view. */

const STATE = {
  family: 'go',
  prudent: 'prudent',
  watch: 'nogo',
  no_go: 'nogo',
};

function finite(value, fallback) {
  return Number.isFinite(value) ? value : fallback;
}

export function assessmentsByTime(payload) {
  const byTime = new Map();
  for (const assessment of payload?.hours ?? []) {
    // Les spots sont publiés sans offset, les évaluations avec offset.
    const key = String(assessment?.time ?? '').slice(0, 16);
    if (key) byTime.set(key, assessment);
  }
  return byTime;
}

export function applyEngineAssessment(fallback, assessment) {
  if (!assessment || !STATE[assessment.condition_state]) return fallback;

  const wind = assessment.metrics?.wind ?? {};
  const wave = assessment.metrics?.wave ?? {};
  const causes = Array.isArray(assessment.reasons) ? assessment.reasons : [];
  const metrics = {
    ...fallback.metrics,
    maxSpeed: finite(wind.max_speed_kmh, fallback.metrics.maxSpeed),
    maxGust: finite(wind.max_gust_kmh, fallback.metrics.maxGust),
    spreadSpeed: finite(wind.model_spread_kmh, fallback.metrics.spreadSpeed),
    nModels: finite(wind.model_count, fallback.metrics.nModels),
    hsSpread: finite(wave.hs_spread_m, fallback.metrics.hsSpread),
    nWaveSources: finite(wave.source_count, fallback.metrics.nWaveSources),
    minVis: finite(assessment.metrics?.visibility_min_km, fallback.metrics.minVis),
    codes: assessment.metrics?.weather_codes ?? fallback.metrics.codes,
  };

  return {
    ...fallback,
    state: STATE[assessment.condition_state],
    engineState: assessment.condition_state,
    hard: Boolean(assessment.hard_veto),
    reasons: causes,
    family: causes,
    metrics,
    daylight: typeof assessment.operating_light === 'boolean'
      ? assessment.operating_light
      : fallback.daylight,
    display: {
      wind: finite(wind.display_speed_kmh, null),
      gust: finite(wind.display_gust_kmh, null),
      direction: finite(wind.display_direction_deg, null),
      hs: finite(wave.display_hs_m, null),
      tp: finite(wave.display_tp_s, null),
    },
  };
}

export function currentEngineWindow(engine, now = new Date()) {
  const candidates = (engine?.windows ?? [])
    .filter((window) => window?.start && window?.end)
    .filter((window) => new Date(window.end).getTime() > now.getTime())
    .sort((a, b) => new Date(a.start) - new Date(b.start));
  return candidates[0] ?? null;
}
