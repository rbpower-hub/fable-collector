"""External healthcheck: validates the LIVE GitHub Pages deployment.

Run from healthcheck.yml on a schedule; independent from the build (that is
the whole point: it detects a pipeline that stopped running). Self-describing:
the expected spot list is read from the live sites.normalized.json.
"""

from __future__ import annotations

import datetime as dt
import json
import sys
import urllib.request
from typing import Any

from . import USER_AGENT
from .util import enable_utf8_stdio

DEFAULT_BASE = "https://rbpower-hub.github.io/fable-collector"
MAX_AGE_MIN = 95           # hourly cadence + leeway
SCHEDULE_MIN_INTERVAL_MIN = 50
MIN_HOURLY_POINTS = 24


def _get(url: str, timeout: int = 20) -> Any:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Cache-Control": "no-cache"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def status_age_minutes(status: dict[str, Any], now: dt.datetime | None = None) -> float:
    gen = dt.datetime.fromisoformat(str(status["generated_at"]))
    current = now or dt.datetime.now(gen.tzinfo or dt.timezone.utc)
    return (current - gen).total_seconds() / 60.0


def live_status_age_minutes(base_url: str = DEFAULT_BASE, now: dt.datetime | None = None) -> float:
    base = base_url.rstrip("/")
    status: dict[str, Any] = _get(f"{base}/status.json")
    return status_age_minutes(status, now=now)


def should_collect_live(
    base_url: str = DEFAULT_BASE,
    min_interval_min: int = SCHEDULE_MIN_INTERVAL_MIN,
    now: dt.datetime | None = None,
) -> tuple[bool, str]:
    try:
        age_min = live_status_age_minutes(base_url, now=now)
    except Exception as e:  # noqa: BLE001
        return True, f"live status unreadable ({e}); forcing refresh"

    if age_min >= min_interval_min:
        return True, f"live status is {age_min:.0f} min old (threshold {min_interval_min})"
    return False, f"live status is {age_min:.0f} min old (threshold {min_interval_min})"


def check_live(base_url: str = DEFAULT_BASE, max_age_min: int = MAX_AGE_MIN,
               now: dt.datetime | None = None) -> list[str]:
    """Return list of problems (empty = healthy)."""
    problems: list[str] = []
    base = base_url.rstrip("/")

    # 1) status.json freshness
    try:
        status: dict[str, Any] = _get(f"{base}/status.json")
        age_min = status_age_minutes(status, now=now)
        if age_min > max_age_min:
            problems.append(f"status.json is stale: {age_min:.0f} min old (max {max_age_min})")
    except Exception as e:  # noqa: BLE001
        problems.append(f"status.json unreachable/unparsable: {e}")
        status = {}

    # 2) expected spots from live sites.normalized.json (fallback: status expected_spots)
    expected: list[str] = []
    try:
        sn = _get(f"{base}/sites.normalized.json")
        expected = [s["path"] for s in sn.get("sites", [])]
    except Exception:  # noqa: BLE001
        expected = list(status.get("expected_spots") or [])
    if not expected:
        problems.append("cannot determine expected spot list (sites.normalized.json missing)")

    # 3) each spot: fresh index + enough hourly points
    for spot in expected:
        try:
            d = _get(f"{base}/{spot}")
            pts = len((d.get("hourly") or {}).get("time") or [])
            if pts < MIN_HOURLY_POINTS:
                problems.append(f"{spot}: only {pts} hourly points (<{MIN_HOURLY_POINTS})")
        except Exception as e:  # noqa: BLE001
            problems.append(f"{spot}: unreachable/unparsable: {e}")

    # 4) windows.json sane
    try:
        w = _get(f"{base}/windows.json")
        if "windows" not in w:
            problems.append("windows.json: missing 'windows' key")
        else:
            names = {x.get("dest_slug", "") for x in w["windows"]}
            for bad in ("catalog.json", "rules.normalized.json", "sites.normalized.json"):
                if bad in names:
                    problems.append(f"windows.json polluted by non-spot destination: {bad}")
    except Exception as e:  # noqa: BLE001
        problems.append(f"windows.json unreachable/unparsable: {e}")

    return problems


def main() -> int:
    base = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_BASE
    problems = check_live(base)
    if problems:
        print("❌ HEALTHCHECK FAILED")
        for p in problems:
            print(f"  - {p}")
        return 1
    print("✅ healthcheck OK — live deployment fresh and complete")
    return 0


if __name__ == "__main__":
    enable_utf8_stdio()
    sys.exit(main())
