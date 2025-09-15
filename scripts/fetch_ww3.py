#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scripts/fetch_ww3.py — Récupère Hs/Tp WW3 (PacIOOS ERDDAP) pour un spot FABLE.
Sortie: public/ww3-<slug>.json  { meta, hourly:{time,hs,tp} }
"""

import argparse, csv, io, json, sys, urllib.parse
from urllib.request import urlopen
from urllib.error import HTTPError, URLError
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
import pathlib

ERDDAP_BASE = "https://pae-paha.pacioos.hawaii.edu/erddap/griddap/ww3_global.csv"

# ---------------------------
# Helpers grille / coordonnées
# ---------------------------

def round_grid_half(v: float) -> float:
    """Accroche à la grille 0.5°."""
    return round(v * 2.0) / 2.0

def to_east_lon(lon_deg: float) -> float:
    """ERDDAP ww3_global utilise [0 .. 359.5] (degrees_east)."""
    lon_e = lon_deg % 360.0
    if lon_e < 0:
        lon_e += 360.0
    return lon_e

# ---------------------------
# Lecture JSON spot & fenêtre
# ---------------------------

def load_spot_json(path_or_url: str) -> dict:
    if path_or_url.startswith(("http://", "https://")):
        with urlopen(path_or_url, timeout=20) as r:
            return json.loads(r.read().decode("utf-8"))
    return json.loads(open(path_or_url, "r", encoding="utf-8").read())

def window_from_spot(d: dict):
    tz_name = (d.get("meta") or {}).get("tz") or "Africa/Tunis"
    try:
        tz = ZoneInfo(tz_name)
    except ZoneInfoNotFoundError:
        print(f"[warn] TZ '{tz_name}' introuvable, fallback UTC", file=sys.stderr)
        tz = timezone.utc

    win = (d.get("meta") or {}).get("window") or {}
    t0s, t1s = win.get("start_local"), win.get("end_local")
    if not (t0s and t1s):
        raise SystemExit("Ce spot JSON ne contient pas meta.window.start_local/end_local")

    def parse_local(iso: str, tzobj):
        # supporte "...:00+01:00" ou naïf local "YYYY-MM-DD" / "YYYY-MM-DDTHH:MM:SS"
        t = datetime.fromisoformat(iso.replace("Z", "+00:00")) if "T" in iso else datetime.fromisoformat(iso + "T00:00")
        if t.tzinfo is None:
            t = t.replace(tzinfo=tzobj)
        else:
            t = t.astimezone(tzobj)
        return t

    t0 = parse_local(t0s, tz)
    t1 = parse_local(t1s, tz)
    # converti en UTC (ERDDAP attend time UTC)
    return t0.astimezone(timezone.utc), t1.astimezone(timezone.utc)

# ---------------------------
# Construction URL griddap
# ---------------------------

def build_erddap_url(t0z: datetime, t1z: datetime, lat: float, lon_e: float) -> str:
    """Construit l'URL griddap ww3_global pour Thgt et Tper à depth=0.0 sur la grille 0.5°."""
    latg = round_grid_half(lat)
    long = round_grid_half(lon_e)

    # fenêtre temporelle en Z, stride=1
    t0s = t0z.replace(microsecond=0).isoformat().replace("+00:00", "Z")
    t1s = t1z.replace(microsecond=0).isoformat().replace("+00:00", "Z")

    # sélection dimensionnelle: [time][depth=0][lat][lon]
    sel = f"[({t0s}):1:({t1s})][(0.0)][({latg})][({long})]"

    # griddap: variables séparées par VIRGULE ; time/lat/lon/depth sont renvoyés automatiquement
    q = f"Thgt{sel},Tper{sel}"
    return ERDDAP_BASE + "?" + urllib.parse.quote(q, safe=",:[]()=")

# ---------------------------
# Récup CSV et parsing
# ---------------------------

def fetch_csv(url: str):
    try:
        with urlopen(url, timeout=25) as r:
            raw = r.read().decode("utf-8", errors="replace")
    except HTTPError as e:
        body = ""
        try:
            body = e.read().decode("utf-8", errors="ignore")
        except Exception:
            pass
        raise SystemExit(f"HTTP {e.code} from ERDDAP\nURL: {url}\n--- server said ---\n{body[:800]}")
    except URLError as e:
        raise SystemExit(f"Network error contacting ERDDAP: {e}")

    buf = io.StringIO(raw)
    rdr = csv.reader(buf)
    rows = list(rdr)

    # ERDDAP .csv renvoie 2 lignes d’entête : noms / unités
    # puis data: time, depth, lat, lon, Thgt, Tper
    if len(rows) <= 2:
        return []

    data = rows[2:]
    out = []
    for row in data:
        # Défensif : certaines versions incluent lat/lon/depth entre Thgt et Tper
        # On ne dépend que des 1ère/dernière colonnes.
        if not row or not row[0]:
            continue
        t = row[0]
        # Par convention griddap ww3_global: Thgt = avant-dernière, Tper = dernière
        hs_s = row[-2] if len(row) >= 2 else ""
        tp_s = row[-1] if len(row) >= 1 else ""
        try:
            hs = float(hs_s) if hs_s not in ("", "NaN", "nan", "NA") else None
        except Exception:
            hs = None
        try:
            tp = float(tp_s) if tp_s not in ("", "NaN", "nan", "NA") else None
        except Exception:
            tp = None
        out.append((t, hs, tp))
    return out

# ---------------------------
# Recherche auto d’une cellule marine
# ---------------------------

# Spirale d’offsets 0.5°, rayon jusqu’à 2.0°
OFFSETS_05 = [(0.0, 0.0)]
for r_steps in (1, 2, 3, 4):  # 0.5°, 1.0°, 1.5°, 2.0°
    r = r_steps * 0.5
    rng = [i * 0.5 for i in range(-r_steps, r_steps + 1)]
    # bord haut et bas (dlat = ±r)
    for dx in rng:
        OFFSETS_05.append((+r, dx))
        OFFSETS_05.append((-r, dx))
    # bord gauche/droite (dlon = ±r) sans re-dupliquer les coins
    for dy in rng[1:-1]:
        OFFSETS_05.append((dy, +r))
        OFFSETS_05.append((dy, -r))

def try_cell(t0z, t1z, lat, lon_e):
    url = build_erddap_url(t0z, t1z, lat, lon_e)
    print("ERDDAP URL:", url)
    rows = fetch_csv(url)
    has_value = any((h is not None or p is not None) for _, h, p in rows)
    return has_value, rows, url

# ---------------------------
# main
# ---------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--from-spot", help="Chemin local d’un JSON spot (public/<slug>.json)")
    ap.add_argument("--from-url",  help="URL publique d’un JSON spot (Pages)")
    ap.add_argument("--slug", help="Slug pour la sortie (si pas from-spot/url)")
    ap.add_argument("--lat", type=float)
    ap.add_argument("--lon", type=float)
    ap.add_argument("--hours", type=int, default=48)
    ap.add_argument("--tz", default="Africa/Tunis")
    args = ap.parse_args()

    if args.from_spot or args.from_url:
        d = load_spot_json(args.from_spot or args.from_url)
        name = (d.get("meta") or {}).get("name") or args.slug or "spot"
        slug = (d.get("meta") or {}).get("slug") or (args.slug or "spot")
        lat  = float((d.get("meta") or {}).get("lat"))
        lon  = float((d.get("meta") or {}).get("lon"))
        t0z, t1z = window_from_spot(d)
    else:
        if not (args.slug and args.lat is not None and args.lon is not None):
            sys.exit("Spécifie --from-spot/--from-url ou bien --slug --lat --lon")
        name, slug, lat, lon = args.slug, args.slug, args.lat, args.lon
        # construit une fenêtre [now_local .. now_local+hours] en TZ choisie puis convertit en UTC
        try:
            tz = ZoneInfo(args.tz)
        except ZoneInfoNotFoundError:
            print(f"[warn] TZ '{args.tz}' introuvable, fallback UTC", file=sys.stderr)
            tz = timezone.utc
        now_loc = datetime.now(tz).replace(minute=0, second=0, microsecond=0)
        t0z = now_loc.astimezone(timezone.utc)
        t1z = (now_loc + timedelta(hours=args.hours)).astimezone(timezone.utc)

    # Recherche automatique d'une cellule marine voisine
    lon_e = to_east_lon(lon)

    best_rows, best_url = None, None
    chosen_lat, chosen_lon_e = None, None

    for dlat, dlon in OFFSETS_05:
        lat_try = round_grid_half(lat + dlat)
        lon_try = round_grid_half((lon_e + dlon) % 360.0)
        ok, rows, url = try_cell(t0z, t1z, lat_try, lon_try)
        if rows:
            if ok:  # première cellule avec données non-NaN → on s'arrête
                best_rows, best_url = rows, url
                chosen_lat, chosen_lon_e = lat_try, lon_try
                break
            # sinon, on mémorise au cas où aucune cellule n'ait de valeur
            if best_rows is None:
                best_rows, best_url = rows, url
                chosen_lat, chosen_lon_e = lat_try, lon_try

    if best_rows is None:
        sys.exit("Aucune ligne renvoyée par ERDDAP (fenêtre temporelle hors couverture ?)")

    if not any((h is not None or p is not None) for _, h, p in best_rows):
        sys.exit("Cellules voisines testées (rayon 2.0°), mais aucune avec données (NaN). Essaie un point plus au large ou une autre fenêtre temporelle.")

    rows = best_rows
    lat_used = chosen_lat if chosen_lat is not None else round_grid_half(lat)
    lon_e_used = chosen_lon_e if chosen_lon_e is not None else round_grid_half(lon_e)

    times, hs, tp = [], [], []
    for t, h, p in rows:
        times.append(t)   # déjà en ISO UTC
        hs.append(h)
        tp.append(p)

    out = {
        "meta": {
            "source": "PacIOOS WW3 (ww3_global)",
            "name": name, "slug": slug,
            "request": {"lat": lat, "lon": lon, "lon_east": lon_e},
            "grid": "0.5deg",
            "grid_used": {"lat": lat_used, "lon_east": lon_e_used, "step_deg": 0.5},
            "queried": datetime.now(timezone.utc).isoformat().replace("+00:00","Z"),
            "time_window_utc": {"start": times[0], "end": times[-1], "points": len(times)},
            "erddap_url": best_url
        },
        "hourly": {"time": times, "hs": hs, "tp": tp}
    }

    pathlib.Path("public").mkdir(exist_ok=True)
    target = f"public/ww3-{slug}.json"
    open(target, "w", encoding="utf-8").write(json.dumps(out, ensure_ascii=False))
    print("✔ écrit", target, f"({len(times)} points)")

if __name__ == "__main__":
    main()
