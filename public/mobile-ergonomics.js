/* FABLE mobile ergonomics — responsive controls without duplicating existing logic. */
(function () {
  const MOBILE_QUERY = window.matchMedia('(max-width: 640px)');
  const COARSE_QUERY = window.matchMedia('(pointer: coarse)');
  const SELECTED_KEY = 'fable_selected_window';
  const movedControls = new Map();
  let restoringSelection = false;
  let scheduledRestore = false;

  const language = () => (
    localStorage.getItem('lang') || document.documentElement.lang || 'fr'
  ).toLowerCase().startsWith('en') ? 'en' : 'fr';

  const copy = () => language() === 'en' ? {
    settings: 'Settings', close: 'Close', info: 'Spot information',
  } : {
    settings: 'Réglages', close: 'Fermer', info: 'Informations du spot',
  };

  function installStyles() {
    if (document.getElementById('fable-mobile-ergonomics-styles')) return;
    const style = document.createElement('style');
    style.id = 'fable-mobile-ergonomics-styles';
    style.textContent = `
      #mobileSettingsBtn{display:none}
      .mobile-sheet-backdrop{position:fixed;inset:0;z-index:5000;background:rgba(2,6,23,.62);display:none;align-items:flex-end;justify-content:center;padding:0}
      .mobile-sheet-backdrop.open{display:flex}.mobile-sheet{width:min(100%,680px);max-height:min(82dvh,700px);overflow:auto;background:var(--card);border:1px solid var(--br);border-radius:20px 20px 0 0;padding:16px calc(16px + env(safe-area-inset-right)) calc(18px + env(safe-area-inset-bottom)) calc(16px + env(safe-area-inset-left));box-shadow:0 -18px 50px rgba(0,0,0,.38)}
      .mobile-sheet-head{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:14px}.mobile-sheet-head h2{margin:0;font-size:1.15rem}.mobile-sheet-close{min-width:44px;min-height:44px;border:1px solid var(--br);border-radius:999px;background:var(--pill-bg);color:var(--fg);font-size:1.2rem;cursor:pointer}
      .mobile-settings-controls{display:grid;gap:11px}.mobile-settings-controls>*{width:100%;min-height:44px;justify-content:center}.mobile-settings-controls .toggle{display:flex}.mobile-settings-controls .toggle button{flex:1;min-height:44px}
      .mobile-tooltip-content{line-height:1.45}.mobile-tooltip-content .row{margin-top:9px}.mobile-tooltip-content .hdr{font-weight:900;font-size:1.05rem}
      @media(max-width:640px){
        .app-header{display:grid;grid-template-columns:minmax(0,1fr) auto;align-items:center!important}.app-header h1{margin:0;font-size:1.18rem!important}.app-header .hdr-tools{width:auto!important;overflow:visible!important;display:flex;align-items:center;gap:7px}.app-header .hdr-tools>*{display:none!important}.app-header .hdr-tools #hc,.app-header .hdr-tools #mobileSettingsBtn{display:inline-flex!important}.app-header #hc{max-width:42vw;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.app-header #gen{display:none!important}
        #mobileSettingsBtn{min-width:44px;min-height:44px;align-items:center;justify-content:center;padding:0;font-size:1.1rem}
      }
      @media(pointer:coarse){
        .btn,.btn-mini,.toggle button,.window-line,.family-tab,.family-action,.verdict-button{min-height:44px!important}
        .btn-mini{min-width:44px;padding:8px 10px!important}.window-line{padding:12px!important;touch-action:manipulation}
      }
    `;
    document.head.appendChild(style);
  }

  function createSheet(id, title) {
    let backdrop = document.getElementById(id);
    if (backdrop) return backdrop;
    backdrop = document.createElement('div');
    backdrop.id = id;
    backdrop.className = 'mobile-sheet-backdrop';
    backdrop.innerHTML = `
      <section class="mobile-sheet" role="dialog" aria-modal="true" aria-labelledby="${id}-title">
        <div class="mobile-sheet-head"><h2 id="${id}-title"></h2><button type="button" class="mobile-sheet-close" aria-label="Close">×</button></div>
        <div class="mobile-sheet-body"></div>
      </section>`;
    document.body.appendChild(backdrop);
    backdrop.querySelector('h2').textContent = title;
    backdrop.addEventListener('click', (event) => {
      if (event.target === backdrop || event.target.closest('.mobile-sheet-close')) closeSheet(backdrop);
    });
    backdrop.addEventListener('keydown', (event) => {
      if (event.key === 'Escape') closeSheet(backdrop);
    });
    return backdrop;
  }

  function openSheet(backdrop) {
    backdrop.classList.add('open');
    document.body.style.overflow = 'hidden';
    backdrop.querySelector('.mobile-sheet-close')?.focus();
  }

  function closeSheet(backdrop) {
    backdrop.classList.remove('open');
    document.body.style.overflow = '';
  }

  function ensureSettings() {
    const tools = document.querySelector('.hdr-tools');
    if (!tools) return;
    let button = document.getElementById('mobileSettingsBtn');
    if (!button) {
      button = document.createElement('button');
      button.id = 'mobileSettingsBtn';
      button.type = 'button';
      button.className = 'btn';
      button.textContent = '⚙️';
      tools.appendChild(button);
    }
    const sheet = createSheet('mobile-settings-sheet', copy().settings);
    sheet.querySelector('h2').textContent = copy().settings;
    sheet.querySelector('.mobile-sheet-close').setAttribute('aria-label', copy().close);
    let controls = sheet.querySelector('.mobile-settings-controls');
    if (!controls) {
      controls = document.createElement('div');
      controls.className = 'mobile-settings-controls';
      sheet.querySelector('.mobile-sheet-body').appendChild(controls);
    }
    if (!button.dataset.bound) {
      button.dataset.bound = '1';
      button.addEventListener('click', () => openSheet(sheet));
    }
    applyMobileHeader(controls);
  }

  function applyMobileHeader(controls) {
    const ids = ['viewToggleBtn', 'themeToggle', 'muteBtn', 'langToggle', 'fullscreenBtn'];
    if (MOBILE_QUERY.matches) {
      ids.forEach((id) => {
        const node = document.getElementById(id);
        if (!node || node.parentElement === controls) return;
        if (!movedControls.has(id)) {
          const marker = document.createElement('span');
          marker.hidden = true;
          marker.dataset.mobilePlaceholder = id;
          node.parentNode.insertBefore(marker, node);
          movedControls.set(id, marker);
        }
        controls.appendChild(node);
      });
    } else {
      ids.forEach((id) => {
        const node = document.getElementById(id);
        const marker = movedControls.get(id);
        if (node && marker?.parentNode) marker.parentNode.insertBefore(node, marker.nextSibling);
      });
      document.getElementById('mobile-settings-sheet')?.classList.remove('open');
      document.body.style.overflow = '';
    }
  }

  function tooltipSheet() {
    const sheet = createSheet('mobile-tooltip-sheet', copy().info);
    sheet.querySelector('h2').textContent = copy().info;
    sheet.querySelector('.mobile-sheet-close').setAttribute('aria-label', copy().close);
    return sheet;
  }

  function clampTooltip() {
    if (COARSE_QUERY.matches) return;
    const tip = document.getElementById('tooltip');
    if (!tip || getComputedStyle(tip).display === 'none') return;
    const rect = tip.getBoundingClientRect();
    const left = Math.max(8, Math.min(rect.left, window.innerWidth - rect.width - 8));
    tip.style.left = `${window.scrollX + left}px`;
  }

  function showTouchTooltip(button) {
    button.dispatchEvent(new MouseEvent('mouseenter', {bubbles: false}));
    setTimeout(() => {
      const source = document.getElementById('tooltip');
      const sheet = tooltipSheet();
      const body = sheet.querySelector('.mobile-sheet-body');
      body.className = 'mobile-sheet-body mobile-tooltip-content';
      body.innerHTML = source?.innerHTML || '';
      if (source) source.style.display = 'none';
      openSheet(sheet);
    }, 0);
  }

  function selectedKey(line) {
    return [line?.dataset.slug, line?.dataset.start, line?.dataset.end].join('|');
  }

  function storeSelection(line) {
    const key = selectedKey(line);
    if (key.split('|').every(Boolean)) sessionStorage.setItem(SELECTED_KEY, key);
  }

  function mapIsVisible() {
    const map = document.getElementById('map');
    if (!map || getComputedStyle(map).display === 'none') return false;
    const rect = map.getBoundingClientRect();
    return rect.bottom > 0 && rect.top < window.innerHeight;
  }

  function revealMapAfterSelection() {
    if (restoringSelection) return;
    if (document.body.classList.contains('family-board-mode')) {
      document.querySelector('[data-family-tab="map"]')?.click();
    }
    setTimeout(() => {
      const map = document.getElementById('map');
      if (map && !mapIsVisible()) map.scrollIntoView({behavior: 'smooth', block: 'start'});
    }, 120);
  }

  function restoreSelection() {
    if (scheduledRestore) return;
    scheduledRestore = true;
    requestAnimationFrame(() => {
      scheduledRestore = false;
      if (document.querySelector('.window-line.select')) return;
      const key = sessionStorage.getItem(SELECTED_KEY);
      if (!key) return;
      const [slug, start, end] = key.split('|');
      const line = Array.from(document.querySelectorAll('.window-line')).find((item) => (
        item.dataset.slug === slug && item.dataset.start === start && item.dataset.end === end
      ));
      if (!line) return;
      restoringSelection = true;
      line.click();
      restoringSelection = false;
    });
  }

  function makeWindowsAccessible() {
    document.querySelectorAll('.window-line').forEach((line) => {
      line.setAttribute('role', 'button');
      line.tabIndex = 0;
    });
  }

  function start() {
    installStyles();
    ensureSettings();
    const wins = document.getElementById('wins');
    const observer = new MutationObserver(() => {
      makeWindowsAccessible();
      restoreSelection();
    });
    if (wins) observer.observe(wins, {childList: true, subtree: true});
    makeWindowsAccessible();
    restoreSelection();

    MOBILE_QUERY.addEventListener?.('change', () => ensureSettings());
    window.addEventListener('resize', clampTooltip);
    document.addEventListener('pointerover', (event) => {
      if (!COARSE_QUERY.matches && event.target.closest('button.why')) setTimeout(clampTooltip, 0);
    });
    document.addEventListener('click', (event) => {
      const why = event.target.closest('button.why');
      if (why && COARSE_QUERY.matches) {
        event.preventDefault();
        event.stopPropagation();
        showTouchTooltip(why);
        return;
      }
      const line = event.target.closest('.window-line');
      if (line) {
        storeSelection(line);
        revealMapAfterSelection();
      }
    });
    document.addEventListener('keydown', (event) => {
      const line = event.target.closest('.window-line');
      if (!line || !['Enter', ' '].includes(event.key)) return;
      event.preventDefault();
      line.click();
    });
    document.getElementById('langToggle')?.addEventListener('click', () => setTimeout(ensureSettings, 0));
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start, {once: true});
  else start();
})();
