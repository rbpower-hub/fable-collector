"""La fixture partagee par Mobile_view doit refleter le moteur.

tests/fixtures/mobile_hours.json contient un payload de spot synthetique et la
sequence d'etats attendue. Ce test verifie le cote Python ; le test Node
tests/js/mobile-hour-verdict.test.mjs verifie que
public/mobile/js/hour-verdict.js produit la meme sequence a partir de la meme
fixture. Les deux cotes sont donc epingles sur la meme table de reference.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from fable.window_models import Thresholds, load_site
from fable.window_policy import hour_ok_for_phase

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "mobile_hours.json"


@pytest.fixture(scope="module")
def payload() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def thresholds() -> Thresholds:
    return Thresholds.from_rules(yaml.safe_load((ROOT / "rules.yaml").read_text(encoding="utf-8")))


def _states(site, thresholds) -> list[str]:
    out = []
    for index in range(len(site.times)):
        ok_family, _ = hour_ok_for_phase(site, index, "transit", thresholds, tier="family")
        if ok_family:
            out.append("go")
            continue
        ok_prudent, _ = hour_ok_for_phase(site, index, "transit", thresholds, tier="prudent")
        out.append("prudent" if ok_prudent else "nogo")
    return out


def test_fixture_matches_engine(tmp_path, payload, thresholds):
    spot = tmp_path / "fixture-spot.json"
    spot.write_text(json.dumps(payload), encoding="utf-8")
    site = load_site(spot)
    assert site is not None
    assert _states(site, thresholds) == payload["expected_states"]


def test_fixture_embeds_the_flat_rules(payload):
    """Mobile_view lit meta.rules : la fixture doit porter le schema plat."""
    rules = payload["meta"]["rules"]
    assert rules["wind"]["family_max_kmh"] == 22
    assert rules["tp_matrix"]["transit"]["hs_lt_0_4_family_tp_s"] == 3.0
    assert rules["prudent"]["tp_min_s"] == 3.3


def test_normalized_rules_are_not_readable_by_the_engine():
    """Garde-fou : rules.normalized.json n'a pas le schema attendu par from_rules.

    Le lui passer ferait retomber silencieusement tous les seuils sur les
    valeurs par defaut du code. Ce test documente l'ecart pour qu'un futur
    branchement ne passe pas inapercu.
    """
    normalized = {
        "meta": {"version": 2},
        "family": {"thresholds": {"wind": {"family_max_kmh": 22.0}}},
    }
    flat = yaml.safe_load((ROOT / "rules.yaml").read_text(encoding="utf-8"))
    from_normalized = Thresholds.from_rules(normalized)
    from_flat = Thresholds.from_rules(flat)
    assert from_flat.wind_family_max == 22
    assert from_normalized.wind_family_max != from_flat.wind_family_max
