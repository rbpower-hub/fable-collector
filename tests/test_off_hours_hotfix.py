from pathlib import Path

from fable.dashboard_patch import patch_dashboard_index

ROOT = Path(__file__).resolve().parents[1]


def test_recursive_off_hours_module_is_not_published(tmp_path):
    source = ROOT / "public" / "index.html"
    target = tmp_path / "index.html"
    target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")

    patch_dashboard_index(target)
    html = target.read_text(encoding="utf-8")

    assert '<script type="module" src="./js/off-hours-refinements.js"></script>' not in html
    assert '<script type="module" src="./js/day-selection.js"></script>' in html


def test_recursive_off_hours_module_is_removed_from_repository():
    assert not (ROOT / "public" / "js" / "off-hours-refinements.js").exists()
    patcher = (ROOT / "fable" / "dashboard_patch.py").read_text(encoding="utf-8")
    assert "OFF_HOURS_REFINEMENTS_TAG" not in patcher
