from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def test_collect_workflow_never_cancels_active_production_refresh():
    workflow = yaml.safe_load(
        (ROOT / ".github" / "workflows" / "collect.yml").read_text(encoding="utf-8")
    )

    assert workflow["concurrency"]["group"] == "fable-pages-refresh"
    assert workflow["concurrency"]["cancel-in-progress"] is False
    assert "concurrency" not in workflow["jobs"]["build"]
    assert "concurrency" not in workflow["jobs"]["deploy"]


def test_refresh_polling_and_fail_safe_freshness_remain_unchanged():
    text = (ROOT / ".github" / "workflows" / "collect.yml").read_text(encoding="utf-8")
    health = (ROOT / "fable" / "healthcheck.py").read_text(encoding="utf-8")
    status = (ROOT / "fable" / "status.py").read_text(encoding="utf-8")

    assert 'cron: "7,27,47 * * * *"' in text
    assert 'FABLE_MIN_INTERVAL_MIN: "50"' in text
    assert "MAX_AGE_MIN = 95" in health
    assert "LEEWAY_MIN = 35" in status
