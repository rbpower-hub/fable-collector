from pathlib import Path

from fable.dashboard_modules import modularize_dashboard
from fable.dashboard_patch import patch_dashboard_index

ROOT = Path(__file__).resolve().parents[1]


def test_removed_module_is_not_injected(tmp_path):
    source = ROOT / "public" / "index.html"
    target = tmp_path / "index.html"
    target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")

    patch_dashboard_index(target)
    html = target.read_text(encoding="utf-8")
    removed_tag = 'off-hours-refinements.js'
    assert removed_tag not in html

    assert patch_dashboard_index(target) is False
    assert removed_tag not in target.read_text(encoding="utf-8")


def test_published_map_uses_all_configured_destinations(tmp_path):
    source = ROOT / "public" / "index.html"
    public = tmp_path / "public"
    public.mkdir()
    target = public / "index.html"
    target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")

    assert modularize_dashboard(target) is True
    app = (public / "js" / "app.js").read_text(encoding="utf-8")

    assert "const DEFAULT_MAP_VIEW = { center:[36.96,11.12], zoom:8 };" in app
    assert "const points = currentSpotLatLngs();" in app
    assert "GULF_OF_TUNIS_RADIUS_KM" not in app
