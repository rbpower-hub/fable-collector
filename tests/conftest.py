"""Shared fixtures: synthetic Open-Meteo payloads + real recorded spot payload."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def ras_fartass_payload() -> dict:
    return json.loads((FIXTURES / "ras-fartass.json").read_text(encoding="utf-8"))


@pytest.fixture
def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]
