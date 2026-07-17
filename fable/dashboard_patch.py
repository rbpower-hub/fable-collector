"""Patch the static dashboard with deployment-time interface behaviour.

The static board predates the offshore one-way model and the decision-first
Family view. Publication applies the upgrades idempotently.
"""

from __future__ import annotations

import re
from pathlib import Path

from .dashboard_modules import modularize_dashboard

_OLD_PREFIX = "const prefix = originFile !== homeFile ? routeSegmentsForFile(originFile, nextTrail) : [];"
_NEW_PREFIX = """const oneWayMultiDay = ['long_trip_one_way','offshore_one_way_beta'].includes(String(spotConfig[file]?.route_kind || ''));
    const prefix = originFile !== homeFile && !oneWayMultiDay ? routeSegmentsForFile(originFile, nextTrail) : [];"""

_OLD_FALLBACK_KIND = "route_kind:'composite_beta'"
_NEW_FALLBACK_KIND = "route_kind:'offshore_one_way_beta'"

_OLD_FALLBACK_NOTE = (
    "route_note:'Beta composite via Kélibia — GO seulement si le transfert Gammarth→Kélibia "
    "puis la fenêtre Kélibia→Pantelleria s’alignent.'"
)
_NEW_FALLBACK_NOTE = (
    "route_note:'Traversée offshore Kélibia↔Pantelleria évaluée séparément. "
    "Le pré-positionnement depuis Gammarth se consulte sur la route de Kélibia.'"
)

_FABRICATED_WINDOWS_RE = re.compile(
    r"\n\s*// Fallback: si windows\.json est vide, synthétiser depuis meta\.window des spots"
    r"\n\s*let winData = windows;"
    r".*?"
    r"\n\s*winData = \{ generated_at: new Date\(\)\.toISOString\(\), windows: synthesized \};"
    r"\n\s*\}",
    re.DOTALL,
)
_SAFE_WINDOWS_ASSIGNMENT = "\n    const winData = windows;"

_OLD_IS_FRESH = """  const isFresh = (entry,genIso) => { const T=180; if(!entry) return false; if(typeof entry.fresh==='boolean') return entry.fresh; if(entry.modified){const age=(Date.now()-new Date(entry.modified))/60000; if(isFinite(age)) return age<=T;} if(genIso){const age=(Date.now()-new Date(genIso))/60000; if(isFinite(age)) return age<=T;} return false; };"""
_NEW_FRESHNESS_HELPERS = """  const freshnessState = (status, referenceIso=null) => {
    const cadence = Number(status?.cadence_minutes);
    const limit_min = Number.isFinite(cadence) && cadence > 0 ? cadence + 35 : 95;
    const reference = referenceIso || status?.generated_at || null;
    const timestamp = reference ? new Date(reference).getTime() : NaN;
    const age_min = Number.isFinite(timestamp) ? Math.max(0, (Date.now() - timestamp) / 60000) : Infinity;
    return { fresh: Number.isFinite(age_min) && age_min <= limit_min, age_min, limit_min };
  };
  window.FABLEFreshness = Object.assign(window.FABLEFreshness || {}, { freshnessState });
  const isFresh = (entry,status) => freshnessState(status, entry?.modified || status?.generated_at).fresh;"""

_OLD_HEADER_FRESH = """    const freshNow = status?.stale_after ? Date.now() <= new Date(status.stale_after).getTime() : false;"""
_NEW_HEADER_FRESH = """    const freshness = freshnessState(status);
    const freshNow = freshness.fresh;"""

_KIOSK_RE = re.compile(
    r"  // ===== KIOSK \(manual via button only\) =====\s+"
    r"let cursorTimer;.*?"
    r"document\.addEventListener\('visibilitychange', \(\)=>\{ if\(!document\.hidden\)\{ updateDashboard\(\); "
    r"if\(!document\.fullscreenElement\) document\.documentElement\.requestFullscreen\(\)\.catch\(\(\)=>\{\}\); \} \}\);",
    re.DOTALL,
)
_EXPLICIT_KIOSK = """  // ===== KIOSK (explicit via ?kiosk=1 only) =====
  const kioskRequested = new URLSearchParams(window.location.search).get('kiosk') === '1';
  if (kioskRequested) sessionStorage.setItem('fable_kiosk', '1');
  const kioskMode = kioskRequested || sessionStorage.getItem('fable_kiosk') === '1';

  let cursorTimer;
  const hideCursor = () => { if (kioskMode) document.body.style.cursor = 'none'; };
  const showCursor = () => {
    if (!kioskMode) { document.body.style.cursor = ''; return; }
    document.body.style.cursor = '';
    clearTimeout(cursorTimer);
    cursorTimer = setTimeout(hideCursor, 5000);
  };
  if (kioskMode) {
    ['mousemove','keydown','click','wheel','touchstart'].forEach(eventName =>
      document.addEventListener(eventName, showCursor, {passive:true})
    );
    showCursor();
  }
  document.addEventListener('visibilitychange', () => {
    if (document.hidden) return;
    updateDashboard();
    if (kioskMode && !document.fullscreenElement) {
      document.documentElement.requestFullscreen().catch(() => {});
    }
  });"""

_OLD_COUNTDOWN = """  setInterval(()=>{ countdown=(countdown<=1)?REFRESH_INTERVAL_SECONDS:countdown-1; $('#refresh-timer').textContent=t('next_refresh',countdown); },1000);"""
_NEW_COUNTDOWN = """  $('#refresh-timer').textContent=t('next_refresh',countdown);
  setInterval(()=>{ countdown=(countdown<=30)?REFRESH_INTERVAL_SECONDS:countdown-30; $('#refresh-timer').textContent=t('next_refresh',countdown); },30000);"""

_OLD_LANGUAGE_LIST = "const languages = ['fr','en'];"
_NEW_LANGUAGE_LIST = "const languages = ['fr','en','ar'];"
_OLD_LANGUAGE_DIRECTION = "document.documentElement.dir  = 'ltr';"
_NEW_LANGUAGE_DIRECTION = "document.documentElement.dir  = l === 'ar' ? 'rtl' : 'ltr';"

_PWA_HEAD = """  <link rel="manifest" href="./manifest.webmanifest" />
  <link rel="icon" href="./icons/fable-192.svg" type="image/svg+xml" />
  <link rel="apple-touch-icon" href="./icons/fable-192.svg" />"""

_FAMILY_VIEW_TAG = '<script src="./family-view.js"></script>'
_DAY_SELECTION_TAG = '<script type="module" src="./js/day-selection.js"></script>'
_DISABLED_OFF_HOURS_REFINEMENTS_TAG = '<script type="module" src="./js/off-hours-refinements.js"></script>'
_VERDICT_HERO_TAG = '<script src="./verdict-hero.js"></script>'
_FAMILY_CONTENT_GATE_TAG = '<script src="./family-content-gate.js"></script>'
_FAMILY_REASONS_TAG = '<script src="./family-reasons.js"></script>'
_MOBILE_ERGONOMICS_TAG = '<script src="./mobile-ergonomics.js"></script>'
_LOCALE_TRANSITION_TAG = '<script src="./locale-transition.js"></script>'
_ARABIC_LOCALE_TAG = '<script src="./arabic-locale.js"></script>'
_PWA_INSTALL_TAG = '<script src="./pwa-install.js"></script>'
_FRESHNESS_GATE_TAG = '<script src="./freshness-gate.js"></script>'


def patch_dashboard_index(path: Path) -> bool:
    """Apply dashboard upgrades; return ``True`` when content changed."""
    html = path.read_text(encoding="utf-8")
    patched = html.replace('<html lang="fr" data-theme="dark">', '<html lang="fr" data-theme="nautical">')
    patched = patched.replace(
        "let theme = localStorage.getItem('theme') || document.documentElement.getAttribute('data-theme') || 'dark';",
        "let theme = localStorage.getItem('theme') || document.documentElement.getAttribute('data-theme') || 'nautical';",
    )
    patched = patched.replace("if(!themes.includes(theme)) theme='dark';", "if(!themes.includes(theme)) theme='nautical';")
    patched = patched.replace(_OLD_LANGUAGE_LIST, _NEW_LANGUAGE_LIST)
    patched = patched.replace(_OLD_LANGUAGE_DIRECTION, _NEW_LANGUAGE_DIRECTION)
    patched = patched.replace(_OLD_PREFIX, _NEW_PREFIX)
    patched = patched.replace(_OLD_FALLBACK_KIND, _NEW_FALLBACK_KIND)
    patched = patched.replace(_OLD_FALLBACK_NOTE, _NEW_FALLBACK_NOTE)
    patched = _FABRICATED_WINDOWS_RE.sub(_SAFE_WINDOWS_ASSIGNMENT, patched, count=1)
    patched = patched.replace(_OLD_IS_FRESH, _NEW_FRESHNESS_HELPERS)
    patched = patched.replace(_OLD_HEADER_FRESH, _NEW_HEADER_FRESH)
    patched = patched.replace("isFresh(entry, gen)", "isFresh(entry, status)")
    patched = patched.replace("isFresh(entry,gen)", "isFresh(entry,status)")
    patched = _KIOSK_RE.sub(_EXPLICIT_KIOSK, patched, count=1)
    patched = patched.replace(_OLD_COUNTDOWN, _NEW_COUNTDOWN)

    # Emergency safety gate: remove the recursive off-hours module until its
    # renderer is rewritten without a document-wide MutationObserver loop.
    patched = patched.replace(f"  {_DISABLED_OFF_HOURS_REFINEMENTS_TAG}\n", "")
    patched = patched.replace(_DISABLED_OFF_HOURS_REFINEMENTS_TAG, "")

    if '<link rel="manifest" href="./manifest.webmanifest" />' not in patched:
        patched = patched.replace("</head>", f"{_PWA_HEAD}\n</head>")

    tags = (
        _FAMILY_VIEW_TAG,
        _DAY_SELECTION_TAG,
        _VERDICT_HERO_TAG,
        _FAMILY_CONTENT_GATE_TAG,
        _FAMILY_REASONS_TAG,
        _MOBILE_ERGONOMICS_TAG,
        _LOCALE_TRANSITION_TAG,
        _ARABIC_LOCALE_TAG,
        _PWA_INSTALL_TAG,
        _FRESHNESS_GATE_TAG,
    )
    for tag in tags:
        if tag not in patched:
            patched = patched.replace("</body>", f"  {tag}\n</body>")

    html_changed = patched != html
    if html_changed:
        path.write_text(patched, encoding="utf-8")
    module_changed = modularize_dashboard(path)
    return html_changed or module_changed
