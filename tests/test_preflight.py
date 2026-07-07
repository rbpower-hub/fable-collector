import json

from fable.preflight import run_preflight


def test_preflight_ok_on_repo(repo_root, tmp_path, capsys):
    rc = run_preflight(repo_root, tmp_path)
    assert rc == 0
    out = capsys.readouterr().out
    assert "sites.yaml OK" in out and "rules.yaml OK" in out
    rn = json.loads((tmp_path / "rules.normalized.json").read_text(encoding="utf-8"))
    assert rn["family"]["window_hours"] == {"min": 4, "max": 6}
    assert rn["family"]["corridor"]["leg_structure_hours"]["transit_out"] == {"min": 1.0, "max": 1.5}
    sn = json.loads((tmp_path / "sites.normalized.json").read_text(encoding="utf-8"))
    assert sn["home"] == "gammarth-port"
    assert len(sn["sites"]) == 7
    assert sn["sites"][0]["map_lat"] == 36.921
    assert sn["sites"][0]["map_lon"] == 10.31
    assert sn["sites"][0]["transit_speed_kts"] == {"min": 16.0, "max": 24.0}
    assert sn["sites"][0]["windows_enabled"] is True
    assert sn["sites"][0]["route_kind"] == "standard"
    assert sn["sites"][0]["onshore_sectors"]
    kelibia = next(site for site in sn["sites"] if site["slug"] == "kelibia")
    assert len(kelibia["route_points"]) == 2
    pantelleria = next(site for site in sn["sites"] if site["slug"] == "pantelleria")
    assert pantelleria["windows_enabled"] is True
    assert pantelleria["beta"] is True
    assert pantelleria["route_origin"] == "kelibia"
    assert pantelleria["route_kind"] == "composite_beta"


def test_preflight_fails_cleanly_on_corrupt_rule_type(tmp_path, capsys):
    (tmp_path / "sites.yaml").write_text("- name: X\n  lat: 36.9\n  lon: 10.2\n", encoding="utf-8")
    (tmp_path / "rules.yaml").write_text("wind: {family_max_kmh: [not, a, number]}\n", encoding="utf-8")
    rc = run_preflight(tmp_path, tmp_path / "public")   # must NOT raise
    assert rc == 1
    assert "not a number" in capsys.readouterr().out


def test_preflight_legacy_v1_without_gammarth(tmp_path):
    (tmp_path / "sites.yaml").write_text("- name: Port X\n  lat: 36.9\n  lon: 10.2\n", encoding="utf-8")
    (tmp_path / "rules.yaml").write_text("", encoding="utf-8")
    rc = run_preflight(tmp_path, tmp_path / "public")
    assert rc == 0   # legacy config: home falls back to first site

def test_preflight_fails_on_missing_sites(tmp_path):
    (tmp_path / "rules.yaml").write_text("", encoding="utf-8")
    rc = run_preflight(tmp_path, tmp_path / "public")
    assert rc == 1
