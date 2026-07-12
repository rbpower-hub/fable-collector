from __future__ import annotations

import json
from pathlib import Path

import pytest

from fable.knowledge import KnowledgePackError, load_knowledge_pack
from fable.recommendations import build_recommendations

ROOT = Path(__file__).resolve().parents[1]


def _write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data), encoding="utf-8")


def test_regional_fish_profiles_have_targeting_and_validation() -> None:
    pack = load_knowledge_pack(ROOT, strict=True)
    assert pack is not None
    assert pack.version == 2
    assert pack.status == "fish_intelligence_tunable"
    assert len(pack.fish) == 11

    for fish in pack.fish.values():
        targeting = fish["targeting"]
        assert targeting["technique_ids"]
        assert isinstance(targeting["terminal_tackle"], dict)
        assert fish["validation"]["local_validation_required"] is True

    catalog = pack.public_catalog()
    assert catalog["validation_summary"]["fish_with_targeting"] == 11
    assert catalog["schema"]["fish_intelligence"] == 1


def test_unknown_targeting_technique_is_blocking(tmp_path: Path) -> None:
    knowledge = tmp_path / "knowledge"
    for category in ("fish", "techniques", "ports", "activities"):
        (knowledge / category).mkdir(parents=True, exist_ok=True)
    (knowledge / "manifest.yaml").write_text(
        "version: 2\nstatus: test\nschema: {fish_intelligence: 1}\n",
        encoding="utf-8",
    )
    (knowledge / "techniques" / "bottom-fishing.yaml").write_text(
        """
id: bottom-fishing
gear:
  hook_sizes: {system: common_numbering, range: ['#8', '#2']}
""",
        encoding="utf-8",
    )
    (knowledge / "fish" / "pageot.yaml").write_text(
        """
id: pageot
targeting:
  technique_ids: [ghost-technique]
  terminal_tackle:
    hook_sizes: {system: common_numbering, range: ['#6', '#2']}
    leader_mm: [0.22, 0.30]
validation:
  local_validation_required: true
""",
        encoding="utf-8",
    )

    with pytest.raises(KnowledgePackError, match="unknown targeting technique"):
        load_knowledge_pack(tmp_path, strict=True)


def test_recommendations_v3_publish_fish_intelligence(tmp_path: Path) -> None:
    public = tmp_path / "public"
    public.mkdir()
    _write_json(
        public / "windows.json",
        {
            "generated_at": "2026-07-12T06:00:00+00:00",
            "windows": [
                {
                    "dest_slug": "gammarth-port.json",
                    "dest_name": "Gammarth",
                    "windows": [
                        {
                            "start": "2026-07-12T06:00:00+01:00",
                            "end": "2026-07-12T10:00:00+01:00",
                            "hours": 4,
                            "confidence": "high",
                            "category": "family",
                        }
                    ],
                }
            ],
        },
    )
    _write_json(
        public / "gammarth-port.json",
        {
            "meta": {"name": "Gammarth", "slug": "gammarth-port"},
            "hourly": {
                "time": [
                    "2026-07-12T06:00",
                    "2026-07-12T07:00",
                    "2026-07-12T08:00",
                    "2026-07-12T09:00",
                ],
                "wind_speed_10m": [8, 9, 10, 9],
                "wind_gusts_10m": [13, 14, 15, 14],
                "hs": [0.18, 0.20, 0.22, 0.20],
                "tp": [5.2, 5.0, 4.8, 5.0],
                "visibility": [20000, 20000, 18000, 18000],
            },
            "daily": {
                "time": ["2026-07-12"],
                "sunrise": ["2026-07-12T05:10"],
                "sunset": ["2026-07-12T19:40"],
                "moonrise": ["2026-07-12T02:00"],
                "moonset": ["2026-07-12T16:00"],
                "moon_phase": [0.25],
            },
        },
    )

    result = build_recommendations(ROOT, public)

    assert result["version"] == 3
    assert result["knowledge_pack"]["version"] == 2
    recommendation = result["recommendations"][0]
    fish = recommendation["fishing"]["species_details"][0]
    technique = recommendation["fishing"]["technique_details"][0]
    assert fish["targeting"]["terminal_tackle"]["hook_sizes"]["range"]
    assert fish["validation"]["local_validation_required"] is True
    assert technique["gear"]["hook_sizes"]["range"]
    assert (public / "knowledge.json").exists()
