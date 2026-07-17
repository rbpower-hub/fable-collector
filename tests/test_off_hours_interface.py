from pathlib import Path

from fable.dashboard_modules import modularize_dashboard
from fable.dashboard_patch import patch_dashboard_index

ROOT = Path(__file__).resolve().parents[1]


def test_off_hours_module_is_injected_once(tmp_path):
    source = ROOT / "public" / "index.html"
    target = tmp_path / "index.html"
    target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")

    assert patch_dashboard_index(target) is True
    html = target.read_text(encoding="utf-8")
    tag = '<script type="module" src="./js/off-hours-refinements.js"></script>'
    assert html.count(tag) == 1

    assert patch_dashboard_index(target) is False
    assert target.read_text(encoding="utf-8").count(tag) == 1


def test_published_map_uses_all_configured_destinations(tmp_path):
    source = ROOT / "public" / "index.html"
    public = tmp_path / "public"
    public.mkdir()
    target = public / "index.html"
    target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")

    # dashboard_modules resolves sites.yaml from the repository fallback when
    # the temporary parent does not contain one.
    assert modularize_dashboard(target) is True
    app = (public / "js" / "app.js").read_text(encoding="utf-8")

    assert "const DEFAULT_MAP_VIEW = { center:[36.96,11.12], zoom:8 };" in app
    assert "const points = currentSpotLatLngs();" in app
    assert "GULF_OF_TUNIS_RADIUS_KM" not in app


def test_off_hours_copy_is_explicitly_not_family_go():
    script = (ROOT / "public" / "js" / "off-hours-refinements.js").read_text(encoding="utf-8")

    assert "GO HORS HORAIRES" in script
    assert "Ce n’est pas un Family GO" in script
    assert "HORS HORAIRES FAMILIAUX" in script
    assert "off-hours-warning" in script
    assert "fishingHtml" in script
