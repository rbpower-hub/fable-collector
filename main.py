#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
fable-collector — main.py (compat Reader, TZ-safe)
- Lit sites.yaml (name, lat, lon, shelter_bonus_radius_km)
- Fenêtre contrôlée par env:
    FABLE_TZ, FABLE_WINDOW_HOURS, FABLE_START_ISO, FABLE_ONLY_SITES
- Sources:
    Open-Meteo (ECMWF): vent/rafales/direction/weather_code/visibility (horaire)
    Open-Meteo Marine : wave_height / wave_period (+ swell) (horaire)
- Écrit: public/<slug>.json
  * keys: meta, ecmwf, marine, hourly (APLATI pour reader)
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
                url, headers={"User-Agent": "fable-collector/1.0 (+github actions)"}
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
    """
    Parse ISO provenant d'Open-Meteo.
    Si l'offset est absent (naive), on l'interprète en timezone `tz`.
    """
    try:
        t = dt.datetime.fromisoformat(t_iso)
    except ValueError:
        # parfois il manque les secondes
        t = dt.datetime.fromisoformat(t_iso + ":00")
    if t.tzinfo is None:  # naive -> interprété en local tz
        t = t.replace(tzinfo=tz)
    return t

def within_window(t_iso: str, start: dt.datetime, end: dt.datetime, tz: ZoneInfo) -> bool:
    t = parse_time_local(t_iso, tz)
    return (t >= start) and (t < end)

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
        if start_local.tzinfo is None:
            start_local = start_local.replace(tzinfo=TZ)
        else:
            start_local = start_local.astimezone(TZ)
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
# URLs Open-Meteo
# -----------------------
def build_ecmwf_url(lat: float, lon: float) -> str:
    params = {
        "latitude": f"{lat:.5f}",
        "longitude": f"{lon:.5f}",
        "hourly": "wind_speed_10m,wind_gusts_10m,wind_direction_10m,weather_code,visibility",
        "timezone": TZ_NAME,
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "models": "ecmwf_ifs04",
    }
    return "https://api.open-meteo.com/v1/forecast?" + urlencode(params)

def build_marine_url(lat: float, lon: float) -> str:
    params = {
        "latitude": f"{lat:.5f}",
        "longitude": f"{lon:.5f}",
        "hourly": "wave_height,wave_period,swell_wave_height,swell_wave_period",
        "timezone": TZ_NAME,
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
    }
    return "https://marine-api.open-meteo.com/v1/marine?" + urlencode(params)

def fetch_ecmwf(lat: float, lon: float) -> Dict[str, Any]:
    try:
        return http_get_json(build_ecmwf_url(lat, lon), retry=2, timeout=25)
    except Exception as e:
        log.warning("ECMWF avec 'models' a échoué (%s). Retente sans 'models'.", e)
        params = {
            "latitude": f"{lat:.5f}",
            "longitude": f"{lon:.5f}",
            "hourly": "wind_speed_10m,wind_gusts_10m,wind_direction_10m,weather_code,visibility",
            "timezone": TZ_NAME,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
        }
        return http_get_json("https://api.open-meteo.com/v1/forecast?" + urlencode(params),
                             retry=2, timeout=25)

def fetch_marine(lat: float, lon: float) -> Dict[str, Any]:
    return http_get_json(build_marine_url(lat, lon), retry=2, timeout=25)

def slice_hourly(payload: Dict[str, Any], keys: List[str],
                 window_start: dt.datetime, window_end: dt.datetime) -> Dict[str, Any]:
    h = payload.get("hourly", {})
    times = h.get("time", [])
    out: Dict[str, Any] = {"time": []}
    for k in keys: out[k] = []
    if not times: return out
    for i, t_iso in enumerate(times):
        if within_window(t_iso, window_start, window_end, TZ):
            out["time"].append(t_iso)
            for k in keys:
                arr = h.get(k, [])
                out[k].append(arr[i] if i < len(arr) else None)
    return out

def make_flat_hourly(ecmwf: Dict[str, Any], marine: Dict[str, Any]) -> Dict[str, List]:
    t_e = ecmwf.get("time", []) or []
    t_m = marine.get("time", []) or []
    L = min(len(t_e), len(t_m)) if (t_e and t_m) else max(len(t_e), len(t_m))
    time_arr = (t_e or t_m)[:L]
    def pick(src, key):
        arr = src.get(key, []) or []
        return arr[:L] if len(arr) >= L else (arr + [None]*(L-len(arr)))
    flat = {
        "time": time_arr,
        "wind_speed_10m":    pick(ecmwf, "wind_speed_10m"),
        "wind_gusts_10m":    pick(ecmwf, "wind_gusts_10m"),
        "wind_direction_10m":pick(ecmwf, "wind_direction_10m"),
        "weather_code":      pick(ecmwf, "weather_code"),
        "visibility":        pick(ecmwf, "visibility"),
        "wave_height":       pick(marine, "wave_height"),
        "wave_period":       pick(marine, "wave_period"),
    }
    flat["hs"] = flat["wave_height"]
    flat["tp"] = flat["wave_period"]
    return flat

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
        wx = fetch_ecmwf(lat, lon)
        sea = fetch_marine(lat, lon)
    except Exception as e:
        log.error("Échec de collecte pour %s: %s", name, e); continue

    ecmwf_keys  = ["wind_speed_10m","wind_gusts_10m","wind_direction_10m","weather_code","visibility"]
    marine_keys = ["wave_height","wave_period","swell_wave_height","swell_wave_period"]

    ecmwf_hourly  = slice_hourly(wx,  ecmwf_keys,  start_local, end_local)
    marine_hourly = slice_hourly(sea, marine_keys, start_local, end_local)
    hourly_flat   = make_flat_hourly(ecmwf_hourly, marine_hourly)

    e_units = wx.get("hourly_units", {})
    m_units = sea.get("hourly_units", {})

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
                    "model_hint": "ecmwf_ifs04 (horaire)",
                    "units": e_units,
                },
                "marine_open_meteo": {
                    "endpoint": "https://marine-api.open-meteo.com/v1/marine",
                    "units": m_units,
                },
            },
            "shelter_bonus_radius_km": site.get("shelter_bonus_radius_km", 0.0),
        },
        "ecmwf": ecmwf_hourly,
        "marine": marine_hourly,
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
