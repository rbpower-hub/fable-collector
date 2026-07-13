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
from pathlib import Path

from . import window_detect as _detect
from . import window_models as _models
from .window_models import HourMetrics, Site, Thresholds
from .window_policy import (
    all_in_operating_light,
    compute_confidence,
    hour_ok_for_phase,
    phases_for_window,
)


_RAW_LOAD_SITE = _models.load_site
_RAW_ADAPTIVE_MIN_HOURS = _detect.adaptive_min_hours


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
run_reader = _detect.run_reader

has_wind_range = _models.has_wind_range
is_spot_payload = _models.is_spot_payload
worst_metrics_at_hour = _models.worst_metrics_at_hour

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
