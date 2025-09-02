#!/usr/bin/env python3
import os, json, argparse
from glob import glob
from datetime import datetime, timezone

THUNDER_WMO = {95, 96, 99}

WANTED_KEYS = {
    "time", "wind_speed_10m", "wind_gusts_10m", "wind_direction_10m",
    "wave_height", "hs", "wave_period", "tp", "weather_code", "visibility"
}

def is_list(x): return isinstance(x, list)

def load_site(path):
    # Ouvre un "site" ; renvoie None si format inattendu
    with open(path, encoding="utf-8") as f:
        d = json.load(f)

    # Si le collecteur écrit un marqueur d'erreur
    if d.get("status", "ok") != "ok":
        return None

    h = d.get("hourly")
    if not isinstance(h, dict):  # pas de bloc hourly => pas un site
        return None

    # On ne garde que les clés utiles et de type "liste"
    hourly = {k: v for k, v in h.items() if k in WANTED_KEYS and is_list(v)}
    T = hourly.get("time")
    if not is_list(T) or len(T) == 0:
        return None

    # Longueur commune minimale entre toutes les listes présentes
    lens = [len(T)] + [len(v) for k, v in hourly.items() if k != "time"]
    N = min(lens) if lens else 0
    if N == 0:
        return None

    rows = []
    for i in range(N):
        row = {"t": T[i]}
        if "wind_speed_10m" in hourly:   row["w"]   = hourly["wind_speed_10m"][i]
        if "wind_gusts_10m" in hourly:   row["g"]   = hourly["wind_gusts_10m"][i]
        if "wind_direction_10m" in hourly: row["dir"] = hourly["wind_direction_10m"][i]
        # Hs/Tp : accepte "wave_height"/"wave_period" ou alias "hs"/"tp"
        if "wave_height" in hourly:      row["hs"]  = hourly["wave_height"][i]
        elif "hs" in hourly:             row["hs"]  = hourly["hs"][i]
        if "wave_period" in hourly:      row["tp"]  = hourly["wave_period"][i]
        elif "tp" in hourly:             row["tp"]  = hourly["tp"][i]
        if "weather_code" in hourly:     row["wc"]  = hourly["weather_code"][i]
        if "visibility" in hourly:       row["vis"] = hourly["visibility"][i]
        rows.append(row)

    meta = d.get("site", {})
    meta["slug"] = meta.get("slug") or os.path.basename(path)
    meta["name"] = meta.get("name") or meta["slug"]

    return {"meta": meta, "rows": rows}

def hard_nogo(seg):
    # 1) orage
    if any((r.get("wc") in THUNDER_WMO) for r in seg):
        return True
    # 2) rafales >= 30
    gvals = [r.get("g") for r in seg if r.get("g") is not None]
    if gvals and max(gvals) >= 30.0:
        return True
    # 3) squalls = rafales - soutenu >= 15
    for r in seg:
        if r.get("g") is not None and r.get("w") is not None and (r["g"] - r["w"] >= 15.0):
            return True
    return False

def primary_rules(seg):
    # Règles Hs/Tp/vent (si info absente => refuse prudemment)
    w = [r.get("w") for r in seg if r.get("w") is not None]
    hs = [r.get("hs") for r in seg if r.get("hs") is not None]
    tp = [r.get("tp") for r in seg if r.get("tp") is not None]
    if not w or not hs or not tp:
        return False
    wmax = max(w)
    hsmax = max(hs)
    tpmin = min(tp)
    if wmax >= 25.0 or hsmax > 0.8:
        return False
    if hsmax < 0.4:
        return tpmin >= 4.0
    elif hsmax <= 0.5:
        return tpmin >= 4.5
    else:
        return False

def windows_family(rows, min_h=4, max_h=6):
    wins = []
    n = len(rows)
    for s in range(0, n - min_h + 1):
        for L in range(min_h, max_h + 1):
            e = s + L
            if e > n: break
            seg = rows[s:e]
            if hard_nogo(seg): 
                continue
            if not primary_rules(seg):
                continue
            wins.append((seg[0]["t"], seg[-1]["t"], L))
    return wins

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--from-dir", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--home", default="gammarth-port.json")
    args = ap.parse_args()

    os.makedirs(args.out, exist_ok=True)

    # Liste des fichiers de sites
    idx_path = os.path.join(args.from_dir, "index.json")
    if os.path.exists(idx_path):
        with open(idx_path, encoding="utf-8") as f:
            idx = json.load(f)
        files = [os.path.join(args.from_dir, it["path"]) for it in idx.get("files", [])]
    else:
        files = sorted(glob(os.path.join(args.from_dir, "*.json")))
        files = [p for p in files if os.path.basename(p) not in ("index.json","windows.json")]

    # Home (Gammarth)
    home_file = None
    for p in files:
        if os.path.basename(p) == args.home:
            home_file = p
            break
    if not home_file:
        for p in files:
            if "gammarth" in os.path.basename(p).lower():
                home_file = p
                break

    home = load_site(home_file) if home_file else None
    home_by_time = {}
    if home:
        for r in home["rows"]:
            home_by_time[r["t"]] = r

    results = []
    for p in files:
        if home_file and os.path.samefile(p, home_file):
            continue
        site = load_site(p)
        if not site:
            continue

        # Recalage sur les timestamps disponibles des deux côtés
        rows = site["rows"]
        if home_by_time:
            rows = [r for r in rows if r["t"] in home_by_time]

        wins = windows_family(rows, 4, 6)

        good = []
        for (t0, t1, L) in wins:
            s_idx = next((i for i, r in enumerate(rows) if r["t"] == t0), None)
            if s_idx is None: 
                continue
            seg = rows[s_idx:s_idx+L]
            # même segment côté port (si dispo, sinon on accepte par défaut)
            if home_by_time:
                try:
                    hseg = [home_by_time[r["t"]] for r in seg]
                except KeyError:
                    continue  # manque une heure côté port -> rejeter
                if hard_nogo(hseg) or not primary_rules(hseg):
                    continue
            good.append({"start": t0, "end": t1, "hours": L})

        if good:
            results.append({
                "dest_slug": os.path.basename(p),
                "dest_name": site["meta"]["name"],
                "windows": good
            })

    out = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "home_slug": os.path.basename(home_file) if home_file else None,
        "windows": results
    }
    with open(os.path.join(args.out, "windows.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    main()
