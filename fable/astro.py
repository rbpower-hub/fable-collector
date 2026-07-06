"""Daily astronomy (sunrise/sunset/moon) backfill.

Order of preference:
1. daily block already present in the forecast payload,
2. /v1/forecast daily-only call (sunrise/sunset),
3. /v1/astronomy HTTP (optional, disabled by default via rules http.disable_astronomy_http),
4. offline Astral computation (moonrise/moonset/moon_phase).
"""

from __future__ import annotations

import datetime as dt
import logging
from typing import Any
from zoneinfo import ZoneInfo

from .openmeteo import Getter, astronomy_url, daily_only_url
from .util import iso_minutes_tz, iter_dates

log = logging.getLogger("fable.astro")

try:
    from astral import Observer
    from astral.moon import moonrise as _moonrise
    from astral.moon import moonset as _moonset
    from astral.moon import phase as _phase
except Exception:  # pragma: no cover - depends on env
    Observer = None
    _moonrise = _moonset = _phase = None

ASTRO_KEYS = ("sunrise", "sunset", "moonrise", "moonset", "moon_phase")
MOON_KEYS = ("moonrise", "moonset", "moon_phase")


def astral_available() -> bool:
    return Observer is not None and _moonrise is not None


def _non_empty(arr: Any) -> bool:
    return isinstance(arr, list) and any(v is not None for v in arr)


def needs_daily_backfill(p: dict[str, Any]) -> bool:
    d = p.get("daily") or {}
    return any(not _non_empty(d.get(k)) for k in ASTRO_KEYS)


def merge_daily(dst: dict[str, Any], src: dict[str, Any]) -> None:
    """Merge src['daily'] into dst['daily'], aligned on dst's time axis,
    filling only holes (never overwriting non-null values)."""
    s_daily = src.get("daily") or {}
    if not isinstance(s_daily, dict):
        return
    dst.setdefault("daily", {})
    dst.setdefault("daily_units", {})

    ref_time = dst["daily"].get("time") or s_daily.get("time") or []
    if ref_time and dst["daily"].get("time") != ref_time:
        dst["daily"]["time"] = ref_time
    idx_src = {t: i for i, t in enumerate(s_daily.get("time") or [])}

    for k, arr in s_daily.items():
        if k == "time" or not isinstance(arr, list):
            continue
        if s_daily.get("time") and ref_time and s_daily["time"] != ref_time:
            new_arr = [arr[i] if (i := idx_src.get(t)) is not None and i < len(arr) else None for t in ref_time]
        else:
            new_arr = list(arr)

        cur = dst["daily"].get(k)
        if not isinstance(cur, list) or not cur:
            dst["daily"][k] = new_arr
            continue
        cur = list(cur)
        n = len(ref_time) or max(len(cur), len(new_arr))
        cur += [None] * (n - len(cur))
        new_arr += [None] * (n - len(new_arr))
        for i in range(n):
            if cur[i] is None and new_arr[i] is not None:
                cur[i] = new_arr[i]
        dst["daily"][k] = cur[:n] if ref_time else cur

    for uk, uv in (src.get("daily_units") or {}).items():
        dst["daily_units"].setdefault(uk, uv)
    if "time" not in dst["daily"] and isinstance(s_daily.get("time"), list):
        dst["daily"]["time"] = s_daily["time"]


def astral_backfill(p: dict[str, Any], lat: float, lon: float, tz: ZoneInfo,
                    start: dt.date, end: dt.date) -> None:
    """Offline moonrise/moonset/moon_phase via Astral."""
    if not astral_available():
        log.info("astral not available — skipping offline backfill")
        return
    p.setdefault("daily", {})
    p.setdefault("daily_units", {})

    ref_dates = p["daily"].get("time")
    if not isinstance(ref_dates, list) or not ref_dates:
        ref_dates = [d.isoformat() for d in iter_dates(start, end)]
        p["daily"]["time"] = ref_dates

    observer = Observer(latitude=lat, longitude=lon)

    def fmt_local(v: dt.datetime | None) -> str | None:
        if not isinstance(v, dt.datetime):
            return None
        return v.astimezone(tz).replace(tzinfo=None).isoformat(timespec="minutes")

    mr_arr, ms_arr, ph_arr = [], [], []
    for ds in ref_dates:
        try:
            d = dt.date.fromisoformat(str(ds)[:10])
        except Exception:
            mr_arr.append(None); ms_arr.append(None); ph_arr.append(None)
            continue
        try:
            mr = _moonrise(observer, d, tzinfo=tz)
        except Exception:
            mr = None
        try:
            ms = _moonset(observer, d, tzinfo=tz)
        except Exception:
            ms = None
        try:
            ph_frac = round(float(_phase(d)) / 29.530588, 3)
        except Exception:
            ph_frac = None
        mr_arr.append(fmt_local(mr)); ms_arr.append(fmt_local(ms)); ph_arr.append(ph_frac)

    merge_daily(p, {"daily": {"time": ref_dates, "moonrise": mr_arr, "moonset": ms_arr, "moon_phase": ph_arr}})
    p["daily_units"].setdefault("moonrise", "iso8601")
    p["daily_units"].setdefault("moonset", "iso8601")
    p["daily_units"].setdefault("moon_phase", "fraction")
    log.info("daily backfill: astral attached")


def normalize_daily_tz(p: dict[str, Any], tz: ZoneInfo) -> None:
    d = p.get("daily") or {}
    for key in ("sunrise", "sunset", "moonrise", "moonset"):
        arr = d.get(key)
        if isinstance(arr, list) and arr:
            d[key] = [iso_minutes_tz(v, tz) for v in arr]
    p["daily"] = d


def attach_daily_best_effort(p: dict[str, Any], lat: float, lon: float, tz: ZoneInfo, tz_name: str,
                             start: dt.date, end: dt.date, getter: Getter,
                             disable_astronomy_http: bool = True,
                             use_astral: bool = True) -> None:
    """Fill p['daily'] with sunrise/sunset (+moon data) — see module docstring."""
    p.setdefault("daily", {})
    p.setdefault("daily_units", {})

    have_sun = _non_empty(p["daily"].get("sunrise")) and _non_empty(p["daily"].get("sunset"))
    have_moon = all(_non_empty(p["daily"].get(k)) for k in MOON_KEYS)

    if not have_sun:
        try:
            dd = getter(daily_only_url(lat, lon, tz_name, start, end))
            if isinstance(dd, dict) and dd.get("daily"):
                merge_daily(p, dd)
                have_sun = _non_empty(p["daily"].get("sunrise")) and _non_empty(p["daily"].get("sunset"))
        except Exception as e:  # noqa: BLE001
            log.debug("daily backfill (forecast) failed: %s", e)

    if not have_moon and not disable_astronomy_http:
        for tf in (True, False):  # some edges 404 with timeformat
            try:
                aa = getter(astronomy_url(lat, lon, tz_name, start, end, timeformat=tf))
                if isinstance(aa, dict) and aa.get("daily"):
                    merge_daily(p, aa)
                    have_moon = all(_non_empty(p["daily"].get(k)) for k in MOON_KEYS)
                    if have_moon:
                        break
            except Exception as e:  # noqa: BLE001
                log.debug("daily backfill (astronomy tf=%s) failed: %s", tf, e)

    if not have_moon and use_astral:
        try:
            astral_backfill(p, lat, lon, tz, start, end)
        except Exception as e:  # noqa: BLE001
            log.debug("daily backfill (astral) failed: %s", e)

    try:
        normalize_daily_tz(p, tz)
    except Exception:  # noqa: BLE001
        pass

    p["daily"].setdefault("time", p["daily"].get("time", []))
    for k in ASTRO_KEYS:
        p["daily"].setdefault(k, [])
    p["daily_units"].setdefault("sunrise", "iso8601")
    p["daily_units"].setdefault("sunset", "iso8601")
    p["daily_units"].setdefault("moonrise", "iso8601")
    p["daily_units"].setdefault("moonset", "iso8601")
    p["daily_units"].setdefault("moon_phase", "fraction")
