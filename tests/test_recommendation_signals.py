"""Classement des activités : créneaux, marée, lune et signaux de confort.

Ces tests couvrent les corrections apportées au classement. Aucun d'eux ne
touche à la sécurité : une activité ne peut toujours ni créer un GO, ni
neutraliser un NO-GO.
"""

from __future__ import annotations

import datetime as dt

import pytest

from fable.recommendations import (
    _angle_in_sectors,
    _lunar_or_tidal_bonus,
    _moon,
    _moon_visible,
    _spread_by_day,
    _tide,
    _window_periods,
    advisories,
)

TZ = dt.timezone(dt.timedelta(hours=1))
DAILY = {
    "sunrise": "2026-08-27T05:45:00+01:00",
    "sunset": "2026-08-27T18:54:00+01:00",
    "moonrise": "2026-08-27T18:37:00+01:00",
    "moonset": "2026-08-27T04:49:00+01:00",
}


def window(start_hour: int, hours: int = 4) -> tuple[dt.datetime, dt.datetime]:
    start = dt.datetime(2026, 8, 27, start_hour, 0, tzinfo=TZ)
    return start, start + dt.timedelta(hours=hours)


def test_window_covering_sunset_is_not_labelled_day():
    """La régression corrigée : 15:00-19:00 couvre le coucher de 18:54."""
    periods = _window_periods(*window(15), DAILY)
    assert "sunset" in periods


def test_window_before_dawn_is_labelled_night():
    periods = _window_periods(*window(1, 3), DAILY)
    assert "night" in periods
    assert "sunrise" not in periods


def test_midday_window_is_day_only():
    assert _window_periods(*window(10), DAILY) == ["day"]


def test_dawn_window_covers_sunrise_and_day():
    periods = _window_periods(*window(5), DAILY)
    assert "sunrise" in periods
    assert "day" in periods


def test_moon_visibility_uses_moonrise_and_moonset():
    # Lune levée à 18:37, couchée à 04:49 : absente l'après-midi, présente le soir.
    assert _moon_visible(DAILY, *window(14, 3)) is False
    assert _moon_visible(DAILY, *window(20, 3)) is True
    assert _moon_visible({}, *window(20, 3)) is None


def test_tide_prefers_measured_range_over_moon_phase():
    spot = {
        "hourly": {
            "time": ["2026-08-27T12:00", "2026-08-27T13:00", "2026-08-27T14:00"],
            "sea_level_height_msl": [0.05, 0.16, 0.21],
        }
    }
    start, end = window(12, 3)
    tide = _tide(spot, start, end)
    assert tide["available"] is True
    assert tide["range_m"] == pytest.approx(0.16, abs=1e-6)
    assert tide["trend"] == "montante"

    ranking = {"lunar_max_bonus": 5, "tide_range_full_bonus_m": 0.25}
    bonus, detail_fr, _ = _lunar_or_tidal_bonus({"tide": tide}, ranking)
    assert bonus == pytest.approx(3.2, abs=0.05)
    assert "marnage mesuré" in detail_fr

    grande_maree = {"available": True, "range_m": 0.40, "trend": "montante"}
    plein, _, _ = _lunar_or_tidal_bonus({"tide": grande_maree}, ranking)
    assert plein == 5.0


def test_lunar_bonus_falls_back_to_phase_without_tide():
    context = {"tide": {"available": False}, "moon": _moon(0.5), "moon_visible": False}
    bonus, detail_fr, _ = _lunar_or_tidal_bonus(context, {"lunar_max_bonus": 5})
    assert bonus == 5.0
    assert "pleine lune" in detail_fr
    assert "sous l’horizon" in detail_fr


def test_quarter_moon_gives_no_bonus():
    context = {"tide": {"available": False}, "moon": _moon(0.25)}
    bonus, _, _ = _lunar_or_tidal_bonus(context, {"lunar_max_bonus": 5})
    assert bonus == 0.0


@pytest.mark.parametrize(
    ("angle", "expected"),
    [(90, True), (30, True), (150, True), (200, False), (350, False)],
)
def test_onshore_sector_membership(angle, expected):
    assert _angle_in_sectors(angle, [[30, 150]]) is expected


def test_onshore_sector_wrapping_north():
    assert _angle_in_sectors(350, [[330, 70]]) is True
    assert _angle_in_sectors(180, [[330, 70]]) is False


def test_advisories_report_heat_uv_and_onshore():
    metrics = {
        "max_uv_index": 7.7,
        "max_apparent_temperature_c": 44.8,
        "onshore_share": 1.0,
        "total_precipitation_mm": 0.0,
    }
    ids = {note["id"] for note in advisories(metrics, {}, {})}
    assert {"uv_high", "heat", "onshore"} <= ids
    assert "rain" not in ids


def test_advisory_thresholds_are_configurable():
    metrics = {"max_uv_index": 7.7}
    assert any(note["id"] == "uv_high" for note in advisories(metrics, {}, {"uv_index_high": 7}))
    assert not any(note["id"] == "uv_high" for note in advisories(metrics, {}, {"uv_index_high": 9}))


def test_offshore_wind_note_mentions_the_drift_as_well_as_the_flat_water():
    """Le vent de terre lisse l'eau et pousse vers le large. Taire la dérive
    serait trompeur : c'est la situation où la mer paraît la plus engageante."""
    notes = advisories({"offshore_share": 0.8}, {}, {})
    note = next(note for note in notes if note["id"] == "offshore")
    assert "large" in note["fr"]
    assert "paddles" in note["fr"] or "embarcations" in note["fr"]


def test_offshore_share_is_not_the_complement_of_onshore():
    """Un vent parallèle à la côte n'est ni onshore ni offshore."""
    from fable.recommendations import _opposite_sectors

    assert _opposite_sectors([[30, 150]]) == [[210, 330]]
    assert _opposite_sectors([[330, 70]]) == [[150, 250]]
    # Vent transversal : aucune des deux catégories ne le revendique.
    assert _angle_in_sectors(190, [[30, 150]]) is False
    assert _angle_in_sectors(190, _opposite_sectors([[30, 150]])) is False


def test_a_paddle_style_activity_can_flag_offshore_wind_as_a_caveat():
    """La dérive vers le large est une réserve d'activité, pas un blocage :
    la sécurité reste au moteur de fenêtres."""
    from fable.recommendations import _score

    activity = {
        "label_fr": "Paddle", "label_en": "Paddle",
        "safety": {"max_wind_kmh": 16, "max_gust_kmh": 24, "max_hs_m": 0.30},
        "comfort": {"max_offshore_share": 0.4, "penalty": 10},
    }
    metrics = {"max_wind_kmh": 10.0, "max_gust_kmh": 18.0, "max_hs_m": 0.20, "offshore_share": 0.9}
    item = _score("paddle", activity, metrics, {}, {}, {})
    assert item["blocked"] is False
    assert any("vent de terre" in caveat for caveat in item["caveats_fr"])
    assert item["score"] < 100


def test_spread_by_day_keeps_every_day_represented():
    items = [
        {"start": "2026-08-27T08:00"}, {"start": "2026-08-27T14:00"}, {"start": "2026-08-27T17:00"},
        {"start": "2026-08-28T08:00"}, {"start": "2026-08-28T14:00"},
        {"start": "2026-08-29T08:00"},
    ]
    kept = _spread_by_day(items, 3)
    days = {item["start"][:10] for item in kept}
    assert len(kept) == 3
    # Une simple troncature chronologique aurait gardé les trois du 27.
    assert days == {"2026-08-27", "2026-08-28", "2026-08-29"}


def test_spread_by_day_is_a_no_op_below_the_cap():
    items = [{"start": "2026-08-27T08:00"}, {"start": "2026-08-28T08:00"}]
    assert _spread_by_day(items, 5) == items


def test_score_reports_the_widest_overshoot_as_the_blocking_reason():
    """Une activité refusée doit dire quelle limite bloque, et de combien."""
    from fable.recommendations import _score

    activity = {
        "label_fr": "Baignade familiale",
        "label_en": "Family swim",
        "safety": {"max_wind_kmh": 14, "max_gust_kmh": 22, "max_hs_m": 0.25},
    }
    metrics = {"max_wind_kmh": 15.0, "max_gust_kmh": 34.9, "max_hs_m": 0.18}
    item = _score("family_swim", activity, metrics, {}, {}, {})
    assert item["blocked"] is True
    # 34,9/22 = 1,59 dépasse plus largement que 15/14 = 1,07.
    assert item["blockers"][0]["metric"] == "max_gust_kmh"
    assert "rafales 35 km/h pour une limite de 22 km/h" in item["reason_fr"]
    assert len(item["blockers"]) == 2


def test_score_keeps_an_unclipped_rank_score():
    """Deux activités à 100 à l'écran doivent rester départageables."""
    from fable.recommendations import _score

    activity = {
        "label_fr": "Escale", "label_en": "Stop", "lunar_sensitive": True,
        "safety": {"max_wind_kmh": 18, "max_gust_kmh": 28, "max_hs_m": 0.35},
    }
    metrics = {"max_wind_kmh": 6.0, "max_gust_kmh": 14.0, "max_hs_m": 0.18}
    context = {"tide": {"available": True, "range_m": 0.40, "trend": "montante"}}
    item = _score("sheltered_stop", activity, metrics, {}, context, {"lunar_max_bonus": 5})
    assert item["blocked"] is False
    assert item["score"] == 100.0
    assert item["rank_score"] > 100.0


def test_a_tolerant_activity_does_not_outrank_a_specialised_one():
    """Un seuil large fait mécaniquement un score élevé : le ratio valeur/limite
    reste petit. Sans rang, l'observation nature passerait devant la pêche un
    jour parfait, ce qui est le contraire de ce qu'attend l'utilisateur."""
    from fable.recommendations import _score

    conditions = {"max_wind_kmh": 8.0, "max_gust_kmh": 16.0, "max_hs_m": 0.15}
    tolerant = _score(
        "nature_watch",
        {"label_fr": "Observation", "label_en": "Watch", "tier": "secondary",
         "safety": {"max_wind_kmh": 20, "max_gust_kmh": 28, "max_hs_m": 0.45}},
        conditions, {}, {}, {},
    )
    specialised = _score(
        "light_jigging",
        {"label_fr": "Micro-jig", "label_en": "Jigging",
         "safety": {"max_wind_kmh": 16, "max_gust_kmh": 26, "max_hs_m": 0.40}},
        conditions, {}, {}, {},
    )
    # L'activité tolérante marque bien plus haut...
    assert tolerant["rank_score"] > specialised["rank_score"]
    # ... mais son rang la place derrière.
    assert tolerant["tier"] == "secondary"
    assert specialised["tier"] == "primary"
    ordered = sorted(
        [tolerant, specialised],
        key=lambda item: (0 if item["tier"] == "primary" else 1, -item["rank_score"]),
    )
    assert ordered[0]["activity_id"] == "light_jigging"


def test_share_caveats_are_written_as_percentages():
    """« 1,00 contre 0,60 » n'est pas lisible ; « 100 % de la fenêtre » l'est."""
    from fable.recommendations import _score

    item = _score(
        "soft_lure",
        {"label_fr": "Leurre souple", "label_en": "Soft lure",
         "safety": {"max_wind_kmh": 17, "max_gust_kmh": 27, "max_hs_m": 0.40},
         "comfort": {"max_onshore_share": 0.6}},
        {"max_wind_kmh": 10.0, "max_gust_kmh": 20.0, "max_hs_m": 0.20, "onshore_share": 1.0},
        {}, {}, {},
    )
    assert item["caveats_fr"] == ["vent de mer sur 100 % de la fenêtre (confort visé : 60 %)"]
