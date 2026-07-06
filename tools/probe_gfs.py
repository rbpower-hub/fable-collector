#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
probe_gfs.py — offline tester for adding Open-Meteo GFS as a secondary model.

Usage examples:
  python probe_gfs.py --lat 36.877 --lon 10.613 --spot "ras-fartass.json" --hours 6 --tz "Africa/Tunis"
  python probe_gfs.py --lat 37.063 --lon 11.008 --spot "el-haouaria.json" --start "2025-09-27T11:00" --hours 9

No changes to your pipeline. Just prints a report.
"""

import json
import math
import sys
import argparse
from datetime import datetime, timezone, timedelta
from urllib.request import urlopen
from urllib.error import URLError

# -------------- utilities --------------

def fetch_json(url: str) -> dict:
    try:
        with urlopen(url, timeout=15) as r:
            return json.loads(r.read().decode("utf-8"))
    except URLError as e:
        print(f"[ERR] fetch failed: {e}", file=sys.stderr)
        return {}

def load_spot_series(path: str) -> dict:
    """
    Accepts both of your schemas:
      - 'hourly.*' (like Open-Meteo relay)
      - 'hours[]'  (your normalized rows)
    Returns dict with lists: time[], wind_kmh[], gust_kmh[], wind_dir_deg[]
    """
    with open(path, "r", encoding="utf-8") as f:
        js = json.load(f)

    hourly = js.get("hourly") or {}
    if hourly:
        return {
            "time": hourly.get("time", []) or [],
            "wind_kmh": hourly.get("wind_speed_10m", []) or [],
            "gust_kmh": hourly.get("wind_gusts_10m", []) or [],
            "wind_dir_deg": hourly.get("wind_direction_10m", []) or [],
            "meta": js.get("meta", {}),
        }

    rows = js.get("hours") or []
    return {
        "time": [r.get("time") for r in rows],
        "wind_kmh": [r.get("wind_kmh") for r in rows],
        "gust_kmh": [r.get("gust_kmh") for r in rows],
        "wind_dir_deg": [r.get("wind_dir_deg", r.get("wind_dir")) for r in rows],
        "meta": js.get("meta", {}),
    }

def fetch_gfs(lat: float, lon: float, tz: str = "auto") -> dict:
    base = "https://api.open-meteo.com/v1/gfs"
    params = (
        f"?latitude={lat:.6f}&longitude={lon:.6f}"
        f"&hourly=wind_speed_10m,wind_gusts_10m,wind_direction_10m"
        f"&timezone={tz}"
    )
    js = fetch_json(base + params)
    hourly = (js or {}).get("hourly", {})
    return {
        "time": hourly.get("time", []) or [],
        "wind_kmh": hourly.get("wind_speed_10m", []) or [],
        "gust_kmh": hourly.get("wind_gusts_10m", []) or [],
        "wind_dir_deg": hourly.get("wind_direction_10m", []) or [],
        "meta": {"model": "gfs", "lat": lat, "lon": lon, "tz": tz},
    }

def to_ts(iso: str) -> float:
    # tolerant ISO → POSIX seconds
    if not iso:
        return float("nan")
    try:
        if iso.endswith("Z"):
            return datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp()
        return datetime.fromisoformat(iso).timestamp()
    except Exception:
        # try without seconds
        try:
            return datetime.strptime(iso[:16], "%Y-%m-%dT%H:%M").replace(tzinfo=timezone.utc).timestamp()
        except Exception:
            return float("nan")

def nearest_idx(times, iso):
    t = to_ts(iso)
    best, idx = 10**20, -1
    for i, s in enumerate(times or []):
        tt = to_ts(s)
        if math.isfinite(tt):
            d = abs(tt - t)
            if d < best:
                best, idx = d, i
    return idx

def circ_diff_deg(a, b):
    if a is None or b is None:
        return None
    try:
        d = abs((float(a) - float(b)) % 360.0)
        return min(d, 360.0 - d)
    except Exception:
        return None

def window_slice(series, i0, n=6):
    out = {}
    L = len(series.get("time", []))
    jmax = min(L, i0 + n)
    for k in ("time", "wind_kmh", "gust_kmh", "wind_dir_deg"):
        arr = series.get(k) or []
        out[k] = arr[i0:jmax] if 0 <= i0 < L else []
    return out

def agreement(icon: dict, gfs: dict, start_iso: str, hours: int = 6):
    i0 = nearest_idx(icon.get("time"), start_iso)
    j0 = nearest_idx(gfs.get("time"),  start_iso)
    if i0 < 0 or j0 < 0:
        return None

    A = window_slice(icon, i0, hours)
    B = window_slice(gfs,  j0, hours)

    diffs_wind, diffs_gust, diffs_dir = [], [], []
    n = min(len(A["time"]), len(B["time"]))
    for k in range(n):
        a_w, b_w = A["wind_kmh"][k], B["wind_kmh"][k]
        a_g, b_g = A["gust_kmh"][k], B["gust_kmh"][k]
        a_d, b_d = A["wind_dir_deg"][k], B["wind_dir_deg"][k]

        if a_w is not None and b_w is not None:
            try: diffs_wind.append(abs(float(a_w) - float(b_w)))
            except: pass
        if a_g is not None and b_g is not None:
            try: diffs_gust.append(abs(float(a_g) - float(b_g)))
            except: pass
        ddir = circ_diff_deg(a_d, b_d)
        if ddir is not None:
            diffs_dir.append(ddir)

    def avg(xs): 
        xs = [float(x) for x in xs if x is not None and math.isfinite(float(x))]
        return sum(xs)/len(xs) if xs else None

    avg_w = avg(diffs_wind)
    avg_g = avg(diffs_gust)
    avg_d = avg(diffs_dir)

    # simple confidence mapping (tune later)
    conf = None
    if avg_w is not None:
        if avg_w <= 5 and (avg_g is None or avg_g <= 8) and (avg_d is None or avg_d <= 30):
            conf = "high"
        elif avg_w <= 10 and (avg_g is None or avg_g <= 15):
            conf = "medium"
        else:
            conf = "low"

    return {
        "points_compared": n,
        "avg_abs_delta_wind_kmh": round(avg_w, 1) if avg_w is not None else None,
        "avg_abs_delta_gust_kmh": round(avg_g, 1) if avg_g is not None else None,
        "avg_dir_spread_deg": round(avg_d, 0) if avg_d is not None else None,
        "suggested_confidence": conf,
    }

# -------------- CLI --------------

def main():
    ap = argparse.ArgumentParser(description="Probe Open-Meteo GFS vs your spot JSON")
    ap.add_argument("--lat", type=float, required=True)
    ap.add_argument("--lon", type=float, required=True)
    ap.add_argument("--spot", type=str, required=False, help="Path to your spot JSON (for comparison)")
    ap.add_argument("--start", type=str, required=False, help="ISO like 2025-09-27T11:00 (default = now)")
    ap.add_argument("--hours", type=int, default=6, help="Hours to compare from start")
    ap.add_argument("--tz", type=str, default="auto")
    ap.add_argument("--save-gfs", type=str, help="Optional path to dump fetched GFS JSON")
    args = ap.parse_args()

    start_iso = args.start or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:00")

    print("== Probe settings ==")
    print(f" Lat/Lon: {args.lat:.5f}, {args.lon:.5f}")
    print(f" Start:   {start_iso}  (compare {args.hours}h)")
    print(f" TZ:      {args.tz}")
    if args.spot: print(f" Spot:    {args.spot}")
    print()

    gfs = fetch_gfs(args.lat, args.lon, args.tz)
    print(f"GFS points: {len(gfs['time'])} (model={gfs['meta'].get('model')})")
    if args.save_gfs:
        with open(args.save_gfs, "w", encoding="utf-8") as f:
            json.dump({"hourly": gfs}, f, ensure_ascii=False, indent=2)
        print(f"Saved raw GFS to {args.save_gfs}")
    print()

    if not args.spot:
        print("No spot JSON provided — connectivity OK. Re-run with --spot to compute agreement.")
        return

    try:
        spot = load_spot_series(args.spot)
    except Exception as e:
        print(f"[ERR] failed to read spot JSON: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"Spot points: {len(spot['time'])} ({spot.get('meta',{}).get('source','local-json')})")
    rep = agreement(spot, gfs, start_iso, hours=args.hours)
    if not rep:
        print("Could not align time series; check start time and JSON times.")
        sys.exit(2)

    print("\n== Agreement report ==")
    for k, v in rep.items():
        print(f" {k}: {v}")

    # quick human tip
    tips = []
    if rep["avg_abs_delta_wind_kmh"] is not None and rep["avg_abs_delta_wind_kmh"] > 10:
        tips.append("Wind speeds diverge >10 km/h; try shorter horizon (3–6h) or check local gustiness.")
    if rep["avg_dir_spread_deg"] is not None and rep["avg_dir_spread_deg"] > 50:
        tips.append("Wind direction spread >50°; coastal turning likely — downweight direction in confidence.")
    if rep["points_compared"] < max(2, args.hours//2):
        tips.append("Few overlapping points — verify timezone or start time.")
    if tips:
        print("\n== Hints ==")
        for t in tips: print(" - " + t)

if __name__ == "__main__":
    main()
