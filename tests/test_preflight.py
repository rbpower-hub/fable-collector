import json

from fable.preflight import run_preflight


def test_preflight_ok_on_repo(repo_root, tmp_path, capsys):
    rc = run_preflight(repo_root, tmp_path)
    assert rc == 0
    out = capsys.readouterr().out
    assert "sites.yaml OK" in out and "rules.yaml OK" in out
    rn = json.loads((tmp_path / "rules.normalized.json").read_text(encoding="utf-8"))
    assert rn["family"]["window_hours"] == {"min": 4, "max": 6}
    sn = json.loads((tmp_path / "sites.normalized.json").read_text(encoding="utf-8"))
    assert sn["home"] == "gammarth-port"
    assert len(sn["sites"]) == 5
    assert sn["sites"][0]["onshore_sectors"]


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
