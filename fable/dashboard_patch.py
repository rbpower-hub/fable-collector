"""Patch the static dashboard with deployment-time interface behaviour.

The static board predates the offshore one-way model and the decision-first
Family view. Publication applies both upgrades idempotently.
"""

from __future__ import annotations

from pathlib import Path

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

_FAMILY_VIEW_TAG = '<script src="./family-view.js"></script>'


def patch_dashboard_index(path: Path) -> bool:
    """Apply dashboard upgrades; return ``True`` when content changed."""
    html = path.read_text(encoding="utf-8")
    patched = html.replace(_OLD_PREFIX, _NEW_PREFIX)
    patched = patched.replace(_OLD_FALLBACK_KIND, _NEW_FALLBACK_KIND)
    patched = patched.replace(_OLD_FALLBACK_NOTE, _NEW_FALLBACK_NOTE)

    if _FAMILY_VIEW_TAG not in patched:
        patched = patched.replace("</body>", f"  {_FAMILY_VIEW_TAG}\n</body>")

    if patched == html:
        return False
    path.write_text(patched, encoding="utf-8")
    return True
