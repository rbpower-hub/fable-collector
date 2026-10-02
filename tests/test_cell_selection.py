"""Forecast requests must read sea grid cells, not Open-Meteo's land default.

Context (audit 2026-10-02): without `cell_selection`, Open-Meteo returns a land
cell for coastal points. ICON land cells produced false squall vetoes and
understated the sustained wind on the water.
"""

import datetime as dt
from urllib.parse import parse_qs, urlparse
from zoneinfo import ZoneInfo

import pytest

from fable.collect import Settings, build_site_payload
from fable.openmeteo import (
    DEFAULT_CELL_SELECTION,
    FORECAST_CELL_SELECTION,
    FORECAST_ENDPOINT,
    forecast_url,
    grid_cell,
    marine_url,
    resolve_cell_selection,
)
from tests.helpers import TZ_NAME, make_forecast_payload, make_marine_payload

TZ = ZoneInfo(TZ_NAME)
START = dt.datetime(2026, 7, 6, 0, 0, tzinfo=TZ)
END = START + dt.timedelta(hours=48)
SITE = {"name": "Gammarth (port)", "slug": "gammarth-port", "lat": 36.9203, "lon": 10.2846,
        "shelter_bonus_radius_km": 0.0, "onshore_sectors": [(30, 150)]}


def _query(url: str) -> dict[str, list[str]]:
    return parse_qs(urlparse(url).query)


def _settings() -> Settings:
    s = Settings()
    s.tz_name = TZ_NAME
    s.window_hours = 48
    s.start_iso = START.isoformat()
    s.model_order = ["icon_seamless", "gfs_seamless", "ecmwf_ifs025", "default"]
    s.parallel_models = ["ecmwf_ifs025", "icon_seamless", "gfs_seamless"]
    return s


def test_default_cell_selection_is_sea():
    assert DEFAULT_CELL_SELECTION == "sea"
    assert FORECAST_CELL_SELECTION == "sea"


def test_forecast_url_requests_sea_cells_by_default():
    url = forecast_url(36.9203, 10.2846, "icon_seamless", TZ_NAME, START.date(), END.date())
    assert _query(url)["cell_selection"] == ["sea"]


def test_forecast_url_requests_sea_cells_without_model_parameter():
    # The no-models and SAFE fallbacks must not silently return to land cells.
    url = forecast_url(36.9203, 10.2846, None, TZ_NAME, START.date(), END.date(), include_daily=False)
    query = _query(url)
    assert "models" not in query
    assert query["cell_selection"] == ["sea"]


def test_forecast_url_accepts_explicit_selection_for_diagnostics():
    url = forecast_url(36.9203, 10.2846, "icon_seamless", TZ_NAME, START.date(), END.date(),
                       cell_selection="land")
    assert _query(url)["cell_selection"] == ["land"]


def test_forecast_url_rejects_unknown_selection():
    with pytest.raises(ValueError):
        forecast_url(36.9203, 10.2846, "icon_seamless", TZ_NAME, START.date(), END.date(),
                     cell_selection="ocean")


@pytest.mark.parametrize(
    ("raw", "expected"),
    [(None, "sea"), ("", "sea"), ("  SEA ", "sea"), ("land", "land"), ("nearest", "nearest"), ("ocean", "sea")],
)
def test_environment_override_is_validated(raw, expected):
    assert resolve_cell_selection(raw) == expected


def test_marine_requests_keep_the_marine_api_default():
    # The marine API already defaults to sea cells; its URL is unchanged.
    url = marine_url(36.9203, 10.2846, TZ_NAME, START.date(), END.date(), model="meteofrance_wave")
    assert "cell_selection" not in _query(url)


def test_every_wind_request_of_a_collection_uses_sea_cells():
    seen: list[str] = []
    primary = make_forecast_payload(START, 48)
    primary["hourly"]["uv_index"] = [None] * 48  # forces the optional extras request too

    def getter(url: str):
        seen.append(url)
        if "marine" in url:
            return make_marine_payload(START, 48)
        if "astronomy" in url:
            raise RuntimeError("no astronomy endpoint")
        return primary

    configured = _settings()
    configured.include_extras = True
    build_site_payload(SITE, configured, {}, START, END, getter=getter)

    forecast_calls = [url for url in seen if url.startswith(FORECAST_ENDPOINT) and "wind_speed_10m" in url]
    extras_calls = [url for url in seen if url.startswith(FORECAST_ENDPOINT) and "uv_index" in url
                    and "wind_speed_10m" not in url]
    assert len(forecast_calls) >= 3  # primary + at least two parallel models
    assert extras_calls, "the optional extras request should have been made"
    for url in forecast_calls + extras_calls:
        assert _query(url)["cell_selection"] == ["sea"], url


def test_payload_publishes_selection_and_grid_cells():
    def getter(url: str):
        if "marine" in url:
            return make_marine_payload(START, 48)
        if "astronomy" in url:
            raise RuntimeError("no astronomy endpoint")
        payload = make_forecast_payload(START, 48)
        payload.update({"latitude": 36.9375, "longitude": 10.3125, "elevation": 6.0})
        return payload

    payload = build_site_payload(SITE, _settings(), {}, START, END, getter=getter)
    meta = payload["meta"]

    assert meta["sources"]["ecmwf_open_meteo"]["cell_selection"] == "sea"
    grid = meta["debug"]["forecast_grid"]
    assert grid["cell_selection"] == "sea"
    assert grid["primary"] == {"latitude": 36.9375, "longitude": 10.3125, "elevation": 6.0}
    parallel_ok = [a for a in meta["debug"]["parallel_attempts"] if a["status"] == "ok"]
    assert parallel_ok
    assert all(a["grid"]["latitude"] == 36.9375 for a in parallel_ok)


def test_grid_cell_tolerates_missing_coordinates():
    assert grid_cell({"hourly": {}}) is None
    assert grid_cell(None) is None
    assert grid_cell({"latitude": 36.9, "longitude": 10.3}) == {
        "latitude": 36.9, "longitude": 10.3, "elevation": None,
    }
