import json

from fable.offshore_recommendations import separate_offshore_recommendations


def test_offshore_crossings_are_removed_from_leisure_recommendations(tmp_path):
    (tmp_path / "windows.json").write_text(
        json.dumps({
            "windows": [
                {
                    "dest_slug": "pantelleria.json",
                    "dest_name": "Pantelleria",
                    "trip_mode": "one_way_multi_day",
                    "windows": [
                        {
                            "start": "2026-07-15T08:00:00+01:00",
                            "end": "2026-07-15T11:00:00+01:00",
                            "hours": 3,
                            "confidence": "High",
                            "category": "family",
                            "direction": "outbound",
                            "origin_slug": "kelibia.json",
                            "origin_name": "Kelibia",
                            "destination_slug": "pantelleria.json",
                            "destination_name": "Pantelleria",
                        }
                    ],
                }
            ]
        }),
        encoding="utf-8",
    )
    (tmp_path / "recommendations.json").write_text(
        json.dumps({
            "version": 3,
            "recommendations": [
                {"dest_slug": "gammarth-port.json", "activities": [{"activity_id": "swimming"}]},
                {"dest_slug": "pantelleria.json", "activities": [{"activity_id": "swimming"}]},
            ],
        }),
        encoding="utf-8",
    )

    result = separate_offshore_recommendations(tmp_path)

    assert [item["dest_slug"] for item in result["recommendations"]] == ["gammarth-port.json"]
    assert result["offshore_activity_policy"] == "navigation_only_no_leisure_recommendations"
    assert result["navigation_only"][0]["direction"] == "outbound"
    assert result["navigation_only"][0]["same_day_round_trip_required"] is False
