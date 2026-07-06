"""Shared fixtures: synthetic Open-Meteo payloads + real recorded spot payload."""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"
TZ_NAME = "Africa/Tunis"


def hourly_axis(start: dt.datetime, hours: int) -> list:
    return [(start + dt.timedelta(hours=i)).strftime("%Y-%m-%dT%H:%M") for i in range(hours)]


def make_forecast_payload(start: dt.datetime, hours: int, *, wind=10.0, gusts=14.0,
                          direction=200.0, code=1, visibility_m=20000.0) -> dict:
    """Synthetic /v1/forecast payload (calm by default, offshore wind for Gammarth)."""
    n = hours
    return {
        "latitude": 36.92, "longitude": 10.28, "timezone": TZ_NAME,
        "hourly_units": {"wind_speed_10m": "km/h", "visibility": "m"},
        "hourly": {
            "time": hourly_axis(start, n),
            "wind_speed_10m": [wind] * n,
            "wind_gusts_10m": [gusts] * n,
            "wind_direction_10m": [direction] * n,
            "weather_code": [code] * n,
            "visibility": [visibility_m] * n,
            "surface_pressure": [1015.0] * n,
            "precipitation": [0.0] * n,
        },
        "daily_units": {"sunrise": "iso8601", "sunset": "iso8601"},
        "daily": {
            "time": sorted({t[:10] for t in hourly_axis(start, n)}),
            "sunrise": ["2026-07-05T05:05"] * len({t[:10] for t in hourly_axis(start, n)}),
            "sunset": ["2026-07-05T19:39"] * len({t[:10] for t in hourly_axis(start, n)}),
        },
    }


def make_marine_payload(start: dt.datetime, hours: int, *, hs=0.2, tp=5.0) -> dict:
    n = hours
    return {
        "latitude": 36.92, "longitude": 10.28, "timezone": TZ_NAME,
        "hourly_units": {"wave_height": "m", "wave_period": "s"},
        "hourly": {
            "time": hourly_axis(start, n),
            "wave_height": [hs] * n,
            "wave_period": [tp] * n,
            "swell_wave_height": [hs * 0.8] * n,
            "swell_wave_period": [tp] * n,
        },
    }


def make_spot_json(name: str, slug: str, start: dt.datetime, hours: int, *,
                   wind=10.0, gusts=14.0, direction=200.0, code=1, vis_m=20000.0,
                   hs=0.2, tp=5.0, n_models=2, onshore_sectors=None,
                   wave_models=None) -> dict:
    """wave_models: {"model_name": (hs, tp)} -> published marine_models block.
    None -> single flat wave source (legacy/one-source payload)."""
    """Synthetic published spot payload (collector output schema)."""
    axis = hourly_axis(start, hours)
    hourly = {
        "time": axis,
        "wind_speed_10m": [wind] * hours,
        "wind_gusts_10m": [gusts] * hours,
        "wind_direction_10m": [direction] * hours,
        "weather_code": [code] * hours,
        "visibility": [vis_m] * hours,
        "wave_height": [hs] * hours,
        "wave_period": [tp] * hours,
        "hs": [hs] * hours,
        "tp": [tp] * hours,
    }
    models = {}
    model_names = ["icon_seamless", "gfs_seamless", "ecmwf_ifs04"][:n_models]
    for i, m in enumerate(model_names):
        models[m] = {"hourly": {
            "time": axis,
            "wind_speed_10m": [wind + i * 1.0] * hours,   # small spread between models
            "wind_gusts_10m": [gusts + i * 1.0] * hours,
            "wind_direction_10m": [direction] * hours,
            "weather_code": [code] * hours,
            "visibility": [vis_m] * hours,
        }}
    marine_models = {}
    if wave_models:
        for mname, (mhs, mtp) in wave_models.items():
            marine_models[mname] = {"hourly": {
                "time": axis,
                "wave_height": [mhs] * hours,
                "wave_period": [mtp] * hours,
            }}
    return {
        "meta": {"name": name, "slug": slug, "lat": 36.9, "lon": 10.3, "tz": TZ_NAME,
                 "generated_at": start.isoformat(),
                 **({"onshore_sectors": onshore_sectors} if onshore_sectors else {})},
        "hourly": hourly,
        "models": models,
        **({"marine_models": marine_models} if marine_models else {}),
        "status": "ok",
    }


@pytest.fixture
def ras_fartass_payload() -> dict:
    return json.loads((FIXTURES / "ras-fartass.json").read_text(encoding="utf-8"))


@pytest.fixture
def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]
