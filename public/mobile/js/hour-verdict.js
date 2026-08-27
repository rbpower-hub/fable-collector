/**
 * Verdict horaire cote client.
 *
 * Portage direct de fable/window_policy.py (hard_reasons,
 * standard_wave_reasons, hour_ok_for_phase) pour la phase "transit" hors
 * mouillage abrite. Le moteur Python reste la reference : cette copie existe
 * parce que le JSON publie n'expose pas encore de verdict heure par heure.
 * Toute divergence est un bug de ce fichier, pas une regle nouvelle.
 */

const HOUR_RE = /T(\d{2}):/;

function normaliseAngle(angle) {
  const value = Number(angle);
  if (!Number.isFinite(value)) return null;
  return ((value % 360) + 360) % 360;
}

export function isOnshore(direction, sectors) {
  const angle = normaliseAngle(direction);
  if (angle === null || !Array.isArray(sectors)) return false;
  return sectors.some((sector) => {
    if (!Array.isArray(sector) || sector.length < 2) return false;
    const start = normaliseAngle(sector[0]);
    const end = normaliseAngle(sector[1]);
    if (start === null || end === null) return false;
    return start <= end ? angle >= start && angle <= end : angle >= start || angle <= end;
  });
}

/**
 * Agrege, pour une heure donnee, le pire cas sur tous les modeles publies.
 * Reprend fable.window_models.worst_metrics_at_hour.
 */
export function metricsAtHour(spot, index, sectors) {
  const windScenarios = [];
  const models = spot?.models ?? {};
  for (const [source, payload] of Object.entries(models)) {
    const hourly = payload?.hourly ?? {};
    const speed = Number(hourly.wind_speed_10m?.[index]);
    const gust = Number(hourly.wind_gusts_10m?.[index]);
    if (!Number.isFinite(speed) || !Number.isFinite(gust)) continue;
    windScenarios.push({
      source,
      speed,
      gust,
      gustDelta: gust - speed,
      direction: Number(hourly.wind_direction_10m?.[index]),
      code: Number(hourly.weather_code?.[index]),
      visibilityKm: Number(hourly.visibility?.[index]) / 1000,
    });
  }
  if (!windScenarios.length) {
    const hourly = spot?.hourly ?? {};
    const speed = Number(hourly.wind_speed_10m?.[index]);
    const gust = Number(hourly.wind_gusts_10m?.[index]);
    if (Number.isFinite(speed) && Number.isFinite(gust)) {
      windScenarios.push({
        source: spot?.forecast_primary?.model ?? 'primaire',
        speed,
        gust,
        gustDelta: gust - speed,
        direction: Number(hourly.wind_direction_10m?.[index]),
        code: Number(hourly.weather_code?.[index]),
        visibilityKm: Number(hourly.visibility?.[index]) / 1000,
      });
    }
  }

  const waveScenarios = [];
  for (const [source, payload] of Object.entries(spot?.marine_models ?? {})) {
    const hourly = payload?.hourly ?? {};
    const hs = Number(hourly.wave_height?.[index]);
    const tp = Number(hourly.wave_period?.[index]);
    if (!Number.isFinite(hs)) continue;
    waveScenarios.push({ source, hs, tp: Number.isFinite(tp) ? tp : null });
  }
  if (!waveScenarios.length) {
    const hs = Number(spot?.hourly?.hs?.[index]);
    const tp = Number(spot?.hourly?.tp?.[index]);
    if (Number.isFinite(hs)) {
      waveScenarios.push({ source: 'primaire', hs, tp: Number.isFinite(tp) ? tp : null });
    }
  }

  const speeds = windScenarios.map((s) => s.speed);
  const gusts = windScenarios.map((s) => s.gust);
  const visibilities = windScenarios.map((s) => s.visibilityKm).filter(Number.isFinite);
  const heights = waveScenarios.map((s) => s.hs);

  return {
    index,
    time: spot?.hourly?.time?.[index] ?? null,
    windScenarios,
    waveScenarios,
    maxSpeed: speeds.length ? Math.max(...speeds) : null,
    minSpeed: speeds.length ? Math.min(...speeds) : null,
    maxGust: gusts.length ? Math.max(...gusts) : null,
    minVis: visibilities.length ? Math.min(...visibilities) : null,
    hs: heights.length ? Math.max(...heights) : null,
    codes: windScenarios.map((s) => s.code).filter(Number.isFinite),
    anyOnshore: windScenarios.some((s) => isOnshore(s.direction, sectors)),
    spreadSpeed: speeds.length ? Math.max(...speeds) - Math.min(...speeds) : 0,
    spreadHs: heights.length ? Math.max(...heights) - Math.min(...heights) : 0,
  };
}

export function hardReasons(m, th) {
  const reasons = [];
  if (m.maxSpeed === null || m.maxGust === null) reasons.push('vent_inconnu');
  const validWaves = m.waveScenarios.filter((s) => s.tp !== null);
  if (!validWaves.length) reasons.push('vagues_inconnues');
  if (m.codes.some((code) => th.thunderCodes.includes(code))) reasons.push('orages');
  if (m.minVis !== null && m.minVis < th.visMinKm) reasons.push(`vis<${th.visMinKm}km`);
  if (m.maxGust !== null && m.maxGust >= th.gustNoGoMin) reasons.push(`rafales>=${th.gustNoGoMin}`);
  if (m.maxSpeed !== null && m.maxSpeed >= th.windNoGoMin) reasons.push(`vent>=${th.windNoGoMin}`);
  if (m.windScenarios.some((s) => s.gustDelta >= th.squallDelta)) reasons.push('squalls');
  if (m.hs !== null && m.hs > th.hsNoGoMin) reasons.push(`Hs>${th.hsNoGoMin}`);
  if (validWaves.some((s) => s.hs >= th.shortSteep2Hs && s.tp <= th.shortSteep2Tp)) {
    reasons.push('short_steep_hard');
  }
  return reasons;
}

function waveReasons(m, th) {
  const scenarios = m.waveScenarios.filter((s) => s.tp !== null);
  if (!scenarios.length) return ['vagues_inconnues'];
  const reasons = [];
  const push = (reason) => {
    if (!reasons.includes(reason)) reasons.push(reason);
  };
  for (const { hs, tp } of scenarios) {
    if (hs >= th.hsFamilyMax) push(`Hs>=${th.hsFamilyMax}`);
    else if (hs < 0.4 && tp < th.tpMinAtLt04) push(`Tp<${th.tpMinAtLt04}@Hs<0.4`);
    else if (hs >= 0.4 && hs < 0.5 && tp < th.tpMinAt0405) push(`Tp<${th.tpMinAt0405}@Hs0.4-0.5`);
    if (hs >= th.shortSteep1Hs && tp <= th.shortSteep1Tp) push('short_steep');
  }
  return reasons;
}

export function familyReasons(m, th) {
  const reasons = [];
  if (m.maxSpeed !== null && m.anyOnshore && m.maxSpeed > th.onshoreMaxOk) {
    reasons.push(`onshore>${th.onshoreMaxOk}`);
  }
  if (m.maxSpeed !== null && m.maxSpeed >= th.windFamilyMax) reasons.push(`vent>=${th.windFamilyMax}`);
  reasons.push(...waveReasons(m, th));
  return reasons;
}

export function prudentReasons(m, th) {
  const reasons = [];
  if (m.anyOnshore) reasons.push('prudent_onshore');
  if (m.maxSpeed !== null && m.maxSpeed > th.prudentWindMax) reasons.push(`vent>${th.prudentWindMax}@prudent`);
  if (m.maxGust !== null && m.maxGust >= th.prudentGustMax) reasons.push(`rafales>=${th.prudentGustMax}@prudent`);
  const scenarios = m.waveScenarios.filter((s) => s.tp !== null);
  if (scenarios.some((s) => s.hs > th.prudentHsMax)) reasons.push(`Hs>${th.prudentHsMax}@prudent`);
  if (scenarios.some((s) => s.tp < th.prudentTpMin)) reasons.push(`Tp<${th.prudentTpMin}@prudent`);
  return reasons;
}

export function hourInFamilyRange(time, th) {
  const match = HOUR_RE.exec(String(time ?? ''));
  if (!match) return true;
  const hour = Number(match[1]);
  return hour >= th.familyStartHour && hour < th.familyEndHour;
}

/**
 * @returns {{state: 'go'|'prudent'|'nogo', hard: boolean, reasons: string[], metrics: object, daylight: boolean}}
 */
export function classifyHour(spot, index, sectors, th) {
  const metrics = metricsAtHour(spot, index, sectors);
  const daylight = hourInFamilyRange(metrics.time, th);
  const hard = hardReasons(metrics, th);
  if (hard.length) {
    return {
      state: 'nogo', hard: true, reasons: hard, family: hard, metrics, daylight,
    };
  }
  const family = familyReasons(metrics, th);
  if (!family.length) {
    return {
      state: 'go', hard: false, reasons: [], family: [], metrics, daylight,
    };
  }
  if (th.prudentEnabled) {
    const prudent = prudentReasons(metrics, th);
    if (!prudent.length) {
      return {
        state: 'prudent', hard: false, reasons: family, family, metrics, daylight,
      };
    }
    return {
      state: 'nogo', hard: false, reasons: prudent, family, metrics, daylight,
    };
  }
  return {
    state: 'nogo', hard: false, reasons: family, family, metrics, daylight,
  };
}

export function classifySeries(spot, sectors, th) {
  const times = spot?.hourly?.time ?? [];
  return times.map((_, index) => classifyHour(spot, index, sectors, th));
}
