"""Shared helpers: slugify, nested dict access, deep merge, time parsing."""

from __future__ import annotations

import datetime as dt
import re
import unicodedata
from typing import Any
from zoneinfo import ZoneInfo


def slugify(name: str) -> str:
    """ASCII slug: 'Sidi Bou Saïd' -> 'sidi-bou-said'."""
    s = unicodedata.normalize("NFKD", name)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = s.lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return re.sub(r"-{2,}", "-", s)


def dget(dct: Any, path: str, default: Any = None) -> Any:
    """Nested dict access: dget(rules, 'wind.family_max_kmh', 20)."""
    cur = dct
    for part in path.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return default
        cur = cur[part]
    return cur


def deep_merge(dst: dict, src: dict) -> dict:
    """Recursive merge of src into dst (src wins). Mutates and returns dst."""
    for k, v in src.items():
        if isinstance(v, dict) and isinstance(dst.get(k), dict):
            deep_merge(dst[k], v)
        else:
            dst[k] = v
    return dst


def csv_to_slug_set(s: str) -> set | None:
    if not s:
        return None
    return {slugify(x.strip()) for x in s.split(",") if x.strip()}


def parse_time_local(t_iso: str, tz: ZoneInfo) -> dt.datetime:
    """Parse ISO time; assume local tz when naive."""
    try:
        t = dt.datetime.fromisoformat(t_iso)
    except ValueError:
        t = dt.datetime.fromisoformat(t_iso + ":00")
    return t.replace(tzinfo=tz) if t.tzinfo is None else t.astimezone(tz)


def indices_in_window(times: list[str], start: dt.datetime, end: dt.datetime, tz: ZoneInfo) -> list[int]:
    """Indices of ISO timestamps falling in [start, end)."""
    keep = []
    for i, t_iso in enumerate(times or []):
        if start <= parse_time_local(t_iso, tz) < end:
            keep.append(i)
    return keep


def iso_minutes_tz(x: str | None, tz: ZoneInfo) -> str | None:
    """Normalize an ISO string to tz-aware, minute precision. Pass through unparsable values."""
    if x is None or not isinstance(x, str):
        return None
    try:
        t = dt.datetime.fromisoformat(x)
    except Exception:
        return x
    t = t.replace(tzinfo=tz) if t.tzinfo is None else t.astimezone(tz)
    return t.isoformat(timespec="minutes")


def iter_dates(d0: dt.date, d1: dt.date):
    cur = d0
    while cur <= d1:
        yield cur
        cur += dt.timedelta(days=1)


def angle_in_ranges(angle: float, ranges) -> bool:
    """True if angle (deg) is inside any [a, b] range; supports wrap-around (330..70)."""
    for a, b in ranges:
        if a <= b:
            if a <= angle <= b:
                return True
        elif angle >= a or angle <= b:
            return True
    return False
