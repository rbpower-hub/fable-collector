#!/usr/bin/env python3
"""CLI — collecte des prévisions et écriture de public/*.json + index.json.

Usage:
    python collect.py [--window-hours 48] [--only slug1,slug2] [--start-iso ...]

Configuration par variables d'env (compat v1) : FABLE_TZ, FABLE_WINDOW_HOURS,
FABLE_START_ISO, FABLE_ONLY_SITES, FABLE_MODEL_ORDER, FABLE_HTTP_*, etc.
Code retour : 0 si au moins un spot a des données horaires, 2 sinon.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

from fable.collect import Settings, run_collect

ROOT = Path(__file__).resolve().parent


def main() -> int:
    ap = argparse.ArgumentParser(description="fable-collector — collecte Open-Meteo")
    ap.add_argument("--window-hours", type=int, default=None)
    ap.add_argument("--only", default=None, help="CSV de slugs à collecter")
    ap.add_argument("--start-iso", default=None)
    ap.add_argument("--public", type=Path, default=ROOT / "public")
    args = ap.parse_args()

    if args.window_hours is not None:
        os.environ["FABLE_WINDOW_HOURS"] = str(args.window_hours)
    if args.only is not None:
        os.environ["FABLE_ONLY_SITES"] = args.only
    if args.start_iso is not None:
        os.environ["FABLE_START_ISO"] = args.start_iso

    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO"),
        format="%(asctime)s [%(levelname)s] %(message)s",
    )
    results = run_collect(ROOT, args.public, Settings())
    ok = [r for r in results if r["points"] > 0]
    if not ok:
        logging.getLogger("fable").error("no hourly data in requested window — check params/timezone")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
