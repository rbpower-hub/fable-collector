from __future__ import annotations
import os, sys, re
from datetime import timedelta
from zoneinfo import ZoneInfo, available_timezones

MODEL_ALIASES = {
    "default": ["ecmwf_ifs04", "icon_seamless", "gfs_seamless"],
    "fast":    ["gfs_seamless", "icon_seamless"],
    "robust":  ["ecmwf_ifs04", "icon_seamless", "gfs_seamless"],
}

VALID_MODELS = {"ecmwf_ifs04","icon_seamless","gfs_seamless"}

def _get(name: str, default: str | None = None) -> str | None:
    v = os.getenv(name, default)
    return v if v is None or (isinstance(v, str) and v.strip() != "") else default

def _fail(msg: str):
    print(f"[ENV] {msg}", file=sys.stderr)
    raise SystemExit(3)

def _parse_int(name: str, default: int | None = None, minv: int | None = None, maxv: int | None = None) -> int | None:
    v = _get(name)
    if v is None:
        return default
    try:
        n = int(v)
    except ValueError:
        _fail(f"{name} must be an integer, got {v!r}")
    if minv is not None and n < minv:
        _fail(f"{name} must be ≥ {minv}, got {n}")
    if maxv is not None and n > maxv:
        _fail(f"{name} must be ≤ {maxv}, got {n}")
    return n

def _parse_tz(name: str, default: str | None = None) -> ZoneInfo | None:
    tz = _get(name, default)
    if tz is None: 
        return None
    if tz not in available_timezones():
        _fail(f"{name} must be a valid IANA timezone (e.g., Africa/Tunis), got {tz!r}")
    return ZoneInfo(tz)

def _parse_models(name: str, default: str | None = None) -> list[str] | None:
    raw = _get(name, default)
    if raw is None:
        return None
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    expanded: list[str] = []
    for p in parts:
        if p in MODEL_ALIASES:
            expanded += MODEL_ALIASES[p]
        else:
            expanded.append(p)
    # de-dupe preserving order, validate
    seen, out = set(), []
    for m in expanded:
        if m not in seen:
            seen.add(m)
            out.append(m)
    unknown = [m for m in out if m not in VALID_MODELS]
    if unknown:
        _fail(f"FABLE_MODELS contains unknown models: {unknown}; valid={sorted(VALID_MODELS)} or aliases={sorted(MODEL_ALIASES)}")
    return out

def validate_env():
    # Window hours
    win = _parse_int("FABLE_WINDOW_HOURS", minv=1, maxv=72)
    if win is not None and win % 1 != 0:
        _fail("FABLE_WINDOW_HOURS must be an integer number of hours")
    # Concurrency limits
    _ = _parse_int("FABLE_PARALLEL_MODELS", minv=1, maxv=8)
    _ = _parse_int("FABLE_PARALLEL_SITES",  minv=1, maxv=64)
    # Timezone
    _ = _parse_tz("FABLE_TZ", "Africa/Tunis")
    # Start ISO (if present) basic sanity
    start_iso = _get("FABLE_START_ISO")
    if start_iso and not re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}", start_iso):
        _fail("FABLE_START_ISO must start like YYYY-MM-DDTHH:MM (timezone optional)")
    # Models (optional; only if user sets)
    models = _parse_models("FABLE_MODELS")  # e.g., "default" or "ecmwf_ifs04,icon_seamless"
    if models:
        print(f"[ENV] Model order: {models}")
    print("[ENV] OK")

if __name__ == "__main__":
    validate_env()
