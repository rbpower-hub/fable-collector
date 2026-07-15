"""Collection orchestration: fetch per-site forecasts, slice/align, write public/*.json.

Output schema is byte-compatible with v1 consumers (FABLE AI):
keys meta / ecmwf / marine / daily / daily_units / hourly / models /
forecast_primary / status are all preserved.
"""

from __future__ import annotations

import datetime as dt
import json
import logging
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from . import __version__
from .astro import attach_daily_best_effort, needs_daily_backfill
from .config import SitesConfig, load_rules, load_sites, rules_digest, rules_path
from .openmeteo import (
    FORECAST_KEYS,
    MARINE_KEYS,
    Getter,
    api_reason,
    default_getter,
    expand_models,
    fetch_forecast,
    fetch_marine,
    first_series,
    has_wind_arrays,
    normalize_hourly_keys,
    payload_has_error,
)
from .util import csv_to_slug_set, indices_in_window

log = logging.getLogger("fable.collect")


# ---------------------------------------------------------------------------
# Settings (env-driven; names unchanged from v1)
# ---------------------------------------------------------------------------
@dataclass
class Settings:
    tz_name: str = field(default_factory=lambda: os.getenv("FABLE_TZ", "Africa/Tunis"))
    window_hours: int = field(default_factory=lambda: int(os.getenv("FABLE_WINDOW_HOURS", "72")))
    start_iso: str = field(default_factory=lambda: os.getenv("FABLE_START_ISO", "").strip())
    only_sites: set | None = field(default_factory=lambda: csv_to_slug_set(os.getenv("FABLE_ONLY_SITES", "")))
    model_order: list[str] = field(default_factory=lambda: [
        m.strip() for m in os.getenv(
            "FABLE_MODEL_ORDER", "icon_seamless,gfs_seamless,ecmwf_ifs04,default"
        ).split(",") if m.strip()
    ])
    parallel_models: list[str] = field(default_factory=lambda: [
        m.strip() for m in os.getenv(
            "FABLE_PARALLEL_MODELS", "ecmwf_ifs04,icon_seamless,gfs_seamless"
        ).split(",") if m.strip()
    ])
    marine_model_order: list[str] = field(default_factory=lambda: [
        m.strip() for m in os.getenv(
            "FABLE_MARINE_MODEL_ORDER", "meteofrance_wave,ncep_gfswave025,ecmwf_wam025,default"
        ).split(",") if m.strip()
    ])
    marine_parallel_models: list[str] = field(default_factory=lambda: [
        m.strip() for m in os.getenv(
            "FABLE_MARINE_PARALLEL_MODELS", "ncep_gfswave025,ecmwf_wam025"
        ).split(",") if m.strip()
    ])
    http_timeout_s: int = field(default_factory=lambda: int(os.getenv("FABLE_HTTP_TIMEOUT_S", "10")))
    http_retries: int = field(default_factory=lambda: int(os.getenv("FABLE_HTTP_RETRIES", "1")))
    parallel_timeout_s: int = field(default_factory=lambda: int(os.getenv("FABLE_PARALLEL_TIMEOUT_S", "10")))
    parallel_retries: int = field(default_factory=lambda: int(os.getenv("FABLE_PARALLEL_RETRIES", "0")))
    site_budget_s: int = field(default_factory=lambda: int(os.getenv("FABLE_SITE_BUDGET_S", "90")))
    hard_budget_s: int = field(default_factory=lambda: int(os.getenv("FABLE_HARD_BUDGET_S", "240")))
    debug_dump: bool = field(default_factory=lambda: os.getenv("FABLE_DEBUG_DUMP", "0") == "1")
    include_extras: bool = field(default_factory=lambda: os.getenv("FABLE_INCLUDE_EXTRAS", "0") == "1")
    astral_fallback: bool = field(default_factory=lambda: os.getenv("FABLE_ASTRAL_FALLBACK", "1") == "1")

    @property
    def tz(self) -> ZoneInfo:
        return ZoneInfo(self.tz_name)


def compute_window(settings: Settings) -> tuple:
    tz = settings.tz
    now_local = dt.datetime.now(tz).replace(minute=0, second=0, microsecond=0)
    start_local = now_local
    if settings.start_iso:
        try:
            s = dt.datetime.fromisoformat(settings.start_iso)
            start_local = (s.replace(tzinfo=s.tzinfo or tz)).astimezone(tz)
        except Exception as e:  # noqa: BLE001
            log.warning("invalid FABLE_START_ISO (%s) — using now local.", e)
    end_local = start_local + dt.timedelta(hours=settings.window_hours)
    return start_local, end_local


# ---------------------------------------------------------------------------
# Slicing & alignment (unchanged logic from v1)
# ---------------------------------------------------------------------------
def slice_by_indices(payload: dict[str, Any], keys: list[str], keep_idx: list[int]) -> dict[str, Any]:
    h = payload.get("hourly") or {}
    times = h.get("time") or []
    out: dict[str, Any] = {"time": [times[i] for i in keep_idx if i < len(times)]}
    for k in keys:
        series = first_series(h, k)
        if series:
            out[k] = [series[i] for i in keep_idx if i < len(series)]
    return out


def align_series_to_axis(model_slice: dict[str, Any], axis: list[str], keys: list[str]) -> dict[str, list]:
    """Align arbitrary sliced series onto the common hourly axis."""
    te = model_slice.get("time") or []
    idx = {t: i for i, t in enumerate(te)}

    def pick(key: str) -> list:
        arr = model_slice.get(key) or []
        return [arr[j] if (j := idx.get(t)) is not None and j < len(arr) else None for t in axis]

    aligned: dict[str, list] = {"time": list(axis)}
    for k in keys:
        if k in (model_slice or {}):
            aligned[k] = pick(k)
    return aligned


def align_model_to_axis(model_slice: dict[str, Any], axis: list[str]) -> dict[str, list]:
    te = model_slice.get("time") or []
    idx = {t: i for i, t in enumerate(te)}

    def pick(key: str) -> list:
        arr = model_slice.get(key) or []
        return [arr[j] if (j := idx.get(t)) is not None and j < len(arr) else None for t in axis]

    aligned: dict[str, list] = {"time": list(axis)}
    for k in ["wind_speed_10m", "wind_gusts_10m", "wind_direction_10m", "weather_code", "visibility"]:
        if k in (model_slice or {}):
            aligned[k] = pick(k)
    return aligned


def flatten_hourly_aligned(fx_slice: dict[str, Any], marine_slice: dict[str, Any]) -> dict[str, list]:
    """Merge forecast+marine on the intersection of their hourly axes
    (ordered union when the intersection is empty)."""
    te = fx_slice.get("time") or []
    tm = marine_slice.get("time") or []
    if te and tm:
        set_tm = set(tm)
        time_axis = [t for t in te if t in set_tm]
        if not time_axis:
            time_axis = sorted(set(te) | set(tm))
    else:
        time_axis = te or tm

    idx_e = {t: i for i, t in enumerate(te)}
    idx_m = {t: i for i, t in enumerate(tm)}

    def pick(src: dict[str, Any], key: str, idx_map: dict[str, int]) -> list[float | None]:
        arr = src.get(key) or []
        return [arr[i] if (i := idx_map.get(t)) is not None and i < len(arr) else None for t in time_axis]

    flat: dict[str, list] = {"time": time_axis}
    for k in ["wind_speed_10m", "wind_gusts_10m", "wind_direction_10m", "weather_code",
              "visibility", "surface_pressure", "precipitation"]:
        if k in fx_slice:
            flat[k] = pick(fx_slice, k, idx_e)
    for k in ["wave_height", "wave_period"]:
        if k in marine_slice:
            flat[k] = pick(marine_slice, k, idx_m)
    if "wave_height" in flat:
        flat["hs"] = flat["wave_height"]
    if "wave_period" in flat:
        flat["tp"] = flat["wave_period"]
    return flat


def non_null_count(d: dict[str, Any], keys: list[str]) -> dict[str, int]:
    return {k: sum(1 for x in (d.get(k) or []) if x is not None) for k in keys}


def fetch_parallel_models(lat: float, lon: float, tz_name: str, start: dt.date, end: dt.date,
                          axis: list[str], start_local: dt.datetime, end_local: dt.datetime,
                          tz: ZoneInfo, primary_used: str | None, site_deadline: float,
                          parallel_models: list[str], getter: Getter) -> tuple:
    models_out: dict[str, dict] = {}
    attempts: list[dict] = []
    wanted = [m for m in expand_models(parallel_models) if m and m != (primary_used or "")]
    for m in wanted:
        if time.monotonic() > site_deadline - 1.5:
            attempts.append({"model": m, "status": "budget_exceeded"})
            continue
        status, url = "unknown", None
        try:
            from .openmeteo import forecast_url  # local import to ease test monkeypatching
            url = forecast_url(lat, lon, m, tz_name, start, end, hourly_keys=FORECAST_KEYS, include_daily=False)
            p = getter(url)
            if payload_has_error(p):
                attempts.append({"model": m, "status": f"payload_error:{api_reason(p)}", "url": url})
                continue
            p = normalize_hourly_keys(p)
            if not has_wind_arrays(p):
                attempts.append({"model": m, "status": "no_wind_arrays", "url": url})
                continue
            keep_idx = indices_in_window((p.get("hourly") or {}).get("time") or [], start_local, end_local, tz)
            mslice = slice_by_indices(p, FORECAST_KEYS, keep_idx)
            aligned = align_model_to_axis(mslice, axis)
            if not any(v is not None for v in (aligned.get("wind_speed_10m") or [])):
                attempts.append({"model": m, "status": "no_overlap_with_axis", "url": url})
                continue
            models_out[m] = {"hourly": aligned}
            status = "ok"
        except Exception as e:  # noqa: BLE001
            status = f"exception:{e.__class__.__name__}"
        attempts.append({"model": m, "status": status, "url": url})
    return models_out, attempts


# ---------------------------------------------------------------------------
# Per-site payload
# ---------------------------------------------------------------------------
def build_site_payload(site: dict[str, Any], settings: Settings, rules: dict[str, Any],
                       start_local: dt.datetime, end_local: dt.datetime,
                       getter: Getter | None = None) -> dict[str, Any]:
    get = getter or default_getter(settings.http_retries, settings.http_timeout_s)
    tz, tz_name = settings.tz, settings.tz_name
    start_date, end_date = start_local.date(), end_local.date()
    lat, lon = site["lat"], site["lon"]
    site_deadline = time.monotonic() + settings.site_budget_s

    from .util import dget as _dget
    disable_astro_http = bool(_dget(rules, "http.disable_astronomy_http", True)) or \
        (os.getenv("FABLE_DISABLE_ASTRONOMY_HTTP", "1") == "1")

    wx = fetch_forecast(lat, lon, tz_name, start_date, end_date, settings.model_order,
                        site_deadline, getter=get, include_extras=settings.include_extras)
    if has_wind_arrays(wx) and needs_daily_backfill(wx):
        attach_daily_best_effort(wx, lat, lon, tz, tz_name, start_date, end_date, get,
                                 disable_astronomy_http=disable_astro_http,
                                 use_astral=settings.astral_fallback)
    sea = fetch_marine(lat, lon, tz_name, start_date, end_date, site_deadline, getter=get,
                       model_order=settings.marine_model_order)

    wx_times = (wx.get("hourly") or {}).get("time") or []
    sea_times = (sea.get("hourly") or {}).get("time") or []
    keep_wx = indices_in_window(wx_times, start_local, end_local, tz)
    keep_sea = indices_in_window(sea_times, start_local, end_local, tz)

    fx_slice = slice_by_indices(wx, FORECAST_KEYS, keep_wx)
    marine_slice = slice_by_indices(sea, MARINE_KEYS, keep_sea)
    hourly_flat = flatten_hourly_aligned(fx_slice, marine_slice)

    primary_used = wx.get("_model_used", "unknown")
    axis = hourly_flat.get("time") or []
    models_parallel: dict[str, dict] = {}
    parallel_attempts: list[dict] = []
    if axis:
        try:
            models_parallel, parallel_attempts = fetch_parallel_models(
                lat, lon, tz_name, start_date, end_date, axis, start_local, end_local, tz,
                primary_used, site_deadline, settings.parallel_models, get)
        except Exception as e:  # noqa: BLE001
            log.debug("parallel models fetch failed: %s", e)
        if primary_used and primary_used not in models_parallel:
            primary_aligned = align_model_to_axis(fx_slice, axis)
            if any(v is not None for v in (primary_aligned.get("wind_speed_10m") or [])):
                models_parallel[primary_used] = {"hourly": primary_aligned}
                parallel_attempts.append({"model": primary_used, "status": "published_primary_copy"})

    # ---- parallel MARINE models (inter-model wave spread -> confidence) ----
    marine_primary_used = sea.get("_model_used")
    marine_models_out: dict[str, dict] = {}
    marine_attempts: list[dict] = []
    if axis and marine_primary_used:
        try:
            from .openmeteo import fetch_parallel_marine
            raw_marine, marine_attempts = fetch_parallel_marine(
                lat, lon, tz_name, start_date, end_date,
                settings.marine_parallel_models, marine_primary_used, site_deadline, getter=get)
            for mname, mp in raw_marine.items():
                keep = indices_in_window((mp.get("hourly") or {}).get("time") or [],
                                         start_local, end_local, tz)
                msl = slice_by_indices(mp, MARINE_KEYS, keep)
                aligned = align_series_to_axis(msl, axis, MARINE_KEYS)
                if any(v is not None for v in (aligned.get("wave_height") or [])):
                    marine_models_out[mname] = {"hourly": aligned}
                else:
                    marine_attempts.append({"model": mname, "status": "no_overlap_with_axis"})
        except Exception as e:  # noqa: BLE001
            log.debug("parallel marine fetch failed: %s", e)
        # republish primary marine under marine_models.* for schema homogeneity
        if marine_primary_used not in marine_models_out:
            primary_aligned = align_series_to_axis(marine_slice, axis, MARINE_KEYS)
            if any(v is not None for v in (primary_aligned.get("wave_height") or [])):
                marine_models_out[marine_primary_used] = {"hourly": primary_aligned}
                marine_attempts.append({"model": marine_primary_used, "status": "published_primary_copy"})

    e_units = wx.get("hourly_units", {}) or {}
    m_units = sea.get("hourly_units", {}) or {}
    d_units = wx.get("daily_units", {}) or {}

    payload: dict[str, Any] = {
        "meta": {
            "name": site["name"], "slug": site["slug"], "lat": lat, "lon": lon, "tz": tz_name,
            "generated_at": dt.datetime.now(tz).isoformat(),
            "collector_version": __version__,
            "transit_speed_kts": site.get("transit_speed_kts"),
            "route_origin": site.get("route_origin"),
            "route_points": site.get("route_points") or [],
            "windows_enabled": bool(site.get("windows_enabled", True)),
            "beta": bool(site.get("beta", False)),
            "route_kind": site.get("route_kind", "standard"),
            "route_note": site.get("route_note"),
            "country": site.get("country"),
            "window": {
                "start_local": start_local.isoformat(),
                "end_local": end_local.isoformat(),
                "hours": int((end_local - start_local).total_seconds() // 3600),
            },
            "rules": {
                "digest": rules_digest(rules),
                "path": str(rules_path()),
                **{k: rules.get(k, {}) for k in (
                    "overrides", "wind", "sea", "tp_matrix", "hysteresis", "shelter",
                    "resolution_policy", "confidence", "corridor", "family_hours_local")},
            },
            "sources": {
                "ecmwf_open_meteo": {
                    "endpoint": "https://api.open-meteo.com/v1/forecast",
                    "model_order": settings.model_order,
                    "model_used": primary_used,
                    "units": e_units,
                    "parallel_models": list(models_parallel.keys()),
                },
                "marine_open_meteo": {
                    "endpoint": "https://marine-api.open-meteo.com/v1/marine",
                    "model_order": settings.marine_model_order,
                    "model_used": marine_primary_used,
                    "units": m_units,
                    "parallel_models": list(marine_models_out.keys()),
                },
                "astro_daily_open_meteo": {
                    "endpoint": "https://api.open-meteo.com/v1/astronomy",
                    "units": d_units,
                },
            },
            "shelter_bonus_radius_km": site.get("shelter_bonus_radius_km", 0.0),
            "onshore_sectors": [list(t) for t in (site.get("onshore_sectors") or [])],
            "debug": {
                "hourly_keys_present_forecast": sorted((wx.get("hourly") or {}).keys()),
                "hourly_keys_present_marine": sorted((sea.get("hourly") or {}).keys()),
                "ecmwf_non_null_counts": non_null_count(fx_slice, FORECAST_KEYS),
                "marine_non_null_counts": non_null_count(marine_slice, MARINE_KEYS),
                "forecast_primary_model": primary_used,
                "forecast_primary_key": "ecmwf",  # historical alias kept for compat
                "marine_error": sea.get("_error"),
                "kept_indices": {
                    "forecast": keep_wx[:6] + (["..."] if len(keep_wx) > 6 else []),
                    "marine": keep_sea[:6] + (["..."] if len(keep_sea) > 6 else []),
                },
                "budgets": {"site_s": settings.site_budget_s, "global_s": settings.hard_budget_s},
                "parallel_models_count": len(models_parallel),
                "parallel_attempts": parallel_attempts,
                "marine_models_count": len(marine_models_out),
                "marine_parallel_attempts": marine_attempts,
            },
        },
        # "ecmwf" key: historical name — contains the PRIMARY model slice
        # (see meta.sources.ecmwf_open_meteo.model_used for the actual model).
        "ecmwf": fx_slice,
        "marine": marine_slice,
        "daily": wx.get("daily", {}) or {},
        "daily_units": d_units,
        "hourly": hourly_flat,
        "models": models_parallel,
        "marine_models": marine_models_out,
        "forecast_primary": {"model": primary_used, "hourly": fx_slice},
        "status": "ok" if axis else "degraded",
    }
    return payload


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------
def write_json_atomic(path: Path, obj: Any, compact: bool = True) -> None:
    tmp = path.parent / f".{path.name}.tmp"
    if compact:
        tmp.write_text(json.dumps(obj, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    else:
        tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def run_collect(root: Path, public: Path, settings: Settings | None = None,
                getter: Getter | None = None) -> list[dict[str, Any]]:
    settings = settings or Settings()
    rules = load_rules(root / os.getenv("FABLE_RULES_PATH", "rules.yaml")
                       if not Path(os.getenv("FABLE_RULES_PATH", "rules.yaml")).is_absolute()
                       else Path(os.getenv("FABLE_RULES_PATH")))
    cfg: SitesConfig = load_sites(root / "sites.yaml", only=settings.only_sites)

    # rules.yaml http.* provides model orders unless overridden by env
    from .util import dget as _dget

    def _csv(v: str) -> list[str]:
        return [m.strip() for m in v.split(",") if m.strip()]

    if not os.getenv("FABLE_MODEL_ORDER") and _dget(rules, "http.model_order"):
        settings.model_order = _csv(str(_dget(rules, "http.model_order")))
    if not os.getenv("FABLE_MARINE_MODEL_ORDER") and _dget(rules, "http.marine_model_order"):
        settings.marine_model_order = _csv(str(_dget(rules, "http.marine_model_order")))
    if not os.getenv("FABLE_MARINE_PARALLEL_MODELS") and _dget(rules, "http.marine_parallel_models"):
        settings.marine_parallel_models = _csv(str(_dget(rules, "http.marine_parallel_models")))

    start_local, end_local = compute_window(settings)

    log.info("window %s → %s (%dh) tz=%s | sites=%d | models=%s",
             start_local.isoformat(), end_local.isoformat(), settings.window_hours,
             settings.tz_name, len(cfg.sites), "/".join(settings.model_order))

    public.mkdir(parents=True, exist_ok=True)
    results = []
    global_deadline = time.monotonic() + settings.hard_budget_s

    for site in cfg.sites:
        if time.monotonic() > global_deadline:
            log.error("global budget exceeded — stopping early")
            break
        log.info("▶ collecting %s (%.5f, %.5f)", site["name"], site["lat"], site["lon"])
        try:
            payload = build_site_payload(site, settings, rules, start_local, end_local, getter=getter)
        except Exception as e:  # noqa: BLE001
            log.error("collection failed for %s: %s", site["name"], e)
            continue
        if settings.debug_dump:
            write_json_atomic(public / f"_debug-{site['slug']}.json", payload, compact=False)
        write_json_atomic(public / f"{site['slug']}.json", payload)
        flat_time = (payload.get("hourly") or {}).get("time") or []
        results.append({
            "slug": site["slug"], "name": site["name"], "points": len(flat_time),
            "first_time": flat_time[0] if flat_time else None,
            "last_time": flat_time[-1] if flat_time else None,
            "path": f"{site['slug']}.json",
        })

    ok = [r for r in results if r["points"] > 0]
    log.info("done: %d/%d spots written with hourly data in window", len(ok), len(cfg.sites))

    index_payload = {
        "generated_at": dt.datetime.now(settings.tz).isoformat(),
        "tz": settings.tz_name,
        "collector_version": __version__,
        "home": cfg.home,
        "window": {
            "start_local": start_local.isoformat(),
            "end_local": end_local.isoformat(),
            "hours": int((end_local - start_local).total_seconds() // 3600),
        },
        "spots": ok,
    }
    write_json_atomic(public / "index.json", index_payload)
    return results
