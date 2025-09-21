# shared.py
from typing import Iterable

DEFAULT_NON_SPOT_JSON = {
    "index.json",
    "index.spots.json",
    "catalog.json",
    "status.json",
    "rules.normalized.json",
    "windows.json",
    "windows.collector.json",
}

def _dget(dct, path, default=None):
    cur = dct or {}
    for part in path.split('.'):
        if not isinstance(cur, dict) or part not in cur:
            return default
        cur = cur[part]
    return cur

def get_non_spot_json(rules: dict | None = None) -> set[str]:
    # Allow optional extension/override from rules.yaml at artifacts.non_spot_json
    extra: Iterable[str] = _dget(rules, "artifacts.non_spot_json", []) or []
    # normalize to strings and ensure .json basenames only
    cleaned = {str(x).strip() for x in extra if str(x).strip().endswith(".json")}
    # union with safe defaults
    return set(DEFAULT_NON_SPOT_JSON) | cleaned
