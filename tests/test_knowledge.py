from __future__ import annotations

import json
from pathlib import Path

import pytest

from fable.knowledge import KnowledgePackError, load_knowledge_pack
from fable.recommendations import build_recommendations


def _write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data), encoding="utf-8")


def _minimal_pack(root: Path, *, bad_ref: bool = False) -> None:
    for name in ("fish", "techniques", "ports", "activities"):
        (root / "knowledge" / name).mkdir(parents=True, exist_ok=True)
    (root / "knowledge" / "manifest.yaml").write_text(
        "version: 1\nstatus: initial_tunable\nranking: {max_per_window: 3, max_total: 5, preferred_period_bonus: 7, lunar_max_bonus: 5}\n",
        encoding="utf-8",
    )
    (root / "knowledge" / "fish" / "pageot.yaml").write_text(
        "id: pageot\nlabel_fr: Pageot\nlabel_en: Common pandora\nhabitats: [sable, roche]\n",
        encoding="utf-8",
    )
    (root / "knowledge" / "techniques" / "bottom-fishing.yaml").write_text(
        "id: bottom-fishing\nlabel_fr: Pêche au fond légère\nlabel_en: Light bottom fishing\nfamily: bottom\n",
        encoding="utf-8",
    )
    species = "unknown" if bad_ref else "pageot"
    (root / "knowledge" / "ports" / "gammarth-port.yaml").write_text(
        f"""id: gammarth-port
label_fr: Gammarth
confidence: medium
depths_m: [4, 18]
habitats: [sable, roche]
fishing:
  seasons:
    summer:
      species: [{species}]
      techniques: [bottom-fishing]
      baits: [ver]
      preferred_periods: [sunrise]
""",
        encoding="utf-8",
    )
    (root / "knowledge" / "activities" / "bottom-fishing.yaml").write_text(
        """id: bottom-fishing
icon: "🎣"
label_fr: Pêche au fond légère
label_en: Light bottom fishing
requires_fishing_profile: true
lunar_sensitive: true
techniques: [bottom-fishing]
safety: {max_wind_kmh: 18, max_gust_kmh: 28, max_hs_m: 0.45, min_tp_s: 3.5, min_visibility_km: 6}
""",
        encoding="utf-8",
    )


def _weather(public: Path) -> None:
    _write_json(
        public / "windows.json",
        {
            "generated_at": "2026-07-10T06:00:00+00:00",
            "windows": [
                {
                    "dest_slug": "gammarth-port.json",
                    "dest_name": "Gammarth",
                    "windows": [
                        {
                            "start": "2026-07-11T06:00:00+01:00",
                            "end": "2026-07-11T10:00:00+01:00",
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
                "time": ["2026-07-11T06:00", "2026-07-11T07:00", "2026-07-11T08:00", "2026-07-11T09:00"],
                "wind_speed_10m": [8, 9, 10, 9],
                "wind_gusts_10m": [13, 14, 15, 14],
                "hs": [0.18, 0.20, 0.22, 0.20],
                "tp": [5.2, 5.0, 4.8, 5.0],
                "visibility": [20000, 20000, 18000, 18000],
            },
            "daily": {
                "time": ["2026-07-11"],
                "sunrise": ["2026-07-11T05:10"],
                "sunset": ["2026-07-11T19:40"],
                "moonrise": ["2026-07-11T02:00"],
                "moonset": ["2026-07-11T16:00"],
                "moon_phase": [0.25],
            },
        },
    )


def test_load_and_validate_knowledge_pack(tmp_path: Path) -> None:
    _minimal_pack(tmp_path)
    pack = load_knowledge_pack(tmp_path)
    assert pack is not None
    assert pack.public_catalog()["counts"] == {"fish": 1, "techniques": 1, "ports": 1, "activities": 1}


def test_unknown_reference_blocks_pack(tmp_path: Path) -> None:
    _minimal_pack(tmp_path, bad_ref=True)
    with pytest.raises(KnowledgePackError, match="unknown fish"):
        load_knowledge_pack(tmp_path)


def test_recommendations_resolve_structured_knowledge(tmp_path: Path) -> None:
    _minimal_pack(tmp_path)
    public = tmp_path / "public"
    public.mkdir()
    _weather(public)
    result = build_recommendations(tmp_path, public)
    assert result["version"] == 2
    assert result["knowledge_pack"]["counts"]["fish"] == 1
    fishing = result["recommendations"][0]["fishing"]
    assert fishing["species"] == ["Pageot"]
    assert fishing["species_ids"] == ["pageot"]
    assert fishing["technique_ids"] == ["bottom-fishing"]
    assert (public / "knowledge.json").exists()
