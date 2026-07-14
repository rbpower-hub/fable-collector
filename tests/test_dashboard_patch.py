from pathlib import Path

from fable.dashboard_patch import patch_dashboard_index

ROOT = Path(__file__).resolve().parents[1]


def test_offshore_map_does_not_prepend_positioning_route(tmp_path):
    source = ROOT / "public" / "index.html"
    target = tmp_path / "index.html"
    target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")

    assert patch_dashboard_index(target) is True
    html = target.read_text(encoding="utf-8")

    assert "const offshoreOneWay" in html
    assert "originFile !== homeFile && !offshoreOneWay" in html
    assert "route_kind:'offshore_one_way_beta'" in html
    assert "route_kind:'composite_beta'" not in html


def test_offshore_map_patch_is_idempotent(tmp_path):
    source = ROOT / "public" / "index.html"
    target = tmp_path / "index.html"
    target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")

    assert patch_dashboard_index(target) is True
    first = target.read_text(encoding="utf-8")
    assert patch_dashboard_index(target) is False
    assert target.read_text(encoding="utf-8") == first
