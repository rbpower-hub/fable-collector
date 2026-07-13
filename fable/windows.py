"""Public API for FABLE navigation-window detection.

Implementation is split into smaller modules so the safety policy, diagnostics
and route logic can be tested independently.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from .window_detect import (
    adaptive_min_hours,
    combine_composite_windows,
    detect_transfer_windows,
    detect_windows,
    detect_windows_detailed,
    route_checkpoints,
    route_distance_km,
    route_transit_profile,
    run_reader,
)
from .window_models import (
    HourMetrics,
    Site,
    Thresholds,
    has_wind_range,
    is_spot_payload,
    load_site,
    worst_metrics_at_hour,
)
from .window_policy import (
    all_in_operating_light,
    compute_confidence,
    hour_ok_for_phase,
    phases_for_window,
)

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
