"""Compare le verdict horaire du moteur avec celui de la vue mobile.

Usage :
    python tools/compare_hour_verdicts.py <dossier_public> [slug ...]

Ecrit sur stdout un JSON : pour chaque spot et chaque heure, l'etat calcule par
fable.window_policy (family / prudent / nogo) au phase "transit". Le script
mobile equivalent (public/mobile/js/hour-verdict.js) doit produire la meme
sequence ; toute divergence est un bug de portage.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml

from fable.window_models import Thresholds, load_site
from fable.window_policy import hour_ok_for_phase


def state_for(site, index, th) -> str:
    ok_family, detail = hour_ok_for_phase(site, index, "transit", th, tier="family")
    if ok_family:
        return "go"
    if th.prudent_enabled:
        ok_prudent, _ = hour_ok_for_phase(site, index, "transit", th, tier="prudent")
        if ok_prudent:
            return "prudent"
    return "nogo"


def main() -> int:
    public = Path(sys.argv[1] if len(sys.argv) > 1 else "public")
    # Le moteur consomme le schema PLAT de rules.yaml, pas rules.normalized.json.
    rules = yaml.safe_load(Path("rules.yaml").read_text(encoding="utf-8"))
    th = Thresholds.from_rules(rules)
    index = json.loads((public / "index.json").read_text(encoding="utf-8"))
    wanted = set(sys.argv[2:])
    out = {}
    for entry in index.get("spots", []):
        if wanted and entry["slug"] not in wanted:
            continue
        site = load_site(public / entry["path"])
        if site is None:
            continue
        states = [state_for(site, i, th) for i in range(len(site.times))]
        out[entry["slug"]] = states
    json.dump(out, sys.stdout, ensure_ascii=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
