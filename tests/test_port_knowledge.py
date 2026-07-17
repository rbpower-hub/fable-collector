from pathlib import Path

import pytest

from fable.port_knowledge import build_port_knowledge

ROOT = Path(__file__).resolve().parents[1]


def test_port_knowledge_publishes_routes_without_unvalidated_shelter_bonus(tmp_path):
    output = build_port_knowledge(ROOT, tmp_path)
    assert (tmp_path / "port-knowledge.json").exists()
    assert output["version"] == 3
    assert output["policy"]["ui_requires_validated_route_or_shelter"] is True
    assert output["policy"]["field_observations_are_advisory"] is True
    assert output["visible_ports_count"] == 0
    by_id = {item["port_id"]: item for item in output["ports"]}
    assert "korbous" not in by_id

    ghar = by_id["ghar-el-melh"]
    assert ghar["route"]["trip_mode"] == "round_trip_day"
    assert ghar["route"]["distance_nm"] > 0
    assert ghar["route"]["validated"] is False
    assert ghar["shelter_summary"]["bonus_enabled"] is False
    assert ghar["display_eligible"] is False

    ras_fartass = by_id["ras-fartass"]
    assert ras_fartass["name"] == "Ras Fartass"
    assert ras_fartass["role"] == "primary_coastal_destination"
    assert ras_fartass["route"]["validation_status"] == "field_observed_tunable"
    assert ras_fartass["route"]["validated"] is False
    assert "distincte de Korbous" in ras_fartass["route"]["note_fr"]
    assert len(ras_fartass["field_observations"]) == 1
    observation = ras_fartass["field_observations"][0]
    assert observation["date"] == "2026-07-17"
    assert observation["destination_id"] == "ras-fartass"
    assert observation["local_time_window"] == "09:00-19:30"
    assert observation["conditions_observed"] == "very_good"
    assert ras_fartass["shelter_summary"]["bonus_enabled"] is False

    kelibia = by_id["kelibia"]
    assert kelibia["route"]["distance_nm"] == pytest.approx(54.9, abs=0.1)
    assert kelibia["route"]["transit_hours"]["fast"] == pytest.approx(2.29, abs=0.01)
    assert kelibia["route"]["transit_hours"]["conservative"] == pytest.approx(3.05, abs=0.01)
    assert kelibia["route"]["validated"] is False
    assert kelibia["route"]["trip_mode"] == "one_way_multi_day"
    assert kelibia["route"]["same_day_round_trip_required"] is False
    assert kelibia["return_policy"]["mode"] == "independent"
    assert kelibia["display_eligible"] is False

    pantelleria = by_id["pantelleria"]
    assert pantelleria["route"]["origin_id"] == "kelibia"
    assert pantelleria["route"]["trip_mode"] == "one_way_multi_day"
    assert pantelleria["route"]["same_day_round_trip_required"] is False
    assert pantelleria["return_policy"]["mode"] == "independent"
    assert pantelleria["route"]["validated"] is False
    assert pantelleria["shelter_summary"]["bonus_enabled"] is False
    assert pantelleria["display_eligible"] is False
