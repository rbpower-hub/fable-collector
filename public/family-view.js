/* FABLE Family View — decision-first responsive interface layered over the expert board. */
(function () {
  const MODE_KEY = 'fable_board_mode';
  const TAB_KEY = 'fable_family_tab';
  const VALID_TABS = new Set(['today', 'activities', 'map', 'details']);
  const state = { best: null, windowCount: 0, offshoreCount: 0 };

  const esc = (value) => String(value ?? '').replace(
    /[&<>"']/g,
    (ch) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch])
  );
  const lang = () => (
    localStorage.getItem('lang') || document.documentElement.lang || 'fr'
  ).toLowerCase().startsWith('en') ? 'en' : 'fr';
  const copy = () => lang() === 'en' ? {
    modeFamily: 'Family View', modeExpert: 'Expert View',
    today: 'Today', activities: 'Activities', map: 'Map', details: 'Details',
    nextGo: 'Next family outing', noGo: 'No validated Family GO window',
    strict: 'FAMILY GO', prudent: 'PRUDENT GO', options: 'Options',
    offshore: 'Offshore windows', updated: 'Updated', confidence: 'Confidence',
    seeWindow: 'See window', seeMap: 'Open map', seeActivities: 'See activities',
    seeReasons: 'See reasons', waiting: 'Waiting for the next safe window.',
    noReason: 'Current forecasts do not provide a complete validated family window.',
    reduced: 'Reduced comfort: monitor strengthening conditions and plan an early return.',
    expertHint: 'Advanced forecasts, spot radar and raw feeds remain available in Expert View or Details.',
  } : {
    modeFamily: 'Vue Famille', modeExpert: 'Vue Expert',
    today: 'Aujourd’hui', activities: 'Activités', map: 'Carte', details: 'Détails',
    nextGo: 'Prochaine sortie familiale', noGo: 'Aucune fenêtre Family GO validée',
    strict: 'FAMILY GO', prudent: 'GO PRUDENT', options: 'Options',
    offshore: 'Fenêtres offshore', updated: 'Mise à jour', confidence: 'Confiance',
    seeWindow: 'Voir la fenêtre', seeMap: 'Ouvrir la carte', seeActivities: 'Voir les activités',
    seeReasons: 'Voir les raisons', waiting: 'En attente de la prochaine fenêtre sûre.',
    noReason: 'Les prévisions actuelles ne donnent pas de fenêtre familiale complète et validée.',
    reduced: 'Confort réduit : surveiller le renforcement et prévoir un retour anticipé.',
    expertHint: 'Les prévisions avancées, le radar des spots et les flux bruts restent accessibles dans Vue Expert ou Détails.',
  };

  function installStyles() {
    if (document.getElementById('fable-family-view-styles')) return;
    const style = document.createElement('style');
    style.id = 'fable-family-view-styles';
    style.textContent = `
      #family-board-nav,#family-summary{display:none}
      .family-board-nav{position:sticky;top:0;z-index:900;align-items:center;gap:6px;padding:7px;margin:0 0 14px;border:1px solid var(--br);border-radius:14px;background:color-mix(in srgb,var(--card) 94%,transparent);box-shadow:var(--shadow);backdrop-filter:blur(12px);overflow-x:auto;scrollbar-width:none}
      .family-board-nav::-webkit-scrollbar{display:none}
      .family-tab{min-height:42px;display:inline-flex;align-items:center;justify-content:center;gap:6px;white-space:nowrap;border:0;border-radius:10px;padding:8px 13px;background:transparent;color:var(--muted);font-weight:800;cursor:pointer}
      .family-tab[aria-selected="true"]{background:var(--accent);color:#041019}
      .family-summary{margin-bottom:16px;padding:18px;border:1px solid var(--br);border-radius:16px;background:linear-gradient(135deg,color-mix(in srgb,var(--accent) 13%,var(--card)),var(--card) 52%);box-shadow:var(--shadow)}
      .family-summary-main{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:18px;align-items:center}
      .family-eyebrow{font-size:.78rem;letter-spacing:.08em;text-transform:uppercase;color:var(--section);font-weight:900}
      .family-summary h2{margin:5px 0 5px;font-size:clamp(1.35rem,2.5vw,2rem);line-height:1.15}
      .family-summary-text{color:var(--muted);line-height:1.45}
      .family-badge{display:inline-flex;align-items:center;border-radius:999px;padding:5px 10px;font-size:.78rem;font-weight:900;background:var(--ok);color:#04110a}
      .family-badge.prudent{background:var(--warn);color:#160f04}
      .family-badge.blocked{background:color-mix(in srgb,var(--bad) 18%,var(--pill-bg));color:var(--bad);border:1px solid color-mix(in srgb,var(--bad) 55%,var(--br))}
      .family-summary-actions{display:flex;flex-wrap:wrap;justify-content:flex-end;gap:8px;max-width:340px}
      .family-action{min-height:42px;border:1px solid var(--br);border-radius:999px;padding:8px 13px;background:var(--pill-bg);color:var(--fg);font-weight:800;cursor:pointer}
      .family-action.primary{background:var(--accent);color:#041019;border-color:transparent}
      .family-kpis{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:9px;margin-top:15px}
      .family-kpi{border:1px solid var(--br);border-radius:11px;padding:9px 11px;background:color-mix(in srgb,var(--pill-bg) 78%,transparent)}
      .family-kpi span{display:block;color:var(--muted);font-size:.76rem;margin-bottom:2px}.family-kpi strong{font-size:.98rem}
      .family-summary-hint{margin-top:11px;color:var(--muted);font-size:.78rem}

      body.family-board-mode #family-board-nav{display:flex}
      body.family-board-mode[data-family-tab="today"] #family-summary{display:block}
      body.family-board-mode .card.wins,body.family-board-mode .card.conditions,body.family-board-mode .card.radar{max-height:none;overflow:visible}
      body.family-board-mode[data-family-tab="today"] #map,
      body.family-board-mode[data-family-tab="today"] .map-toolbar,
      body.family-board-mode[data-family-tab="today"] .card.radar,
      body.family-board-mode[data-family-tab="today"] #fable-activities,
      body.family-board-mode[data-family-tab="today"] #port-knowledge-card{display:none!important}
      body.family-board-mode[data-family-tab="today"] .layout-grid.threecol{display:grid;grid-template-columns:minmax(0,1.25fr) minmax(300px,.75fr);gap:16px}

      body.family-board-mode[data-family-tab="activities"] #map,
      body.family-board-mode[data-family-tab="activities"] .map-toolbar,
      body.family-board-mode[data-family-tab="activities"] .layout-grid.threecol,
      body.family-board-mode[data-family-tab="activities"] #port-knowledge-card{display:none!important}
      body.family-board-mode[data-family-tab="activities"] #fable-activities{display:block!important;margin-top:0}

      body.family-board-mode[data-family-tab="map"] .layout-grid.threecol,
      body.family-board-mode[data-family-tab="map"] #fable-activities{display:none!important}
      body.family-board-mode[data-family-tab="map"] #map{display:block!important;height:min(62vh,610px);min-height:330px}
      body.family-board-mode[data-family-tab="map"] .map-toolbar{display:flex!important}
      body.family-board-mode[data-family-tab="map"] #port-knowledge-card{display:block!important}

      body.family-board-mode[data-family-tab="details"] #map,
      body.family-board-mode[data-family-tab="details"] .map-toolbar,
      body.family-board-mode[data-family-tab="details"] .card.wins,
      body.family-board-mode[data-family-tab="details"] .card.conditions,
      body.family-board-mode[data-family-tab="details"] #fable-activities,
      body.family-board-mode[data-family-tab="details"] #port-knowledge-card{display:none!important}
      body.family-board-mode[data-family-tab="details"] .layout-grid.threecol{display:grid;grid-template-columns:minmax(0,1fr)}
      body.family-board-mode[data-family-tab="details"] .card.radar{display:block!important}

      body.expert-board-mode #family-board-nav,body.expert-board-mode #family-summary{display:none!important}
      body.family-board-mode .hdr-tools{min-width:0}

      @media(max-width:900px){
        body{padding:calc(14px + env(safe-area-inset-top)) 12px 18px}
        .app-header{align-items:flex-start;gap:10px}.app-header h1{font-size:1.25rem;width:100%;white-space:normal}
        .hdr-tools{width:100%;overflow-x:auto;padding-bottom:3px;gap:7px;scrollbar-width:none}.hdr-tools::-webkit-scrollbar{display:none}
        .hdr-tools>*{flex:0 0 auto}#gen{display:none}
        .family-board-nav{margin-left:-2px;margin-right:-2px;top:4px}
        .family-summary{padding:14px}.family-summary-main{grid-template-columns:1fr}.family-summary-actions{justify-content:flex-start;max-width:none}
        .family-kpis{grid-template-columns:1fr 1fr}.family-kpi:last-child{grid-column:1/-1}
        body.family-board-mode[data-family-tab="today"] .layout-grid.threecol{grid-template-columns:1fr}
        body.family-board-mode[data-family-tab="map"] #map{height:48dvh;min-height:300px}
        .activity-grid{grid-template-columns:1fr!important}
      }
      @media(max-width:520px){
        .family-tab{padding:8px 10px;font-size:.9rem}.family-tab .family-tab-label{display:none}
        .family-tab::after{content:attr(data-short);font-size:.84rem}
        .family-summary-actions{display:grid;grid-template-columns:1fr 1fr;width:100%}.family-action{width:100%}
        .family-kpis{grid-template-columns:1fr}.family-kpi:last-child{grid-column:auto}
        .card{padding:13px;border-radius:12px}.window-line{padding:10px}.window-line .title{font-size:1rem;flex-wrap:wrap}
      }
    `;
    document.head.appendChild(style);
  }

  function formatDateTime(iso) {
    const date = new Date(iso);
    if (Number.isNaN(date.getTime())) return String(iso || '—');
    return date.toLocaleString(lang() === 'en' ? 'en-GB' : 'fr-FR', {
      weekday:'short', day:'2-digit', month:'2-digit', hour:'2-digit', minute:'2-digit', hour12:false,
    });
  }

  function flattenWindows(data) {
    const coastal = [];
    let offshoreCount = 0;
    (data?.windows || []).forEach((destination) => {
      (destination?.windows || []).forEach((windowItem) => {
        const tripMode = windowItem?.trip_mode || destination?.trip_mode || '';
        const row = { destination, windowItem };
        if (tripMode === 'one_way_multi_day') offshoreCount += 1;
        else if (windowItem?.start && windowItem?.end) coastal.push(row);
      });
    });
    coastal.sort((a, b) => {
      const tierA = (a.windowItem.family_tier || a.destination.family_tier) === 'prudent' ? 1 : 0;
      const tierB = (b.windowItem.family_tier || b.destination.family_tier) === 'prudent' ? 1 : 0;
      return tierA - tierB || new Date(a.windowItem.start) - new Date(b.windowItem.start);
    });
    return { coastal, offshoreCount };
  }

  function bestBlocker(data) {
    const candidates = (data?.windows || [])
      .filter((destination) => !(destination?.windows || []).length && destination?.diagnostics)
      .map((destination) => {
        const near = destination.diagnostics.near_miss || {};
        const required = Number(near.required_hours || destination.required_hours || 0);
        const validated = Number(near.validated_hours || 0);
        return { destination, score: required > 0 ? validated / required : 0 };
      })
      .sort((a, b) => b.score - a.score);
    return candidates[0]?.destination || null;
  }

  function renderTabs() {
    const c = copy();
    const nav = document.getElementById('family-board-nav');
    if (!nav) return;
    const labels = {
      today: ['☀️', c.today, c.today], activities: ['🌊', c.activities, c.activities],
      map: ['🗺️', c.map, c.map], details: ['⚙️', c.details, c.details],
    };
    nav.querySelectorAll('[data-family-tab]').forEach((button) => {
      const values = labels[button.dataset.familyTab];
      button.innerHTML = `<span aria-hidden="true">${values[0]}</span><span class="family-tab-label">${esc(values[1])}</span>`;
      button.dataset.short = values[2];
    });
  }

  function setTab(tab, persist = true) {
    const next = VALID_TABS.has(tab) ? tab : 'today';
    document.body.dataset.familyTab = next;
    if (persist) localStorage.setItem(TAB_KEY, next);
    document.querySelectorAll('[data-family-tab]').forEach((button) => {
      const active = button.dataset.familyTab === next;
      button.setAttribute('aria-selected', active ? 'true' : 'false');
      button.tabIndex = active ? 0 : -1;
    });
    if (next === 'map') setTimeout(() => window.dispatchEvent(new Event('resize')), 100);
  }

  function setMode(mode, persist = true) {
    const next = mode === 'expert' ? 'expert' : 'family';
    document.body.classList.toggle('family-board-mode', next === 'family');
    document.body.classList.toggle('expert-board-mode', next === 'expert');
    document.body.classList.remove('simplified-view');
    if (persist) localStorage.setItem(MODE_KEY, next);
    const button = document.getElementById('viewToggleBtn');
    if (button) {
      const c = copy();
      button.textContent = next === 'family' ? `🧰 ${c.modeExpert}` : `👨‍👩‍👧 ${c.modeFamily}`;
      button.setAttribute('aria-pressed', next === 'expert' ? 'true' : 'false');
    }
    if (next === 'family') setTab(localStorage.getItem(TAB_KEY) || 'today', false);
    else setTimeout(() => window.dispatchEvent(new Event('resize')), 100);
  }

  function findWindowElement(best) {
    if (!best) return null;
    return Array.from(document.querySelectorAll('.window-line')).find((element) => (
      element.dataset.slug === best.destination.dest_slug &&
      element.dataset.start === best.windowItem.start &&
      element.dataset.end === best.windowItem.end
    )) || null;
  }

  function focusBest(openMap) {
    const element = findWindowElement(state.best);
    if (!element) return;
    setTab('today');
    element.scrollIntoView({behavior:'smooth', block:'center'});
    if (openMap) {
      element.click();
      setTimeout(() => setTab('map'), 120);
    }
  }

  function renderSummary(windows, recommendations, status) {
    const summary = document.getElementById('family-summary');
    if (!summary) return;
    const c = copy();
    const { coastal, offshoreCount } = flattenWindows(windows);
    state.best = coastal[0] || null;
    state.windowCount = coastal.length;
    state.offshoreCount = offshoreCount;
    const generatedAt = windows?.generated_at || status?.generated_at;
    const recommendationCount = Array.isArray(recommendations?.recommendations)
      ? recommendations.recommendations.length : 0;

    if (state.best) {
      const destination = state.best.destination;
      const item = state.best.windowItem;
      const prudent = (item.family_tier || destination.family_tier) === 'prudent';
      const confidence = item.confidence || destination.confidence || '—';
      const caution = prudent
        ? (lang() === 'en' ? item.caution_en : item.caution_fr) || c.reduced
        : `${formatDateTime(item.start)} → ${formatDateTime(item.end)}`;
      summary.innerHTML = `
        <div class="family-summary-main">
          <div>
            <div class="family-eyebrow">${esc(c.nextGo)}</div>
            <h2>${esc(destination.dest_name || destination.dest_slug || '—')}</h2>
            <div class="family-summary-text">${esc(caution)}</div>
          </div>
          <div class="family-summary-actions">
            <span class="family-badge ${prudent ? 'prudent' : ''}">${esc(prudent ? c.prudent : c.strict)}</span>
            <button class="family-action primary" data-family-action="window">${esc(c.seeWindow)}</button>
            <button class="family-action" data-family-action="map">${esc(c.seeMap)}</button>
            ${recommendationCount ? `<button class="family-action" data-family-action="activities">${esc(c.seeActivities)}</button>` : ''}
          </div>
        </div>
        <div class="family-kpis">
          <div class="family-kpi"><span>${esc(c.options)}</span><strong>${coastal.length}</strong></div>
          <div class="family-kpi"><span>${esc(c.confidence)}</span><strong>${esc(String(confidence))}</strong></div>
          <div class="family-kpi"><span>${esc(c.updated)}</span><strong>${esc(generatedAt ? formatDateTime(generatedAt) : '—')}</strong></div>
        </div>
        ${offshoreCount ? `<div class="family-summary-hint">${esc(c.offshore)} : ${offshoreCount}</div>` : ''}
        <div class="family-summary-hint">${esc(c.expertHint)}</div>`;
      return;
    }

    const blocked = bestBlocker(windows);
    const diagnostics = blocked?.diagnostics || {};
    const reason = lang() === 'en'
      ? diagnostics.summary_en || diagnostics.first_blocker?.reason_en
      : diagnostics.summary_fr || diagnostics.first_blocker?.reason_fr;
    summary.innerHTML = `
      <div class="family-summary-main">
        <div>
          <div class="family-eyebrow">${esc(c.waiting)}</div>
          <h2>${esc(c.noGo)}</h2>
          <div class="family-summary-text">${esc(reason || c.noReason)}</div>
        </div>
        <div class="family-summary-actions">
          <span class="family-badge blocked">NO-GO</span>
          <button class="family-action primary" data-family-action="reasons">${esc(c.seeReasons)}</button>
          <button class="family-action" data-family-action="map-tab">${esc(c.seeMap)}</button>
        </div>
      </div>
      <div class="family-kpis">
        <div class="family-kpi"><span>${esc(c.options)}</span><strong>0</strong></div>
        <div class="family-kpi"><span>${esc(c.offshore)}</span><strong>${offshoreCount}</strong></div>
        <div class="family-kpi"><span>${esc(c.updated)}</span><strong>${esc(generatedAt ? formatDateTime(generatedAt) : '—')}</strong></div>
      </div>
      <div class="family-summary-hint">${esc(c.expertHint)}</div>`;
  }

  async function refreshSummary() {
    try {
      const [windowsResponse, recommendationsResponse, statusResponse] = await Promise.all([
        fetch('windows.json', {cache:'no-store'}),
        fetch('recommendations.json', {cache:'no-store'}),
        fetch('status.json', {cache:'no-store'}),
      ]);
      renderSummary(
        windowsResponse.ok ? await windowsResponse.json() : {},
        recommendationsResponse.ok ? await recommendationsResponse.json() : {},
        statusResponse.ok ? await statusResponse.json() : {}
      );
    } catch {
      renderSummary({}, {}, {});
    }
  }

  function buildUI() {
    installStyles();
    const header = document.querySelector('.app-header');
    const dashboard = document.getElementById('dashboard-content');
    if (!header || !dashboard) return;

    if (!document.getElementById('family-board-nav')) {
      const nav = document.createElement('nav');
      nav.id = 'family-board-nav';
      nav.className = 'family-board-nav';
      nav.setAttribute('aria-label', 'FABLE family navigation');
      ['today', 'activities', 'map', 'details'].forEach((tab) => {
        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'family-tab';
        button.dataset.familyTab = tab;
        button.setAttribute('role', 'tab');
        nav.appendChild(button);
      });
      header.insertAdjacentElement('afterend', nav);
      nav.addEventListener('click', (event) => {
        const button = event.target.closest('[data-family-tab]');
        if (button) setTab(button.dataset.familyTab);
      });
    }

    if (!document.getElementById('family-summary')) {
      const summary = document.createElement('section');
      summary.id = 'family-summary';
      summary.className = 'family-summary';
      summary.setAttribute('aria-live', 'polite');
      dashboard.insertAdjacentElement('beforebegin', summary);
      summary.addEventListener('click', (event) => {
        const action = event.target.closest('[data-family-action]')?.dataset.familyAction;
        if (action === 'window') focusBest(false);
        if (action === 'map') focusBest(true);
        if (action === 'activities') setTab('activities');
        if (action === 'map-tab') setTab('map');
        if (action === 'reasons') {
          setTab('today');
          setTimeout(() => document.querySelector('.card.conditions')?.scrollIntoView({behavior:'smooth'}), 80);
        }
      });
    }

    const modeButton = document.getElementById('viewToggleBtn');
    if (modeButton && !modeButton.dataset.familyViewBound) {
      modeButton.dataset.familyViewBound = '1';
      modeButton.addEventListener('click', (event) => {
        event.preventDefault();
        event.stopImmediatePropagation();
        const current = document.body.classList.contains('family-board-mode') ? 'family' : 'expert';
        setMode(current === 'family' ? 'expert' : 'family');
      }, true);
    }

    document.getElementById('langToggle')?.addEventListener('click', () => {
      setTimeout(() => { renderTabs(); setMode(localStorage.getItem(MODE_KEY) || 'family', false); refreshSummary(); }, 0);
    });

    renderTabs();
    setMode(localStorage.getItem(MODE_KEY) || 'family', false);
    setTab(localStorage.getItem(TAB_KEY) || 'today', false);
    refreshSummary();
    setInterval(refreshSummary, 10 * 60 * 1000);
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', buildUI, {once:true});
  else buildUI();
})();
