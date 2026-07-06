"""Pre-collection validation: sites.yaml + rules.yaml sanity, and export of
rules.normalized.json + sites.normalized.json for downstream consumers.

Replaces ~200 lines of inline Python previously embedded in pages.yml.
Exit code != 0 stops the workflow before any API call.
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

from .config import load_rules, load_sites, normalize_rules, rules_digest, validate_rules, window_bounds

log = logging.getLogger("fable.preflight")


def run_preflight(root: Path, public: Path) -> int:
    ok = True

    # --- sites.yaml ---
    try:
        cfg = load_sites(root / "sites.yaml")
        print(f"✅ sites.yaml OK — {len(cfg.sites)} site(s), home={cfg.home}, schema v{cfg.version}")
        if not cfg.site(cfg.home):
            print(f"❌ home '{cfg.home}' is not one of the configured sites")
            ok = False
    except Exception as e:  # noqa: BLE001
        print(f"❌ sites.yaml: {e}")
        return 1

    # --- rules.yaml ---
    rules = load_rules(root / "rules.yaml")
    problems = validate_rules(rules)
    if problems:
        print(f"❌ rules.yaml: {problems}")
        return 1
    try:
        wmin, wmax = window_bounds(rules)
    except Exception as e:  # noqa: BLE001
        print(f"❌ rules.yaml: invalid window/corridor values: {e}")
        return 1
    print(f"✅ rules.yaml OK — digest={rules_digest(rules)}, family window {wmin}–{wmax} h")

    # --- normalized exports ---
    public.mkdir(parents=True, exist_ok=True)
    try:
        normalized = normalize_rules(rules)
    except Exception as e:  # noqa: BLE001
        print(f"❌ rules.yaml: normalization failed (type error in a threshold?): {e}")
        return 1
    (public / "rules.normalized.json").write_text(
        json.dumps(normalized, ensure_ascii=False, indent=2), encoding="utf-8")
    sites_normalized = {
        "version": cfg.version,
        "tz": cfg.tz,
        "home": cfg.home,
        "sites": [
            {
                "name": s["name"], "slug": s["slug"], "lat": s["lat"], "lon": s["lon"],
                "shelter_bonus_radius_km": s["shelter_bonus_radius_km"],
                "onshore_sectors": [list(t) for t in s["onshore_sectors"]],
                "path": f"{s['slug']}.json",
            } for s in cfg.sites
        ],
    }
    (public / "sites.normalized.json").write_text(
        json.dumps(sites_normalized, ensure_ascii=False, indent=2), encoding="utf-8")
    print("✅ exported public/rules.normalized.json + public/sites.normalized.json")
    return 0 if ok else 1


if __name__ == "__main__":
    logging.basicConfig(level="INFO", format="%(levelname)s %(name)s: %(message)s")
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
    sys.exit(run_preflight(root, root / "public"))
