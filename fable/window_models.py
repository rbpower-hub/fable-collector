"""Data models and parsing helpers for FABLE navigation windows."""

from __future__ import annotations

import datetime as dt
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from .config import DEFAULT_ONSHORE_SECTORS, LEGACY_ONSHORE_SECTORS
from .util import angle_in_ranges, dget, slugify


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
    thunder_codes: set[int]
    anchor_hs_ease_max: float
    anchor_tp_family: float
    anchor_gust_allow: float
    anchor_sustained_allow: float
    high_wind_spread_lt: float
    high_hs_spread_lt: float
    medium_wind_spread_lt: float
    min_models_not_low: int
    min_wave_sources: int
    prudent_enabled: bool
    prudent_wind_max: float
    prudent_gust_max: float
    prudent_hs_max: float
    prudent_tp_min: float
    prudent_min_confidence: str
    adaptive_enabled: bool
    adaptive_absolute_min_h: int
    adaptive_zone_min_h: float
    daylight_enabled: bool
    daylight_after_sunrise_min: int
    daylight_before_sunset_min: int

    @classmethod
    def from_rules(cls, rules: dict[str, Any]) -> "Thresholds":
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
            thunder_codes={int(x) for x in dget(rules, "overrides.thunder_wmo", [95, 96, 99])},
            anchor_hs_ease_max=float(dget(rules, "tp_matrix.anchor_sheltered.hs_max_m", 0.35)),
            anchor_tp_family=float(dget(rules, "tp_matrix.anchor_sheltered.hs_le_0_35_family_tp_s", 3.2)),
            anchor_gust_allow=float(dget(rules, "shelter.anchor_gusts_allow_up_to_kmh", 34)),
            anchor_sustained_allow=float(dget(rules, "shelter.anchor_sustained_allow_up_to_kmh", 32)),
            high_wind_spread_lt=float(dget(rules, "confidence.high.wind_spread_kmh_lt", 5)),
            high_hs_spread_lt=float(dget(rules, "confidence.high.hs_spread_m_lt", 0.2)),
            medium_wind_spread_lt=float(dget(rules, "confidence.medium.wind_spread_kmh_lt", 8)),
            min_models_not_low=(
                2 if bool(dget(rules, "resolution_policy.second_model_required_for_medium", True)) else 1
            ),
            min_wave_sources=int(dget(rules, "confidence.high.min_wave_sources", 2)),
            prudent_enabled=bool(dget(rules, "prudent.enabled", True)),
            prudent_wind_max=float(dget(rules, "prudent.wind_max_kmh", 22)),
            prudent_gust_max=float(dget(rules, "prudent.gust_max_kmh", 28)),
            prudent_hs_max=float(dget(rules, "prudent.hs_max_m", 0.4)),
            prudent_tp_min=float(dget(rules, "prudent.tp_min_s", 3.5)),
            prudent_min_confidence=str(dget(rules, "prudent.min_confidence", "Medium")),
            adaptive_enabled=bool(dget(rules, "adaptive_window.enabled", True)),
            adaptive_absolute_min_h=int(dget(rules, "adaptive_window.absolute_min_hours", 3)),
            adaptive_zone_min_h=float(dget(rules, "adaptive_window.min_zone_hours", 1.5)),
            daylight_enabled=bool(dget(rules, "daylight.use_astronomy", True)),
            daylight_after_sunrise_min=int(dget(rules, "daylight.start_after_sunrise_min", 30)),
            daylight_before_sunset_min=int(dget(rules, "daylight.end_before_sunset_min", 60)),
        )


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
    shelter_radius_km: float
    daylight: dict[str, tuple[dt.datetime, dt.datetime]]
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


def is_spot_payload(value: Any) -> bool:
    return (
        isinstance(value, dict)
        and isinstance(value.get("meta"), dict)
        and isinstance(value.get("hourly"), dict)
        and isinstance(value["hourly"].get("time"), list)
        and bool(value["hourly"]["time"])
    )


def _safe(values: list[Any] | None, index: int) -> Any:
    return None if values is None or index >= len(values) else values[index]


def _vis_to_km(values: Any) -> list[float | None] | None:
    if not isinstance(values, list):
        return None
    metres = any(isinstance(v, (int, float)) and v > 50 for v in values if v is not None)
    return [
        (float(v) / 1000 if metres else float(v)) if isinstance(v, (int, float)) else None
        for v in values
    ]


def _sectors(meta: dict[str, Any], slug: str) -> list[tuple[int, int]]:
    raw = meta.get("onshore_sectors")
    if isinstance(raw, list):
        parsed = [
            (int(pair[0]), int(pair[1]))
            for pair in raw
            if isinstance(pair, (list, tuple)) and len(pair) == 2
        ]
        if parsed:
            return parsed
    return LEGACY_ONSHORE_SECTORS.get(slug.replace(".json", "").lower(), DEFAULT_ONSHORE_SECTORS)


def _speed_range(meta: dict[str, Any]) -> dict[str, float] | None:
    raw = meta.get("transit_speed_kts")
    if isinstance(raw, dict):
        lo, hi = raw.get("min"), raw.get("max")
    elif isinstance(raw, (list, tuple)) and len(raw) == 2:
        lo, hi = raw
    else:
        return None
    try:
        lo_f, hi_f = sorted((float(lo), float(hi)))
    except (TypeError, ValueError):
        return None
    return {"min": lo_f, "max": hi_f} if lo_f > 0 else None


def _route_points(meta: dict[str, Any]) -> list[dict[str, Any]]:
    output = []
    for point in meta.get("route_points") or []:
        if not isinstance(point, dict):
            continue
        try:
            lat, lon = float(point["lat"]), float(point["lon"])
        except (KeyError, TypeError, ValueError):
            continue
        if -90 <= lat <= 90 and -180 <= lon <= 180:
            output.append({
                "lat": lat,
                "lon": lon,
                "name": str(point.get("name", "")).strip() or None,
                "slug": slugify(str(point.get("slug", "")).strip()) or None,
            })
    return output


def _local_datetime(value: Any, tz: ZoneInfo) -> dt.datetime | None:
    if not value:
        return None
    try:
        parsed = dt.datetime.fromisoformat(str(value))
    except ValueError:
        return None
    return parsed.replace(tzinfo=tz) if parsed.tzinfo is None else parsed.astimezone(tz)


def _daylight(payload: dict[str, Any], tz: ZoneInfo) -> dict[str, tuple[dt.datetime, dt.datetime]]:
    daily = payload.get("daily") or {}
    output = {}
    for index, raw_date in enumerate(daily.get("time") or []):
        sunrises, sunsets = daily.get("sunrise") or [], daily.get("sunset") or []
        if index >= len(sunrises) or index >= len(sunsets):
            continue
        sunrise = _local_datetime(sunrises[index], tz)
        sunset = _local_datetime(sunsets[index], tz)
        if sunrise and sunset and sunrise < sunset:
            output[str(raw_date)[:10]] = (sunrise, sunset)
    return output


def load_site(path: Path) -> Site | None:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not is_spot_payload(payload):
        return None
    meta, hourly = payload["meta"], payload["hourly"]
    try:
        tz = ZoneInfo(meta.get("tz") or meta.get("timezone") or "Africa/Tunis")
    except Exception:
        tz = ZoneInfo("UTC")
    times = []
    for raw in hourly["time"]:
        parsed = dt.datetime.fromisoformat(str(raw))
        times.append(parsed.replace(tzinfo=tz) if parsed.tzinfo is None else parsed.astimezone(tz))

    wind_models = {}
    for name, model in (payload.get("models") or {}).items():
        values = (model or {}).get("hourly") or {}
        if isinstance(values, dict):
            wind_models[name] = {
                "wind_speed_10m": values.get("wind_speed_10m"),
                "wind_gusts_10m": values.get("wind_gusts_10m"),
                "wind_direction_10m": values.get("wind_direction_10m"),
                "weather_code": values.get("weather_code"),
                "visibility_km": _vis_to_km(values.get("visibility")),
            }
    if not wind_models:
        wind_models = {"om": {
            "wind_speed_10m": hourly.get("wind_speed_10m"),
            "wind_gusts_10m": hourly.get("wind_gusts_10m"),
            "wind_direction_10m": hourly.get("wind_direction_10m"),
            "weather_code": hourly.get("weather_code"),
            "visibility_km": _vis_to_km(hourly.get("visibility")),
        }}

    wave_models = {}
    for name, model in (payload.get("marine_models") or {}).items():
        values = (model or {}).get("hourly") or {}
        hs, tp = values.get("wave_height"), values.get("wave_period")
        if isinstance(hs, list) and any(value is not None for value in hs):
            wave_models[name] = {"hs": hs, "tp": tp if isinstance(tp, list) else []}
    if not wave_models:
        hs, tp = hourly.get("hs") or hourly.get("wave_height"), hourly.get("tp") or hourly.get("wave_period")
        if isinstance(hs, list) and any(value is not None for value in hs):
            wave_models = {"om": {"hs": hs, "tp": tp if isinstance(tp, list) else []}}

    slug = str(meta.get("slug") or path.stem)
    return Site(
        name=str(meta.get("name") or meta.get("site_name") or path.stem),
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
        waves_models=wave_models,
        onshore_sectors=_sectors(meta, slug),
        transit_speed_kts=_speed_range(meta),
        route_origin=slugify(str(meta.get("route_origin", "")).strip()) or None,
        route_points=_route_points(meta),
        windows_enabled=bool(meta.get("windows_enabled", True)),
        shelter_radius_km=float(meta.get("shelter_bonus_radius_km", 0.0) or 0.0),
        daylight=_daylight(payload, tz),
        path=path,
    )


def worst_metrics_at_hour(site: Site, index: int) -> HourMetrics:
    speeds, gusts, directions, visibility, codes = [], [], [], [], []
    models = 0
    for values in site.wind_models.values():
        speed = _safe(values.get("wind_speed_10m"), index)
        gust = _safe(values.get("wind_gusts_10m"), index)
        direction = _safe(values.get("wind_direction_10m"), index)
        if speed is None or gust is None or direction is None:
            continue
        speeds.append(float(speed)); gusts.append(float(gust)); directions.append(float(direction))
        visible = _safe(values.get("visibility_km"), index)
        if visible is not None:
            visibility.append(float(visible))
        code = _safe(values.get("weather_code"), index)
        if code is not None:
            try:
                codes.append(int(code))
            except (TypeError, ValueError):
                pass
        models += 1

    hs_values, tp_values = [], []
    for values in site.waves_models.values():
        hs, tp = _safe(values.get("hs"), index), _safe(values.get("tp"), index)
        if hs is not None:
            hs_values.append(float(hs))
        if tp is not None:
            tp_values.append(float(tp))
    if hs_values:
        hs, tp = max(hs_values), min(tp_values) if tp_values else None
    else:
        raw_hs = _safe(site.waves.get("significant_wave_height"), index)
        raw_tp = _safe(site.waves.get("wave_period"), index)
        hs = float(raw_hs) if raw_hs is not None else None
        tp = float(raw_tp) if raw_tp is not None else None

    return HourMetrics(
        max_speed=max(speeds) if speeds else None,
        min_speed=min(speeds) if speeds else None,
        max_gust=max(gusts) if gusts else None,
        spread_speed=max(speeds) - min(speeds) if len(speeds) >= 2 else None,
        any_dir=directions[0] if directions else None,
        any_onshore=(any(angle_in_ranges(v, site.onshore_sectors) for v in directions) if directions else None),
        min_vis=min(visibility) if visibility else None,
        codes=codes,
        hs=hs,
        tp=tp,
        n_models=models,
        hs_spread=max(hs_values) - min(hs_values) if len(hs_values) >= 2 else None,
        n_wave_sources=len(hs_values),
    )


def has_wind_range(site: Site, start: int, end: int) -> bool:
    return all(worst_metrics_at_hour(site, index).max_speed is not None for index in range(start, end + 1))
