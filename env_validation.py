# env_validation.py (replace validate_env and helpers as shown)

from __future__ import annotations
import os, sys, re
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

def _maybe_int(name: str, minv: int | None = None, maxv: int | None = None) -> int | None:
    v = _get(name)
    if v is None:
        return None
    if re.fullmatch(r"\d+", v.strip()):
        return _parse_int(name, minv=minv, maxv=maxv)
    return None  # not purely numeric → treat as something else

def _parse_tz(name: str, default: str | None = None) -> ZoneInfo | None:
    tz = _get(name, default)
    if tz is None:
        return None
    if tz not in available_timezones():
        _fail(f"{name} must be a valid IANA timezone (e.g., Africa/Tunis), got {tz!r}")
    return ZoneInfo(tz)

def _expand_models(raw_csv: str) -> list[str]:
    parts = [p.strip() for p in raw_csv.split(",") if p.strip()]
    expanded: list[str] = []
    for p in parts:
        expanded += MODEL_ALIASES.get(p, [p])
    # de-dupe preserving order, validate
    out, seen = [], set()
    for m in expanded:
        if m not in seen:
            seen.add(m)
            out.append(m)
    unknown = [m for m in out if m not in VALID_MODELS]
    if unknown:
        _fail(f"Unknown model(s): {unknown}; valid={sorted(VALID_MODELS)}; aliases={sorted(MODEL_ALIASES)}")
    return out

def _detect_models() -> tuple[list[str], str]:
    """
    Priority:
      1) FABLE_MODEL_ORDER (exported from rules.yaml in your workflow)
      2) FABLE_MODELS
      3) FABLE_PARALLEL_MODELS if it looks like a list (contains comma or letters)
      4) fallback to alias 'default'
    Returns (models, source_env_name)
    """
    for env_name in ("FABLE_MODEL_ORDER", "FABLE_MODELS", "FABLE_PARALLEL_MODELS"):
        raw = _get(env_name)
        if not raw:
            continue
        if env_name == "FABLE_PARALLEL_MODELS" and re.fullmatch(r"\d+", raw.strip()):
            # here it's being used as a numeric concurrency; skip as model list
            continue
        if env_name == "FABLE_PARALLEL_MODELS":
            print("[ENV] Detected legacy use of FABLE_PARALLEL_MODELS as a model list; supported for compatibility.")
        return _expand_models(raw), env_name
    return _expand_models("default"), "alias:default"

def validate_env():
    # Window horizon
    _ = _parse_int("FABLE_WINDOW_HOURS", minv=1, maxv=72)

    # Timezone
    _ = _parse_tz("FABLE_TZ", "Africa/Tunis")

    # Models (order)
    models, src = _detect_models()
    print(f"[ENV] Model order ({src}): {models}")

    # Concurrency knobs
    # If FABLE_PARALLEL_MODELS is numeric → treat as concurrency value (in addition to any model list above)
    pm_conc = _maybe_int("FABLE_PARALLEL_MODELS", minv=1, maxv=8)
    if pm_conc is not None:
        print(f"[ENV] Parallel model concurrency: {pm_conc}")
    else:
        print("[ENV] Parallel model concurrency: (not set)")

    _ = _parse_int("FABLE_PARALLEL_SITES",  minv=1, maxv=64) if _get("FABLE_PARALLEL_SITES") else None

    # Start ISO (if provided)
    start_iso = _get("FABLE_START_ISO")
    if start_iso and not re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}", start_iso):
        _fail("FABLE_START_ISO must start like YYYY-MM-DDTHH:MM (timezone optional)")

    print("[ENV] OK")

if __name__ == "__main__":
    validate_env()
