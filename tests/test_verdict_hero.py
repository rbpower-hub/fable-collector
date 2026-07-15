from pathlib import Path

from fable.dashboard_patch import patch_dashboard_index

ROOT = Path(__file__).resolve().parents[1]


def test_verdict_hero_is_injected_once(tmp_path):
    source = ROOT / "public" / "index.html"
    target = tmp_path / "index.html"
    target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")

    assert patch_dashboard_index(target) is True
    html = target.read_text(encoding="utf-8")
    assert html.count('<script src="./verdict-hero.js"></script>') == 1

    assert patch_dashboard_index(target) is False
    assert target.read_text(encoding="utf-8").count('<script src="./verdict-hero.js"></script>') == 1


def test_family_verdict_has_five_states_and_map_action():
    engine = (ROOT / "public" / "js" / "verdict.js").read_text(encoding="utf-8")
    hero = (ROOT / "public" / "verdict-hero.js").read_text(encoding="utf-8")

    for state in ("STALE", "NO_DATA", "GO_TODAY", "GO_SOON", "NO_GO"):
        assert state in engine
    assert "category !== 'family'" in engine
    assert "tripMode === 'one_way_multi_day'" in engine
    assert "routeKind.includes('offshore')" in engine
    assert "limited reliability — reconfirm before departure" in hero
    assert "fiabilité limitée — à reconfirmer avant de partir" in hero
    assert "data-verdict-action" in hero
    assert "scrollIntoView({behavior: 'smooth', block: 'start'})" in hero
