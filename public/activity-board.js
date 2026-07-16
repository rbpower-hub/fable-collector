/* Render recommendations generated only from backend-validated GO windows. */
(function () {
  const TUNIS_TZ = 'Africa/Tunis';
  const esc = (value) => String(value ?? '').replace(
    /[&<>"']/g,
    (ch) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch])
  );
  const language = () => (
    localStorage.getItem('lang') || document.documentElement.lang || 'fr'
  ).toLowerCase().startsWith('en') ? 'en' : 'fr';
  const tunisDateKey = (value) => {
    const date = value instanceof Date ? value : new Date(value);
    if (!Number.isFinite(date.getTime())) return '';
    const parts = new Intl.DateTimeFormat('en-CA', {
      timeZone:TUNIS_TZ, year:'numeric', month:'2-digit', day:'2-digit',
    }).formatToParts(date).reduce((result, part) => {
      if (part.type !== 'literal') result[part.type] = part.value;
      return result;
    }, {});
    return `${parts.year}-${parts.month}-${parts.day}`;
  };
  const timeOnly = (iso) => {
    if (!iso) return '—';
    const date = new Date(iso);
    if (Number.isNaN(date.getTime())) return String(iso).slice(11, 16) || String(iso);
    return date.toLocaleTimeString(
      language() === 'en' ? 'en-GB' : 'fr-FR',
      {timeZone:TUNIS_TZ, hour:'2-digit', minute:'2-digit', hour12:false}
    );
  };
  const dateTime = (iso) => {
    const date = new Date(iso);
    if (Number.isNaN(date.getTime())) return String(iso || '—');
    return date.toLocaleString(
      language() === 'en' ? 'en-GB' : 'fr-FR',
      {timeZone:TUNIS_TZ, weekday:'short', day:'2-digit', month:'2-digit', hour:'2-digit', minute:'2-digit', hour12:false}
    );
  };
  const pair = (value, suffix = '') => (
    Array.isArray(value) && value.length === 2 ? `${value[0]}–${value[1]}${suffix}` : ''
  );

  function installStyles() {
    if (document.getElementById('fable-activity-styles')) return;
    const style = document.createElement('style');
    style.id = 'fable-activity-styles';
    style.textContent = `
      .activity-card{margin-top:16px}.activity-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(290px,1fr));gap:12px}
      .activity-window{border:1px solid var(--br);border-radius:12px;padding:12px;background:var(--pill-bg)}
      .activity-window.prudent{border-color:var(--warn);background:rgb(from var(--warn) r g b / .08)}
      .activity-window h4{margin:0 0 6px;color:var(--fg);font-size:1rem}.activity-choice{border-top:1px solid var(--br);padding-top:8px;margin-top:8px}
      .activity-choice:first-of-type{border-top:0}.activity-score{float:right;border:1px solid var(--br);border-radius:999px;padding:1px 7px;color:var(--ok);font-weight:800;font-size:.8rem}
      .activity-meta{font-size:.88rem;color:var(--muted);margin-top:4px;line-height:1.45}.activity-note{margin-top:10px;font-size:.82rem;color:var(--muted)}
      .fish-intel{margin-top:8px;padding:8px;border:1px dashed var(--br);border-radius:9px}.fish-intel b{color:var(--fg)}
      .intel-badge,.prudent-badge{display:inline-block;margin-left:5px;padding:1px 6px;border:1px solid var(--br);border-radius:999px;font-size:.72rem}
      .intel-badge{color:var(--muted)}.prudent-badge{color:var(--warn);border-color:var(--warn)}
      .prudent-warning{margin-top:8px;color:var(--warn);font-size:.84rem;line-height:1.4}
    `;
    document.head.appendChild(style);
  }

  function fishing(rec, lang) {
    const profile = rec.fishing || {};
    if (!Array.isArray(profile.species) || !profile.species.length) return '';
    const species = profile.species.slice(0, 4).map(esc).join(', ');
    const techniques = (profile.techniques || []).slice(0, 3).map(esc).join(', ');
    const baits = (profile.baits || []).slice(0, 4).map(esc).join(', ');
    const depth = pair(profile.depths_m, ' m') || '—';
    return `<div class="activity-meta"><b>${lang === 'en' ? 'Fishing profile' : 'Profil pêche'}:</b> ${species}<br><b>Techniques:</b> ${techniques || '—'}<br><b>${lang === 'en' ? 'Baits / lures' : 'Appâts / leurres'}:</b> ${baits || '—'} · <b>${lang === 'en' ? 'Depth' : 'Profondeur'}:</b> ${esc(depth)}</div>`;
  }

  function fishIntelligence(rec, lang) {
    const profile = rec.fishing || {};
    const fish = Array.isArray(profile.species_details) ? profile.species_details[0] : null;
    const technique = Array.isArray(profile.technique_details) ? profile.technique_details[0] : null;
    const targeting = fish?.targeting || {};
    const tackle = targeting.terminal_tackle || {};
    const hookRange = tackle.hook_sizes?.system === 'not_applicable'
      ? (lang === 'en' ? 'method-specific' : 'selon méthode')
      : pair(tackle.hook_sizes?.range);
    const leader = pair(tackle.leader_mm, ' mm');
    const sinker = pair(tackle.sinker_g, ' g');
    const natural = (targeting.natural_baits || []).slice(0, 3).map(esc).join(', ');
    const lures = (targeting.artificial_lures || []).slice(0, 3).map(esc).join(', ');
    const rigs = (technique?.gear?.rigs || []).slice(0, 3).map(esc).join(', ');
    if (!fish || (!hookRange && !leader && !natural && !lures && !rigs)) return '';
    const fishName = esc(lang === 'en' ? fish.label_en : fish.label_fr);
    const rows = [];
    if (natural || lures) rows.push(`<b>${lang === 'en' ? 'Baits / lures' : 'Appâts / leurres'}:</b> ${natural || '—'}${natural && lures ? ' · ' : ''}${lures || ''}`);
    if (rigs) rows.push(`<b>${lang === 'en' ? 'Rig' : 'Montage'}:</b> ${rigs}`);
    if (hookRange || leader || sinker) rows.push(`<b>${lang === 'en' ? 'Starting tackle' : 'Matériel de départ'}:</b> ${hookRange ? `${lang === 'en' ? 'hooks' : 'hameçons'} ${esc(hookRange)}` : ''}${leader ? ` · ${lang === 'en' ? 'leader' : 'bas de ligne'} ${esc(leader)}` : ''}${sinker ? ` · ${lang === 'en' ? 'sinker' : 'plomb'} ${esc(sinker)}` : ''}`);
    return `<div class="activity-meta fish-intel"><b>🎯 ${fishName}</b><span class="intel-badge">${lang === 'en' ? 'indicative' : 'indicatif'}</span><br>${rows.join('<br>')}</div>`;
  }

  function astronomy(rec, lang) {
    const astro = rec.astronomy || {};
    const moon = lang === 'en' ? astro.label_en : astro.label_fr;
    if (!astro.sunrise && !astro.sunset && !moon) return '';
    const moonText = moon
      ? `${esc(moon)}${astro.illumination_pct != null ? ` (${Math.round(astro.illumination_pct)}%)` : ''}`
      : '—';
    return `<div class="activity-meta">☀️ ${lang === 'en' ? 'Sunrise' : 'Lever'} ${esc(timeOnly(astro.sunrise))} · ${lang === 'en' ? 'sunset' : 'coucher'} ${esc(timeOnly(astro.sunset))}<br>🌙 ${moonText} · ${lang === 'en' ? 'moonrise' : 'lever'} ${esc(timeOnly(astro.moonrise))}</div>`;
  }

  function windowIndex(windows) {
    const index = new Map();
    (windows?.windows || []).forEach((destination) => {
      (destination?.windows || []).forEach((item) => {
        index.set(
          [destination.dest_slug || '', item.start || '', item.end || ''].join('|'),
          item
        );
      });
    });
    return index;
  }

  function render(data, windows) {
    installStyles();
    let card = document.getElementById('fable-activities');
    if (!card) {
      card = document.createElement('section');
      card.id = 'fable-activities';
      card.className = 'card activity-card';
      const dashboard = document.getElementById('dashboard-content');
      const grid = dashboard?.querySelector('.layout-grid.threecol');
      if (grid?.parentNode) grid.parentNode.insertBefore(card, grid.nextSibling);
      else (dashboard || document.body).appendChild(card);
    }
    const lang = language();
    const title = lang === 'en' ? '🌊 What to do on the water?' : '🌊 Que faire sur l’eau ?';
    const recommendations = Array.isArray(data?.recommendations) ? data.recommendations : [];
    const byWindow = windowIndex(windows);
    if (!recommendations.length) {
      card.innerHTML = `<h3><span>${title}</span></h3><div class="small">${lang === 'en' ? 'No compatible activity in a validated Family GO window.' : 'Aucune activité compatible dans une fenêtre Family GO validée.'}</div>`;
      window.dispatchEvent(new CustomEvent('fable:activities-rendered', {detail:{recommendations:[]}}));
      return;
    }
    card.innerHTML = `<h3><span>${title}</span></h3><div class="activity-grid">${recommendations.map((rec) => {
      const sourceWindow = byWindow.get(
        [rec.dest_slug || '', rec.start || '', rec.end || ''].join('|')
      ) || {};
      const prudent = sourceWindow.family_tier === 'prudent';
      const choices = (rec.activities || []).map((item) => `<div class="activity-choice"><span class="activity-score">${Math.round(item.score)}/100</span><b>${esc(item.icon)} ${esc(lang === 'en' ? item.label_en : item.label_fr)}</b><div class="activity-meta">${esc(lang === 'en' ? item.why_en : item.why_fr)}</div></div>`).join('');
      const prudentBadge = prudent
        ? `<span class="prudent-badge">${lang === 'en' ? 'PRUDENT GO' : 'GO PRUDENT'}</span>`
        : '';
      const prudentWarning = prudent
        ? `<div class="prudent-warning">⚠ ${esc(lang === 'en'
            ? (sourceWindow.caution_en || 'Reduced comfort. Monitor strengthening conditions and return early.')
            : (sourceWindow.caution_fr || 'Confort réduit. Surveiller le renforcement et prévoir un retour anticipé.'))}</div>`
        : '';
      const dateKey = tunisDateKey(rec.start);
      return `<article class="activity-window ${prudent ? 'prudent' : ''}" data-slug="${esc(rec.dest_slug || '')}" data-start="${esc(rec.start || '')}" data-end="${esc(rec.end || '')}" data-family-day-key="${esc(dateKey)}"><h4>${esc(rec.dest_name)} · ${esc(dateTime(rec.start))} → ${esc(timeOnly(rec.end))}${prudentBadge}</h4>${prudentWarning}${choices}${fishing(rec, lang)}${fishIntelligence(rec, lang)}${astronomy(rec, lang)}<div class="activity-note">${esc(lang === 'en' ? rec.method_note_en : rec.method_note_fr)}</div></article>`;
    }).join('')}</div>`;
    window.dispatchEvent(new CustomEvent('fable:activities-rendered', {detail:{recommendations}}));
  }

  async function refresh() {
    try {
      const [recommendationsResponse, windowsResponse] = await Promise.all([
        fetch('recommendations.json', {cache:'no-store'}),
        fetch('windows.json', {cache:'no-store'}),
      ]);
      if (!recommendationsResponse.ok) throw new Error(String(recommendationsResponse.status));
      const recommendations = await recommendationsResponse.json();
      const windows = windowsResponse.ok ? await windowsResponse.json() : {};
      render(recommendations, windows);
    } catch {
      render({recommendations:[]}, {});
    }
  }

  refresh();
  setInterval(refresh, 10 * 60 * 1000);
  window.addEventListener('storage', (event) => {
    if (event.key === 'lang') refresh();
  });
  window.FABLEActivityBoard = Object.assign(window.FABLEActivityBoard || {}, {
    refresh,
    tunisDateKey,
  });
})();
