from pathlib import Path

from fable.dashboard_patch import patch_dashboard_index

ROOT = Path(__file__).resolve().parents[1]


def test_offshore_map_does_not_prepend_positioning_route(tmp_path):
    source = ROOT / "public" / "index.html"
    target = tmp_path / "index.html"
    target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")

    assert patch_dashboard_index(target) is True
    html = target.read_text(encoding="utf-8")

    assert "const oneWayMultiDay" in html
    assert "originFile !== homeFile && !oneWayMultiDay" in html
    assert "route_kind:'offshore_one_way_beta'" in html
    assert "route_kind:'composite_beta'" not in html


def test_family_view_is_injected_once(tmp_path):
    source = ROOT / "public" / "index.html"
    target = tmp_path / "index.html"
    target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")

    assert patch_dashboard_index(target) is True
    html = target.read_text(encoding="utf-8")
    assert html.count('<script src="./family-view.js"></script>') == 1

    assert patch_dashboard_index(target) is False
    assert target.read_text(encoding="utf-8").count('<script src="./family-view.js"></script>') == 1


def test_missing_windows_never_synthesizes_family_go_from_collection_span(tmp_path):
    source = ROOT / "public" / "index.html"
    target = tmp_path / "index.html"
    target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")

    assert patch_dashboard_index(target) is True
    html = target.read_text(encoding="utf-8")

    assert "const winData = windows;" in html
    assert "synthétiser depuis meta.window" not in html
    assert "const synthesized = []" not in html
    assert "confidence: 'medium'" not in html
    assert "winItems.length ? winItems.map" in html
    assert "t('none_windows')" in html


def test_offshore_map_patch_is_idempotent(tmp_path):
    source = ROOT / "public" / "index.html"
    target = tmp_path / "index.html"
    target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")

    assert patch_dashboard_index(target) is True
    first = target.read_text(encoding="utf-8")
    assert patch_dashboard_index(target) is False
    assert target.read_text(encoding="utf-8") == first
