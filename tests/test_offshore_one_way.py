"""Regression tests for one-way multi-day offshore semantics."""

import datetime as dt
import json
from zoneinfo import ZoneInfo

from fable.config import DEFAULT_RULES
from fable.offshore import detect_directional_crossings
from fable.windows import Thresholds, load_site, run_reader
from tests.helpers import TZ_NAME, make_spot_json

TZ = ZoneInfo(TZ_NAME)
START = dt.datetime(2026, 7, 15, 8, 0, tzinfo=TZ)


def _write(
    tmp_path,
    name,
    slug,
    *,
    lat,
    lon,
    route_origin=None,
    route_kind="standard",
    route_points=None,
    hours=12,
    wind=10.0,
    gusts=14.0,
):
    payload = make_spot_json(
        name,
        slug,
        START,
        hours,
        wind=wind,
        gusts=gusts,
        wave_models={"m1": (0.2, 5.0), "m2": (0.22, 5.2)},
    )
    payload["meta"].update({
        "lat": lat,
        "lon": lon,
        "route_origin": route_origin,
        "route_kind": route_kind,
        "route_points": route_points or [],
        "transit_speed_kts": {"min": 18, "max": 24},
        "windows_enabled": True,
    })
    path = tmp_path / f"{slug}.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_directional_crossings_publish_outbound_and_return(tmp_path):
    relay = load_site(_write(tmp_path, "Kelibia", "kelibia", lat=36.8473, lon=11.0934))
    destination = load_site(
        _write(
            tmp_path,
            "Pantelleria",
            "pantelleria",
            lat=36.8333,
            lon=11.95,
            route_origin="kelibia",
            route_kind="offshore_one_way_beta",
        )
    )
    assert relay is not None and destination is not None
    windows, diagnostics, profile = detect_directional_crossings(
        relay,
        destination,
        Thresholds.from_rules(DEFAULT_RULES),
    )
    assert windows
    assert {window["direction"] for window in windows} == {"outbound", "return"}
    assert all(window["same_day_round_trip_required"] is False for window in windows)
    assert diagnostics["same_day_round_trip_required"] is False
    assert profile["trip_mode"] == "one_way_multi_day"


def test_reader_replaces_round_trip_composite_with_one_way_windows(tmp_path):
    _write(tmp_path, "Gammarth (port)", "gammarth-port", lat=36.9203, lon=10.2846)
    _write(tmp_path, "Kelibia", "kelibia", lat=36.8473, lon=11.0934)
    _write(
        tmp_path,
        "Pantelleria",
        "pantelleria",
        lat=36.8333,
        lon=11.95,
        route_origin="kelibia",
        route_kind="offshore_one_way_beta",
    )

    result = run_reader(
        tmp_path,
        tmp_path,
        "gammarth-port.json",
        min_h=4,
        max_h=6,
        rules=DEFAULT_RULES,
    )
    pantelleria = next(item for item in result["windows"] if item["dest_slug"] == "pantelleria.json")
    assert result["version"] >= 4
    assert result["policy"]["offshore_same_day_round_trip_required"] is False
    assert pantelleria["trip_mode"] == "one_way_multi_day"
    assert pantelleria["same_day_round_trip_required"] is False
    assert {window["direction"] for window in pantelleria["windows"]} == {"outbound", "return"}


def test_kelibia_long_trip_has_independent_outbound_and_return_over_three_days(tmp_path):
    _write(
        tmp_path,
        "Gammarth (port)",
        "gammarth-port",
        lat=36.9203,
        lon=10.2846,
        hours=72,
    )
    _write(
        tmp_path,
        "Kelibia",
        "kelibia",
        lat=36.8473,
        lon=11.0934,
        route_kind="long_trip_one_way",
        hours=72,
    )

    result = run_reader(
        tmp_path,
        tmp_path,
        "gammarth-port.json",
        min_h=4,
        max_h=6,
        rules=DEFAULT_RULES,
    )

    kelibia = next(item for item in result["windows"] if item["dest_slug"] == "kelibia.json")
    assert result["version"] >= 5
    assert result["policy"]["one_way_multi_day_supported"] is True
    assert kelibia["route_kind"] == "long_trip_one_way"
    assert kelibia["trip_mode"] == "one_way_multi_day"
    assert kelibia["same_day_round_trip_required"] is False
    assert {window["direction"] for window in kelibia["windows"]} == {"outbound", "return"}
    assert all(window["route_kind"] == "long_trip_one_way" for window in kelibia["windows"])
    assert len({window["start"][:10] for window in kelibia["windows"]}) >= 3


def test_kelibia_long_trip_checks_known_corridor_sites(tmp_path):
    _write(tmp_path, "Gammarth (port)", "gammarth-port", lat=36.9203, lon=10.2846)
    _write(
        tmp_path,
        "El Haouaria",
        "el-haouaria",
        lat=37.0630,
        lon=11.0080,
        wind=35.0,
        gusts=55.0,
    )
    _write(
        tmp_path,
        "Kelibia",
        "kelibia",
        lat=36.8473,
        lon=11.0934,
        route_kind="long_trip_one_way",
        route_points=[{"name": "El Haouaria — au large", "lat": 37.0630, "lon": 11.0080}],
    )

    result = run_reader(tmp_path, tmp_path, "gammarth-port.json", rules=DEFAULT_RULES)
    kelibia = next(item for item in result["windows"] if item["dest_slug"] == "kelibia.json")

    assert kelibia["windows"] == []
    assert kelibia["diagnostics"]["first_blocker"]["stage"] == "corridor"
    assert kelibia["diagnostics"]["first_blocker"]["location_slug"] == "el-haouaria.json"
