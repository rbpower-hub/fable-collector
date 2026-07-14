import textwrap

import pytest

from fable.config import (
    load_rules,
    load_sites,
    normalize_rules,
    rules_digest,
    validate_rules,
    window_bounds,
)


def test_rules_defaults_complete():
    from fable.config import DEFAULT_RULES
    assert validate_rules(DEFAULT_RULES) == []


def test_load_rules_merges_over_defaults(tmp_path):
    p = tmp_path / "rules.yaml"
    p.write_text("wind:\n  family_max_kmh: 18\n", encoding="utf-8")
    rules = load_rules(p)
    assert rules["wind"]["family_max_kmh"] == 18
    assert rules["sea"]["nogo_min_hs_m"] == 0.8  # default preserved
    assert validate_rules(rules) == []


def test_rules_digest_stable(tmp_path):
    p = tmp_path / "rules.yaml"
    p.write_text("wind:\n  family_max_kmh: 18\n", encoding="utf-8")
    assert rules_digest(load_rules(p)) == rules_digest(load_rules(p))
    assert rules_digest(load_rules(p)) != rules_digest(load_rules(tmp_path / "missing.yaml"))


def test_window_bounds_clamped():
    assert window_bounds({"window_hours": {"min": 1, "max": 12}}) == (4, 6)
    assert window_bounds({"window_hours": {"min": 5, "max": 6}}) == (5, 6)


def test_window_bounds_derived_from_corridor():
    rules = {
        "corridor": {
            "leg_structure_hours": {
                "transit_out": "1-1.5",
                "anchor_min": 2,
                "anchor_max": 4,
                "transit_back": "1.5-2",
            }
        }
    }
    assert window_bounds(rules) == (4, 6)


def test_normalize_rules_schema(repo_root):
    rules = load_rules(repo_root / "rules.yaml")
    n = normalize_rules(rules)
    assert n["family"]["hours_local"] == {"start": 8, "end": 21}
    assert n["family"]["window_hours"] == {"min": 4, "max": 6}
    assert n["family"]["thresholds"]["wind"]["family_max_kmh"] == 20.0
    assert n["family"]["thresholds"]["waves"]["tp_min_at_hs_lt_0_4_s"] == 3.2
    assert n["family"]["corridor"]["leg_structure_hours"]["transit_out"] == {"min": 1.0, "max": 1.5}
    assert n["family"]["corridor"]["leg_structure_hours"]["anchor"] == {"min": 2.0, "max": 4.0}
    assert n["family"]["corridor"]["leg_structure_hours"]["transit_back"] == {"min": 1.0, "max": 1.5}
    assert n["confidence"]["min_wind_models_for_not_low"] == 2


def test_load_sites_v2(repo_root):
    cfg = load_sites(repo_root / "sites.yaml")
    assert cfg.version == 2
    assert cfg.home == "gammarth-port"
    slugs = {s["slug"] for s in cfg.sites}
    assert slugs == {"gammarth-port", "sidi-bou-said", "ghar-el-melh", "ras-fartass", "el-haouaria", "kelibia", "pantelleria"}
    assert cfg.onshore_sectors("el-haouaria") == [(330, 360), (0, 70)]
    assert cfg.onshore_sectors("gammarth-port") == [(30, 150)]
    assert cfg.site("gammarth-port")["map_lat"] == pytest.approx(36.921)
    assert cfg.site("gammarth-port")["map_lon"] == pytest.approx(10.31)
    assert cfg.site("gammarth-port")["transit_speed_kts"] == {"min": 16.0, "max": 24.0}
    assert cfg.site("gammarth-port")["windows_enabled"] is True
    assert cfg.site("gammarth-port")["route_kind"] == "standard"
    kelibia_points = cfg.site("kelibia")["route_points"]
    assert len(kelibia_points) == 6
    assert kelibia_points[0]["name"] == "El Haouaria — au large"
    assert kelibia_points[-1]["name"] == "Approche Kélibia par le large"
    assert all(point["lon"] >= 11.008 for point in kelibia_points)
    assert cfg.site("pantelleria")["route_origin"] == "kelibia"
    assert cfg.site("pantelleria")["windows_enabled"] is True
    assert cfg.site("pantelleria")["beta"] is True
    assert cfg.site("pantelleria")["route_kind"] == "offshore_one_way_beta"


def test_load_sites_v1_legacy(tmp_path):
    p = tmp_path / "sites.yaml"
    p.write_text(textwrap.dedent("""
        - name: "Gammarth (port)"
          lat: 36.92
          lon: 10.28
        - name: "Kélibia"
          lat: 36.85
          lon: 11.09
    """), encoding="utf-8")
    cfg = load_sites(p)
    assert cfg.version == 1
    assert cfg.home == "gammarth-port"
    slugs = {s["slug"] for s in cfg.sites}
    assert "kelibia" not in slugs          # legacy exclusion preserved
    assert cfg.onshore_sectors("gammarth-port") == [(30, 150)]  # legacy hardcoded map


def test_load_sites_invalid_coords_skipped(tmp_path):
    p = tmp_path / "sites.yaml"
    p.write_text("- name: Bad\n  lat: 999\n  lon: 10\n- name: Good\n  lat: 36.9\n  lon: 10.2\n", encoding="utf-8")
    cfg = load_sites(p)
    assert [s["slug"] for s in cfg.sites] == ["good"]


def test_load_sites_invalid_map_coords_fallback(tmp_path):
    p = tmp_path / "sites.yaml"
    p.write_text(textwrap.dedent("""
        version: 2
        home: spot-a
        sites:
          - name: Spot A
            lat: 36.9
            lon: 10.2
            map_lat: 999
            map_lon: 999
    """), encoding="utf-8")
    cfg = load_sites(p)
    site = cfg.site("spot-a")
    assert site["map_lat"] == pytest.approx(36.9)
    assert site["map_lon"] == pytest.approx(10.2)


def test_load_sites_transit_speed_override(tmp_path):
    p = tmp_path / "sites.yaml"
    p.write_text(textwrap.dedent("""
        version: 2
        home: spot-a
        defaults:
          transit_speed_kts: {min: 14, max: 22}
        sites:
          - name: Spot A
            lat: 36.9
            lon: 10.2
          - name: Spot B
            lat: 37.0
            lon: 10.3
            transit_speed_kts: {min: 18, max: 28}
    """), encoding="utf-8")
    cfg = load_sites(p)
    assert cfg.site("spot-a")["transit_speed_kts"] == {"min": 14.0, "max": 22.0}
    assert cfg.site("spot-b")["transit_speed_kts"] == {"min": 18.0, "max": 28.0}


def test_load_sites_beta_route_metadata(tmp_path):
    p = tmp_path / "sites.yaml"
    p.write_text(textwrap.dedent("""
        version: 2
        home: gammarth-port
        sites:
          - name: Gammarth (port)
            lat: 36.9
            lon: 10.2
          - name: Pantelleria
            lat: 36.8333
            lon: 11.95
            beta: true
            windows_enabled: false
            route_origin: Gammarth (port)
            route_points:
              - name: Waypoint 1
                lat: 36.9
                lon: 10.8
            route_kind: offshore_beta
            route_note: Test beta route
            country: Italy
    """), encoding="utf-8")
    cfg = load_sites(p)
    pantelleria = cfg.site("pantelleria")
    assert pantelleria["beta"] is True
    assert pantelleria["windows_enabled"] is False
    assert pantelleria["route_origin"] == "gammarth-port"
    assert pantelleria["route_points"] == [{"lat": 36.9, "lon": 10.8, "name": "Waypoint 1"}]
    assert pantelleria["route_kind"] == "offshore_beta"
    assert pantelleria["route_note"] == "Test beta route"
    assert pantelleria["country"] == "Italy"


def test_load_sites_malformed(tmp_path):
    p = tmp_path / "sites.yaml"
    p.write_text("just a string", encoding="utf-8")
    with pytest.raises(ValueError):
        load_sites(p)
