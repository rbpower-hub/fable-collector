"""Les variables océaniques sont facultatives et ne doivent rien casser.

Température d'eau et niveau de la mer arrivent par un appel séparé, exprès :
la chaîne de repli des modèles de vagues porte la sécurité, elle ne doit jamais
échouer parce qu'un modèle de houle ignore la SST.
"""

from __future__ import annotations

import datetime as dt

import pytest

from fable.collect import attach_on_axis
from fable.openmeteo import OCEAN_KEYS, fetch_ocean, ocean_url

START = dt.date(2026, 8, 27)
END = dt.date(2026, 8, 30)
FAR_DEADLINE = 1e18


def test_ocean_url_asks_the_default_model_only():
    url = ocean_url(36.92, 10.28, "Africa/Tunis", START, END)
    assert "sea_surface_temperature" in url
    assert "sea_level_height_msl" in url
    # Un `models=` ici renverrait la requête vers un modèle de vagues qui
    # n'expose pas ces variables.
    assert "models=" not in url


def test_fetch_ocean_returns_series_when_available():
    payload = {
        "hourly": {
            "time": ["2026-08-27T12:00", "2026-08-27T13:00"],
            "sea_surface_temperature": [27.4, 27.6],
            "sea_level_height_msl": [0.11, 0.14],
        }
    }
    result = fetch_ocean(36.92, 10.28, "Africa/Tunis", START, END, FAR_DEADLINE, getter=lambda url: payload)
    assert result["_keys_present"] == OCEAN_KEYS
    assert result["hourly"]["sea_surface_temperature"] == [27.4, 27.6]


@pytest.mark.parametrize(
    "getter",
    [
        lambda url: (_ for _ in ()).throw(TimeoutError("timeout")),
        lambda url: {"error": True, "reason": "variable not available"},
        lambda url: {"hourly": {"time": ["2026-08-27T12:00"], "sea_surface_temperature": [None]}},
        lambda url: "pas un objet",
    ],
)
def test_fetch_ocean_never_raises(getter):
    result = fetch_ocean(36.92, 10.28, "Africa/Tunis", START, END, FAR_DEADLINE, getter=getter)
    assert result["hourly"] == {}
    assert result["_error"]


def test_fetch_ocean_respects_the_site_budget():
    def getter(url):
        raise AssertionError("aucun appel ne doit partir quand le budget est dépassé")

    result = fetch_ocean(36.92, 10.28, "Africa/Tunis", START, END, -1.0, getter=getter)
    assert result == {"hourly": {}, "_error": "site budget exceeded"}


def test_attach_on_axis_aligns_and_pads_holes():
    flat = {"time": ["12:00", "13:00", "14:00"], "wind_speed_10m": [8, 9, 10]}
    source = {"time": ["13:00", "14:00"], "sea_surface_temperature": [27.6, 27.8]}
    attached = attach_on_axis(flat, source, OCEAN_KEYS)
    assert attached == ["sea_surface_temperature"]
    assert flat["sea_surface_temperature"] == [None, 27.6, 27.8]
    assert flat["wind_speed_10m"] == [8, 9, 10]


def test_attach_on_axis_ignores_empty_sources():
    flat = {"time": ["12:00"], "wind_speed_10m": [8]}
    assert attach_on_axis(flat, {}, OCEAN_KEYS) == []
    assert attach_on_axis(flat, {"time": ["12:00"], "sea_surface_temperature": [None]}, OCEAN_KEYS) == []
    assert "sea_surface_temperature" not in flat
