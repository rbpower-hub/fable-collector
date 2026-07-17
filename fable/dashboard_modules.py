"""Build the published dashboard module boundary without changing behaviour."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .config import load_sites

_MAIN_SCRIPT_RE = re.compile(
    r"<script>\s*(\(async function main\(\) \{.*?\}\)\(\);)\s*</script>",
    re.DOTALL,
)
_PRETTIFY_DUPLICATE_RE = re.compile(
    r"      const prettifyDates = s =>\s*.*?\n        \}\);\n\s*// cleanse",
    re.DOTALL,
)
_APP_IMPORTS = """import './i18n.js';
import './map.js';
import './corridor.js';

"""
_APP_TAG = '<script type="module" src="./js/app.js"></script>'
_FALLBACK_TAG = '<script src="./js/fallback-sites.js"></script>'
_DEBT_STYLE = """  <style id="fable-dashboard-debt-styles">
    .pill{display:inline-flex;align-items:center;min-height:30px;padding:4px 9px;border:1px solid var(--br);border-radius:999px;background:var(--pill-bg);color:var(--muted);font-size:.78rem;white-space:nowrap}
  </style>"""
_RADAR_RESET_BUTTON = '        <button id="resetMapBtn" class="btn" title="Vue initiale">🔄</button>\n'
_DEFAULT_MAP_VIEW = "  const DEFAULT_MAP_VIEW = { center:[36.95,10.6], zoom:9 };"
_GLOBAL_MAP_VIEW = "  const DEFAULT_MAP_VIEW = { center:[36.96,11.12], zoom:8 };"
_RESET_MAP_POINTS = "    const points = currentSpotLatLngs();"
_GLOBAL_RESET_MAP_POINTS = "    const points = currentSpotLatLngs();"


def _write_if_changed(path: Path, content: str) -> bool:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_text(encoding="utf-8") == content:
        return False
    path.write_text(content, encoding="utf-8")
    return True


def _repo_root(index_path: Path) -> Path:
    candidates = [index_path.parent.parent, Path(__file__).resolve().parents[1]]
    return next((candidate for candidate in candidates if (candidate / "sites.yaml").exists()), candidates[-1])


def _fallback_record(site: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": site["name"],
        "lat": site.get("map_lat", site["lat"]),
        "lon": site.get("map_lon", site["lon"]),
        "onshore_sectors": [list(pair) for pair in site.get("onshore_sectors") or []],
        "shelter_bonus_radius_km": site.get("shelter_bonus_radius_km", 0),
        "transit_speed_kts": site.get("transit_speed_kts") or {"min": 16, "max": 24},
        "route_origin": site.get("route_origin"),
        "route_points": site.get("route_points") or [],
        "windows_enabled": bool(site.get("windows_enabled", True)),
        "beta": bool(site.get("beta", False)),
        "route_kind": site.get("route_kind", "standard"),
        "route_note": site.get("route_note"),
        "country": site.get("country"),
    }


def build_fallback_sites(index_path: Path) -> bool:
    """Generate the browser fallback from the same ``sites.yaml`` parser as the backend."""
    config = load_sites(_repo_root(index_path) / "sites.yaml")
    payload = {f"{site['slug']}.json": _fallback_record(site) for site in config.sites}
    content = "window.FABLE_DEFAULT_SPOT_CONFIG = " + json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        indent=2,
    ) + ";\n"
    return _write_if_changed(index_path.parent / "js" / "fallback-sites.js", content)


def modularize_dashboard(index_path: Path) -> bool:
    """Externalize the legacy IIFE and apply low-risk front-end debt cleanup."""
    original = index_path.read_text(encoding="utf-8")
    html = original
    html = html.replace(
        "const DEFAULT_SPOT_CONFIG = {",
        "const DEFAULT_SPOT_CONFIG = window.FABLE_DEFAULT_SPOT_CONFIG || {",
        1,
    )
    html = html.replace(_RADAR_RESET_BUTTON, "")
    html = _PRETTIFY_DUPLICATE_RE.sub(
        "      const prettifyDates = prettifyReasonDates;\n      \n      // cleanse",
        html,
        count=1,
    )
    if 'id="fable-dashboard-debt-styles"' not in html:
        html = html.replace("</head>", f"{_DEBT_STYLE}\n</head>")

    files_changed = build_fallback_sites(index_path)
    match = _MAIN_SCRIPT_RE.search(html)
    if match:
        app_content = _APP_IMPORTS + match.group(1).strip() + "\n"
        app_content = app_content.replace(_DEFAULT_MAP_VIEW, _GLOBAL_MAP_VIEW, 1)
        app_content = app_content.replace(_RESET_MAP_POINTS, _GLOBAL_RESET_MAP_POINTS, 1)
        files_changed = _write_if_changed(index_path.parent / "js" / "app.js", app_content) or files_changed
        html = html[:match.start()] + f"{_FALLBACK_TAG}\n{_APP_TAG}" + html[match.end():]

    html_changed = html != original
    if html_changed:
        index_path.write_text(html, encoding="utf-8")
    return html_changed or files_changed
