/* FABLE family/expert content gate — presentation only. */
(function () {
  const state = {sites: {}, windows: new Map(), spots: new Map()};
  let scheduled = false;

  const language = () => (
    localStorage.getItem('lang') || document.documentElement.lang || 'fr'
  ).toLowerCase().startsWith('en') ? 'en' : 'fr';

  const copy = () => language() === 'en' ? {
    qualityLabel: 'Forecast quality', confidence: {
      high: 'Very good', medium: 'Good', low: 'Limited — reconfirm before departure',
    },
    agreement: (count) => `✓ ${count} weather models agree`,
    marineMissing: '⚠️ Wave data unavailable — windows are not confirmed',
    longTrips: '🧭 Long trips',
  } : {
    qualityLabel: 'Qualité des prévisions', confidence: {
      high: 'Très bonne', medium: 'Bonne', low: 'Limitée — à reconfirmer avant de partir',
    },
    agreement: (count) => `✓ ${count} modèles météo d’accord`,
    marineMissing: '⚠️ Données de vagues indisponibles — fenêtres non confirmées',
    longTrips: '🧭 Trajets longs',
  };

  async function json(path) {
    try {
      const response = await fetch(path, {cache: 'no-store'});
      return response.ok ? await response.json() : null;
    } catch {
      return null;
    }
  }

  function installStyles() {
    if (document.getElementById('fable-content-gate-styles')) return;
    const style = document.createElement('style');
    style.id = 'fable-content-gate-styles';
    style.textContent = `
      body.family-board-mode .expert-only{display:none!important}
      body.expert-board-mode .family-only{display:none!important}
      .family-reliability,.family-model-agreement,.family-marine-warning{margin-top:5px;font-size:.83rem;color:var(--muted);line-height:1.35}
      .family-reliability{--quality-color:#60a5fa;display:flex;align-items:center;flex-wrap:wrap;gap:7px;font-weight:700}.family-reliability[data-quality-level="high"]{--quality-color:var(--ok)}.family-reliability[data-quality-level="medium"]{--quality-color:var(--warn)}.family-reliability .quality-label{color:var(--quality-color);font-size:.88rem;font-weight:900}.family-reliability .quality-bars{display:inline-flex;align-items:flex-end;gap:3px;height:17px;color:var(--quality-color)}.family-reliability .quality-bars i{display:block;width:4px;border-radius:2px;background:color-mix(in srgb,currentColor 22%,transparent)}.family-reliability .quality-bars i:nth-child(1){height:7px}.family-reliability .quality-bars i:nth-child(2){height:11px}.family-reliability .quality-bars i:nth-child(3){height:16px}.family-reliability[data-quality-level="low"] .quality-bars i:nth-child(1),.family-reliability[data-quality-level="medium"] .quality-bars i:nth-child(-n+2),.family-reliability[data-quality-level="high"] .quality-bars i{background:currentColor}.family-marine-warning{color:var(--warn);font-weight:800}
      .family-long-trips{margin-top:14px;border-top:1px solid var(--br);padding-top:10px}.family-long-trips>summary{cursor:pointer;font-weight:900;color:var(--section)}
      .family-long-trips .trip-planner{margin-top:10px}
    `;
    document.head.appendChild(style);
  }

  function setText(node, value) {
    if (node && node.textContent !== value) node.textContent = value;
  }

  function isLongTrip(slug) {
    const site = state.sites[slug] || {};
    const kind = String(site.route_kind || '').toLowerCase();
    return Boolean(site.beta) || kind.includes('one_way') || kind.includes('offshore') || kind.includes('composite');
  }

  function technicalSmall(node) {
    const text = String(node.textContent || '').trim();
    return /(^|\s)(Src:|Δ:|ΔHs\b|Vent x\d|Houle x\d|Vent:\s*\S+|Houle:\s*\S+)/i.test(text);
  }

  function windowRecord(line) {
    return state.windows.get(`${line.dataset.slug}|${line.dataset.start}|${line.dataset.end}|${line.dataset.direction || ''}`) || null;
  }

  function applyWindow(line) {
    const slug = line.dataset.slug || '';
    // Long directional trips are first-class Family navigation windows.
    // Technical source details remain expert-only, but the card itself stays visible.
    line.classList.remove('expert-only');
    const title = line.querySelector('.title');
    const conf = title?.querySelector('.conf');
    conf?.classList.add('expert-only');

    let reliability = line.querySelector('.family-reliability');
    const confKey = Array.from(conf?.classList || []).find((value) => ['high', 'medium', 'low'].includes(value)) || 'low';
    if (!reliability && title) {
      reliability = document.createElement('div');
      reliability.className = 'family-reliability family-only';
      title.insertAdjacentElement('afterend', reliability);
    }
    const quality = copy().confidence[confKey] || copy().confidence.low;
    const qualitySignature = `${language()}|${confKey}`;
    if (reliability.dataset.qualitySignature !== qualitySignature) {
      reliability.dataset.qualityLevel = confKey;
      reliability.dataset.qualitySignature = qualitySignature;
      reliability.setAttribute('aria-label', `${copy().qualityLabel}: ${quality}`);
      reliability.innerHTML = `<span>${copy().qualityLabel}</span><span class="quality-bars" aria-hidden="true"><i></i><i></i><i></i></span><strong class="quality-label">${quality}</strong>`;
    }

    line.querySelectorAll('.small').forEach((node) => {
      if (!node.classList.contains('family-only') && technicalSmall(node)) node.classList.add('expert-only');
    });

    const record = windowRecord(line);
    const details = record?.confidence_details || {};
    const windModels = Number(details.min_wind_models_per_hour || 0);
    const waveModels = Number(details.min_wave_sources_per_hour || 0);
    const agreed = Math.min(windModels, waveModels);
    let agreement = line.querySelector('.family-model-agreement');
    if (agreed >= 2) {
      if (!agreement) {
        agreement = document.createElement('div');
        agreement.className = 'family-model-agreement family-only';
        line.appendChild(agreement);
      }
      setText(agreement, copy().agreement(agreed));
    } else {
      agreement?.remove();
    }

    const marineError = state.spots.get(slug)?.meta?.debug?.marine_error;
    let warning = line.querySelector('.family-marine-warning');
    if (marineError) {
      if (!warning) {
        warning = document.createElement('div');
        warning.className = 'family-marine-warning family-only';
        line.appendChild(warning);
      }
      setText(warning, copy().marineMissing);
      warning.title = String(marineError);
    } else {
      warning?.remove();
    }
  }

  function moveLongTrips() {
    const planner = document.querySelector('#family-planning-host .trip-planner');
    const radar = document.querySelector('.card.radar');
    if (!planner || !radar) return;
    let details = radar.querySelector('.family-long-trips');
    if (!details) {
      details = document.createElement('details');
      details.className = 'family-long-trips family-only';
      const summary = document.createElement('summary');
      details.appendChild(summary);
      radar.appendChild(details);
    }
    setText(details.querySelector('summary'), copy().longTrips);
    if (planner.parentElement !== details) details.appendChild(planner);
  }

  function apply() {
    document.querySelector('#raw-links-list')?.closest('details')?.classList.add('expert-only');
    document.querySelectorAll('.window-line').forEach(applyWindow);
    moveLongTrips();
  }

  function scheduleApply() {
    if (scheduled) return;
    scheduled = true;
    requestAnimationFrame(() => {
      scheduled = false;
      apply();
    });
  }

  async function refreshData() {
    const [sites, windows] = await Promise.all([json('sites.normalized.json'), json('windows.json')]);
    state.sites = Object.fromEntries((sites?.sites || []).map((site) => [site.path, site]));
    state.windows.clear();
    (windows?.windows || []).forEach((destination) => {
      (destination?.windows || []).forEach((item) => {
        state.windows.set(`${destination.dest_slug}|${item.start}|${item.end}|${item.direction || ''}`, item);
      });
    });
    const slugs = Object.keys(state.sites);
    const spotPayloads = await Promise.all(slugs.map((slug) => json(slug)));
    state.spots = new Map(slugs.map((slug, index) => [slug, spotPayloads[index] || {}]));
    apply();
  }

  function start() {
    installStyles();
    const observer = new MutationObserver(scheduleApply);
    observer.observe(document.body, {childList: true, subtree: true});
    document.getElementById('langToggle')?.addEventListener('click', () => setTimeout(apply, 0));
    refreshData();
    setInterval(refreshData, 10 * 60 * 1000);
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start, {once: true});
  else start();
})();
