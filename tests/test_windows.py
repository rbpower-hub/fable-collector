"""Window detector tests: calm day -> family windows; storms/thunder -> none;
non-spot JSON files never become destinations."""

import datetime as dt
import json
from zoneinfo import ZoneInfo

from fable.config import DEFAULT_RULES
from fable.windows import Thresholds, detect_windows, load_site, run_reader
from tests.helpers import TZ_NAME, make_spot_json

TZ = ZoneInfo(TZ_NAME)
TH = Thresholds.from_rules(DEFAULT_RULES)
# 08:00 local start => full daylight family range
DAY = dt.datetime(2026, 7, 6, 8, 0, tzinfo=TZ)


def write_spot(tmp_path, name, slug, **kw):
    d = make_spot_json(name, slug, kw.pop("start", DAY), kw.pop("hours", 12), **kw)
    p = tmp_path / f"{slug}.json"
    p.write_text(json.dumps(d), encoding="utf-8")
    return p


def load(tmp_path, name, slug, **kw):
    return load_site(write_spot(tmp_path, name, slug, **kw))


def test_calm_day_produces_family_window(tmp_path):
    home = load(tmp_path, "Gammarth (port)", "gammarth-port")
    dest = load(tmp_path, "Sidi Bou Saïd", "sidi-bou-said")
    wins = detect_windows(home, dest, 4, 6, TH)
    assert wins, "calm forecast must produce at least one window"
    w = wins[0]
    assert 4 <= w["hours"] <= 6                      # capped by phase design
    assert w["category"] == "family"
    assert w["confidence"] in ("Medium", "Low")      # High capped (single wave source)
    assert w["confidence"] == "Medium"               # 2 models, small spread


def test_storm_day_produces_no_window(tmp_path):
    home = load(tmp_path, "Gammarth (port)", "gammarth-port",
                wind=35.0, gusts=55.0, hs=1.4, tp=4.0)
    dest = load(tmp_path, "Sidi Bou Saïd", "sidi-bou-said",
                wind=35.0, gusts=55.0, hs=1.4, tp=4.0)
    assert detect_windows(home, dest, 4, 6, TH) == []


def test_thunderstorm_kills_window(tmp_path):
    home = load(tmp_path, "Gammarth (port)", "gammarth-port", code=95)
    dest = load(tmp_path, "Sidi Bou Saïd", "sidi-bou-said", code=95)
    assert detect_windows(home, dest, 4, 6, TH) == []


def test_short_steep_sea_blocks(tmp_path):
    # Hs 0.6 + Tp 4.5 -> short_steep_hard, even though Hs < nogo(0.8)
    home = load(tmp_path, "Gammarth (port)", "gammarth-port")
    dest = load(tmp_path, "Ras Fartass", "ras-fartass", hs=0.6, tp=4.5)
    assert detect_windows(home, dest, 4, 6, TH) == []


def test_onshore_wind_blocks_when_strong(tmp_path):
    # 23 km/h onshore (>22 threshold) at a spot with sector [30,150], dir=90
    home = load(tmp_path, "Gammarth (port)", "gammarth-port")
    dest = load(tmp_path, "Sidi Bou Saïd", "sidi-bou-said",
                wind=23.0, gusts=26.0, direction=90.0,
                onshore_sectors=[[30, 150]])
    assert detect_windows(home, dest, 4, 6, TH) == []


def test_offshore_same_speed_blocked_by_family_cap(tmp_path):
    # same 23 km/h but offshore: still blocked (family cap 20) -> asymmetry only below cap
    home = load(tmp_path, "Gammarth (port)", "gammarth-port")
    dest = load(tmp_path, "Sidi Bou Saïd", "sidi-bou-said",
                wind=23.0, gusts=26.0, direction=250.0)
    assert detect_windows(home, dest, 4, 6, TH) == []


def test_night_calm_is_off_hours(tmp_path):
    night = dt.datetime(2026, 7, 6, 22, 0, tzinfo=TZ)
    home = load(tmp_path, "Gammarth (port)", "gammarth-port", start=night, hours=6)
    dest = load(tmp_path, "Sidi Bou Saïd", "sidi-bou-said", start=night, hours=6)
    wins = detect_windows(home, dest, 4, 6, TH)
    assert wins and wins[0]["category"] == "off_hours"


def test_single_model_gives_low_confidence(tmp_path):
    home = load(tmp_path, "Gammarth (port)", "gammarth-port", n_models=1)
    dest = load(tmp_path, "Sidi Bou Saïd", "sidi-bou-said", n_models=1)
    wins = detect_windows(home, dest, 4, 6, TH)
    assert wins and wins[0]["confidence"] == "Low"


def test_run_reader_ignores_non_spot_files(tmp_path):
    """The v1 bug: catalog.json & rules.normalized.json appeared as destinations."""
    write_spot(tmp_path, "Gammarth (port)", "gammarth-port")
    write_spot(tmp_path, "Sidi Bou Saïd", "sidi-bou-said")
    (tmp_path / "catalog.json").write_text(json.dumps({"generated_at": "x", "files": []}))
    (tmp_path / "rules.normalized.json").write_text(json.dumps({"meta": {}, "family": {}}))
    (tmp_path / "sites.normalized.json").write_text(json.dumps({"sites": []}))
    (tmp_path / "index.json").write_text(json.dumps({"spots": []}))
    # a rogue non-spot json not in the blacklist -> excluded by CONTENT check
    (tmp_path / "notes.json").write_text(json.dumps({"hello": "world"}))

    out = run_reader(tmp_path, tmp_path, "gammarth-port.json", 4, 6, rules=DEFAULT_RULES)
    dests = {w["dest_slug"] for w in out["windows"]}
    assert dests == {"gammarth-port.json", "sidi-bou-said.json"}


def test_run_reader_caps_max_hours(tmp_path):
    write_spot(tmp_path, "Gammarth (port)", "gammarth-port", hours=13)
    out = run_reader(tmp_path, tmp_path, "gammarth-port.json", 4, 12, rules=DEFAULT_RULES)
    assert out["window_hours"]["max"] == 6            # v1 allowed 8+ with wrong phases
    for w in out["windows"]:
        for seg in w["windows"]:
            assert seg["hours"] <= 6


def test_run_reader_skips_windows_disabled_route(tmp_path):
    write_spot(tmp_path, "Gammarth (port)", "gammarth-port")
    pantelleria = make_spot_json("Pantelleria", "pantelleria", DAY, 12)
    pantelleria["meta"]["windows_enabled"] = False
    pantelleria["meta"]["beta"] = True
    (tmp_path / "pantelleria.json").write_text(json.dumps(pantelleria), encoding="utf-8")
    out = run_reader(tmp_path, tmp_path, "gammarth-port.json", 4, 6, rules=DEFAULT_RULES)
    dests = {w["dest_slug"] for w in out["windows"]}
    assert "pantelleria.json" not in dests


def test_run_reader_builds_composite_beta_window(tmp_path):
    write_spot(tmp_path, "Gammarth (port)", "gammarth-port")
    write_spot(tmp_path, "Ras Fartass", "ras-fartass")
    write_spot(tmp_path, "El Haouaria", "el-haouaria")
    kelibia = make_spot_json("Kelibia", "kelibia", DAY, 12)
    kelibia["meta"]["transit_speed_kts"] = {"min": 18, "max": 24}
    kelibia["meta"]["route_points"] = [
        {"name": "Ras Fartass", "lat": 36.8770, "lon": 10.6130},
        {"name": "El Haouaria", "lat": 37.0630, "lon": 11.0080},
    ]
    (tmp_path / "kelibia.json").write_text(json.dumps(kelibia), encoding="utf-8")
    pantelleria = make_spot_json("Pantelleria", "pantelleria", DAY, 12)
    pantelleria["meta"]["beta"] = True
    pantelleria["meta"]["windows_enabled"] = True
    pantelleria["meta"]["route_origin"] = "kelibia"
    pantelleria["meta"]["route_kind"] = "composite_beta"
    pantelleria["meta"]["transit_speed_kts"] = {"min": 18, "max": 24}
    (tmp_path / "pantelleria.json").write_text(json.dumps(pantelleria), encoding="utf-8")

    out = run_reader(tmp_path, tmp_path, "gammarth-port.json", 4, 6, rules=DEFAULT_RULES)
    pant = next(w for w in out["windows"] if w["dest_slug"] == "pantelleria.json")
    assert pant["windows"]
    comp = pant["windows"][0]["composite"]
    assert comp["route_origin"] == "kelibia.json"
    assert comp["transfer_origin"] == "gammarth-port.json"
    assert comp["transfer_hours"]["min"] > 0
    assert pant["windows"][0]["reason"] == "valid_composite_beta"


def test_composite_beta_requires_transfer_window(tmp_path):
    write_spot(tmp_path, "Gammarth (port)", "gammarth-port")
    write_spot(tmp_path, "Ras Fartass", "ras-fartass", wind=35.0, gusts=55.0, hs=1.4, tp=4.0)
    write_spot(tmp_path, "El Haouaria", "el-haouaria")
    kelibia = make_spot_json("Kelibia", "kelibia", DAY, 12)
    kelibia["meta"]["transit_speed_kts"] = {"min": 18, "max": 24}
    kelibia["meta"]["route_points"] = [
        {"name": "Ras Fartass", "lat": 36.8770, "lon": 10.6130},
        {"name": "El Haouaria", "lat": 37.0630, "lon": 11.0080},
    ]
    (tmp_path / "kelibia.json").write_text(json.dumps(kelibia), encoding="utf-8")
    pantelleria = make_spot_json("Pantelleria", "pantelleria", DAY, 12)
    pantelleria["meta"]["beta"] = True
    pantelleria["meta"]["windows_enabled"] = True
    pantelleria["meta"]["route_origin"] = "kelibia"
    pantelleria["meta"]["route_kind"] = "composite_beta"
    pantelleria["meta"]["transit_speed_kts"] = {"min": 18, "max": 24}
    (tmp_path / "pantelleria.json").write_text(json.dumps(pantelleria), encoding="utf-8")

    out = run_reader(tmp_path, tmp_path, "gammarth-port.json", 4, 6, rules=DEFAULT_RULES)
    pant = next(w for w in out["windows"] if w["dest_slug"] == "pantelleria.json")
    assert pant["windows"] == []


def test_reader_on_real_v1_payload(tmp_path, ras_fartass_payload):
    """Real recorded production payload (Oct 2025) must load & evaluate."""
    p = tmp_path / "ras-fartass.json"
    p.write_text(json.dumps(ras_fartass_payload), encoding="utf-8")
    s = load_site(p)
    assert s is not None
    assert s.slug == "ras-fartass"
    assert len(s.times) == 48
    assert s.onshore_sectors == [(330, 360), (0, 70)]  # legacy map fallback
    out = run_reader(tmp_path, tmp_path, "ras-fartass.json", 4, 6, rules=DEFAULT_RULES)
    assert out["windows"][0]["dest_slug"] == "ras-fartass.json"


# ---------------------------------------------------------------------------
# v2.1 — multi-model waves & conditional confidence
# ---------------------------------------------------------------------------
CALM_WAVES_2 = {"meteofrance_wave": (0.2, 5.0), "ncep_gfswave025": (0.25, 5.2)}


def test_two_agreeing_wave_models_allow_high(tmp_path):
    home = load(tmp_path, "Gammarth (port)", "gammarth-port", wave_models=CALM_WAVES_2)
    dest = load(tmp_path, "Sidi Bou Saïd", "sidi-bou-said", wave_models=CALM_WAVES_2)
    wins = detect_windows(home, dest, 4, 6, TH)
    assert wins and wins[0]["confidence"] == "High"
    det = wins[0]["confidence_details"]
    assert det["min_wave_sources_per_hour"] == 2
    assert det["max_hs_spread_m"] == 0.05


def test_single_wave_source_still_capped_medium(tmp_path):
    """Regression: one wave model -> High remains impossible."""
    home = load(tmp_path, "Gammarth (port)", "gammarth-port")   # flat single source
    dest = load(tmp_path, "Sidi Bou Saïd", "sidi-bou-said")
    wins = detect_windows(home, dest, 4, 6, TH)
    assert wins and wins[0]["confidence"] == "Medium"


def test_disagreeing_wave_models_no_high(tmp_path):
    waves = {"meteofrance_wave": (0.15, 5.5), "ncep_gfswave025": (0.45, 4.8)}  # spread 0.30 >= 0.2
    home = load(tmp_path, "Gammarth (port)", "gammarth-port", wave_models=CALM_WAVES_2)
    dest = load(tmp_path, "Sidi Bou Saïd", "sidi-bou-said", wave_models=waves)
    wins = detect_windows(home, dest, 4, 6, TH)
    assert wins and wins[0]["confidence"] == "Medium"


def test_worst_wave_model_wins_blocking(tmp_path):
    """If ANY wave model predicts dangerous seas, the hour is out (safety-first)."""
    waves = {"meteofrance_wave": (0.3, 5.5), "ncep_gfswave025": (0.9, 5.5)}  # one says Hs 0.9 > nogo
    home = load(tmp_path, "Gammarth (port)", "gammarth-port", wave_models=CALM_WAVES_2)
    dest = load(tmp_path, "Ras Fartass", "ras-fartass", wave_models=waves)
    assert detect_windows(home, dest, 4, 6, TH) == []


def test_worst_tp_wins_blocking(tmp_path):
    """Shortest period across models is retained: Hs 0.45 + Tp 4.0 < 4.5 -> refused."""
    waves = {"meteofrance_wave": (0.45, 5.5), "ncep_gfswave025": (0.45, 4.0)}
    home = load(tmp_path, "Gammarth (port)", "gammarth-port", wave_models=CALM_WAVES_2)
    dest = load(tmp_path, "Sidi Bou Saïd", "sidi-bou-said", wave_models=waves)
    assert detect_windows(home, dest, 4, 6, TH) == []
