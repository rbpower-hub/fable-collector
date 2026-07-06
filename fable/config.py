"""Configuration: rules.yaml + sites.yaml loading, validation, normalization.

Single source of truth for default thresholds (previously duplicated in
main.py, reader.py and pages.yml with diverging values).
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from pathlib import Path
from typing import Any

import yaml

from .util import deep_merge, dget, slugify

log = logging.getLogger("fable.config")

# ---------------------------------------------------------------------------
# Rules
# ---------------------------------------------------------------------------
# Values aligned with rules.yaml (production ruleset). rules.yaml overrides these.
DEFAULT_RULES: dict[str, Any] = {
    "overrides": {
        "thunder_wmo": [95, 96, 99],
        "gusts_hard_nogo_kmh": 30,
        "squall_delta_kmh": 17,
        "visibility_km_min": 5,
    },
    "wind": {"family_max_kmh": 20, "nogo_min_kmh": 25, "onshore_degrade_kmh": 22},
    "sea": {"family_max_hs_m": 0.5, "nogo_min_hs_m": 0.8},
    "tp_matrix": {
        "transit": {
            "hs_lt_0_4_family_tp_s": 3.2,
            "hs_0_4_0_5_family_tp_s": 4.5,
            "hs_lt_0_4_expert_tp_min_s": 3.2,
            "hs_0_4_0_5_expert_tp_min_s": 4.0,
        },
        "anchor_sheltered": {
            "hs_max_m": 0.35,
            "hs_le_0_35_family_tp_s": 3.2,
            "hs_le_0_35_expert_tp_min_s": 3.5,
        },
    },
    "combined": {  # short/steep sea clauses (previously hardcoded in reader.py)
        "short_steep_downgrade": {"hs_min_m": 0.5, "tp_max_s": 6.0},
        "short_steep_hard_nogo": {"hs_min_m": 0.6, "tp_max_s": 5.0},
    },
    "hysteresis": {"wind_kmh": 1.0, "hs_m": 0.05},
    "shelter": {
        "radius_km_default": 3,
        "apply_on_transit": False,
        "anchor_gusts_allow_up_to_kmh": 34,
        "anchor_squall_delta_max_kmh": 20,
        "anchor_sustained_allow_up_to_kmh": 32,
        "require_lee": True,
        "max_fetch_km": 1.5,
    },
    "resolution_policy": {
        "family_requires_hourly": True,
        "expert_allows_3h": True,
        "second_model_required_for_medium": True,
    },
    "confidence": {
        "high": {"wind_spread_kmh_lt": 5, "hs_spread_m_lt": 0.2, "min_wave_sources": 2},
        "medium": {"same_band_minor_disagreement": True, "wind_spread_kmh_lt": 8},
        "low": {"cross_band_disagreement_or_3h": True},
    },
    "corridor": {
        "samples": 9,
        "validate_departure_and_return": True,
        "leg_structure_hours": {"transit_out": "1-1.5", "anchor_min": 2, "anchor_max": 4, "transit_back": "1-1.5"},
    },
    "family_hours_local": {"start_h": 8, "end_h": 21},
    "window_hours": {"min": 4, "max": 6},
    "http": {
        "disable_astronomy_http": True,
        "model_order": "icon_seamless,gfs_seamless,ecmwf_ifs04,default",
        "marine_model_order": "meteofrance_wave,ncep_gfswave025,ecmwf_wam025,default",
        "marine_parallel_models": "ncep_gfswave025,ecmwf_wam025",
    },
}

REQUIRED_RULE_KEYS = [
    "overrides.thunder_wmo",
    "overrides.gusts_hard_nogo_kmh",
    "overrides.squall_delta_kmh",
    "wind.family_max_kmh",
    "wind.nogo_min_kmh",
    "wind.onshore_degrade_kmh",
    "sea.family_max_hs_m",
    "sea.nogo_min_hs_m",
    "tp_matrix.transit",
    "tp_matrix.anchor_sheltered",
    "family_hours_local.start_h",
    "family_hours_local.end_h",
]


def rules_path() -> Path:
    return Path(os.getenv("FABLE_RULES_PATH", "rules.yaml"))


def load_rules(path: Path | None = None) -> dict[str, Any]:
    """rules.yaml merged over defaults. Missing file -> defaults (logged)."""
    p = path or rules_path()
    base = json.loads(json.dumps(DEFAULT_RULES))  # deep copy
    try:
        if p.exists():
            data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
            return deep_merge(base, data)
        log.warning("rules.yaml not found (%s) — using built-in defaults.", p)
    except Exception as e:
        log.warning("rules.yaml unreadable (%s) — using built-in defaults.", e)
    return base


NUMERIC_RULE_KEYS = [
    "overrides.gusts_hard_nogo_kmh", "overrides.squall_delta_kmh", "overrides.visibility_km_min",
    "wind.family_max_kmh", "wind.nogo_min_kmh", "wind.onshore_degrade_kmh",
    "sea.family_max_hs_m", "sea.nogo_min_hs_m",
    "family_hours_local.start_h", "family_hours_local.end_h",
]


def validate_rules(rules: dict[str, Any]) -> list[str]:
    """Return list of problems (empty = OK): missing critical keys or non-numeric values."""
    problems = [f"missing: {k}" for k in REQUIRED_RULE_KEYS if dget(rules, k) is None]
    for k in NUMERIC_RULE_KEYS:
        v = dget(rules, k)
        if v is not None and not isinstance(v, (int, float)):
            problems.append(f"not a number: {k}={v!r}")
    return problems


def rules_digest(rules: dict[str, Any]) -> str:
    try:
        raw = json.dumps(rules, sort_keys=True, ensure_ascii=False).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()[:12]
    except Exception:
        return "unknown"


def _parse_leg_span(span: Any, dmin: float, dmax: float) -> tuple[float, float]:
    if isinstance(span, (int, float)):
        return float(span), float(span)
    s = str(span)
    if "-" in s:
        a, b = s.split("-", 1)
        try:
            return float(a), float(b)
        except Exception:
            return dmin, dmax
    try:
        v = float(s)
        return v, v
    except Exception:
        return dmin, dmax


def window_bounds(rules: dict[str, Any]) -> tuple[int, int]:
    """Family window min/max hours. Explicit window_hours wins; else derived
    from corridor legs; clamped to [4, 6] (phase design T-A...A-T)."""
    explicit_min = dget(rules, "window_hours.min")
    explicit_max = dget(rules, "window_hours.max")
    if explicit_min is not None and explicit_max is not None:
        wmin, wmax = int(explicit_min), int(explicit_max)
    else:
        leg = dget(rules, "corridor.leg_structure_hours", {}) or {}
        tmin, tmax = _parse_leg_span(leg.get("transit_out", "1-1.5"), 1.0, 1.5)
        bmin, bmax = _parse_leg_span(leg.get("transit_back", "1-1.5"), 1.0, 1.5)
        amin = float(leg.get("anchor_min", 2))
        amax = float(leg.get("anchor_max", 4))
        wmin = int(round(tmin + amin + bmin))
        wmax = int(round(tmax + amax + bmax))
    wmin = max(4, min(wmin, 6))
    wmax = max(wmin, min(wmax, 6))
    return wmin, wmax


def normalize_rules(rules: dict[str, Any]) -> dict[str, Any]:
    """Flat rules.yaml -> normalized structure published as rules.normalized.json
    (consumed by FABLE AI / dashboard). Schema preserved from v1 pipeline."""
    win_min, win_max = window_bounds(rules)
    return {
        "meta": {"version": 2, "tz_default": "Africa/Tunis", "source_schema": "flat"},
        "family": {
            "hours_local": {
                "start": int(dget(rules, "family_hours_local.start_h", 8)),
                "end": int(dget(rules, "family_hours_local.end_h", 21)),
            },
            "window_hours": {"min": win_min, "max": win_max},
            "thresholds": {
                "wind": {
                    "family_max_kmh": float(dget(rules, "wind.family_max_kmh", 20)),
                    "no_go_min_kmh": float(dget(rules, "wind.nogo_min_kmh", 25)),
                    "onshore_downgrade_kmh": float(dget(rules, "wind.onshore_degrade_kmh", 22)),
                },
                "gusts": {
                    "no_go_min_kmh": float(dget(rules, "overrides.gusts_hard_nogo_kmh", 30)),
                    "squall_delta_kmh": float(dget(rules, "overrides.squall_delta_kmh", 17)),
                },
                "waves": {
                    "hs_family_max_m": float(dget(rules, "sea.family_max_hs_m", 0.5)),
                    "hs_no_go_min_m": float(dget(rules, "sea.nogo_min_hs_m", 0.8)),
                    "tp_min_at_hs_lt_0_4_s": float(dget(rules, "tp_matrix.transit.hs_lt_0_4_family_tp_s", 3.2)),
                    "tp_min_at_hs_0_4_0_5_s": float(dget(rules, "tp_matrix.transit.hs_0_4_0_5_family_tp_s", 4.5)),
                },
                "visibility_km_min": float(dget(rules, "overrides.visibility_km_min", 5.0)),
            },
            "combined": {
                "short_steep": {
                    "downgrade": {
                        "hs_min_m": float(dget(rules, "combined.short_steep_downgrade.hs_min_m", 0.5)),
                        "tp_max_s": float(dget(rules, "combined.short_steep_downgrade.tp_max_s", 6.0)),
                    },
                    "hard_nogo": {
                        "hs_min_m": float(dget(rules, "combined.short_steep_hard_nogo.hs_min_m", 0.6)),
                        "tp_max_s": float(dget(rules, "combined.short_steep_hard_nogo.tp_max_s", 5.0)),
                    },
                },
                "hysteresis": {
                    "hs_m": float(dget(rules, "hysteresis.hs_m", 0.05)),
                    "wind_kmh": float(dget(rules, "hysteresis.wind_kmh", 1.0)),
                },
            },
            "shelter_bonus": {
                "enabled": True,
                "radius_km_default": float(dget(rules, "shelter.radius_km_default", 3)),
                "apply_on_transit": bool(dget(rules, "shelter.apply_on_transit", False)),
                "anchor": {
                    "gusts_allow_up_to_kmh": float(dget(rules, "shelter.anchor_gusts_allow_up_to_kmh", 34)),
                    "sustained_allow_up_to_kmh": float(dget(rules, "shelter.anchor_sustained_allow_up_to_kmh", 32)),
                    "squall_delta_max_kmh": float(dget(rules, "shelter.anchor_squall_delta_max_kmh", 20)),
                    "require_lee": bool(dget(rules, "shelter.require_lee", True)),
                    "max_fetch_km": float(dget(rules, "shelter.max_fetch_km", 1.5)),
                },
            },
            "anchor_sheltered": {
                "waves": {
                    "hs_max_m": float(dget(rules, "tp_matrix.anchor_sheltered.hs_max_m", 0.35)),
                    "hs_le_0_35_family_tp_s": float(
                        dget(rules, "tp_matrix.anchor_sheltered.hs_le_0_35_family_tp_s", 3.2)
                    ),
                    "hs_le_0_35_expert_tp_min_s": float(
                        dget(rules, "tp_matrix.anchor_sheltered.hs_le_0_35_expert_tp_min_s", 3.5)
                    ),
                },
            },
            "corridor": {
                "check": True,
                "buffer_km": 5,
                "samples": int(dget(rules, "corridor.samples", 9)),
                "validate_departure_and_return": bool(dget(rules, "corridor.validate_departure_and_return", True)),
            },
            "thunder_codes": [int(x) for x in dget(rules, "overrides.thunder_wmo", [95, 96, 99])],
        },
        "confidence": {
            "high": {
                "wind_spread_kmh": float(dget(rules, "confidence.high.wind_spread_kmh_lt", 5)),
                "hs_spread_m": float(dget(rules, "confidence.high.hs_spread_m_lt", 0.2)),
                "min_wave_sources": int(dget(rules, "confidence.high.min_wave_sources", 2)),
            },
            "medium_wind_spread_kmh": float(dget(rules, "confidence.medium.wind_spread_kmh_lt", 8.0)),
            "cap_high_if_single_wave_source": True,
            "min_wind_models_for_not_low": (
                2 if bool(dget(rules, "resolution_policy.second_model_required_for_medium", True)) else 1
            ),
        },
    }


# ---------------------------------------------------------------------------
# Sites
# ---------------------------------------------------------------------------
# Legacy onshore sectors (v1 sites.yaml has no sectors; these mirror the map
# previously hardcoded in reader.py).
LEGACY_ONSHORE_SECTORS = {
    "gammarth-port": [(30, 150)],
    "gammarth": [(30, 150)],
    "sidi-bou-said": [(30, 150)],
    "ghar-el-melh": [(10, 130)],
    "el-haouaria": [(330, 360), (0, 70)],
    "ras-fartass": [(330, 360), (0, 70)],
    "korbous": [(30, 150)],
    "kelibia": [(330, 360), (0, 70)],
}
DEFAULT_ONSHORE_SECTORS = [(20, 160)]
LEGACY_EXCLUDE = {"korbous", "kelibia"}
LEGACY_HOME = "gammarth-port"


def _norm_sectors(raw: Any) -> list[tuple[int, int]] | None:
    if not isinstance(raw, list) or not raw:
        return None
    out = []
    for pair in raw:
        if isinstance(pair, (list, tuple)) and len(pair) == 2:
            out.append((int(pair[0]), int(pair[1])))
    return out or None


class SitesConfig:
    """Parsed sites.yaml (v1 list or v2 mapping)."""

    def __init__(self, sites: list[dict[str, Any]], home: str, tz: str, exclude: set, version: int):
        self.sites = sites          # each: name, slug, lat, lon, shelter_bonus_radius_km, onshore_sectors
        self.home = home            # home-port slug
        self.tz = tz
        self.exclude = exclude
        self.version = version

    def site(self, slug: str) -> dict[str, Any] | None:
        return next((s for s in self.sites if s["slug"] == slug), None)

    def onshore_sectors(self, slug: str) -> list[tuple[int, int]]:
        s = self.site(slug)
        if s and s.get("onshore_sectors"):
            return s["onshore_sectors"]
        return LEGACY_ONSHORE_SECTORS.get(slug, DEFAULT_ONSHORE_SECTORS)


def load_sites(path: Path, only: set | None = None) -> SitesConfig:
    """Load sites.yaml. v1 = plain list of sites; v2 = mapping with
    home/tz/defaults/exclude/sites. Raises ValueError on invalid content."""
    data = yaml.safe_load(path.read_text(encoding="utf-8"))

    if isinstance(data, list):  # ---- v1 (legacy) ----
        version, tz, home = 1, "Africa/Tunis", LEGACY_HOME
        exclude = set(LEGACY_EXCLUDE)
        raw_sites, defaults = data, {}
    elif isinstance(data, dict) and isinstance(data.get("sites"), list):  # ---- v2 ----
        version = int(data.get("version", 2))
        tz = data.get("tz", "Africa/Tunis")
        home = slugify(str(data.get("home", LEGACY_HOME)))
        exclude = {slugify(str(x)) for x in (data.get("exclude") or [])}
        raw_sites = data["sites"]
        defaults = data.get("defaults") or {}
    else:
        raise ValueError("sites.yaml malformed: expected a list (v1) or a mapping with 'sites' (v2)")

    default_sectors = _norm_sectors(defaults.get("onshore_sectors")) or None
    default_shelter = float(defaults.get("shelter_bonus_radius_km", 0.0))

    sites: list[dict[str, Any]] = []
    for s in raw_sites:
        if not isinstance(s, dict):
            continue
        name = s.get("name") or "Site"
        slug = slugify(name)
        if slug in exclude:
            log.info("Excluded by policy: %s", name)
            continue
        if only and slug not in only:
            continue
        try:
            lat, lon = float(s["lat"]), float(s["lon"])
        except Exception:
            log.warning("Invalid coordinates for %s — skipped.", name)
            continue
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            log.warning("Out-of-range coordinates for %s — skipped.", name)
            continue
        sectors = _norm_sectors(s.get("onshore_sectors")) or default_sectors \
            or LEGACY_ONSHORE_SECTORS.get(slug, DEFAULT_ONSHORE_SECTORS)
        sites.append({
            "name": name,
            "slug": slug,
            "lat": lat,
            "lon": lon,
            "shelter_bonus_radius_km": float(s.get("shelter_bonus_radius_km", default_shelter)),
            "onshore_sectors": sectors,
        })

    if not sites:
        raise ValueError("No site selected (empty sites.yaml or FABLE_ONLY_SITES filter too strict)")
    if version == 1 and not any(s["slug"] == home for s in sites):
        # legacy files never declared a home; fall back to the first site
        log.warning("legacy sites.yaml: home '%s' not present — using first site '%s'", home, sites[0]["slug"])
        home = sites[0]["slug"]
    return SitesConfig(sites, home, tz, exclude, version)
