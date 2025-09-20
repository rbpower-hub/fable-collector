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
import hashlib
import datetime as dt
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from urllib.parse import urlencode
from zoneinfo import ZoneInfo
import requests  # urllib.request est inutile ici, tu peux le retirer si non utilisé

# -----------------------
# Config & budgets
# -----------------------
HTTP_TIMEOUT_S       = int(os.getenv("FABLE_HTTP_TIMEOUT_S", "10"))
HTTP_RETRIES         = int(os.getenv("FABLE_HTTP_RETRIES", "1"))
MODEL_ORDER          = [m.strip() for m in os.getenv(
    "FABLE_MODEL_ORDER", "icon_seamless,gfs_seamless,ecmwf_ifs04,default"
).split(",") if m.strip()]
SITE_BUDGET_S        = int(os.getenv("FABLE_SITE_BUDGET_S", "90"))
HARD_BUDGET_S        = int(os.getenv("FABLE_HARD_BUDGET_S", "240"))

# Logger (unique)
log = logging.getLogger("fable-collector")
if not logging.getLogger().handlers:
    logging.basicConfig(
        level=getattr(logging, os.getenv("LOGLEVEL","INFO"), "INFO"),
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

# Dossier public : auto-détection + unification
ROOT = Path(__file__).resolve().parent
PUBLIC = ROOT / "Public"
PUBLIC.mkdir(parents=True, exist_ok=True)

# On unifie tout le code sur un alias unique
PUBLIC.mkdir(parents=True, exist_ok=True)  # à la place de ensure_dir(PUBLIC)

# Modèles parallèles à tenter (en plus du primaire choisi pour hourly)
PARALLEL_MODELS        = [m.strip() for m in os.getenv(
    "FABLE_PARALLEL_MODELS", "ecmwf_ifs04,icon_seamless,gfs_seamless"
).split(",") if m.strip()]
PARALLEL_TIMEOUT_S     = int(os.getenv("FABLE_PARALLEL_TIMEOUT_S", "10"))
PARALLEL_RETRIES       = int(os.getenv("FABLE_PARALLEL_RETRIES", "0"))  # appels parallèles = best-effort

# ➕ Debug dumps activables
DEBUG_DUMP = os.getenv("FABLE_DEBUG_DUMP", "0") == "1"
# Extras optionnels (activables sans impacter la logique)
INCLUDE_EXTRAS = os.getenv("FABLE_INCLUDE_EXTRAS", "0") == "1"
EXTRA_HOURLY   = ["relative_humidity_2m", "cloud_cover"]  # variables largement supportées

# Fallback astro local (optionnel)
ASTRAL_FALLBACK = os.getenv("FABLE_ASTRAL_FALLBACK", "1") == "1"
try:
    from astral import Observer
    from astral.moon import moonrise as _astral_moonrise, moonset as _astral_moonset, phase as _astral_phase
except Exception:
    Observer = None
    _astral_moonrise = _astral_moonset = _astral_phase = None
    
log.info("Astral ready=%s", ASTRAL_FALLBACK and (Observer is not None) and (_astral_moonrise is not None))

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

# --- HTTP robuste: Session + connect/read timeouts + backoff 0.5→1→2→4 ---
SESSION = requests.Session()

def http_get_json(url: str, retry: int | None = None, timeout: int | float | None = None):
    # fallback si les constantes ne sont pas encore définies
    try:
        _retries = retry if retry is not None else int(os.getenv("FABLE_HTTP_RETRIES", "1"))
    except Exception:
        _retries = 1
    try:
        _timeout = float(timeout if timeout is not None else os.getenv("FABLE_HTTP_TIMEOUT_S", "10"))
    except Exception:
        _timeout = 10.0

    backoffs = [0.5, 1.0, 2.0, 4.0]
    connect_read = (3.0, _timeout)
    last_err = None
    for attempt in range(min(_retries + 1, len(backoffs) + 1)):
        try:
            r = SESSION.get(
                url,
                timeout=connect_read,
                headers={"User-Agent": "fable-collector/1.5 (+github actions)"}
            )
            r.raise_for_status()
            return r.json()
        except Exception as e:
            last_err = e
            if attempt < len(backoffs):
                time.sleep(backoffs[attempt])
            else:
                break
    raise RuntimeError(f"GET failed after retries: {last_err}")

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
    else:
        t = t.astimezone(tz)
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
ONLY     = csv_to_set(os.getenv("FABLE_ONLY_SITES", ""))

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

# --- Normalisation DAILY: forcer TZ-aware (+01:00) au format ISO minutes ---
def _iso_min_with_tz(x: str) -> str | None:
    if x is None or not isinstance(x, str):
        return None
    try:
        t = dt.datetime.fromisoformat(x)
    except Exception:
        # Si format inattendu, on renvoie tel quel (évite d'effacer des valeurs)
        return x
    if t.tzinfo is None:
        t = t.replace(tzinfo=TZ)
    else:
        t = t.astimezone(TZ)
    return t.isoformat(timespec="minutes")

def _normalize_daily_timezones_inplace(p: Dict[str, Any]) -> None:
    d = p.get("daily") or {}
    for key in ("sunrise", "sunset", "moonrise", "moonset"):
        arr = d.get(key)
        if isinstance(arr, list) and arr:
            d[key] = [_iso_min_with_tz(v) for v in arr]
    p["daily"] = d

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
# ASTRONOMY_DAILY_KEYS = ["sunrise", "sunset", "moonrise", "moonset", "moon_phase"]

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
        "wind_speed_unit":"kmh",
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
    d = p.get("daily") or {}
    for k in ("sunrise", "sunset", "moonrise", "moonset", "moon_phase"):
        arr = d.get(k)
        if not isinstance(arr, list) or len(arr) == 0 or all(v is None for v in arr):
            return True
    return False
    
def _iter_dates(d0: dt.date, d1: dt.date):
    cur = d0
    while cur <= d1:
        yield cur
        cur += dt.timedelta(days=1)

def _astral_backfill_daily(p: Dict[str, Any], lat: float, lon: float) -> None:
    """Complète moonrise/moonset/moon_phase offline via astral si l’API astronomy échoue."""
    if not ASTRAL_FALLBACK or Observer is None or _astral_moonrise is None:
        log.info("  DAILY backfill (astral) non disponible (lib manquante ou désactivée).")
        return

    p.setdefault("daily", {})
    p.setdefault("daily_units", {})

    # Axe de dates : on réutilise daily.time si présent, sinon start_date..end_date inclus
    ref_dates = p["daily"].get("time")
    if not isinstance(ref_dates, list) or not ref_dates:
        ref_dates = [d.isoformat() for d in _iter_dates(start_date, end_date)]
        p["daily"]["time"] = ref_dates

    observer = Observer(latitude=lat, longitude=lon)
    tz = TZ

    moonrise_arr, moonset_arr, phase_arr = [], [], []
    for ds in ref_dates:
        try:
            d = dt.date.fromisoformat(ds)
        except Exception:
            # si format inattendu, on saute ce jour
            moonrise_arr.append(None); moonset_arr.append(None); phase_arr.append(None)
            continue

        try:
            mr = _astral_moonrise(observer, d, tzinfo=tz)
        except Exception:
            mr = None
        try:
            ms = _astral_moonset(observer, d, tzinfo=tz)
        except Exception:
            ms = None
        try:
            # astral.phase retourne un jour lunaire (0..29.x). Converti en fraction 0..1.
            ph = _astral_phase(d)
            ph_frac = round(float(ph) / 29.530588, 3)
        except Exception:
            ph_frac = None
            
        def _fmt_local_naive(dt_obj):
            # convertit en TZ locale Africa/Tunis, puis drop le tzinfo pour "YYYY-MM-DDTHH:MM"
            return dt_obj.astimezone(TZ).replace(tzinfo=None).isoformat(timespec="minutes")
            
        mr_s = _fmt_local_naive(mr) if isinstance(mr, dt.datetime) else None
        ms_s = _fmt_local_naive(ms) if isinstance(ms, dt.datetime) else None
        moonrise_arr.append(mr_s)
        moonset_arr.append(ms_s)
        phase_arr.append(ph_frac)
        
    # ---- Fusion sans écraser les valeurs non-nulles déjà présentes
    def _merge_if_empty(key: str, arr_new: list):
        # Harmoniser arr_new à l'axe ref_dates
        ref_len = len(ref_dates)
        arr_new = list(arr_new)
        if len(arr_new) < ref_len:
            arr_new += [None] * (ref_len - len(arr_new))
        elif len(arr_new) > ref_len:
            arr_new = arr_new[:ref_len]

        cur = p["daily"].get(key)
        if not isinstance(cur, list) or len(cur) == 0:
            p["daily"][key] = arr_new
            return

        cur = list(cur)
        if len(cur) < ref_len:
            cur += [None] * (ref_len - len(cur))
        elif len(cur) > ref_len:
            cur = cur[:ref_len]

        # Compléter uniquement les trous
        for i in range(ref_len):
            if cur[i] is None and arr_new[i] is not None:
                cur[i] = arr_new[i]
        p["daily"][key] = cur

    _merge_if_empty("moonrise",  moonrise_arr)
    _merge_if_empty("moonset",   moonset_arr)
    _merge_if_empty("moon_phase", phase_arr)

    # Unités garanties
    p["daily_units"].setdefault("moonrise",  "iso8601")
    p["daily_units"].setdefault("moonset",   "iso8601")
    p["daily_units"].setdefault("moon_phase","fraction")

    log.info("  DAILY backfill: astronomy (astral) attached.")

# -----------------------
# Règles FABLE (rules.yaml) — chargement tolérant
# -----------------------
def _dget(dct, path, default=None):
    cur = dct
    for part in path.split('.'):
        if not isinstance(cur, dict) or part not in cur:
            return default
        cur = cur[part]
    return cur

def load_rules_yaml():
    """
    Charge rules.yaml depuis la racine du repo (ou chemin fourni par FABLE_RULES_PATH).
    Si indisponible, retourne un petit set de défauts pour ne pas casser.
    """
    path = os.getenv("FABLE_RULES_PATH", "rules.yaml")
    p = Path(path)
    default_rules = {
        "overrides": {"thunder_wmo": [95,96,99], "gusts_hard_nogo_kmh": 30, "squall_delta_kmh": 17},
        "wind": {"family_max_kmh": 20, "nogo_min_kmh": 25, "onshore_degrade_kmh": 22},
        "sea": {"family_max_hs_m": 0.5, "nogo_min_hs_m": 0.8},
        "tp_matrix": {
            "transit": {
                "hs_lt_0_4_family_tp_s": 4.0,
                "hs_0_4_0_5_family_tp_s": 4.5,
                "hs_lt_0_4_expert_tp_min_s": 3.6,
                "hs_0_4_0_5_expert_tp_min_s": 4.0,
            },
            "anchor_sheltered": {
                "hs_le_0_35_family_tp_s": 3.8,
                "hs_le_0_35_expert_tp_min_s": 3.5,
            },
        },
        "hysteresis": {"wind_kmh": 1.0, "hs_m": 0.05},
        "shelter": {
            "radius_km_default": 3,
            "apply_on_transit": False,
            "anchor_gusts_allow_up_to_kmh": 34,
            "anchor_squall_delta_max_kmh": 20,
            "require_lee": True,
            "max_fetch_km": 1.5,
        },
        "resolution_policy": {
            "family_requires_hourly": True,
            "expert_allows_3h": True,
            "second_model_required_for_medium": True,
        },
        "confidence": {
            "high": {"wind_spread_kmh_lt": 5, "hs_spread_m_lt": 0.2},
            "medium": {"same_band_minor_disagreement": True},
            "low": {"cross_band_disagreement_or_3h": True},
        },
        "corridor": {
            "samples": 9,
            "validate_departure_and_return": True,
            "leg_structure_hours": {"transit_out": "1-1.5", "anchor_min": 2, "anchor_max": 4, "transit_back": "1-1.5"},
        },
        "family_hours_local": {"start_h": 8, "end_h": 21},
    }
    try:
        if p.exists():
            data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
            # merge superficiel (on garde default si manquant)
            def deep_merge(dst, src):
                for k, v in src.items():
                    if isinstance(v, dict) and isinstance(dst.get(k), dict):
                        deep_merge(dst[k], v)
                    else:
                        dst[k] = v
                return dst
            return deep_merge(default_rules, data)
        else:
            log.warning("rules.yaml introuvable (%s) — utilisation des règles par défaut.", p)
            return default_rules
    except Exception as e:
        log.warning("Lecture rules.yaml échouée (%s) — utilisation des règles par défaut.", e)
        return default_rules

def rules_digest_sha(rules: dict) -> str:
    try:
        raw = json.dumps(rules, sort_keys=True, ensure_ascii=False).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()[:12]
    except Exception:
        return "unknown"

# Charger le ruleset (exposé en meta, pas de logique collector changée)
RULES = load_rules_yaml()
RULES_DIGEST = rules_digest_sha(RULES)
log.info("[rules] loaded digest=%s (squall_delta=%s, onshore=%s, family_hours=%s-%s)",
         RULES_DIGEST,
         _dget(RULES, "overrides.squall_delta_kmh", 17),
         _dget(RULES, "wind.onshore_degrade_kmh", 22),
         _dget(RULES, "family_hours_local.start_h", 8),
         _dget(RULES, "family_hours_local.end_h", 21))
# --- feature flag (rules.yaml + ENV) pour couper l'HTTP astronomy ---
DISABLE_ASTRONOMY_HTTP = bool(_dget(RULES, "http.disable_astronomy_http", False)) \
                         or (os.getenv("FABLE_DISABLE_ASTRONOMY_HTTP", "1") == "1")


# PATCH astro/daily — fusion robuste + alignement par dates
def _attach_daily_best_effort(p: Dict[str, Any], lat: float, lon: float) -> None:
    """
    Remplit/complète p['daily'] et p['daily_units'] avec :
      - /v1/forecast (sunrise, sunset) si manquants
      - /v1/astronomy (moonrise, moonset, moon_phase) si manquants
    Règles :
      - On crée les sections si absentes.
      - On respecte l’axe temporel 'time' si déjà présent ; sinon on adopte celui reçu.
      - On n’écrase pas des valeurs existantes par des nulls ; on comble seulement les trous.
      - On rééchantillonne si les dates ne correspondent pas exactement.
    """
    p.setdefault("daily", {})
    p.setdefault("daily_units", {})

    # ---------- utilitaires locaux ----------
    def _non_empty(arr) -> bool:
        return isinstance(arr, list) and any(v is not None for v in arr)

    def _merge_daily(dst: Dict[str, Any], src: Dict[str, Any]) -> None:
        s_daily = (src.get("daily") or {})
        if not isinstance(s_daily, dict):
            return

        # Axe temporel de référence
        ref_time = dst["daily"].get("time") or s_daily.get("time") or []
        if ref_time and dst["daily"].get("time") != ref_time:
            dst["daily"]["time"] = ref_time

        # Index source pour re-sampler
        idx_src = {t: i for i, t in enumerate(s_daily.get("time") or [])}

        # Fusion
        for k, arr in s_daily.items():
            if k == "time" or not isinstance(arr, list):
                continue

            if s_daily.get("time") and ref_time and s_daily["time"] != ref_time:
                new_arr = []
                for t in ref_time:
                    i = idx_src.get(t)
                    new_arr.append(arr[i] if i is not None and i < len(arr) else None)
            else:
                new_arr = list(arr)

            if k not in dst["daily"] or not isinstance(dst["daily"][k], list) or not dst["daily"][k]:
                dst["daily"][k] = new_arr
            else:
                dst_arr = list(dst["daily"][k])
                if len(dst_arr) < len(ref_time):
                    dst_arr += [None] * (len(ref_time) - len(dst_arr))
                if len(new_arr) < len(ref_time):
                    new_arr += [None] * (len(ref_time) - len(new_arr))
                for i in range(min(len(dst_arr), len(new_arr))):
                    if dst_arr[i] is None and new_arr[i] is not None:
                        dst_arr[i] = new_arr[i]
                dst["daily"][k] = dst_arr

        # Units
        for uk, uv in (src.get("daily_units") or {}).items():
            if uk not in dst["daily_units"]:
                dst["daily_units"][uk] = uv

        # S'assure que 'time' existe
        if "time" not in dst["daily"]:
            if isinstance(s_daily.get("time"), list):
                dst["daily"]["time"] = s_daily["time"]

    # ---------- on ne requête que ce qui manque ----------
    have_sun = _non_empty(p["daily"].get("sunrise")) and _non_empty(p["daily"].get("sunset"))
    have_moon = _non_empty(p["daily"].get("moonrise")) and _non_empty(p["daily"].get("moonset")) and _non_empty(p["daily"].get("moon_phase"))

    # a) /v1/forecast : uniquement si sunrise/sunset manquants
    if not have_sun:
        try:
            durl = daily_only_url(lat, lon)
            log.debug("  DAILY backfill: forecast URL=%s", durl)
            dd = http_get_json(durl, retry=HTTP_RETRIES, timeout=HTTP_TIMEOUT_S)
            if isinstance(dd, dict) and dd.get("daily"):
                _merge_daily(p, dd)
                log.info("  DAILY backfill: forecast keys=%s", list((dd.get("daily") or {}).keys()))
                have_sun = _non_empty(p["daily"].get("sunrise")) and _non_empty(p["daily"].get("sunset"))
            else:
                log.warning("  DAILY backfill: forecast returned no daily.")
        except Exception as e:
            log.debug("  DAILY backfill (forecast) failed: %s", e)

    # b) /v1/astronomy : uniquement si moon* manquants ET si non désactivé
    if not have_moon and not DISABLE_ASTRONOMY_HTTP:
        try:
            aurl = astronomy_url(lat, lon)
            log.debug("  DAILY backfill: astronomy URL=%s", aurl)
            # appel non bloquant : pas de retry, timeout court
            aa = http_get_json(aurl, retry=0, timeout=min(HTTP_TIMEOUT_S, 6))
            if isinstance(aa, dict) and aa.get("daily"):
                _merge_daily(p, aa)
                log.info("  DAILY backfill: astronomy keys=%s", list((aa.get("daily") or {}).keys()))
                have_moon = _non_empty(p["daily"].get("moonrise")) and _non_empty(p["daily"].get("moonset")) and _non_empty(p["daily"].get("moon_phase"))
            else:
                log.warning("  DAILY backfill: astronomy returned no daily.")
        except Exception as e:
            log.warning("  DAILY backfill (astronomy) failed: %s — retrying without timeformat", e)
            # Variante sans timeformat (certains edges retournent 404)
            try:
                def astronomy_url_no_tf(lat: float, lon: float) -> str:
                    params = {
                        "latitude":  f"{lat:.5f}",
                        "longitude": f"{lon:.5f}",
                        "daily":     "sunrise,sunset,moonrise,moonset,moon_phase",
                        "timezone":  TZ_NAME,
                        "start_date": start_date.isoformat(),
                        "end_date":   end_date.isoformat(),
                    }
                    return "https://api.open-meteo.com/v1/astronomy?" + urlencode(params)

                aurl2 = astronomy_url_no_tf(lat, lon)
                log.debug("  DAILY backfill: astronomy URL (no timeformat)=%s", aurl2)
                aa2 = http_get_json(aurl2, retry=0, timeout=min(HTTP_TIMEOUT_S, 6))
                if isinstance(aa2, dict) and aa2.get("daily"):
                    _merge_daily(p, aa2)
                    log.info("  DAILY backfill: astronomy(keys, no tf)=%s", list((aa2.get("daily") or {}).keys()))
                    have_moon = _non_empty(p["daily"].get("moonrise")) and _non_empty(p["daily"].get("moonset")) and _non_empty(p["daily"].get("moon_phase"))
                else:
                    log.warning("  DAILY backfill: astronomy(no tf) returned no daily.")
            except Exception as e2:
                log.debug("  DAILY backfill (astronomy, no tf) failed: %s", e2)

    # c) Fallback local (Astral) si moon* encore vides
    if not have_moon:
        try:
            def _empty_or_all_none(arr):
                return (not isinstance(arr, list)) or (len(arr) == 0) or all(v is None for v in arr)
            need_astral = any(_empty_or_all_none(p["daily"].get(k)) for k in ("moonrise", "moonset", "moon_phase"))
        except Exception:
            need_astral = True

        if need_astral:
            if "_astral_backfill_daily" in globals():
                try:
                    before = {k: len(p["daily"].get(k) or []) for k in ("moonrise", "moonset", "moon_phase")}
                    _astral_backfill_daily(p, lat, lon)
                    after  = {k: len(p["daily"].get(k) or []) for k in ("moonrise", "moonset", "moon_phase")}
                    log.info("  DAILY backfill: astronomy (astral) attached. counts=%s→%s", before, after)
                except Exception as e3:
                    log.debug("  DAILY backfill (astral) failed: %s", e3)
            else:
                log.debug("  DAILY backfill: astral helper not available in globals() — skipping.")

    # d) (optionnel) uniformiser TZ dans les timestamps daily, si tu as le helper
    try:
        _normalize_daily_timezones_inplace(p)
    except Exception:
        pass

    # e) Clés & unités garanties
    p["daily"].setdefault("time", p["daily"].get("time", []))
    for k in ("sunrise", "sunset", "moonrise", "moonset", "moon_phase"):
        p["daily"].setdefault(k, [])
    p["daily_units"].setdefault("sunrise", "iso8601")
    p["daily_units"].setdefault("sunset", "iso8601")
    p["daily_units"].setdefault("moonrise", "iso8601")
    p["daily_units"].setdefault("moonset", "iso8601")
    p["daily_units"].setdefault("moon_phase", "fraction")



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
                p["_model_used"] = (model or "default")
                log.info("  ✔ forecast model used: %s", p["_model_used"])
                if _needs_daily_backfill(p):
                    _attach_daily_best_effort(p, lat, lon)
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
    
def _align_model_to_axis(model_slice: Dict[str, Any], axis: list[str]) -> Dict[str, list]:
    """Aligne un slice forecast (time + variables vent) sur l’axe commun `axis`."""
    te = model_slice.get("time") or []
    idx = {t: i for i, t in enumerate(te)}
    def pick(key: str) -> list:
        arr = model_slice.get(key) or []
        out = []
        for t in axis:
            j = idx.get(t)
            out.append(arr[j] if (j is not None and j < len(arr)) else None)
        return out

    aligned = {"time": list(axis)}
    for k in ["wind_speed_10m", "wind_gusts_10m", "wind_direction_10m", "weather_code", "visibility"]:
        if k in (model_slice or {}):
            aligned[k] = pick(k)
    return aligned


def fetch_parallel_models(
    lat: float, lon: float, axis: list[str],
    start_local: dt.datetime, end_local: dt.datetime, tz: ZoneInfo,
    primary_used: Optional[str], site_deadline: float
) -> tuple[dict, list]:
    """
    Tente de récupérer ≥1 modèle vent additionnel et de l’aligner sur `axis`.
    Retourne: (models_parallel: dict[str, {"hourly": {...}}], attempts_debug: list[dict]).
    """
    models_out: dict[str, dict] = {}
    attempts: list[dict] = []

    # Ne pas retenter le primaire sous un autre nom, et dédupliquer via expand_models()
    wanted = [m for m in expand_models(PARALLEL_MODELS) if m and m != (primary_used or "")]
    for m in wanted:
        status = "unknown"; url = None
        # On garde un peu de marge budget (1.5s) pour éviter l’arrêt abrupt
        if time.monotonic() > site_deadline - 1.5:
            attempts.append({"model": m, "status": "budget_exceeded"})
            continue
        try:
            url = forecast_url(lat, lon, m, hourly_keys=ECMWF_KEYS, include_daily=False)
            p = http_get_json(url, retry=PARALLEL_RETRIES, timeout=min(PARALLEL_TIMEOUT_S, HTTP_TIMEOUT_S))
            if payload_has_error(p):
                status = f"payload_error:{api_reason(p)}"; attempts.append({"model": m, "status": status, "url": url}); continue

            p = normalize_hourly_keys(p)
            if not has_wind_arrays(p):
                status = "no_wind_arrays"; attempts.append({"model": m, "status": status, "url": url}); continue

            # Slicing sur la même fenêtre temporelle
            keep_idx = indices_in_window((p.get("hourly") or {}).get("time") or [], start_local, end_local, tz)
            mslice   = slice_by_indices(p, ECMWF_KEYS, keep_idx)

            # Alignement sur l’axe commun
            aligned = _align_model_to_axis(mslice, axis)
            ws = aligned.get("wind_speed_10m") or []
            if not any(v is not None for v in ws):
                status = "no_overlap_with_axis"; attempts.append({"model": m, "status": status, "url": url}); continue

            models_out[m] = {"hourly": aligned}
            status = "ok"
        except Exception as e:
            status = f"exception:{e.__class__.__name__}"
        attempts.append({"model": m, "status": status, "url": url})
    return models_out, attempts



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
    out: Dict[str, int] = {}
    for k in keys:
        arr = d.get(k) or []
        out[k] = sum(1 for x in arr if x is not None)
    return out

# -----------------------
# Collecte
# -----------------------

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

    #
    # ---------- Modèles parallèles (vent) alignés sur l’axe commun ----------
    primary_used = wx.get("_model_used", "unknown")
    axis = hourly_flat.get("time") or []
    models_parallel, parallel_attempts = ({}, [])
    if axis:  # seulement si on a un axe horaire aligné valable
        try:
            models_parallel, parallel_attempts = fetch_parallel_models(
                lat, lon, axis, start_local, end_local, TZ, primary_used, site_deadline
            )
        except Exception as e:
            log.debug("parallel models fetch failed: %s", e)
    
    # Assure la présence du primaire sous models.* pour homogénéité du schéma
    if axis and primary_used and primary_used not in models_parallel:
        try:
            primary_aligned = _align_model_to_axis(ecmwf_slice, axis)
            if any(v is not None for v in (primary_aligned.get("wind_speed_10m") or [])):
                models_parallel[primary_used] = {"hourly": primary_aligned}
                parallel_attempts.append({"model": primary_used, "status": "published_primary_copy"})
        except Exception as e:
            log.debug("cannot publish primary under models.*: %s", e)

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
    # -----
    def _hysteresis(prev_ok: bool, value: float, cap: float, hys: float) -> bool:
        return value <= (cap + hys) if prev_ok else value <= cap
    
    def _iter_segments(flags: List[bool]) -> List[Tuple[int, int]]:
        segs = []; cur = None
        for i, ok in enumerate(flags):
            if ok:
                if cur is None:
                    cur = [i, i]
                else:
                    cur[1] = i
            else:
                if cur is not None:
                    segs.append((cur[0], cur[1])); cur = None
        if cur is not None:
            segs.append((cur[0], cur[1]))
        return segs
    
    def _local_hour_from_iso(iso: str) -> int:
        # Les JSON spots ont déjà des heures locales "YYYY-MM-DDTHH:MM"
        try:
            return int(iso[11:13])
        except Exception:
            return 0
    
    def _class_flags_for_model(hourly: Dict[str, Any],
                               marine: Dict[str, Any],
                               rules: Dict[str, Any]) -> Tuple[List[bool], List[bool]]:
        times = (hourly or {}).get("time") or []
        wind  = (hourly or {}).get("wind_speed_10m") or []
        gust  = (hourly or {}).get("wind_gusts_10m") or []
        hs    = (marine or {}).get("wave_height") or (marine or {}).get("hs") or []
    
        fam_w   = (rules.get("wind") or {}).get("family_max_kmh", 20.0)
        fam_hs  = (rules.get("sea")  or {}).get("family_max_hs_m", 0.5)
        exp_w, exp_hs = 25.0, 0.8
        exp_gust = (rules.get("shelter") or {}).get("anchor_gusts_allow_up_to_kmh", 34.0)
        hys_w  = (rules.get("hysteresis") or {}).get("wind_kmh", 1.0)
        hys_hs = (rules.get("hysteresis") or {}).get("hs_m", 0.05)
        fam_h1 = (rules.get("family_hours_local") or {}).get("start_h", 8)
        fam_h2 = (rules.get("family_hours_local") or {}).get("end_h", 21)
    
        fam_flags = []; exp_flags = []
        prev_fam = False; prev_exp = False
        n = min(len(times), len(wind), len(gust), len(hs))
        for i in range(n):
            hh = _local_hour_from_iso(times[i])
            ok_hour = (fam_h1 <= hh <= fam_h2)
            fam_ok = ok_hour and _hysteresis(prev_fam, float(wind[i]), float(fam_w), hys_w) \
                             and _hysteresis(prev_fam, float(hs[i]),   float(fam_hs), hys_hs)
            exp_ok = (float(gust[i]) <= float(exp_gust)) \
                     and _hysteresis(prev_exp, float(wind[i]), float(exp_w), hys_w) \
                     and _hysteresis(prev_exp, float(hs[i]),   float(exp_hs), hys_hs)
            fam_flags.append(bool(fam_ok)); exp_flags.append(bool(exp_ok))
            prev_fam = bool(fam_ok); prev_exp = bool(exp_ok)
        return fam_flags, exp_flags
    
    def _aggregate_one_spot(spot: Dict[str, Any], rules: Dict[str, Any]) -> Dict[str, Any]:
        primary = (spot.get("forecast_primary") or {})
        hourly_p = (primary.get("hourly") or {})
        marine   = (spot.get("marine") or {})
    
        fam_p, exp_p = _class_flags_for_model(hourly_p, marine, rules)
        model_flags = [(fam_p, exp_p)]
        for _, m in (spot.get("models") or {}).items():
            fam_m, exp_m = _class_flags_for_model((m or {}).get("hourly") or {}, marine, rules)
            model_flags.append((fam_m, exp_m))
    
        n = len(fam_p)
        safe_w_cap = 12.0  # tolérance sécurité (ton choix)
        safe_hs_cap = 0.4
        wind = hourly_p.get("wind_speed_10m") or []
        hs   = marine.get("wave_height") or marine.get("hs") or []
        times = hourly_p.get("time") or []
    
        fam_cons = []; exp_cons = []
        for i in range(n):
            fam_cons.append(bool(fam_p[i]))  # suit le primaire
            exp_cons.append(bool(exp_p[i]))
            fam_cons.append(fam_ok); exp_cons.append(exp_ok)
            if not fam_ok:
                try:
                    if float(wind[i]) <= safe_w_cap and float(hs[i]) <= safe_hs_cap:
                        fam_ok = True
                except Exception:
                    pass
            fam_cons.append(fam_ok); exp_cons.append(exp_ok)
    
        fam_segs = _iter_segments(fam_cons)
        exp_segs = _iter_segments(exp_cons)
    
        def seg_conf(segs, idx):
            out = []
            T = len(times)
            W = len(wind)
            H = len(hs)
            for a, b in segs:
                # clamp dans [0, T-1] pour l'accès aux timestamps
                if T == 0: 
                    continue
                aa = max(0, min(a, T-1))
                bb = max(aa, min(b, T-1))
        
                # votes de consensus (protégés)
                agree = 0
                L = bb - aa + 1
                for i in range(aa, bb + 1):
                    votes = 0
                    for flags in model_flags:
                        arr = flags[idx]
                        if i < len(arr) and arr[i]:
                            votes += 1
                    if votes >= 2:
                        agree += 1
                conf = "medium" if (agree / max(1, L)) >= 0.8 else "low"
        
                # promotion "sécurité" si toutes les heures sont calmes, avec garde d’index
                if conf == "low":
                    safe_all = True
                    for i in range(aa, bb + 1):
                        wi = float(wind[i]) if (i < W and wind[i] is not None) else None
                        hi = float(hs[i])   if (i < H and hs[i] is not None)   else None
                        if wi is None or hi is None or wi > safe_w_cap or hi > safe_hs_cap:
                            safe_all = False
                            break
                    if safe_all:
                        conf = "medium"
        
                out.append({"start_idx": aa, "end_idx": bb, "confidence": conf})
            return out

    
        fam_out = seg_conf(fam_segs, 0)
        exp_out = seg_conf(exp_segs, 1)
    
        def to_iso(seg):
            T = len(times)
            if T == 0:
                return None
            a, b = seg["start_idx"], seg["end_idx"]
            a = max(0, min(a, T-1))
            b = max(a, min(b, T-1))
            return {"start": times[a], "end": times[b], "confidence": seg["confidence"]}
            
        fam_iso = [x for x in (to_iso(s) for s in fam_out) if x is not None]
        exp_iso = [x for x in (to_iso(s) for s in exp_out) if x is not None]
        
        return {
            "dest_slug": f"{spot['meta']['slug']}.json",
            "dest_name": spot["meta"]["name"],
            "windows": [
                {"class": "Family", "segments": fam_iso},
                {"class": "Expert", "segments": exp_iso},
            ],
        }
    
    def build_windows_json(spots_dir: Path, out_path: Path, rules: Dict[str, Any]) -> Dict[str, Any]:
        entries = []
        SKIP = {"windows.json", "index.json", "status.json"}
        for p in sorted(spots_dir.glob("*.json")):
            if p.name in SKIP:
                continue
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                if isinstance(data, dict) and "meta" in data and "forecast_primary" in data:
                    entries.append(_aggregate_one_spot(data, rules))
            except Exception as e:
                log.warning("skip %s: %s", p, e)
    
        payload = {
            "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
            "windows": entries,
        }
        tmp = out_path.with_suffix(".tmp.json")
        out_path.parent.mkdir(parents=True, exist_ok=True)
        tmp.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    
        total_segments = sum(len(c.get("segments", [])) for e in entries for c in e.get("windows", []))
        if total_segments == 0 and out_path.exists():
            log.warning("windows aggregate empty — keeping last-known file")
            try: tmp.unlink()
            except Exception: pass
        else:
            os.replace(tmp, out_path)  # atomique
    
        return payload

    # --- Construction du payload JSON ---


    out: Dict[str, Any] = {        
        "meta": {
            "name": name, "slug": slug, "lat": lat, "lon": lon, "tz": TZ_NAME,
            "generated_at": dt.datetime.now(TZ).isoformat(),
            "window": {
                "start_local": start_local.isoformat(),
                "end_local":   end_local.isoformat(),
                "hours": int((end_local - start_local).total_seconds() // 3600),
            },
            "rules": {
                "digest": RULES_DIGEST,
                "path": os.getenv("FABLE_RULES_PATH", "rules.yaml"),
                "overrides": RULES.get("overrides", {}),
                "wind": RULES.get("wind", {}),
                "sea": RULES.get("sea", {}),
                "tp_matrix": RULES.get("tp_matrix", {}),
                "hysteresis": RULES.get("hysteresis", {}),
                "shelter": RULES.get("shelter", {}),
                "resolution_policy": RULES.get("resolution_policy", {}),
                "confidence": RULES.get("confidence", {}),
                "corridor": RULES.get("corridor", {}),
                "family_hours_local": RULES.get("family_hours_local", {}),
            },
            "sources": {
                "ecmwf_open_meteo": {
                    "endpoint": "https://api.open-meteo.com/v1/forecast",
                    "model_order": MODEL_ORDER,
                    "model_used": wx.get("_model_used", "unknown"),
                    "units": e_units,
                    "parallel_models": list(models_parallel.keys()),
                },
                "marine_open_meteo": {
                    "endpoint": "https://marine-api.open-meteo.com/v1/marine",
                    "units": m_units,
                },
                "astro_daily_open_meteo": {
                    "endpoint": "https://api.open-meteo.com/v1/astronomy",
                    "units": d_units
                },
            },
            "shelter_bonus_radius_km": site.get("shelter_bonus_radius_km", 0.0),
            "debug": {
                "hourly_keys_present_forecast": wx_keys_raw,
                "hourly_keys_present_marine": sea_keys_raw,
                "ecmwf_non_null_counts": nn_ecmwf,
                "marine_non_null_counts": nn_marine,
                "forecast_primary_model": primary_used,
                "forecast_primary_key": "ecmwf",  # alias historique conservé pour compat
                "kept_indices": {
                    "forecast": keep_wx[:6] + (["..."] if len(keep_wx) > 6 else []),
                    "marine":   keep_sea[:6] + (["..."] if len(keep_sea) > 6 else []),
                },
                "budgets": {"site_s": SITE_BUDGET_S, "global_s": HARD_BUDGET_S},
                "parallel_models_count": len(models_parallel),
                "parallel_attempts": parallel_attempts,
            },
        },
        "ecmwf": ecmwf_slice,
        "marine": marine_slice,
        "daily": daily,
        "daily_units": d_units,   # expose aussi les unités daily
        "hourly": hourly_flat,
        "models": models_parallel,  # <-- NOUVEAU : séries vent parallèles alignées
        "forecast_primary": { "model": primary_used, "hourly": ecmwf_slice },
        "status": "ok",
    }

    # --- Écriture atomique ---
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
index_target = PUBLIC / "index.json"
if index_target.exists():
    # Si pages.yml doit publier son propre index.json (catalogue), on n’écrase pas.
    alt = PUBLIC / "index.spots.json"
    alt.write_text(json.dumps(index_payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
else:
    index_target.write_text(json.dumps(index_payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
# --- build windows.json (agrégat) ---
try:
    build_windows_json(PUBLIC, PUBLIC / "windows.json", RULES)
    log.info("windows.json built at %s", (PUBLIC / "windows.json").as_posix())
except Exception as e:
    log.error("windows.json build failed: %s", e)

status_payload = {
    "status": "ok",
    "generated_at": dt.datetime.now(TZ).isoformat(),
    "all_fresh": True
}
(PUBLIC / "status.json").write_text(
    json.dumps(status_payload, ensure_ascii=False, separators=(",", ":")),
    encoding="utf-8"
)
# ---------------------------------------------------------------
