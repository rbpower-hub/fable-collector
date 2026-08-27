import {
  getNavigationWindowsForDay,
  isLongTripNavigationWindow,
  navigationWindowBreakdown,
  tunisNavigationDateKey,
} from './navigation-windows.js';

const CONFIDENCE_RANK = {high: 3, medium: 2, low: 1};

export function freshnessState(status, now = new Date()) {
  const current = now instanceof Date ? now : new Date(now);
  const cadence = Number(status?.cadence_minutes);
  const limit_min = Number.isFinite(cadence) && cadence > 0 ? cadence + 35 : 95;
  const generated = status?.generated_at ? new Date(status.generated_at) : null;
  const age_min = generated && Number.isFinite(generated.getTime())
    ? Math.max(0, (current.getTime() - generated.getTime()) / 60000)
    : Infinity;
  return {fresh: Number.isFinite(age_min) && age_min <= limit_min, age_min, limit_min};
}

function confidenceRank(row) {
  const value = row?.windowItem?.confidence || row?.destination?.confidence;
  return CONFIDENCE_RANK[String(value || '').toLowerCase()] || 0;
}

function distanceProxy(row) {
  return Number(
    row?.windowItem?.distance_nm
    ?? row?.destination?.distance_nm
    ?? row?.destination?.required_hours
    ?? Infinity
  );
}

function familyTier(row) {
  return String(row?.windowItem?.family_tier || row?.destination?.family_tier || '').toLowerCase();
}

function isBetaOrOffshore(row) {
  const item = row?.windowItem || {};
  const destination = row?.destination || {};
  const routeKind = String(item.route_kind || destination.route_kind || '').toLowerCase();
  return Boolean(item.beta || destination.beta)
    || routeKind.includes('composite')
    || routeKind.includes('offshore');
}

function isStillActionable(row, selectedDay, now, rules) {
  const start = new Date(row?.windowItem?.start || '');
  const end = new Date(row?.windowItem?.end || '');
  if (!Number.isFinite(start.getTime()) || !Number.isFinite(end.getTime())) return false;
  const today = tunisNavigationDateKey(now);
  if (selectedDay !== today) return true;
  const publishedRequiredHours = Number(
    row?.windowItem?.required_hours ?? row?.destination?.required_hours
  );
  const fallbackHours = Number(rules?.window_hours?.min || 4);
  const requiredHours = Number.isFinite(publishedRequiredHours) && publishedRequiredHours > 0
    ? publishedRequiredHours : fallbackHours;
  const effectiveDeparture = Math.max(now.getTime(), start.getTime());
  return end.getTime() >= effectiveDeparture + requiredHours * 3600000;
}

function sortFamilyRows(rows) {
  return [...rows].sort((a, b) => {
    const prudentA = familyTier(a) === 'prudent' ? 1 : 0;
    const prudentB = familyTier(b) === 'prudent' ? 1 : 0;
    return prudentA - prudentB
      || new Date(a.windowItem.start) - new Date(b.windowItem.start)
      || confidenceRank(b) - confidenceRank(a)
      || distanceProxy(a) - distanceProxy(b);
  });
}

function diagnosticForDay(destination, selectedDay) {
  const daily = destination?.daily_diagnostics;
  if (daily && typeof daily === 'object') {
    const record = Array.isArray(daily)
      ? daily.find((item) => item?.date === selectedDay)
      : daily[selectedDay];
    if (record) return record;
  }
  const diagnostics = destination?.diagnostics || null;
  const blockerDay = tunisNavigationDateKey(diagnostics?.first_blocker?.time);
  if (!blockerDay || blockerDay === selectedDay) return diagnostics;
  return null;
}

function nearestBlocker(windows, selectedDay) {
  return (windows?.windows || [])
    .map((destination) => ({
      destination,
      diagnostics: diagnosticForDay(destination, selectedDay),
      distance: Number(destination.distance_nm ?? destination.required_hours ?? Infinity),
    }))
    .filter((item) => item.diagnostics)
    .sort((a, b) => a.distance - b.distance)[0] || null;
}

function emptyVerdict(state, selectedDay, args = {}) {
  return {
    state,
    selected_day: selectedDay,
    spot: null,
    window: null,
    row: null,
    rows: [],
    family_rows: [],
    off_hours_rows: [],
    watch_rows: [],
    long_trip_rows: [],
    counts: {strict:0, prudent:0, offHours:0, watch:0, family:0, longTrip:0, total:0},
    message_key: state.toLowerCase(),
    args,
  };
}

export function navigationVerdictForDay({
  windows,
  status,
  selectedDay,
  rules = {},
  now = new Date(),
}) {
  const current = now instanceof Date ? now : new Date(now);
  const day = selectedDay || tunisNavigationDateKey(current);
  const freshness = freshnessState(status, current);
  if (!freshness.fresh) {
    return emptyVerdict('STALE', day, {
      age_min: freshness.age_min,
      limit_min: freshness.limit_min,
    });
  }
  if (!windows || !Array.isArray(windows.windows)) return emptyVerdict('NO_DATA', day);

  const rows = getNavigationWindowsForDay(day, windows, {
    categories:['family', 'off_hours', 'watch'],
  });
  const actionable = rows.filter((row) => (
    isStillActionable(row, day, current, rules)
    && (isLongTripNavigationWindow(row) || !isBetaOrOffshore(row))
  ));
  const familyRows = sortFamilyRows(actionable.filter((row) => (
    row.category === 'family'
    && !isLongTripNavigationWindow(row)
  )));
  const offHoursRows = actionable.filter((row) => (
    row.category === 'off_hours'
    && !isLongTripNavigationWindow(row)
  ));
  const watchRows = actionable.filter((row) => (
    row.category === 'watch'
    && !isLongTripNavigationWindow(row)
    && row.windowItem?.family_go === false
    && row.windowItem?.review_required === true
  ));
  const longTripRows = actionable.filter(isLongTripNavigationWindow);
  const counts = navigationWindowBreakdown(actionable);
  const blocker = nearestBlocker(windows, day);
  const shared = {
    selected_day: day,
    rows: actionable,
    family_rows: familyRows,
    off_hours_rows: offHoursRows,
    watch_rows: watchRows,
    long_trip_rows: longTripRows,
    counts,
    blocker: blocker?.destination || null,
  };

  if (familyRows.length) {
    const row = familyRows[0];
    const prudent = familyTier(row) === 'prudent';
    return {
      ...shared,
      state: prudent ? 'GO_PRUDENT' : 'GO_FAMILY',
      spot: row.destination,
      window: row.windowItem,
      row,
      message_key: prudent ? 'go_prudent' : 'go_family',
      args: {confidence: row.windowItem.confidence || row.destination.confidence || 'low'},
    };
  }
  if (watchRows.length) {
    const row = watchRows[0];
    return {
      ...shared,
      state: 'WATCH',
      spot: row.destination,
      window: row.windowItem,
      row,
      message_key: 'watch',
      args: {count: watchRows.length},
    };
  }
  if (offHoursRows.length) {
    const row = offHoursRows[0];
    return {
      ...shared,
      state: 'OFF_HOURS',
      spot: row.destination,
      window: row.windowItem,
      row,
      message_key: 'off_hours',
      args: {count: offHoursRows.length},
    };
  }
  if (longTripRows.length) {
    const row = longTripRows[0];
    return {
      ...shared,
      state: 'TRAVEL_ONLY',
      spot: row.destination,
      window: row.windowItem,
      row,
      message_key: 'travel_only',
      args: {count: longTripRows.length},
    };
  }

  const diagnostics = blocker?.diagnostics || {};
  return {
    ...shared,
    state: 'NO_GO',
    spot: blocker?.destination || null,
    window: null,
    row: null,
    message_key: 'no_go',
    args: {
      reason_fr: diagnostics.summary_fr || diagnostics.first_blocker?.reason_fr || '',
      reason_en: diagnostics.summary_en || diagnostics.first_blocker?.reason_en || '',
    },
  };
}

if (typeof window !== 'undefined') {
  window.FABLENavigationVerdicts = Object.assign(window.FABLENavigationVerdicts || {}, {
    freshnessState,
    navigationVerdictForDay,
  });
}
