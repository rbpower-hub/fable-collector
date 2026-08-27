"""Genere tests/fixtures/mobile_hours.json.

La fixture est un payload de spot minimal qui exerce chaque branche de
fable.window_policy.hour_ok_for_phase pour la phase transit. Elle sert de
table de reference partagee : le test Python verifie le moteur, le test
Node verifie public/mobile/js/hour-verdict.js. Les deux doivent donner la
meme sequence d'etats.

Relancer apres toute evolution de rules.yaml :
    python tools/make_mobile_fixture.py
"""

from __future__ import annotations

import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]

# (libelle, heure, vent, rafale, direction, hs, tp, visibilite_m, code)
CASES = [
    ("famille GO, vent offshore", "08:00", 8.0, 15.0, 200, 0.20, 3.6, 20000, 1),
    ("GO prudent : vent au-dessus de la limite famille", "09:00", 22.5, 26.0, 200, 0.30, 3.4, 20000, 1),
    ("veto rafales", "10:00", 12.0, 31.0, 200, 0.20, 3.6, 20000, 1),
    ("veto grain (ecart rafale/vent)", "11:00", 8.0, 26.0, 200, 0.20, 3.6, 20000, 1),
    ("periode trop courte", "12:00", 8.0, 15.0, 200, 0.30, 2.8, 20000, 1),
    ("vent onshore trop fort", "13:00", 23.0, 27.0, 90, 0.20, 3.6, 20000, 1),
    ("veto visibilite", "14:00", 8.0, 15.0, 200, 0.20, 3.6, 3000, 1),
    ("veto orage", "15:00", 8.0, 15.0, 200, 0.20, 3.6, 20000, 95),
    ("veto houle", "16:00", 8.0, 15.0, 200, 0.90, 6.0, 20000, 1),
    ("nuit, conditions famille", "03:00", 8.0, 15.0, 200, 0.20, 3.6, 20000, 1),
]

EXPECTED = [
    "go",
    "prudent",
    "nogo",
    "nogo",
    "nogo",
    "nogo",
    "nogo",
    "nogo",
    "nogo",
    "go",
]


def build() -> dict:
    rules = yaml.safe_load((ROOT / "rules.yaml").read_text(encoding="utf-8"))
    times = [f"2026-08-27T{case[1]}" for case in CASES]
    hourly = {
        "time": times,
        "wind_speed_10m": [c[2] for c in CASES],
        "wind_gusts_10m": [c[3] for c in CASES],
        "wind_direction_10m": [c[4] for c in CASES],
        "weather_code": [c[8] for c in CASES],
        "visibility": [c[7] for c in CASES],
        "hs": [c[5] for c in CASES],
        "tp": [c[6] for c in CASES],
        "wave_height": [c[5] for c in CASES],
        "wave_period": [c[6] for c in CASES],
    }
    wind_hourly = {
        key: hourly[key]
        for key in ("time", "wind_speed_10m", "wind_gusts_10m", "wind_direction_10m", "weather_code", "visibility")
    }
    marine_hourly = {"time": times, "wave_height": hourly["hs"], "wave_period": hourly["tp"]}
    return {
        "meta": {
            "name": "Fixture",
            "slug": "fixture-spot",
            "lat": 36.92,
            "lon": 10.28,
            "tz": "Africa/Tunis",
            "onshore_sectors": [[30, 150]],
            "shelter_bonus_radius_km": 0.0,
            "windows_enabled": True,
            "rules": rules,
        },
        "hourly": hourly,
        "models": {"model_a": {"hourly": wind_hourly}, "model_b": {"hourly": wind_hourly}},
        "marine_models": {"wave_a": {"hourly": marine_hourly}, "wave_b": {"hourly": marine_hourly}},
        "expected_states": EXPECTED,
        "case_labels": [case[0] for case in CASES],
    }


def main() -> int:
    target = ROOT / "tests" / "fixtures" / "mobile_hours.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(build(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
