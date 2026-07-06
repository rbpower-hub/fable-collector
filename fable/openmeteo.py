"""Open-Meteo HTTP client: forecast, marine, astronomy; retries, model fallback.

Pure functions of (lat, lon, window) — an injectable `getter` makes every
call testable offline with recorded fixtures.
"""

from __future__ import annotations

import datetime as dt
import json
import logging
import os
import random
import time
import urllib.request
from collections.abc import Callable
from typing import Any
from urllib.parse import urlencode

from . import USER_AGENT

log = logging.getLogger("fable.openmeteo")

FORECAST_ENDPOINT = "https://api.open-meteo.com/v1/forecast"
MARINE_ENDPOINT = "https://marine-api.open-meteo.com/v1/marine"
ASTRONOMY_ENDPOINT = "https://api.open-meteo.com/v1/astronomy"

HTTP_TIMEOUT_S = int(os.getenv("FABLE_HTTP_TIMEOUT_S", "10"))
HTTP_RETRIES = int(os.getenv("FABLE_HTTP_RETRIES", "1"))

FORECAST_KEYS = [
    "wind_speed_10m", "wind_gusts_10m", "wind_direction_10m",
    "weather_code", "visibility", "surface_pressure", "precipitation",
]
SAFE_HOURLY = ["wind_speed_10m", "wind_gusts_10m", "wind_direction_10m", "weather_code", "visibility"]
MARINE_KEYS = ["wave_height", "wave_period", "swell_wave_height", "swell_wave_period"]
DAILY_KEYS = ["sunrise", "sunset"]
EXTRA_HOURLY = ["relative_humidity_2m", "cloud_cover"]

KEY_SYNONYMS = {
    "wind_speed_10m": ["wind_speed_10m", "windspeed_10m"],
    "wind_gusts_10m": ["wind_gusts_10m", "windgusts_10m"],
    "wind_direction_10m": ["wind_direction_10m", "winddirection_10m"],
    "weather_code": ["weather_code", "weathercode"],
    "visibility": ["visibility"],
    "wave_height": ["wave_height", "significant_wave_height"],
    "wave_period": ["wave_period", "waveperiod"],
    "swell_wave_height": ["swell_wave_height"],
    "swell_wave_period": ["swell_wave_period"],
    "surface_pressure": ["surface_pressure"],
    "precipitation": ["precipitation"],
}

# Models officially accepted by Open-Meteo `models=` parameter.
MODEL_ALIASES = {
    "ecmwf_ifs04": ["ecmwf_ifs04"],
    "icon_seamless": ["icon_seamless"],
    "gfs_seamless": ["gfs_seamless"],
    "default": ["default", None],  # None => omit ?models= (API chooses)
}

# Marine (wave) models — Open-Meteo Marine API `models=` parameter.
# meteofrance_wave = MFWAM 0.08 deg (reference cotiere Mediterranee),
# ncep_gfswave025 = NOAA GFS-Wave 0.25 deg (natif horaire),
# ecmwf_wam025    = ECMWF WAM 0.25 deg.
MARINE_MODEL_ALIASES = {
    "meteofrance_wave": ["meteofrance_wave"],
    "ncep_gfswave025": ["ncep_gfswave025"],
    "ecmwf_wam025": ["ecmwf_wam025"],
    "default": ["default", None],
}


def expand_marine_models(order: list[str]) -> list[str | None]:
    out: list[str | None] = []
    for m in order:
        out.extend(MARINE_MODEL_ALIASES.get(m, [m]))
    seen, dedup = set(), []
    for m in out:
        key = m or "default"
        if key in seen:
            continue
        seen.add(key)
        dedup.append(m)
    return dedup


def http_get_json(url: str, retry: int = HTTP_RETRIES, timeout: int = HTTP_TIMEOUT_S) -> dict[str, Any]:
    last_err: Exception | None = None
    for attempt in range(retry + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                if resp.status != 200:
                    raise RuntimeError(f"HTTP {resp.status}")
                return json.loads(resp.read().decode("utf-8"))
        except Exception as e:  # noqa: BLE001 - network layer catch-all by design
            last_err = e
            if attempt < retry:
                sleep_s = 0.8 + attempt * 1.2 + random.random() * 0.5
                log.warning("GET failed (%s). retry in %.1fs ...", e, sleep_s)
                time.sleep(sleep_s)
    raise RuntimeError(f"GET failed after retries: {last_err}")


Getter = Callable[[str], dict[str, Any]]


def default_getter(retry: int = HTTP_RETRIES, timeout: int = HTTP_TIMEOUT_S) -> Getter:
    return lambda url: http_get_json(url, retry=retry, timeout=timeout)


# ---------------------------------------------------------------------------
# URL builders
# ---------------------------------------------------------------------------
def forecast_url(lat: float, lon: float, model: str | None, tz_name: str,
                 start: dt.date, end: dt.date, hourly_keys: list[str] | None = None,
                 include_daily: bool = True, include_extras: bool = False) -> str:
    hk = list(hourly_keys or FORECAST_KEYS)
    if include_extras:
        hk += [k for k in EXTRA_HOURLY if k not in hk]
    params = {
        "latitude": f"{lat:.5f}",
        "longitude": f"{lon:.5f}",
        "hourly": ",".join(hk),
        "timezone": tz_name,
        "timeformat": "iso8601",
        "wind_speed_unit": "kmh",
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
    }
    if include_daily:
        params["daily"] = ",".join(DAILY_KEYS)
    if model and model != "default":
        params["models"] = model
    return FORECAST_ENDPOINT + "?" + urlencode(params)


def marine_url(lat: float, lon: float, tz_name: str, start: dt.date, end: dt.date,
               model: str | None = None) -> str:
    params = {
        "latitude": f"{lat:.5f}",
        "longitude": f"{lon:.5f}",
        "hourly": ",".join(MARINE_KEYS),
        "timezone": tz_name,
        "timeformat": "iso8601",
        "wave_height_unit": "m",
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
    }
    if model and model != "default":
        params["models"] = model
    return MARINE_ENDPOINT + "?" + urlencode(params)


def daily_only_url(lat: float, lon: float, tz_name: str, start: dt.date, end: dt.date) -> str:
    params = {
        "latitude": f"{lat:.5f}",
        "longitude": f"{lon:.5f}",
        "daily": ",".join(DAILY_KEYS),
        "timezone": tz_name,
        "timeformat": "iso8601",
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
    }
    return FORECAST_ENDPOINT + "?" + urlencode(params)


def astronomy_url(lat: float, lon: float, tz_name: str, start: dt.date, end: dt.date,
                  timeformat: bool = True) -> str:
    params = {
        "latitude": f"{lat:.5f}",
        "longitude": f"{lon:.5f}",
        "daily": "sunrise,sunset,moonrise,moonset,moon_phase",
        "timezone": tz_name,
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
    }
    if timeformat:
        params["timeformat"] = "iso8601"
    return ASTRONOMY_ENDPOINT + "?" + urlencode(params)


# ---------------------------------------------------------------------------
# Payload helpers
# ---------------------------------------------------------------------------
def first_series(h: dict[str, Any], canonical_key: str) -> list:
    for cand in KEY_SYNONYMS.get(canonical_key, [canonical_key]):
        arr = h.get(cand)
        if isinstance(arr, list) and arr:
            return arr
    return []


def normalize_hourly_keys(payload: dict[str, Any]) -> dict[str, Any]:
    h = (payload.get("hourly") or {}).copy()
    normalized = dict(h)
    for canonical, syns in KEY_SYNONYMS.items():
        if isinstance(normalized.get(canonical), list) and normalized.get(canonical):
            continue
        for cand in syns:
            arr = h.get(cand)
            if isinstance(arr, list) and arr:
                normalized[canonical] = arr
                break
    payload["hourly"] = normalized
    return payload


def has_non_null(arr: list) -> bool:
    return isinstance(arr, list) and any(v is not None for v in arr)


def has_wind_arrays(payload: dict[str, Any]) -> bool:
    h = payload.get("hourly") or {}
    return has_non_null(first_series(h, "wind_speed_10m")) and has_non_null(first_series(h, "wind_gusts_10m"))


def payload_has_error(p: Any) -> bool:
    if not isinstance(p, dict) or p.get("error"):
        return True
    h = p.get("hourly")
    if not isinstance(h, dict):
        return True
    t = h.get("time")
    return not (isinstance(t, list) and t)


def api_reason(p: Any) -> str:
    if isinstance(p, dict):
        return str(p.get("reason") or p.get("error_message") or "hourly/time missing")
    return "invalid json"


def expand_models(order: list[str]) -> list[str | None]:
    out: list[str | None] = []
    for m in order:
        out.extend(MODEL_ALIASES.get(m, [m]))
    seen, dedup = set(), []
    for m in out:
        key = m or "default"
        if key in seen:
            continue
        seen.add(key)
        dedup.append(m)
    return dedup


# ---------------------------------------------------------------------------
# Fetchers (getter-injectable)
# ---------------------------------------------------------------------------
def fetch_forecast(lat: float, lon: float, tz_name: str, start: dt.date, end: dt.date,
                   model_order: list[str], site_deadline: float,
                   getter: Getter | None = None, include_extras: bool = False) -> dict[str, Any]:
    """Try model_order, then no-models fallback, then SAFE minimal set.
    Returns payload with `_model_used`; {"_model_used": "unknown", "hourly": {}} on total failure."""
    get = getter or default_getter()

    for model in expand_models(model_order):
        if time.monotonic() > site_deadline:
            log.warning("site budget nearly exhausted — jumping to fallbacks")
            break
        url = forecast_url(lat, lon, model, tz_name, start, end,
                           hourly_keys=FORECAST_KEYS, include_daily=True, include_extras=include_extras)
        try:
            p = get(url)
            if payload_has_error(p):
                log.warning("model %s invalid payload: %s", model or "default", api_reason(p))
                continue
            p = normalize_hourly_keys(p)
            if has_wind_arrays(p):
                p["_model_used"] = model or "default"
                log.info("forecast model used: %s", p["_model_used"])
                return p
            log.warning("model %s has empty wind arrays, trying next", model or "default")
        except Exception as e:  # noqa: BLE001
            log.warning("request failed for model %s: %s", model or "default", e)

    log.warning("all models failed; retry without 'models'")
    try:
        p = get(forecast_url(lat, lon, None, tz_name, start, end, hourly_keys=FORECAST_KEYS, include_daily=True))
        if not payload_has_error(p):
            p = normalize_hourly_keys(p)
            if has_wind_arrays(p):
                p["_model_used"] = "default"
                return p
    except Exception as e:  # noqa: BLE001
        log.warning("default (no models) request failed: %s", e)

    log.warning("fallback SAFE set (no daily)")
    try:
        p = get(forecast_url(lat, lon, None, tz_name, start, end, hourly_keys=SAFE_HOURLY, include_daily=False))
        if not payload_has_error(p):
            p = normalize_hourly_keys(p)
            if has_wind_arrays(p):
                p["_model_used"] = "safe_default"
                return p
    except Exception as e:  # noqa: BLE001
        log.warning("SAFE mode request failed: %s", e)

    return {"_model_used": "unknown", "hourly": {}}


def _marine_has_waves(p: dict[str, Any]) -> bool:
    h = p.get("hourly") or {}
    return has_non_null(first_series(h, "wave_height"))


def fetch_marine(lat: float, lon: float, tz_name: str, start: dt.date, end: dt.date,
                 site_deadline: float, getter: Getter | None = None,
                 model_order: list[str] | None = None) -> dict[str, Any]:
    """Marine fetch with model fallback chain. NEVER raises: on failure or
    exhausted budget returns {"hourly": {}, "_error": reason} so the site
    still publishes wind-only data. Sets `_model_used` on success."""
    get = getter or default_getter()
    order = model_order or ["meteofrance_wave", "ncep_gfswave025", "ecmwf_wam025", "default"]
    last_err = "no marine model succeeded"
    for model in expand_marine_models(order):
        if time.monotonic() > site_deadline:
            log.warning("site budget exceeded — skipping marine (degraded, wind-only)")
            return {"hourly": {}, "_error": "site budget exceeded"}
        try:
            p = get(marine_url(lat, lon, tz_name, start, end, model=model))
        except Exception as e:  # noqa: BLE001
            last_err = str(e)
            log.warning("marine model %s failed: %s", model or "default", e)
            continue
        if payload_has_error(p) or not isinstance(p, dict):
            last_err = api_reason(p)
            log.warning("marine model %s invalid payload: %s", model or "default", last_err)
            continue
        p = normalize_hourly_keys(p)
        if not _marine_has_waves(p):
            last_err = f"{model or 'default'}: empty wave arrays"
            log.warning("marine model %s has empty wave arrays, trying next", model or "default")
            continue
        p["_model_used"] = model or "default"
        log.info("marine model used: %s", p["_model_used"])
        return p
    log.warning("all marine models failed (%s) — degraded, wind-only", last_err)
    return {"hourly": {}, "_error": last_err}


def fetch_parallel_marine(lat: float, lon: float, tz_name: str, start: dt.date, end: dt.date,
                          parallel_models: list[str], primary_used: str | None,
                          site_deadline: float, getter: Getter | None = None) -> tuple:
    """Best-effort extra wave models (for inter-model spread / confidence).
    Returns (models_out, attempts). Never raises."""
    get = getter or default_getter()
    models_out: dict[str, dict[str, Any]] = {}
    attempts: list[dict[str, Any]] = []
    wanted = [m for m in expand_marine_models(parallel_models) if m and m != (primary_used or "")]
    for m in wanted:
        if time.monotonic() > site_deadline - 1.5:
            attempts.append({"model": m, "status": "budget_exceeded"})
            continue
        status, url = "unknown", None
        try:
            url = marine_url(lat, lon, tz_name, start, end, model=m)
            p = get(url)
            if payload_has_error(p) or not isinstance(p, dict):
                attempts.append({"model": m, "status": f"payload_error:{api_reason(p)}", "url": url})
                continue
            p = normalize_hourly_keys(p)
            if not _marine_has_waves(p):
                attempts.append({"model": m, "status": "no_wave_arrays", "url": url})
                continue
            models_out[m] = p
            status = "ok"
        except Exception as e:  # noqa: BLE001
            status = f"exception:{e.__class__.__name__}"
        attempts.append({"model": m, "status": status, "url": url})
    return models_out, attempts
