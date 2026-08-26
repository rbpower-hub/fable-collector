"""Safety regressions for the review-only WATCH decision state."""

import datetime as dt
import json
from copy import deepcopy
from zoneinfo import ZoneInfo

from fable.config import DEFAULT_RULES
from fable.windows import Thresholds, detect_watch_windows, detect_windows_detailed, load_site, run_reader
from tests.helpers import TZ_NAME, make_spot_json

TZ = ZoneInfo(TZ_NAME)
START = dt.datetime(2026, 8, 26, 8, 0, tzinfo=TZ)


def _site(tmp_path, name, slug, **kwargs):
    payload = make_spot_json(name, slug, START, 8, **kwargs)
    path = tmp_path / f"{slug}.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return load_site(path)


def test_small_single_source_tp_miss_is_watch_but_never_family_go(tmp_path):
    th = Thresholds.from_rules(DEFAULT_RULES)
    home = _site(tmp_path, "Gammarth", "gammarth-port", tp=5.0)
    destination = _site(tmp_path, "Sidi Bou Saïd", "sidi-bou-said", hs=0.25, tp=3.1)

    family, _ = detect_windows_detailed(home, destination, 4, 6, th, allow_prudent=True)
    watch = detect_watch_windows(home, destination, 4, 6, th)

    assert family == []
    assert watch
    assert watch[0]["category"] == "watch"
    assert watch[0]["technical_tier"] == "expert_review"
    assert watch[0]["family_go"] is False
    assert watch[0]["review_required"] is True
    assert watch[0]["margins"][0]["metric"] == "tp_s"


def test_watch_never_overrides_a_hard_veto(tmp_path):
    th = Thresholds.from_rules(DEFAULT_RULES)
    home = _site(tmp_path, "Gammarth", "gammarth-port")
    destination = _site(
        tmp_path,
        "Sidi Bou Saïd",
        "sidi-bou-said",
        wind=20.0,
        gusts=30.0,
        hs=0.25,
        tp=3.1,
    )

    assert detect_watch_windows(home, destination, 4, 6, th) == []


def test_watch_rejects_a_miss_outside_the_uncertainty_band(tmp_path):
    th = Thresholds.from_rules(DEFAULT_RULES)
    home = _site(tmp_path, "Gammarth", "gammarth-port")
    destination = _site(tmp_path, "Sidi Bou Saïd", "sidi-bou-said", hs=0.25, tp=2.9)

    assert detect_watch_windows(home, destination, 4, 6, th) == []


def test_watch_rejects_multiple_failing_wave_sources(tmp_path):
    th = Thresholds.from_rules(DEFAULT_RULES)
    home = _site(tmp_path, "Gammarth", "gammarth-port")
    destination = _site(
        tmp_path,
        "Sidi Bou Saïd",
        "sidi-bou-said",
        wave_models={"model_a": (0.25, 3.1), "model_b": (0.28, 3.1)},
    )

    assert detect_watch_windows(home, destination, 4, 6, th) == []


def test_reader_publishes_watch_in_a_separate_non_go_collection(tmp_path):
    rules = deepcopy(DEFAULT_RULES)
    home = make_spot_json("Gammarth", "gammarth-port", START, 8, tp=5.0)
    destination = make_spot_json("Sidi Bou Saïd", "sidi-bou-said", START, 8, hs=0.25, tp=3.1)
    (tmp_path / "gammarth-port.json").write_text(json.dumps(home), encoding="utf-8")
    (tmp_path / "sidi-bou-said.json").write_text(json.dumps(destination), encoding="utf-8")

    output = run_reader(tmp_path, tmp_path, "gammarth-port.json", 4, 6, rules=rules)
    entry = next(item for item in output["windows"] if item["dest_slug"] == "sidi-bou-said.json")

    assert entry["windows"] == []
    assert entry["watch_windows"]
    assert output["policy"]["watch_state_is_family_go"] is False
    assert entry["diagnostics"]["technical_review_candidates"] > 0


def test_reader_suppresses_watch_when_the_day_has_a_validated_go(tmp_path):
    home = make_spot_json("Gammarth", "gammarth-port", START, 8, tp=5.0)
    destination = make_spot_json("Sidi Bou Saïd", "sidi-bou-said", START, 8, hs=0.25, tp=5.0)
    (tmp_path / "gammarth-port.json").write_text(json.dumps(home), encoding="utf-8")
    (tmp_path / "sidi-bou-said.json").write_text(json.dumps(destination), encoding="utf-8")

    output = run_reader(tmp_path, tmp_path, "gammarth-port.json", 4, 6, rules=DEFAULT_RULES)
    entry = next(item for item in output["windows"] if item["dest_slug"] == "sidi-bou-said.json")

    assert entry["windows"]
    assert entry["watch_windows"] == []
