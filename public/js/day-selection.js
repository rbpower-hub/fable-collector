const TUNIS_TZ = 'Africa/Tunis';
const STORAGE_KEY = 'fable_selected_day';
const DAY_COUNT = 3;

const state = {
  selectedKey: null,
  recommendations: [],
  syncScheduled: false,
};

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
    noActivities: 'No activity is associated with this day in a validated Family GO window.',
  };
  if (lang === 'ar') return {
    selectDay: 'اختر هذا اليوم',
    selectedDay: 'اليوم المختار',
    activitiesFor: 'أنشطة يوم',
    noActivities: 'لا توجد أنشطة مرتبطة بهذا اليوم ضمن نافذة Family GO صالحة.',
  };
  return {
    selectDay: 'Sélectionner cette journée',
    selectedDay: 'Journée sélectionnée',
    activitiesFor: 'Activités du',
    noActivities: 'Aucune activité associée à cette journée dans une fenêtre Family GO validée.',
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

function selectedKey() {
  const saved = state.selectedKey || localStorage.getItem(STORAGE_KEY) || '';
  const normalized = normalizeSelectedDay(saved);
  state.selectedKey = normalized;
  if (normalized && saved !== normalized) localStorage.setItem(STORAGE_KEY, normalized);
  return normalized;
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
    .activity-selected-day{margin-inline-start:auto;color:var(--muted);font-size:.78rem;font-weight:800;text-align:end}
    .activity-day-empty{padding:14px;border:1px dashed var(--br);border-radius:11px;color:var(--muted);background:var(--pill-bg)}
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

function syncActivityCards() {
  const card = document.getElementById('fable-activities');
  if (!card) return;
  const articles = Array.from(card.querySelectorAll('.activity-window'));
  const grid = card.querySelector('.activity-grid');
  const key = selectedKey();
  ensureActivityLabel(card, key);

  if (!articles.length || !grid) {
    card.querySelector('.activity-day-empty')?.remove();
    return;
  }

  articles.forEach((article, index) => {
    const recommendation = state.recommendations[index] || null;
    const articleKey = tunisDateKey(recommendation?.start);
    article.dataset.familyDayKey = articleKey;
    article.hidden = articleKey !== key;
  });

  const visibleCount = articles.filter((article) => !article.hidden).length;
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

async function refreshRecommendations() {
  try {
    const response = await fetch('recommendations.json', {cache: 'no-store'});
    const payload = response.ok ? await response.json() : {};
    state.recommendations = Array.isArray(payload?.recommendations) ? payload.recommendations : [];
  } catch {
    state.recommendations = [];
  }
  syncActivityCards();
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
  const observer = new MutationObserver(scheduleSync);
  observer.observe(document.body, {subtree: true, childList: true});
  syncAll();
  refreshRecommendations();
  setInterval(refreshRecommendations, 10 * 60 * 1000);
  window.FABLEDaySelection = Object.assign(window.FABLEDaySelection || {}, {
    getSelectedDay: selectedKey,
    setSelectedDay,
    tunisDateKey,
    planningDayKeys,
    recommendationsForDay,
  });
}

if (typeof window !== 'undefined' && typeof document !== 'undefined') {
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start, {once: true});
  else start();
}
