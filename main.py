#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
fable-collector — main.py (durci: timeouts/budgets, fallback modèles, clés normalisées, slicing séparé, alignement commun & index.json)
- Lit sites.yaml (name, lat, lon, shelter_bonus_radius_km)
- Fenêtre contrôlée par env:
    FABLE_TZ, FABLE_WINDOW_HOURS, FABLE_START_ISO, FABLE_ONLY_SITES
- Sources:
    Open-Meteo (ECMWF/ICON/GFS fallback): vent/rafales/direction/weather_code/visibility/pressure/precip (horaire)
    Open-Meteo Marine: wave_height / wave_period (+ swell) (horaire)
- Écrit: public/<slug>.json  (keys: meta, ecmwf, marine, daily, hourly)
- Écrit aussi: public/index.json (inventaire léger)
"""

import os, sys, json, time, yaml, random, logging
import datetime as dt
from pathlib import Path
from typing import Dict, Any, List, Optional
from urllib.parse import urlencode
from zoneinfo import ZoneInfo
import urllib.request

# -----------------------
# Config & budgets
# -----------------------
HTTP_TIMEOUT_S       = int(os.getenv("FABLE_HTTP_TIMEOUT_S", "10"))
HTTP_RETRIES         = int(os.getenv("FABLE_HTTP_RETRIES", "1"))
MODEL_ORDER          = [m.strip() for m in os.getenv(
    "FABLE_MODEL_ORDER", "icon_seamless,gfs_seamless,default,ecmwf_ifs04"
).split(",") if m.strip()]
SITE_BUDGET_S        = int(os.getenv("FABLE_SITE_BUDGET_S", "70"))
HARD_BUDGET_S        = int(os.getenv("FABLE_HARD_BUDGET_S", "240"))

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("fable-collector")

# ➕ Debug dumps activables
DEBUG_DUMP = os.getenv("FABLE_DEBUG_DUMP", "1") == "1"
# Extras optionnels (activables sans impacter la logique)
INCLUDE_EXTRAS = os.getenv("FABLE_INCLUDE_EXTRAS", "1") == "1"
EXTRA_HOURLY   = ["relative_humidity_2m", "cloud_cover"]  # variables largement supportées


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

def http_get_json(url: str, retry: int = HTTP_RETRIES, timeout: int = HTTP_TIMEOUT_S) -> Dict[str, Any]:
    last_err = None
    for attempt in range(retry + 1):
        try:
            req = urllib.request.Request(
                url, headers={"User-Agent": "fable-collector/1.4 (+github actions)"}
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                if resp.status != 200:
                    raise RuntimeError(f"HTTP {resp.status}")
                return json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            last_err = e
            if attempt < retry:
                sleep_s = 0.8 + attempt * 1.2 + random.random() * 0.5
                log.warning("GET failed (%s). retry in %.1fs ...", e, sleep_s)
                time.sleep(sleep_s)
    raise RuntimeError(f"GET failed after retries: {last_err}")

def ensure_dir(p: Path): p.mkdir(parents=True, exist_ok=True)

def csv_to_set(s: str) -> Optional[set]:
    if not s: return None
    return {slugify(x.strip()) for x in s.split(",") if x.strip()}

def parse_time_local(t_iso: str, tz: ZoneInfo) -> dt.datetime:
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
TZ_NAME  = os.getenv("FABLE_TZ", "Africa/Tunis")
TZ       = ZoneInfo(TZ_NAME)
WINDOW_H = int(os.getenv("FABLE_WINDOW_HOURS", "48"))
START_ISO= os.getenv("FABLE_START_ISO", "").strip()
ONLY     = csv_to_set(os.getenv("FABLE_ONLY_SITES", "gammarth-port"))

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

end_local   = start_local + dt.timedelta(hours=WINDOW_H)
start_date  = start_local.date()
end_date    = end_local.date()

log.info("Fenêtre locale %s → %s (%dh) TZ=%s | timeouts=%ss retries=%d models=%s | budgets: site=%ss, global=%ss",
         start_local.isoformat(), end_local.isoformat(), WINDOW_H, TZ_NAME,
         HTTP_TIMEOUT_S, HTTP_RETRIES, "/".join(MODEL_ORDER), SITE_BUDGET_S, HARD_BUDGET_S)

# -----------------------
# Charger sites.yaml
# -----------------------
ROOT = Path(__file__).resolve().parent
sites_yaml = ROOT / "sites.yaml"
if not sites_yaml.exists():
    log.error("sites.yaml introuvable à la racine du repo."); sys.exit(1)
try:
    sites = yaml.safe_load(sites_yaml.read_text(encoding="utf-8"))
except Exception as e:
    log.error("Impossible de lire sites.yaml: %s", e); sys.exit(1)
if not isinstance(sites, list) or not sites:
    log.error("sites.yaml mal formé ou vide."); sys.exit(1)

# ➕ Exclusion définitive (politique FABLE)
EXCLUDE_SLUGS = {"korbous", "kelibia", "kélibia"}

selected_sites = []
for s in sites:
    name = s.get("name") or "Site"
    slug = slugify(name)
    if slug in EXCLUDE_SLUGS:
        log.info("Exclu par politique: %s", name)
        continue
    if ONLY and slug not in ONLY:
        continue
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
# Clés & synonymes
# -----------------------
ECMWF_KEYS  = ["wind_speed_10m","wind_gusts_10m","wind_direction_10m","weather_code","visibility","surface_pressure","precipitation"]
MARINE_KEYS = ["wave_height","wave_period","swell_wave_height","swell_wave_period"]
DAILY_KEYS  = ["sunrise","sunset"]
ASTRONOMY_DAILY_KEYS = ["sunrise", "sunset", "moonrise", "moonset", "moon_phase"]

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
    "surface_pressure":   ["surface_pressure"],
    "precipitation":      ["precipitation"],
}

def first_series(h: Dict[str, Any], canonical_key: str) -> List:
    for cand in KEY_SYNONYMS.get(canonical_key, [canonical_key]):
        arr = h.get(cand)
        if isinstance(arr, list) and arr:
            return arr
    return []

def normalize_hourly_keys(payload: Dict[str, Any]) -> Dict[str, Any]:
    h = (payload.get("hourly") or {}).copy()
    normalized = dict(h)
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
def forecast_url(lat: float, lon: float, model: Optional[str], hourly_keys: Optional[List[str]] = None,
                 include_daily: bool = True) -> str:

    # fusionne clés de base + extras si activés
    hk = list(hourly_keys or ECMWF_KEYS)
    if INCLUDE_EXTRAS:
        hk = hk + [k for k in EXTRA_HOURLY if k not in hk]
    params = {
        "latitude":      f"{lat:.5f}",
        "longitude":     f"{lon:.5f}",
        "hourly":        ",".join(hk),
        "timezone":      TZ_NAME,
        "timeformat":    "iso8601",
        "windspeed_unit":"kmh",
        "start_date":    start_date.isoformat(),
        "end_date":      end_date.isoformat(),
    }
    if include_daily:
        params["daily"] = ",".join(DAILY_KEYS)
    if model and model != "default":
        params["models"] = model
    return "https://api.open-meteo.com/v1/forecast?" + urlencode(params)
def astronomy_url(lat: float, lon: float) -> str:
    # L’API Astronomy fournit sunrise/sunset + moonrise/moonset/moon_phase
    params = {
        "latitude":  f"{lat:.5f}",
        "longitude": f"{lon:.5f}",
        "daily":     "sunrise,sunset,moonrise,moonset,moon_phase",
        "timezone":  TZ_NAME,
        "timeformat":"iso8601",
        "start_date":start_date.isoformat(),
        "end_date":  end_date.isoformat(),
    }
    return "https://api.open-meteo.com/v1/astronomy?" + urlencode(params)
    
### PATCH 5 — helpers: détection/greffe des DAILY si manquants/incomplets
def _needs_daily_backfill(p: Dict[str, Any]) -> bool:
    """True si daily manque l'une des clés d'astronomie ou est vide."""
    d = (p.get("daily") or {})
    for k in ASTRONOMY_DAILY_KEYS:  # ["sunrise","sunset","moonrise","moonset","moon_phase"]
        arr = d.get(k)
        if not isinstance(arr, list) or len(arr) == 0:
            return True
    return False

# PATCH astro/daily — fusion robuste + alignement par dates
def _attach_daily_best_effort(p: Dict[str, Any], lat: float, lon: float) -> None:
    """
    Remplit/complète p['daily'] et p['daily_units'] avec:
      - /v1/forecast (sunrise, sunset)
      - /v1/astronomy (moonrise, moonset, moon_phase)
    Règles:
      - On crée les sections si absentes.
      - On respecte l’axe temporel du forecast daily s’il existe, sinon on prend celui reçu.
      - On n’écrase pas une clé déjà présente avec des nulls.
      - On tronque/étend proprement pour faire correspondre les longueurs aux dates.
    """
    p.setdefault("daily", {})
    p.setdefault("daily_units", {})

    def _merge_daily(dst: Dict[str, Any], src: Dict[str, Any]) -> None:
        """Fusionne src.daily dans dst.daily en préservant valeurs existantes non-nulles."""
        s_daily = (src.get("daily") or {})
        if not isinstance(s_daily, dict):
            return
        # Axe temps de référence
        ref_time = dst["daily"].get("time") or s_daily.get("time")
        if not isinstance(ref_time, list) or not ref_time:
            ref_time = s_daily.get("time") or []
            if ref_time:
                dst["daily"]["time"] = ref_time

        # Map temps -> index pour re-sampler les autres séries
        idx_src = {t: i for i, t in enumerate(s_daily.get("time") or [])}

        for k, arr in s_daily.items():
            if k == "time":
                continue
            if not isinstance(arr, list):
                continue
            # Re-échantillonnage sur l’axe ref_time si besoin
            if s_daily.get("time") and s_daily["time"] != ref_time:
                new_arr: List[Optional[Any]] = []
                for t in ref_time:
                    i = idx_src.get(t)
                    new_arr.append(arr[i] if i is not None and i < len(arr) else None)
            else:
                new_arr = list(arr)

            # Injecte seulement si la clé manque ou est vide; n’écrase pas des valeurs non-nulles
            if k not in dst["daily"] or not isinstance(dst["daily"][k], list) or not dst["daily"][k]:
                dst["daily"][k] = new_arr
            else:
                # complète élément par élément si dst possède des trous (None)
                dst_arr = dst["daily"][k]
                # harmonise les longueurs
                if len(dst_arr) < len(ref_time):
                    dst_arr = dst_arr + [None] * (len(ref_time) - len(dst_arr))
                if len(new_arr) < len(ref_time):
                    new_arr = new_arr + [None] * (len(ref_time) - len(new_arr))
                for i in range(min(len(dst_arr), len(new_arr))):
                    if dst_arr[i] is None and new_arr[i] is not None:
                        dst_arr[i] = new_arr[i]
                dst["daily"][k] = dst_arr

        # Units
        for uk, uv in (src.get("daily_units") or {}).items():
            if uk not in dst["daily_units"]:
                dst["daily_units"][uk] = uv

    # a) /v1/forecast : soleil
    try:
        durl = daily_only_url(lat, lon)  # doit inclure sunrise,sunset (+ time)
        dd   = http_get_json(durl, retry=HTTP_RETRIES, timeout=HTTP_TIMEOUT_S)
        log.info("  DAILY backfill: forecast keys=%s", list((dd.get("daily") or {}).keys()))
        if isinstance(dd, dict) and dd.get("daily"):
            _merge_daily(p, dd)
        log.info("  DAILY backfill: forecast attached.")
    except Exception as e:
        log.debug("  DAILY backfill (forecast) failed: %s", e)

    # b) /v1/astronomy : lune
    try:
        aurl = astronomy_url(lat, lon)   # moonrise,moonset,moon_phase (+ time)
        aa   = http_get_json(aurl, retry=HTTP_RETRIES, timeout=HTTP_TIMEOUT_S)
        log.info("  DAILY backfill: astronomy keys=%s", list((aa.get("daily") or {}).keys()))
        if isinstance(aa, dict) and aa.get("daily"):
            _merge_daily(p, aa)
        log.info("  DAILY backfill: astronomy attached.")
    except Exception as e:
        log.debug("  DAILY backfill (astronomy) failed: %s", e)

    # c) Nettoyage : s’assurer que les 5 clés existent (même si None)
    for k in ("sunrise", "sunset", "moonrise", "moonset", "moon_phase"):
        p["daily"].setdefault(k, [])
        p["daily_units"].setdefault(k, "iso8601" if k in ("sunrise", "sunset", "moonrise", "moonset") else "fraction")


def marine_url(lat: float, lon: float) -> str:
    params = {
        "latitude":        f"{lat:.5f}",
        "longitude":       f"{lon:.5f}",
        "hourly":          ",".join(MARINE_KEYS),
        "timezone":        TZ_NAME,
        "timeformat":      "iso8601",
        "wave_height_unit":"m",
        "start_date":      start_date.isoformat(),
        "end_date":        end_date.isoformat(),
    }
    return "https://marine-api.open-meteo.com/v1/marine?" + urlencode(params)
    
# PATCH 4 — helper: fetch only daily astro even in SAFE mode
def daily_only_url(lat: float, lon: float) -> str:
    params = {
        "latitude":  f"{lat:.5f}",
        "longitude": f"{lon:.5f}",
        "daily":     ",".join(DAILY_KEYS),
        "timezone":  TZ_NAME,
        "timeformat":"iso8601",
        "start_date":start_date.isoformat(),
        "end_date":  end_date.isoformat(),
    }
    return "https://api.open-meteo.com/v1/forecast?" + urlencode(params)

def _has_non_null(arr: List) -> bool:
    return isinstance(arr, list) and any(v is not None for v in arr)

def has_wind_arrays(payload: Dict[str, Any]) -> bool:
    h = payload.get("hourly") or {}
    return _has_non_null(first_series(h, "wind_speed_10m")) and _has_non_null(first_series(h, "wind_gusts_10m"))
    
def payload_has_error(p: Dict[str, Any]) -> bool:
    if not isinstance(p, dict):
        return True
    if p.get("error"):
        return True
    h = p.get("hourly")
    if not isinstance(h, dict):
        return True
    t = h.get("time")
    if not isinstance(t, list) or len(t) == 0:
        return True
    return False

def api_reason(p: Dict[str, Any]) -> str:
    if isinstance(p, dict):
        return str(p.get("reason") or p.get("error_message") or "hourly/time missing")
    return "invalid json"

# Alias de modèles (au cas où “*_seamless” n’est pas accepté par l’API)
MODEL_ALIASES = {
    # Modèles officiellement acceptés par Open-Meteo
    "ecmwf_ifs04": ["ecmwf_ifs04"],
    "icon_seamless": ["icon_seamless"],
    "gfs_seamless": ["gfs_seamless"],
    "default": ["default", None],  # None => pas de param ?models= (laisser l’API choisir)
}
def expand_models(order: List[str]) -> List[Optional[str]]:
    out: List[Optional[str]] = []
    for m in order:
        out.extend(MODEL_ALIASES.get(m, [m]))
    # supprime doublons en conservant l’ordre
    seen=set(); dedup=[]
    for m in out:
        key = m or "default"
        if key in seen: 
            continue
        seen.add(key); dedup.append(m)
    return dedup

SAFE_HOURLY = ["wind_speed_10m","wind_gusts_10m","wind_direction_10m","weather_code","visibility"]

def fetch_forecast(lat: float, lon: float, site_deadline: float) -> Dict[str, Any]:
    # 1) Essais avec jeu complet (ECMWF_KEYS) + alias de modèles
    for model in expand_models(MODEL_ORDER):
        log.debug("  trying model=%s", model or "default")
        if time.monotonic() > site_deadline:
            log.warning("⏱️ site budget presque dépassé → on saute aux fallbacks (sans 'models').")
            break
        url = forecast_url(lat, lon, model, hourly_keys=ECMWF_KEYS, include_daily=True)
        try:
            p = http_get_json(url, retry=HTTP_RETRIES, timeout=HTTP_TIMEOUT_S)
            if payload_has_error(p):
                log.warning("  ⚠ model %s invalid payload: %s", model or "default", api_reason(p))
                continue
            p = normalize_hourly_keys(p)
            if has_wind_arrays(p):
                p["_model_used"] = "safe_default"
                log.info("  ✔ forecast SAFE mode used.")
                _attach_daily_best_effort(p, lat, lon)  # SAFE: on backfill d’office
                return p        
            else:
                log.warning("  ⚠ model %s has empty wind arrays, trying next...", model or "default")
        except Exception as e:
            log.warning("  ⚠ request failed for model %s: %s", model or "default", e)

    # 2) Fallback n°1 : même set complet mais SANS 'models'
    log.warning("  ↩︎ All models failed; retry WITHOUT 'models' (ECMWF_KEYS).")
    try:
        url = forecast_url(lat, lon, None, hourly_keys=ECMWF_KEYS, include_daily=True)  # pas de &models=
        p = http_get_json(url, retry=HTTP_RETRIES, timeout=HTTP_TIMEOUT_S)
        if not payload_has_error(p):
            p = normalize_hourly_keys(p)
            if has_wind_arrays(p):
                p["_model_used"] = "default"
                log.info("  ✔ forecast default (no 'models') used.")
                if _needs_daily_backfill(p):
                    _attach_daily_best_effort(p, lat, lon)
                return p
            else:
                log.warning("  ⚠ default(no 'models'): wind arrays empty.")
        else:
            log.warning("  ⚠ default(no 'models') invalid payload: %s", api_reason(p))
    except Exception as e:
        log.warning("  ⚠ default(no 'models') request failed: %s", e)

    # 3) Fallback n°2 : SAFE minimal (sans daily)
    log.warning("  ↩︎ Fallback SAFE set (no daily, SAFE_HOURLY).")
    try:
        url = forecast_url(lat, lon, None, hourly_keys=SAFE_HOURLY, include_daily=False)
        p = http_get_json(url, retry=HTTP_RETRIES, timeout=HTTP_TIMEOUT_S)
        if not payload_has_error(p):
            p = normalize_hourly_keys(p)
            if has_wind_arrays(p):
                p["_model_used"] = "safe_default"
                log.info("  ✔ forecast SAFE mode used.")
                # SAFE n’a pas de daily → on backfill d’office
                _attach_daily_best_effort(p, lat, lon)
                return p
            else:
                log.warning("  ⚠ SAFE mode: wind arrays still empty.")
        else:
            log.warning("  ⚠ SAFE mode invalid payload: %s", api_reason(p))
    except Exception as e:
        log.warning("  ⚠ SAFE mode request failed: %s", e)

    # 4) Échec complet
    return {"_model_used": "unknown", "hourly": {}}


def fetch_marine(lat: float, lon: float, site_deadline: float) -> Dict[str, Any]:
    if time.monotonic() > site_deadline:
        raise TimeoutError("site budget exceeded (marine)")
    p = http_get_json(marine_url(lat, lon), retry=HTTP_RETRIES, timeout=HTTP_TIMEOUT_S)
    if payload_has_error(p):
        log.warning("  ⚠ marine payload invalid: %s", api_reason(p))
        # on laisse normalize pour tenter de récupérer les clés canoniques
    return normalize_hourly_keys(p)


def slice_by_indices(payload: Dict[str, Any], keys: List[str], keep_idx: List[int]) -> Dict[str, Any]:
    h = payload.get("hourly") or {}
    times = h.get("time") or []
    out: Dict[str, Any] = {}
    out["time"] = [times[i] for i in keep_idx if i < len(times)]
    for k in keys:
        series = first_series(h, k)
        if series:
            out[k] = [series[i] for i in keep_idx if i < len(series)]
    return out

# ---------- NOUVEAU : alignement robuste par INTERSECTION des timestamps ----------
def flatten_hourly_aligned(ecmwf_slice: Dict[str, Any], marine_slice: Dict[str, Any]) -> Dict[str, List]:
    te = ecmwf_slice.get("time") or []
    tm = marine_slice.get("time") or []

    if te and tm:
        set_tm = set(tm)
        time_axis = [t for t in te if t in set_tm]  # préserve l’ordre du forecast
        # si intersection vide, on prend l’UNION ordonnée
        if not time_axis:
            union = sorted(set(te) | set(tm))
            time_axis = union
    else:
        time_axis = te or tm

    # maps temps -> index
    idx_e = {t:i for i, t in enumerate(te)}
    idx_m = {t:i for i, t in enumerate(tm)}

    def pick_aligned(src: Dict[str, Any], key: str, idx_map: Dict[str, int]) -> List[Optional[float]]:
        arr = src.get(key) or []
        out: List[Optional[float]] = []
        for t in time_axis:
            i = idx_map.get(t)
            if i is None or i >= len(arr):
                out.append(None)
            else:
                out.append(arr[i])
        return out

    flat: Dict[str, List] = {"time": time_axis}

    for k in ["wind_speed_10m","wind_gusts_10m","wind_direction_10m","weather_code","visibility","surface_pressure","precipitation"]:
        if k in ecmwf_slice:
            flat[k] = pick_aligned(ecmwf_slice, k, idx_e)

    for k in ["wave_height","wave_period"]:
        if k in marine_slice:
            flat[k] = pick_aligned(marine_slice, k, idx_m)

    if "wave_height" in flat: flat["hs"] = flat["wave_height"]
    if "wave_period" in flat: flat["tp"] = flat["wave_period"]
    return flat
# -------------------------------------------------------------------------------

def non_null_count(d: Dict[str, Any], keys: List[str]) -> Dict[str, int]:
    out = {}
    for k in keys:
        arr = d.get(k) or []
        out[k] = sum(1 for x in arr if x is not None)
    return out

# -----------------------
# Collecte
# -----------------------
ROOT    = Path(__file__).resolve().parent
PUBLIC  = ROOT / "public"
ensure_dir(PUBLIC)

results = []
t0_global = time.monotonic()
global_deadline = t0_global + HARD_BUDGET_S

def _len_series(h: Dict[str, Any], key: str) -> int:
    arr = first_series(h or {}, key)
    return len(arr) if isinstance(arr, list) else 0

for site in selected_sites:
    if time.monotonic() > global_deadline:
        log.error("⏱️ Budget global dépassé — arrêt anticipé."); break

    name = site["name"]; slug = site["slug"]; lat = site["lat"]; lon = site["lon"]
    log.info("▶ Collecte: %s (%.5f, %.5f)", name, lat, lon)
    log.debug("  forecast URL (model order=%s) will be built per-attempt", "/".join(MODEL_ORDER))
    log.debug("  marine   URL: %s", marine_url(lat, lon))
 

    site_deadline = time.monotonic() + SITE_BUDGET_S
    try:
        wx  = fetch_forecast(lat, lon, site_deadline)   # fallback ECMWF→ICON→GFS→default
        sea = fetch_marine(lat, lon, site_deadline)
    except Exception as e:
        log.error("Échec de collecte pour %s: %s", name, e); continue

    # ➕ Dumps bruts optionnels (avant slicing)
    if DEBUG_DUMP:
        (PUBLIC / f"_debug-forecast-{slug}.json").write_text(json.dumps(wx,  ensure_ascii=False, indent=2), encoding="utf-8")
        (PUBLIC / f"_debug-marine-{slug}.json").write_text(  json.dumps(sea, ensure_ascii=False, indent=2), encoding="utf-8")

    # Télémétrie bruts AVANT slicing
    h_wx  = wx.get("hourly")  or {}
    h_sea = sea.get("hourly") or {}
    log.info("  raw forecast: time=%d wind=%d gust=%d dir=%d vis=%d | marine: time=%d hs=%d tp=%d",
             len(h_wx.get("time") or []),
             _len_series(h_wx, "wind_speed_10m"),
             _len_series(h_wx, "wind_gusts_10m"),
             _len_series(h_wx, "wind_direction_10m"),
             _len_series(h_wx, "visibility"),
             len(h_sea.get("time") or []),
             _len_series(h_sea, "wave_height"),
             _len_series(h_sea, "wave_period"))

    # --- indices fenêtre (séparés par source) ---
    wx_times  = (wx.get("hourly")  or {}).get("time") or []
    sea_times = (sea.get("hourly") or {}).get("time") or []
    keep_wx   = indices_in_window(wx_times,  start_local, end_local, TZ)
    keep_sea  = indices_in_window(sea_times, start_local, end_local, TZ)

    ecmwf_slice  = slice_by_indices(wx,  ECMWF_KEYS,  keep_wx)
    marine_slice = slice_by_indices(sea, MARINE_KEYS, keep_sea)

    # ⚠️ NOUVEAU : agrégat aligné sur intersection des heures
    hourly_flat  = flatten_hourly_aligned(ecmwf_slice, marine_slice)

    # Télémétrie APRÈS slicing + alignement
    log.info("  sliced forecast: time=%d wind=%d gust=%d dir=%d vis=%d | sliced marine: time=%d hs=%d tp=%d",
             len(ecmwf_slice.get("time") or []),
             len(ecmwf_slice.get("wind_speed_10m") or []),
             len(ecmwf_slice.get("wind_gusts_10m") or []),
             len(ecmwf_slice.get("wind_direction_10m") or []),
             len(ecmwf_slice.get("visibility") or []),
             len(marine_slice.get("time") or []),
             len(marine_slice.get("wave_height") or []),
             len(marine_slice.get("wave_period") or []))
    log.info("  aligned axis: %d hours | first=%s | last=%s",
             len(hourly_flat.get("time") or []),
             (hourly_flat.get("time") or [None])[0],
             (hourly_flat.get("time") or [None])[-1])

    e_units = wx.get("hourly_units", {}) or {}
    m_units = sea.get("hourly_units", {}) or {}
    d_units = wx.get("daily_units",  {}) or {}
    daily   = wx.get("daily",        {}) or {}

    # Debug meta
    wx_keys_raw  = sorted(list((wx.get("hourly")  or {}).keys()))
    sea_keys_raw = sorted(list((sea.get("hourly") or {}).keys()))
    nn_ecmwf = non_null_count(ecmwf_slice, ["wind_speed_10m","wind_gusts_10m","wind_direction_10m","weather_code","visibility","surface_pressure","precipitation"])
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
                    "model_order": MODEL_ORDER,
                    "model_used": wx.get("_model_used", "unknown"),
                    "units": e_units,
                },
                "marine_open_meteo": {
                    "endpoint": "https://marine-api.open-meteo.com/v1/marine",
                    "units": m_units,
                },
                "astro_daily_open_meteo": {
                    "endpoint":"https://api.open-meteo.com/v1/forecast",
                    "units": d_units
                },
            },
            "shelter_bonus_radius_km": site.get("shelter_bonus_radius_km", 0.0),
            "debug": {
                "hourly_keys_present_forecast": wx_keys_raw,
                "hourly_keys_present_marine": sea_keys_raw,
                "ecmwf_non_null_counts": nn_ecmwf,
                "marine_non_null_counts": nn_marine,
                "kept_indices": {
                    "forecast": keep_wx[:6] + (["..."] if len(keep_wx) > 6 else []),
                    "marine":   keep_sea[:6] + (["..."] if len(keep_sea) > 6 else []),
                },
                "budgets": {"site_s": SITE_BUDGET_S, "global_s": HARD_BUDGET_S}
            },
        },
        "ecmwf": ecmwf_slice,
        "marine": marine_slice,
        "daily": daily,
        "hourly": hourly_flat,
        "status": "ok",
    }

    tmp = PUBLIC / f".{slug}.json.tmp"
    final = PUBLIC / f"{slug}.json"
    tmp.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    tmp.replace(final)

    results.append({
        "slug": slug,
        "name": name,
        "points": len(hourly_flat.get("time", []) or []),
        "first_time": (hourly_flat.get("time") or [None])[0],
        "last_time":  (hourly_flat.get("time") or [None])[-1],
        "path": f"{slug}.json"
    })

ok = [r for r in results if r["points"] > 0]
log.info("Terminé: %d/%d spots écrits (avec données horaires dans la fenêtre).", len(ok), len(selected_sites))
if not ok:
    log.error("Aucune donnée horaire dans la fenêtre demandée — vérifier paramètres/timezone.")
    sys.exit(2)

# ---------- NOUVEAU : index.json léger pour la page GitHub ----------
index_payload = {
    "generated_at": dt.datetime.now(TZ).isoformat(),
    "tz": TZ_NAME,
    "window": {
        "start_local": start_local.isoformat(),
        "end_local": end_local.isoformat(),
        "hours": int((end_local - start_local).total_seconds() // 3600),
    },
    "spots": ok,  # liste déjà préparée (slug, name, points, first/last, path)
}
(PUBLIC / "index.json").write_text(json.dumps(index_payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
# ---------------------------------------------------------------
