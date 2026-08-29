import {
  getDisplayedNavigationWindows,
  isLongTripNavigationWindow,
  navigationWindowCounts,
} from './navigation-windows.js';

const TUNIS_TZ = 'Africa/Tunis';
const STORAGE_KEY = 'fable_selected_day';
const DAY_COUNT = 3;

const state = {
  selectedKey: null,
  recommendations: [],
  windows: null,
  rules: {},
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
    activitiesAllDays: 'All days in the 72 h horizon',
    noActivities: 'No activity is associated with this day in a validated Family GO window.',
    noSpecialized: 'No specialised activity passed its own comfort limits. A family outing on the water remains possible inside this validated Family GO window.',
    familyOuting: 'Family outing on the water',
    noWindows: 'No navigation window is validated for this selected day.',
    outbound: 'Outbound',
    return: 'Return',
    oneWay: 'one way — return to be planned separately',
    beta: 'Beta',
    confidence: 'Confidence',
    noWarnings: 'No NO-GO warning for the selected day.',
    genericNoGo: 'No Family GO window is validated for this destination on the selected day.',
    offHoursOnly: 'Only an out-of-hours window is available on the selected day.',
    dataUnavailable: 'Selected-day warnings are temporarily unavailable.',
    blocking: 'Blocking',
  };
  if (lang === 'ar') return {
    selectDay: 'اختر هذا اليوم',
    selectedDay: 'اليوم المختار',
    activitiesFor: 'أنشطة يوم',
    windowsFor: 'نوافذ الملاحة ليوم',
    warningsFor: 'تحذيرات عدم الخروج ليوم',
    activitiesAllDays: 'كل الأيام ضمن أفق 72 ساعة',
    noActivities: 'لا توجد أنشطة مرتبطة بهذا اليوم ضمن نافذة Family GO صالحة.',
    noSpecialized: 'لم يتجاوز أي نشاط متخصص حدود الراحة الخاصة به. تبقى خرجة عائلية على الماء ممكنة داخل نافذة Family GO الصالحة.',
    familyOuting: 'خرجة عائلية على الماء',
    noWindows: 'لا توجد نافذة ملاحة صالحة لليوم المختار.',
    outbound: 'الذهاب',
    return: 'العودة',
    oneWay: 'ذهاب فقط — يجب التخطيط للعودة بشكل منفصل',
    beta: 'تجريبي',
    confidence: 'الثقة',
    noWarnings: 'لا يوجد تحذير عدم خروج لليوم المختار.',
    genericNoGo: 'لا توجد نافذة Family GO صالحة لهذه الوجهة في اليوم المختار.',
    offHoursOnly: 'توجد فقط نافذة خارج الساعات العائلية في اليوم المختار.',
    dataUnavailable: 'تحذيرات اليوم المختار غير متاحة مؤقتاً.',
    blocking: 'مانع',
  };
  return {
    selectDay: 'Sélectionner cette journée',
    selectedDay: 'Journée sélectionnée',
    activitiesFor: 'Activités du',
    windowsFor: 'Fenêtres de navigation du',
    warningsFor: 'Avertissements NO-GO du',
    activitiesAllDays: 'Toutes les journées de l’horizon 72 h',
    noActivities: 'Aucune activité associée à cette journée dans une fenêtre Family GO validée.',
    noSpecialized: 'Aucune activité spécialisée ne passe ses propres limites de confort. Une sortie familiale sur l’eau reste possible dans cette fenêtre Family GO validée.',
    familyOuting: 'Sortie familiale sur l’eau',
    noWindows: 'Aucune fenêtre de navigation validée pour la journée sélectionnée.',
    outbound: 'Aller',
    return: 'Retour',
    oneWay: 'aller simple — retour à planifier séparément',
    beta: 'Bêta',
    confidence: 'Confiance',
    noWarnings: 'Aucun avertissement NO-GO pour la journée sélectionnée.',
    genericNoGo: 'Aucune fenêtre Family GO validée pour cette destination pendant la journée sélectionnée.',
    offHoursOnly: 'Seule une fenêtre hors horaires familiaux est disponible pendant la journée sélectionnée.',
    dataUnavailable: 'Les avertissements de la journée sélectionnée sont temporairement indisponibles.',
    blocking: 'Bloquant',
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
    .activity-window.activity-fallback{border-style:dashed}.activity-blocked-list{margin:7px 0 0;padding-left:9px;border-left:2px solid var(--br);list-style:none;display:flex;flex-direction:column;gap:4px;font-size:.83rem;color:var(--muted);line-height:1.4}.activity-window.activity-fallback .activity-choice{border-top:0;margin-top:0}
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
  let lines = Array.from(root.querySelectorAll('.window-line[data-start]'));
  const oldContext = root.querySelector('.day-filter-context');
  const oldEmpty = root.querySelector('.navigation-day-empty');
  if (!familyMode()) {
    lines.filter((line) => line.dataset.normalizedNavigation === 'true').forEach((line) => line.remove());
    lines.filter((line) => line.dataset.normalizedNavigation !== 'true').forEach((line) => { line.hidden = false; });
    oldContext?.remove();
    oldEmpty?.remove();
    return;
  }

  const key = selectedKey();
  const displayed = getDisplayedNavigationWindows(key, state.windows);
  const displayedKeys = new Map(displayed.map((row) => [navigationRowKey(row), row]));
  const existingKeys = new Set(lines.map(
    (line) => navigationLineKey(line)
  ));
  displayedKeys.forEach((row, rowKey) => {
    if (existingKeys.has(rowKey)) return;
    const line = document.createElement('div');
    line.className = 'window-line';
    line.dataset.slug = row.destination?.dest_slug || '';
    line.dataset.start = row.windowItem.start;
    line.dataset.end = row.windowItem.end;
    line.dataset.direction = row.windowItem.direction || '';
    line.dataset.normalizedNavigation = 'true';
    root.appendChild(line);
    lines.push(line);
  });
  const matchedKeys = new Set();
  let visible = 0;
  lines.forEach((line) => {
    const lineKey = tunisDateKey(line.dataset.start);
    line.dataset.familyDayKey = lineKey;
    const row = displayedKeys.get(navigationLineKey(line));
    const rowKey = row ? navigationRowKey(row) : '';
    line.hidden = !row || matchedKeys.has(rowKey);
    if (row && !line.hidden) {
      matchedKeys.add(rowKey);
      if (isLongTripNavigationWindow(row)) renderLongTripLine(line, row);
      else if (line.dataset.normalizedNavigation === 'true') renderStandardLine(line, row);
    }
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

  syncNavigationCounts(displayed);
}

function navigationRowKey(row) {
  return [
    row.destination?.dest_slug || '',
    row.windowItem.start || '',
    row.windowItem.end || '',
    row.windowItem.direction || '',
  ].join('|');
}

function navigationLineKey(line) {
  return [
    line.dataset.slug || '',
    line.dataset.start || '',
    line.dataset.end || '',
    line.dataset.direction || '',
  ].join('|');
}

function renderStandardLine(line, row) {
  const item = row.windowItem;
  const destination = row.destination;
  const renderKey = [language(), item.start, item.end, item.confidence].join('|');
  if (line.dataset.standardRenderKey === renderKey) return;
  line.dataset.standardRenderKey = renderKey;
  line.innerHTML = `<div class="title">${esc(destination.dest_name || destination.dest_slug || '—')} <span class="go family">FAMILY GO</span></div>
    <div class="small">${esc(formatDateTime(item.start))} → ${esc(formatDateTime(item.end))}</div>
    <div class="small">${esc(durationLabel(item.start, item.end))} · ${esc(copy().confidence)} ${esc(item.confidence || destination.confidence || '—')}</div>`;
}

function durationLabel(start, end) {
  const hours = (new Date(end) - new Date(start)) / 36e5;
  if (!Number.isFinite(hours)) return '—';
  return Number.isInteger(hours) ? `${hours} h` : `${hours.toFixed(1)} h`;
}

function formatDateTime(value) {
  const date = new Date(value);
  if (!Number.isFinite(date.getTime())) return '—';
  return date.toLocaleString(language() === 'en' ? 'en-GB' : language() === 'ar' ? 'ar-TN' : 'fr-FR', {
    timeZone:TUNIS_TZ, weekday:'long', day:'2-digit', month:'short',
    hour:'2-digit', minute:'2-digit', hour12:false,
  });
}

function renderLongTripLine(line, row) {
  const item = row.windowItem;
  const destination = row.destination;
  const text = copy();
  const direction = item.direction === 'return' ? text.return : text.outbound;
  const beta = item.route_kind === 'offshore_one_way_beta'
    || destination.route_kind === 'offshore_one_way_beta'
    || destination.beta || item.beta;
  const outboundOrigin = item.origin_name || item.origin_slug || '—';
  const outboundTarget = item.destination_name || destination.dest_name || destination.dest_slug || '—';
  const origin = item.direction === 'return' ? outboundTarget : outboundOrigin;
  const target = item.direction === 'return' ? outboundOrigin : outboundTarget;
  const renderKey = [
    language(), item.start, item.end, item.direction, item.confidence,
    origin, target, beta ? 'beta' : '',
  ].join('|');
  line.classList.add('long-trip-window');
  line.classList.remove('expert-only');
  if (line.dataset.longTripRenderKey === renderKey) return;
  line.dataset.longTripRenderKey = renderKey;
  const confidenceKey = String(item.confidence || destination.confidence || '').toLowerCase();
  const confidenceClass = ['high', 'medium', 'low'].includes(confidenceKey) ? confidenceKey : 'low';
  line.innerHTML = `<div class="title">${esc(destination.dest_name || destination.dest_slug || target)} <span class="go family">${esc(direction)}</span> <span class="conf ${confidenceClass} expert-only" data-quality-level="${esc(confidenceClass)}"><span class="quality-bars" aria-hidden="true"><i></i><i></i><i></i></span><span class="quality-label">${esc(item.confidence || destination.confidence || '—')}</span></span>${beta ? ` <span class="family-badge prudent long-trip-beta">${esc(text.beta)}</span>` : ''}</div>
    <div class="small long-trip-route"><b>${esc(origin)} → ${esc(target)}</b></div>
    <div class="small">${esc(formatDateTime(item.start))} → ${esc(formatDateTime(item.end))}</div>
    <div class="small">${esc(durationLabel(item.start, item.end))} · ${esc(text.confidence || 'Confiance')} ${esc(item.confidence || destination.confidence || '—')}</div>
    <div class="offshore-note">${esc(text.oneWay)}</div>`;
}

function syncNavigationCounts(displayed) {
  const counts = navigationWindowCounts(displayed);
  const key = selectedKey();
  document.querySelectorAll(`[data-nav-family-count="${key}"]`).forEach((node) => {
    if (node.textContent !== String(counts.family)) node.textContent = String(counts.family);
  });
  document.querySelectorAll(`[data-nav-long-count="${key}"]`).forEach((node) => {
    if (node.textContent !== String(counts.longTrip)) node.textContent = String(counts.longTrip);
  });
  document.querySelectorAll('[data-nav-selected-family-count]').forEach((node) => {
    if (node.textContent !== String(counts.family)) node.textContent = String(counts.family);
  });
  document.querySelectorAll('[data-nav-selected-long-count]').forEach((node) => {
    if (node.textContent !== String(counts.longTrip)) node.textContent = String(counts.longTrip);
  });
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
  const diagnosticDestination = {...destination, diagnostics};
  const checks = window.FABLEDecisionWidgets?.checksHtml(diagnosticDestination,state.rules,lang) || '';
  return `<div class="line bad" data-day-warning-destination="${esc(destination?.dest_slug || '')}"><span class="reason-status">${esc(text.blocking)}</span><div class="reason-content"><div class="reason">${esc(summary)}</div><div class="small">${esc(detail)}</div></div>${checks}</div>`;
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
  // key null = vue Expert : toutes les journees sont affichees, annoncer une
  // date precise au-dessus mentait sur le contenu.
  const value = key ? `${copy().activitiesFor} ${formatDayLabel(key)}` : copy().activitiesAllDays;
  if (label.textContent !== value) label.textContent = value;
}

/* Le moteur publie, pour une fenetre Family GO sans activite, les activites
   les plus proches d'etre acceptees et la limite qui les bloque. Sans cette
   information la carte ne disait que « aucune activite specialisee », ce qui
   n'aide personne a decider. */
function blockedActivityDetail(slug, start) {
  const entry = (state.noActivity || []).find(
    (item) => item.dest_slug === slug && item.start === start
  );
  const closest = entry?.closest;
  if (!Array.isArray(closest) || !closest.length) return '';
  const lang = language();
  return `<ul class="activity-blocked-list">${closest.map((item) => {
    const label = esc(lang === 'en' ? item.label_en : item.label_fr);
    const reason = esc(lang === 'en' ? item.reason_en : item.reason_fr);
    return `<li>${esc(item.icon || '•')} <b>${label}</b> : ${reason}</li>`;
  }).join('')}</ul>`;
}

function fallbackActivityHtml(row) {
  const text = copy();
  const destination = row.destination?.dest_name || row.destination?.dest_slug || '—';
  const item = row.windowItem || {};
  const prudent = String(item.family_tier || row.destination?.family_tier || '').toLowerCase() === 'prudent';
  const detail = blockedActivityDetail(row.destination?.dest_slug || '', item.start || '');
  return `<article class="activity-window activity-fallback ${prudent ? 'prudent' : ''}" data-family-day-key="${esc(tunisDateKey(item.start))}" data-slug="${esc(row.destination?.dest_slug || '')}" data-start="${esc(item.start || '')}" data-end="${esc(item.end || '')}"><h4>${esc(destination)} · ${esc(formatTime(item.start))} → ${esc(formatTime(item.end))}</h4><div class="activity-choice"><b>⛵ ${esc(text.familyOuting)}</b><div class="activity-meta">${esc(text.noSpecialized)}</div>${detail}</div></article>`;
}

function syncActivityCards() {
  const card = document.getElementById('fable-activities');
  if (!card) return;
  const key = selectedKey();
  ensureActivityLabel(card, familyMode() ? key : null);
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
    const [recommendationsResponse, windowsResponse, rulesResponse] = await Promise.all([
      fetch('recommendations.json', {cache: 'no-store'}),
      fetch('windows.json', {cache: 'no-store'}),
      fetch('rules.normalized.json', {cache: 'no-store'}),
    ]);
    const recommendationPayload = recommendationsResponse.ok ? await recommendationsResponse.json() : {};
    state.recommendations = Array.isArray(recommendationPayload?.recommendations)
      ? recommendationPayload.recommendations : [];
    state.noActivity = Array.isArray(recommendationPayload?.no_activity)
      ? recommendationPayload.no_activity : [];
    state.windows = windowsResponse.ok ? await windowsResponse.json() : null;
    state.rules = rulesResponse.ok ? await rulesResponse.json() : {};
  } catch {
    state.recommendations = [];
    state.noActivity = [];
    state.windows = null;
    state.rules = {};
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
    getDisplayedNavigationWindows: (key = selectedKey()) => getDisplayedNavigationWindows(key, state.windows),
    refresh: refreshData,
  });
}

if (typeof window !== 'undefined' && typeof document !== 'undefined') {
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start, {once: true});
  else start();
}
