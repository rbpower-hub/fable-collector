#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Probe Open-Meteo models quickly (full vs safe varsets), plus Marine.
Usage:
  python scripts/probe_models.py --lat 36.9203 --lon 10.2846 --hours 72 --tz Africa/Tunis \
    --models icon_seamless,gfs_seamless,ecmwf_ifs04,default --timeout 10 --retries 1
"""

import argparse, json, sys, time, random, urllib.request
import datetime as dt
from urllib.parse import urlencode

FULL = ["wind_speed_10m","wind_gusts_10m","wind_direction_10m","weather_code","visibility","surface_pressure","precipitation"]
SAFE = ["wind_speed_10m","wind_gusts_10m","wind_direction_10m","weather_code","visibility"]
MARINE = ["wave_height","wave_period"]

def http_get(url, timeout, retries):
    last = None
    for a in range(retries+1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "fable-probe/1.0"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                if r.status != 200:
                    raise RuntimeError(f"HTTP {r.status}")
                return json.loads(r.read().decode("utf-8"))
        except Exception as e:
            last = e
            if a < retries:
                time.sleep(0.8 + a*0.8 + random.random()*0.4)
    raise RuntimeError(f"GET failed after retries: {last}")

def payload_ok(p):
    return isinstance(p,dict) and isinstance(p.get("hourly"),dict) and isinstance(p["hourly"].get("time"),list) and len(p["hourly"]["time"])>0

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lat", type=float, required=True)
    ap.add_argument("--lon", type=float, required=True)
    ap.add_argument("--hours", type=int, default=72)
    ap.add_argument("--tz", default="Africa/Tunis")
    ap.add_argument("--models", default="icon_seamless,gfs_seamless,ecmwf_ifs04,default")
    ap.add_argument("--timeout", type=int, default=10)
    ap.add_argument("--retries", type=int, default=1)
    args = ap.parse_args()

    now_local = dt.datetime.now(dt.timezone.utc).astimezone(dt.timezone(dt.timedelta(0))).replace(microsecond=0)
    # Open-Meteo start/end accept dates; we’ll cover the next N hours by spanning days
    start_date = (dt.datetime.now(dt.timezone.utc)).astimezone(dt.timezone(dt.timedelta(0))).date()
    end_date   = (dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=args.hours)).date()

    print("=== FORECAST (Open-Meteo /v1/forecast) ===")
    ok_full, ok_safe, fails = [], [], []

    for model in [m.strip() for m in args.models.split(",") if m.strip()]:
        # FULL
        q = {
            "latitude": f"{args.lat:.5f}",
            "longitude": f"{args.lon:.5f}",
            "hourly": ",".join(FULL),
            "timezone": args.tz,
            "timeformat":"iso8601",
            "windspeed_unit":"kmh",
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
        }
        if model != "default":
            q["models"]=model
        url_full = "https://api.open-meteo.com/v1/forecast?" + urlencode(q)

        try:
            p = http_get(url_full, timeout=args.timeout, retries=args.retries)
            if payload_ok(p):
                h = p["hourly"]["time"]
                print(f"  ✔ {model:12s} OK(full)      hours={len(h)} first={h[0]} last={h[-1]}")
                ok_full.append(model)
            else:
                print(f"  ✖ {model:12s} FAIL(full):   structure/hourly missing")
                # try SAFE
                raise RuntimeError("bad payload(full)")
        except Exception as e:
            print(f"  ✖ {model:12s} FAIL(full):   {e}")

            # SAFE
            q["hourly"]=",".join(SAFE)
            url_safe = "https://api.open-meteo.com/v1/forecast?" + urlencode(q)
            try:
                p = http_get(url_safe, timeout=args.timeout, retries=args.retries)
                if payload_ok(p):
                    h = p["hourly"]["time"]
                    print(f"  ✔ {model:12s} OK(safe)      hours={len(h)} first={h[0]} last={h[-1]}")
                    ok_safe.append(model)
                else:
                    print(f"  ✖ {model:12s} FAIL(safe):  structure/hourly missing")
                    fails.append(model)
            except Exception as e2:
                print(f"  ✖ {model:12s} FAIL(safe):  {e2}")
                fails.append(model)

    print("\n=== MARINE (Open-Meteo Marine) ===")
    mq = {
        "latitude": f"{args.lat:.5f}",
        "longitude": f"{args.lon:.5f}",
        "hourly": ",".join(MARINE),
        "timezone": args.tz,
        "timeformat":"iso8601",
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
    }
    url_marine = "https://marine-api.open-meteo.com/v1/marine?" + urlencode(mq)
    try:
        mp = http_get(url_marine, timeout=args.timeout, retries=args.retries)
        if payload_ok(mp):
            h = mp["hourly"]["time"]
            print(f"  ✔ Marine OK       hours={len(h)} first={h[0]} last={h[-1]}")
        else:
            print("  ✖ Marine FAIL:    structure/hourly missing")
    except Exception as eme:
        print(f"  ✖ Marine FAIL:    {eme}")

    print("\n=== RÉCAP ===")
    print(f"Forecast OK(full):     {ok_full if ok_full else '-'}")
    print(f"Forecast OK(safe):     {ok_safe if ok_safe else '-'}")
    print(f"Forecast FAIL:         {fails if fails else '-'}")

if __name__ == "__main__":
    main()
