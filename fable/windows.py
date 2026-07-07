"""Family GO window detection (Transit–Anchor–Transit phases).

Fixes vs v1 reader.py:
- spot files are recognized by CONTENT (meta + hourly.time), so catalog.json,
  rules.normalized.json etc. can never appear as boating destinations;
- onshore sectors come from the spot JSON meta or sites.yaml (config-driven),
  with the legacy hardcoded map as last-resort fallback;
- window length capped to the phase design (4–6 h) via rules window_hours;
- thresholds come from fable.config (single source of defaults).
"""

from __future__ import annotations

import datetime as dt
import json
import logging
import math
import statistics
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from .config import DEFAULT_ONSHORE_SECTORS, LEGACY_ONSHORE_SECTORS, load_rules, window_bounds
from .util import angle_in_ranges, dget, slugify

log = logging.getLogger("fable.windows")

NON_SPOT_FILES = {
    "index.json", "index.spots.json", "windows.json", "catalog.json",
    "status.json", "rules.normalized.json", "sites.normalized.json", "config.normalized.json",
}


# ---------------------------------------------------------------------------
# Thresholds (resolved once per run from rules)
# ---------------------------------------------------------------------------
@dataclass
class Thresholds:
    wind_family_max: float
    wind_no_go_min: float
    gust_no_go_min: float
    squall_delta: float
    hs_family_max: float
    hs_no_go_min: float
    tp_min_at_lt04: float
    tp_min_at_04_05: float
    family_hour_start: int
    family_hour_end: int
    short_steep_1_hs: float
    short_steep_1_tp: float
    short_steep_2_hs: float
    short_steep_2_tp: float
    vis_min_km: float
    onshore_max_ok: float
    thunder_codes: set
    anchor_hs_ease_max: float
    anchor_tp_family: float
    anchor_gust_allow: float
    anchor_squall_delta_max: float
    anchor_sustained_allow: float
    high_wind_spread_lt: float
    high_hs_spread_lt: float
    medium_wind_spread_lt: float
    min_models_not_low: int
    min_wave_sources: int

    @classmethod
    def from_rules(cls, rules: dict[str, Any]) -> Thresholds:
        return cls(
            wind_family_max=float(dget(rules, "wind.family_max_kmh", 20)),
            wind_no_go_min=float(dget(rules, "wind.nogo_min_kmh", 25)),
            gust_no_go_min=float(dget(rules, "overrides.gusts_hard_nogo_kmh", 30)),
            squall_delta=float(dget(rules, "overrides.squall_delta_kmh", 17)),
            hs_family_max=float(dget(rules, "sea.family_max_hs_m", 0.5)),
            hs_no_go_min=float(dget(rules, "sea.nogo_min_hs_m", 0.8)),
            tp_min_at_lt04=float(dget(rules, "tp_matrix.transit.hs_lt_0_4_family_tp_s", 3.2)),
            tp_min_at_04_05=float(dget(rules, "tp_matrix.transit.hs_0_4_0_5_family_tp_s", 4.5)),
            family_hour_start=int(dget(rules, "family_hours_local.start_h", 8)),
            family_hour_end=int(dget(rules, "family_hours_local.end_h", 21)),
            short_steep_1_hs=float(dget(rules, "combined.short_steep_downgrade.hs_min_m", 0.5)),
            short_steep_1_tp=float(dget(rules, "combined.short_steep_downgrade.tp_max_s", 6.0)),
            short_steep_2_hs=float(dget(rules, "combined.short_steep_hard_nogo.hs_min_m", 0.6)),
            short_steep_2_tp=float(dget(rules, "combined.short_steep_hard_nogo.tp_max_s", 5.0)),
            vis_min_km=float(dget(rules, "overrides.visibility_km_min", 5.0)),
            onshore_max_ok=float(dget(rules, "wind.onshore_degrade_kmh", 22)),
            thunder_codes=set(dget(rules, "overrides.thunder_wmo", [95, 96, 99])),
            anchor_hs_ease_max=float(dget(rules, "tp_matrix.anchor_sheltered.hs_max_m", 0.35)),
            anchor_tp_family=float(dget(rules, "tp_matrix.anchor_sheltered.hs_le_0_35_family_tp_s", 3.2)),
            anchor_gust_allow=float(dget(rules, "shelter.anchor_gusts_allow_up_to_kmh", 34)),
            anchor_squall_delta_max=float(dget(rules, "shelter.anchor_squall_delta_max_kmh", 20)),
            anchor_sustained_allow=float(dget(rules, "shelter.anchor_sustained_allow_up_to_kmh", 32)),
            high_wind_spread_lt=float(dget(rules, "confidence.high.wind_spread_kmh_lt", 5)),
            high_hs_spread_lt=float(dget(rules, "confidence.high.hs_spread_m_lt", 0.2)),
            medium_wind_spread_lt=float(dget(rules, "confidence.medium.wind_spread_kmh_lt", 8)),
            min_models_not_low=(
                2 if bool(dget(rules, "resolution_policy.second_model_required_for_medium", True)) else 1
            ),
            min_wave_sources=int(dget(rules, "confidence.high.min_wave_sources", 2)),
        )


# ---------------------------------------------------------------------------
# Site model
# ---------------------------------------------------------------------------
@dataclass
class Site:
    name: str
    slug: str
    lat: float
    lon: float
    tz: ZoneInfo
    times: list[dt.datetime]
    wind_models: dict[str, dict[str, list[float | None]]]
    waves: dict[str, list[float | None]]
    waves_models: dict[str, dict[str, list[float | None]]]
    onshore_sectors: list[tuple[int, int]]
    transit_speed_kts: dict[str, float] | None
    route_origin: str | None
    route_points: list[dict[str, Any]]
    windows_enabled: bool
    path: Path


@dataclass
class HourMetrics:
    max_speed: float | None
    min_speed: float | None
    max_gust: float | None
    spread_speed: float | None
    any_dir: float | None
    any_onshore: bool | None
    min_vis: float | None
    codes: list[int]
    hs: float | None
    tp: float | None
    n_models: int
    hs_spread: float | None
    n_wave_sources: int


def is_spot_payload(d: Any) -> bool:
    """A spot file has meta + non-empty hourly.time. Content-based, so
    inventory/status files are never mistaken for destinations."""
    return (
        isinstance(d, dict)
        and isinstance(d.get("meta"), dict)
        and isinstance(d.get("hourly"), dict)
        and isinstance(d["hourly"].get("time"), list)
        and len(d["hourly"]["time"]) > 0
    )


def _vis_to_km(vis: Any) -> list[float | None] | None:
    if not isinstance(vis, list):
        return None
    if any(v is not None and isinstance(v, (int, float)) and v > 50 for v in vis):
        return [(v / 1000.0) if isinstance(v, (int, float)) else None for v in vis]
    return [float(v) if v is not None else None for v in vis]


def _sectors_from_meta(meta: dict[str, Any], slug: str) -> list[tuple[int, int]]:
    raw = meta.get("onshore_sectors")
    if isinstance(raw, list) and raw:
        out = []
        for pair in raw:
            if isinstance(pair, (list, tuple)) and len(pair) == 2:
                out.append((int(pair[0]), int(pair[1])))
        if out:
            return out
    key = slug.replace(".json", "").lower()
    return LEGACY_ONSHORE_SECTORS.get(key, DEFAULT_ONSHORE_SECTORS)


def _transit_speed_from_meta(meta: dict[str, Any]) -> dict[str, float] | None:
    raw = meta.get("transit_speed_kts")
    if isinstance(raw, dict):
        lo = raw.get("min")
        hi = raw.get("max")
    elif isinstance(raw, (list, tuple)) and len(raw) == 2:
        lo, hi = raw
    else:
        return None
    try:
        lo_f = float(lo)
        hi_f = float(hi)
    except Exception:
        return None
    lo_f, hi_f = min(lo_f, hi_f), max(lo_f, hi_f)
    if lo_f <= 0 or hi_f <= 0:
        return None
    return {"min": lo_f, "max": hi_f}


def _route_points_from_meta(meta: dict[str, Any]) -> list[dict[str, Any]]:
    raw = meta.get("route_points")
    if not isinstance(raw, list):
        return []
    out = []
    for point in raw:
        if not isinstance(point, dict):
            continue
        try:
            lat = float(point["lat"])
            lon = float(point["lon"])
        except Exception:
            continue
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            continue
        out.append({
            "lat": lat,
            "lon": lon,
            "name": (str(point.get("name", "")).strip() or None),
            "slug": (slugify(str(point.get("slug", "")).strip()) or None),
        })
    return out


def load_site(path: Path) -> Site | None:
    """Parse one public/*.json spot file; None if it is not a spot payload."""
    d = json.loads(path.read_text(encoding="utf-8"))
    if not is_spot_payload(d):
        return None
    meta = d["meta"]
    try:
        tz = ZoneInfo(meta.get("tz") or meta.get("timezone") or "Africa/Tunis")
    except Exception:
        tz = ZoneInfo("UTC")

    hourly = d["hourly"]
    times: list[dt.datetime] = []
    for t in hourly["time"]:
        tt = dt.datetime.fromisoformat(t)
        times.append(tt.replace(tzinfo=tz) if tt.tzinfo is None else tt.astimezone(tz))

    vis_km = _vis_to_km(hourly.get("visibility"))

    wind_models: dict[str, dict[str, Any]] = {}
    models = d.get("models") or {}
    if isinstance(models, dict):
        for mname, mobj in models.items():
            hh = (mobj or {}).get("hourly") or {}
            if not isinstance(hh, dict):
                continue
            wind_models[mname] = {
                "wind_speed_10m": hh.get("wind_speed_10m"),
                "wind_gusts_10m": hh.get("wind_gusts_10m"),
                "wind_direction_10m": hh.get("wind_direction_10m"),
                "weather_code": hh.get("weather_code"),
                "visibility_km": _vis_to_km(hh.get("visibility")),
            }
    if not wind_models:
        wind_models = {"om": {
            "wind_speed_10m": hourly.get("wind_speed_10m"),
            "wind_gusts_10m": hourly.get("wind_gusts_10m"),
            "wind_direction_10m": hourly.get("wind_direction_10m"),
            "weather_code": hourly.get("weather_code"),
            "visibility_km": vis_km,
        }}

    waves_models: dict[str, dict[str, Any]] = {}
    marine_models = d.get("marine_models") or {}
    if isinstance(marine_models, dict):
        for mname, mobj in marine_models.items():
            hh = (mobj or {}).get("hourly") or {}
            if not isinstance(hh, dict):
                continue
            hs_arr = hh.get("wave_height")
            tp_arr = hh.get("wave_period")
            if isinstance(hs_arr, list) and any(v is not None for v in hs_arr):
                waves_models[mname] = {"hs": hs_arr, "tp": tp_arr if isinstance(tp_arr, list) else []}
    if not waves_models:
        hs_arr = hourly.get("hs") or hourly.get("wave_height")
        tp_arr = hourly.get("tp") or hourly.get("wave_period")
        if isinstance(hs_arr, list) and any(v is not None for v in hs_arr):
            waves_models = {"om": {"hs": hs_arr, "tp": tp_arr if isinstance(tp_arr, list) else []}}

    slug = meta.get("slug", path.name)
    return Site(
        name=meta.get("name", meta.get("site_name", path.stem)),
        slug=slug,
        lat=float(meta.get("lat", 0.0)),
        lon=float(meta.get("lon", 0.0)),
        tz=tz,
        times=times,
        wind_models=wind_models,
        waves={
            "significant_wave_height": hourly.get("hs") or hourly.get("wave_height"),
            "wave_period": hourly.get("tp") or hourly.get("wave_period"),
        },
        waves_models=waves_models,
        onshore_sectors=_sectors_from_meta(meta, slug),
        transit_speed_kts=_transit_speed_from_meta(meta),
        route_origin=(slugify(str(meta.get("route_origin", "")).strip()) or None),
        route_points=_route_points_from_meta(meta),
        windows_enabled=bool(meta.get("windows_enabled", True)),
        path=path,
    )


# ---------------------------------------------------------------------------
# Hourly metrics (worst-value-wins across models)
# ---------------------------------------------------------------------------
def _safe_get(arr: list[Any] | None, i: int) -> Any:
    return None if arr is None or i >= len(arr) else arr[i]


def worst_metrics_at_hour(site: Site, idx: int) -> HourMetrics:
    speeds, gusts, dirs, vis, codes = [], [], [], [], []
    n_models = 0
    for arrs in site.wind_models.values():
        sp = arrs.get("wind_speed_10m") or []
        gu = arrs.get("wind_gusts_10m") or []
        di = arrs.get("wind_direction_10m") or []
        vc = arrs.get("visibility_km") or []
        wc = arrs.get("weather_code") or []
        if idx < len(sp) and sp[idx] is not None and idx < len(gu) and gu[idx] is not None \
                and idx < len(di) and di[idx] is not None:
            speeds.append(sp[idx]); gusts.append(gu[idx]); dirs.append(di[idx])
            if idx < len(vc) and vc[idx] is not None:
                vis.append(vc[idx])
            if idx < len(wc) and wc[idx] is not None:
                try:
                    codes.append(int(wc[idx]))
                except (TypeError, ValueError):
                    pass
            n_models += 1

    # Waves: worst-value-wins across wave models.
    # Worst Hs = highest; worst Tp = SHORTEST period (steeper, more dangerous sea).
    hs_vals = []
    tp_vals = []
    for arrs in site.waves_models.values():
        hv = _safe_get(arrs.get("hs"), idx)
        if hv is not None:
            hs_vals.append(hv)
        tv = _safe_get(arrs.get("tp"), idx)
        if tv is not None:
            tp_vals.append(tv)
    if hs_vals:
        hs = max(hs_vals)
        tp = min(tp_vals) if tp_vals else None
    else:  # fallback to flat series (very old payloads)
        hs = _safe_get(site.waves.get("significant_wave_height"), idx)
        tp = _safe_get(site.waves.get("wave_period"), idx)
    hs_spread = (max(hs_vals) - min(hs_vals)) if len(hs_vals) >= 2 else None
    n_wave_sources = len(hs_vals)
    any_onshore = any(angle_in_ranges(d, site.onshore_sectors) for d in dirs) if dirs else None

    return HourMetrics(
        max_speed=max(speeds) if speeds else None,
        min_speed=min(speeds) if speeds else None,
        max_gust=max(gusts) if gusts else None,
        spread_speed=(max(speeds) - min(speeds)) if len(speeds) >= 2 else None,
        any_dir=dirs[0] if dirs else None,
        any_onshore=any_onshore,
        min_vis=min(vis) if vis else None,
        codes=codes,
        hs=hs,
        tp=tp,
        n_models=n_models,
        hs_spread=hs_spread,
        n_wave_sources=n_wave_sources,
    )


def has_wind_range(site: Site, i0: int, i1: int) -> bool:
    for i in range(i0, i1 + 1):
        ok_hour = False
        for arrs in site.wind_models.values():
            sp = arrs.get("wind_speed_10m") or []
            gu = arrs.get("wind_gusts_10m") or []
            di = arrs.get("wind_direction_10m") or []
            if i < len(sp) and sp[i] is not None and i < len(gu) and gu[i] is not None \
                    and i < len(di) and di[i] is not None:
                ok_hour = True
                break
        if not ok_hour:
            return False
    return True


# ---------------------------------------------------------------------------
# Per-hour evaluation by phase
# ---------------------------------------------------------------------------
def _waves_ok_transit(m: HourMetrics, th: Thresholds, reasons: list[str]) -> bool:
    ok = True
    if m.hs is None or m.tp is None:
        reasons.append("vagues_inconnues")
        return False
    if m.hs > th.hs_no_go_min:
        ok = False; reasons.append(f"Hs>{th.hs_no_go_min}")
    if m.hs >= th.hs_family_max:
        ok = False; reasons.append(f"Hs>={th.hs_family_max}")
    else:
        if m.hs < 0.4 and m.tp < th.tp_min_at_lt04:
            ok = False; reasons.append(f"Tp<{th.tp_min_at_lt04}@Hs<0.4")
        if 0.4 <= m.hs < 0.5 and m.tp < th.tp_min_at_04_05:
            ok = False; reasons.append(f"Tp<{th.tp_min_at_04_05}@Hs0.4-0.5")
    if m.hs >= th.short_steep_1_hs and m.tp <= th.short_steep_1_tp:
        ok = False; reasons.append("short_steep")
    if m.hs >= th.short_steep_2_hs and m.tp <= th.short_steep_2_tp:
        ok = False; reasons.append("short_steep_hard")
    return ok


def _waves_ok_anchor(m: HourMetrics, th: Thresholds, reasons: list[str]) -> bool:
    if m.hs is None or m.tp is None:
        reasons.append("vagues_inconnues")
        return False
    if m.hs <= th.anchor_hs_ease_max:
        if m.tp < th.anchor_tp_family:
            reasons.append(f"Tp<{th.anchor_tp_family}@Hs<={th.anchor_hs_ease_max}")
            return False
        return True
    return _waves_ok_transit(m, th, reasons)


def hour_ok_for_phase(site: Site, idx: int, phase: str, th: Thresholds) -> tuple[bool, dict[str, Any]]:
    m = worst_metrics_at_hour(site, idx)
    reasons: list[str] = []
    ok = True

    if any(c in th.thunder_codes for c in m.codes):
        return False, {"reasons": ["orages"], "metrics": m}

    if m.min_vis is not None and m.min_vis < th.vis_min_km:
        ok = False; reasons.append(f"vis<{th.vis_min_km:g}km")

    if m.max_speed is not None and m.any_onshore and m.max_speed > th.onshore_max_ok:
        ok = False; reasons.append(f"onshore>{int(th.onshore_max_ok)}")

    if m.max_gust is not None and m.min_speed is not None:
        delta = m.max_gust - m.min_speed
        if phase == "anchor":
            if delta >= th.anchor_squall_delta_max:
                ok = False; reasons.append("squalls_anchor")
        elif delta >= th.squall_delta:
            ok = False; reasons.append("squalls")

    if phase == "anchor":
        if m.max_gust is not None and m.max_gust >= th.anchor_gust_allow:
            ok = False; reasons.append(f"gusts>={int(th.anchor_gust_allow)}@anchor")
        if m.max_speed is not None and m.max_speed >= th.anchor_sustained_allow:
            ok = False; reasons.append(f"vent>={int(th.anchor_sustained_allow)}@anchor")
        if not _waves_ok_anchor(m, th, reasons):
            ok = False
    else:
        if m.max_gust is not None and m.max_gust >= th.gust_no_go_min:
            ok = False; reasons.append(f"rafales>={int(th.gust_no_go_min)}")
        if m.max_speed is not None and m.max_speed >= th.wind_no_go_min:
            ok = False; reasons.append(f"vent>={int(th.wind_no_go_min)}")
        if m.max_speed is not None and m.max_speed >= th.wind_family_max:
            ok = False; reasons.append(f"vent>={int(th.wind_family_max)}")
        if not _waves_ok_transit(m, th, reasons):
            ok = False

    return ok, {"reasons": reasons, "metrics": m}


# ---------------------------------------------------------------------------
# Confidence
# ---------------------------------------------------------------------------
def compute_confidence(site: Site, i0: int, i1: int, th: Thresholds) -> str:
    """High requires: >=2 wind models with small spread, AND >=2 wave models
    agreeing within hs_spread threshold on EVERY hour of the window.
    With a single wave source, confidence is capped at Medium (v1 behaviour —
    the cap is now conditional instead of unconditional)."""
    wind_spreads = []
    min_models = float("inf")
    min_wave_sources = float("inf")
    max_hs_spread = None
    for i in range(i0, i1 + 1):
        m = worst_metrics_at_hour(site, i)
        if m.spread_speed is not None:
            wind_spreads.append(m.spread_speed)
        min_models = min(min_models, m.n_models or 0)
        min_wave_sources = min(min_wave_sources, m.n_wave_sources or 0)
        if m.hs_spread is not None:
            max_hs_spread = m.hs_spread if max_hs_spread is None else max(max_hs_spread, m.hs_spread)

    if min_models < th.min_models_not_low:
        return "Low"

    avg_wind_spread = statistics.mean(wind_spreads) if wind_spreads else None
    waves_corroborated = (
        min_wave_sources >= th.min_wave_sources
        and max_hs_spread is not None
        and max_hs_spread < th.high_hs_spread_lt
    )

    if (avg_wind_spread is not None and avg_wind_spread < th.high_wind_spread_lt) and waves_corroborated:
        result = "High"
    elif avg_wind_spread is not None and avg_wind_spread < th.medium_wind_spread_lt:
        result = "Medium"
    else:
        result = "Low"

    if min_wave_sources < th.min_wave_sources and result == "High":
        result = "Medium"
    return result


def _confidence_rank(value: str) -> int:
    return {"Low": 1, "Medium": 2, "High": 3}.get(value, 0)


def _min_confidence(values: Sequence[str]) -> str:
    cleaned = [v for v in values if v]
    if not cleaned:
        return "Low"
    return min(cleaned, key=_confidence_rank)


def _route_site_key(point: dict[str, Any], sites: dict[str, Site]) -> str | None:
    slug = point.get("slug")
    if slug:
        fname = f"{slug}.json"
        if fname in sites:
            return fname
    name = point.get("name")
    if name:
        fname = f"{slugify(name)}.json"
        if fname in sites:
            return fname
    lat = point.get("lat")
    lon = point.get("lon")
    if lat is None or lon is None:
        return None
    for fname, site in sites.items():
        if abs(site.lat - float(lat)) < 0.02 and abs(site.lon - float(lon)) < 0.02:
            return fname
    return None


def _route_checkpoints(origin: Site, dest: Site, sites: dict[str, Site]) -> list[Site]:
    checkpoints = [origin]
    for point in dest.route_points:
        key = _route_site_key(point, sites)
        if key and key in sites and all(existing.path != sites[key].path for existing in checkpoints):
            checkpoints.append(sites[key])
    if all(existing.path != dest.path for existing in checkpoints):
        checkpoints.append(dest)
    return checkpoints


def _dist_km(a: dict[str, float], b: dict[str, float]) -> float:
    lat1 = math.radians(float(a["lat"]))
    lat2 = math.radians(float(b["lat"]))
    d_lat = lat2 - lat1
    d_lon = math.radians(float(b["lon"]) - float(a["lon"]))
    x = math.sin(d_lat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(d_lon / 2) ** 2
    return 6371.0 * 2 * math.asin(math.sqrt(x))


def _route_distance_km(origin: Site, dest: Site) -> float:
    points = [{"lat": origin.lat, "lon": origin.lon}]
    points.extend({"lat": p["lat"], "lon": p["lon"]} for p in dest.route_points)
    points.append({"lat": dest.lat, "lon": dest.lon})
    total = 0.0
    for i in range(1, len(points)):
        total += _dist_km(points[i - 1], points[i])
    return total


def _route_transit_profile(origin: Site, dest: Site) -> tuple[float, float]:
    speed = dest.transit_speed_kts or {"min": 16.0, "max": 24.0}
    distance_nm = _route_distance_km(origin, dest) / 1.852
    return distance_nm / float(speed["max"]), distance_nm / float(speed["min"])


def detect_transfer_windows(origin: Site, dest: Site, checkpoints: list[Site], th: Thresholds) -> list[dict[str, Any]]:
    if not checkpoints:
        return []
    min_h, max_h = _route_transit_profile(origin, dest)
    span_hours = max(1, math.ceil(max_h))
    n = min(len(site.times) for site in checkpoints)
    windows: list[dict[str, Any]] = []
    i = 0
    while i + span_hours <= n:
        j = i + span_hours - 1
        ok = True
        confs = []
        for site in checkpoints:
            if not has_wind_range(site, i, j):
                ok = False
                break
            for idx in range(i, j + 1):
                hour_ok, _ = hour_ok_for_phase(site, idx, "transit", th)
                if not hour_ok:
                    ok = False
                    break
            if not ok:
                break
            confs.append(compute_confidence(site, i, j, th))
        if ok:
            start_dt = origin.times[i]
            windows.append({
                "start": start_dt.isoformat(),
                "arrival_earliest": (start_dt + dt.timedelta(hours=min_h)).isoformat(),
                "arrival_latest": (start_dt + dt.timedelta(hours=max_h)).isoformat(),
                "hours": {"min": round(min_h, 2), "max": round(max_h, 2)},
                "confidence": _min_confidence(confs),
                "category": "family" if _all_in_family_hours(origin.times[i:j + 1], origin.tz, th) else "off_hours",
                "checkpoints": [site.slug for site in checkpoints],
            })
        i += 1
    return windows


def combine_composite_windows(home: Site, relay: Site, dest: Site, relay_windows: list[dict[str, Any]],
                              offshore_windows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for ow in offshore_windows:
        start_dt = dt.datetime.fromisoformat(ow["start"])
        eligible = []
        for rw in relay_windows:
            arrival_latest = dt.datetime.fromisoformat(rw["arrival_latest"])
            if arrival_latest <= start_dt:
                eligible.append(rw)
        if not eligible:
            continue
        transfer = max(eligible, key=lambda item: item["arrival_latest"])
        transfer_arrival = dt.datetime.fromisoformat(transfer["arrival_latest"])
        staging_hours = max(0.0, (start_dt - transfer_arrival).total_seconds() / 3600.0)
        out.append({
            **ow,
            "confidence": _min_confidence([ow.get("confidence", "Low"), transfer.get("confidence", "Low")]),
            "category": "family" if ow.get("category") == "family" and transfer.get("category") == "family" else "off_hours",
            "reason": "valid_composite_beta",
            "composite": {
                "transfer_origin": f"{home.slug}.json",
                "route_origin": f"{relay.slug}.json",
                "transfer_start": transfer["start"],
                "transfer_arrival_earliest": transfer["arrival_earliest"],
                "transfer_arrival_latest": transfer["arrival_latest"],
                "transfer_hours": transfer["hours"],
                "transfer_confidence": transfer["confidence"],
                "transfer_category": transfer["category"],
                "staging_hours": round(staging_hours, 2),
            },
        })
    return out


# ---------------------------------------------------------------------------
# Window detection
# ---------------------------------------------------------------------------
def phases_for_window(length: int) -> list[str]:
    """L=4: T A A T ; L=5: T A A A T ; L=6: T A A A A T."""
    if length < 4:
        return ["transit"] * length
    if length == 4:
        return ["transit", "anchor", "anchor", "transit"]
    if length == 5:
        return ["transit", "anchor", "anchor", "anchor", "transit"]
    return ["transit"] + ["anchor"] * (length - 2) + ["transit"]


def _all_in_family_hours(dts: Sequence[dt.datetime], tz: ZoneInfo, th: Thresholds) -> bool:
    for t in dts:
        tt = (t if t.tzinfo else t.replace(tzinfo=tz)).astimezone(tz)
        if not (th.family_hour_start <= tt.hour < th.family_hour_end):
            return False
    return True


def _window_ok_dest(dest: Site, i: int, end: int, th: Thresholds) -> tuple[bool, list[str]]:
    phases = phases_for_window(end - i)
    reasons_all: list[str] = []
    for k, idx in enumerate(range(i, end)):
        phase = phases[k] if k < len(phases) else "transit"
        ok_h, det = hour_ok_for_phase(dest, idx, phase, th)
        if not ok_h:
            reasons_all.extend([f"h{idx - i}:{r}" for r in det.get("reasons", [])])
            return False, reasons_all
    return True, reasons_all


def detect_windows(home: Site, dest: Site, min_h: int, max_h: int, th: Thresholds) -> list[dict[str, Any]]:
    n = min(len(dest.times), len(home.times))
    windows: list[dict[str, Any]] = []
    i = 0
    while i < n:
        dep_ok, _ = hour_ok_for_phase(home, i, "transit", th)
        dep_dest_ok, _ = hour_ok_for_phase(dest, i, "transit", th)
        if not (dep_ok and dep_dest_ok):
            i += 1
            continue

        best_end = i
        end = i + 1
        while end <= n and (end - i) <= max_h:
            length = end - i
            if length < min_h:
                end += 1
                continue
            ok_dest, _ = _window_ok_dest(dest, i, end, th)
            if not ok_dest:
                break
            ret_ok, _ = hour_ok_for_phase(home, end - 1, "transit", th)
            if not ret_ok:
                break
            if not has_wind_range(dest, i, end - 1) or not has_wind_range(home, i, end - 1):
                break
            best_end = end
            end += 1

        if best_end - i >= min_h:
            start_dt = dest.times[i]
            end_dt = dest.times[best_end - 1] + dt.timedelta(hours=1)
            category = "family" if _all_in_family_hours(dest.times[i:best_end], dest.tz, th) else "off_hours"
            spreads = [worst_metrics_at_hour(dest, j).spread_speed for j in range(i, best_end)]
            spreads = [s for s in spreads if s is not None]
            models_per_hour = [worst_metrics_at_hour(dest, j).n_models for j in range(i, best_end)]
            wave_sources_per_hour = [worst_metrics_at_hour(dest, j).n_wave_sources for j in range(i, best_end)]
            hs_spreads = [s for s in (worst_metrics_at_hour(dest, j).hs_spread for j in range(i, best_end))
                          if s is not None]
            windows.append({
                "start": start_dt.isoformat(),
                "end": end_dt.isoformat(),
                "hours": best_end - i,
                "confidence": compute_confidence(dest, i, best_end - 1, th),
                "confidence_details": {
                    "min_wind_models_per_hour": min(models_per_hour) if models_per_hour else 0,
                    "avg_wind_spread_kmh": round(statistics.mean(spreads), 2) if spreads else None,
                    "min_wave_sources_per_hour": min(wave_sources_per_hour) if wave_sources_per_hour else 0,
                    "max_hs_spread_m": round(max(hs_spreads), 3) if hs_spreads else None,
                },
                "category": category,
                "reason": "valid_FAMILY_rules" + ("" if category == "family" else "_outside_08_21"),
            })
            i = best_end
        else:
            i += 1
    return windows


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------
def run_reader(from_dir: Path, out_dir: Path, home_slug: str | None,
               min_h: int | None = None, max_h: int | None = None,
               rules: dict[str, Any] | None = None) -> dict[str, Any]:
    rules = rules or load_rules()
    th = Thresholds.from_rules(rules)
    wmin, wmax = window_bounds(rules)
    min_h = min_h if min_h is not None else wmin
    max_h = max_h if max_h is not None else wmax
    if max_h > 6:
        log.warning("max_hours=%d exceeds the Transit–Anchor–Transit design; capping to 6", max_h)
        max_h = 6

    candidates = sorted(p for p in from_dir.glob("*.json")
                        if p.name not in NON_SPOT_FILES and not p.name.startswith("_debug-"))
    sites: dict[str, Site] = {}
    for p in candidates:
        try:
            s = load_site(p)
        except Exception as e:  # noqa: BLE001
            log.warning("skipped (unreadable) %s: %s", p.name, e)
            continue
        if s is None:
            log.info("skipped (not a spot payload): %s", p.name)
            continue
        sites[p.name] = s

    if not sites:
        raise SystemExit(f"No valid spot JSON found in {from_dir}")

    if not home_slug:
        # 1) home port from sites.yaml (multi-port), 2) legacy gammarth heuristic, 3) first site
        try:
            from .config import load_sites
            cfg = load_sites(from_dir.parent / "sites.yaml")
            if f"{cfg.home}.json" in sites:
                home_slug = f"{cfg.home}.json"
        except Exception:  # noqa: BLE001
            pass
    if not home_slug:
        candidates_home = [k for k in sites if "gammarth" in k]
        home_slug = candidates_home[0] if candidates_home else sorted(sites.keys())[0]
    if home_slug not in sites:
        log.warning("--home=%s not found, falling back to first site", home_slug)
        home_slug = sorted(sites.keys())[0]
    home = sites[home_slug]

    out: dict[str, Any] = {
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "home_slug": home_slug,
        "window_hours": {"min": min_h, "max": max_h},
        "rules_digest": None,
        "windows": [],
    }
    try:
        from .config import rules_digest
        out["rules_digest"] = rules_digest(rules)
    except Exception:  # noqa: BLE001
        pass

    for fname, dest in sites.items():
        if fname != home_slug and not dest.windows_enabled:
            log.info("skipped (windows disabled): %s", fname)
            continue
        if fname != home_slug and dest.route_origin:
            relay_fname = f"{dest.route_origin}.json"
            relay = sites.get(relay_fname)
            if relay is None:
                log.warning("composite route origin not found for %s: %s", fname, relay_fname)
                wins = []
            else:
                transfer_windows = detect_transfer_windows(home, relay, _route_checkpoints(home, relay, sites), th)
                offshore_windows = detect_windows(relay, dest, min_h=min_h, max_h=max_h, th=th)
                wins = combine_composite_windows(home, relay, dest, transfer_windows, offshore_windows)
        else:
            wins = detect_windows(home, dest, min_h=min_h, max_h=max_h, th=th)
        out["windows"].append({"dest_slug": fname, "dest_name": dest.name, "windows": wins})

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "windows.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    return out
