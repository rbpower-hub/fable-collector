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


def test_scheduled_guard_allows_slow_hosted_runner_setup():
    workflow = yaml.safe_load(
        (ROOT / ".github" / "workflows" / "collect.yml").read_text(encoding="utf-8")
    )

    # GitHub-hosted runner setup has occasionally exceeded three minutes.
    # The guard must not fail before the checkout or FABLE check can start.
    assert workflow["jobs"]["schedule_guard"]["timeout-minutes"] >= 10


def test_external_healthcheck_budget_covers_confirmation_retries():
    workflow = yaml.safe_load(
        (ROOT / ".github" / "workflows" / "healthcheck.yml").read_text(encoding="utf-8")
    )

    # Four 60-second waits, network checks and runner setup must fit in the job.
    assert workflow["jobs"]["health"]["timeout-minutes"] >= 12


def test_refresh_polling_and_fail_safe_freshness_remain_bounded():
    text = (ROOT / ".github" / "workflows" / "collect.yml").read_text(encoding="utf-8")
    health = (ROOT / "fable" / "healthcheck.py").read_text(encoding="utf-8")
    status = (ROOT / "fable" / "status.py").read_text(encoding="utf-8")

    assert 'cron: "7,27,47 * * * *"' in text
    assert 'FABLE_MIN_INTERVAL_MIN: "50"' in text
    assert "MAX_AGE_MIN = 150" in health
    assert "LEEWAY_MIN = 35" in status


def test_healthcheck_confirms_failures_and_routes_semantic_results():
    workflow = yaml.safe_load(
        (ROOT / ".github" / "workflows" / "healthcheck.yml").read_text(encoding="utf-8")
    )
    job = workflow["jobs"]["health"]
    steps = {step["name"]: step for step in job["steps"] if "name" in step}
    check = steps["Check live Pages deployment with confirmation retries"]
    open_incident = steps["Open or update issue on persistent failure"]
    close_incident = steps["Close recovered healthcheck incident"]
    fail_job = steps["Fail job if persistently unhealthy"]

    assert job["env"]["HEALTHCHECK_ATTEMPTS"] == "5"
    assert job["env"]["HEALTHCHECK_DELAY_SECONDS"] == "60"
    assert check["id"] == "check"
    assert 'result="healthy"' in check["run"]
    assert 'result="persistent_failure"' in check["run"]
    assert 'echo "result=${result}"' in check["run"]
    assert check["run"].rstrip().endswith("exit 0")

    assert "steps.check.outputs.result == 'persistent_failure'" in open_incident["if"]
    assert "steps.check.outputs.result == 'healthy'" in close_incident["if"]
    assert "steps.check.outputs.result == 'persistent_failure'" in fail_job["if"]
    assert "exit 1" in fail_job["run"]
