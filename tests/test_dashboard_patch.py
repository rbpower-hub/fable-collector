from pathlib import Path

from fable.dashboard_patch import patch_dashboard_index

ROOT = Path(__file__).resolve().parents[1]


def publish_to(tmp_path):
    source = ROOT / "public" / "index.html"
    target = tmp_path / "index.html"
    target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    assert patch_dashboard_index(target) is True
    return target, target.read_text(encoding="utf-8"), (tmp_path / "js" / "app.js").read_text(encoding="utf-8")


def test_offshore_map_does_not_prepend_positioning_route(tmp_path):
    _, _, app = publish_to(tmp_path)

    assert "const oneWayMultiDay" in app
    assert "originFile !== homeFile && !oneWayMultiDay" in app
    assert "route_kind:'offshore_one_way_beta'" in app
    assert "route_kind:'composite_beta'" not in app


def test_family_and_freshness_components_are_injected_once(tmp_path):
    target, html, _ = publish_to(tmp_path)
    assert html.count('<script src="./family-view.js"></script>') == 1
    assert html.count('<script src="./freshness-gate.js"></script>') == 1

    assert patch_dashboard_index(target) is False
    stable = target.read_text(encoding="utf-8")
    assert stable.count('<script src="./family-view.js"></script>') == 1
    assert stable.count('<script src="./freshness-gate.js"></script>') == 1


def test_missing_windows_never_synthesizes_family_go_from_collection_span(tmp_path):
    _, _, app = publish_to(tmp_path)

    assert "const winData = windows;" in app
    assert "synthétiser depuis meta.window" not in app
    assert "const synthesized = []" not in app
    assert "confidence: 'medium'" not in app
    assert "winItems.length ? winItems.map" in app
    assert "t('none_windows')" in app


def test_dashboard_uses_one_cadence_based_freshness_definition(tmp_path):
    _, _, app = publish_to(tmp_path)

    assert "const freshnessState = (status, referenceIso=null)" in app
    assert "cadence + 35 : 95" in app
    assert "const freshness = freshnessState(status);" in app
    assert "const freshNow = freshness.fresh;" in app
    assert "isFresh(entry, status)" in app
    assert "isFresh(entry,status)" in app
    assert "const T=180" not in app


def test_fullscreen_on_visibility_is_reserved_for_explicit_kiosk_mode(tmp_path):
    _, _, app = publish_to(tmp_path)

    assert "new URLSearchParams(window.location.search).get('kiosk') === '1'" in app
    assert "sessionStorage.setItem('fable_kiosk', '1')" in app
    assert "if (kioskMode && !document.fullscreenElement)" in app
    assert "if(!document.fullscreenElement) document.documentElement.requestFullscreen" not in app
    assert "if (document.hidden) return;\n    updateDashboard();" in app


def test_dashboard_patch_is_idempotent(tmp_path):
    target, first, first_app = publish_to(tmp_path)
    assert patch_dashboard_index(target) is False
    assert target.read_text(encoding="utf-8") == first
    assert (tmp_path / "js" / "app.js").read_text(encoding="utf-8") == first_app
