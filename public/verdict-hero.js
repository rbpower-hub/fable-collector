/* FABLE family verdict hero — presentation only, all decisions come from windows.json. */
(function () {
  const TUNIS_TZ = 'Africa/Tunis';
  let verdictModule = null;
  let planningObserver = null;

  const language = () => (
    localStorage.getItem('lang') || document.documentElement.lang || 'fr'
  ).toLowerCase().startsWith('en') ? 'en' : 'fr';

  const copy = () => language() === 'en' ? {
    eyebrow: 'Today’s family verdict', stale: 'Stale data — do not rely on this board',
    staleDetail: 'Wait for a fresh collection before planning an outing.',
    noData: 'Data unavailable — do not rely on this board',
    noDataDetail: 'The safety window file could not be loaded.',
    goToday: 'A family outing is possible today', goSoon: 'Not today — next safe family window',
    noGo: 'No family outing in the forecast horizon',
    noReason: 'No complete safe family window was detected.',
    openMap: 'View on the map', seeReasons: 'See why', strict: 'FAMILY GO', prudent: 'PRUDENT GO',
    staleBadge: 'STALE DATA', noDataBadge: 'NO DATA', noGoBadge: 'NO-GO',
    confidence: {
      high: ['●●●', 'very good reliability'], medium: ['●●○', 'good reliability'],
      low: ['●○○', 'limited reliability — reconfirm before departure'],
    },
  } : {
    eyebrow: 'Verdict famille du jour', stale: 'Données périmées — ne pas se fier au tableau',
    staleDetail: 'Attendre une nouvelle collecte avant de planifier une sortie.',
    noData: 'Données indisponibles — ne pas se fier au tableau',
    noDataDetail: 'Le fichier des fenêtres de sécurité n’a pas pu être chargé.',
    goToday: 'Une sortie familiale est possible aujourd’hui',
    goSoon: 'Pas aujourd’hui — prochaine fenêtre familiale sûre',
    noGo: 'Pas de sortie famille sur l’horizon météo',
    noReason: 'Aucune fenêtre familiale complète et sûre n’a été détectée.',
    openMap: 'Voir sur la carte', seeReasons: 'Voir pourquoi', strict: 'FAMILY GO', prudent: 'GO PRUDENT',
    staleBadge: 'DONNÉES PÉRIMÉES', noDataBadge: 'DONNÉES ABSENTES', noGoBadge: 'NO-GO',
    confidence: {
      high: ['●●●', 'fiabilité très bonne'], medium: ['●●○', 'fiabilité bonne'],
      low: ['●○○', 'fiabilité limitée — à reconfirmer avant de partir'],
    },
  };

  function dateTime(value, timeOnly = false) {
    const date = new Date(value || '');
    if (!Number.isFinite(date.getTime())) return '—';
    const locale = language() === 'en' ? 'en-GB' : 'fr-FR';
    const options = timeOnly
      ? {timeZone: TUNIS_TZ, hour: '2-digit', minute: '2-digit', hour12: false}
      : {timeZone: TUNIS_TZ, weekday: 'short', day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit', hour12: false};
    return timeOnly ? date.toLocaleTimeString(locale, options) : date.toLocaleString(locale, options);
  }

  async function loadJson(path) {
    try {
      const response = await fetch(path, {cache: 'no-store'});
      return response.ok ? {ok: true, data: await response.json()} : {ok: false, data: null};
    } catch {
      return {ok: false, data: null};
    }
  }

  function installStyles() {
    if (document.getElementById('fable-verdict-styles')) return;
    const style = document.createElement('style');
    style.id = 'fable-verdict-styles';
    style.textContent = `
      #family-verdict-hero,#family-planning-host{display:none}body.family-board-mode #family-verdict-hero{display:block}body.family-board-mode #family-summary{display:none!important}body.family-board-mode #family-planning-host:not(:empty){display:block}
      .family-verdict{margin:0 0 14px;padding:18px;border:1px solid var(--br);border-radius:17px;background:linear-gradient(135deg,color-mix(in srgb,var(--ok) 14%,var(--card)),var(--card) 58%);box-shadow:var(--shadow)}
      .family-verdict[data-state="GO_SOON"],.family-verdict[data-state="NO_GO"]{background:linear-gradient(135deg,color-mix(in srgb,var(--warn) 15%,var(--card)),var(--card) 58%);border-color:color-mix(in srgb,var(--warn) 58%,var(--br))}
      .family-verdict[data-state="STALE"],.family-verdict[data-state="NO_DATA"]{background:linear-gradient(135deg,color-mix(in srgb,var(--bad) 18%,var(--card)),var(--card) 58%);border-color:color-mix(in srgb,var(--bad) 68%,var(--br))}
      .verdict-grid{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:18px;align-items:center}.verdict-eyebrow{font-size:.76rem;text-transform:uppercase;letter-spacing:.09em;font-weight:900;color:var(--section)}
      .family-verdict h2{margin:5px 0;font-size:clamp(1.45rem,2.8vw,2.25rem);line-height:1.12}.verdict-detail{color:var(--muted);font-size:1rem;line-height:1.45}.verdict-confidence{margin-top:8px;font-weight:800}
      .verdict-actions{display:flex;align-items:center;justify-content:flex-end;flex-wrap:wrap;gap:8px}.verdict-badge{display:inline-flex;padding:6px 11px;border-radius:999px;background:var(--ok);color:#04110a;font-weight:900;font-size:.78rem}
      .family-verdict[data-state="GO_SOON"] .verdict-badge,.family-verdict[data-state="NO_GO"] .verdict-badge{background:var(--warn);color:#1a1002}.family-verdict[data-state="STALE"] .verdict-badge,.family-verdict[data-state="NO_DATA"] .verdict-badge{background:var(--bad);color:#fff}
      .verdict-button{min-height:44px;border:1px solid var(--br);border-radius:999px;padding:9px 14px;background:var(--pill-bg);color:var(--fg);font-weight:900;cursor:pointer}.verdict-button.primary{background:var(--accent);color:#041019;border-color:transparent}
      #family-planning-host{margin-bottom:15px;padding:16px;border:1px solid var(--br);border-radius:15px;background:var(--card);box-shadow:var(--shadow)}#family-planning-host .family-planning{margin:0;padding:0;border:0}
      @media(max-width:640px){.family-verdict{padding:15px}.verdict-grid{grid-template-columns:1fr}.verdict-actions{justify-content:flex-start}.verdict-button{width:100%}.verdict-badge{order:-1}.family-verdict h2{font-size:1.5rem}}
    `;
    document.head.appendChild(style);
  }

  function ensureContainers() {
    const summary = document.getElementById('family-summary');
    const nav = document.getElementById('family-board-nav');
    if (!summary && !nav) return null;
    let hero = document.getElementById('family-verdict-hero');
    if (!hero) {
      hero = document.createElement('section');
      hero.id = 'family-verdict-hero';
      hero.className = 'family-verdict';
      hero.setAttribute('aria-live', 'polite');
      (summary || nav).insertAdjacentElement('afterend', hero);
    }
    let planningHost = document.getElementById('family-planning-host');
    if (!planningHost) {
      planningHost = document.createElement('section');
      planningHost.id = 'family-planning-host';
      hero.insertAdjacentElement('afterend', planningHost);
    }
    return {hero, planningHost, summary};
  }

  function movePlanning() {
    const containers = ensureContainers();
    const planning = containers?.summary?.querySelector('.family-planning');
    if (planning) containers.planningHost.replaceChildren(planning);
  }

  function button(label, action, primary = false) {
    const node = document.createElement('button');
    node.type = 'button';
    node.className = `verdict-button${primary ? ' primary' : ''}`;
    node.dataset.verdictAction = action;
    node.textContent = label;
    return node;
  }

  function render(verdict) {
    const containers = ensureContainers();
    if (!containers) return;
    const {hero} = containers;
    const text = copy();
    hero.dataset.state = verdict.state;
    hero.replaceChildren();
    const grid = document.createElement('div');
    grid.className = 'verdict-grid';
    const message = document.createElement('div');
    const eyebrow = document.createElement('div');
    eyebrow.className = 'verdict-eyebrow';
    eyebrow.textContent = text.eyebrow;
    const title = document.createElement('h2');
    const detail = document.createElement('div');
    detail.className = 'verdict-detail';
    const actions = document.createElement('div');
    actions.className = 'verdict-actions';
    const badge = document.createElement('span');
    badge.className = 'verdict-badge';

    if (['GO_TODAY', 'GO_SOON'].includes(verdict.state)) {
      const item = verdict.window;
      const name = verdict.spot?.dest_name || verdict.spot?.name || verdict.spot?.dest_slug || '—';
      const prudent = String(item?.family_tier || '').toLowerCase() === 'prudent';
      title.textContent = verdict.state === 'GO_TODAY' ? text.goToday : text.goSoon;
      detail.textContent = verdict.state === 'GO_TODAY'
        ? `${name} · ${dateTime(item.start, true)} → ${dateTime(item.end, true)}`
        : `${name} · ${dateTime(item.start)} → ${dateTime(item.end, true)}`;
      badge.textContent = prudent ? text.prudent : text.strict;
      const confidence = text.confidence[String(item?.confidence || verdict.args?.confidence || 'low').toLowerCase()] || text.confidence.low;
      const reliability = document.createElement('div');
      reliability.className = 'verdict-confidence';
      reliability.textContent = `${confidence[0]} · ${confidence[1]}`;
      message.append(eyebrow, title, detail, reliability);
      actions.append(badge, button(text.openMap, 'map', true));
    } else {
      const stateCopy = {
        STALE: [text.stale, text.staleDetail, text.staleBadge],
        NO_DATA: [text.noData, text.noDataDetail, text.noDataBadge],
        NO_GO: [text.noGo, language() === 'en' ? verdict.args?.reason_en || text.noReason : verdict.args?.reason_fr || text.noReason, text.noGoBadge],
      }[verdict.state] || [text.noGo, text.noReason, text.noGoBadge];
      title.textContent = stateCopy[0];
      detail.textContent = stateCopy[1];
      badge.textContent = stateCopy[2];
      message.append(eyebrow, title, detail);
      actions.appendChild(badge);
      if (verdict.state === 'NO_GO') actions.appendChild(button(text.seeReasons, 'reasons', true));
    }

    grid.append(message, actions);
    hero.appendChild(grid);
    hero.dataset.slug = verdict.spot?.dest_slug || '';
    hero.dataset.start = verdict.window?.start || '';
    hero.dataset.end = verdict.window?.end || '';
  }

  function focusMap() {
    const hero = document.getElementById('family-verdict-hero');
    const card = Array.from(document.querySelectorAll('.window-line')).find((element) => (
      element.dataset.slug === hero?.dataset.slug && element.dataset.start === hero?.dataset.start && element.dataset.end === hero?.dataset.end
    ));
    card?.click();
    document.querySelector('[data-family-tab="map"]')?.click();
    setTimeout(() => document.getElementById('map')?.scrollIntoView({behavior: 'smooth', block: 'start'}), 150);
  }

  async function refresh() {
    verdictModule ||= await import('./js/verdict.js');
    const [windowsResult, statusResult, rulesResult] = await Promise.all([
      loadJson('windows.json'), loadJson('status.json'), loadJson('rules.normalized.json'),
    ]);
    render(verdictModule.computeVerdict({
      windows: windowsResult.ok ? windowsResult.data : null,
      status: statusResult.ok ? statusResult.data : null,
      rules: rulesResult.ok ? rulesResult.data : {},
      now: new Date(),
    }));
    movePlanning();
  }

  function start() {
    installStyles();
    ensureContainers();
    const summary = document.getElementById('family-summary');
    if (summary && !planningObserver) {
      planningObserver = new MutationObserver(movePlanning);
      planningObserver.observe(summary, {childList: true, subtree: true});
    }
    document.addEventListener('click', (event) => {
      const action = event.target.closest('[data-verdict-action]')?.dataset.verdictAction;
      if (action === 'map') focusMap();
      if (action === 'reasons') {
        document.querySelector('[data-family-tab="today"]')?.click();
        setTimeout(() => document.querySelector('.card.conditions')?.scrollIntoView({behavior: 'smooth'}), 80);
      }
    });
    document.getElementById('langToggle')?.addEventListener('click', () => setTimeout(refresh, 0));
    document.addEventListener('visibilitychange', () => { if (!document.hidden) refresh(); });
    refresh();
    setInterval(refresh, 60 * 1000);
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start, {once: true});
  else start();
})();
