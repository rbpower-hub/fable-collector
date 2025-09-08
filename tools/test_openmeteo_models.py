#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse, json, time, random
import datetime as dt
from urllib.parse import urlencode
from zoneinfo import ZoneInfo
import urllib.request

# -------- Config par défaut (modifiable en CLI) --------
DEFAULT_MODELS = ["ecmwf_ifs04","icon_seamless","gfs_seamless","default"]

# Jeu "collector-like"
ECMWF_KEYS = [
    "wind_speed_10m","wind_gusts_10m","wind_direction_10m",
    "weather_code","visibility","surface_pressure","precipitation"
]
SAFE_HOURLY = ["wind_speed_10m","wind_gusts_10m","wind_direction_10m","weather_code","visibility"]

MARINE_KEYS = ["wave_height","wave_period","swell_wave_height","swell_wave_period"]

# Modèles réellement acceptés par /v1/forecast
MODEL_ALIASES = {
    "ecmwf_ifs04":  ["ecmwf_ifs04"],
    "icon_seamless":["icon_seamless"],
    "gfs_seamless": ["gfs_seamless"],
    "default":      ["default", None],
}

def expand_models(order):
    out = []
    seen = set()
    for m in order:
        for a in MODEL_ALIASES.get(m, [m]):
            k = a or "default"
            if k not in seen:
                seen.add(k); out.append(a)
    return out

def http_get_json(url, retry=2, timeout=12):
    last = None
    for attempt in range(retry+1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent":"fable-healthcheck/1.0"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                if r.status != 200:
                    raise RuntimeError(f"HTTP {r.status}")
                return json.loads(r.read().decode("utf-8"))
        except Exception as e:
            last = e
            if attempt < retry:
                time.sleep(0.8 + attempt*1.2 + random.random()*0.4)
    raise RuntimeError(f"GET failed after retries: {last}")

def forecast_url(lat, lon, tz, start_date, end_date, model=None, hourly_keys=None, include_daily=True):
    params = {
        "latitude": f"{lat:.5f}",
        "longitude": f"{lon:.5f}",
        "timezone": tz,
        "timeformat": "iso8601",
        "windspeed_unit": "kmh",
        "hourly": ",".join(hourly_keys or ECMWF_KEYS),
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
    }
    if include_daily:
        params["daily"] = "sunrise,sunset,moon_phase,moonrise,moonset"
    if model and model != "default":
        params["models"] = model
    return "https://api.open-meteo.com/v1/forecast?" + urlencode(params)

def marine_url(lat, lon, tz, start_date, end_date):
    params = {
        "latitude": f"{lat:.5f}",
        "longitude": f"{lon:.5f}",
        "timezone": tz,
        "timeformat": "iso8601",
        "hourly": ",".join(MARINE_KEYS),
        "wave_height_unit": "m",
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
    }
    return "https://marine-api.open-meteo.com/v1/marine?" + urlencode(params)

def payload_ok(p):
    return isinstance(p, dict) and isinstance(p.get("hourly"), dict) and isinstance(p["hourly"].get("time"), list) and len(p["hourly"]["time"])>0

def has_wind_arrays(p):
    h = (p or {}).get("hourly") or {}
    def _has(key):
        arr = h.get(key) or []
        return isinstance(arr, list) and any(x is not None for x in arr)
    return _has("wind_speed_10m") and _has("wind_gusts_10m")

def test_forecast(lat, lon, tz, start_date, end_date, models, timeout, retries):
    results = []
    print("\n=== FORECAST (Open-Meteo /v1/forecast) ===")
    for m in expand_models(models):
        label = m or "default"
        # 1) Jeu complet
        url_full = forecast_url(lat, lon, tz, start_date, end_date, m, ECMWF_KEYS, include_daily=True)
        try:
            p = http_get_json(url_full, retry=retries, timeout=timeout)
            if payload_ok(p) and has_wind_arrays(p):
                t = p["hourly"]["time"]
                print(f"  ✔ {label:<12} OK(full)    hours={len(t)} first={t[0]} last={t[-1]}")
                results.append((label, "OK(full)"))
                continue
            else:
                why = p.get("reason") if isinstance(p, dict) else "bad json"
                print(f"  … {label:<12} partial/invalid(full): {why}")
        except Exception as e:
            print(f"  ✖ {label:<12} FAIL(full): {e}")

        # 2) SAFE vars (sans daily)
        url_safe = forecast_url(lat, lon, tz, start_date, end_date, m, SAFE_HOURLY, include_daily=False)
        try:
            ps = http_get_json(url_safe, retry=retries, timeout=timeout)
            if payload_ok(ps) and has_wind_arrays(ps):
                t = ps["hourly"]["time"]
                print(f"  ✔ {label:<12} OK(safe_vars) hours={len(t)} first={t[0]} last={t[-1]}")
                results.append((label, "OK(safe_vars)"))
            else:
                why = ps.get("reason") if isinstance(ps, dict) else "bad json"
                print(f"  ✖ {label:<12} FAIL(safe_vars): {why}")
                results.append((label, "FAIL"))
        except Exception as e2:
            print(f"  ✖ {label:<12} FAIL(safe_vars): {e2}")
            results.append((label, "FAIL"))
    return results

def test_marine(lat, lon, tz, start_date, end_date, timeout, retries):
    print("\n=== MARINE (Open-Meteo Marine) ===")
    url = marine_url(lat, lon, tz, start_date, end_date)
    try:
        p = http_get_json(url, retry=retries, timeout=timeout)
        if not payload_ok(p):
            print(f"  ✖ Marine FAIL: {p.get('reason','no hourly/time') if isinstance(p,dict) else 'bad json'}")
            return "FAIL"
        h = p["hourly"]
        hs = h.get("wave_height") or h.get("significant_wave_height") or []
        tp = h.get("wave_period") or []
        hs_ok = isinstance(hs, list) and any(x is not None for x in hs)
        tp_ok = isinstance(tp, list) and any(x is not None for x in tp)
        t = h["time"]
        if hs_ok and tp_ok:
            print(f"  ✔ Marine OK       hours={len(t)} first={t[0]} last={t[-1]}")
            return "OK"
        elif hs_ok or tp_ok:
            print(f"  … Marine PARTIAL  hours={len(t)} (hs_ok={hs_ok}, tp_ok={tp_ok})")
            return "PARTIAL"
        else:
            print("  ✖ Marine FAIL: no hs/tp data")
            return "FAIL"
    except Exception as e:
        print(f"  ✖ Marine FAIL: {e}")
        return "FAIL"

def main():
    ap = argparse.ArgumentParser(description="Healthcheck Open-Meteo models (forecast + marine)")
    ap.add_argument("--lat", type=float, default=36.9203, help="Latitude (default: Gammarth)")
    ap.add_argument("--lon", type=float, default=10.2846, help="Longitude (default: Gammarth)")
    ap.add_argument("--tz", default="Africa/Tunis", help="Timezone name")
    ap.add_argument("--hours", type=int, default=48, help="Window length in hours")
    ap.add_argument("--models", default=",".join(DEFAULT_MODELS), help="Comma-separated model list")
    ap.add_argument("--timeout", type=int, default=12, help="HTTP timeout (s)")
    ap.add_argument("--retries", type=int, default=2, help="HTTP retries")
    args = ap.parse_args()

    tz = ZoneInfo(args.tz)
    now_local = dt.datetime.now(tz).replace(minute=0, second=0, microsecond=0)
    start_date = now_local.date()
    end_date = (now_local + dt.timedelta(hours=args.hours)).date()

    print(f"Point: ({args.lat:.5f}, {args.lon:.5f}) TZ={args.tz} window={start_date}→{end_date} ({args.hours}h)")
    model_list = [m.strip() for m in args.models.split(",") if m.strip()]

    fr = test_forecast(args.lat, args.lon, args.tz, start_date, end_date, model_list, args.timeout, args.retries)
    mr = test_marine(args.lat, args.lon, args.tz, start_date, end_date, args.timeout, args.retries)

    # Récap
    print("\n=== RÉCAP ===")
    ok_full = [m for m,s in fr if s=="OK(full)"]
    ok_safe = [m for m,s in fr if s=="OK(safe_vars)"]
    fail    = [m for m,s in fr if s=="FAIL"]
    print(f"Forecast OK(full):     {ok_full or '-'}")
    print(f"Forecast OK(safe_vars):{ok_safe or '-'}")
    print(f"Forecast FAIL:         {fail or '-'}")
    print(f"Marine:                {mr}")

    # Code retour non-zero si tout a échoué
    if not ok_full and not ok_safe:
        raise SystemExit(2 if mr!="OK" else 1)

if __name__ == "__main__":
    main()
