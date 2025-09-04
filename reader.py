#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FABLE reader — détecteur de fenêtres Family GO (4–6 h)
------------------------------------------------------
- Entrée : JSON de spots produits par le collector (public/*.json)
- Sortie : public/windows.json (liste des fenêtres par destination)
- Règles : "worst-value-wins", squalls, onshore>20, visibilité >=5 km,
           couplage Hs/Tp, NO-GO rafales>=30 ou orages, port check T0/T0+durée.
- Confiance : High/Medium/Low (capée à Medium si une seule source de houle).

Exemples :
    python reader.py --from-dir public --out public \
                     --home gammarth-port.json --min-hours 4 --max-hours 6

Notes :
- Les heures fournies par le collector sont interprétées dans `meta.timezone`
  (ex: Africa/Tunis) via zoneinfo. Les ISO émis dans windows.json sont TZ-aware.
- Le script est robuste aux champs absents/None ; il préfère “rater une fenêtre”
  plutôt que proposer une fenêtre douteuse.
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple
from zoneinfo import ZoneInfo
import datetime as dt


# =========================
# Paramètres FABLE (seuils)
# =========================
WIND_FAMILY_MAX = 20.0        # km/h  -> Family GO si vent soutenu < 20
WIND_NO_GO_MIN  = 25.0        # km/h  -> NO-GO si soutenu >= 25
GUST_NO_GO_MIN  = 30.0        # km/h  -> NO-GO si rafales >= 30
SQUALL_DELTA    = 15.0        # km/h  -> squall si rafales - soutenu >= 15

HS_FAMILY_MAX   = 0.5         # m     -> Family GO si Hs < 0.5
HS_NO_GO_MIN    = 0.8         # m     -> NO-GO si Hs > 0.8
TP_MIN_AT_LT04  = 4.0         # s     -> si Hs < 0.4, Tp >= 4.0
TP_MIN_AT_04_05 = 4.5         # s     -> si 0.4 <= Hs < 0.5, Tp >= 4.5

# Clauses combinées (mers courtes / raides)
SHORT_STEEP_1_HS = 0.5  # downgrade si Hs >= 0.5 et Tp <= 6 s (ici Family GO devient faux)
SHORT_STEEP_1_TP = 6.0
SHORT_STEEP_2_HS = 0.6  # NO-GO dur si Hs >= 0.6 et Tp <= 5 s
SHORT_STEEP_2_TP = 5.0

VIS_MIN_KM      = 5.0        # km    -> exigence mini
ONSHORE_MAX_OK  = 20.0       # km/h  -> onshore > 20 => downgrade (pas Family GO)

# Orages (WMO code)
THUNDER_CODES = {95, 96, 99}

# Fenêtres
DEFAULT_MIN_H = 4
DEFAULT_MAX_H = 6


# =========================
# Petites structures utiles
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
    s = slug.replace(".json", "")
    # Orientation approximée des côtes locales (gulf de Tunis & Cap Bon)
    if s in {"gammarth-port", "sidi-bou-said", "korbous"}:
        return [(30, 150)]
    if s in {"ghar-el-melh"}:
        return [(10, 130)]
    if s in {"rasfartass", "houaria", "kelibia"}:
        return [(330, 360), (0, 70)]
    return [(20, 160)]  # fallback prudent


def _safe_get(arr: Optional[List[Any]], i: int) -> Any:
    return None if arr is None or i >= len(arr) else arr[i]


# =========================
# Lecture d’un site (JSON)
# =========================
def load_site(path: Path) -> Site:
    d = json.loads(path.read_text(encoding="utf-8"))
    meta = d.get("meta", {})
    tzname = meta.get("timezone", "UTC")
    try:
        tz = ZoneInfo(tzname)
    except Exception:
        tz = ZoneInfo("UTC")

    times = []
    for t in d["hourly"]["time"]:
        # Les timestamps du collector sont naïfs locaux -> on les localise
        tt = dt.datetime.fromisoformat(t)
        tt = tt.replace(tzinfo=tz) if tt.tzinfo is None else tt.astimezone(tz)
        times.append(tt)

    return Site(
        name=meta.get("name", path.stem),
        slug=meta.get("slug", path.name),
        tz=tz,
        times=times,
        wind_models=d["hourly"].get("wind", {}),
        waves=d["hourly"].get("waves", {}),
        path=path,
    )


def worst_metrics_at_hour(site: Site, idx: int) -> HourMetrics:
    speeds, gusts, dirs, vis, codes = [], [], [], [], []
    n_models = 0
    for _, arrs in site.wind_models.items():
        sp = arrs.get("wind_speed_10m")
        gu = arrs.get("wind_gusts_10m")
        di = arrs.get("wind_direction_10m")
        vc = arrs.get("visibility_km")
        wc = arrs.get("weather_code")

        if sp and idx < len(sp) and sp[idx] is not None:
            speeds.append(sp[idx])
        if gu and idx < len(gu) and gu[idx] is not None:
            gusts.append(gu[idx])
        if di and idx < len(di) and di[idx] is not None:
            dirs.append(di[idx])
        if vc and idx < len(vc) and vc[idx] is not None:
            vis.append(vc[idx])
        if wc and idx < len(wc) and wc[idx] is not None:
            codes.append(int(wc[idx]))
        if arrs.get("wind_speed_10m"):
            n_models += 1

    waves = site.waves
    hs_arr = waves.get("significant_wave_height") or waves.get("wave_height")
    tp_arr = waves.get("wave_period")

    hs = _safe_get(hs_arr, idx)
    tp = _safe_get(tp_arr, idx)

    return HourMetrics(
        max_speed=max(speeds) if speeds else None,
        min_speed=min(speeds) if speeds else None,
        max_gust=max(gusts) if gusts else None,
        spread_speed=(max(speeds) - min(speeds)) if len(speeds) >= 2 else None,
        any_dir=dirs[0] if dirs else None,  # direction représentative
        min_vis=min(vis) if vis else None,
        codes=codes,
        hs=hs,
        tp=tp,
        n_models=n_models,
    )


def hour_is_family_ok(site: Site, idx: int) -> Tuple[bool, Dict[str, Any]]:
    m = worst_metrics_at_hour(site, idx)
    reasons: List[str] = []
    ok = True

    # Surclassement NO-GO
    if any(c in THUNDER_CODES for c in m.codes):
        ok = False; reasons.append("orages")
    if m.max_gust is not None and m.max_gust >= GUST_NO_GO_MIN:
        ok = False; reasons.append("rafales>=30")
    if m.max_speed is not None and m.max_speed >= WIND_NO_GO_MIN:
        ok = False; reasons.append("vent>=25")

    # Houle + période (couplage)
    if m.hs is None or m.tp is None:
        reasons.append("vagues_inconnues")
        ok = False
    else:
        if m.hs > HS_NO_GO_MIN:
            ok = False; reasons.append("Hs>0.8")
        if m.hs >= HS_FAMILY_MAX:
            ok = False; reasons.append("Hs>=0.5")
        else:
            if m.hs < 0.4 and m.tp < TP_MIN_AT_LT04:
                ok = False; reasons.append("Tp<4.0@Hs<0.4")
            if 0.4 <= m.hs < 0.5 and m.tp < TP_MIN_AT_04_05:
                ok = False; reasons.append("Tp<4.5@Hs0.4-0.5")
        # mers courtes / raides
        if m.hs is not None and m.tp is not None:
            if m.hs >= SHORT_STEEP_1_HS and m.tp <= SHORT_STEEP_1_TP:
                ok = False; reasons.append("short_steep")
            if m.hs >= SHORT_STEEP_2_HS and m.tp <= SHORT_STEEP_2_TP:
                ok = False; reasons.append("short_steep_hard")

    # Squalls
    if m.max_gust is not None and m.min_speed is not None:
        if (m.max_gust - m.min_speed) >= SQUALL_DELTA:
            ok = False; reasons.append("squalls")

    # Onshore > 20
    if m.max_speed is not None and m.any_dir is not None:
        if m.max_speed > ONSHORE_MAX_OK and _angle_in_ranges(m.any_dir, _onshore_sectors(site.slug)):
            ok = False; reasons.append("onshore>20")

    # Visibilité
    if m.min_vis is not None and m.min_vis < VIS_MIN_KM:
        ok = False; reasons.append("vis<5km")

    # Baseline Family GO (vent)
    if m.max_speed is not None and m.max_speed >= WIND_FAMILY_MAX:
        ok = False; reasons.append("vent>=20")

    return ok, {"reasons": reasons, "metrics": m}


def compute_confidence(site: Site, i0: int, i1: int) -> str:
    """Capée à Medium si une seule source de houle ; Low si <2 modèles vent."""
    spreads = []
    n_models = 0
    for i in range(i0, i1 + 1):
        m = worst_metrics_at_hour(site, i)
        if m.spread_speed is not None:
            spreads.append(m.spread_speed)
        n_models = max(n_models, m.n_models)

    if n_models < 2:
        return "Low"

    avg_spread = statistics.mean(spreads) if spreads else None
    cap = "Medium"  # pas de 2ème modèle houle => on ne dépasse pas Medium
    if avg_spread is not None and avg_spread < 5:
        return cap
    if avg_spread is not None and avg_spread < 8:
        return "Low" if cap == "Medium" else "Medium"
    return "Low"


def detect_windows(home: Site, dest: Site, min_h: int, max_h: int) -> List[Dict[str, Any]]:
    """Fenêtres 4–6 h : toutes les heures de la fenêtre doivent être Family OK
       sur la destination *et* port OK au départ (T0) et au retour (T0+durée)."""
    n = min(len(dest.times), len(home.times))
    windows: List[Dict[str, Any]] = []
    i = 0

    while i < n:
        dest_ok, _ = hour_is_family_ok(dest, i)
        if not dest_ok:
            i += 1
            continue

        end = i
        while end < n and (end - i) < max_h:
            ok_h, _ = hour_is_family_ok(dest, end)
            if not ok_h:
                break
            end += 1

        length = end - i
        if length >= min_h:
            # Port check : départ à i, retour à end-1 (fin incluse)
            dep_ok, _ = hour_is_family_ok(home, i)
            ret_ok, _ = hour_is_family_ok(home, end - 1)
            if dep_ok and ret_ok:
                start_dt = dest.times[i]
                end_dt = dest.times[end - 1] + dt.timedelta(hours=1)  # borne exclusive
                windows.append({
                    "start": start_dt.isoformat(),
                    "end": end_dt.isoformat(),
                    "hours": length,
                    "confidence": compute_confidence(dest, i, end - 1),
                })
                i = end
                continue

        i += 1

    return windows


# =========================
# Exécution principale
# =========================
def run(from_dir: Path, out_dir: Path, home_slug: Optional[str],
        min_h: int, max_h: int) -> Dict[str, Any]:

    # Lister les fichiers de spots
    spots = sorted([p for p in from_dir.glob("*.json")
                    if p.name not in ("index.json", "windows.json")])
    if not spots:
        raise SystemExit(f"Aucun JSON de spot trouvé dans {from_dir}")

    # Charger les sites
    sites: Dict[str, Site] = {}
    for p in spots:
        try:
            s = load_site(p)
            sites[p.name] = s
        except Exception as e:
            print(f"⚠️  Ignoré (lecture impossible) {p.name}: {e}")

    if not sites:
        raise SystemExit("Aucun site valide.")

    # Déterminer le port d’attache
    if not home_slug:
        candidates = [k for k in sites if "gammarth" in k]
        home_slug = candidates[0] if candidates else list(sites.keys())[0]
    if home_slug not in sites:
        print(f"⚠️  reader --home={home_slug} introuvable, fallback arbitraire.")
        home_slug = list(sites.keys())[0]

    home = sites[home_slug]

    # Détection
    out: Dict[str, Any] = {
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "home_slug": home_slug,
        "windows": []
    }
    for slug, dest in sites.items():
        if slug == home_slug:
            continue
        wins = detect_windows(home, dest, min_h=min_h, max_h=max_h)
        out["windows"].append({
            "dest_slug": slug,
            "dest_name": dest.name,
            "windows": wins
        })

    # Écriture
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
