"""Production calibration after the first eight observed family outings."""

import datetime as dt
import json
from pathlib import Path
from zoneinfo import ZoneInfo

from fable.config import load_rules
from fable.window_detect import detect_windows_detailed
from fable.window_models import Thresholds, load_site
from tests.helpers import TZ_NAME, make_spot_json

TZ = ZoneInfo(TZ_NAME)
START = dt.datetime(2026, 7, 18, 8, 0, tzinfo=TZ)
RULES = load_rules(Path("rules.yaml"))
TH = Thresholds.from_rules(RULES)


def _site(tmp_path, name, slug, **kwargs):
    payload = make_spot_json(name, slug, START, 6, **kwargs)
    path = tmp_path / f"{slug}.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return load_site(path)


def _detect(tmp_path, *, wind, gusts, hs, tp, direction=250.0):
    home = _site(
        tmp_path,
        "Gammarth",
        "gammarth-port",
        wind=10.0,
        gusts=15.0,
        direction=250.0,
        hs=0.2,
        tp=5.0,
    )
    dest = _site(
        tmp_path,
        "Sidi Bou Saïd",
        "sidi-bou-said",
        wind=wind,
        gusts=gusts,
        direction=direction,
        hs=hs,
        tp=tp,
    )
    return detect_windows_detailed(home, dest, 3, 6, TH, allow_prudent=True)


def test_production_calibration_values_are_explicit():
    assert TH.wind_family_max == 22
    assert TH.prudent_wind_max == 23
    assert TH.tp_min_at_lt04 == 3.0
    assert TH.tp_min_at_04_05 == 4.2
    assert TH.prudent_tp_min == 3.3

    # Hard safety vetoes are deliberately unchanged.
    assert TH.wind_no_go_min == 25
    assert TH.gust_no_go_min == 30
    assert TH.squall_delta == 17
    assert TH.vis_min_km == 5
    assert TH.hs_no_go_min == 0.8
    assert TH.short_steep_2_hs == 0.6
    assert TH.short_steep_2_tp == 5.0


def test_worst_model_below_22_is_standard_family_go(tmp_path):
    # Synthetic helper publishes a second model at input +1 km/h.
    windows, _ = _detect(tmp_path, wind=20.5, gusts=24.0, hs=0.3, tp=4.5)
    assert windows
    assert windows[0]["family_tier"] == "family"


def test_worst_model_22_to_23_is_only_prudent_go(tmp_path):
    # Worst sustained model = 22.5 km/h; worst gust = 27 km/h.
    windows, diagnostics = _detect(tmp_path, wind=21.5, gusts=26.0, hs=0.35, tp=3.4)
    assert windows
    assert windows[0]["family_tier"] == "prudent"
    assert diagnostics["prudent_windows"] > 0


def test_worst_model_above_23_is_not_promoted_to_family_go(tmp_path):
    windows, diagnostics = _detect(tmp_path, wind=22.5, gusts=26.0, hs=0.35, tp=3.4)
    assert windows == []
    assert diagnostics["status"] == "blocked"


def test_slight_wave_period_relaxation_is_bounded(tmp_path):
    low_sea, _ = _detect(tmp_path, wind=15.0, gusts=20.0, hs=0.35, tp=3.0)
    medium_sea, _ = _detect(tmp_path, wind=15.0, gusts=20.0, hs=0.45, tp=4.2)
    too_short, _ = _detect(tmp_path, wind=15.0, gusts=20.0, hs=0.45, tp=4.1)

    assert low_sea and low_sea[0]["family_tier"] == "family"
    assert medium_sea and medium_sea[0]["family_tier"] == "family"
    assert too_short == []


def test_hard_gust_and_short_steep_vetoes_still_win(tmp_path):
    # Second model is input +1, so 29 produces a worst-case hard veto at 30.
    gust_veto, _ = _detect(tmp_path, wind=15.0, gusts=29.0, hs=0.3, tp=5.0)
    steep_veto, _ = _detect(tmp_path, wind=15.0, gusts=20.0, hs=0.6, tp=5.0)

    assert gust_veto == []
    assert steep_veto == []
