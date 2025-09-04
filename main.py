#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
fable-collector — main.py
- Lit sites.yaml (name, lat, lon, shelter_bonus_radius_km)
- Fenêtre contrôlée par:
    FABLE_TZ            (ex: "Africa/Tunis")
    FABLE_WINDOW_HOURS  (ex: "48")
    FABLE_START_ISO     (optionnel; ex: "2025-09-03T06:00")
    FABLE_ONLY_SITES    (CSV de noms/slugs à restreindre)
- Sources:
    Open-Meteo forecast (ECMWF)  : vent/rafales/direction/weather_code/visibility (horaire)
    Open-Meteo Marine           : wave_height / wave_period (+ swell*) (horaire)
- Écrit: public/<slug>.json  (avec clés top-level "ecmwf" et "marine" + doublon sous "hourly")
"""

import os
import sys
import json
import time
import yaml
import random
import logging
import datetime as dt
from pathlib import Path
from typing import Dict, Any, List, Optional
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

import urllib.request

# -----------------------
# Config logging simple
# -----------------------
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

def http_get_json(url: str, retry: int = 2, timeout: int = 30) -> Dict[str, Any]:
    last_err = None
    for attempt in range(retry + 1):
        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "fable-collector/1.0 (+github actions)"},
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                if resp.status != 200:
                    raise RuntimeError(f"HTTP {resp.status}")
                data = resp.read()
                return json.loads(data.decode("utf-8"))
        except Exception as e:
            last_err = e
            sleep_s = 1.2 + attempt * 1.5 + random.random()
            log.warning("GET failed (%s). retry in %.1fs ...", e, sleep_s)
            time.sleep(sleep_s)
    raise RuntimeError(f"GET failed after retries: {last_err}")

def ensure_dir(p: Path):
    p.mkdir(parents=True, exist_ok=True)

def _as_local_aware(x: dt.datetime, tz: ZoneInfo) -> dt.datetime:
    """Force un datetime à être tz-aware dans `tz` (ou le convertir)."""
    if x.tzinfo is None:
        return x.replace(tzinfo=tz)
    return x.astimezone(tz)

def parse_iso_local(s: str, tz: ZoneInfo) -> dt.datetime:
    """
    Open-Meteo renvoie souvent 'YYYY-MM-DDTHH:00' (sans offset).
    Traite comme heure locale `tz`. Si un offset est présent, convertit vers `tz`.
    """
    try:
        d = dt.datetime.fromisoformat(s)  # gère YYYY-MM-DDTHH:MM[:SS][±HH:MM]
    except ValueError:
        # Cas rare: chaîne sans minutes (YYYY-MM-DDTHH)
        if len(s) == 13 and "T" in s:
            d = dt.datetime.fromisoformat(s + ":00")
        else:
            raise
    if d.tzinfo is None:
        return d.replace(tzinfo=tz)
    return d.astimezone(tz)

def within_window(t_iso: str, start: dt.datetime, end: dt.datetime) -> bool:
    """Comparaison tz-aware en Africa/Tunis."""
    t = parse_iso_local(t_iso, TZ)
    s = _as_local_aware(start, TZ)
    e = _as_local_aware(end, TZ)
    return (t >= s) and (t < e)

def csv_to_set(s: str) -> Optional[set]:
    if not s:
        return None
    return {slugify(x.strip()) for x in s.split(",") if x.strip()}

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
# Normalisation défensive (déjà aware mais on verrouille)
start_local = _as_local_aware(start_local, TZ)
end_local   = _as_local_aware(end_local, TZ)

# Open-Meteo préfère start_date/end_date (jour). On filtrera ensuite heure par heure.
start_date = start_local.date()
end_date = end_local.date()

log.info("Fenêtre locale %s → %s (%dh) TZ=%s",
         start_local.isoformat(), end_local.isoformat(), WINDOW_H, TZ_NAME)

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
    log.error("Impossible de lire sites.yaml: %s", e)
    sys.exit(1)

if not isinstance(sites, list) or not sites:
    log.error("sites.yaml mal formé ou vide.")
    sys.exit(1)

# Sélection optionnelle (FABLE_ONLY_SITES)
selected_sites = []
for s in sites:
    name = s.get("name") or "Site"
    slug = slugify(name)
    if ONLY and slug not in ONLY and slugify(name) not in ONLY:
        continue
    try:
        lat = float(s["lat"])
        lon = float(s["lon"])
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
# URLs Open-Meteo
# -----------------------
def build_ecmwf_url(lat: float, lon: float) -> str:
    params = {
        "latitude": f"{lat:.5f}",
        "longitude": f"{lon:.5f}",
        "hourly": ",".join([
            "wind_speed_10m",
            "wind_gusts_10m",
            "wind_direction_10m",
            "weather_code",
            "visibility",
        ]),
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
        "hourly": ",".join([
            "wave_height",
            "wave_period",
            "swell_wave_height",
            "swell_wave_period",
        ]),
        "timezone": TZ_NAME,
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
    }
    return "https://marine-api.open-meteo.com/v1/marine?" + urlencode(params)

def fetch_ecmwf(lat: float, lon: float) -> Dict[str, Any]:
    url = build_ecmwf_url(lat, lon)
    try:
        return http_get_json(url, retry=2, timeout=30)
    except Exception as e:
        log.warning("ECMWF avec 'models' a échoué (%s). On retente sans param models.", e)
        base = "https://api.open-meteo.com/v1/forecast?"
        params = {
            "latitude": f"{lat:.5f}",
            "longitude": f"{lon:.5f}",
            "hourly": "wind_speed_10m,wind_gusts_10m,wind_direction_10m,weather_code,visibility",
            "timezone": TZ_NAME,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
        }
        return http_get_json(base + urlencode(params), retry=2, timeout=30)

def fetch_marine(lat: float, lon: float) -> Dict[str, Any]:
    return http_get_json(build_marine_url(lat, lon), retry=2, timeout=30)

def slice_hourly(payload: Dict[str, Any],
                 keys: List[str],
                 window_start: dt.datetime,
                 window_end: dt.datetime) -> Dict[str, Any]:
    """Filtre les tableaux horaires d'Open-Meteo pour ne garder que la fenêtre [start, end[."""
    h = payload.get("hourly", {})
    times = h.get("time", [])
    out: Dict[str, Any] = {"time": []}
    for k in keys:
        out[k] = []
    if not times:
        return out

    for i, t_iso in enumerate(times):
        if within_window(t_iso, window_start, window_end):
            out["time"].append(t_iso)
            for k in keys:
                arr = h.get(k, [])
                out[k].append(arr[i] if i < len(arr) else None)
    return out

# -----------------------
# Collecte
# -----------------------
ROOT = Path(__file__).resolve().parent
PUBLIC = ROOT / "public"
ensure_dir(PUBLIC)

results = []

for site in selected_sites:
    name = site["name"]
    slug = site["slug"]
    lat = site["lat"]
    lon = site["lon"]

    log.info("▶ Collecte: %s (%.5f, %.5f)", name, lat, lon)

    try:
        wx = fetch_ecmwf(lat, lon)
        sea = fetch_marine(lat, lon)
    except Exception as e:
        log.error("Échec de collecte pour %s: %s", name, e)
        continue

    ecmwf_keys = [
        "wind_speed_10m",
        "wind_gusts_10m",
        "wind_direction_10m",
        "weather_code",
        "visibility",
    ]
    marine_keys = [
        "wave_height",
        "wave_period",
        "swell_wave_height",
        "swell_wave_period",
    ]

    # Filtrer sur la fenêtre exacte en heure locale
    ecmwf_hourly = slice_hourly(wx, ecmwf_keys, start_local, end_local)
    marine_hourly = slice_hourly(sea, marine_keys, start_local, end_local)

    e_units = wx.get("hourly_units", {})
    m_units = sea.get("hourly_units", {})

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
        # Doublon volontaire: top-level + sous-clé "hourly" (compatibilité reader)
        "ecmwf": ecmwf_hourly,
        "marine": marine_hourly,
        "hourly": {
            "ecmwf": ecmwf_hourly,
            "marine": marine_hourly,
        },
    }

    # Écriture atomique
    tmp = PUBLIC / f".{slug}.json.tmp"
    final = PUBLIC / f"{slug}.json"
    tmp.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    tmp.replace(final)

    results.append({"slug": slug, "path": str(final), "points": len(ecmwf_hourly.get("time", []))})

# Petit résumé stdout
ok = [r for r in results if r["points"] > 0]
log.info("Terminé: %d/%d spots écrits (avec données horaires dans la fenêtre).",
         len(ok), len(selected_sites))

# Si aucun fichier n’a été écrit, renvoyer code non-0 pour alerter le workflow
if not ok:
    log.error("Aucune donnée horaire dans la fenêtre demandée — vérifier paramètres/timezone.")
    sys.exit(2)
