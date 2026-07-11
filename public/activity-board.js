/* Render recommendations generated from validated Family GO windows. */
(function () {
  const esc = (value) => String(value ?? '').replace(/[&<>"']/g, (ch) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
  const language = () => (localStorage.getItem('lang') || document.documentElement.lang || 'fr').toLowerCase().startsWith('en') ? 'en' : 'fr';
  const timeOnly = (iso) => {
    if (!iso) return '—';
    const date = new Date(iso);
    if (Number.isNaN(date.getTime())) return String(iso).slice(11, 16) || String(iso);
    return date.toLocaleTimeString(language() === 'en' ? 'en-GB' : 'fr-FR', {hour:'2-digit', minute:'2-digit', hour12:false});
  };
  const dateTime = (iso) => {
    const date = new Date(iso);
    if (Number.isNaN(date.getTime())) return String(iso || '—');
    return date.toLocaleString(language() === 'en' ? 'en-GB' : 'fr-FR', {weekday:'short', day:'2-digit', month:'2-digit', hour:'2-digit', minute:'2-digit', hour12:false});
  };

  function installStyles() {
    if (document.getElementById('fable-activity-styles')) return;
    const style = document.createElement('style');
    style.id = 'fable-activity-styles';
    style.textContent = `
      .activity-card{margin-top:16px}.activity-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(290px,1fr));gap:12px}
      .activity-window{border:1px solid var(--br);border-radius:12px;padding:12px;background:var(--pill-bg)}
      .activity-window h4{margin:0 0 6px;color:var(--fg);font-size:1rem}.activity-choice{border-top:1px solid var(--br);padding-top:8px;margin-top:8px}
      .activity-choice:first-of-type{border-top:0}.activity-score{float:right;border:1px solid var(--br);border-radius:999px;padding:1px 7px;color:var(--ok);font-weight:800;font-size:.8rem}
      .activity-meta{font-size:.88rem;color:var(--muted);margin-top:4px;line-height:1.45}.activity-note{margin-top:10px;font-size:.82rem;color:var(--muted)}
    `;
    document.head.appendChild(style);
  }

  function fishing(rec, lang) {
    const profile = rec.fishing || {};
    if (!Array.isArray(profile.species) || !profile.species.length) return '';
    const species = profile.species.slice(0, 4).map(esc).join(', ');
    const techniques = (profile.techniques || []).slice(0, 3).map(esc).join(', ');
    const baits = (profile.baits || []).slice(0, 4).map(esc).join(', ');
    const depth = Array.isArray(profile.depths_m) ? `${profile.depths_m[0]}–${profile.depths_m[1]} m` : '—';
    return `<div class="activity-meta"><b>${lang === 'en' ? 'Fishing profile' : 'Profil pêche'}:</b> ${species}<br><b>Techniques:</b> ${techniques || '—'}<br><b>${lang === 'en' ? 'Baits / lures' : 'Appâts / leurres'}:</b> ${baits || '—'} · <b>${lang === 'en' ? 'Depth' : 'Profondeur'}:</b> ${esc(depth)}</div>`;
  }

  function astronomy(rec, lang) {
    const astro = rec.astronomy || {};
    const moon = lang === 'en' ? astro.label_en : astro.label_fr;
    if (!astro.sunrise && !astro.sunset && !moon) return '';
    const moonText = moon ? `${esc(moon)}${astro.illumination_pct != null ? ` (${Math.round(astro.illumination_pct)}%)` : ''}` : '—';
    return `<div class="activity-meta">☀️ ${lang === 'en' ? 'Sunrise' : 'Lever'} ${esc(timeOnly(astro.sunrise))} · ${lang === 'en' ? 'sunset' : 'coucher'} ${esc(timeOnly(astro.sunset))}<br>🌙 ${moonText} · ${lang === 'en' ? 'moonrise' : 'lever'} ${esc(timeOnly(astro.moonrise))}</div>`;
  }

  function render(data) {
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
    if (!recommendations.length) {
      card.innerHTML = `<h3><span>${title}</span></h3><div class="small">${lang === 'en' ? 'No compatible activity in a validated Family GO window.' : 'Aucune activité compatible dans une fenêtre Family GO validée.'}</div>`;
      return;
    }
    card.innerHTML = `<h3><span>${title}</span></h3><div class="activity-grid">${recommendations.map((rec) => {
      const choices = (rec.activities || []).map((item) => `<div class="activity-choice"><span class="activity-score">${Math.round(item.score)}/100</span><b>${esc(item.icon)} ${esc(lang === 'en' ? item.label_en : item.label_fr)}</b><div class="activity-meta">${esc(lang === 'en' ? item.why_en : item.why_fr)}</div></div>`).join('');
      return `<article class="activity-window"><h4>${esc(rec.dest_name)} · ${esc(dateTime(rec.start))} → ${esc(timeOnly(rec.end))}</h4>${choices}${fishing(rec, lang)}${astronomy(rec, lang)}<div class="activity-note">${esc(lang === 'en' ? rec.method_note_en : rec.method_note_fr)}</div></article>`;
    }).join('')}</div>`;
  }

  async function refresh() {
    try {
      const response = await fetch('recommendations.json', {cache:'no-store'});
      if (!response.ok) throw new Error(String(response.status));
      render(await response.json());
    } catch {
      render({recommendations:[]});
    }
  }

  refresh();
  setInterval(refresh, 10 * 60 * 1000);
  window.addEventListener('storage', (event) => { if (event.key === 'lang') refresh(); });
})();
