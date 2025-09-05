#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
fable-collector — main.py (robuste, avec fallback de modèles)
- Lit sites.yaml (name, lat, lon, shelter_bonus_radius_km)
- Fenêtre via env:
    FABLE_TZ, FABLE_WINDOW_HOURS, FABLE_START_ISO (optionnel), FABLE_ONLY_SITES (CSV)
- Sources:
    Open-Meteo forecast (ECMWF/ICON/GFS/fallback) : vent/rafales/direction/weather_code/visibility (horaire)
    Open-Meteo Marine                              : wave_height / wave_period (+ swell) (horaire)
- Sortie: public/<slug>.json (clés "ecmwf" et "marine", + doublon sous "hourly")
"""

from __future__ import annotations
import os, sys, json, time, random, logging, datetime as dt
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from urllib.parse import urlencode
from zoneinfo import ZoneInfo
import urllib.request, urllib.error
import yaml

# -----------------------
# Logging
# -----------------------
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("fable-collector")

# -----------------------
# Constantes
# -----------------------
ECMWF_KEYS = [
    "wind_speed_10m",
    "wind_gusts_10m",
    "wind_direction_10m",
    "weather_code",
    "visibility",
]
MARINE_KEYS = [
    "wave_height",
    "wave_period",
    "swell_wave_height",
    "swell_wave_period",
]

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

def ensure_dir(p: Path):
    p.mkdir(parents=True, exist_ok=True)

def http_get_json(url: str, retry: int = 2, timeout: int = 25) -> Dict[str, Any]:
    last_err = None
    for attempt in range(retry + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "fable-collector/1.1 (+github actions)"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                if resp.status != 200:
                    raise RuntimeError(f"HTTP {resp.status}")
                return json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            last_err = e
            sleep_s = 1.2 + attempt * 1.5 + random.random()
            log.warning("GET %s failed (%s). Retry in %.1fs...", url.split("?")[0], e, sleep_s)
            time.sleep(sleep_s)
    raise RuntimeError(f"GET failed after retries: {last_err}")

def parse_iso_local_guess(s: str, tz: ZoneInfo) -> dt.datetime:
    """Open-Meteo renvoie souvent 'YYYY-MM-DDTHH:MM' (naïf) quand timezone=... est passé.
    On interprète alors ces timestamps comme en 'tz' (Africa/Tunis)."""
    t = dt.datetime.fromisoformat(s)
    if t.tzinfo is None:
        t = t.replace(tzinfo=tz)
    return t

def within_window(t_iso: str, start: dt.datetime, end: dt.datetime, tz: ZoneInfo) -> bool:
    t = parse_iso_local_guess(t_iso, tz)
    return (t >= start) and (t < end)

def csv_to_set(s: str) -> Optional[set]:
    if not s:
        return None
    return {slugify(x.strip()) for x in s.split(",") if x.strip()}

def arrays_ok(hourly: Dict[str, Any], needed: List[str]) -> Tuple[bool, List[str]]:
    """Vérifie que toutes les clés existent et que leur longueur == len(time)."""
    times = hourly.get("time") or []
    missing: List[str] = []
    if not times:
        return False, needed[:]  # rien
    n = len(times)
    for k in needed:
        arr = hourly.get(k)
        if not isinstance(arr, list) or len(arr) != n:
            missing.append(k)
    return len(missing) == 0, missing

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

log.info("Fenêtre locale %s → %s (%dh) TZ=%s",
         start_local.isoformat(), end_local.isoformat(), WINDOW_H, TZ_NAME)

# -----------------------
# Charger sites.yaml
# -----------------------
ROOT = Path(__file__).resolve().parent
PUBLIC = ROOT / "public"
ensure_dir(PUBLIC)

sites_yaml = ROOT / "sites.yaml"
if not sites_yaml.exists():
    log.error("sites.yaml introuvable à la racine du repo.")
    sys.exit(1)

try:
    sites = yaml.safe_load(sites_yaml.read_text(encoding="utf-8"))
except Exception as e:
    log.error("Impossible de lire sites.yaml: %s", e)
    sys.exit(1)

if not isinstance(sites, list) or not sites:
    log.error("sites.yaml mal formé ou vide.")
    sys.exit(1)

selected_sites = []
for s in sites:
    name = s.get("name") or "Site"
    slug = slugify(name)
    if ONLY and slug not in ONLY and slugify(name) not in ONLY:
        continue
    try:
        lat = float(s["lat"]); lon = float(s["lon"])
    except Exception:
        log.warning("Coordonnées invalides pour %s — ignoré.", name)
        continue
    selected_sites.append({
        "name": name,
        "slug": slug,
        "lat": lat,
        "lon": lon,
        "shelter_bonus_radius_km": float(s.get("shelter_bonus_radius_km", 0.0)),
    })

if not selected_sites:
    log.error("Aucun site sélectionné (filtre FABLE_ONLY_SITES ?).")
    sys.exit(1)

# -----------------------
# Constructions d'URL
# -----------------------
def build_forecast_url(lat: float, lon: float, model: Optional[str]) -> str:
    params = {
        "latitude": f"{lat:.5f}",
        "longitude": f"{lon:.5f}",
        "hourly": ",".join(ECMWF_KEYS),
        "timezone": TZ_NAME,
        "timeformat": "iso8601",
        "windspeed_unit": "kmh",
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
    }
    if model:
        params["models"] = model
    return "https://api.open-meteo.com/v1/forecast?" + urlencode(params)

def build_marine_url(lat: float, lon: float) -> str:
    params = {
        "latitude": f"{lat:.5f}",
        "longitude": f"{lon:.5f}",
        "hourly": ",".join(MARINE_KEYS),
        "timezone": TZ_NAME,
        "timeformat": "iso8601",
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
    }
    return "https://marine-api.open-meteo.com/v1/marine?" + urlencode(params)

# -----------------------
# Fetch robustes
# -----------------------
FORECAST_MODEL_TRY_ORDER = [
    "ecmwf_ifs04",
    "icon_seamless",
    "gfs_seamless",
    None,  # pas de filtre "models"
]

def fetch_forecast_ok(lat: float, lon: float) -> Tuple[Dict[str, Any], str]:
    """Essaie plusieurs modèles jusqu'à obtenir toutes les clés horaires attendues."""
    last_payload: Dict[str, Any] | None = None
    last_model = "unknown"
    for model in FORECAST_MODEL_TRY_ORDER:
        url = build_forecast_url(lat, lon, model)
        payload = http_get_json(url, retry=2, timeout=25)
        hourly = payload.get("hourly") or {}
        ok, missing = arrays_ok(hourly, ECMWF_KEYS)
        if ok:
            return payload, (model or "auto")
        last_payload = payload
        last_model = model or "auto"
        log.warning("Forecast %s: clés manquantes %s — on essaie le modèle suivant...", last_model, missing)
    # Dernière chance: si on a au moins le vent/rafales, on accepte et on remplira les autres à vide
    if last_payload:
        hourly = last_payload.get("hourly") or {}
        core_ok, missing = arrays_ok(hourly, ["wind_speed_10m", "wind_gusts_10m"])
        if core_ok:
            return last_payload, last_model + " (partial)"
    raise RuntimeError("Impossible d'obtenir les tableaux horaires requis pour forecast (tous modèles testés).")

def fetch_marine_ok(lat: float, lon: float) -> Dict[str, Any]:
    url = build_marine_url(lat, lon)
    payload = http_get_json(url, retry=2, timeout=25)
    ok, missing = arrays_ok(payload.get("hourly") or {}, MARINE_KEYS)
    if not ok:
        raise RuntimeError(f"Marine: clés manquantes {missing}")
    return payload

# -----------------------
# Découpage horaire
# -----------------------
def slice_hourly(payload: Dict[str, Any],
                 keys: List[str],
                 window_start: dt.datetime,
                 window_end: dt.datetime,
                 tz: ZoneInfo) -> Dict[str, Any]:
    h = payload.get("hourly", {}) or {}
    times = h.get("time", []) or []
    out: Dict[str, Any] = {"time": []}
    for k in keys:
        out[k] = []
    if not times:
        return out
    for i, t_iso in enumerate(times):
        if within_window(t_iso, window_start, window_end, tz):
            out["time"].append(t_iso)
            for k in keys:
                arr = h.get(k)
                if isinstance(arr, list) and i < len(arr):
                    out[k].append(arr[i])
                else:
                    out[k].append(None)
    return out

# -----------------------
# Collecte principale
# -----------------------
results = []

for site in selected_sites:
    name = site["name"]; slug = site["slug"]; lat = site["lat"]; lon = site["lon"]
    log.info("▶ Collecte: %s (%.5f, %.5f)", name, lat, lon)

    try:
        wx_payload, model_used = fetch_forecast_ok(lat, lon)
    except Exception as e:
        log.error("Forecast KO pour %s: %s", name, e)
        wx_payload, model_used = {"hourly": {"time": []}, "hourly_units": {}}, "none"

    try:
        sea_payload = fetch_marine_ok(lat, lon)
    except Exception as e:
        log.error("Marine KO pour %s: %s", name, e)
        sea_payload = {"hourly": {"time": []}, "hourly_units": {}}

    ecmwf_hourly = slice_hourly(wx_payload, ECMWF_KEYS, start_local, end_local, TZ)
    marine_hourly = slice_hourly(sea_payload, MARINE_KEYS, start_local, end_local, TZ)

    # Méta / unités
    e_units = wx_payload.get("hourly_units", {}) or {}
    m_units = sea_payload.get("hourly_units", {}) or {}

    out: Dict[str, Any] = {
        "meta": {
            "site_name": name,
            "slug": slug,
            "lat": lat,
            "lon": lon,
            "tz": TZ_NAME,
            "generated_at": dt.datetime.now(TZ).isoformat(),
            "window": {
                "start_local": start_local.isoformat(),
                "end_local": end_local.isoformat(),
                "hours": int((end_local - start_local).total_seconds() // 3600),
            },
            "sources": {
                "forecast_open_meteo": {
                    "endpoint": "https://api.open-meteo.com/v1/forecast",
                    "model_used": model_used,
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
        "hourly": {  # compat reader
            "ecmwf": ecmwf_hourly,
            "marine": marine_hourly,
        },
    }

    # Écriture atomique
    tmp = PUBLIC / f".{slug}.json.tmp"
    final = PUBLIC / f"{slug}.json"
    tmp.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    tmp.replace(final)

    points = len(ecmwf_hourly.get("time", []))
    results.append({"slug": slug, "path": str(final), "points": points, "model": model_used})

# Résumé
ok = [r for r in results if r["points"] > 0]
for r in results:
    log.info(" - %s: %d h (modèle=%s)", r["slug"], r["points"], r["model"])
log.info("Terminé: %d/%d spots écrits avec données horaires.", len(ok), len(selected_sites))

if not ok:
    log.error("Aucune donnée horaire dans la fenêtre — vérifier paramètres/timezone.")
    sys.exit(2)
