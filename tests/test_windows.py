"""Window detector tests: calm day -> family windows; storms/thunder -> none;
non-spot JSON files never become destinations."""

import datetime as dt
import json
from zoneinfo import ZoneInfo

from fable.config import DEFAULT_RULES, load_rules, rules_digest
from fable.window_policy import blocker
from fable.windows import (
    Thresholds,
    detect_windows,
    hour_ok_for_phase,
    load_site,
    run_reader,
    worst_metrics_at_hour,
)
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
    write_spot(tmp_path, "El Haouaria", "el-haouaria")
    kelibia = make_spot_json("Kelibia", "kelibia", DAY, 12)
    kelibia["meta"]["transit_speed_kts"] = {"min": 18, "max": 24}
    kelibia["meta"]["route_points"] = [
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
    assert comp["offshore_confidence"] in {"High", "Medium", "Low"}
    assert comp["offshore_start"] == pant["windows"][0]["start"]
    assert comp["offshore_end"] == pant["windows"][0]["end"]
    assert pant["windows"][0]["reason"] == "valid_composite_beta"


def test_composite_beta_requires_transfer_window(tmp_path):
    write_spot(tmp_path, "Gammarth (port)", "gammarth-port")
    write_spot(tmp_path, "El Haouaria", "el-haouaria", wind=35.0, gusts=55.0, hs=1.4, tp=4.0)
    kelibia = make_spot_json("Kelibia", "kelibia", DAY, 12)
    kelibia["meta"]["transit_speed_kts"] = {"min": 18, "max": 24}
    kelibia["meta"]["route_points"] = [
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


# ---------------------------------------------------------------------------
# v3.2 — source-coherent wave scenarios and invalid-source filtering
# ---------------------------------------------------------------------------


def test_wave_thresholds_never_use_an_artificial_cross_model_pair(tmp_path):
    waves = {
        "high_long_period": (0.60, 6.5),
        "low_short_period": (0.30, 3.0),
    }
    site = load(tmp_path, "Kélibia", "kelibia", wave_models=waves)

    _, detail = hour_ok_for_phase(site, 0, "transit", TH)

    assert "short_steep_hard" not in detail["reasons"]
    assert detail["metrics"].hs == 0.60
    assert detail["metrics"].tp == 6.5
    assert detail["metrics"].wave_scenarios == [
        {"source": "high_long_period", "hs": 0.60, "tp": 6.5},
        {"source": "low_short_period", "hs": 0.30, "tp": 3.0},
    ]


def test_gammarth_real_short_steep_pair_keeps_its_veto_and_source(tmp_path):
    waves = {
        "ncep_gfswave025": (0.60, 3.45),
        "ecmwf_wam025": (0.32, 4.20),
        "meteofrance_wave": (0.26, 4.75),
    }
    site = load(tmp_path, "Gammarth (port)", "gammarth-port", wave_models=waves)

    _, detail = hour_ok_for_phase(site, 0, "transit", TH)

    assert "short_steep_hard" in detail["reasons"]
    assert detail["blocking_wave_source"] == "ncep_gfswave025"
    assert detail["blocking_wave_pair"] == {"hs": 0.60, "tp": 3.45}


def test_tp_diagnostic_uses_the_model_that_actually_fails_its_hs_band(tmp_path):
    waves = {
        "ncep_gfswave025": (0.32, 3.85),
        "ecmwf_wam025": (0.14, 2.85),
        "meteofrance_wave": (0.14, 3.25),
    }
    site = load(tmp_path, "Gammarth (port)", "gammarth-port", wave_models=waves)

    ok, detail = hour_ok_for_phase(site, 0, "transit", TH)

    assert ok is False
    assert f"Tp<{TH.tp_min_at_lt04}@Hs<0.4" in detail["reasons"]
    assert detail["blocking_wave_source"] == "ecmwf_wam025"
    assert detail["blocking_wave_pair"] == {"hs": 0.14, "tp": 2.85}
    diagnostic = blocker(site, 0, "destination", "transit", detail)
    assert diagnostic["reason_fr"] == "période de vague trop courte (2.9 s)"
    assert diagnostic["reason_en"] == "wave period too short (2.9 s)"


def test_squall_delta_never_combines_gust_and_speed_from_different_models(tmp_path):
    payload = make_spot_json(
        "Kélibia",
        "kelibia",
        DAY,
        4,
        wave_models=CALM_WAVES_2,
    )
    gfs = payload["models"]["gfs_seamless"]["hourly"]
    icon = payload["models"]["icon_seamless"]["hourly"]
    gfs["wind_speed_10m"] = [12.7] * 4
    gfs["wind_gusts_10m"] = [24.1] * 4
    icon["wind_speed_10m"] = [3.8] * 4
    icon["wind_gusts_10m"] = [11.2] * 4
    path = tmp_path / "kelibia.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    site = load_site(path)

    ok, detail = hour_ok_for_phase(site, 0, "transit", TH)

    assert ok is True
    assert "squalls" not in detail["reasons"]
    assert {
        scenario["source"]: round(scenario["gust_delta"], 1)
        for scenario in detail["metrics"].wind_scenarios
    } == {
        "icon_seamless": 7.4,
        "gfs_seamless": 11.4,
    }


def test_real_single_model_squall_delta_still_blocks(tmp_path):
    payload = make_spot_json(
        "Kélibia",
        "kelibia",
        DAY,
        4,
        wave_models=CALM_WAVES_2,
    )
    icon = payload["models"]["icon_seamless"]["hourly"]
    icon["wind_speed_10m"] = [10.0] * 4
    icon["wind_gusts_10m"] = [28.0] * 4
    path = tmp_path / "kelibia.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    site = load_site(path)

    ok, detail = hour_ok_for_phase(site, 0, "transit", TH)

    assert ok is False
    assert "squalls" in detail["reasons"]


def test_dangerous_hs_with_missing_tp_keeps_hs_veto_only(tmp_path):
    site = load(
        tmp_path,
        "Kélibia",
        "kelibia",
        wave_models={"dangerous_missing_tp": (0.85, None)},
    )

    _, detail = hour_ok_for_phase(site, 0, "transit", TH)

    assert f"Hs>{TH.hs_no_go_min}" in detail["reasons"]
    assert "short_steep_hard" not in detail["reasons"]
    assert detail["metrics"].wave_scenarios == [
        {"source": "dangerous_missing_tp", "hs": 0.85, "tp": None}
    ]


def test_missing_tp_is_never_borrowed_from_another_source(tmp_path):
    site = load(
        tmp_path,
        "Kélibia",
        "kelibia",
        wave_models={
            "dangerous_missing_tp": (0.85, None),
            "low_short_period": (0.30, 3.0),
        },
    )

    _, detail = hour_ok_for_phase(site, 0, "transit", TH)

    assert f"Hs>{TH.hs_no_go_min}" in detail["reasons"]
    assert "short_steep_hard" not in detail["reasons"]
    assert {"source": "dangerous_missing_tp", "hs": 0.85, "tp": None} in (
        detail["metrics"].wave_scenarios
    )
    assert {"source": "low_short_period", "hs": 0.30, "tp": 3.0} in (
        detail["metrics"].wave_scenarios
    )


def test_all_zero_wave_series_is_excluded_from_hourly_statistics(tmp_path):
    waves = {
        "ncep_gfswave025": (0.0, 0.0),
        "ecmwf_wam025": (1.12, 4.20),
        "meteofrance_wave": (0.98, 4.30),
    }
    site = load(tmp_path, "Kélibia", "kelibia", wave_models=waves)

    metrics = worst_metrics_at_hour(site, 0)

    assert "ncep_gfswave025" not in site.waves_models
    assert site.excluded_wave_sources == [
        {"source": "ncep_gfswave025", "reason": "all_zero_wave_series"}
    ]
    assert metrics.n_wave_sources == 2
    assert round(metrics.hs_spread, 2) == 0.14
    assert metrics.hs == 1.12
    assert metrics.tp == 4.20


def test_zero_wave_pair_is_filtered_per_hour_without_disabling_source(tmp_path):
    payload = make_spot_json(
        "El Haouaria",
        "el-haouaria",
        DAY,
        12,
        wave_models={
            "ncep_gfswave025": (0.20, 5.0),
            "ecmwf_wam025": (0.30, 5.2),
        },
    )
    payload["marine_models"]["ncep_gfswave025"]["hourly"]["wave_height"][0] = 0.0
    payload["marine_models"]["ncep_gfswave025"]["hourly"]["wave_period"][0] = 0.0
    path = tmp_path / "el-haouaria.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    site = load_site(path)

    first = worst_metrics_at_hour(site, 0)
    second = worst_metrics_at_hour(site, 1)

    assert "ncep_gfswave025" in site.waves_models
    assert first.n_wave_sources == 1
    assert {
        "source": "ncep_gfswave025",
        "reason": "invalid_wave_pair",
    } in first.excluded_wave_sources
    assert second.n_wave_sources == 2


def test_three_valid_pantelleria_sources_remain_unchanged(tmp_path):
    waves = {
        "ncep_gfswave025": (1.08, 4.90),
        "ecmwf_wam025": (1.08, 4.15),
        "meteofrance_wave": (1.16, 4.30),
    }
    site = load(tmp_path, "Pantelleria", "pantelleria", wave_models=waves)

    metrics = worst_metrics_at_hour(site, 0)

    assert metrics.n_wave_sources == 3
    assert metrics.hs == 1.16
    assert metrics.tp == 4.30
    assert metrics.excluded_wave_sources == []


def test_decision_policy_does_not_change_existing_navigation_rules():
    rules = load_rules()
    watch = rules.pop("decision_policy")["watch"]

    assert rules_digest(rules) == "75d3a79038f4"
    assert watch["enabled"] is True


def test_prudent_never_accepts_a_sea_the_family_tier_refuses(tmp_path):
    """Le palier prudent élargit le vent, jamais l'état de la mer.

    `hour_ok_for_phase` est un if/elif : la branche prudent sautait entièrement
    la branche famille, et avec elle la matrice `tp_matrix`. Une heure refusée
    pour mer courte était donc repêchée par le palier censé être le plus
    conservateur, et publiée en GO PRUDENT avec, dans ses `cautions`, la règle
    même qui l'interdisait.

    On vérifie l'invariant sur une grille plutôt qu'une chaîne de raison : le
    test doit survivre à un réglage des seuils.
    """
    inversions = []
    for index, hs in enumerate((0.15, 0.25, 0.35, 0.40, 0.45, 0.55)):
        for tp in (3.0, 3.4, 3.8, 4.2, 4.6, 5.5):
            site = load(tmp_path, f"S{index}{tp}", f"s{index}-{tp}".replace(".", ""), hs=hs, tp=tp)
            ok_family, _ = hour_ok_for_phase(site, 0, "transit", TH, tier="family")
            ok_prudent, info = hour_ok_for_phase(site, 0, "transit", TH, tier="prudent")
            if ok_prudent and not ok_family:
                inversions.append((hs, tp, info["reasons"]))
    assert inversions == [], f"le palier prudent accepte une mer refusée par le palier famille : {inversions}"


def test_prudent_still_widens_the_wind_envelope(tmp_path):
    """L'élargissement du vent est voulu et configuré : c'est la raison d'être
    du palier. Le correctif sur les vagues ne doit pas le supprimer."""
    milieu = (TH.wind_family_max + TH.prudent_wind_max) / 2
    assert TH.prudent_wind_max > TH.wind_family_max, "le palier prudent doit élargir le vent"

    site = load(tmp_path, "Sidi Bou Saïd", "sidi-bou-said",
                wind=milieu, gusts=TH.prudent_gust_max - 2, hs=0.20, tp=6.0)
    ok_family, info_family = hour_ok_for_phase(site, 0, "transit", TH, tier="family")
    ok_prudent, _ = hour_ok_for_phase(site, 0, "transit", TH, tier="prudent")

    assert ok_family is False
    assert any(reason.startswith("vent>=") for reason in info_family["reasons"])
    assert ok_prudent is True


def test_prudent_keeps_its_own_stricter_limits(tmp_path):
    """Les limites propres au palier prudent restent en vigueur."""
    trop_haut = load(tmp_path, "Haut", "haut", hs=TH.prudent_hs_max + 0.05, tp=6.0)
    _, info = hour_ok_for_phase(trop_haut, 0, "transit", TH, tier="prudent")
    assert any("@prudent" in reason and reason.startswith("Hs>") for reason in info["reasons"])

    trop_court = load(tmp_path, "Court", "court", hs=0.20, tp=TH.prudent_tp_min - 0.2)
    _, info = hour_ok_for_phase(trop_court, 0, "transit", TH, tier="prudent")
    assert any("@prudent" in reason and reason.startswith("Tp<") for reason in info["reasons"])


def test_the_sunset_margin_covers_the_end_of_the_window(tmp_path):
    """`end_before_sunset_min` est le temps de rentrer, pas un réglage d'affichage.

    `all_in_operating_light` ne recevait que les *débuts* d'heure, alors que la
    fenêtre court jusqu'à `times[-1] + 1 h`. La marge était donc amputée de la
    durée de la dernière heure : coucher 19:34, limite 18:34, l'heure de 18:00
    passait et la fenêtre se terminait à 19:00, soit 34 minutes de marge au lieu
    de 60.
    """
    import datetime as dt

    from fable.window_policy import all_in_operating_light, operating_light_end

    sunset = dt.datetime(2026, 6, 21, 19, 34, tzinfo=TZ)

    class Site:
        tz = TZ
        daylight = {"2026-06-21": (dt.datetime(2026, 6, 21, 5, 3, tzinfo=TZ), sunset)}

    site = Site()
    limite = operating_light_end(site, dt.datetime(2026, 6, 21, 12, tzinfo=TZ), TH)
    assert limite == sunset - dt.timedelta(minutes=TH.daylight_before_sunset_min)

    def window(first_hour, last_hour):
        return [dt.datetime(2026, 6, 21, hour, 0, tzinfo=TZ) for hour in range(first_hour, last_hour)]

    # Se termine à 19:00 : 34 minutes de marge, sous les 60 exigées.
    assert all_in_operating_light(window(13, 19), site, TH) is False
    # Se termine à 18:00 : 94 minutes de marge.
    assert all_in_operating_light(window(12, 18), site, TH) is True
    # La borne exacte est acceptée : une fenêtre finissant à 18:34 tient.
    exacte = window(12, 18) + [dt.datetime(2026, 6, 21, 17, 34, tzinfo=TZ)]
    assert all_in_operating_light(exacte, site, TH) is True

    # Toute fenêtre acceptée respecte réellement la marge configurée.
    for first in range(5, 19):
        for last in range(first + 1, 20):
            times = window(first, last)
            if not times or not all_in_operating_light(times, site, TH):
                continue
            fin = times[-1] + dt.timedelta(hours=1)
            marge = (sunset - fin).total_seconds() / 60
            assert marge >= TH.daylight_before_sunset_min, (
                f"fenêtre {first:02d}:00 → {fin:%H:%M} acceptée avec {marge:.0f} min de marge"
            )


def test_an_empty_window_is_never_daylight(tmp_path):
    from fable.window_policy import all_in_operating_light

    class Site:
        tz = TZ
        daylight = {}

    assert all_in_operating_light([], Site(), TH) is False
