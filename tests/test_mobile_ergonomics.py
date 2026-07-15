from pathlib import Path

from fable.dashboard_patch import patch_dashboard_index

ROOT = Path(__file__).resolve().parents[1]


def test_mobile_ergonomics_is_injected_once(tmp_path):
    source = ROOT / "public" / "index.html"
    target = tmp_path / "index.html"
    target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")

    assert patch_dashboard_index(target) is True
    html = target.read_text(encoding="utf-8")
    app = (tmp_path / "js" / "app.js").read_text(encoding="utf-8")
    assert html.count('<script src="./mobile-ergonomics.js"></script>') == 1
    assert "},30000);" in app
    assert "countdown-30" in app

    assert patch_dashboard_index(target) is False
    assert target.read_text(encoding="utf-8").count('<script src="./mobile-ergonomics.js"></script>') == 1


def test_mobile_controls_reuse_existing_nodes_and_touch_targets():
    script = (ROOT / "public" / "mobile-ergonomics.js").read_text(encoding="utf-8")

    for element_id in ("viewToggleBtn", "themeToggle", "muteBtn", "langToggle", "fullscreenBtn"):
        assert element_id in script
    assert "controls.appendChild(node)" in script
    assert "@media(pointer:coarse)" in script
    assert "min-height:44px!important" in script
    assert "role=\"dialog\"" in script
    assert "aria-modal=\"true\"" in script


def test_mobile_tooltip_map_and_selection_behaviour_are_accessible():
    script = (ROOT / "public" / "mobile-ergonomics.js").read_text(encoding="utf-8")

    assert "showTouchTooltip" in script
    assert "window.innerWidth - rect.width - 8" in script
    assert "map.scrollIntoView({behavior: 'smooth', block: 'start'})" in script
    assert "sessionStorage.setItem(SELECTED_KEY" in script
    assert "restoreSelection" in script
    assert "line.setAttribute('role', 'button')" in script
    assert "line.tabIndex = 0" in script
    assert "['Enter', ' ']" in script
