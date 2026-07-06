#!/usr/bin/env python3
"""Probe live des modèles de vagues Open-Meteo Marine pour un spot.

À lancer une fois avant mise en prod (30 s) pour vérifier que les noms de
modèles de rules.yaml (http.marine_model_order) sont bien servis par l'API :

    python tools/probe_marine_models.py --lat 36.9203 --lon 10.2846
"""
import argparse
import datetime as dt
import json
import urllib.request
from urllib.parse import urlencode

MODELS = ["meteofrance_wave", "ncep_gfswave025", "ecmwf_wam025", None]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lat", type=float, default=36.9203)
    ap.add_argument("--lon", type=float, default=10.2846)
    args = ap.parse_args()
    start = dt.date.today()
    end = start + dt.timedelta(days=2)
    for model in MODELS:
        params = {
            "latitude": f"{args.lat:.5f}", "longitude": f"{args.lon:.5f}",
            "hourly": "wave_height,wave_period", "timezone": "Africa/Tunis",
            "start_date": start.isoformat(), "end_date": end.isoformat(),
        }
        if model:
            params["models"] = model
        url = "https://marine-api.open-meteo.com/v1/marine?" + urlencode(params)
        label = model or "default (best_match)"
        try:
            with urllib.request.urlopen(url, timeout=15) as r:
                d = json.loads(r.read())
            h = d.get("hourly") or {}
            hs = [v for v in (h.get("wave_height") or []) if v is not None]
            print(f"✅ {label:28s} {len(hs):3d} points Hs non-nuls "
                  f"(min {min(hs):.2f} max {max(hs):.2f})" if hs else f"⚠️  {label}: aucun point")
        except Exception as e:
            print(f"❌ {label:28s} {e}")


if __name__ == "__main__":
    main()
