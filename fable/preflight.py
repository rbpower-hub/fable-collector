"""Pre-collection validation and normalized configuration exports."""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path
from typing import Any

from .config import load_rules, load_sites, normalize_rules, rules_digest, validate_rules, window_bounds
from .util import dget, enable_utf8_stdio

log = logging.getLogger("fable.preflight")


def _validate_v3_policy(rules: dict[str, Any]) -> list[str]:
    problems = []
    numeric = {
        "prudent.wind_max_kmh": (0, float(dget(rules, "wind.nogo_min_kmh", 25))),
        "prudent.gust_max_kmh": (0, float(dget(rules, "overrides.gusts_hard_nogo_kmh", 30))),
        "prudent.hs_max_m": (0, float(dget(rules, "sea.nogo_min_hs_m", 0.8))),
        "prudent.tp_min_s": (0, 30),
        "adaptive_window.absolute_min_hours": (1, 6),
        "adaptive_window.min_zone_hours": (0.5, 6),
        "daylight.start_after_sunrise_min": (0, 240),
        "daylight.end_before_sunset_min": (0, 240),
    }
    for key, (minimum, maximum) in numeric.items():
        value = dget(rules, key)
        if not isinstance(value, (int, float)):
            problems.append(f"not a number: {key}={value!r}")
        elif not minimum <= float(value) <= maximum:
            problems.append(f"out of range: {key}={value!r} expected {minimum}..{maximum}")
    confidence = str(dget(rules, "prudent.min_confidence", "Medium"))
    if confidence not in {"Low", "Medium", "High"}:
        problems.append(f"invalid prudent.min_confidence={confidence!r}")
    return problems


def run_preflight(root: Path, public: Path) -> int:
    ok = True

    try:
        cfg = load_sites(root / "sites.yaml")
        print(f"✅ sites.yaml OK — {len(cfg.sites)} site(s), home={cfg.home}, schema v{cfg.version}")
        if not cfg.site(cfg.home):
            print(f"❌ home '{cfg.home}' is not one of the configured sites")
            ok = False
    except Exception as exc:  # noqa: BLE001
        print(f"❌ sites.yaml: {exc}")
        return 1

    rules = load_rules(root / "rules.yaml")
    problems = validate_rules(rules) + _validate_v3_policy(rules)
    if problems:
        print(f"❌ rules.yaml: {problems}")
        return 1
    try:
        minimum, maximum = window_bounds(rules)
    except Exception as exc:  # noqa: BLE001
        print(f"❌ rules.yaml: invalid window/corridor values: {exc}")
        return 1
    print(
        f"✅ rules.yaml OK — digest={rules_digest(rules)}, configured family window "
        f"{minimum}–{maximum} h, prudent={bool(dget(rules, 'prudent.enabled', True))}"
    )

    public.mkdir(parents=True, exist_ok=True)
    try:
        normalized = normalize_rules(rules)
    except Exception as exc:  # noqa: BLE001
        print(f"❌ rules.yaml: normalization failed (type error in a threshold?): {exc}")
        return 1
    normalized["decision_policy_version"] = 3
    normalized["prudent"] = rules.get("prudent") or {}
    normalized["adaptive_window"] = rules.get("adaptive_window") or {}
    normalized["daylight"] = rules.get("daylight") or {}
    normalized["hard_vetoes_unchanged"] = True
    (public / "rules.normalized.json").write_text(
        json.dumps(normalized, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    sites_normalized = {
        "version": cfg.version,
        "tz": cfg.tz,
        "home": cfg.home,
        "sites": [
            {
                "name": site["name"],
                "slug": site["slug"],
                "lat": site["lat"],
                "lon": site["lon"],
                "map_lat": site["map_lat"],
                "map_lon": site["map_lon"],
                "transit_speed_kts": site["transit_speed_kts"],
                "route_origin": site["route_origin"],
                "route_points": site["route_points"],
                "windows_enabled": site["windows_enabled"],
                "beta": site["beta"],
                "route_kind": site["route_kind"],
                "route_note": site["route_note"],
                "country": site["country"],
                "shelter_bonus_radius_km": site["shelter_bonus_radius_km"],
                "onshore_sectors": [list(value) for value in site["onshore_sectors"]],
                "path": f"{site['slug']}.json",
            }
            for site in cfg.sites
        ],
    }
    (public / "sites.normalized.json").write_text(
        json.dumps(sites_normalized, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print("✅ exported public/rules.normalized.json + public/sites.normalized.json")
    return 0 if ok else 1


if __name__ == "__main__":
    enable_utf8_stdio()
    logging.basicConfig(level="INFO", format="%(levelname)s %(name)s: %(message)s")
    repository = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
    sys.exit(run_preflight(repository, repository / "public"))
