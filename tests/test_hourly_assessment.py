"""Hourly chart contract: engine-owned states, causes and paired model data."""

import datetime as dt
import json
from zoneinfo import ZoneInfo

from fable.config import load_rules
from fable.hourly_assessment import assess_hour
from fable.windows import Thresholds, load_site, run_reader
from tests.helpers import TZ_NAME, make_spot_json

TZ = ZoneInfo(TZ_NAME)
DAY = dt.datetime(2026, 7, 6, 8, 0, tzinfo=TZ)
ACTIVE_RULES = load_rules()
TH = Thresholds.from_rules(ACTIVE_RULES)


def _site(tmp_path, *, wind=10.0, gusts=14.0, hs=0.2, tp=5.0, direction=200.0):
    payload = make_spot_json(
        "Gammarth",
        "gammarth-port",
        DAY,
        6,
        wind=wind,
        gusts=gusts,
        hs=hs,
        tp=tp,
        direction=direction,
        wave_models={"meteofrance_wave": (hs, tp)},
    )
    path = tmp_path / "gammarth-port.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return load_site(path), payload, path


def test_hourly_record_is_not_a_window_go(tmp_path):
    site, _, _ = _site(tmp_path)
    record = assess_hour(site, 0, TH)
    assert record["condition_state"] == "family"
    assert record["is_window_decision"] is False
    assert record["hard_veto"] is False
    assert record["confidence"] in {"High", "Medium", "Low"}


def test_display_wind_and_gust_are_from_same_model(tmp_path):
    site, payload, path = _site(tmp_path)
    first = payload["models"]["icon_seamless"]["hourly"]
    second = payload["models"]["gfs_seamless"]["hourly"]
    first["wind_speed_10m"][0], first["wind_gusts_10m"][0] = 24.0, 25.0
    second["wind_speed_10m"][0], second["wind_gusts_10m"][0] = 8.0, 31.0
    path.write_text(json.dumps(payload), encoding="utf-8")
    site = load_site(path)

    wind = assess_hour(site, 0, TH)["metrics"]["wind"]
    assert wind["max_speed_kmh"] == 24.0
    assert wind["max_gust_kmh"] == 31.0
    assert wind["display_source"] == "gfs_seamless"
    assert wind["display_speed_kmh"] == 8.0
    assert wind["display_gust_kmh"] == 31.0
    assert wind["display_gust_delta_kmh"] == 23.0


def test_no_go_exposes_gust_and_short_period_causes(tmp_path):
    site, _, _ = _site(tmp_path, gusts=33.0, hs=0.12, tp=2.35)
    record = assess_hour(site, 0, TH)
    codes = {reason["code"] for reason in record["reasons"]}
    assert record["condition_state"] == "no_go"
    assert record["hard_veto"] is True
    assert "rafales>=30" in codes
    assert "Tp<3.0@Hs<0.4" in codes
    period = next(reason for reason in record["reasons"] if reason["code"].startswith("Tp<"))
    assert period["source"] == "meteofrance_wave"
    assert period["wave_pair"] == {"hs": 0.12, "tp": 2.35}


def test_onshore_direction_alone_is_not_a_blocker(tmp_path):
    site, _, _ = _site(tmp_path, wind=15.5, gusts=20.0, direction=60.0)
    record = assess_hour(site, 0, TH)
    assert record["condition_state"] == "family"
    assert not any(reason["code"].startswith("onshore") for reason in record["reasons"])


def test_reader_publishes_hourly_contract_for_each_destination(tmp_path):
    for name, slug in (("Gammarth", "gammarth-port"), ("Sidi Bou Saïd", "sidi-bou-said")):
        payload = make_spot_json(name, slug, DAY, 6, wave_models={"meteofrance_wave": (0.2, 5.0)})
        (tmp_path / f"{slug}.json").write_text(json.dumps(payload), encoding="utf-8")

    output = run_reader(tmp_path, tmp_path, "gammarth-port.json", 3, 6, rules=ACTIVE_RULES)
    assert output["version"] == 7
    assert output["policy"]["hourly_assessment_is_window_decision"] is False
    assert output["policy"]["hourly_assessment_files"] is True
    assert all(entry["hourly_assessment"]["count"] == 6 for entry in output["windows"])
    published = json.loads((tmp_path / "windows.json").read_text(encoding="utf-8"))
    reference = published["windows"][0]["hourly_assessment"]
    assert reference["scope"] == "single_hour_conditions"
    hourly = json.loads((tmp_path / reference["path"]).read_text(encoding="utf-8"))
    assert hourly["is_window_decision"] is False
    assert len(hourly["hours"]) == reference["count"]
    assert hourly["hours"][0]["scope"] == "single_hour_conditions"
