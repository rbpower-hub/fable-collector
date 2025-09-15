#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scripts/fetch_ww3.py — Récupère Hs/Tp WW3 (PacIOOS ERDDAP) pour un spot FABLE.
Sortie: public/ww3-<slug>.json  { meta, hourly:{time,hs,tp} }
"""
import argparse, csv, io, json, sys, math, urllib.parse
from urllib.request import urlopen
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

ERDDAP_BASE = "https://pae-paha.pacioos.hawaii.edu/erddap/griddap/ww3_global.csv"

def round_grid_half(v):  # accroche à 0.5°
    return round(v * 2.0) / 2.0

def to_east_lon(lon_deg):
    # ERDDAP ww3_global utilise [0 .. 359.5] (degrees_east)
    lon_e = lon_deg % 360.0
    if lon_e < 0: lon_e += 360.0
    return lon_e

def load_spot_json(path_or_url):
    if path_or_url.startswith("http://") or path_or_url.startswith("https://"):
        with urlopen(path_or_url, timeout=20) as r:
            return json.loads(r.read().decode("utf-8"))
    else:
        return json.loads(open(path_or_url, "r", encoding="utf-8").read())

def window_from_spot(d):
    tz = ZoneInfo((d.get("meta") or {}).get("tz") or "Africa/Tunis")
    win = (d.get("meta") or {}).get("window") or {}
    t0s = win.get("start_local")
    t1s = win.get("end_local")
    if not (t0s and t1s):
        raise SystemExit("Ce spot JSON ne contient pas meta.window.start_local/end_local")
    def parse_local(iso, tz):
        # supporte "...:00+01:00" ou naïf local
        t = datetime.fromisoformat(iso.replace("Z","+00:00")) if "T" in iso else datetime.fromisoformat(iso + "T00:00")
        if t.tzinfo is None: t = t.replace(tzinfo=tz)
        else: t = t.astimezone(tz)
        return t
    t0 = parse_local(t0s, tz)
    t1 = parse_local(t1s, tz)
    # converti en UTC (ERDDAP attend time UTC)
    return t0.astimezone(timezone.utc), t1.astimezone(timezone.utc)

def build_erddap_url(t0z, t1z, lat, lon_e):
    # accroche à la grille 0.5°
    latg = round_grid_half(lat)
    long = round_grid_half(lon_e)
    # range temporel en UTC Z (inclu t0..t1, stride=1)
    t0s = t0z.replace(microsecond=0).isoformat().replace("+00:00","Z")
    t1s = t1z.replace(microsecond=0).isoformat().replace("+00:00","Z")
    # sélection dimensionnelle: [time][depth=0][lat][lon]
    sel = f"[({t0s}):1:({t1s})][(0.0)][({latg})][({long})]"
    q = f"Thgt{sel},Tper{sel}"
    return ERDDAP_BASE + "?" + urllib.parse.quote(q, safe=",:[]()&=")

def fetch_csv(url):
    with urlopen(url, timeout=25) as r:
        raw = r.read().decode("utf-8", errors="replace")
    buf = io.StringIO(raw)
    rdr = csv.reader(buf)
    rows = list(rdr)
    # ERDDAP .csv renvoie 2 lignes d’entête : noms / unités
    # puis data: time, Thgt, Tper
    if len(rows) <= 2:
        return []
    data = rows[2:]
    out = []
    for t, hs, tp in data:
        if not t: continue
        try:
            out.append((t, float(hs) if hs else None, float(tp) if tp else None))
        except Exception:
            # lignes NaN -> None
            hs = None if (hs.strip().lower() in ("nan","")) else float(hs)
            tp = None if (tp.strip().lower() in ("nan","")) else float(tp)
            out.append((t, hs, tp))
    return out

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
        tz = ZoneInfo(args.tz)
        now_loc = datetime.now(tz).replace(minute=0, second=0, microsecond=0)
        t0z = now_loc.astimezone(timezone.utc)
        t1z = (now_loc + timedelta(hours=args.hours)).astimezone(timezone.utc)

    lon_e = to_east_lon(lon)
    url = build_erddap_url(t0z, t1z, lat, lon_e)
    print("ERDDAP URL:", url)

    rows = fetch_csv(url)
    if not rows:
        sys.exit("Aucune ligne renvoyée (vérifie la fenêtre temporelle et la grille)")

    times, hs, tp = [], [], []
    for t, h, p in rows:
        times.append(t)   # déjà en ISO UTC
        hs.append(h)
        tp.append(p)

    out = {
        "meta": {
            "source": "PacIOOS WW3 (ww3_global)",
            "name": name, "slug": slug,
            "lat": lat, "lon": lon,
            "lon_east": lon_e,
            "grid": "0.5deg",
            "queried": datetime.now(timezone.utc).isoformat().replace("+00:00","Z"),
            "time_window_utc": {"start": times[0], "end": times[-1], "points": len(times)}
        },
        "hourly": {"time": times, "hs": hs, "tp": tp}
    }

    import os, pathlib
    pathlib.Path("public").mkdir(exist_ok=True)
    target = f"public/ww3-{slug}.json"
    open(target, "w", encoding="utf-8").write(json.dumps(out, ensure_ascii=False))
    print("✔ écrit", target, f"({len(times)} points)")

if __name__ == "__main__":
    main()
