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


def _minimal_profiles(tmp_path: Path) -> None:
    (tmp_path / "activity_profiles.yaml").write_text(
        "ranking: {max_per_window: 2, max_total: 5}\nactivities: {}\n", encoding="utf-8"
    )
    (tmp_path / "fishing_profiles.yaml").write_text("profiles: {}", encoding="utf-8")


def _no_go_for(tmp_path: Path, blocker: dict, dest_name: str = "El Haouaria") -> dict:
    public = tmp_path / "public"
    public.mkdir()
    _minimal_profiles(tmp_path)
    _write(
        public / "windows.json",
        {
            "generated_at": "2026-08-27T06:00:00+00:00",
            "windows": [
                {
                    "dest_slug": "dest.json",
                    "dest_name": dest_name,
                    "required_hours": 6,
                    "windows": [],
                    "diagnostics": {"first_blocker": blocker},
                }
            ],
        },
    )
    return build_recommendations(tmp_path, public)["no_go"][0]


def test_no_go_reason_omits_a_location_equal_to_the_destination(tmp_path: Path) -> None:
    """« à El Haouaria » pour El Haouaria n'apporte rien : on ne le répète pas."""
    entry = _no_go_for(
        tmp_path,
        {
            "location_name": "El Haouaria",
            "phase": "transit",
            "reason_fr": "rafales trop fortes (34 km/h)",
            "reason_en": "gusts too strong (34 km/h)",
        },
    )
    assert "à El Haouaria" not in entry["reason_fr"]
    assert "rafales trop fortes (34 km/h)" in entry["reason_fr"]
    assert "(traversée)" in entry["reason_fr"]


def test_no_go_reason_keeps_a_location_on_the_route(tmp_path: Path) -> None:
    """Le blocage peut tomber sur une étape : là, le lieu est l'information utile."""
    entry = _no_go_for(
        tmp_path,
        {
            "location_name": "Kelibia",
            "phase": "transit",
            "reason_fr": "vent trop fort (26 km/h)",
            "reason_en": "wind too strong (26 km/h)",
        },
        dest_name="Pantelleria",
    )
    assert "à Kelibia" in entry["reason_fr"]
    assert "at Kelibia" in entry["reason_en"]


def test_no_go_english_carries_the_same_detail_as_french(tmp_path: Path) -> None:
    entry = _no_go_for(
        tmp_path,
        {
            "location_name": "Ras Fartass",
            "phase": "anchor",
            "reason_fr": "période de vague trop courte (2.9 s)",
            "reason_en": "wave period too short (2.9 s)",
        },
        dest_name="Ras Fartass",
    )
    assert "(au mouillage)" in entry["reason_fr"]
    assert "(at anchor)" in entry["reason_en"]


def _gust_case(tmp_path: Path, gusts: list[float]) -> dict:
    """Fenêtre 08:00→13:00 dont la fin monte en rafales."""
    public = tmp_path / "public"
    public.mkdir()
    (tmp_path / "activity_profiles.yaml").write_text(
        """
ranking: {max_per_window: 2, max_total: 5, min_activity_hours: 2}
activities:
  sheltered_stop:
    icon: "⚓"
    label_fr: Escale côtière abritée
    label_en: Sheltered coastal stop
    safety: {max_wind_kmh: 18, max_gust_kmh: 28, max_hs_m: 0.35}
""",
        encoding="utf-8",
    )
    (tmp_path / "fishing_profiles.yaml").write_text("profiles: {}", encoding="utf-8")
    _write(
        public / "windows.json",
        {
            "generated_at": "2026-08-31T06:00:00+00:00",
            "windows": [
                {
                    "dest_slug": "gammarth-port.json",
                    "dest_name": "Gammarth",
                    "windows": [
                        {
                            "start": "2026-08-31T08:00:00+01:00",
                            "end": "2026-08-31T13:00:00+01:00",
                            "hours": 5,
                            "category": "family",
                        }
                    ],
                }
            ],
        },
    )
    _write(
        public / "gammarth-port.json",
        {
            "meta": {"name": "Gammarth", "tz": "Africa/Tunis"},
            "hourly": {
                "time": [f"2026-08-31T{hour:02d}:00" for hour in range(8, 13)],
                "wind_speed_10m": [4.2, 3.3, 3.6, 5.4, 7.9],
                "wind_gusts_10m": gusts,
                "wave_height": [0.16] * 5,
                "wave_period": [4.0] * 5,
            },
        },
    )
    return build_recommendations(tmp_path, public)


def test_a_single_windy_hour_yields_a_reduced_slot_not_an_empty_day(tmp_path: Path) -> None:
    """Le cas réel du lundi 31 août : une seule heure au-dessus de la limite.

    Les seuils portaient sur le maximum de la fenêtre, donc cette heure écartait
    l'activité pour les cinq heures. On propose désormais le créneau réduit, qui
    reste strictement inclus dans la fenêtre Family GO validée.
    """
    result = _gust_case(tmp_path, [9.7, 10.4, 10.8, 13.7, 34.9])
    assert result["no_activity"] == []
    activity = result["recommendations"][0]["activities"][0]
    slot = activity["slot"]
    assert slot["partial"] is True
    assert slot["start"] == "2026-08-31T08:00:00+01:00"
    # 12:00 est l'heure a 34,9 km/h : le creneau s'arrete avant.
    assert slot["end"] == "2026-08-31T12:00:00+01:00"
    assert slot["hours"] == 4
    assert slot["window_hours"] == 5
    # La justification cite les rafales du creneau, pas celles de la fenetre.
    assert "14 km/h" in activity["why_fr"]
    assert "35 km/h" not in activity["why_fr"]


def test_a_slot_too_short_still_blocks_and_explains(tmp_path: Path) -> None:
    """Sous le minimum, on ne bricole pas un créneau : on dit pourquoi."""
    result = _gust_case(tmp_path, [9.7, 34.9, 34.9, 34.9, 34.9])
    assert result["recommendations"] == []
    entry = result["no_activity"][0]
    assert entry["closest"][0]["activity_id"] == "sheltered_stop"
    assert "rafales" in entry["closest"][0]["reason_fr"]


def test_a_calm_window_keeps_its_full_span(tmp_path: Path) -> None:
    result = _gust_case(tmp_path, [9.7, 10.4, 10.8, 13.7, 14.0])
    slot = result["recommendations"][0]["activities"][0]["slot"]
    assert slot["partial"] is False
    assert slot["hours"] == 5


def test_reduced_slot_recomputes_tide_and_moon_visibility(tmp_path: Path, monkeypatch) -> None:
    """Les signaux d'un creneau reduit doivent utiliser ses propres bornes."""
    import fable.recommendations as recommendations

    tide_bounds = []
    moon_bounds = []

    def fake_tide(_spot, start, end):
        tide_bounds.append((start.hour, end.hour))
        return {"available": False}

    def fake_moon(_daily, start, end):
        moon_bounds.append((start.hour, end.hour))
        return None

    monkeypatch.setattr(recommendations, "_tide", fake_tide)
    monkeypatch.setattr(recommendations, "_moon_visible", fake_moon)
    _gust_case(tmp_path, [9.7, 10.4, 10.8, 13.7, 34.9])

    assert tide_bounds == [(8, 13), (8, 12)]
    assert moon_bounds == [(8, 13), (8, 12)]


def test_nature_content_is_only_published_when_the_pack_sources_it(tmp_path: Path) -> None:
    """Le bloc nature ne se fabrique pas : sans référence dans le pack, rien.

    Une carte vide vaut mieux qu'une observation inventée pour la remplir.
    """
    from fable.recommendations import _nature

    class Pack:
        ports = {
            "el-haouaria": {"nature": {"status": "sourced_public_reference",
                                       "sources": ["AAO BirdLife"],
                                       "seasons": {"spring": {"headline_fr": "Migration de printemps"}}}},
            "gammarth-port": {},
        }

    assert _nature(Pack(), "el-haouaria", "spring")["headline_fr"] == "Migration de printemps"
    assert _nature(Pack(), "el-haouaria", "summer") == {}
    assert _nature(Pack(), "gammarth-port", "spring") == {}
    assert _nature(None, "el-haouaria", "spring") == {}

    Pack.ports["unsourced"] = {
        "nature": {"sources": [], "seasons": {"spring": {"headline_fr": "Sans preuve"}}}
    }
    assert _nature(Pack(), "unsourced", "spring") == {}
