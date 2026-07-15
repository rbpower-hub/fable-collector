/* FABLE freshness gate — one fail-safe source for stale UI decisions. */
(function () {
  const FALLBACK_LIMIT_MIN = 95;
  const LEEWAY_MIN = 35;
  let currentStatus = null;
  let scheduled = false;

  const freshnessState = window.FABLEFreshness?.freshnessState || ((status, referenceIso = null) => {
    const cadence = Number(status?.cadence_minutes);
    const limit_min = Number.isFinite(cadence) && cadence > 0
      ? cadence + LEEWAY_MIN
      : FALLBACK_LIMIT_MIN;
    const reference = referenceIso || status?.generated_at || null;
    const timestamp = reference ? new Date(reference).getTime() : NaN;
    const age_min = Number.isFinite(timestamp)
      ? Math.max(0, (Date.now() - timestamp) / 60000)
      : Infinity;
    return {fresh: Number.isFinite(age_min) && age_min <= limit_min, age_min, limit_min};
  });

  window.FABLEFreshness = Object.assign(window.FABLEFreshness || {}, {freshnessState});

  function language() {
    return (localStorage.getItem('lang') || document.documentElement.lang || 'fr')
      .toLowerCase().startsWith('en') ? 'en' : 'fr';
  }

  function formatDate(value) {
    const date = new Date(value || '');
    if (Number.isNaN(date.getTime())) return '—';
    return date.toLocaleString(language() === 'en' ? 'en-GB' : 'fr-FR', {
      timeZone: 'Africa/Tunis',
      weekday: 'short',
      day: '2-digit',
      month: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      hour12: false,
    });
  }

  function copy() {
    return language() === 'en' ? {
      banner: (date) => `⚠️ Data from ${date}. The board is no longer reliable — do not depart on this basis.`,
      eyebrow: 'Safety lock',
      title: 'Stale data — do not rely on this board',
      detail: (date) => `Last usable update: ${date}. Wait for a fresh collection before planning an outing.`,
      badge: 'STALE DATA',
    } : {
      banner: (date) => `⚠️ Données du ${date}. Le tableau n'est plus fiable — ne pas partir sur cette base.`,
      eyebrow: 'Verrou de sécurité',
      title: 'Données périmées — ne pas se fier au tableau',
      detail: (date) => `Dernière mise à jour exploitable : ${date}. Attendre une nouvelle collecte avant de planifier une sortie.`,
      badge: 'DONNÉES PÉRIMÉES',
    };
  }

  function installStyles() {
    if (document.getElementById('fable-freshness-styles')) return;
    const style = document.createElement('style');
    style.id = 'fable-freshness-styles';
    style.textContent = `
      .stale-data-banner{margin:0 0 12px;padding:12px 14px;border:1px solid color-mix(in srgb,var(--bad) 70%,var(--br));border-radius:11px;background:color-mix(in srgb,var(--bad) 13%,var(--card));color:var(--fg);font-weight:800;line-height:1.4}
      .go.stale,.family-badge.stale,.family-day-state.stale{filter:grayscale(1);opacity:.62;text-decoration:line-through;background:color-mix(in srgb,var(--muted) 24%,var(--pill-bg))!important;color:var(--muted)!important;border-color:var(--muted)!important}
      body.fable-data-stale .window-line{border-color:color-mix(in srgb,var(--muted) 55%,var(--br))}
      body.fable-data-stale .window-line .small{opacity:.78}
      #family-summary[data-freshness-state="stale"]{border-color:color-mix(in srgb,var(--bad) 70%,var(--br));background:linear-gradient(135deg,color-mix(in srgb,var(--bad) 18%,var(--card)),var(--card) 58%)}
    `;
    document.head.appendChild(style);
  }

  function setBadgeState(stale) {
    const selectors = [
      '.go',
      '.family-badge:not(.blocked)',
      '.family-day.good .family-day-state',
      '.family-day.prudent .family-day-state',
    ];
    document.querySelectorAll(selectors.join(',')).forEach((badge) => {
      badge.classList.toggle('stale', stale);
    });
  }

  function setBanner(stale, status) {
    const card = document.querySelector('.card.wins');
    if (!card) return;
    let banner = card.querySelector('.stale-data-banner');
    if (!stale) {
      banner?.remove();
      return;
    }
    if (!banner) {
      banner = document.createElement('div');
      banner.className = 'stale-data-banner';
      banner.setAttribute('role', 'alert');
      const wins = card.querySelector('#wins');
      card.insertBefore(banner, wins || card.firstChild);
    }
    const message = copy().banner(formatDate(status?.generated_at));
    if (banner.textContent !== message) banner.textContent = message;
  }

  function setStaleHero(stale, status) {
    const summary = document.getElementById('family-summary');
    if (!summary) return;
    if (!stale) {
      summary.removeAttribute('data-freshness-state');
      return;
    }
    if (summary.querySelector('[data-freshness-hero="stale"]')) return;
    const text = copy();
    const date = formatDate(status?.generated_at);
    summary.dataset.freshnessState = 'stale';
    summary.innerHTML = '';

    const main = document.createElement('div');
    main.className = 'family-summary-main';
    main.dataset.freshnessHero = 'stale';

    const message = document.createElement('div');
    const eyebrow = document.createElement('div');
    eyebrow.className = 'family-eyebrow';
    eyebrow.textContent = text.eyebrow;
    const title = document.createElement('h2');
    title.textContent = text.title;
    const detail = document.createElement('div');
    detail.className = 'family-summary-text';
    detail.textContent = text.detail(date);
    message.append(eyebrow, title, detail);

    const actions = document.createElement('div');
    actions.className = 'family-summary-actions';
    const badge = document.createElement('span');
    badge.className = 'family-badge blocked';
    badge.textContent = text.badge;
    actions.appendChild(badge);

    main.append(message, actions);
    summary.appendChild(main);
  }

  function apply(status) {
    currentStatus = status || null;
    const state = freshnessState(currentStatus);
    const stale = !state.fresh;
    document.body.classList.toggle('fable-data-stale', stale);
    document.body.dataset.freshnessState = stale ? 'stale' : 'fresh';
    setBadgeState(stale);
    setBanner(stale, currentStatus);
    setStaleHero(stale, currentStatus);
    window.dispatchEvent(new CustomEvent('fable:freshness', {detail: state}));
  }

  function scheduleApply() {
    if (scheduled || !currentStatus) return;
    scheduled = true;
    queueMicrotask(() => {
      scheduled = false;
      apply(currentStatus);
    });
  }

  async function refresh() {
    try {
      const response = await fetch('status.json', {cache: 'no-store'});
      apply(response.ok ? await response.json() : null);
    } catch {
      apply(null);
    }
  }

  function start() {
    installStyles();
    const observer = new MutationObserver(scheduleApply);
    observer.observe(document.body, {subtree: true, childList: true});
    refresh();
    setInterval(refresh, 60 * 1000);
    document.addEventListener('visibilitychange', () => {
      if (!document.hidden) refresh();
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', start, {once: true});
  } else {
    start();
  }
})();
