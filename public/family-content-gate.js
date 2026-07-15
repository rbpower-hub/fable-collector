/* FABLE family/expert content gate — presentation only. */
(function () {
  const state = {sites: {}, windows: new Map(), spots: new Map()};
  let scheduled = false;

  const language = () => (
    localStorage.getItem('lang') || document.documentElement.lang || 'fr'
  ).toLowerCase().startsWith('en') ? 'en' : 'fr';

  const copy = () => language() === 'en' ? {
    confidence: {
      high: '●●● · very good reliability',
      medium: '●●○ · good reliability',
      low: '●○○ · limited reliability — reconfirm before departure',
    },
    agreement: (count) => `✓ ${count} weather models agree`,
    marineMissing: '⚠️ Wave data unavailable — windows are not confirmed',
    longTrips: '🧭 Long trips',
  } : {
    confidence: {
      high: '●●● · fiabilité très bonne',
      medium: '●●○ · fiabilité bonne',
      low: '●○○ · fiabilité limitée — à reconfirmer avant de partir',
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
      .family-reliability{font-weight:800}.family-marine-warning{color:var(--warn);font-weight:800}
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
    return state.windows.get(`${line.dataset.slug}|${line.dataset.start}|${line.dataset.end}`) || null;
  }

  function applyWindow(line) {
    const slug = line.dataset.slug || '';
    line.classList.toggle('expert-only', isLongTrip(slug));
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
    setText(reliability, copy().confidence[confKey] || copy().confidence.low);

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
        state.windows.set(`${destination.dest_slug}|${item.start}|${item.end}`, item);
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
