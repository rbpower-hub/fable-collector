from pathlib import Path

from fable.knowledge import load_knowledge_pack

ROOT = Path(__file__).resolve().parents[1]


def test_regional_tunisian_ports_are_migrated() -> None:
    pack = load_knowledge_pack(ROOT, strict=True)
    assert pack is not None

    expected_ports = {
        "gammarth-port",
        "sidi-bou-said",
        "ghar-el-melh",
        "ras-fartass",
        "el-haouaria",
        "kelibia",
    }
    assert expected_ports.issubset(pack.ports)
    assert "pantelleria" not in pack.ports


def test_migrated_ports_have_four_seasons_and_no_unvalidated_zones() -> None:
    pack = load_knowledge_pack(ROOT, strict=True)
    assert pack is not None

    for port_id in (
        "gammarth-port",
        "sidi-bou-said",
        "ghar-el-melh",
        "ras-fartass",
        "el-haouaria",
        "kelibia",
    ):
        port = pack.ports[port_id]
        seasons = (port.get("fishing") or {}).get("seasons") or {}
        assert set(seasons) == {"spring", "summer", "autumn", "winter"}
        assert port.get("zones") == []


def test_regional_species_catalog_is_complete_for_migrated_profiles() -> None:
    pack = load_knowledge_pack(ROOT, strict=True)
    assert pack is not None

    expected_species = {
        "bonitot",
        "bogue",
        "chinchard",
        "dorade-grise",
        "dorade-royale",
        "merlan",
        "moustelle",
        "oblade",
        "pageot",
        "poulpe",
        "sar",
    }
    assert expected_species.issubset(pack.fish)
