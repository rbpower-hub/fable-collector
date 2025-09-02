#!/usr/bin/env python3
# reader.py — lit public/index.json + *.json et détecte les fenêtres Family GO (4–6 h)
from __future__ import annotations
from pathlib import Path
from datetime import datetime, timezone
import json, math, argparse

# --- Paramètres réglables ---
SHELTER_HS_BONUS = 0.10      # +0.10 m tolérance Hs en mouillage
SHELTER_WIND_BONUS = 3       # +3 km/h tolérance vent onshore en mouillage
HYST_HS = 0.05               # hysteresis Hs
HYST_WIND = 1                # hysteresis vent
TH_STORM = {95,96,99}        # weather_code orage
HOME_SLUG = "gammarth-port"  # doit correspondre au nom de fichier du port

def load_json(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8"))

def parse_iso(s: str) -> datetime:
    # accepte ISO avec 'Z' ou offset
    return datetime.fromisoformat(s.replace("Z","+00:00"))

def is_onshore(wdir: int, coast_bearing: int|None) -> bool:
    if coast_bearing is None: return False  # si inconnu, on ne dégrade pas
    # onshore si le vent souffle vers la côte (±90° autour de la normale à la côte côté mer)
    # convention: coast_bearing = azimut du rivage (sens littoral). Normale mer->terre = coast_bearing - 90°
    n = (coast_bearing - 90) % 360
    ang = abs(((wdir - n + 180) % 360) - 180)
    return ang <= 90

def classify_hour(h: dict, coast_bearing: int|None, phase: str) -> str:
    """Retourne 'FAMILY','EXP','NO' selon les règles FABLE + Shelter Bonus au mouillage."""
    w = h.get("wind_speed_10m"); g = h.get("wind_gusts_10m"); d = h.get("wind_direction_10m")
    hs = h.get("wave_height"); tp = h.get("wave_period"); code = h.get("weather_code")
    vis = h.get("visibility")  # km si dispo, sinon None

    # Overriding NO-GO
    if code in TH_STORM: return "NO"
    if g is not None and g >= 30 - HYST_WIND: return "NO"  # rafales ≥30 km/h

    # Squalls ≥ +15 km/h
    if w is not None and g is not None and (g - w) >= 15: return "NO"

    level = "FAMILY"

    # Vent soutenu
    if w is not None:
        if w >= 25 - HYST_WIND: return "NO"
        if w >= 20 - HYST_WIND: level = "EXP"

    # Hs
    if hs is not None:
        if hs > 0.8 + HYST_HS: return "NO"
        if hs >= 0.5 - HYST_HS: level = "EXP"

    # Tp dynamique
    if tp is not None and hs is not None:
        if hs < 0.4 - HYST_HS:
            if tp < 4.0: level = "EXP" if level == "FAMILY" else level
        elif hs <= 0.5 + HYST_HS:
            if tp < 4.5: level = "EXP" if level == "FAMILY" else level
        else:
            level = "EXP" if level == "FAMILY" else level  # Hs ≥ 0.5 => pas Family

    # Combined clauses (short/steep)
    if hs is not None and tp is not None:
        if hs >= 0.6 - HYST_HS and tp <= 5.0 + 1e-9: return "NO"
        if hs >= 0.5 - HYST_HS and tp <= 6.0 + 1e-9:
            level = "EXP" if level == "FAMILY" else level

    # Onshore > 20 km/h
    if d is not None and w is not None and is_onshore(d, coast_bearing):
        if w > 20 - HYST_WIND:
            level = "EXP" if level == "FAMILY" else level

    # Visibilité < 5 km
    if vis is not None and vis < 5.0:
        level = "EXP" if level == "FAMILY" else level

    # Shelter Bonus (uniquement pendant le mouillage)
    if phase == "MOUILLAGE" and hs is not None:
        # bonus sur la limite Family (tolérance)
        if level == "EXP" and hs <= 0.5 + SHELTER_HS_BONUS:
            level = "FAMILY"
        if d is not None and w is not None and is_onshore(d, coast_bearing):
            if level == "EXP" and w <= 20 + SHELTER_WIND_BONUS:
                level = "FAMILY"

    return level

def best_windows(spot: dict, coast_bearing: int|None, home_series: list[dict]) -> list[dict]:
    """Détecte des fenêtres 4–6 h Family GO en validant départ/retour Gammarth et corridor (approche prudente)."""
    series = spot["series"]               # liste d'heures dict alignées sur 'time'
    times = [parse_iso(h["time"]) for h in series]

    wins = []
    for i in range(0, len(series) - 4 + 1):
        for dur in (4,5,6):
            j = i + dur - 1
            if j >= len(series): break
            window = series[i:j+1]
            # Transit (1er et dernier créneau), Mouillage (milieu)
            phases = ["TRANSIT"] + ["MOUILLAGE"]*(dur-2) + ["TRANSIT"]
            ratings = [classify_hour(h, coast_bearing, phases[k]) for k, h in enumerate(window)]
            if "NO" in ratings: continue
            if any(r != "FAMILY" for r in ratings): continue  # need full FAMILY

            # Port check: Gammarth doit être FAMILY au départ et au retour
            t0, t1 = window[0]["time"], window[-1]["time"]
            try:
                gh0 = next(h for h in home_series if h["time"] == t0)
                gh1 = next(h for h in home_series if h["time"] == t1)
            except StopIteration:
                continue
            if classify_hour(gh0, None, "TRANSIT") != "FAMILY": continue
            if classify_hour(gh1, None, "TRANSIT") != "FAMILY": continue

            # Corridor (approximation prudente) : on exige FAMILY au spot et à Gammarth pour toutes les heures
            ok_corr = True
            for hh in window:
                try: ght = next(h for h in home_series if h["time"] == hh["time"])
                except StopIteration: ok_corr = False; break
                if classify_hour(ght, None, "TRANSIT") != "FAMILY": ok_corr = False; break
            if not ok_corr: continue

            wins.append({
                "start": times[i].isoformat(),
                "end":   times[j].isoformat(),
                "duration_h": dur
            })
    return wins

def load_series(file_path: Path) -> list[dict]:
    raw = load_json(file_path)
    # On attend un bloc 'hourly' façon Open-Meteo; on fusionne les colonnes par index
    H = raw.get("hourly", {})
    keys = [k for k in H.keys() if k != "time"]
    out = []
    for idx, t in enumerate(H.get("time", [])):
        row = {"time": t}
        for k in keys:
            vlist = H.get(k)
            if vlist is not None and idx < len(vlist):
                row[k] = vlist[idx]
        out.append(row)
    return out

def coast_bearing_for(slug: str) -> int|None:
    # Option: renseigne tes azimuts de côte ici (ou charge depuis sites.yaml)
    table = {
        "gammarth-port": 40,      # ~NE–SW (exemple)
        "sidi-bou-said": 60,
        "ghar-el-melh": 45,
        "rasfartass": 80,
        "houaria": 95,
    }
    return table.get(slug)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--from-dir", default="public", help="répertoire contenant index.json et les fichiers spot")
    ap.add_argument("--out", default="public", help="répertoire de sortie (windows.json, report.md)")
    args = ap.parse_args()

    base = Path(args.from_dir)
    outdir = Path(args.out); outdir.mkdir(parents=True, exist_ok=True)

    index = load_json(base/"index.json")
    files = [f["path"] for f in index["files"] if f["path"].endswith(".json") and "index.json" not in f["path"]]

    # charge Gammarth d'abord
    home_file = next((Path(base)/p for p in files if p.startswith(HOME_SLUG)), None)
    if not home_file: raise SystemExit("Gammarth introuvable dans index.json")
    home_series = load_series(home_file)

    all_windows = []
    for p in files:
        slug = p.replace(".json","")
        spot_series = load_series(Path(base)/p)
        wins = best_windows({"series": spot_series}, coast_bearing_for(slug), home_series)
        if wins:
            all_windows.append({"spot": slug, "windows": wins})

    # écrit résultats
    windows_path = outdir/"windows.json"
    windows_path.write_text(json.dumps({
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00","Z"),
        "home": HOME_SLUG,
        "windows": all_windows
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    # petit rapport texte (lisible vite)
    lines = ["# FABLE — Fenêtres Family GO détectées", ""]
    if not all_windows:
        lines.append("_Aucune fenêtre Family GO dans l’horizon analysé._")
    else:
        for blk in all_windows:
            lines.append(f"## {blk['spot']}")
            for w in blk["windows"]:
                lines.append(f"- {w['start']} → {w['end']}  ({w['duration_h']} h)")
            lines.append("")
    (outdir/"windows.md").write_text("\n".join(lines), encoding="utf-8")

if __name__ == "__main__":
    main()
