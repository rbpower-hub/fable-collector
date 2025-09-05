#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
fable-collector — main.py (durci: normalisation clés, slicing par indices, télémétrie)
- Lit sites.yaml (name, lat, lon, shelter_bonus_radius_km)
- Fenêtre contrôlée par env:
    FABLE_TZ, FABLE_WINDOW_HOURS, FABLE_START_ISO, FABLE_ONLY_SITES
- Sources:
    Open-Meteo (ECMWF/ICON/GFS avec fallback): vent/rafales/direction/weather_code/visibility (horaire)
    Open-Meteo Marine : wave_height / wave_period (+ swell) (horaire)
- Écrit: public/<slug>.json
  * keys: meta, ecmwf, marine, hourly (aplati pour le reader)
"""

import os, sys, json, time, yaml, random, logging
import datetime as dt
from pathlib import Path
from typing import Dict, Any, List, Optional
from urllib.parse import urlencode
from zoneinfo import ZoneInfo
import urllib.request

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("fable-collector")

# -----------------------
# Helpers
# -----------------------
def slugify(name: str) -> str:
    import unicodedata, re
    s = unicodedata.normalize("NFKD", name)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = s.lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    s = re.sub(r"-{2,}", "-", s)
    return s

def http_get_json(url: str, retry: int = 2, timeout: int = 25) -> Dict[str, Any]:
    last_err = None
    for attempt in range(retry + 1):
        try:
            req = urllib.request.Request(
                url, headers={"User-Agent": "fable-collector/1.3 (+github actions)"}
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                if resp.status != 200:
                    raise RuntimeError(f"HTTP {resp.status}")
                return json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            last_err = e
            sleep_s = 1.2 + attempt * 1.5 + random.random()
            log.warning("GET failed (%s). retry in %.1fs ...", e, sleep_s)
            time.sleep(sleep_s)
    raise RuntimeError(f"GET failed after retries: {last_err}")

def ensure_dir(p: Path): p.mkdir(parents=True, exist_ok=True)

def csv_to_set(s: str) -> Optional[set]:
    if not s: return None
    return {slugify(x.strip()) for x in s.split(",") if x.strip()}

# ——— TZ-safe parsing ———
def parse_time_local(t_iso: str, tz: ZoneInfo) -> dt.datetime:
    """Parse ISO; si offset absent, interprète en timezone `tz`."""
    try:
        t = dt.datetime.fromisoformat(t_iso)
    except ValueError:
        t = dt.datetime.fromisoformat(t_iso + ":00")
    if t.tzinfo is None:
        t = t.replace(tzinfo=tz)
    return t

def indices_in_window(times: List[str], start: dt.datetime, end: dt.datetime, tz: ZoneInfo) -> List[int]:
    keep = []
    for i, t_iso in enumerate(times or []):
        t = parse_time_local(t_iso, tz)
        if start <= t < end:
            keep.append(i)
    return keep

# -----------------------
# Fenêtre & paramètres
# -----------------------
TZ_NAME = os.getenv("FABLE_TZ", "Africa/Tunis")
TZ = ZoneInfo(TZ_NAME)
WINDOW_H = int(os.getenv("FABLE_WINDOW_HOURS", "48"))
START_ISO = os.getenv("FABLE_START_ISO", "").strip()
ONLY = csv_to_set(os.getenv("FABLE_ONLY_SITES", ""))

now_local = dt.datetime.now(TZ).replace(minute=0, second=0, microsecond=0)
if START_ISO:
    try:
        start_local = dt.datetime.fromisoformat(START_ISO)
        start_local = start_local.replace(tzinfo=start_local.tzinfo or TZ).astimezone(TZ)
    except Exception as e:
        log.warning("FABLE_START_ISO invalide (%s). On utilise maintenant local.", e)
        start_local = now_local
else:
    start_local = now_local

end_local = start_local + dt.timedelta(hours=WINDOW_H)
start_date = start_local.date()
end_date = end_local.date()

log.info(
    "Fenêtre locale %s → %s (%dh) TZ=%s",
    start_local.isoformat(),
    end_local.isoformat(),
    WINDOW_H,
    TZ_NAME,
)

# -----------------------
# Charger sites.yaml
# -----------------------
ROOT = Path(__file__).resolve().parent
sites_yaml = ROOT / "sites.yaml"
if not sites_yaml.exists():
    log.error("sites.yaml introuvable à la racine du repo.")
    sys.exit(1)
try:
    sites = yaml.safe_load(sites_yaml.read_text(encoding="utf-8"))
except Exception as e:
    log.error("Impossible de lire sites.yaml: %s", e); sys.exit(1)
if not isinstance(sites, list) or not sites:
    log.error("sites.yaml mal formé ou vide."); sys.exit(1)

selected_sites = []
for s in sites:
    name = s.get("name") or "Site"
    slug = slugify(name)
    if ONLY and slug not in ONLY: continue
    try:
        lat = float(s["lat"]); lon = float(s["lon"])
    except Exception:
        log.warning("Coordonnées invalides pour %s — ignoré.", name); continue
    selected_sites.append({
        "name": name, "slug": slug, "lat": lat, "lon": lon,
        "shelter_bonus_radius_km": float(s.get("shelter_bonus_radius_km", 0.0)),
    })
if not selected_sites:
    log.error("Aucun site sélectionné (filtre FABLE_ONLY_SITES ?)."); sys.exit(1)

# -----------------------
# Open-Meteo keys + synonyms
# -----------------------
ECMWF_KEYS  = ["wind_speed_10m","wind_gusts_10m","wind_direction_10m","weather_code","visibility"]
MARINE_KEYS = ["wave_height","wave_period","swell_wave_height","swell_wave_period"]

KEY_SYNONYMS = {
    "wind_speed_10m":     ["wind_speed_10m", "windspeed_10m"],
    "wind_gusts_10m":     ["wind_gusts_10m", "windgusts_10m"],
    "wind_direction_10m": ["wind_direction_10m", "winddirection_10m"],
    "weather_code":       ["weather_code", "weathercode"],
    "visibility":         ["visibility"],
    "wave_height":        ["wave_height", "significant_wave_height"],
    "wave_period":        ["wave_period", "waveperiod"],
    "swell_wave_height":  ["swell_wave_height"],
    "swell_wave_period":  ["swell_wave_period"],
}

def first_series(h: Dict[str, Any], canonical_key: str) -> List:
    for cand in KEY_SYNONYMS.get(canonical_key, [canonical_key]):
        arr = h.get(cand)
        if isinstance(arr, list) and len(arr) > 0:
            return arr
    return []

def normalize_hourly_keys(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Copie les séries existantes sous les noms canoniques."""
    h = (payload.get("hourly") or {}).copy()
    normalized = dict(h)  # shallow copy
    for canonical, syns in KEY_SYNONYMS.items():
        if isinstance(normalized.get(canonical), list) and normalized.get(canonical):
            continue
        for cand in syns:
            arr = h.get(cand)
            if isinstance(arr, list) and arr:
                normalized[canonical] = arr
                break
    payload["hourly"] = normalized
    return payload

# -----------------------
# URLs Open-Meteo
# -----------------------
def forecast_url(lat: float, lon: float, model: Optional[str]) -> str:
    params = {
        "latitude": f"{lat:.5f}",
        "longitude": f"{lon:.5f}",
        "hourly": ",".join(ECMWF_KEYS),  # on demande les canoniques
        "timezone": TZ_NAME,
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
    }
    if model:
        params["models"] = model
    return "https://api.open-meteo.com/v1/forecast?" + urlencode(params)

def marine_url(lat: float, lon: float) -> str:
    params = {
        "latitude": f"{lat:.5f}",
        "longitude": f"{lon:.5f}",
        "hourly": ",".join(MARINE_KEYS),
        "timezone": TZ_NAME,
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
    }
    return "https://marine-api.open-meteo.com/v1/marine?" + urlencode(params)

def _has_non_null(arr: List) -> bool:
    return isinstance(arr, list) and any(v is not None for v in arr)

def has_wind_arrays(payload: Dict[str, Any]) -> bool:
    h = payload.get("hourly") or {}
    return _has_non_null(first_series(h, "wind_speed_10m")) and _has_non_null(first_series(h, "wind_gusts_10m"))

def fetch_forecast(lat: float, lon: float) -> Dict[str, Any]:
    """Essaie successivement: ECMWF -> ICON -> GFS -> défaut (sans models), en refusant les séries tout-NULL."""
    for model in ["ecmwf_ifs04", "icon_seamless", "gfs_seamless", None]:
        url = forecast_url(lat, lon, model)
        try:
            p = http_get_json(url, retry=2, timeout=25)
            p = normalize_hourly_keys(p)
            if has_wind_arrays(p):
                p["_model_used"] = model or "default"
                log.info("  ✔ forecast model used: %s", p["_model_used"])
                return p
            else:
                log.warning("  ⚠ model %s returned only NULL series, trying next...", model or "default")
        except Exception as e:
            log.warning("  ⚠ request failed for model %s: %s", model or "default", e)
    return {"_model_used": "unknown", "hourly": {}}

def fetch_marine(lat: float, lon: float) -> Dict[str, Any]:
    p = http_get_json(marine_url(lat, lon), retry=2, timeout=25)
    return normalize_hourly_keys(p)

def slice_by_indices(payload: Dict[str, Any], keys: List[str],
                     keep_idx: List[int]) -> Dict[str, Any]:
    h = payload.get("hourly") or {}
    times = h.get("time") or []
    out: Dict[str, Any] = {}
    out["time"] = [times[i] for i in keep_idx if i < len(times)]
    for k in keys:
        series = first_series(h, k)
        if series:
            out[k] = [series[i] for i in keep_idx if i < len(series)]
    return out

def flatten_hourly(ecmwf_slice: Dict[str, Any], marine_slice: Dict[str, Any]) -> Dict[str, List]:
    t = ecmwf_slice.get("time") or marine_slice.get("time") or []
    L = len(t)
    def pick(src: Dict[str, Any], key: str) -> List:
        arr = src.get(key) or []
        return arr if len(arr) == L else (arr + [None]*(L - len(arr)))
    flat = {"time": t}
    for k in ["wind_speed_10m","wind_gusts_10m","wind_direction_10m","weather_code","visibility"]:
        if k in ecmwf_slice:
            flat[k] = pick(ecmwf_slice, k)
    for k in ["wave_height","wave_period"]:
        if k in marine_slice:
            flat[k] = pick(marine_slice, k)
    if "wave_height" in flat: flat["hs"] = flat["wave_height"]
    if "wave_period" in flat: flat["tp"] = flat["wave_period"]
    return flat

def non_null_count(d: Dict[str, Any], keys: List[str]) -> Dict[str, int]:
    out = {}
    for k in keys:
        arr = d.get(k) or []
        out[k] = sum(1 for x in arr if x is not None)
    return out

# -----------------------
# Collecte
# -----------------------
PUBLIC = ROOT / "public"
ensure_dir(PUBLIC)

results = []

for site in selected_sites:
    name = site["name"]; slug = site["slug"]; lat = site["lat"]; lon = site["lon"]
    log.info("▶ Collecte: %s (%.5f, %.5f)", name, lat, lon)

    try:
        wx = fetch_forecast(lat, lon)   # <— Fallback ECMWF→ICON→GFS
        sea = fetch_marine(lat, lon)
    except Exception as e:
        log.error("Échec de collecte pour %s: %s", name, e)
        continue

    # --- DEBUG dumps lisibles à l’œil nu ---
    if os.getenv("FABLE_DEBUG_DUMP", "0") == "1":
        (PUBLIC / f"_debug-forecast-{slug}.json").write_text(
            json.dumps(wx, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        (PUBLIC / f"_debug-marine-{slug}.json").write_text(
            json.dumps(sea, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    # indices dans la fenêtre
    all_times = (wx.get("hourly") or {}).get("time") or (sea.get("hourly") or {}).get("time") or []
    keep = indices_in_window(all_times, start_local, end_local, TZ)

    ecmwf_slice  = slice_by_indices(wx,  ECMWF_KEYS,  keep)
    marine_slice = slice_by_indices(sea, MARINE_KEYS, keep)
    hourly_flat  = flatten_hourly(ecmwf_slice, marine_slice)

    e_units = wx.get("hourly_units", {})
    m_units = sea.get("hourly_units", {})

    # Debug meta: clés présentes + compte non-nulls
    wx_keys_raw  = sorted(list((wx.get("hourly") or {}).keys()))
    sea_keys_raw = sorted(list((sea.get("hourly") or {}).keys()))
    nn_ecmwf = non_null_count(ecmwf_slice, ["wind_speed_10m","wind_gusts_10m","wind_direction_10m","weather_code","visibility"])
    nn_marine = non_null_count(marine_slice, ["wave_height","wave_period","swell_wave_height","swell_wave_period"])

    out: Dict[str, Any] = {
        "meta": {
            "name": name, "slug": slug, "lat": lat, "lon": lon, "tz": TZ_NAME,
            "generated_at": dt.datetime.now(TZ).isoformat(),
            "window": {
                "start_local": start_local.isoformat(),
                "end_local":   end_local.isoformat(),
                "hours": int((end_local - start_local).total_seconds() // 3600),
            },
            "sources": {
                "ecmwf_open_meteo": {
                    "endpoint": "https://api.open-meteo.com/v1/forecast",
                    "model_hint": "ecmwf_ifs04/icon/gfs (horaire, fallback)",
                    "model_used": wx.get("_model_used", "unknown"),
                    "units": e_units,
                },
                "marine_open_meteo": {
                    "endpoint": "https://marine-api.open-meteo.com/v1/marine",
                    "units": m_units,
                },
            },
            "shelter_bonus_radius_km": site.get("shelter_bonus_radius_km", 0.0),
            "debug": {
                "hourly_keys_present_forecast": wx_keys_raw,
                "hourly_keys_present_marine": sea_keys_raw,
                "ecmwf_non_null_counts": nn_ecmwf,
                "marine_non_null_counts": nn_marine,
                "kept_indices": keep[:6] + (["..."] if len(keep) > 6 else []),
            },
        },
        "ecmwf": ecmwf_slice,
        "marine": marine_slice,
        "hourly": hourly_flat,
        "status": "ok",
    }

    tmp = PUBLIC / f".{slug}.json.tmp"
    final = PUBLIC / f"{slug}.json"
    tmp.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    tmp.replace(final)

    results.append({"slug": slug, "points": len(hourly_flat.get("time", []))})

ok = [r for r in results if r["points"] > 0]
log.info("Terminé: %d/%d spots écrits (avec données horaires dans la fenêtre).", len(ok), len(selected_sites))
if not ok:
    log.error("Aucune donnée horaire dans la fenêtre demandée — vérifier paramètres/timezone.")
    sys.exit(2)
