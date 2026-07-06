#!/usr/bin/env python3
"""CLI — détecteur de fenêtres Family GO (compatible v1).

Usage:
    python reader.py --from-dir public --out public --home gammarth-port.json \
                     [--min-hours 4] [--max-hours 6]

Par défaut min/max viennent de rules.yaml (window_hours, 4–6 h).
"""

from __future__ import annotations

import argparse
import logging
import os
from pathlib import Path

from fable.windows import run_reader


def main() -> None:
    ap = argparse.ArgumentParser(description="FABLE reader — détecteur de fenêtres Family GO")
    ap.add_argument("--from-dir", default="public", type=Path)
    ap.add_argument("--out", default="public", type=Path)
    ap.add_argument("--home", default=None, help="Fichier JSON du port d'attache (ex: gammarth-port.json)")
    ap.add_argument("--min-hours", default=None, type=int)
    ap.add_argument("--max-hours", default=None, type=int)
    args = ap.parse_args()

    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO"),
        format="%(asctime)s [%(levelname)s] %(message)s",
    )
    run_reader(args.from_dir, args.out, args.home, args.min_hours, args.max_hours)


if __name__ == "__main__":
    main()
