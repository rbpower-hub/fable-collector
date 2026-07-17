import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_production_recovery_marker_is_published():
    marker = json.loads(
        (ROOT / "public" / "production-recovery.json").read_text(encoding="utf-8")
    )

    assert marker["status"] == "recovered"
    assert marker["safe_base"] == "day-selection-v1"
    assert not (ROOT / "public" / "js" / "off-hours-refinements.js").exists()
