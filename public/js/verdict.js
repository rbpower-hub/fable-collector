const TUNIS_TZ = 'Africa/Tunis';
const CONFIDENCE_RANK = {high: 3, medium: 2, low: 1};

export function freshnessState(status, now = new Date()) {
  const cadence = Number(status?.cadence_minutes);
  const limit_min = Number.isFinite(cadence) && cadence > 0 ? cadence + 35 : 95;
  const generated = status?.generated_at ? new Date(status.generated_at) : null;
  const age_min = generated && Number.isFinite(generated.getTime())
    ? Math.max(0, (now.getTime() - generated.getTime()) / 60000)
    : Infinity;
  return {fresh: Number.isFinite(age_min) && age_min <= limit_min, age_min, limit_min};
}

function tunisDateKey(value) {
  const date = value instanceof Date ? value : new Date(value);
  if (!Number.isFinite(date.getTime())) return '';
  const parts = new Intl.DateTimeFormat('en-CA', {
    timeZone: TUNIS_TZ,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).formatToParts(date).reduce((result, part) => {
    if (part.type !== 'literal') result[part.type] = part.value;
    return result;
  }, {});
  return `${parts.year}-${parts.month}-${parts.day}`;
}

function confidenceRank(value) {
  return CONFIDENCE_RANK[String(value || '').toLowerCase()] || 0;
}

function isFamilyCandidate(destination, windowItem) {
  const category = String(windowItem?.category || destination?.category || 'family').toLowerCase();
  const tripMode = String(windowItem?.trip_mode || destination?.trip_mode || '').toLowerCase();
  const routeKind = String(windowItem?.route_kind || destination?.route_kind || '').toLowerCase();
  const beta = Boolean(windowItem?.beta || destination?.beta);
  if (category !== 'family') return false;
  if (tripMode === 'one_way_multi_day') return false;
  if (beta) return false;
  if (routeKind.includes('composite') || routeKind.includes('offshore')) return false;
  return Boolean(windowItem?.start && windowItem?.end);
}

function remainingDurationIsEnough(windowItem, now, rules) {
  const minHours = Number(rules?.window_hours?.min || 4);
  const end = new Date(windowItem.end);
  if (!Number.isFinite(end.getTime())) return false;
  return end.getTime() >= now.getTime() + minHours * 3600000;
}

function flattenCandidates(windows, now, rules) {
  const rows = [];
  (windows?.windows || []).forEach((destination) => {
    (destination?.windows || []).forEach((windowItem) => {
      if (!isFamilyCandidate(destination, windowItem)) return;
      if (!remainingDurationIsEnough(windowItem, now, rules)) return;
      const start = new Date(windowItem.start);
      const end = new Date(windowItem.end);
      if (!Number.isFinite(start.getTime()) || !Number.isFinite(end.getTime())) return;
      if (end <= now) return;
      rows.push({
        destination,
        windowItem,
        start,
        end,
        confidence: windowItem.confidence || destination.confidence || 'Low',
        distanceProxy: Number(
          windowItem.distance_nm ?? destination.distance_nm ?? destination.required_hours ?? Infinity
        ),
      });
    });
  });
  return rows.sort((a, b) => (
    a.start - b.start ||
    confidenceRank(b.confidence) - confidenceRank(a.confidence) ||
    a.distanceProxy - b.distanceProxy
  ));
}

function nearestBlocker(windows) {
  return (windows?.windows || [])
    .filter((destination) => !(destination?.windows || []).some((item) => isFamilyCandidate(destination, item)))
    .map((destination) => ({
      destination,
      distanceProxy: Number(destination.distance_nm ?? destination.required_hours ?? Infinity),
    }))
    .sort((a, b) => a.distanceProxy - b.distanceProxy)[0]?.destination || null;
}

export function computeVerdict({windows, status, rules = {}, now = new Date()}) {
  const current = now instanceof Date ? now : new Date(now);
  const freshness = freshnessState(status, current);
  if (!freshness.fresh) {
    return {
      state: 'STALE',
      spot: null,
      window: null,
      message_key: 'stale',
      args: {age_min: freshness.age_min, limit_min: freshness.limit_min},
    };
  }

  if (!windows || !Array.isArray(windows.windows)) {
    return {
      state: 'NO_DATA',
      spot: null,
      window: null,
      message_key: 'no_data',
      args: {},
    };
  }

  const candidates = flattenCandidates(windows, current, rules);
  const todayKey = tunisDateKey(current);
  const today = candidates.find((row) => (
    tunisDateKey(row.start) <= todayKey && tunisDateKey(row.end) >= todayKey
  ));
  if (today) {
    return {
      state: 'GO_TODAY',
      spot: today.destination,
      window: today.windowItem,
      message_key: 'go_today',
      args: {confidence: today.confidence},
    };
  }

  const soon = candidates.find((row) => tunisDateKey(row.start) > todayKey);
  if (soon) {
    return {
      state: 'GO_SOON',
      spot: soon.destination,
      window: soon.windowItem,
      message_key: 'go_soon',
      args: {confidence: soon.confidence},
    };
  }

  const blocked = nearestBlocker(windows);
  const diagnostics = blocked?.diagnostics || {};
  return {
    state: 'NO_GO',
    spot: blocked,
    window: null,
    message_key: 'no_go',
    args: {
      reason_fr: diagnostics.summary_fr || diagnostics.first_blocker?.reason_fr || '',
      reason_en: diagnostics.summary_en || diagnostics.first_blocker?.reason_en || '',
    },
  };
}

if (typeof window !== 'undefined') {
  window.FABLEVerdict = Object.assign(window.FABLEVerdict || {}, {
    computeVerdict,
    freshnessState,
  });
}
