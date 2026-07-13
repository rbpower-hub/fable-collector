"""Regression tests for the FABLE 3.0 route-origin deployment incident."""

import datetime as dt
import json
from zoneinfo import ZoneInfo

from fable.config import DEFAULT_RULES
from fable.windows import Thresholds, adaptive_min_hours, load_site, run_reader
from tests.helpers import TZ_NAME, make_spot_json

TZ = ZoneInfo(TZ_NAME)
START = dt.datetime(2026, 7, 14, 8, 0, tzinfo=TZ)
TH = Thresholds.from_rules(DEFAULT_RULES)


def _write(tmp_path, name, slug, *, route_origin=None, lat=36.9, lon=10.3, hours=12):
    payload = make_spot_json(name, slug, START, hours)
    payload["meta"]["lat"] = lat
    payload["meta"]["lon"] = lon
    payload["meta"]["route_origin"] = route_origin
    path = tmp_path / f"{slug}.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_json_null_route_origin_is_not_slugified_to_none(tmp_path):
    path = _write(tmp_path, "Ghar el Melh", "ghar-el-melh", route_origin=None)
    site = load_site(path)
    assert site is not None
    assert site.route_origin is None


def test_standard_ports_do_not_report_missing_relay(tmp_path):
    _write(tmp_path, "Gammarth (port)", "gammarth-port", route_origin=None)
    _write(tmp_path, "Ghar el Melh", "ghar-el-melh", route_origin=None)

    result = run_reader(
        tmp_path,
        tmp_path,
        "gammarth-port.json",
        min_h=3,
        max_h=6,
        rules=DEFAULT_RULES,
    )
    destination = next(item for item in result["windows"] if item["dest_slug"] == "ghar-el-melh.json")
    assert "Port relais introuvable" not in destination["diagnostics"].get("summary_fr", "")
    assert destination["diagnostics"]["status"] in {"available", "blocked"}
    assert "diagnostics" in destination


def test_composite_dispatch_does_not_use_direct_home_distance(tmp_path):
    home_path = _write(
        tmp_path,
        "Gammarth (port)",
        "gammarth-port",
        route_origin=None,
        lat=36.9203,
        lon=10.2846,
    )
    relay_path = _write(
        tmp_path,
        "Kelibia",
        "kelibia",
        route_origin=None,
        lat=36.8473,
        lon=11.0934,
    )
    destination_path = _write(
        tmp_path,
        "Pantelleria",
        "pantelleria",
        route_origin="kelibia",
        lat=36.8333,
        lon=11.9500,
    )

    home = load_site(home_path)
    relay = load_site(relay_path)
    destination = load_site(destination_path)
    assert home is not None and relay is not None and destination is not None

    # The dispatcher must enter the relay workflow instead of rejecting the
    # destination using the direct Gammarth-to-Pantelleria distance.
    assert adaptive_min_hours(home, destination, 4, TH) == 4
    assert adaptive_min_hours(relay, destination, 4, TH) >= 4

    result = run_reader(
        tmp_path,
        tmp_path,
        "gammarth-port.json",
        min_h=4,
        max_h=6,
        rules=DEFAULT_RULES,
    )
    pantelleria = next(item for item in result["windows"] if item["dest_slug"] == "pantelleria.json")
    summary = pantelleria["diagnostics"].get("summary_fr", "")
    assert "Port relais introuvable" not in summary
    assert "Trajet trop long" not in summary
