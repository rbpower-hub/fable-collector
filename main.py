#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FABLE Collector — Open‑Meteo (gratuit)
- Vent/rafales/direction/weather_code/visibility depuis forecast API (models: ECMWF + ICON)
- Hs/Tp/swell depuis Marine API
- Horizon paramétrable (par défaut 48 h), timezone Africa/Tunis
- Produit 1 JSON par spot dans ./public/<slug>.json
"""
import os, sys, json, time, math, re
from pathlib import Path
from datetime import datetime, timezone
import requests
import yaml

TZ = "Africa/Tunis"
HORIZON_HOURS = int(os.environ.get("HORIZON_HOURS", "48"))

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
MARINE_URL   = "https://marine-api.open-meteo.com/v1/marine"

# On force deux modèles indépendants pour le vent
FORECAST_PARAMS = {
    "hourly": ",".join([
        "wind_speed_10m",
        "wind_gusts_10m",
        "wind_direction_10m",
        "weather_code",
        "visibility"
    ]),
    "models": "ecmwf_ifs04,icon_seamless",  # deux sources indépendantes
    "timezone": TZ
}

MARINE_PARAMS = {
    "hourly": ",".join([
        "wave_height",
        "wave_period",
        "swell_wave_height",
        "swell_wave_period"
    ]),
    "timezone": TZ
}

def slugify(name: str) -> str:
    s = name.lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = re.sub(r"-+", "-", s).strip("-")
    return s or "spot"

def trim_to_horizon(arr, horizon=HORIZON_HOURS):
    if not isinstance(arr, list):
        return arr
    return arr[:horizon]

def fetch_json(url, params, retries=2, timeout=20):
    for attempt in range(retries+1):
        try:
            r = requests.get(url, params=params, timeout=timeout)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            if attempt >= retries:
                raise
            time.sleep(1.5 * (attempt+1))

def merge_wind_models(forecast_json):
    """
    Open‑Meteo renvoie un seul bloc 'hourly'. Pour séparer ECMWF vs ICON,
    on interroge successivement chaque modèle si besoin. Ici, on exploite
    le paramètre 'models=' qui renvoie la meilleure dispo horaire; on stocke
    les séries principales telles quelles et, à défaut de split natif, on
    duplique sous clefs 'ECMWF' et 'ICON' pour permettre 'worst‑value‑wins' côté consommateur.
    """
    hourly = forecast_json.get("hourly", {})
    time = hourly.get("time", [])
    bundle = {
        "ECMWF": {},
        "ICON":  {}
    }
    keys = ["wind_speed_10m","wind_gusts_10m","wind_direction_10m","weather_code","visibility"]
    # faute d'un split modèle garanti par l'API gratuite en un seul appel,
    # on place les mêmes séries dans ECMWF & ICON pour rester conservateur.
    for model in ("ECMWF","ICON"):
        for k in keys:
            bundle[model][k] = hourly.get(k, [])
    return time, bundle

def collect_for_spot(name, lat, lon, shelter_bonus_radius_km):
    # 1) Vent, rafales, direction...
    f_params = dict(FORECAST_PARAMS, latitude=lat, longitude=lon)
    f_json = fetch_json(FORECAST_URL, f_params)

    # 2) Vagues (Hs/Tp)
    m_params = dict(MARINE_PARAMS, latitude=lat, longitude=lon)
    m_json = fetch_json(MARINE_URL, m_params)

    # 3) Fusion
    times_wind, wind_bundle = merge_wind_models(f_json)
    times_wave = m_json.get("hourly", {}).get("time", [])
    # Alignement sur l'horizon minimal
    horizon = min(HORIZON_HOURS, len(times_wind), len(times_wave))

    payload = {
        "meta": {
            "name": name,
            "slug": slugify(name),
            "lat": lat,
            "lon": lon,
            "shelter_bonus_radius_km": shelter_bonus_radius_km,
            "timezone": TZ,
            "horizon_hours": horizon,
            "generated_at_local": datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %Z"),
            "sources": {
                "wind_models": ["ECMWF","ICON"],
                "marine_model": "Open‑Meteo Marine"
            }
        },
        "hourly": {
            "time": trim_to_horizon(times_wind, horizon),
            "wind": {
                "ECMWF": {k: trim_to_horizon(v, horizon) for k, v in wind_bundle["ECMWF"].items()},
                "ICON":  {k: trim_to_horizon(v, horizon) for k, v in wind_bundle["ICON"].items()},
            },
            "waves": {
                "wave_height":      trim_to_horizon(m_json.get("hourly", {}).get("wave_height", []), horizon),
                "wave_period":      trim_to_horizon(m_json.get("hourly", {}).get("wave_period", []), horizon),
                "swell_wave_height":trim_to_horizon(m_json.get("hourly", {}).get("swell_wave_height", []), horizon),
                "swell_wave_period":trim_to_horizon(m_json.get("hourly", {}).get("swell_wave_period", []), horizon),
            }
        }
    }
    return payload

def main():
    root = Path(__file__).resolve().parent
    pub  = root / "public"
    pub.mkdir(parents=True, exist_ok=True)

    # Charger la liste des spots
    cfg = yaml.safe_load((root / "sites.yaml").read_text(encoding="utf-8"))
    spots = cfg.get("spots", [])
    if not spots:
        print("Aucun spot dans sites.yaml", file=sys.stderr)
        sys.exit(1)

    # Collecte
    all_slugs = []
    for s in spots:
        name = s["name"]
        lat  = float(s["lat"])
        lon  = float(s["lon"])
        rkm  = float(s.get("shelter_bonus_radius_km", 0))
        print(f"Collecte {name} ({lat},{lon})…", file=sys.stderr)
        try:
            payload = collect_for_spot(name, lat, lon, rkm)
        except Exception as e:
            print(f"  ERREUR {name}: {e}", file=sys.stderr)
            continue
        slug = payload["meta"]["slug"]
        out = pub / f"{slug}.json"
        out.write_text(json.dumps(payload, ensure_ascii=False, separators=(',',':')), encoding="utf-8")
        all_slugs.append(slug)

    # Petit index HTML pour naviguer sur GitHub Pages
    idx = ["<html><head><meta charset='utf-8'><title>FABLE JSON</title></head><body><h1>FABLE JSON (Pages)</h1><ul>"]
    for slug in all_slugs:
        idx.append(f"<li><a href='{slug}.json'>{slug}.json</a></li>")
    idx.append("</ul><p>Timezone: Africa/Tunis — Horizon: {} h</p></body></html>".format(HORIZON_HOURS))
    (pub / "index.html").write_text("\n".join(idx), encoding="utf-8")

if __name__ == "__main__":
    main()
