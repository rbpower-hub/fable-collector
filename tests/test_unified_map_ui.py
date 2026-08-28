from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read_public(name: str) -> str:
    return (ROOT / "public" / name).read_text(encoding="utf-8")


def test_map_has_one_shared_modern_touch_interface():
    expert = read_public("index.html")

    assert 'id="map-card"' in expert
    assert 'id="mapDestinations"' in expert
    assert 'class="map-recenter"' in expert
    assert 'min-width:44px;min-height:44px' in expert
    assert 'class="map-legend"' in expert
    assert 'id="resetMapBtnTop"' not in expert
    assert 'id="resetMapBtn"' not in expert
    assert "L.map('map',{zoomControl:false})" in expert
    assert "noWrap:true,maxZoom:18" in expert
    assert '.leaflet-tile-pane{filter:invert(1)' in expert
    assert "const DEFAULT_MAP_VIEW = { center:[36.96,11.12], zoom:8 };" in expert
    assert "خريطة الرحلات" in expert
    assert "المسار المحدد" in expert


def test_simple_view_mounts_map_without_leaving_simple_mode():
    simple = read_public("simple-view.js")

    assert 'id="simple-map-section"' in simple
    assert 'id="simple-map-slot"' in simple
    assert "window.FABLEMap?.restoreHome?.()" in simple
    assert "window.FABLEMap?.mount?.(document.getElementById('simple-map-slot'))" in simple
    assert "openFamilyTab('map')" not in simple
    assert "setMode('family', false)" not in simple


def test_family_and_expert_share_map_without_losing_selected_corridor():
    expert = read_public("index.html")
    family = read_public("family-view.js")

    assert "let activeMapFile = null" in expert
    assert "let activeMapWindowKey = null" in expert
    assert "setActiveMapFile(slug)" in expert
    assert "showRoutePreview(activeMapFile, {preserveWindow:true})" in expert
    assert "activeMapWindowKey.split('|')" in expert
    assert "window.FABLEMap = {" in expert
    assert 'body.family-board-mode[data-family-tab="map"] .map-card{display:block!important}' in family
    assert 'body.family-board-mode[data-family-tab="map"] #family-planning-host{display:none!important}' in family
    assert "window.FABLEMap?.restoreHome?.()" in family
    assert "window.FABLEMap?.invalidate?.()" in family
