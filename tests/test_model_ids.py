"""Guard against wind-model IDs that Open-Meteo no longer serves.

Context (audit 2026-10-02): `ecmwf_ifs04` returned all-null series on every
production run (`no_wind_arrays`), so ECMWF was silently missing and FABLE ran
on two wind models instead of three.
"""

from pathlib import Path

import pytest
import yaml

from fable.collect import Settings
from fable.config import DEFAULT_RULES
from fable.openmeteo import MODEL_ALIASES, RETIRED_MODEL_IDS, expand_models

ROOT = Path(__file__).resolve().parents[1]


def _csv(value: str) -> list[str]:
    return [item.strip() for item in str(value).split(",") if item.strip()]


def _workflow_parallel_models() -> list[str]:
    workflow = yaml.safe_load((ROOT / ".github/workflows/collect.yml").read_text(encoding="utf-8"))
    for step in workflow["jobs"]["build"]["steps"]:
        value = (step.get("env") or {}).get("FABLE_PARALLEL_MODELS")
        if value:
            return _csv(value)
    raise AssertionError("collect.yml no longer sets FABLE_PARALLEL_MODELS")


def _configured_wind_model_lists(monkeypatch) -> dict[str, list[str]]:
    monkeypatch.delenv("FABLE_MODEL_ORDER", raising=False)
    monkeypatch.delenv("FABLE_PARALLEL_MODELS", raising=False)
    rules = yaml.safe_load((ROOT / "rules.yaml").read_text(encoding="utf-8"))
    defaults = Settings()
    return {
        "rules.yaml http.model_order": _csv(rules["http"]["model_order"]),
        "config.DEFAULT_RULES http.model_order": _csv(DEFAULT_RULES["http"]["model_order"]),
        "Settings.model_order default": defaults.model_order,
        "Settings.parallel_models default": defaults.parallel_models,
        "collect.yml FABLE_PARALLEL_MODELS": _workflow_parallel_models(),
    }


def test_no_retired_wind_model_is_configured(monkeypatch):
    for source, models in _configured_wind_model_lists(monkeypatch).items():
        retired = [model for model in models if model in RETIRED_MODEL_IDS]
        assert not retired, f"{source} still lists retired model(s) {retired}"


def test_every_configured_wind_model_is_known(monkeypatch):
    for source, models in _configured_wind_model_lists(monkeypatch).items():
        unknown = [model for model in models if model not in MODEL_ALIASES]
        assert not unknown, f"{source} lists model(s) unknown to MODEL_ALIASES: {unknown}"


def test_ecmwf_ifs025_is_both_primary_fallback_and_parallel_source(monkeypatch):
    lists = _configured_wind_model_lists(monkeypatch)
    assert "ecmwf_ifs025" in lists["rules.yaml http.model_order"]
    assert "ecmwf_ifs025" in lists["collect.yml FABLE_PARALLEL_MODELS"]


@pytest.mark.parametrize("legacy", sorted(RETIRED_MODEL_IDS))
def test_legacy_names_resolve_to_their_replacement(legacy):
    assert expand_models([legacy]) == [RETIRED_MODEL_IDS[legacy]]


def test_legacy_and_current_names_are_not_requested_twice():
    assert expand_models(["ecmwf_ifs04", "ecmwf_ifs025", "icon_seamless"]) == ["ecmwf_ifs025", "icon_seamless"]
