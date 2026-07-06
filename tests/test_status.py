import datetime as dt
import json
from zoneinfo import ZoneInfo

from fable.status import build_catalog, build_status, build_status_html, build_windows_md, final_check

TZ = ZoneInfo("Africa/Tunis")


def seed_public(tmp_path):
    (tmp_path / "gammarth-port.json").write_text(json.dumps(
        {"meta": {}, "hourly": {"time": [f"t{i}" for i in range(48)]}}), encoding="utf-8")
    (tmp_path / "index.json").write_text("{}", encoding="utf-8")
    return tmp_path


def test_catalog_excludes_itself(tmp_path):
    seed_public(tmp_path)
    cat = build_catalog(tmp_path, TZ)
    names = [f["path"] for f in cat["files"]]
    assert "catalog.json" not in names
    assert "gammarth-port.json" in names


def test_status_flags_missing_spots(tmp_path):
    seed_public(tmp_path)
    build_catalog(tmp_path, TZ)
    st = build_status(tmp_path, TZ, expected_spots=["gammarth-port.json", "sidi-bou-said.json"])
    assert st["missing_spots"] == ["sidi-bou-said.json"]
    assert st["build_ok"] is False
    # stale_after = generated + cadence + leeway
    gen = dt.datetime.fromisoformat(st["generated_at"])
    stale = dt.datetime.fromisoformat(st["stale_after"])
    assert (stale - gen) == dt.timedelta(minutes=95)


def test_status_html_contains_client_side_freshness(tmp_path):
    seed_public(tmp_path)
    build_catalog(tmp_path, TZ)
    st = build_status(tmp_path, TZ, expected_spots=["gammarth-port.json"])
    build_status_html(tmp_path, st)
    html = (tmp_path / "status.html").read_text(encoding="utf-8")
    assert "Date.now()" in html          # freshness judged in the browser, not at build
    assert "OBSOLÈTE" in html


def test_windows_md(tmp_path):
    (tmp_path / "windows.json").write_text(json.dumps({
        "generated_at": "2026-07-06T10:00:00+01:00",
        "windows": [
            {"dest_slug": "a.json", "dest_name": "A", "windows": []},
            {"dest_slug": "b.json", "dest_name": "B", "windows": [
                {"start": "s", "end": "e", "hours": 5, "category": "family", "confidence": "Medium"}]},
        ]}), encoding="utf-8")
    build_windows_md(tmp_path, TZ)
    md = (tmp_path / "windows.md").read_text(encoding="utf-8")
    assert "## B" in md and "## A" not in md
    assert "(5 h, family, confiance Medium)" in md


def test_final_check_detects_problems(tmp_path):
    problems = final_check(tmp_path, ["gammarth-port.json"])
    assert any("index.json" in p for p in problems)
    assert any("gammarth-port.json" in p for p in problems)
