"""Public API for FABLE navigation-window detection.

Implementation is split into smaller modules so the safety policy, diagnostics
and route logic can be tested independently.

This module also owns the public parsing boundary. Production spot payloads use
JSON ``null`` for sites without a relay. The lower-level parser historically
slugified that value into ``"none"``; the normalizer below prevents ordinary
ports from being misclassified as composite routes.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from . import window_detect as _detect
from . import window_models as _models
from .config import load_rules
from .offshore import detect_directional_crossings
from .window_models import HourMetrics, Site, Thresholds
from .window_policy import (
    all_in_operating_light,
    compute_confidence,
    hour_ok_for_phase,
    phases_for_window,
)

_RAW_LOAD_SITE = _models.load_site
_RAW_ADAPTIVE_MIN_HOURS = _detect.adaptive_min_hours
_RAW_RUN_READER = _detect.run_reader

_ONE_WAY_ROUTE_KINDS = {"long_trip_one_way", "offshore_one_way_beta"}


def load_site(path: Path) -> Site | None:
    """Load a spot and normalize absent relay metadata to ``None``.

    Open-Meteo publication payloads encode an absent ``route_origin`` as JSON
    ``null``. Converting that value with ``str(None)`` produces the misleading
    slug ``"none"``. Treat null-like values as absent at the public boundary.
    """
    site = _RAW_LOAD_SITE(path)
    if site is not None and site.route_origin in {"none", "null", "nil"}:
        site.route_origin = None
    return site


def adaptive_min_hours(home: Site, dest: Site, configured_min: int, th: Thresholds) -> int:
    """Return the duration required for the leg currently being evaluated.

    For a composite destination, the first dispatcher call only decides whether
    to enter the relay workflow. The real offshore duration is calculated later
    from the configured relay. Using the direct home-to-destination distance at
    this point would incorrectly bypass the composite route.
    """
    if dest.route_origin and home.slug != dest.route_origin:
        return configured_min
    return _RAW_ADAPTIVE_MIN_HOURS(home, dest, configured_min, th)


# The detector resolves these helpers from its module globals at runtime.
# Install the normalized public versions before exposing run_reader.
_detect.load_site = load_site
_detect.adaptive_min_hours = adaptive_min_hours

combine_composite_windows = _detect.combine_composite_windows
detect_transfer_windows = _detect.detect_transfer_windows
detect_windows = _detect.detect_windows
detect_windows_detailed = _detect.detect_windows_detailed
route_checkpoints = _detect.route_checkpoints
route_distance_km = _detect.route_distance_km
route_transit_profile = _detect.route_transit_profile

has_wind_range = _models.has_wind_range
is_spot_payload = _models.is_spot_payload
worst_metrics_at_hour = _models.worst_metrics_at_hour


def _payload_meta(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {}
    meta = payload.get("meta") if isinstance(payload, dict) else None
    return meta if isinstance(meta, dict) else {}


def _loaded_sites(from_dir: Path) -> dict[str, Site]:
    sites: dict[str, Site] = {}
    for path in sorted(from_dir.glob("*.json")):
        try:
            site = load_site(path)
        except Exception:  # noqa: BLE001
            continue
        if site is not None:
            sites[path.name] = site
    return sites


def _apply_one_way_routes(
    output: dict[str, Any],
    from_dir: Path,
    out_dir: Path,
    rules: dict[str, Any],
) -> dict[str, Any]:
    """Replace long-route round trips with independent outbound/return legs."""
    sites = _loaded_sites(from_dir)
    th = Thresholds.from_rules(rules)
    by_slug = {str(item.get("dest_slug")): item for item in output.get("windows", [])}
    home_filename = str(output.get("home_slug") or "")
    home = sites.get(home_filename)

    for filename, destination in sites.items():
        meta = _payload_meta(destination.path)
        route_kind = str(meta.get("route_kind") or "")
        if route_kind not in _ONE_WAY_ROUTE_KINDS:
            continue
        origin_slug = destination.route_origin
        origin = sites.get(f"{origin_slug}.json") if origin_slug else home
        entry = by_slug.get(filename)
        if entry is None:
            continue
        if origin is None:
            entry["windows"] = []
            entry["trip_mode"] = "one_way_multi_day"
            entry["route_kind"] = route_kind
            entry["same_day_round_trip_required"] = False
            entry["diagnostics"] = {
                "status": "blocked",
                "trip_mode": "one_way_multi_day",
                "route_kind": route_kind,
                "same_day_round_trip_required": False,
                "summary_fr": "Port d’origine du trajet long introuvable dans la configuration.",
                "summary_en": "Long-trip origin port is missing from configuration.",
                "first_blocker": None,
                "near_miss": {"validated_hours": 0, "required_hours": None},
            }
            continue

        windows, diagnostics, profile = detect_directional_crossings(
            origin,
            destination,
            th,
            route_kind=route_kind,
            checkpoints=_detect.route_checkpoints(origin, destination, sites),
        )
        entry["windows"] = windows
        entry["diagnostics"] = diagnostics
        entry["trip_mode"] = "one_way_multi_day"
        entry["route_kind"] = route_kind
        entry["same_day_round_trip_required"] = False
        entry["required_hours"] = profile["crossing_hours_evaluated"]
        entry["trip_profile"] = profile
        if route_kind == "offshore_one_way_beta":
            entry["offshore_profile"] = profile

    output["version"] = max(int(output.get("version", 3)), 5)
    output.setdefault("policy", {})["one_way_multi_day_supported"] = True
    output["policy"]["long_trip_same_day_round_trip_required"] = False
    output.setdefault("policy", {})["offshore_one_way_supported"] = True
    output["policy"]["offshore_same_day_round_trip_required"] = False
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "windows.json").write_text(
        json.dumps(output, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return output


# Backward-compatible internal name used by older imports and documentation.
_apply_one_way_offshore = _apply_one_way_routes


def run_reader(
    from_dir: Path,
    out_dir: Path,
    home_slug: str | None,
    min_h: int | None = None,
    max_h: int | None = None,
    rules: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Generate day-trip windows, then apply directional multi-day semantics."""
    active_rules = rules or load_rules()
    output = _RAW_RUN_READER(from_dir, out_dir, home_slug, min_h, max_h, active_rules)
    return _apply_one_way_routes(output, from_dir, out_dir, active_rules)


__all__ = [
    "HourMetrics",
    "Site",
    "Thresholds",
    "adaptive_min_hours",
    "all_in_operating_light",
    "combine_composite_windows",
    "compute_confidence",
    "detect_transfer_windows",
    "detect_windows",
    "detect_windows_detailed",
    "has_wind_range",
    "hour_ok_for_phase",
    "is_spot_payload",
    "load_site",
    "phases_for_window",
    "route_checkpoints",
    "route_distance_km",
    "route_transit_profile",
    "run_reader",
    "worst_metrics_at_hour",
]


def _main() -> None:
    parser = argparse.ArgumentParser(description="Generate FABLE Family GO windows")
    parser.add_argument("--from", dest="from_dir", default="public")
    parser.add_argument("--out", dest="out_dir", default="public")
    parser.add_argument("--home", dest="home_slug", default=None)
    parser.add_argument("--min-hours", type=int, default=None)
    parser.add_argument("--max-hours", type=int, default=None)
    args = parser.parse_args()
    run_reader(
        Path(args.from_dir),
        Path(args.out_dir),
        args.home_slug,
        args.min_hours,
        args.max_hours,
    )


if __name__ == "__main__":
    _main()
