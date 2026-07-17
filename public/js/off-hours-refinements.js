const TUNIS_TZ = 'Africa/Tunis';
const STORAGE_KEY = 'fable_selected_day';

const state = {
  windows: null,
  recommendations: [],
  scheduled: false,
};

const esc = (value) => String(value ?? '').replace(
  /[&<>"']/g,
  (char) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char])
);

export function tunisDateKey(value) {
  const date = value instanceof Date ? value : new Date(value || '');
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

export function categoryOf(recommendation, sourceWindow = null) {
  return String(recommendation?.category || sourceWindow?.category || 'family').toLowerCase();
}

export function offHoursRowsForDay(windows, selectedKey) {
  const rows = [];
  (windows?.windows || []).forEach((destination) => {
    (destination?.windows || []).forEach((windowItem) => {
      const tripMode = windowItem?.trip_mode || destination?.trip_mode || '';
      if (tripMode === 'one_way_multi_day') return;
      if (categoryOf(null, windowItem) !== 'off_hours') return;
      if (tunisDateKey(windowItem?.start) !== selectedKey) return;
      rows.push({destination, windowItem});
    });
  });
  return rows;
}

function language() {
  const value = (localStorage.getItem('lang') || document.documentElement.lang || 'fr').toLowerCase();
  if (value.startsWith('ar')) return 'ar';
  return value.startsWith('en') ? 'en' : 'fr';
}

function copy() {
  if (language() === 'en') return {
    state: 'GO OUTSIDE FAMILY HOURS',
    summary: (count) => `${count} window${count === 1 ? '' : 's'} available outside family hours`,
    count: 'outside family hours',
    badge: 'OUTSIDE FAMILY HOURS',
    caution: 'Not a Family GO. Early or late slot intended for experienced users; reassess conditions before departure.',
    warning: 'A navigation window exists, but only outside family hours.',
    activities: 'Activities outside family hours',
    fishing: 'Fishing profile',
    techniques: 'Techniques',
    baits: 'Baits / lures',
    depth: 'Depth',
  };
  if (language() === 'ar') return {
    state: 'مناسب خارج الساعات العائلية',
    summary: (count) => `${count} نافذة متاحة خارج الساعات العائلية`,
    count: 'خارج الساعات العائلية',
    badge: 'خارج الساعات العائلية',
    caution: 'ليست نافذة Family GO. توقيت مبكر أو متأخر للمستخدمين ذوي الخبرة مع إعادة التحقق قبل الانطلاق.',
    warning: 'توجد نافذة ملاحة، ولكن فقط خارج الساعات العائلية.',
    activities: 'أنشطة خارج الساعات العائلية',
    fishing: 'ملف الصيد',
    techniques: 'التقنيات',
    baits: 'الطعوم / الشِباك',
    depth: 'العمق',
  };
  return {
    state: 'GO HORS HORAIRES',
    summary: (count) => `${count} fenêtre${count === 1 ? '' : 's'} disponible${count === 1 ? '' : 's'} hors horaires familiaux`,
    count: 'hors horaires',
    badge: 'HORS HORAIRES FAMILIAUX',
    caution: 'Ce n’est pas un Family GO. Créneau tôt ou tard destiné aux utilisateurs expérimentés, avec nouvelle vérification avant départ.',
    warning: 'Une fenêtre de navigation existe, mais uniquement hors horaires familiaux.',
    activities: 'Activités hors horaires familiaux',
    fishing: 'Profil pêche',
    techniques: 'Techniques',
    baits: 'Appâts / leurres',
    depth: 'Profondeur',
  };
}

function selectedKey() {
  return document.body.dataset.familyDay || localStorage.getItem(STORAGE_KEY) || tunisDateKey(new Date());
}

function formatTime(value) {
  const date = new Date(value || '');
  if (!Number.isFinite(date.getTime())) return '—';
  const locale = language() === 'ar' ? 'ar-TN' : language() === 'en' ? 'en-GB' : 'fr-FR';
  return date.toLocaleTimeString(locale, {
    timeZone: TUNIS_TZ,
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  });
}

function installStyles() {
  if (document.getElementById('fable-off-hours-styles')) return;
  const style = document.createElement('style');
  style.id = 'fable-off-hours-styles';
  style.textContent = `
    .family-day.off-hours{border-color:color-mix(in srgb,var(--warn) 72%,var(--br))}
    .family-day.off-hours .family-day-state{color:var(--warn);border-color:color-mix(in srgb,var(--warn) 55%,var(--br))}
    .family-day-offhours-option{border-top:1px solid var(--br);padding:7px 0;font-size:.84rem;line-height:1.35}
    .family-day-offhours-option small{display:block;color:var(--warn);margin-top:2px}
    .activity-window.off-hours{border-color:color-mix(in srgb,var(--warn) 72%,var(--br));background:color-mix(in srgb,var(--warn) 8%,var(--pill-bg))}
    .off-hours-badge{display:inline-block;margin-inline-start:6px;padding:2px 7px;border:1px solid var(--warn);border-radius:999px;color:var(--warn);font-size:.72rem;font-weight:900}
    .off-hours-caution{margin:7px 0;color:var(--warn);font-size:.84rem;line-height:1.4}
    .day-warning-list .line.off-hours-warning{border-color:var(--warn);background:color-mix(in srgb,var(--warn) 8%,var(--card))}
  `;
  document.head.appendChild(style);
}

function distinctRows(rows) {
  return [...new Map(rows.map((row) => [
    `${row.destination?.dest_slug || row.destination?.dest_name}|${row.windowItem?.start}|${row.windowItem?.end}`,
    row,
  ])).values()];
}

function familyRowsForDay(key) {
  const rows = [];
  (state.windows?.windows || []).forEach((destination) => {
    (destination?.windows || []).forEach((windowItem) => {
      if (tunisDateKey(windowItem?.start) !== key) return;
      if (categoryOf(null, windowItem) !== 'family') return;
      const tripMode = windowItem?.trip_mode || destination?.trip_mode || '';
      if (tripMode !== 'one_way_multi_day') rows.push({destination, windowItem});
    });
  });
  return distinctRows(rows);
}

function tripRowsForDay(key) {
  const rows = [];
  (state.windows?.windows || []).forEach((destination) => {
    (destination?.windows || []).forEach((windowItem) => {
      if (tunisDateKey(windowItem?.start) !== key) return;
      const tripMode = windowItem?.trip_mode || destination?.trip_mode || '';
      if (tripMode === 'one_way_multi_day' && categoryOf(null, windowItem) === 'family') rows.push({destination, windowItem});
    });
  });
  return distinctRows(rows);
}

function refineDayCards() {
  const text = copy();
  document.querySelectorAll('.family-days .family-day[data-family-day-key]').forEach((card) => {
    const key = card.dataset.familyDayKey;
    const familyRows = familyRowsForDay(key);
    const offRows = distinctRows(offHoursRowsForDay(state.windows, key));
    const trips = tripRowsForDay(key);

    card.classList.remove('off-hours');
    card.querySelectorAll('.family-day-offhours-option').forEach((node) => node.remove());
    if (!offRows.length) return;

    const count = card.querySelector('.family-day-count');
    if (count) count.textContent = `${familyRows.length} ${language() === 'en' ? 'family options' : language() === 'ar' ? 'خيارات عائلية' : 'options famille'} · ${offRows.length} ${text.count} · ${trips.length} ${language() === 'en' ? 'long-trip windows' : language() === 'ar' ? 'رحلات طويلة' : 'fenêtres long trajet'}`;

    if (familyRows.length || trips.length) return;
    card.classList.add('off-hours');
    const stateLabel = card.querySelector('.family-day-state');
    if (stateLabel) stateLabel.textContent = text.state;
    const empty = card.querySelector('.family-day-empty');
    if (empty) empty.textContent = text.summary(offRows.length);

    const insertionPoint = count || null;
    offRows.slice(0, 2).forEach((row) => {
      const option = document.createElement('div');
      option.className = 'family-day-offhours-option';
      option.innerHTML = `<b>${esc(row.destination?.dest_name || row.destination?.dest_slug || '—')}</b><small>${esc(formatTime(row.windowItem?.start))}–${esc(formatTime(row.windowItem?.end))} · ${esc(text.badge)}</small>`;
      card.insertBefore(option, insertionPoint);
    });
  });
}

function sourceWindowIndex() {
  const index = new Map();
  (state.windows?.windows || []).forEach((destination) => {
    (destination?.windows || []).forEach((windowItem) => {
      index.set(`${destination?.dest_slug || ''}|${windowItem?.start || ''}|${windowItem?.end || ''}`, windowItem);
    });
  });
  return index;
}

function fishingHtml(recommendation) {
  const profile = recommendation?.fishing || {};
  const species = (profile.species || []).slice(0, 4).map(esc).join(', ');
  const techniques = (profile.techniques || []).slice(0, 3).map(esc).join(', ');
  const baits = (profile.baits || []).slice(0, 4).map(esc).join(', ');
  const depth = Array.isArray(profile.depths_m) && profile.depths_m.length === 2
    ? `${profile.depths_m[0]}–${profile.depths_m[1]} m`
    : '';
  if (!species && !techniques && !baits && !depth) return '';
  const text = copy();
  return `<div class="activity-meta"><b>${esc(text.fishing)}:</b> ${species || '—'}<br><b>${esc(text.techniques)}:</b> ${techniques || '—'}<br><b>${esc(text.baits)}:</b> ${baits || '—'}${depth ? ` · <b>${esc(text.depth)}:</b> ${esc(depth)}` : ''}</div>`;
}

function offHoursRecommendations(key) {
  const byWindow = sourceWindowIndex();
  return (state.recommendations || []).filter((recommendation) => {
    if (tunisDateKey(recommendation?.start) !== key) return false;
    const source = byWindow.get(`${recommendation?.dest_slug || ''}|${recommendation?.start || ''}|${recommendation?.end || ''}`) || null;
    return categoryOf(recommendation, source) === 'off_hours';
  });
}

function renderOffHoursActivities() {
  const card = document.getElementById('fable-activities');
  if (!card) return;
  let grid = card.querySelector('.activity-grid');
  if (!grid) {
    grid = document.createElement('div');
    grid.className = 'activity-grid';
    card.appendChild(grid);
  }
  grid.querySelectorAll('[data-off-hours-card="1"]').forEach((node) => node.remove());

  const key = selectedKey();
  const recommendations = offHoursRecommendations(key);
  if (!recommendations.length) return;

  const text = copy();
  recommendations.forEach((recommendation) => {
    const activities = (recommendation.activities || []).map((item) => `<div class="activity-choice"><span class="activity-score">${Math.round(Number(item.score || 0))}/100</span><b>${esc(item.icon || '')} ${esc(language() === 'en' ? item.label_en : language() === 'ar' ? (item.label_ar || item.label_fr) : item.label_fr)}</b><div class="activity-meta">${esc(language() === 'en' ? item.why_en : item.why_fr)}</div></div>`).join('');
    const article = document.createElement('article');
    article.className = 'activity-window off-hours';
    article.dataset.offHoursCard = '1';
    article.dataset.familyDayKey = key;
    article.dataset.start = recommendation.start || '';
    article.dataset.end = recommendation.end || '';
    article.dataset.category = 'off_hours';
    article.innerHTML = `<h4>${esc(recommendation.dest_name || recommendation.dest_slug || '—')} · ${esc(formatTime(recommendation.start))} → ${esc(formatTime(recommendation.end))}<span class="off-hours-badge">${esc(text.badge)}</span></h4><div class="off-hours-caution">⚠ ${esc(text.caution)}</div>${activities}${fishingHtml(recommendation)}`;
    grid.appendChild(article);
  });

  card.querySelector('.activity-day-empty')?.remove();
  card.querySelectorAll('.activity-fallback').forEach((node) => node.remove());
  grid.hidden = false;
}

function refineWarnings() {
  const key = selectedKey();
  const text = copy();
  const offRows = offHoursRowsForDay(state.windows, key);
  const slugs = new Set(offRows.map((row) => row.destination?.dest_slug).filter(Boolean));
  document.querySelectorAll('#reasons .line[data-day-warning-destination]').forEach((line) => {
    const slug = line.dataset.dayWarningDestination;
    if (!slugs.has(slug)) return;
    line.classList.remove('bad');
    line.classList.add('warn', 'off-hours-warning');
    const reason = line.querySelector('.reason');
    if (reason) reason.textContent = `⚠️ ${text.warning}`;
  });
}

function sync() {
  installStyles();
  refineDayCards();
  refineWarnings();
  renderOffHoursActivities();
}

function scheduleSync() {
  if (state.scheduled) return;
  state.scheduled = true;
  queueMicrotask(() => {
    state.scheduled = false;
    sync();
  });
}

async function refresh() {
  try {
    const [windowsResponse, recommendationsResponse] = await Promise.all([
      fetch('windows.json', {cache: 'no-store'}),
      fetch('recommendations.json', {cache: 'no-store'}),
    ]);
    state.windows = windowsResponse.ok ? await windowsResponse.json() : null;
    const recommendations = recommendationsResponse.ok ? await recommendationsResponse.json() : null;
    state.recommendations = Array.isArray(recommendations?.recommendations) ? recommendations.recommendations : [];
  } catch {
    state.windows = null;
    state.recommendations = [];
  }
  scheduleSync();
}

function start() {
  refresh();
  window.addEventListener('fable:day-selected', scheduleSync);
  window.addEventListener('fable:activities-rendered', scheduleSync);
  window.addEventListener('fable:languagechange', scheduleSync);
  const observer = new MutationObserver((mutations) => {
    if (mutations.some((mutation) => !mutation.target?.closest?.('[data-off-hours-card="1"], .family-day-offhours-option'))) scheduleSync();
  });
  observer.observe(document.body, {subtree: true, childList: true});
  setInterval(refresh, 10 * 60 * 1000);
}

if (typeof window !== 'undefined' && typeof document !== 'undefined') {
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start, {once: true});
  else start();
}
