const TUNIS_TZ = 'Africa/Tunis';
const LONG_TRIP_MODES = new Set(['one_way_multi_day']);
const LONG_ROUTE_KINDS = new Set(['long_trip_one_way', 'offshore_one_way_beta']);

const asArray = (value) => Array.isArray(value) ? value : [];

export function tunisNavigationDateKey(value) {
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

function directionalWindows(destination) {
  const containers = [
    destination,
    destination?.long_trip_one_way,
    destination?.offshore_one_way_beta,
    destination?.offshore,
  ].filter(Boolean);
  return containers.flatMap((container) => [
    ...asArray(container.outbound).map((item) => ({...item, direction:item.direction || 'outbound'})),
    ...asArray(container.outbound_windows).map((item) => ({...item, direction:item.direction || 'outbound'})),
    ...asArray(container.return).map((item) => ({...item, direction:item.direction || 'return'})),
    ...asArray(container.returns).map((item) => ({...item, direction:item.direction || 'return'})),
    ...asArray(container.return_windows).map((item) => ({...item, direction:item.direction || 'return'})),
  ]);
}

export function isLongTripNavigationWindow(row) {
  const item = row?.windowItem || {};
  const destination = row?.destination || {};
  return LONG_TRIP_MODES.has(String(item.trip_mode || destination.trip_mode || ''))
    || LONG_ROUTE_KINDS.has(String(item.route_kind || destination.route_kind || ''));
}

export function getDisplayedNavigationWindows(selectedDay, windowsData) {
  const rows = [];
  asArray(windowsData?.windows).forEach((destination) => {
    const candidates = [...asArray(destination?.windows), ...directionalWindows(destination)];
    candidates.forEach((windowItem) => {
      if (!windowItem?.start || !windowItem?.end) return;
      if (tunisNavigationDateKey(windowItem.start) !== selectedDay) return;
      const category = String(windowItem.category || destination.category || 'family').toLowerCase();
      if (category !== 'family') return;
      rows.push({destination, windowItem});
    });
  });

  const unique = new Map();
  rows.forEach((row) => {
    const destinationKey = row.destination.dest_slug || row.destination.dest_name || '';
    const direction = row.windowItem.direction || (isLongTripNavigationWindow(row) ? 'outbound' : '');
    const key = `${destinationKey}|${direction}|${row.windowItem.start}|${row.windowItem.end}`;
    if (!unique.has(key)) unique.set(key, row);
  });
  return [...unique.values()].sort(
    (a, b) => new Date(a.windowItem.start) - new Date(b.windowItem.start)
  );
}

export function navigationWindowCounts(displayedWindows) {
  const longTrip = displayedWindows.filter(isLongTripNavigationWindow).length;
  return {family: displayedWindows.length - longTrip, longTrip, total:displayedWindows.length};
}

if (typeof window !== 'undefined') {
  window.FABLENavigationWindows = Object.assign(window.FABLENavigationWindows || {}, {
    getDisplayedNavigationWindows,
    isLongTripNavigationWindow,
    navigationWindowCounts,
    tunisNavigationDateKey,
  });
}
