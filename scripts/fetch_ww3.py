#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fetch_ww3.py — sonde WW3 (PacIOOS/NOAA) et écrit public/ww3-<slug>.json
- Variables : Thgt (Hs, m) et Tper (Tp, s)
- Source    : ERDDAP griddap ww3_global (0.5°, 1h, UTC)
Usage:
  python scripts/fetch_ww3.py --slug gammarth-port --lat 36.9203 --lon 10.2846 --hours 48
  # ou pour aligner sur la fenêtre d’un JSON spot existant :
  python scripts/fetch_ww3.py --from-spot public/gammarth-port.json
"""
import csv, json, math, argparse, datetime as dt
from zoneinfo import ZoneInfo
from urllib.parse import quote
from urllib.request import urlopen

ERDDAP = "https://pae-paha.pacioos.hawaii.edu/erddap/griddap/ww3_global.csvp"
TZ_LOCAL = ZoneInfo("Africa/Tunis")

def east_lon(lon):
    # ERDDAP de ce dataset est 0..359.5E
    x = lon % 360.0
    return x if x >= 0 else x + 360.0

def iso_utc(dtobj):
    return dtobj.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def round_to_half(v):
    # grille 0.5° -> choisir le point le plus proche
    return round(v*2)/2.0

def build_query(lat, lon_e, t0z, t1z):
    # Slicing griddap en CSV "csvp" :
    # var[(t0):1:(t1)][(0.0)][(lat)][(lon)]
    # on encode en conservant [](),: et virgules
    def sl(var): 
        return f"{var}[({t0z}):1:({t1z})][(0.0)][({lat})][({lon_e})]"
    q = f"{sl('Thgt')},{sl('Tper')},time,latitude,longitude"
    return ERDDAP + "?" + quote(q, safe="[],():,=")

def fetch_csv(url):
    with urlopen(url, timeout=20) as r:
        rows = list(csv.DictReader(r.read().decode("utf-8").splitlines()))
    return rows

def from_spot_window(spot_json_path):
    d = json.loads(open(spot_json_path, "r", encoding="utf-8").read())
    meta = d.get("meta", {})
    w = meta.get("window", {})
    start = dt.datetime.fromisoformat(w.get("start_local")).astimezone(TZ_LOCAL)
    end   = dt.datetime.fromisoformat(w.get("end_local")).astimezone(TZ_LOCAL)
    return start, end, meta.get("name","?"), meta.get("slug","?")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--slug", required=False, help="slug (ex: gammarth-port)")
    ap.add_argument("--lat", type=float)
    ap.add_argument("--lon", type=float)
    ap.add_argument("--hours", type=int, default=48)
    ap.add_argument("--from-spot", help="chemin vers public/<slug>.json pour caler la fenêtre")
    ap.add_argument("--outdir", default="public")
    args = ap.parse_args()

    if args.from_spot:
        t0_local, t1_local, name, slug = from_spot_window(args.from_spot)
        # récupère lat/lon depuis le spot si dispo
        d = json.loads(open(args.from_spot, "r", encoding="utf-8").read())
        lat = float(d["meta"]["lat"]); lon = float(d["meta"]["lon"])
    else:
        if args.lat is None or args.lon is None or not args.slug:
            ap.error("--slug, --lat, --lon requis si --from-spot non fourni")
        slug = args.slug
        name = slug
        t0_local = dt.datetime.now(TZ_LOCAL).replace(minute=0, second=0, microsecond=0)
        t1_local = t0_local + dt.timedelta(hours=args.hours)
        lat = args.lat; lon = args.lon

    # grille 0.5° -> verrouille sur le point le plus proche pour stabilité
    lat_q = round_to_half(lat)
    lon_e = round_to_half(east_lon(lon))

    t0z = iso_utc(t0_local)
    t1z = iso_utc(t1_local)

    url = build_query(lat_q, lon_e, t0z, t1z)
    rows = fetch_csv(url)

    # Normalise -> séries horaires
    times_utc, times_local, hs, tp = [], [], [], []
    for r in rows:
        # ERDDAP retourne time en ISO UTC (ex: 2025-09-15T00:00:00Z)
        t_utc = dt.datetime.fromisoformat(r["time"].replace("Z","+00:00"))
        t_loc = t_utc.astimezone(TZ_LOCAL)
        times_utc.append(t_utc.isoformat().replace("+00:00","Z"))
        times_local.append(t_loc.isoformat(timespec="minutes"))
        # Valeurs
        def f(x):
            try:
                v = float(x); 
                if math.isnan(v): return None
                return v
            except: 
                return None
        hs.append(f(r.get("Thgt")))
        tp.append(f(r.get("Tper")))

    out = {
        "meta": {
            "source": "PacIOOS WW3 (NOAA) — ww3_global (0.5°, hourly, UTC)",
            "url": ERDDAP,
            "dataset_id": "ww3_global",
            "lat_query": lat_q, "lon_query_east": lon_e,
            "spot": {"name": name, "slug": slug, "lat": lat, "lon": lon},
            "generated_at": dt.datetime.now(TZ_LOCAL).isoformat(),
            "tz_local": TZ_LOCAL.key
        },
        "hourly": {
            "time_utc": times_utc,
            "time_local": times_local,
            "hs": hs,
            "tp": tp
        }
    }
    out_path = f"{args.outdir}/ww3-{slug}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, separators=(",",":"))
    print(f"✅ écrit {out_path} ({len(times_utc)} points)")

if __name__ == "__main__":
    main()
