"""Patch the static dashboard with deployment-time route behaviour.

The dashboard source predates the offshore one-way model and recursively prepends
relay routes. For Pantelleria this incorrectly combines the separate
Gammarth→Kélibia positioning trip with the Kélibia→Pantelleria crossing.
"""

from __future__ import annotations

from pathlib import Path

_OLD_PREFIX = "const prefix = originFile !== homeFile ? routeSegmentsForFile(originFile, nextTrail) : [];"
_NEW_PREFIX = """const offshoreOneWay = String(spotConfig[file]?.route_kind || '') === 'offshore_one_way_beta';
    const prefix = originFile !== homeFile && !offshoreOneWay ? routeSegmentsForFile(originFile, nextTrail) : [];"""

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


def patch_dashboard_index(path: Path) -> bool:
    """Apply the one-way offshore map patch; return True when content changed."""
    html = path.read_text(encoding="utf-8")
    patched = html.replace(_OLD_PREFIX, _NEW_PREFIX)
    patched = patched.replace(_OLD_FALLBACK_KIND, _NEW_FALLBACK_KIND)
    patched = patched.replace(_OLD_FALLBACK_NOTE, _NEW_FALLBACK_NOTE)

    if patched == html:
        return False
    path.write_text(patched, encoding="utf-8")
    return True
