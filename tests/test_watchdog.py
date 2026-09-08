import datetime as dt
import sys

from fable import watchdog


def test_recovery_does_not_duplicate_active_or_recent_runs():
    now = dt.datetime.fromisoformat("2026-09-08T17:30:00+00:00")
    assert watchdog.recovery_pending([{"status": "in_progress"}], now)
    assert watchdog.recovery_pending([{
        "status": "completed", "event": "workflow_dispatch", "created_at": "2026-09-08T17:25:00Z",
    }], now)
    assert not watchdog.recovery_pending([{
        "status": "completed", "event": "schedule", "created_at": "2026-09-08T17:25:00Z",
    }], now)


def test_watchdog_checks_without_dispatch_by_default(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["watchdog"])
    monkeypatch.setattr(watchdog, "check_live", lambda _base: ["stale"])
    monkeypatch.setattr(watchdog, "github_request", lambda *args: (_ for _ in ()).throw(AssertionError()))
    assert watchdog.main() == 1


def test_watchdog_dispatches_when_stale_and_no_run_pending(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["watchdog", "--dispatch"])
    monkeypatch.setenv("FABLE_GITHUB_TOKEN", "test-only")
    monkeypatch.setattr(watchdog, "check_live", lambda _base: ["stale"])
    calls = []

    def request(repo, token, endpoint, payload=None):
        calls.append((endpoint, payload))
        return {"workflow_runs": []}

    monkeypatch.setattr(watchdog, "github_request", request)
    assert watchdog.main() == 0
    assert calls[-1] == ("dispatches", {"ref": "main"})


def test_healthy_production_does_not_need_credentials(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["watchdog", "--dispatch"])
    monkeypatch.delenv("FABLE_GITHUB_TOKEN", raising=False)
    monkeypatch.setattr(watchdog, "check_live", lambda _base: [])
    assert watchdog.main() == 0
