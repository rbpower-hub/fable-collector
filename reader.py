#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FABLE reader — détecteur de fenêtres Family GO (4–6 h)
------------------------------------------------------
- Entrée : JSON de spots produits par le collector (public/*.json)
- Sortie : public/windows.json (liste des fenêtres par destination)
- Règles : worst-value-wins, squalls (Δ rafale-soutenu), onshore>k, visibilité>=5 km,
           couplage Hs/Tp, overrides orage / rafales, port check (T0/T0+durée).
- Confiance : High/Medium/Low (capée à Medium si une seule source de houle).

NOUVEAUTÉS :
- Lecture de rules.yaml (seuils dynamiques).
- Fenêtres 4–6 h découpées en phases : Transit – Mouillage – Transit.
- Shelter Bonus appliqué SEULEMENT en Mouillage, avec tolérances définies
  dans rules.yaml (rafales, squalls, Tp assoupli si Hs faible).

Usage :
    python reader.py --from-dir public --out public \
                     --home gammarth-port.json --min-hours 4 --max-hours 6
"""

from __future__ import annotations

import argparse
import json
import statistics
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple
from zoneinfo import ZoneInfo
import datetime as dt
import os

# --- PyYAML optionnel (fallback auto si absent) ---
try:
    import yaml
except Exception:
    yaml = None

# =========================
# Fallback règles par défaut (si rules.yaml absent)
# =========================
_DEFAULT_RULES = {
    "overrides": {"thunder_wmo": [95, 96, 99], "gusts_hard_nogo_kmh": 30, "squall_delta_kmh": 17},
    "wind": {"family_max_kmh": 20, "nogo_min_kmh": 25, "onshore_degrade_kmh": 22},
    "sea": {"family_max_hs_m": 0.5, "nogo_min_hs_m": 0.8},
    "tp_matrix": {
        "transit": {
            "hs_lt_0_4_family_tp_s": 3.2,
            "hs_0_4_0_5_family_tp_s": 4.5,
            "hs_lt_0_4_expert_tp_min_s": 3.2,
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
        # tolérance soutenu au mouillage (si non défini : 30 par défaut)
        "anchor_sustained_allow_up_to_kmh": 30,
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

def _dget(dct: Dict[str, Any], path: str, default=None):
    cur = dct
    for part in path.split('.'):
        if not isinstance(cur, dict) or part not in cur:
            return default
        cur = cur[part]
    return cur

def load_rules() -> Dict[str, Any]:
    path = os.getenv("FABLE_RULES_PATH", "rules.yaml")
    p = Path(path)
    if yaml is None or not p.exists():
        print(f"[reader.rules] Using defaults (yaml missing or not found at {p})")
        return _DEFAULT_RULES
    with p.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    # merge shallow
    def deep_merge(dst, src):
        for k, v in src.items():
            if isinstance(v, dict) and isinstance(dst.get(k), dict):
                deep_merge(dst[k], v)
            else:
                dst[k] = v
        return dst
    return deep_merge(dict(_DEFAULT_RULES), data)

RULES: Dict[str, Any] = load_rules()

# =========================
# Paramètres init (seront surchargés par RULES)
# =========================
WIND_FAMILY_MAX = 20.0        # km/h  -> Family GO si vent soutenu < 20
WIND_NO_GO_MIN  = 25.0        # km/h  -> NO-GO si soutenu >= 25
GUST_NO_GO_MIN  = 30.0        # km/h  -> NO-GO si rafales >= 30
SQUALL_DELTA    = 15.0        # km/h  -> squall si rafales - soutenu >= 15

HS_FAMILY_MAX   = 0.5         # m     -> Family GO si Hs < 0.5
HS_NO_GO_MIN    = 0.8         # m     -> NO-GO si Hs > 0.8
TP_MIN_AT_LT04  = 4.0         # s     -> si Hs < 0.4, Tp >= 4.0
TP_MIN_AT_04_05 = 4.5         # s     -> si 0.4 <= Hs < 0.5, Tp >= 4.5

# --- fenêtre horaire Family ---
FAMILY_HOUR_START = 8   # 08:00 inclus
FAMILY_HOUR_END   = 21  # 21:00 exclu

# Clauses combinées (mers courtes / raides)
SHORT_STEEP_1_HS = 0.5  # downgrade si Hs >= 0.5 et Tp <= 6 s
SHORT_STEEP_1_TP = 6.0
SHORT_STEEP_2_HS = 0.6  # NO-GO dur si Hs >= 0.6 et Tp <= 5 s
SHORT_STEEP_2_TP = 5.0

VIS_MIN_KM      = 5.0
ONSHORE_MAX_OK  = 20.0
THUNDER_CODES = {95, 96, 99}

# Shelter (phase Mouillage)
ANCHOR_HS_EASE_MAX = 0.35
ANCHOR_GUST_ALLOW  = 34
ANCHOR_SQUALL_DELTA_MAX = 20
ANCHOR_SUSTAINED_ALLOW  = 30  # soutenu toléré au mouillage (si Hs faible + pas d’orage)

def _apply_rules_globals() -> None:
    """Surcharger les constantes ci-dessus depuis RULES (compat maximale avec le code existant)."""
    global WIND_FAMILY_MAX, WIND_NO_GO_MIN, GUST_NO_GO_MIN, SQUALL_DELTA
    global HS_FAMILY_MAX, HS_NO_GO_MIN, TP_MIN_AT_LT04, TP_MIN_AT_04_05
    global FAMILY_HOUR_START, FAMILY_HOUR_END, ONSHORE_MAX_OK, THUNDER_CODES
    global ANCHOR_HS_EASE_MAX, ANCHOR_GUST_ALLOW, ANCHOR_SQUALL_DELTA_MAX, ANCHOR_SUSTAINED_ALLOW

    WIND_FAMILY_MAX = float(_dget(RULES, "wind.family_max_kmh", WIND_FAMILY_MAX))
    WIND_NO_GO_MIN  = float(_dget(RULES, "wind.nogo_min_kmh", WIND_NO_GO_MIN))
    ONSHORE_MAX_OK  = float(_dget(RULES, "wind.onshore_degrade_kmh", ONSHORE_MAX_OK))

    GUST_NO_GO_MIN  = float(_dget(RULES, "overrides.gusts_hard_nogo_kmh", GUST_NO_GO_MIN))
    SQUALL_DELTA    = float(_dget(RULES, "overrides.squall_delta_kmh", SQUALL_DELTA))
    THUNDER_CODES   = set(_dget(RULES, "overrides.thunder_wmo", list(THUNDER_CODES)))

    HS_FAMILY_MAX   = float(_dget(RULES, "sea.family_max_hs_m", HS_FAMILY_MAX))
    HS_NO_GO_MIN    = float(_dget(RULES, "sea.nogo_min_hs_m", HS_NO_GO_MIN))

    TP_MIN_AT_LT04  = float(_dget(RULES, "tp_matrix.transit.hs_lt_0_4_family_tp_s", TP_MIN_AT_LT04))
    TP_MIN_AT_04_05 = float(_dget(RULES, "tp_matrix.transit.hs_0_4_0_5_family_tp_s", TP_MIN_AT_04_05))

    FAMILY_HOUR_START = int(_dget(RULES, "family_hours_local.start_h", FAMILY_HOUR_START))
    FAMILY_HOUR_END   = int(_dget(RULES, "family_hours_local.end_h", FAMILY_HOUR_END))

    ANCHOR_HS_EASE_MAX      = float(_dget(RULES, "tp_matrix.anchor_sheltered.hs_le_0_35_family_tp_s", 3.8) and 0.35) or 0.35
    ANCHOR_GUST_ALLOW       = float(_dget(RULES, "shelter.anchor_gusts_allow_up_to_kmh", ANCHOR_GUST_ALLOW))
    ANCHOR_SQUALL_DELTA_MAX = float(_dget(RULES, "shelter.anchor_squall_delta_max_kmh", ANCHOR_SQUALL_DELTA_MAX))
    ANCHOR_SUSTAINED_ALLOW  = float(_dget(RULES, "shelter.anchor_sustained_allow_up_to_kmh", ANCHOR_SUSTAINED_ALLOW))

_apply_rules_globals()

# Fenêtres
DEFAULT_MIN_H = 4
DEFAULT_MAX_H = 6

# =========================
# Structures utiles
# =========================
@dataclass
class Site:
    name: str
    slug: str
    tz: ZoneInfo
    times: List[dt.datetime]          # TZ-aware, croissantes
    wind_models: Dict[str, Dict[str, List[Optional[float]]]]
    waves: Dict[str, List[Optional[float]]]
    path: Path

@dataclass
class HourMetrics:
    max_speed: Optional[float]
    min_speed: Optional[float]
    max_gust: Optional[float]
    spread_speed: Optional[float]
    any_dir: Optional[float]
    any_onshore: Optional[bool]
    min_vis: Optional[float]
    codes: List[int]
    hs: Optional[float]
    tp: Optional[float]
    n_models: int

# =========================
# Utilitaires
# =========================
def _angle_in_ranges(angle: float, ranges: Sequence[Tuple[int, int]]) -> bool:
    for a, b in ranges:
        if a <= b:
            if a <= angle <= b:
                return True
        else:  # wrap-around (ex: 330..360, 0..70)
            if angle >= a or angle <= b:
                return True
    return False

def _onshore_sectors(slug: str) -> List[Tuple[int, int]]:
    s = slug.replace(".json", "").lower()
    if s in {"gammarth-port", "gammarth"}:
        return [(30, 150)]
    if s in {"sidi-bou-said", "sidibousaid", "sidi-bou"}:
        return [(30, 150)]
    if s in {"ghar-el-melh", "ghar el melh", "gharemelh", "ghar-elmelh"}:
        return [(10, 130)]
    if s in {"el-haouaria", "haouaria", "el haouaria"}:
        return [(330, 360), (0, 70)]
    if s in {"ras-fartass", "rasfartass", "ras fartass"}:
        return [(330, 360), (0, 70)]
    if s in {"korbous"}:
        return [(30, 150)]
    if s in {"kelibia", "kélibia"}:
        return [(330, 360), (0, 70)]
    return [(20, 160)]

def _all_in_family_hours_dts(dts: Sequence[dt.datetime], tz: ZoneInfo) -> bool:
    for t in dts:
        tt = t if t.tzinfo else t.replace(tzinfo=tz)
        tt = tt.astimezone(tz)
        if not (FAMILY_HOUR_START <= tt.hour < FAMILY_HOUR_END):
            return False
    return True
#
def _has_wind_range(site: Site, i0: int, i1: int) -> bool:
    """
    Vrai si, pour chaque heure de [i0..i1], il existe AU MOINS UN modèle
    qui possède speed/gust/dir non-nuls. (Compat multi-modèles.)
    """
    for i in range(i0, i1 + 1):
        ok_hour = False
        for _, arrs in site.wind_models.items():
            sp = arrs.get("wind_speed_10m") or []
            gu = arrs.get("wind_gusts_10m") or []
            di = arrs.get("wind_direction_10m") or []
            if (
                i < len(sp) and sp[i] is not None
                and i < len(gu) and gu[i] is not None
                and i < len(di) and di[i] is not None
            ):
                ok_hour = True
                break
        if not ok_hour:
            return False
    return True

def _safe_get(arr: Optional[List[Any]], i: int) -> Any:
    return None if arr is None or i >= len(arr) else arr[i]

# =========================
# Lecture d’un site (JSON)
# =========================
def load_site(path: Path) -> Site:
    d = json.loads(path.read_text(encoding="utf-8"))
    meta = d.get("meta", {}) or {}

    tzname = meta.get("tz") or meta.get("timezone") or "Africa/Tunis"
    try:
        tz = ZoneInfo(tzname)
    except Exception:
        tz = ZoneInfo("UTC")

    hourly = d.get("hourly", {}) or {}
    raw_time = hourly.get("time") or []
    times: List[dt.datetime] = []
    for t in raw_time:
        tt = dt.datetime.fromisoformat(t)
        tt = tt.replace(tzinfo=tz) if tt.tzinfo is None else tt.astimezone(tz)
        times.append(tt)

    vis = hourly.get("visibility")
    vis_km: Optional[List[Optional[float]]] = None
    if isinstance(vis, list):
        if any(v is not None and isinstance(v, (int, float)) and v > 50 for v in vis):
            vis_km = [(v / 1000.0) if isinstance(v, (int, float)) else None for v in vis]
        else:
            vis_km = [float(v) if v is not None else None for v in vis]

    wind_models = {}
    # [NOUVEAU] support des séries multi-modèles alignées par le collector
    models = d.get("models") or {}
    if isinstance(models, dict) and models:
        for mname, mobj in models.items():
            hh = (mobj.get("hourly") or {})
            if not isinstance(hh, dict): 
                continue
            wind_models[mname] = {
                "wind_speed_10m":     hh.get("wind_speed_10m"),
                "wind_gusts_10m":     hh.get("wind_gusts_10m"),
                "wind_direction_10m": hh.get("wind_direction_10m"),
                "weather_code":       hh.get("weather_code"),
                "visibility_km":      ([(v/1000.0) if isinstance(v,(int,float)) and v>50 else (float(v) if v is not None else None) for v in (hh.get("visibility") or [])] if isinstance(hh.get("visibility"), list) else None),
            }
    # Fallback compat si aucun modèle parallèle exposé
    if not wind_models:
        wind_models = {
            "om": {
                "wind_speed_10m":     hourly.get("wind_speed_10m"),
                "wind_gusts_10m":     hourly.get("wind_gusts_10m"),
                "wind_direction_10m": hourly.get("wind_direction_10m"),
                "weather_code":       hourly.get("weather_code"),
                "visibility_km":      vis_km,
            }
        }
    waves = {
        "significant_wave_height": hourly.get("hs") or hourly.get("wave_height"),
        "wave_period":             hourly.get("tp") or hourly.get("wave_period"),
    }

    return Site(
        name=meta.get("name", meta.get("site_name", path.stem)),
        slug=meta.get("slug", path.name),
        tz=tz,
        times=times,
        wind_models=wind_models,
        waves=waves,
        path=path,
    )

# =========================
# Métriques à l’heure (worst-value-wins)
# =========================
def worst_metrics_at_hour(site: Site, idx: int) -> HourMetrics:
    speeds: List[float] = []
    gusts: List[float] = []
    dirs: List[float] = []
    vis: List[float] = []
    codes: List[int] = []
    n_models = 0

    for _, arrs in site.wind_models.items():
        sp = arrs.get("wind_speed_10m") or []
        gu = arrs.get("wind_gusts_10m") or []
        di = arrs.get("wind_direction_10m") or []
        vc = arrs.get("visibility_km") or []
        wc = arrs.get("weather_code") or []

        has_triplet = (
            idx < len(sp) and sp[idx] is not None and
            idx < len(gu) and gu[idx] is not None and
            idx < len(di) and di[idx] is not None
        )
        if has_triplet:
            speeds.append(sp[idx]); gusts.append(gu[idx]); dirs.append(di[idx])
            if idx < len(vc) and vc[idx] is not None: vis.append(vc[idx])
            if idx < len(wc) and wc[idx] is not None:
                try: codes.append(int(wc[idx]))
                except: pass
            n_models += 1

    hs_arr = site.waves.get("significant_wave_height") or site.waves.get("wave_height")
    tp_arr = site.waves.get("wave_period")
    hs = _safe_get(hs_arr, idx)
    tp = _safe_get(tp_arr, idx)

    onshore_ranges = _onshore_sectors(site.slug)
    any_onshore = None
    if dirs:
        any_onshore = any(_angle_in_ranges(d, onshore_ranges) for d in dirs)

    return HourMetrics(
        max_speed=max(speeds) if speeds else None,
        min_speed=min(speeds) if speeds else None,
        max_gust=max(gusts) if gusts else None,
        spread_speed=(max(speeds) - min(speeds)) if len(speeds) >= 2 else None,
        any_dir=dirs[0] if dirs else None,
        any_onshore=any_onshore,
        min_vis=min(vis) if vis else None,
        codes=codes,
        hs=hs,
        tp=tp,
        n_models=n_models,
    )

# =========================
# Évaluation Family selon PHASE
# =========================
def _waves_ok_transit(m: HourMetrics, reasons: List[str]) -> bool:
    ok = True
    if m.hs is None or m.tp is None:
        reasons.append("vagues_inconnues"); return False

    if m.hs > HS_NO_GO_MIN:
        ok = False; reasons.append("Hs>0.8")
    if m.hs >= HS_FAMILY_MAX:
        ok = False; reasons.append("Hs>=0.5")
    else:
        if m.hs < 0.4 and m.tp < TP_MIN_AT_LT04:
            ok = False; reasons.append("Tp<4.0@Hs<0.4")
        if 0.4 <= m.hs < 0.5 and m.tp < TP_MIN_AT_04_05:
            ok = False; reasons.append("Tp<4.5@Hs0.4-0.5")

    if m.hs is not None and m.tp is not None:
        if m.hs >= SHORT_STEEP_1_HS and m.tp <= SHORT_STEEP_1_TP:
            ok = False; reasons.append("short_steep")
        if m.hs >= SHORT_STEEP_2_HS and m.tp <= SHORT_STEEP_2_TP:
            ok = False; reasons.append("short_steep_hard")
    return ok

def _waves_ok_anchor(m: HourMetrics, reasons: List[str]) -> bool:
    # Bonus "mouillage abrité" si Hs ≤ 0.35 et pas d’orage : Tp assoupli (famille >= 3.8s).
    if m.hs is None or m.tp is None:
        reasons.append("vagues_inconnues"); return False
    if m.hs <= 0.35:
        # on autorise période famille >= 3.8s (seuil chargé via rules.yaml → 3.8 par défaut)
        tp_family_anchor = float(_dget(RULES, "tp_matrix.anchor_sheltered.hs_le_0_35_family_tp_s", 3.8))
        if m.tp < tp_family_anchor:
            reasons.append(f"Tp<{tp_family_anchor}@Hs<=0.35"); return False
        # short/steep non bloquant ici (Hs faible) → pas de pénalité
        return True
    # sinon, on retombe sur la logique "transit"
    return _waves_ok_transit(m, reasons)

def hour_ok_for_phase(site: Site, idx: int, phase: str) -> Tuple[bool, Dict[str, Any]]:
    """Retourne (ok, details) pour une heure donnée selon phase 'transit'|'anchor'."""
    m = worst_metrics_at_hour(site, idx)
    reasons: List[str] = []
    ok = True

    # Orages : NO-GO partout
    if any(c in THUNDER_CODES for c in m.codes):
        return False, {"reasons": reasons + ["orages"], "metrics": m}

    # Visibilité
    if m.min_vis is not None and m.min_vis < VIS_MIN_KM:
        ok = False; reasons.append("vis<5km")

    # Onshore > seuil (déclassement : pas Family)
    if m.max_speed is not None and m.any_onshore:
        if m.max_speed > ONSHORE_MAX_OK:
            ok = False; reasons.append(f"onshore>{int(ONSHORE_MAX_OK)}")

    # Squalls (Δ gust-soutenu)
    if m.max_gust is not None and m.min_speed is not None:
        delta = m.max_gust - m.min_speed
        if phase == "anchor":
            if delta >= ANCHOR_SQUALL_DELTA_MAX:
                ok = False; reasons.append("squalls_anchor")
        else:
            if delta >= SQUALL_DELTA:
                ok = False; reasons.append("squalls")

    # Rafales / Vent soutenu
    if phase == "anchor":
        # tolérance au mouillage (si Hs faible et pas d’orage) → gestion rafales/soutenu
        # rafales tolérées jusqu’à ANCHOR_GUST_ALLOW
        if m.max_gust is not None and m.max_gust >= ANCHOR_GUST_ALLOW:
            ok = False; reasons.append(f"gusts>={int(ANCHOR_GUST_ALLOW)}@anchor")
        # soutenu toléré jusqu’à ANCHOR_SUSTAINED_ALLOW (si les vagues restent conformes)
        if m.max_speed is not None and m.max_speed >= ANCHOR_SUSTAINED_ALLOW:
            ok = False; reasons.append(f"vent>={int(ANCHOR_SUSTAINED_ALLOW)}@anchor")
        # vagues & période (version assouplie si Hs<=0.35)
        if not _waves_ok_anchor(m, reasons):
            ok = False
    else:
        # Transit : seuils stricts Family
        if m.max_gust is not None and m.max_gust >= GUST_NO_GO_MIN:
            ok = False; reasons.append(f"rafales>={int(GUST_NO_GO_MIN)}")
        if m.max_speed is not None and m.max_speed >= WIND_NO_GO_MIN:
            ok = False; reasons.append(f"vent>={int(WIND_NO_GO_MIN)}")
        # baseline Family wind
        if m.max_speed is not None and m.max_speed >= WIND_FAMILY_MAX:
            ok = False; reasons.append(f"vent>={int(WIND_FAMILY_MAX)}")
        if not _waves_ok_transit(m, reasons):
            ok = False

    return ok, {"reasons": reasons, "metrics": m}

# =========================
# Confiance (inchangée, conservative)
# =========================
def compute_confidence(site: Site, i0: int, i1: int) -> str:
    wind_spreads: List[float] = []
    hs_values: List[float] = []
    min_models = float("inf")

    for i in range(i0, i1 + 1):
        m = worst_metrics_at_hour(site, i)
        if m.spread_speed is not None:
            wind_spreads.append(m.spread_speed)
        if m.hs is not None:
            hs_values.append(m.hs)
        min_models = min(min_models, m.n_models or 0)

    # Politique : toutes les heures de la fenêtre doivent avoir ≥2 modèles pour sortir de LOW
    if min_models < 2:
        return "Low"

    avg_wind_spread = statistics.mean(wind_spreads) if wind_spreads else None
    hs_spread = (max(hs_values) - min(hs_values)) if len(hs_values) >= 2 else None

    if (avg_wind_spread is not None and avg_wind_spread < _dget(RULES,"confidence.high.wind_spread_kmh_lt",5)) \
       and (hs_spread is not None and hs_spread < _dget(RULES,"confidence.high.hs_spread_m_lt",0.2)):
        result = "High"
    elif avg_wind_spread is not None and avg_wind_spread < 8:
        result = "Medium"
    else:
        result = "Low"

    # Cap à Medium si une seule source de houle (collector actuel)
    return "Medium" if result == "High" else result

# =========================
# Fenêtres 4–6 h avec phases
# =========================
def _phases_for_window(length: int) -> List[str]:
    """Mappe offsets -> phase selon longueur 4..6:
       L=4: [T, A, A, T]
       L=5: [T, A, A, A, T]
       L=6: [T, A, A, A, A, T]
    """
    if length < 4:
        return ["transit"] * length
    if length == 4:
        return ["transit", "anchor", "anchor", "transit"]
    if length == 5:
        return ["transit", "anchor", "anchor", "anchor", "transit"]
    # length >=6 (on borne à 6 en appelant cette fonction)
    return ["transit", "anchor", "anchor", "anchor", "anchor", "transit"]

def _window_ok_dest(dest: Site, i: int, end: int) -> Tuple[bool, List[str]]:
    """Vérifie toutes les heures [i..end-1] côté destination avec phases."""
    length = end - i
    phases = _phases_for_window(length)
    reasons_all: List[str] = []
    for k, idx in enumerate(range(i, end)):
        phase = phases[k] if k < len(phases) else "transit"
        ok_h, det = hour_ok_for_phase(dest, idx, phase)
        if not ok_h:
            reasons_all.extend([f"h{idx - i}:{r}" for r in det.get("reasons", [])])
            return False, reasons_all
    return True, reasons_all

def detect_windows(home: Site, dest: Site, min_h: int, max_h: int) -> List[Dict[str, Any]]:
    """Fenêtres 4–6 h : phases Transit–Mouillage–Transit sur la destination,
       + port check Family au départ (T0) et retour (T0+durée) à Gammarth.
       Catégorie : 'family' si [08–21) entièrement, sinon 'off_hours'."""
    n = min(len(dest.times), len(home.times))
    windows: List[Dict[str, Any]] = []
    i = 0

    while i < n:
        # Petite garde : le départ doit être faisable en transit
        dep_ok, _ = hour_ok_for_phase(home, i, "transit")
        dep_dest_ok, _ = hour_ok_for_phase(dest, i, "transit")
        if not (dep_ok and dep_dest_ok):
            i += 1
            continue

        best_end = i
        end = i + 1
        # on tente d'étendre jusqu'à max_h (mais on revalide tout à chaque extension car les phases changent)
        while end <= n and (end - i) <= max_h:
            length = end - i
            if length < min_h:
                end += 1
                continue
            # vérif destination (phases) pour la fenêtre courante
            ok_dest, _ = _window_ok_dest(dest, i, end)
            if not ok_dest:
                break

            # retour port à l'heure de fin-1, en transit
            ret_ok, _ = hour_ok_for_phase(home, end - 1, "transit")
            if not ret_ok:
                break

            # les données vent doivent être présentes sur tout l'intervalle (dest + home)
            if not _has_wind_range(dest, i, end - 1) or not _has_wind_range(home, i, end - 1):
                break

            best_end = end
            end += 1

        if best_end - i >= min_h:
            start_dt = dest.times[i]
            end_dt = dest.times[best_end - 1] + dt.timedelta(hours=1)  # borne exclusive
            window_dts = dest.times[i:best_end]
            category = "family" if _all_in_family_hours_dts(window_dts, dest.tz) else "off_hours"

            conf = compute_confidence(dest, i, best_end - 1)
            # diagnostics utiles
            wind_models_per_hour = [worst_metrics_at_hour(dest, j).n_models for j in range(i, best_end)]
            avg_spread = (statistics.mean([worst_metrics_at_hour(dest, j).spread_speed
                                           for j in range(i, best_end)
                                           if worst_metrics_at_hour(dest, j).spread_speed is not None])
                          if any(worst_metrics_at_hour(dest, j).spread_speed is not None for j in range(i, best_end))
                          else None)
            windows.append({
                "start": start_dt.isoformat(),
                "end": end_dt.isoformat(),
                "hours": best_end - i,
                "confidence": conf,
                "confidence_details": {
                    "min_wind_models_per_hour": min(wind_models_per_hour) if wind_models_per_hour else 0,
                    "avg_wind_spread_kmh": round(avg_spread, 2) if isinstance(avg_spread, (int, float)) else None
                },
                "category": category,
                "reason": "valid_FAMILY_rules" + ("" if category == "family" else "_outside_08_21"),
            })
            i = best_end
        else:
            i += 1

    return windows

# =========================
# Exécution principale
# =========================
@dataclass
class RunResult:
    generated_at: str
    home_slug: str
    windows: List[Dict[str, Any]]

def run(from_dir: Path, out_dir: Path, home_slug: Optional[str],
        min_h: int, max_h: int) -> Dict[str, Any]:

    _apply_rules_globals()  # au cas où RULES a été modifié par l'env

    spots = sorted([p for p in from_dir.glob("*.json")
                    if p.name not in ("index.json", "windows.json")])
    if not spots:
        raise SystemExit(f"Aucun JSON de spot trouvé dans {from_dir}")

    sites: Dict[str, Site] = {}
    for p in spots:
        try:
            s = load_site(p)
            sites[p.name] = s
        except Exception as e:
            print(f"⚠️  Ignoré (lecture impossible) {p.name}: {e}")

    if not sites:
        raise SystemExit("Aucun site valide.")

    if not home_slug:
        candidates = [k for k in sites if "gammarth" in k]
        home_slug = candidates[0] if candidates else list(sites.keys())[0]
    if home_slug not in sites:
        print(f"⚠️  reader --home={home_slug} introuvable, fallback arbitraire.")
        home_slug = list(sites.keys())[0]

    home = sites[home_slug]

    out: Dict[str, Any] = {
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "home_slug": home_slug,
        "windows": []
    }

    for slug, dest in sites.items():
        wins = detect_windows(home, dest, min_h=min_h, max_h=max_h)
        out["windows"].append({
            "dest_slug": slug,
            "dest_name": dest.name,
            "windows": wins
        })

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "windows.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return out

def main() -> None:
    ap = argparse.ArgumentParser(description="FABLE reader – détecteur de fenêtres Family GO")
    ap.add_argument("--from-dir", default="public", type=Path,
                    help="Répertoire où se trouvent les JSON de spots.")
    ap.add_argument("--out", default="public", type=Path,
                    help="Répertoire de sortie (windows.json).")
    ap.add_argument("--home", default=None,
                    help="Nom de fichier JSON du port d’attache (ex: gammarth-port.json).")
    ap.add_argument("--min-hours", default=DEFAULT_MIN_H, type=int,
                    help="Durée minimale d’une fenêtre (heures).")
    ap.add_argument("--max-hours", default=DEFAULT_MAX_H, type=int,
                    help="Durée maximale d’une fenêtre (heures).")
    args = ap.parse_args()

    run(args.from_dir, args.out, args.home, args.min_hours, args.max_hours)

if __name__ == "__main__":
    main()
