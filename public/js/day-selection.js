const TUNIS_TZ = 'Africa/Tunis';
const STORAGE_KEY = 'fable_selected_day';
const DAY_COUNT = 3;

const state = {
  selectedKey: null,
  recommendations: [],
  windows: null,
  syncScheduled: false,
  originalReasonsHtml: null,
};

const esc = (value) => String(value ?? '').replace(
  /[&<>"']/g,
  (char) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot',"'":'&#39;'}[char])
);

export function tunisDateKey(value) {
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

function offsetDateKey(key, offset) {
  const [year, month, day] = String(key).split('-').map(Number);
  if (![year, month, day].every(Number.isFinite)) return '';
  return new Date(Date.UTC(year, month - 1, day + offset, 12)).toISOString().slice(0, 10);
}

export function planningDayKeys(now = new Date(), count = DAY_COUNT) {
  const first = tunisDateKey(now);
  if (!first) return [];
  return Array.from({length: count}, (_, index) => offsetDateKey(first, index));
}

export function normalizeSelectedDay(candidate, now = new Date()) {
  const keys = planningDayKeys(now);
  return keys.includes(candidate) ? candidate : (keys[0] || '');
}

export function recommendationsForDay(recommendations, selectedKey) {
  return (Array.isArray(recommendations) ? recommendations : []).filter(
    (recommendation) => tunisDateKey(recommendation?.start) === selectedKey
  );
}

function language() {
  const value = (localStorage.getItem('lang') || document.documentElement.lang || 'fr').toLowerCase();
  if (value.startsWith('ar')) return 'ar';
  return value.startsWith('en') ? 'en' : 'fr';
}

function copy() {
  const lang = language();
  if (lang === 'en') return {
    selectDay: 'Select this day',
    selectedDay: 'Selected day',
    activitiesFor: 'Activities for',
    windowsFor: 'Navigation windows for',
    warningsFor: 'NO-GO warnings for',
    noActivities: 'No activity is associated with this day in a validated Family GO window.',
    noSpecialized: 'No specialised activity passed its own comfort limits. A family outing on the water remains possible inside this validated Family GO window.',
    familyOuting: 'Family outing on the water',
    noWindows: 'No navigation window is validated for this selected day.',
    noWarnings: 'No NO-GO warning for the selected day.',
    genericNoGo: 'No Family GO window is validated for this destination on the selected day.',
    offHoursOnly: 'Only an out-of-hours window is available on the selected day.',
    dataUnavailable: 'Selected-day warnings are temporarily unavailable.',
  };
  if (lang === 'ar') return {
    selectDay: 'اختر هذا اليوم',
    selectedDay: 'اليوم المختار',
    activitiesFor: 'أنشطة يوم',
    windowsFor: 'نوافذ الملاحة ليوم',
    warningsFor: 'تحذيرات عدم الخروج ليوم',
    noActivities: 'لا توجد أنشطة مرتبطة بهذا اليوم ضمن نافذة Family GO صالحة.',
    noSpecialized: 'لم يتجاوز أي نشاط متخصص حدود الراحة الخاصة به. تبقى خرجة عائلية على الماء ممكنة داخل نافذة Family GO الصالحة.',
    familyOuting: 'خرجة عائلية على الماء',
    noWindows: 'لا توجد نافذة ملاحة صالحة لليوم المختار.',
    noWarnings: 'لا يوجد تحذير عدم خروج لليوم المختار.',
    genericNoGo: 'لا توجد نافذة Family GO صالحة لهذه الوجهة في اليوم المختار.',
    offHoursOnly: 'توجد فقط نافذة خارج الساعات العائلية في اليوم المختار.',
    dataUnavailable: 'تحذيرات اليوم المختار غير متاحة مؤقتاً.',
  };
  return {
    selectDay: 'Sélectionner cette journée',
    selectedDay: 'Journée sélectionnée',
    activitiesFor: 'Activités du',
    windowsFor: 'Fenêtres de navigation du',
    warningsFor: 'Avertissements NO-GO du',
    noActivities: 'Aucune activité associée à cette journée dans une fenêtre Family GO validée.',
    noSpecialized: 'Aucune activité spécialisée ne passe ses propres limites de confort. Une sortie familiale sur l’eau reste possible dans cette fenêtre Family GO validée.',
    familyOuting: 'Sortie familiale sur l’eau',
    noWindows: 'Aucune fenêtre de navigation validée pour la journée sélectionnée.',
    noWarnings: 'Aucun avertissement NO-GO pour la journée sélectionnée.',
    genericNoGo: 'Aucune fenêtre Family GO validée pour cette destination pendant la journée sélectionnée.',
    offHoursOnly: 'Seule une fenêtre hors horaires familiaux est disponible pendant la journée sélectionnée.',
    dataUnavailable: 'Les avertissements de la journée sélectionnée sont temporairement indisponibles.',
  };
}

function formatDayLabel(key) {
  if (!key) return '—';
  const locale = language() === 'ar' ? 'ar-TN' : language() === 'en' ? 'en-GB' : 'fr-FR';
  return new Date(`${key}T12:00:00Z`).toLocaleDateString(locale, {
    timeZone: 'UTC',
    weekday: 'long',
    day: '2-digit',
    month: 'long',
  });
}

function formatTime(value) {
  const date = new Date(value || '');
  if (!Number.isFinite(date.getTime())) return '—';
  const locale = language() === 'ar' ? 'ar-TN' : language() === 'en' ? 'en-GB' : 'fr-FR';
  return date.toLocaleTimeString(locale, {
    timeZone:TUNIS_TZ, hour:'2-digit', minute:'2-digit', hour12:false,
  });
}

function selectedKey() {
  const saved = state.selectedKey || localStorage.getItem(STORAGE_KEY) || '';
  const normalized = normalizeSelectedDay(saved);
  state.selectedKey = normalized;
  if (normalized && saved !== normalized) localStorage.setItem(STORAGE_KEY, normalized);
  return normalized;
}

function familyMode() {
  return document.body.classList.contains('family-board-mode');
}

function installStyles() {
  if (document.getElementById('fable-day-selection-styles')) return;
  const style = document.createElement('style');
  style.id = 'fable-day-selection-styles';
  style.textContent = `
    #family-board-nav [data-family-tab="details"]{margin-inline-start:auto}
    .family-day[data-family-day-key]{position:relative;cursor:pointer;transition:border-color .16s ease,box-shadow .16s ease,transform .16s ease}
    .family-day[data-family-day-key]:hover{transform:translateY(-1px);border-color:var(--accent)}
    .family-day[data-family-day-key]:focus-visible{outline:3px solid color-mix(in srgb,var(--accent) 65%,transparent);outline-offset:2px}
    .family-day[data-family-day-key][aria-pressed="true"]{border-color:var(--accent)!important;box-shadow:0 0 0 3px color-mix(in srgb,var(--accent) 22%,transparent)}
    .family-day[data-family-day-key][aria-pressed="true"]::after{content:'✓';position:absolute;inset-inline-end:9px;bottom:8px;display:grid;place-items:center;width:22px;height:22px;border-radius:999px;background:var(--accent);color:#041019;font-size:.76rem;font-weight:900}
    .activity-selected-day,.day-filter-context{margin-inline-start:auto;color:var(--muted);font-size:.78rem;font-weight:800;text-align:end}
    .day-filter-context{display:block;margin:0 0 10px;text-align:start}
    .activity-day-empty,.navigation-day-empty{padding:14px;border:1px dashed var(--br);border-radius:11px;color:var(--muted);background:var(--pill-bg)}
    .activity-window.activity-fallback{border-style:dashed}.activity-window.activity-fallback .activity-choice{border-top:0;margin-top:0}
    .day-warning-list{display:grid;gap:8px}.day-warning-list .line{margin:0}
    @media(max-width:620px){.activity-selected-day{width:100%;margin:6px 0 0;text-align:start}.activity-card h3{flex-wrap:wrap}}
  `;
  document.head.appendChild(style);
}

function syncDayCards() {
  const cards = Array.from(document.querySelectorAll('.family-days .family-day'));
  if (!cards.length) return;
  const keys = planningDayKeys();
  const active = selectedKey();
  const text = copy();
  cards.forEach((card, index) => {
    const key = keys[index] || '';
    card.dataset.familyDayKey = key;
    card.setAttribute('role', 'button');
    card.tabIndex = 0;
    card.setAttribute('aria-pressed', key === active ? 'true' : 'false');
    const label = `${text.selectDay}: ${formatDayLabel(key)}`;
    card.setAttribute('aria-label', label);
    card.title = label;
  });
}

function destinationWindowsForDay(destination, key, {familyOnly = false} = {}) {
  return (destination?.windows || []).filter((item) => {
    if (tunisDateKey(item?.start) !== key) return false;
    if (!familyOnly) return true;
    return String(item?.category || 'family').toLowerCase() === 'family';
  });
}

function coastalWindowsForSelectedDay() {
  const key = selectedKey();
  const rows = [];
  (state.windows?.windows || []).forEach((destination) => {
    destinationWindowsForDay(destination, key, {familyOnly:true}).forEach((windowItem) => {
      const tripMode = windowItem?.trip_mode || destination?.trip_mode || '';
      if (tripMode !== 'one_way_multi_day') rows.push({destination, windowItem});
    });
  });
  return rows;
}

function syncNavigationWindows() {
  const root = document.getElementById('wins');
  if (!root) return;
  const lines = Array.from(root.querySelectorAll('.window-line[data-start]'));
  const oldContext = root.querySelector('.day-filter-context');
  const oldEmpty = root.querySelector('.navigation-day-empty');
  if (!familyMode()) {
    lines.forEach((line) => { line.hidden = false; });
    oldContext?.remove();
    oldEmpty?.remove();
    return;
  }

  const key = selectedKey();
  let visible = 0;
  lines.forEach((line) => {
    const lineKey = tunisDateKey(line.dataset.start);
    line.dataset.familyDayKey = lineKey;
    line.hidden = lineKey !== key;
    if (!line.hidden) visible += 1;
  });

  const contextText = `${copy().windowsFor} ${formatDayLabel(key)}`;
  let context = oldContext;
  if (!context) {
    context = document.createElement('div');
    context.className = 'day-filter-context';
    root.prepend(context);
  }
  if (context.textContent !== contextText) context.textContent = contextText;

  let empty = oldEmpty;
  if (visible > 0) {
    empty?.remove();
  } else {
    if (!empty) {
      empty = document.createElement('div');
      empty.className = 'navigation-day-empty';
      root.appendChild(empty);
    }
    if (empty.textContent !== copy().noWindows) empty.textContent = copy().noWindows;
  }
}

function dayDiagnostic(destination, key) {
  const daily = destination?.daily_diagnostics;
  if (daily && typeof daily === 'object') {
    const record = Array.isArray(daily)
      ? daily.find((item) => item?.date === key)
      : daily[key];
    if (record) return record;
  }
  const diagnostics = destination?.diagnostics || null;
  const blockerKey = tunisDateKey(diagnostics?.first_blocker?.time);
  return blockerKey === key ? diagnostics : null;
}

function warningHtml(destination, key) {
  const text = copy();
  const allDay = destinationWindowsForDay(destination, key);
  const familyDay = allDay.filter((item) => String(item?.category || 'family').toLowerCase() === 'family');
  if (familyDay.length) return '';
  const offHours = allDay.some((item) => String(item?.category || '').toLowerCase() === 'off_hours');
  const diagnostics = dayDiagnostic(destination, key);
  const lang = language();
  const summary = offHours
    ? text.offHoursOnly
    : (lang === 'en' ? diagnostics?.summary_en : lang === 'ar' ? null : diagnostics?.summary_fr) || text.genericNoGo;
  const blocker = diagnostics?.first_blocker || {};
  const metricParts = [];
  if (Number.isFinite(Number(blocker?.metrics?.wind_kmh))) metricParts.push(`${Math.round(Number(blocker.metrics.wind_kmh))} km/h`);
  if (Number.isFinite(Number(blocker?.metrics?.gust_kmh))) metricParts.push(`raf. ${Math.round(Number(blocker.metrics.gust_kmh))} km/h`);
  if (Number.isFinite(Number(blocker?.metrics?.hs_m))) metricParts.push(`Hs ${Number(blocker.metrics.hs_m).toFixed(1)} m`);
  const detail = [destination?.dest_name || destination?.dest_slug || '—', metricParts.join(' · ')].filter(Boolean).join(' · ');
  return `<div class="line bad" data-day-warning-destination="${esc(destination?.dest_slug || '')}"><div class="reason">🚫 ${esc(summary)}</div><div class="small">${esc(detail)}</div></div>`;
}

function syncWarnings() {
  const root = document.getElementById('reasons');
  if (!root) return;
  const generated = root.querySelector('[data-day-warning-context]');
  if (!familyMode()) {
    if (generated && state.originalReasonsHtml != null) {
      root.innerHTML = state.originalReasonsHtml;
      state.originalReasonsHtml = null;
    }
    return;
  }

  if (!generated) state.originalReasonsHtml = root.innerHTML;
  const key = selectedKey();
  const destinations = state.windows?.windows || [];
  const warnings = destinations.map((destination) => warningHtml(destination, key)).filter(Boolean);
  const text = copy();
  const content = destinations.length
    ? (warnings.length ? warnings.join('') : `<div class="small">✅ ${esc(text.noWarnings)}</div>`)
    : `<div class="small">${esc(text.dataUnavailable)}</div>`;
  const html = `<div data-day-warning-context="${esc(key)}"><div class="day-filter-context">${esc(text.warningsFor)} ${esc(formatDayLabel(key))}</div><div class="day-warning-list">${content}</div></div>`;
  if (root.innerHTML !== html) root.innerHTML = html;
}

function ensureActivityLabel(card, key) {
  const heading = card.querySelector('h3');
  if (!heading) return;
  let label = heading.querySelector('.activity-selected-day');
  if (!label) {
    label = document.createElement('span');
    label.className = 'activity-selected-day';
    heading.appendChild(label);
  }
  const value = `${copy().activitiesFor} ${formatDayLabel(key)}`;
  if (label.textContent !== value) label.textContent = value;
}

function fallbackActivityHtml(row) {
  const text = copy();
  const destination = row.destination?.dest_name || row.destination?.dest_slug || '—';
  const item = row.windowItem || {};
  const prudent = String(item.family_tier || row.destination?.family_tier || '').toLowerCase() === 'prudent';
  return `<article class="activity-window activity-fallback ${prudent ? 'prudent' : ''}" data-family-day-key="${esc(tunisDateKey(item.start))}" data-slug="${esc(row.destination?.dest_slug || '')}" data-start="${esc(item.start || '')}" data-end="${esc(item.end || '')}"><h4>${esc(destination)} · ${esc(formatTime(item.start))} → ${esc(formatTime(item.end))}</h4><div class="activity-choice"><b>⛵ ${esc(text.familyOuting)}</b><div class="activity-meta">${esc(text.noSpecialized)}</div></div></article>`;
}

function syncActivityCards() {
  const card = document.getElementById('fable-activities');
  if (!card) return;
  const key = selectedKey();
  ensureActivityLabel(card, key);
  if (!familyMode()) {
    card.querySelectorAll('.activity-window').forEach((article) => { article.hidden = false; });
    card.querySelector('.activity-day-empty')?.remove();
    card.querySelectorAll('.activity-fallback').forEach((article) => article.remove());
    const grid = card.querySelector('.activity-grid');
    if (grid) grid.hidden = false;
    return;
  }

  let grid = card.querySelector('.activity-grid');
  if (!grid) {
    grid = document.createElement('div');
    grid.className = 'activity-grid';
    card.appendChild(grid);
  }
  grid.querySelectorAll('.activity-fallback').forEach((article) => article.remove());
  const articles = Array.from(grid.querySelectorAll('.activity-window:not(.activity-fallback)'));
  articles.forEach((article) => {
    const articleKey = article.dataset.familyDayKey || tunisDateKey(article.dataset.start);
    article.dataset.familyDayKey = articleKey;
    article.hidden = articleKey !== key;
  });

  let visibleCount = articles.filter((article) => !article.hidden).length;
  if (visibleCount === 0) {
    const fallbackRows = coastalWindowsForSelectedDay();
    const distinct = [...new Map(fallbackRows.map((row) => [row.destination?.dest_slug || row.destination?.dest_name, row])).values()];
    if (distinct.length) {
      grid.insertAdjacentHTML('beforeend', distinct.slice(0, 4).map(fallbackActivityHtml).join(''));
      visibleCount = distinct.length;
    }
  }

  grid.hidden = visibleCount === 0;
  let empty = card.querySelector('.activity-day-empty');
  if (visibleCount > 0) {
    empty?.remove();
    return;
  }
  if (!empty) {
    empty = document.createElement('div');
    empty.className = 'activity-day-empty';
    grid.insertAdjacentElement('beforebegin', empty);
  }
  const message = copy().noActivities;
  if (empty.textContent !== message) empty.textContent = message;
}

function syncAll() {
  installStyles();
  document.body.dataset.familyDay = selectedKey();
  syncDayCards();
  syncNavigationWindows();
  syncWarnings();
  syncActivityCards();
}

function scheduleSync() {
  if (state.syncScheduled) return;
  state.syncScheduled = true;
  queueMicrotask(() => {
    state.syncScheduled = false;
    syncAll();
  });
}

function setSelectedDay(key, {persist = true, announce = true} = {}) {
  const normalized = normalizeSelectedDay(key);
  if (!normalized) return;
  state.selectedKey = normalized;
  if (persist) localStorage.setItem(STORAGE_KEY, normalized);
  syncAll();
  if (announce) {
    window.dispatchEvent(new CustomEvent('fable:day-selected', {
      detail: {dateKey: normalized, label: formatDayLabel(normalized)},
    }));
  }
}

async function refreshData() {
  try {
    const [recommendationsResponse, windowsResponse] = await Promise.all([
      fetch('recommendations.json', {cache: 'no-store'}),
      fetch('windows.json', {cache: 'no-store'}),
    ]);
    const recommendationPayload = recommendationsResponse.ok ? await recommendationsResponse.json() : {};
    state.recommendations = Array.isArray(recommendationPayload?.recommendations)
      ? recommendationPayload.recommendations : [];
    state.windows = windowsResponse.ok ? await windowsResponse.json() : null;
  } catch {
    state.recommendations = [];
    state.windows = null;
  }
  syncAll();
}

function bindEvents() {
  document.addEventListener('click', (event) => {
    const card = event.target.closest('.family-day[data-family-day-key]');
    if (card) setSelectedDay(card.dataset.familyDayKey);
  });
  document.addEventListener('keydown', (event) => {
    const card = event.target.closest?.('.family-day[data-family-day-key]');
    if (!card || !['Enter', ' '].includes(event.key)) return;
    event.preventDefault();
    setSelectedDay(card.dataset.familyDayKey);
  });
  document.getElementById('langToggle')?.addEventListener('click', () => setTimeout(syncAll, 0));
  window.addEventListener('fable:activities-rendered', (event) => {
    if (Array.isArray(event.detail?.recommendations)) state.recommendations = event.detail.recommendations;
    scheduleSync();
  });
  window.addEventListener('storage', (event) => {
    if (event.key === STORAGE_KEY) {
      state.selectedKey = normalizeSelectedDay(event.newValue || '');
      syncAll();
    }
    if (event.key === 'lang') syncAll();
  });
}

function start() {
  installStyles();
  bindEvents();
  state.selectedKey = normalizeSelectedDay(localStorage.getItem(STORAGE_KEY) || '');
  localStorage.setItem(STORAGE_KEY, state.selectedKey);
  const contentObserver = new MutationObserver((mutations) => {
    const meaningful = mutations.some((mutation) => {
      const target = mutation.target?.nodeType === Node.ELEMENT_NODE
        ? mutation.target
        : mutation.target?.parentElement;
      return !target?.closest?.('#fable-activities');
    });
    if (meaningful) scheduleSync();
  });
  contentObserver.observe(document.body, {subtree: true, childList: true});
  const modeObserver = new MutationObserver(scheduleSync);
  modeObserver.observe(document.body, {attributes:true, attributeFilter:['class', 'data-family-tab']});
  syncAll();
  refreshData();
  setInterval(refreshData, 10 * 60 * 1000);
  window.FABLEDaySelection = Object.assign(window.FABLEDaySelection || {}, {
    getSelectedDay: selectedKey,
    setSelectedDay,
    tunisDateKey,
    planningDayKeys,
    recommendationsForDay,
    windowsForDay: (key = selectedKey()) => (state.windows?.windows || []).flatMap((destination) => (
      destinationWindowsForDay(destination, key).map((windowItem) => ({destination, windowItem}))
    )),
    refresh: refreshData,
  });
}

if (typeof window !== 'undefined' && typeof document !== 'undefined') {
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start, {once: true});
  else start();
}
