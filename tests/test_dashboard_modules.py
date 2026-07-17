import json
import re
from pathlib import Path

from fable.config import load_sites
from fable.dashboard_patch import patch_dashboard_index

ROOT = Path(__file__).resolve().parents[1]


def published_dashboard(tmp_path):
    target = tmp_path / "index.html"
    target.write_text((ROOT / "public" / "index.html").read_text(encoding="utf-8"), encoding="utf-8")
    assert patch_dashboard_index(target) is True
    return target, target.read_text(encoding="utf-8")


def test_published_dashboard_externalizes_legacy_app_as_module(tmp_path):
    _, html = published_dashboard(tmp_path)
    app = (tmp_path / "js" / "app.js").read_text(encoding="utf-8")

    assert '<script type="module" src="./js/app.js"></script>' in html
    assert '<script src="./js/fallback-sites.js"></script>' in html
    inline_scripts = re.findall(r"<script>(.*?)</script>", html, flags=re.DOTALL)
    assert sum(len(script.splitlines()) for script in inline_scripts) < 50
    assert "import './i18n.js';" in app
    assert "import './map.js';" in app
    assert "import './corridor.js';" in app
    assert "(async function main()" in app


def test_generated_fallback_matches_sites_yaml(tmp_path):
    _, _ = published_dashboard(tmp_path)
    raw = (tmp_path / "js" / "fallback-sites.js").read_text(encoding="utf-8")
    payload = json.loads(raw.removeprefix("window.FABLE_DEFAULT_SPOT_CONFIG = ").removesuffix(";\n"))
    config = load_sites(ROOT / "sites.yaml")

    assert set(payload) == {f"{site['slug']}.json" for site in config.sites}
    for site in config.sites:
        item = payload[f"{site['slug']}.json"]
        assert item["name"] == site["name"]
        assert abs(item["lat"] - site["map_lat"]) <= 0.02
        assert abs(item["lon"] - site["map_lon"]) <= 0.02
        assert item["route_origin"] == site["route_origin"]
        assert item["route_kind"] == site["route_kind"]


def test_low_risk_debt_cleanup_is_present(tmp_path):
    _, html = published_dashboard(tmp_path)
    app = (tmp_path / "js" / "app.js").read_text(encoding="utf-8")

    assert 'id="fable-dashboard-debt-styles"' in html
    assert ".pill{" in html
    assert 'id="resetMapBtnTop"' in html
    assert 'id="resetMapBtn"' not in html
    assert "const prettifyDates = prettifyReasonDates;" in app


def test_family_map_is_reframed_after_hidden_tab_is_revealed(tmp_path):
    _, _ = published_dashboard(tmp_path)
    app = (tmp_path / "js" / "app.js").read_text(encoding="utf-8")

    assert "noWrap:true" in app
    assert "map.invalidateSize({ pan:false });" in app
    assert "resetMapView({ animate:false });" in app
    assert "attributeFilter:['data-family-tab','class']" in app
    assert '[data-family-tab="map"]' in app
