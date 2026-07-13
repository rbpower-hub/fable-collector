from pathlib import Path

from fable.port_knowledge import build_port_knowledge

ROOT = Path(__file__).resolve().parents[1]


def test_port_knowledge_publishes_routes_without_unvalidated_shelter_bonus(tmp_path):
    output = build_port_knowledge(ROOT, tmp_path)
    assert (tmp_path / "port-knowledge.json").exists()
    by_id = {item["port_id"]: item for item in output["ports"]}

    ghar = by_id["ghar-el-melh"]
    assert ghar["route"]["trip_mode"] == "round_trip_day"
    assert ghar["route"]["distance_nm"] > 0
    assert ghar["shelter_summary"]["bonus_enabled"] is False

    pantelleria = by_id["pantelleria"]
    assert pantelleria["route"]["origin_id"] == "kelibia"
    assert pantelleria["route"]["trip_mode"] == "one_way_multi_day"
    assert pantelleria["route"]["same_day_round_trip_required"] is False
    assert pantelleria["return_policy"]["mode"] == "independent"
    assert pantelleria["shelter_summary"]["bonus_enabled"] is False
