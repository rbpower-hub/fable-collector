"""Offline collector tests: fake getter injects synthetic API payloads."""

import datetime as dt
import json
from zoneinfo import ZoneInfo

from fable.collect import (
    Settings,
    align_model_to_axis,
    build_site_payload,
    flatten_hourly_aligned,
    run_collect,
    slice_by_indices,
)
from fable.openmeteo import normalize_hourly_keys
from tests.conftest import TZ_NAME, make_forecast_payload, make_marine_payload

TZ = ZoneInfo(TZ_NAME)
START = dt.datetime(2026, 7, 6, 0, 0, tzinfo=TZ)
SITE = {"name": "Gammarth (port)", "slug": "gammarth-port", "lat": 36.9203, "lon": 10.2846,
        "shelter_bonus_radius_km": 0.0, "onshore_sectors": [(30, 150)]}


def make_getter(fx=None, marine=None, fail_marine=False, fail_models=False):
    def getter(url: str):
        if "marine" in url:
            if fail_marine:
                raise RuntimeError("marine api down")
            return marine or make_marine_payload(START, 48)
        if "astronomy" in url:
            raise RuntimeError("no astronomy endpoint")
        if fail_models and "models=" in url:
            raise RuntimeError("model api down")
        return fx or make_forecast_payload(START, 48)
    return getter


def settings():
    s = Settings()
    s.tz_name = TZ_NAME
    s.window_hours = 48
    s.start_iso = START.isoformat()
    s.model_order = ["icon_seamless", "gfs_seamless", "ecmwf_ifs04", "default"]
    s.parallel_models = ["ecmwf_ifs04", "icon_seamless", "gfs_seamless"]
    return s


def test_normalize_hourly_synonyms():
    p = normalize_hourly_keys({"hourly": {"time": ["t"], "windspeed_10m": [5], "weathercode": [3]}})
    assert p["hourly"]["wind_speed_10m"] == [5]
    assert p["hourly"]["weather_code"] == [3]


def test_slice_and_align():
    fx = {"hourly": {"time": ["a", "b", "c"], "wind_speed_10m": [1, 2, 3]}}
    s = slice_by_indices(fx, ["wind_speed_10m"], [1, 2])
    assert s == {"time": ["b", "c"], "wind_speed_10m": [2, 3]}
    aligned = align_model_to_axis({"time": ["b"], "wind_speed_10m": [9]}, ["a", "b", "c"])
    assert aligned["wind_speed_10m"] == [None, 9, None]


def test_flatten_intersection_and_union():
    fx = {"time": ["a", "b"], "wind_speed_10m": [1, 2]}
    ma = {"time": ["b", "c"], "wave_height": [0.3, 0.4]}
    flat = flatten_hourly_aligned(fx, ma)
    assert flat["time"] == ["b"]                      # intersection, forecast order
    assert flat["hs"] == [0.3]
    flat2 = flatten_hourly_aligned({"time": ["a"], "wind_speed_10m": [1]},
                                   {"time": ["z"], "wave_height": [0.1]})
    assert flat2["time"] == ["a", "z"]                # empty intersection -> ordered union


def test_build_site_payload_nominal():
    p = build_site_payload(SITE, settings(), {}, START, START + dt.timedelta(hours=48),
                           getter=make_getter())
    assert p["status"] == "ok"
    assert len(p["hourly"]["time"]) == 48
    assert p["meta"]["sources"]["ecmwf_open_meteo"]["model_used"] == "icon_seamless"
    assert p["meta"]["debug"]["marine_error"] is None
    assert "icon_seamless" in p["models"]              # primary republished under models.*
    assert p["hourly"]["hs"][0] == 0.2
    assert p["meta"]["onshore_sectors"] == [[30, 150]]


def test_build_site_payload_marine_down_degrades_not_fails():
    """v1 lost the whole site when marine failed; v2 must publish wind-only."""
    p = build_site_payload(SITE, settings(), {}, START, START + dt.timedelta(hours=48),
                           getter=make_getter(fail_marine=True))
    assert p["status"] == "ok"
    assert len(p["hourly"]["time"]) == 48              # wind axis survives
    assert "hs" not in p["hourly"]                     # no fabricated wave data
    assert p["meta"]["debug"]["marine_error"] is not None
    assert p["marine"]["time"] == []


def test_run_collect_writes_files(tmp_path, repo_root, monkeypatch):
    monkeypatch.chdir(repo_root)
    monkeypatch.setenv("FABLE_START_ISO", START.isoformat())
    monkeypatch.setenv("FABLE_WINDOW_HOURS", "48")
    public = tmp_path / "public"
    results = run_collect(repo_root, public, getter=make_getter())
    assert len(results) == 5
    assert all(r["points"] == 48 for r in results)
    idx = json.loads((public / "index.json").read_text(encoding="utf-8"))
    assert idx["home"] == "gammarth-port"
    assert {s["slug"] for s in idx["spots"]} == {
        "gammarth-port", "sidi-bou-said", "ghar-el-melh", "ras-fartass", "el-haouaria"}
    spot = json.loads((public / "gammarth-port.json").read_text(encoding="utf-8"))
    for key in ("meta", "ecmwf", "marine", "daily", "daily_units", "hourly",
                "models", "forecast_primary", "status"):
        assert key in spot, f"v1 consumer key missing: {key}"


# ---------------------------------------------------------------------------
# v2.1 — multi-model marine
# ---------------------------------------------------------------------------
def make_getter_marine_models(fail_primary=False):
    def getter(url: str):
        if "marine" in url:
            if "models=meteofrance_wave" in url:
                if fail_primary:
                    raise RuntimeError("mfwam down")
                return make_marine_payload(START, 48, hs=0.2, tp=5.0)
            if "models=ncep_gfswave025" in url:
                return make_marine_payload(START, 48, hs=0.25, tp=5.2)
            if "models=ecmwf_wam025" in url:
                return make_marine_payload(START, 48, hs=0.22, tp=5.1)
            return make_marine_payload(START, 48)
        if "astronomy" in url:
            raise RuntimeError("no astronomy endpoint")
        return make_forecast_payload(START, 48)
    return getter


def test_marine_multi_model_published():
    p = build_site_payload(SITE, settings(), {}, START, START + dt.timedelta(hours=48),
                           getter=make_getter_marine_models())
    src_marine = p["meta"]["sources"]["marine_open_meteo"]
    assert src_marine["model_used"] == "meteofrance_wave"
    assert set(p["marine_models"].keys()) == {"meteofrance_wave", "ncep_gfswave025", "ecmwf_wam025"}
    mm = p["marine_models"]["ncep_gfswave025"]["hourly"]
    assert mm["time"] == p["hourly"]["time"]           # aligned on common axis
    assert mm["wave_height"][0] == 0.25
    assert p["hourly"]["hs"][0] == 0.2                 # primary keeps hourly.hs (compat)


def test_marine_primary_fallback_on_failure():
    p = build_site_payload(SITE, settings(), {}, START, START + dt.timedelta(hours=48),
                           getter=make_getter_marine_models(fail_primary=True))
    assert p["meta"]["sources"]["marine_open_meteo"]["model_used"] == "ncep_gfswave025"
    assert p["hourly"]["hs"][0] == 0.25                # fallback series became primary
    assert "meteofrance_wave" not in p["marine_models"]
