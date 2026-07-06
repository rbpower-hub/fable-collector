/* reasons-debug.js - FABLE "first failing reason" helper */
window.FABLE = window.FABLE || {};
(function (NS) {
  const DEFAULT_RULES = {
    family_hours_local: { start_h: 8, end_h: 21 },
    wind: { family_max_kmh: 20, nogo_min_kmh: 25, onshore_degrade_kmh: 22 },
    sea: { family_max_hs_m: 0.5, nogo_min_hs_m: 0.8 },
    overrides: {
      gusts_hard_nogo_kmh: 30,
      squall_delta_kmh: 17,
      thunder_wmo: [95, 96, 99],
      visibility_km_min: 5,
    },
    corridor: { minHours: 4 },
  };

  const rulesState = JSON.parse(JSON.stringify(DEFAULT_RULES));
  const siteRanges = new Map();

  async function loadJSON(path) {
    try {
      const response = await fetch(path, { cache: "no-store" });
      if (!response.ok) throw new Error(response.statusText);
      return await response.json();
    } catch {
      return null;
    }
  }

  function visToKm(value) {
    if (value == null) return null;
    return value > 50 ? value / 1000 : value;
  }

  function applyRulesNormalized(normalized) {
    if (!normalized || !normalized.family) return;
    const family = normalized.family || {};
    const thresholds = family.thresholds || {};
    const wind = thresholds.wind || {};
    const gusts = thresholds.gusts || {};
    const waves = thresholds.waves || {};

    rulesState.family_hours_local = {
      start_h: Number(family.hours_local?.start ?? rulesState.family_hours_local.start_h),
      end_h: Number(family.hours_local?.end ?? rulesState.family_hours_local.end_h),
    };
    rulesState.wind = {
      family_max_kmh: Number(wind.family_max_kmh ?? rulesState.wind.family_max_kmh),
      nogo_min_kmh: Number(wind.no_go_min_kmh ?? rulesState.wind.nogo_min_kmh),
      onshore_degrade_kmh: Number(wind.onshore_downgrade_kmh ?? rulesState.wind.onshore_degrade_kmh),
    };
    rulesState.sea = {
      family_max_hs_m: Number(waves.hs_family_max_m ?? rulesState.sea.family_max_hs_m),
      nogo_min_hs_m: Number(waves.hs_no_go_min_m ?? rulesState.sea.nogo_min_hs_m),
    };
    rulesState.overrides = {
      gusts_hard_nogo_kmh: Number(gusts.no_go_min_kmh ?? rulesState.overrides.gusts_hard_nogo_kmh),
      squall_delta_kmh: Number(gusts.squall_delta_kmh ?? rulesState.overrides.squall_delta_kmh),
      thunder_wmo: Array.isArray(family.thunder_codes) ? family.thunder_codes : rulesState.overrides.thunder_wmo,
      visibility_km_min: Number(thresholds.visibility_km_min ?? rulesState.overrides.visibility_km_min),
    };
    rulesState.corridor = {
      minHours: Number(family.window_hours?.min ?? rulesState.corridor.minHours),
    };
  }

  function applySitesNormalized(normalized) {
    if (!normalized || !Array.isArray(normalized.sites)) return;
    siteRanges.clear();
    normalized.sites.forEach((site) => {
      const ranges = Array.isArray(site?.onshore_sectors) ? site.onshore_sectors : [[20, 160]];
      const path = String(site?.path || "");
      const slug = path.replace(/\.json$/i, "");
      if (path) siteRanges.set(path.toLowerCase(), ranges);
      if (slug) siteRanges.set(slug.toLowerCase(), ranges);
    });
  }

  NS.configure = function configure(options = {}) {
    applyRulesNormalized(options.rulesNormalized);
    applySitesNormalized(options.sitesNormalized);
  };

  async function ensureConfig(options = {}) {
    NS.configure(options);
    if (siteRanges.size > 0) return;
    const [rulesNormalized, sitesNormalized] = await Promise.all([
      loadJSON("rules.normalized.json"),
      loadJSON("sites.normalized.json"),
    ]);
    NS.configure({ rulesNormalized, sitesNormalized });
  }

  function onshoreRanges(slugOrFile) {
    const key = String(slugOrFile || "").replace(/\.json$/i, "").toLowerCase();
    return siteRanges.get(`${key}.json`) || siteRanges.get(key) || [[20, 160]];
  }

  function angleInRanges(angle, ranges) {
    for (const [lo, hi] of ranges) {
      if (lo <= hi) {
        if (angle >= lo && angle <= hi) return true;
      } else if (angle >= lo || angle <= hi) {
        return true;
      }
    }
    return false;
  }

  function minutesLocal(iso, tz) {
    try {
      const d = new Date(iso);
      const s = d.toLocaleTimeString("fr-FR", {
        timeZone: tz || Intl.DateTimeFormat().resolvedOptions().timeZone,
        hour: "2-digit",
        minute: "2-digit",
        hour12: false,
      });
      const [hh, mm] = s.split(":").map((n) => parseInt(n, 10) || 0);
      return hh * 60 + mm;
    } catch {
      return null;
    }
  }

  function toSeries(data) {
    const hourly = data?.hourly || {};
    return {
      time: hourly.time || [],
      wind: hourly.wind_speed_10m || hourly.wind_speed || [],
      gusts: hourly.wind_gusts_10m || hourly.wind_gusts || null,
      wind_dir: hourly.wind_direction_10m || hourly.wind_direction || null,
      hs: hourly.hs || hourly.wave_height || null,
      wcode: hourly.weather_code || null,
      vis_km: Array.isArray(hourly.visibility) ? hourly.visibility.map(visToKm) : null,
    };
  }

  function firstFailForWindow(series, tz, slugOrFile) {
    const windCap = rulesState.wind.family_max_kmh;
    const windHard = rulesState.wind.nogo_min_kmh;
    const hsCap = rulesState.sea.family_max_hs_m;
    const hsHard = rulesState.sea.nogo_min_hs_m;
    const startM = rulesState.family_hours_local.start_h * 60;
    const endM = rulesState.family_hours_local.end_h * 60;
    const segHours = rulesState.corridor.minHours;
    const ranges = onshoreRanges(slugOrFile);
    const N = (series.time || []).length;

    for (let i = 0; i + segHours <= N; i++) {
      let allDay = true;
      for (let k = 0; k < segHours; k++) {
        const mm = minutesLocal(series.time[i + k], tz);
        if (mm == null || mm < startM || mm >= endM) {
          allDay = false;
          break;
        }
      }
      if (!allDay) continue;

      for (let k = 0; k < segHours; k++) {
        const t = series.time[i + k];
        const ws = series.wind?.[i + k];
        const gu = series.gusts?.[i + k];
        const wd = series.wind_dir?.[i + k];
        const hs = series.hs?.[i + k];
        const wc = series.wcode?.[i + k];
        const vk = series.vis_km?.[i + k];

        if (wc != null && rulesState.overrides.thunder_wmo.includes(Number(wc))) {
          return `orages (code ${wc}) à ${t}`;
        }
        if (vk != null && vk < rulesState.overrides.visibility_km_min) {
          return `vis<${rulesState.overrides.visibility_km_min}km à ${t}`;
        }
        if (typeof gu === "number" && gu >= rulesState.overrides.gusts_hard_nogo_kmh) {
          return `rafales≥${rulesState.overrides.gusts_hard_nogo_kmh} km/h à ${t}`;
        }
        if (
          typeof ws === "number" &&
          typeof gu === "number" &&
          gu - ws >= rulesState.overrides.squall_delta_kmh
        ) {
          return `squalls Δ≥${rulesState.overrides.squall_delta_kmh} à ${t}`;
        }
        if (typeof ws === "number" && ws >= windHard) return `vent ${ws} ≥ ${windHard} km/h à ${t}`;
        if (typeof hs === "number" && hs >= hsHard) return `vagues ${hs.toFixed(2)} ≥ ${hsHard} m à ${t}`;

        if (typeof ws === "number" && ws > windCap) {
          if (typeof wd === "number" && angleInRanges(wd, ranges) && ws >= rulesState.wind.onshore_degrade_kmh) {
            return `vent onshore ${ws} ≥ ${rulesState.wind.onshore_degrade_kmh} km/h à ${t}`;
          }
          return `vent ${ws} > ${windCap} km/h à ${t}`;
        }
        if (typeof hs === "number" && hs > hsCap) return `vagues ${hs.toFixed(2)} > ${hsCap} m à ${t}`;
      }
      return null;
    }

    return `aucune fenêtre de ${segHours}h dans ${rulesState.family_hours_local.start_h}:00-${rulesState.family_hours_local.end_h}:00`;
  }

  async function loadSpot(path) {
    return loadJSON(path);
  }

  NS.debugReasons = async function debugReasons(paths, options = {}) {
    await ensureConfig(options);
    const defaultPaths = Array.from(siteRanges.keys()).filter((key) => key.endsWith(".json"));
    const list = paths && paths.length ? paths : defaultPaths;
    const rows = [];

    for (const path of list) {
      const spot = await loadSpot(path);
      if (!spot) {
        rows.push({ spot: path, family: "✗ erreur de lecture", note: "Mode Expert non activé dans le backend" });
        continue;
      }
      const tz = spot?.meta?.tz || null;
      const series = toSeries(spot);
      const famFail = firstFailForWindow(series, tz, spot?.meta?.slug || path);
      rows.push({
        spot: spot?.meta?.name ? `${spot.meta.name} (${path})` : path,
        family: famFail ? `✗ ${famFail}` : "✓ fenêtre possible",
        note: "Mode Expert non activé dans le backend",
      });
    }
    console.table(rows);
    return rows;
  };
})(window.FABLE);
