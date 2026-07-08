/* reasons-debug.js - FABLE "first failing reason" helper */
window.FABLE = window.FABLE || {};
(function (NS) {
  const DEFAULT_RULES = {
    family_hours_local: { start_h: 8, end_h: 21 },
    wind: { family_max_kmh: 20, nogo_min_kmh: 25, onshore_degrade_kmh: 22 },
    sea: { family_max_hs_m: 0.5, nogo_min_hs_m: 0.8 },
    waves: { tp_min_at_hs_lt_0_4_s: 3.2, tp_min_at_hs_0_4_0_5_s: 4.5 },
    combined: { short_steep: { downgrade: { hs_min_m: 0.5, tp_max_s: 6.0 }, hard_nogo: { hs_min_m: 0.6, tp_max_s: 5.0 } } },
    anchor: { hs_ease_max_m: 0.35, tp_family_min_s: 3.2, gust_allow_kmh: 34, squall_delta_max_kmh: 20, sustained_allow_kmh: 32 },
    overrides: {
      gusts_hard_nogo_kmh: 30,
      squall_delta_kmh: 17,
      thunder_wmo: [95, 96, 99],
      visibility_km_min: 5,
    },
    corridor: { minHours: 4, maxHours: 6 },
  };

  const rulesState = JSON.parse(JSON.stringify(DEFAULT_RULES));
  const siteRanges = new Map();
  const siteMeta = new Map();
  let homePath = "gammarth-port.json";
  const KM_PER_NM = 1.852;

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
    const shortSteep = family.combined?.short_steep || {};
    const anchor = family.anchor_sheltered?.waves || {};
    const shelterAnchor = family.shelter_bonus?.anchor || {};

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
    rulesState.waves = {
      tp_min_at_hs_lt_0_4_s: Number(waves.tp_min_at_hs_lt_0_4_s ?? rulesState.waves.tp_min_at_hs_lt_0_4_s),
      tp_min_at_hs_0_4_0_5_s: Number(waves.tp_min_at_hs_0_4_0_5_s ?? rulesState.waves.tp_min_at_hs_0_4_0_5_s),
    };
    rulesState.combined = {
      short_steep: {
        downgrade: {
          hs_min_m: Number(shortSteep?.downgrade?.hs_min_m ?? rulesState.combined.short_steep.downgrade.hs_min_m),
          tp_max_s: Number(shortSteep?.downgrade?.tp_max_s ?? rulesState.combined.short_steep.downgrade.tp_max_s),
        },
        hard_nogo: {
          hs_min_m: Number(shortSteep?.hard_nogo?.hs_min_m ?? rulesState.combined.short_steep.hard_nogo.hs_min_m),
          tp_max_s: Number(shortSteep?.hard_nogo?.tp_max_s ?? rulesState.combined.short_steep.hard_nogo.tp_max_s),
        },
      },
    };
    rulesState.anchor = {
      hs_ease_max_m: Number(anchor.hs_max_m ?? rulesState.anchor.hs_ease_max_m),
      tp_family_min_s: Number(anchor.hs_le_0_35_family_tp_s ?? rulesState.anchor.tp_family_min_s),
      gust_allow_kmh: Number(shelterAnchor.gusts_allow_up_to_kmh ?? rulesState.anchor.gust_allow_kmh),
      squall_delta_max_kmh: Number(shelterAnchor.squall_delta_max_kmh ?? rulesState.anchor.squall_delta_max_kmh),
      sustained_allow_kmh: Number(shelterAnchor.sustained_allow_up_to_kmh ?? rulesState.anchor.sustained_allow_kmh),
    };
    rulesState.overrides = {
      gusts_hard_nogo_kmh: Number(gusts.no_go_min_kmh ?? rulesState.overrides.gusts_hard_nogo_kmh),
      squall_delta_kmh: Number(gusts.squall_delta_kmh ?? rulesState.overrides.squall_delta_kmh),
      thunder_wmo: Array.isArray(family.thunder_codes) ? family.thunder_codes : rulesState.overrides.thunder_wmo,
      visibility_km_min: Number(thresholds.visibility_km_min ?? rulesState.overrides.visibility_km_min),
    };
    rulesState.corridor = {
      minHours: Number(family.window_hours?.min ?? rulesState.corridor.minHours),
      maxHours: Number(family.window_hours?.max ?? rulesState.corridor.maxHours),
    };
  }

  function applySitesNormalized(normalized) {
    if (!normalized || !Array.isArray(normalized.sites)) return;
    siteRanges.clear();
    siteMeta.clear();
    homePath = normalized.home ? `${String(normalized.home).replace(/\.json$/i, "")}.json` : homePath;
    normalized.sites.forEach((site) => {
      const ranges = Array.isArray(site?.onshore_sectors) ? site.onshore_sectors : [[20, 160]];
      const path = String(site?.path || "");
      const slug = path.replace(/\.json$/i, "");
      const meta = {
        path,
        slug,
        name: String(site?.name || path || slug),
        lat: Number(site?.lat),
        lon: Number(site?.lon),
        route_origin: site?.route_origin ? `${String(site.route_origin).replace(/\.json$/i, "")}.json` : null,
        route_points: Array.isArray(site?.route_points) ? site.route_points : [],
        transit_speed_kts: site?.transit_speed_kts || null,
        windows_enabled: site?.windows_enabled !== false,
        beta: Boolean(site?.beta),
        route_kind: String(site?.route_kind || "standard"),
      };
      if (path) siteRanges.set(path.toLowerCase(), ranges);
      if (slug) siteRanges.set(slug.toLowerCase(), ranges);
      if (path) siteMeta.set(path.toLowerCase(), meta);
      if (slug) siteMeta.set(slug.toLowerCase(), meta);
    });
  }

  function windowsEnabled(path) {
    return siteMeta.get(String(path || "").toLowerCase())?.windows_enabled !== false;
  }

  function siteRecord(pathOrSlug) {
    const key = String(pathOrSlug || "").replace(/\.json$/i, "").toLowerCase();
    return siteMeta.get(`${key}.json`) || siteMeta.get(key) || null;
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
      tp: hourly.tp || hourly.wave_period || null,
      wcode: hourly.weather_code || null,
      vis_km: Array.isArray(hourly.visibility) ? hourly.visibility.map(visToKm) : null,
    };
  }

  function toSlug(value) {
    return String(value || "")
      .normalize("NFD")
      .replace(/\p{Diacritic}/gu, "")
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-+|-+$/g, "");
  }

  const toRad = (d) => (Number(d) || 0) * Math.PI / 180;
  function distKm(a, b) {
    const latA = Number(a?.lat), latB = Number(b?.lat);
    const lonA = Number(a?.lon), lonB = Number(b?.lon);
    if (![latA, latB, lonA, lonB].every(Number.isFinite)) return 0;
    const dLat = toRad(latB - latA);
    const dLon = toRad(lonB - lonA);
    const la1 = toRad(latA), la2 = toRad(latB);
    const x = Math.sin(dLat / 2) ** 2 + Math.cos(la1) * Math.cos(la2) * Math.sin(dLon / 2) ** 2;
    return 6371 * 2 * Math.asin(Math.sqrt(x));
  }

  function pathDistanceKm(points) {
    if (!Array.isArray(points) || points.length < 2) return 0;
    let total = 0;
    for (let i = 1; i < points.length; i++) total += distKm(points[i - 1], points[i]);
    return total;
  }

  function normalizeSpeedRange(range) {
    const rawMin = Number(range?.min ?? 16);
    const rawMax = Number(range?.max ?? 24);
    const min = Number.isFinite(rawMin) && rawMin > 0 ? rawMin : 16;
    const max = Number.isFinite(rawMax) && rawMax > 0 ? rawMax : 24;
    return { min: Math.min(min, max), max: Math.max(min, max) };
  }

  function routeDistanceKm(origin, dest, points = []) {
    const all = [{ lat: origin?.lat, lon: origin?.lon }, ...(points || []).map((p) => ({ lat: p?.lat, lon: p?.lon })), { lat: dest?.lat, lon: dest?.lon }];
    return pathDistanceKm(all);
  }

  function routeTransitProfile(origin, dest, points = []) {
    const speed = normalizeSpeedRange(dest?.transit_speed_kts);
    const distanceNm = routeDistanceKm(origin, dest, points) / KM_PER_NM;
    return { min: distanceNm / speed.max, max: distanceNm / speed.min };
  }

  function addHoursISO(iso, hours) {
    return new Date(new Date(iso).getTime() + hours * 3600 * 1000).toISOString();
  }

  function allFamilyHours(times, i0, i1, tz) {
    const startM = rulesState.family_hours_local.start_h * 60;
    const endM = rulesState.family_hours_local.end_h * 60;
    for (let i = i0; i <= i1; i++) {
      const mm = minutesLocal(times[i], tz);
      if (mm == null || mm < startM || mm >= endM) return false;
    }
    return true;
  }

  function resolveRoutePath(point) {
    const bySlug = point?.slug ? siteRecord(point.slug) : null;
    if (bySlug?.path) return bySlug.path;
    const byName = point?.name ? siteRecord(toSlug(point.name)) : null;
    if (byName?.path) return byName.path;
    const lat = Number(point?.lat), lon = Number(point?.lon);
    if (!Number.isFinite(lat) || !Number.isFinite(lon)) return null;
    for (const candidate of new Set(siteMeta.values())) {
      if (Math.abs(Number(candidate?.lat) - lat) < 0.02 && Math.abs(Number(candidate?.lon) - lon) < 0.02) return candidate.path;
    }
    return null;
  }

  function routePathList(originPath, destPath) {
    const origin = siteRecord(originPath);
    const dest = siteRecord(destPath);
    if (!origin || !dest) return [];
    const list = [origin.path];
    (dest.route_points || []).forEach((point) => {
      const path = resolveRoutePath(point);
      if (path && !list.includes(path)) list.push(path);
    });
    if (!list.includes(dest.path)) list.push(dest.path);
    return list;
  }

  function routeLabelFromPaths(paths) {
    return paths.map((path) => siteRecord(path)?.name || path).join(" → ");
  }

  function phaseLabels(length) {
    if (length < 4) return Array.from({ length }, () => "transit");
    if (length === 4) return ["transit", "anchor", "anchor", "transit"];
    if (length === 5) return ["transit", "anchor", "anchor", "anchor", "transit"];
    return ["transit", ...Array.from({ length: Math.max(0, length - 2) }, () => "anchor"), "transit"];
  }

  function wavesOkTransit(hs, tp, reasons) {
    if (hs == null || tp == null) {
      reasons.push("vagues inconnues");
      return false;
    }
    if (hs > rulesState.sea.nogo_min_hs_m) reasons.push(`vagues ${Number(hs).toFixed(2)} > ${rulesState.sea.nogo_min_hs_m} m`);
    if (hs >= rulesState.sea.family_max_hs_m) reasons.push(`vagues ${Number(hs).toFixed(2)} ≥ ${rulesState.sea.family_max_hs_m} m`);
    else {
      if (hs < 0.4 && tp < rulesState.waves.tp_min_at_hs_lt_0_4_s) reasons.push(`Tp ${Number(tp).toFixed(1)} < ${rulesState.waves.tp_min_at_hs_lt_0_4_s} s`);
      if (hs >= 0.4 && hs < 0.5 && tp < rulesState.waves.tp_min_at_hs_0_4_0_5_s) reasons.push(`Tp ${Number(tp).toFixed(1)} < ${rulesState.waves.tp_min_at_hs_0_4_0_5_s} s`);
    }
    if (hs >= rulesState.combined.short_steep.downgrade.hs_min_m && tp <= rulesState.combined.short_steep.downgrade.tp_max_s) reasons.push("mer courte et raide");
    if (hs >= rulesState.combined.short_steep.hard_nogo.hs_min_m && tp <= rulesState.combined.short_steep.hard_nogo.tp_max_s) reasons.push("mer courte et raide (dur)");
    return reasons.length === 0;
  }

  function wavesOkAnchor(hs, tp, reasons) {
    if (hs == null || tp == null) {
      reasons.push("vagues inconnues");
      return false;
    }
    if (hs <= rulesState.anchor.hs_ease_max_m) {
      if (tp < rulesState.anchor.tp_family_min_s) reasons.push(`Tp ${Number(tp).toFixed(1)} < ${rulesState.anchor.tp_family_min_s} s au mouillage`);
      return reasons.length === 0;
    }
    return wavesOkTransit(hs, tp, reasons);
  }

  function evaluateHour(series, idx, phase, slugOrFile) {
    const ws = series.wind?.[idx];
    const gu = series.gusts?.[idx];
    const wd = series.wind_dir?.[idx];
    const hs = series.hs?.[idx];
    const tp = series.tp?.[idx];
    const wc = series.wcode?.[idx];
    const vk = series.vis_km?.[idx];
    const reasons = [];
    const ranges = onshoreRanges(slugOrFile);

    if (wc != null && rulesState.overrides.thunder_wmo.includes(Number(wc))) reasons.push(`orages (code ${wc})`);
    if (vk != null && vk < rulesState.overrides.visibility_km_min) reasons.push(`vis<${rulesState.overrides.visibility_km_min}km`);
    if (typeof ws === "number" && typeof wd === "number" && angleInRanges(wd, ranges) && ws > rulesState.wind.onshore_degrade_kmh) reasons.push(`vent onshore ${Math.round(ws)} ≥ ${rulesState.wind.onshore_degrade_kmh} km/h`);
    if (typeof gu === "number" && typeof ws === "number") {
      const delta = gu - ws;
      if (phase === "anchor") {
        if (delta >= rulesState.anchor.squall_delta_max_kmh) reasons.push(`squalls Δ≥${rulesState.anchor.squall_delta_max_kmh}`);
      } else if (delta >= rulesState.overrides.squall_delta_kmh) reasons.push(`squalls Δ≥${rulesState.overrides.squall_delta_kmh}`);
    }

    if (phase === "anchor") {
      if (typeof gu === "number" && gu >= rulesState.anchor.gust_allow_kmh) reasons.push(`rafales ${Math.round(gu)} ≥ ${rulesState.anchor.gust_allow_kmh} km/h au mouillage`);
      if (typeof ws === "number" && ws >= rulesState.anchor.sustained_allow_kmh) reasons.push(`vent ${Math.round(ws)} ≥ ${rulesState.anchor.sustained_allow_kmh} km/h au mouillage`);
      wavesOkAnchor(hs, tp, reasons);
    } else {
      if (typeof gu === "number" && gu >= rulesState.overrides.gusts_hard_nogo_kmh) reasons.push(`rafales ${Math.round(gu)} ≥ ${rulesState.overrides.gusts_hard_nogo_kmh} km/h`);
      if (typeof ws === "number" && ws >= rulesState.wind.nogo_min_kmh) reasons.push(`vent ${Math.round(ws)} ≥ ${rulesState.wind.nogo_min_kmh} km/h`);
      if (typeof ws === "number" && ws >= rulesState.wind.family_max_kmh) reasons.push(`vent ${Math.round(ws)} ≥ ${rulesState.wind.family_max_kmh} km/h`);
      wavesOkTransit(hs, tp, reasons);
    }
    return { ok: reasons.length === 0, reason: reasons[0] || null };
  }

  function firstTransferFailure(paths, seriesByPath, i0, i1) {
    for (const path of paths) {
      const series = seriesByPath.get(path);
      if (!series?.time?.length) return `${siteRecord(path)?.name || path} — données manquantes`;
      for (let idx = i0; idx <= i1; idx++) {
        const result = evaluateHour(series, idx, "transit", path);
        if (!result.ok) return `${siteRecord(path)?.name || path} — ${result.reason} à ${series.time[idx]}`;
      }
    }
    return null;
  }

  function firstOffshoreFailure(relayPath, destPath, relaySeries, destSeries, i0, end) {
    const relayStart = evaluateHour(relaySeries, i0, "transit", relayPath);
    if (!relayStart.ok) return `${siteRecord(relayPath)?.name || relayPath} — ${relayStart.reason} à ${relaySeries.time[i0]}`;
    const destStart = evaluateHour(destSeries, i0, "transit", destPath);
    if (!destStart.ok) return `${siteRecord(destPath)?.name || destPath} — ${destStart.reason} à ${destSeries.time[i0]}`;
    const phases = phaseLabels(end - i0);
    for (let idx = i0; idx < end; idx++) {
      const result = evaluateHour(destSeries, idx, phases[idx - i0] || "transit", destPath);
      if (!result.ok) return `${siteRecord(destPath)?.name || destPath} — ${result.reason} à ${destSeries.time[idx]}`;
    }
    const relayEnd = evaluateHour(relaySeries, end - 1, "transit", relayPath);
    if (!relayEnd.ok) return `${siteRecord(relayPath)?.name || relayPath} — ${relayEnd.reason} à ${relaySeries.time[end - 1]}`;
    return null;
  }

  function detectTransferWindowsComposite(originPath, relayPath, seriesByPath) {
    const origin = siteRecord(originPath);
    const relay = siteRecord(relayPath);
    if (!origin || !relay) return { windows: [], firstFail: "sites du relais introuvables", route: [] };
    const route = routePathList(originPath, relayPath);
    const seriesOrigin = seriesByPath.get(originPath);
    const profile = routeTransitProfile(origin, relay, relay.route_points || []);
    const spanHours = Math.max(1, Math.ceil(profile.max));
    const lengths = route.map((path) => seriesByPath.get(path)?.time?.length || 0).filter(Boolean);
    const n = lengths.length ? Math.min(...lengths) : 0;
    const windows = [];
    let firstFail = null;
    for (let i = 0; i + spanHours <= n; i++) {
      const j = i + spanHours - 1;
      const failure = firstTransferFailure(route, seriesByPath, i, j);
      if (!failure) {
        const start = seriesOrigin.time[i];
        windows.push({
          start,
          arrival_earliest: addHoursISO(start, profile.min),
          arrival_latest: addHoursISO(start, profile.max),
          category: allFamilyHours(seriesOrigin.time, i, j, null) ? "family" : "off_hours",
          hours: { min: profile.min, max: profile.max },
        });
      } else if (!firstFail) firstFail = failure;
    }
    return { windows, firstFail: firstFail || "aucun créneau de transfert valide", route };
  }

  function detectOffshoreWindowsComposite(relayPath, destPath, seriesByPath) {
    const relaySeries = seriesByPath.get(relayPath);
    const destSeries = seriesByPath.get(destPath);
    const route = routePathList(relayPath, destPath);
    if (!relaySeries?.time?.length || !destSeries?.time?.length) return { windows: [], firstFail: "données offshore manquantes", route };
    const minHours = Math.max(4, Number(rulesState.corridor.minHours || 4));
    const maxHours = Math.max(minHours, Number(rulesState.corridor.maxHours || 6));
    const n = Math.min(relaySeries.time.length, destSeries.time.length);
    const windows = [];
    let firstFail = null;
    for (let i = 0; i < n; i++) {
      let bestEnd = i;
      for (let end = i + 1; end <= n && (end - i) <= maxHours; end++) {
        if ((end - i) < minHours) continue;
        const failure = firstOffshoreFailure(relayPath, destPath, relaySeries, destSeries, i, end);
        if (failure) {
          if (!firstFail) firstFail = failure;
          break;
        }
        bestEnd = end;
      }
      if (bestEnd - i >= minHours) {
        windows.push({
          start: destSeries.time[i],
          end: addHoursISO(destSeries.time[bestEnd - 1], 1),
          category: allFamilyHours(destSeries.time, i, bestEnd - 1, null) ? "family" : "off_hours",
        });
        i = bestEnd - 1;
      }
    }
    return { windows, firstFail: firstFail || `aucune fenêtre de ${minHours}h détectée`, route };
  }

  function buildCompositeRow(destPath, seriesByPath) {
    const dest = siteRecord(destPath);
    const relayPath = dest?.route_origin;
    const relay = siteRecord(relayPath);
    const home = siteRecord(homePath);
    if (!dest || !relay || !home) return null;

    const transfer = detectTransferWindowsComposite(home.path, relay.path, seriesByPath);
    const offshore = detectOffshoreWindowsComposite(relay.path, dest.path, seriesByPath);
    const transferRouteLabel = routeLabelFromPaths(transfer.route);
    const offshoreRouteLabel = routeLabelFromPaths(offshore.route);
    const transferHasFamily = transfer.windows.some((window) => window.category === "family");
    const offshoreHasFamily = offshore.windows.some((window) => window.category === "family");
    const transferStatus = transfer.windows.length ? (transferHasFamily ? "ok" : "off_hours") : "blocked";
    const offshoreStatus = offshore.windows.length ? (offshoreHasFamily ? "ok" : "off_hours") : (transfer.windows.length ? "blocked" : "waiting");

    let alignment = { status: "waiting", reason: "en attente de validation des deux étapes" };
    let compositeOk = false;
    if (transfer.windows.length && offshore.windows.length) {
      const compatible = [];
      offshore.windows.forEach((offshoreWindow) => {
        const offshoreStart = new Date(offshoreWindow.start).getTime();
        transfer.windows.forEach((transferWindow) => {
          if (new Date(transferWindow.arrival_latest).getTime() <= offshoreStart) compatible.push({ transferWindow, offshoreWindow });
        });
      });
      if (compatible.length) {
        compositeOk = true;
        const allFamily = compatible.some(({ transferWindow, offshoreWindow }) => transferWindow.category === "family" && offshoreWindow.category === "family");
        alignment = { status: allFamily ? "ok" : "off_hours", reason: allFamily ? "fenêtre composite disponible" : "fenêtre composite disponible hors horaires" };
      } else {
        const latestArrival = transfer.windows.map((window) => window.arrival_latest).sort().at(-1);
        const earliestOffshore = offshore.windows.map((window) => window.start).sort().at(0);
        alignment = {
          status: "blocked",
          reason: `alignement impossible · arrivée relai ${latestArrival || "—"} > fenêtre offshore ${earliestOffshore || "—"}`,
        };
      }
    } else if (!transfer.windows.length) {
      alignment = { status: "waiting", reason: "étape 1 à valider d’abord" };
    } else if (!offshore.windows.length) {
      alignment = { status: "waiting", reason: "étape 2 à valider d’abord" };
    }

    const summary = compositeOk
      ? (alignment.status === "ok" ? "✓ GO composite possible" : "✓ GO composite possible hors horaires")
      : !transfer.windows.length
        ? "✗ Étape 1 bloquée"
        : !offshore.windows.length
          ? "✗ Étape 2 bloquée"
          : "✗ Alignement composite impossible";
    const severity = compositeOk ? "ok" : (alignment.status === "blocked" || !transfer.windows.length || !offshore.windows.length ? "bad" : "warn");

    return {
      spot: `${dest.name} (${dest.path})`,
      family: summary,
      note: dest.route_kind === "composite_beta" ? "Diagnostic composite par étape activé" : "",
      composite: {
        severity,
        summary: summary.replace(/^[✗✓]\s*/, ""),
        step1: {
          title: "Étape 1",
          status: transferStatus,
          route: transferRouteLabel,
          reason: transfer.windows.length ? (transferHasFamily ? "GO disponible" : "GO disponible hors horaires") : transfer.firstFail,
        },
        step2: {
          title: "Étape 2",
          status: offshoreStatus,
          route: offshoreRouteLabel,
          reason: offshore.windows.length ? (offshoreHasFamily ? "GO disponible" : "GO disponible hors horaires") : (transfer.windows.length ? offshore.firstFail : "en attente de validation de l’étape 1"),
        },
        alignment,
      },
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

  async function loadSpot(path, preloaded = null) {
    if (preloaded && preloaded[path]) return preloaded[path];
    return loadJSON(path);
  }

  NS.debugReasons = async function debugReasons(paths, options = {}) {
    await ensureConfig(options);
    const defaultPaths = Array.from(siteRanges.keys()).filter((key) => key.endsWith(".json") && windowsEnabled(key));
    const requested = paths && paths.length ? paths : defaultPaths;
    const list = requested.filter((path) => windowsEnabled(path));
    const rows = [];
    const preloaded = options.preloadedSpots || null;
    const seriesByPath = new Map();

    for (const path of list) {
      const spot = await loadSpot(path, preloaded);
      if (spot) seriesByPath.set(path, toSeries(spot));
    }

    for (const path of list) {
      const record = siteRecord(path);
      if (record?.route_kind === "composite_beta" && record?.route_origin) {
        const row = buildCompositeRow(path, seriesByPath);
        if (row) {
          rows.push(row);
          continue;
        }
      }
      const spot = await loadSpot(path, preloaded);
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
