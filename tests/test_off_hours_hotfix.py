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


def test_disabled_module_contains_document_wide_observer_regression():
    script = (ROOT / "public" / "js" / "off-hours-refinements.js").read_text(encoding="utf-8")

    assert "observer.observe(document.body, {subtree: true, childList: true})" in script
    assert "_DISABLED_OFF_HOURS_REFINEMENTS_TAG" in (
        ROOT / "fable" / "dashboard_patch.py"
    ).read_text(encoding="utf-8")
