from __future__ import annotations

import json
from pathlib import Path

from fable.recommendations import build_recommendations


def _write(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data), encoding="utf-8")


def test_recommendations_only_use_valid_family_windows(tmp_path: Path) -> None:
    public = tmp_path / "public"
    public.mkdir()
    (tmp_path / "activity_profiles.yaml").write_text(
        """
ranking: {max_per_window: 2, max_total: 5, preferred_period_bonus: 7, lunar_max_bonus: 5}
activities:
  bottom_fishing:
    label_fr: Pêche au fond
    label_en: Bottom fishing
    requires_fishing_profile: true
    lunar_sensitive: true
    safety: {max_wind_kmh: 18, max_gust_kmh: 28, max_hs_m: 0.45, min_tp_s: 3.5, min_visibility_km: 6}
""",
        encoding="utf-8",
    )
    (tmp_path / "fishing_profiles.yaml").write_text(
        """
profiles:
  gammarth-port:
    seasons:
      summer:
        species: [pageot]
        techniques: [fond]
        baits: [ver]
        preferred_periods: [sunrise]
""",
        encoding="utf-8",
    )
    _write(
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
                },
                {"dest_slug": "blocked.json", "dest_name": "Blocked", "windows": []},
            ],
        },
    )
    _write(
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

    result = build_recommendations(tmp_path, public)

    assert len(result["recommendations"]) == 1
    recommendation = result["recommendations"][0]
    assert recommendation["dest_slug"] == "gammarth-port.json"
    assert recommendation["fishing"]["species"] == ["pageot"]
    assert recommendation["astronomy"]["illumination_pct"] == 50
    assert result["no_go"][0]["dest_slug"] == "blocked.json"
    assert (public / "recommendations.json").exists()


def test_activity_threshold_can_remove_option(tmp_path: Path) -> None:
    public = tmp_path / "public"
    public.mkdir()
    (tmp_path / "activity_profiles.yaml").write_text(
        "activities: {family_swim: {label_fr: Baignade, safety: {max_wind_kmh: 10, max_hs_m: 0.20}}}",
        encoding="utf-8",
    )
    (tmp_path / "fishing_profiles.yaml").write_text("profiles: {}", encoding="utf-8")
    _write(
        public / "windows.json",
        {"windows": [{"dest_slug": "spot.json", "dest_name": "Spot", "windows": [{"start": "2026-07-11T08:00:00+01:00", "end": "2026-07-11T12:00:00+01:00"}]}]},
    )
    _write(
        public / "spot.json",
        {"hourly": {"time": ["2026-07-11T08:00", "2026-07-11T09:00", "2026-07-11T10:00", "2026-07-11T11:00"], "wind_speed_10m": [12, 12, 12, 12], "hs": [0.25, 0.25, 0.25, 0.25]}, "daily": {"time": ["2026-07-11"]}},
    )

    assert build_recommendations(tmp_path, public)["recommendations"] == []
