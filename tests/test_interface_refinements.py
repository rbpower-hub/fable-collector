from pathlib import Path

from fable.dashboard_patch import patch_dashboard_index

ROOT = Path(__file__).resolve().parents[1]


def published_dashboard(tmp_path):
    target = tmp_path / "index.html"
    target.write_text((ROOT / "public" / "index.html").read_text(encoding="utf-8"), encoding="utf-8")
    assert patch_dashboard_index(target) is True
    return target, target.read_text(encoding="utf-8"), (tmp_path / "js" / "app.js").read_text(encoding="utf-8")


def test_default_map_is_limited_to_the_gulf_of_tunis(tmp_path):
    _, _, app = published_dashboard(tmp_path)

    assert "center:[36.98,10.43], zoom:10" in app
    assert "const GULF_OF_TUNIS_RADIUS_KM = 55;" in app
    assert "distKm(home, spot) <= GULF_OF_TUNIS_RADIUS_KM" in app
    assert "const points = currentSpotLatLngs();" not in app


def test_day_selection_module_is_injected_once(tmp_path):
    target, html, _ = published_dashboard(tmp_path)
    tag = '<script type="module" src="./js/day-selection.js"></script>'

    assert html.count(tag) == 1
    assert patch_dashboard_index(target) is False
    assert target.read_text(encoding="utf-8").count(tag) == 1


def test_day_selection_module_moves_details_and_filters_activities():
    script = (ROOT / "public" / "js" / "day-selection.js").read_text(encoding="utf-8")

    assert '[data-family-tab="details"]{margin-inline-start:auto}' in script
    assert ".family-day[data-family-day-key]" in script
    assert "article.hidden = articleKey !== key" in script
    assert "Aucune activité associée à cette journée" in script
    assert "fable_selected_day" in script
