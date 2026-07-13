"""Prudent Family GO, backend diagnostics and adaptive-window regression tests."""

import datetime as dt
import json
from zoneinfo import ZoneInfo

from fable.config import DEFAULT_RULES
from fable.windows import Thresholds, adaptive_min_hours, detect_windows_detailed, load_site
from tests.helpers import TZ_NAME, make_spot_json

TZ = ZoneInfo(TZ_NAME)
START = dt.datetime(2026, 7, 6, 6, 0, tzinfo=TZ)
TH = Thresholds.from_rules(DEFAULT_RULES)


def _site(tmp_path, name, slug, **kwargs):
    payload = make_spot_json(name, slug, kwargs.pop("start", START), kwargs.pop("hours", 8), **kwargs)
    path = tmp_path / f"{slug}.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return load_site(path)


def _set_wind(payload, indexes, wind, gust, direction=250.0):
    for model in payload["models"].values():
        hourly = model["hourly"]
        for index in indexes:
            hourly["wind_speed_10m"][index] = wind
            hourly["wind_gusts_10m"][index] = gust
            hourly["wind_direction_10m"][index] = direction


def test_prudent_window_is_explicitly_labelled(tmp_path):
    home = _site(tmp_path, "Gammarth", "gammarth-port")
    dest = _site(
        tmp_path,
        "Sidi Bou Saïd",
        "sidi-bou-said",
        wind=20.0,
        gusts=24.0,
        direction=250.0,
        hs=0.3,
        tp=5.0,
    )
    windows, diagnostics = detect_windows_detailed(home, dest, 3, 6, TH, allow_prudent=True)
    assert windows
    assert windows[0]["category"] == "family"
    assert windows[0]["family_tier"] == "prudent"
    assert "vent>=20" in windows[0]["cautions"]
    assert diagnostics["prudent_windows"] > 0


def test_prudent_never_overrides_hard_gust_veto(tmp_path):
    home = _site(tmp_path, "Gammarth", "gammarth-port")
    dest = _site(
        tmp_path,
        "Sidi Bou Saïd",
        "sidi-bou-said",
        wind=20.0,
        gusts=30.0,
        direction=250.0,
        hs=0.3,
        tp=5.0,
    )
    windows, diagnostics = detect_windows_detailed(home, dest, 3, 6, TH, allow_prudent=True)
    assert windows == []
    assert "rafales" in diagnostics["first_blocker"]["reasons"][0]


def test_prudent_rejects_onshore_wind(tmp_path):
    home = _site(tmp_path, "Gammarth", "gammarth-port")
    dest = _site(
        tmp_path,
        "Sidi Bou Saïd",
        "sidi-bou-said",
        wind=20.0,
        gusts=24.0,
        direction=90.0,
        hs=0.3,
        tp=5.0,
        onshore_sectors=[[30, 150]],
    )
    windows, diagnostics = detect_windows_detailed(home, dest, 3, 6, TH, allow_prudent=True)
    assert windows == []
    assert diagnostics["status"] == "blocked"


def test_backend_diagnostic_identifies_return_blocker(tmp_path):
    home_payload = make_spot_json("Gammarth", "gammarth-port", START, 3)
    _set_wind(home_payload, [2], 25.0, 31.0)
    home_path = tmp_path / "gammarth-port.json"
    home_path.write_text(json.dumps(home_payload), encoding="utf-8")
    home = load_site(home_path)
    dest = _site(tmp_path, "Ghar el Melh", "ghar-el-melh", hours=3)

    windows, diagnostics = detect_windows_detailed(home, dest, 3, 3, TH, allow_prudent=True)
    assert windows == []
    blocker = diagnostics["first_blocker"]
    assert blocker["stage"] == "return"
    assert blocker["location_slug"] == "gammarth-port.json"
    assert blocker["time"].startswith("2026-07-06T08:00")


def test_adaptive_minimum_allows_short_three_hour_outing(tmp_path):
    home = _site(tmp_path, "Gammarth", "gammarth-port")
    nearby = _site(tmp_path, "Sidi Bou Saïd", "sidi-bou-said")
    assert adaptive_min_hours(home, nearby, 4, TH) == 3


def test_astronomy_marks_pre_sunrise_margin_off_hours(tmp_path):
    payload = make_spot_json(
        "Sidi Bou Saïd",
        "sidi-bou-said",
        dt.datetime(2026, 7, 6, 5, 0, tzinfo=TZ),
        6,
    )
    payload["daily"] = {
        "time": ["2026-07-06"],
        "sunrise": ["2026-07-06T05:00"],
        "sunset": ["2026-07-06T19:30"],
    }
    path = tmp_path / "sidi-bou-said.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    dest = load_site(path)

    home_payload = json.loads(json.dumps(payload))
    home_payload["meta"]["name"] = "Gammarth"
    home_payload["meta"]["slug"] = "gammarth-port"
    home_path = tmp_path / "gammarth-port.json"
    home_path.write_text(json.dumps(home_payload), encoding="utf-8")
    home = load_site(home_path)

    windows, _ = detect_windows_detailed(home, dest, 3, 3, TH, allow_prudent=False)
    assert windows
    assert windows[0]["category"] == "off_hours"


def test_anchor_tolerance_requires_configured_shelter(tmp_path):
    home = _site(tmp_path, "Gammarth", "gammarth-port", hours=4)
    payload = make_spot_json("Sheltered stop", "sheltered-stop", START, 4)
    _set_wind(payload, [1, 2], 21.0, 25.0, direction=250.0)
    path = tmp_path / "sheltered-stop.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    unvalidated = load_site(path)

    windows, _ = detect_windows_detailed(home, unvalidated, 4, 4, TH, allow_prudent=False)
    assert windows == []

    payload["meta"]["shelter_bonus_radius_km"] = 2.0
    path.write_text(json.dumps(payload), encoding="utf-8")
    validated = load_site(path)
    windows, _ = detect_windows_detailed(home, validated, 4, 4, TH, allow_prudent=False)
    assert windows
