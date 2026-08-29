from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read_public(name: str) -> str:
    return (ROOT / "public" / name).read_text(encoding="utf-8")


def test_map_uses_mobile_visual_language_without_portaling_leaflet_dom():
    html = read_public("index.html")
    simple = read_public("simple-view.js")
    family = read_public("family-view.js")

    assert 'id="map-card" class="map-card"' in html
    assert 'id="mapDestinations"' in html
    assert 'class="map-toolbar"><div id="mapSummary"' in html
    assert 'class="map-legend"' in html
    assert "leaflet-tile-pane" in html
    assert "map-destination" in html
    assert "function afterMapLayout(action)" in html
    assert "requestAnimationFrame(()=>requestAnimationFrame" in html
    assert 'class="marker-pulse"' in html
    assert "function onshoreWedges(site)" in html
    assert "renderOnshoreSector(spotConfig[routePlan.origin_file || originFile] || origin)" in html
    assert 'class="onshore">Secteur onshore' in html
    assert "@keyframes pulsate-shelter" in html
    assert "Bateau abrité · Gammarth" in html
    assert "corridorRenderToken" in html
    assert "const exactRequested = Boolean(start || end || direction)" in html
    assert "width:44px;height:44px;line-height:44px" in html
    assert "simple-map-open" in simple
    assert "window.FABLEMapUI?.open?.(slug)" in simple
    assert "openFamilyTab('map')" not in simple
    assert ".map-card" in family
    assert "appendChild(mapCard)" not in simple
    assert "append(mapCard)" not in simple


def test_all_three_views_use_bar_quality_and_structured_no_go_checks():
    html = read_public("index.html")
    simple = read_public("simple-view.js")
    family = read_public("family-view.js")
    day_selection = read_public("js/day-selection.js")
    widgets = read_public("decision-widgets.js")

    assert "FABLEDecisionWidgets?.checksHtml" in simple
    assert "FABLEDecisionWidgets?.checksHtml" in family
    assert "FABLEDecisionWidgets?.checksHtml" in html
    assert 'class="quality-bars"' in day_selection
    assert "confidenceBarsHtml" in widgets
    assert "diagnostics.first_blocker" in widgets
    assert "confidence_score" not in widgets
    assert 'class="decision-check-panel"' in html
    assert "primaryChecksHTML" in html
