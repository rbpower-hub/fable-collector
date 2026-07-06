"""Post-collection publication steps: catalog, status, windows.md, final checks.

Replaces the remaining inline Python of pages.yml. Exit != 0 blocks deploy.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

from .config import load_sites
from .status import build_catalog, build_status, build_status_html, build_windows_md, final_check
from .util import enable_utf8_stdio

log = logging.getLogger("fable.publish")


def run_publish(root: Path, public: Path) -> int:
    cfg = load_sites(root / "sites.yaml")
    tz = ZoneInfo(cfg.tz)
    expected = [f"{s['slug']}.json" for s in cfg.sites]

    build_catalog(public, tz)
    status = build_status(public, tz, expected_spots=expected)
    build_status_html(public, status)
    build_windows_md(public, tz)

    # .nojekyll to keep static assets served as-is
    (public / ".nojekyll").write_text("", encoding="utf-8")

    problems = final_check(public, expected)
    if problems:
        for p in problems:
            print(f"❌ {p}")
        return 1
    print(f"✅ publication ready — {len(expected)} spots, all outputs present")
    return 0


if __name__ == "__main__":
    enable_utf8_stdio()
    logging.basicConfig(level="INFO", format="%(levelname)s %(name)s: %(message)s")
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
    sys.exit(run_publish(root, root / "public"))
