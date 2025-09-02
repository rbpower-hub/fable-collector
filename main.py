#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FABLE Collector — Open-Meteo (gratuit)
- Vent/rafales/direction/weather_code/visibility depuis Forecast API (models: ECMWF + ICON) — deux appels séparés
- Hs/Tp/swell depuis Marine API
- Horizon paramétrable (par défaut 48 h), timezone Africa/Tunis (séries locales)
- Produit 1 JSON par spot dans ./public/<slug>.json + index.json + index.html
"""

import os, sys, json, time, re, unicodedata, hashlib
from pathlib import Path
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import requests
import yaml

# =========================
# Configuration générale
# =========================
TZ = "Africa/Tunis"
TZINFO = ZoneInfo(TZ)
HORIZON_HOURS = int(os.environ.get("HORIZON_HOURS", "48"))

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
MARINE_URL   = "https://marine-api.open-meteo.com/v1/marine"

FORECAST_HOURLY = ",".join([
    "wind_speed_10m",
    "wind_gusts_10m",
    "wind_direction_10m",
    "weather_code",
    "visibility"
])

MARINE_HOURLY = ",".join([
    "wave_height",
    "wave_period",
    "swell_wave_height",
    "swell_wave_period"
])

# =========================
# Utilitaires
# =========================
def now_local_iso() -> str:
    return datetime.now(TZINFO).isoformat()

def now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

def to_utc_iso_from_epoch(ts: float) -> str:
    return datetime.fromtimestamp(ts, timezone.utc).isoformat().replace("+00:00", "Z")

def parse_local_iso(s: str) -> datetime:
    # Open-Meteo renvoie "YYYY-MM-DDTHH:MM" sans tz quand on passe timezone=Africa/Tunis
    # On l'interprète explicitement comme horaire local Africa/Tunis.
    return datetime.fromisoformat(s).replace(tzinfo=TZINFO)

def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()

def slugify(name: str) -> str:
    # ASCII only, accents supprimés, séparateurs -> "-"
    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    s = re.sub(r"[^a-zA-Z0-9]+", "-", s).strip("-").lower()
    return s or "spot"

def trim_to_horizon(arr, horizon=HORIZON_HOURS):
    if not isinstance(arr, list):
        return arr
    return arr[:horizon]

def fetch_json(url, params, retries=2, timeout=30):
    last_err = None
    for attempt in range(retries + 1):
        try:
            r = requests.get(url, params=params, timeout=timeout)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            last_err = e
            if attempt < retries:
                time.sleep(1.5 * (attempt + 1))
    raise last_err

# =========================
# Acquisition par modèle
# =========================
def fetch_forecast_model(lat: float, lon: float, model_code: str) -> dict:
    """
    model_code: "ecmwf_ifs04" ou "icon_seamless"
    Renvoie le JSON Forecast pour un seul modèle, heures locales Africa/Tunis.
    """
    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": FORECAST_HOURLY,
        "models": model_code,
        "timezone": TZ,
    }
    return fetch_json(FORECAST_URL, params)

def fetch_marine(lat: float, lon: float) -> dict:
    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": MARINE_HOURLY,
        "timezone": TZ,
    }
    return fetch_json(MARINE_URL, params)

# =========================
# Collecte spot
# =========================
def collect_for_spot(name: str, lat: float, lon: float, shelter_bonus_radius_km: float) -> dict:
    # 1) Vent via deux modèles indépendants
    ec = fetch_forecast_model(lat, lon, "ecmwf_ifs04")
    ic = fetch_forecast_model(lat, lon, "icon_seamless")

    # 2) Mer (Hs/Tp)
    ma = fetch_marine(lat, lon)

    # 3) Détermination de l’horizon commun
    times_ec = ec.get("hourly", {}).get("time", []) or []
    times_ic = ic.get("hourly", {}).get("time", []) or []
    times_ma = ma.get("hourly", {}).get("time", []) or []

    # On prend le min des trois longueurs pour garantir l’alignement horaire
    horizon = min(HORIZON_HOURS, len(times_ec), len(times_ic), len(times_ma))

    # On retient la grille temporelle de l'ECMWF (elles sont normalement identiques)
    times = trim_to_horizon(times_ec, horizon)

    # 4) Construction du payload
    payload = {
        "schema_version": "1.0",
        "meta": {
            "name": name,
            "slug": slugify(name),
            "lat": lat,
            "lon": lon,
            "shelter_bonus_radius_km": shelter_bonus_radius_km,
            "timezone": TZ,
            "horizon_hours": horizon,
            "generated_at_local": now_local_iso(),
            "generated_at_utc": now_utc_iso(),
            "sources": {
                "wind_models": ["ECMWF", "ICON"],
                "marine_model": "Open-Meteo Marine",
                "endpoints": {
                    "forecast": FORECAST_URL,
                    "marine": MARINE_URL
                }
            },
            "units": {
                "wind_speed_10m": "km/h",
                "wind_gusts_10m": "km/h",
                "wind_direction_10m": "°",
                "weather_code": "WMO",
                "visibility": "m",
                "wave_height": "m",
                "wave_period": "s",
                "swell_wave_height": "m",
                "swell_wave_period": "s"
            },
            "utc_offset_seconds": {
                "forecast_ecmwf": ec.get("utc_offset_seconds"),
                "forecast_icon": ic.get("utc_offset_seconds"),
                "marine": ma.get("utc_offset_seconds")
            }
        },
        "hourly": {
            "time": times,  # horaires locaux Africa/Tunis
            "wind": {
                "ECMWF": {
                    "wind_speed_10m":      trim_to_horizon(ec.get("hourly", {}).get("wind_speed_10m", []), horizon),
                    "wind_gusts_10m":      trim_to_horizon(ec.get("hourly", {}).get("wind_gusts_10m", []), horizon),
                    "wind_direction_10m":  trim_to_horizon(ec.get("hourly", {}).get("wind_direction_10m", []), horizon),
                    "weather_code":        trim_to_horizon(ec.get("hourly", {}).get("weather_code", []), horizon),
                    "visibility":          trim_to_horizon(ec.get("hourly", {}).get("visibility", []), horizon),
                },
                "ICON": {
                    "wind_speed_10m":      trim_to_horizon(ic.get("hourly", {}).get("wind_speed_10m", []), horizon),
                    "wind_gusts_10m":      trim_to_horizon(ic.get("hourly", {}).get("wind_gusts_10m", []), horizon),
                    "wind_direction_10m":  trim_to_horizon(ic.get("hourly", {}).get("wind_direction_10m", []), horizon),
                    "weather_code":        trim_to_horizon(ic.get("hourly", {}).get("weather_code", []), horizon),
                    "visibility":          trim_to_horizon(ic.get("hourly", {}).get("visibility", []), horizon),
                }
            },
            "waves": {
                "wave_height":        trim_to_horizon(ma.get("hourly", {}).get("wave_height", []), horizon),
                "wave_period":        trim_to_horizon(ma.get("hourly", {}).get("wave_period", []), horizon),
                "swell_wave_height":  trim_to_horizon(ma.get("hourly", {}).get("swell_wave_height", []), horizon),
                "swell_wave_period":  trim_to_horizon(ma.get("hourly", {}).get("swell_wave_period", []), horizon),
            }
        }
    }
    return payload

# =========================
# Index JSON / HTML
# =========================
def build_index(pub: Path, base_url: str | None = None):
    files = []
    for p in sorted(pub.glob("*.json")):
        if p.name == "index.json":
            continue
        try:
            stat = p.stat()
            data = json.loads(p.read_text(encoding="utf-8"))
            meta = data.get("meta", {})
            hours = int(meta.get("horizon_hours", 0))
            lat = meta.get("lat")
            lon = meta.get("lon")
            slug = meta.get("slug", p.stem)

            # Fraîcheur >= 24 h ?
            times = data.get("hourly", {}).get("time", [])
            fresh_24h = False
            if times:
                try:
                    last_local = parse_local_iso(times[-1])
                    fresh_24h = (last_local - datetime.now(TZINFO)).total_seconds() >= 24 * 3600
                except Exception:
                    fresh_24h = False

            item = {
                "path": p.name,
                "size": stat.st_size,
                "modified_utc": to_utc_iso_from_epoch(stat.st_mtime),
                "sha256": sha256_file(p),
                "slug": slug,
                "lat": lat,
                "lon": lon,
                "hours": hours,
                "fresh_24h": fresh_24h
            }
            if base_url:
                item["url"] = f"{base_url.rstrip('/')}/{p.name}"
            files.append(item)
        except Exception as e:
            print(f"[index] Skip {p.name}: {e}", file=sys.stderr)

    index = {
        "schema_version": "1.0",
        "tz": TZ,
        "range_hours": HORIZON_HOURS,
        "hourly_step": "1h",
        "sources": {
            "wind": ["Open-Meteo ECMWF", "Open-Meteo ICON"],
            "waves": "Open-Meteo Marine"
        },
        "generated_at_utc": now_utc_iso(),
        "files": files
    }

    (pub / "index.json").write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")

    # Petit index HTML
    html = [
        "<!doctype html><html><head><meta charset='utf-8'><title>FABLE JSON</title>",
        "<style>body{font-family:system-ui,Segoe UI,Roboto,Arial,sans-serif;padding:16px}</style>",
        "</head><body><h1>FABLE JSON (GitHub Pages)</h1>",
        f"<p>Timezone séries: <b>{TZ}</b> — Horizon: <b>{HORIZON_HOURS} h</b></p>",
        "<ul>"
    ]
    for f in files:
        href = f.get("url") or f["path"]
        html.append(f"<li><a href='{href}'>{f['path']}</a> — {f['hours']}h — SHA256: {f['sha256'][:12]}…</li>")
    html += ["</ul></body></html>"]
    (pub / "index.html").write_text("\n".join(html), encoding="utf-8")

# =========================
# Programme principal
# =========================
def main():
    root = Path(__file__).resolve().parent
    pub  = root / "public"
    pub.mkdir(parents=True, exist_ok=True)

    # Lecture des spots
    cfg_path = root / "sites.yaml"
    if not cfg_path.exists():
        print("Aucun sites.yaml trouvé.", file=sys.stderr)
        sys.exit(1)
    cfg = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
    spots = cfg.get("spots", [])
    if not spots:
        print("Aucun spot dans sites.yaml", file=sys.stderr)
        sys.exit(1)

    all_slugs = []

    for s in spots:
        try:
            name = s["name"]
            lat  = float(s["lat"])
            lon  = float(s["lon"])
            rkm  = float(s.get("shelter_bonus_radius_km", 0.0))
        except Exception as e:
            print(f"[cfg] Spot invalide {s}: {e}", file=sys.stderr)
            continue

        print(f"[collecte] {name} ({lat},{lon}) …", file=sys.stderr)
        try:
            payload = collect_for_spot(name, lat, lon, rkm)
        except Exception as e:
            print(f"[ERREUR] {name}: {e}", file=sys.stderr)
            continue

        slug = payload["meta"]["slug"]
        out = pub / f"{slug}.json"
        out.write_text(json.dumps(payload, ensure_ascii=False, separators=(',', ':')), encoding="utf-8")
        all_slugs.append(slug)

    # Base URL publique (si disponible dans l'env GitHub Actions)
    base_url = None
    repo = os.environ.get("GITHUB_REPOSITORY")  # "owner/repo"
    owner = os.environ.get("GITHUB_REPOSITORY_OWNER")
    if repo and owner:
        repo_name = repo.split("/")[-1]
        base_url = f"https://{owner}.github.io/{repo_name}"

    build_index(pub, base_url=base_url)

if __name__ == "__main__":
    main()
