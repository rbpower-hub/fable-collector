import datetime as dt

from fable import healthcheck


def test_status_age_minutes_uses_embedded_timezone():
    status = {"generated_at": "2026-07-09T17:09:12+01:00"}
    now = dt.datetime.fromisoformat("2026-07-09T18:39:12+02:00")
    assert healthcheck.status_age_minutes(status, now=now) == 30.0


def test_default_health_age_allows_transient_pages_delay():
    assert healthcheck.MAX_AGE_MIN == 150


def test_cache_busted_url_preserves_existing_query(monkeypatch):
    monkeypatch.setattr(healthcheck.time, "time", lambda: 1234567890)
    assert healthcheck._cache_busted_url("https://example.test/status.json") == (
        "https://example.test/status.json?_fable_hc=1234567890"
    )
    assert healthcheck._cache_busted_url("https://example.test/status.json?x=1") == (
        "https://example.test/status.json?x=1&_fable_hc=1234567890"
    )


def test_should_collect_live_skips_when_live_is_recent(monkeypatch):
    monkeypatch.setattr(healthcheck, "_get", lambda _url: {"generated_at": "2026-07-09T12:00:00+00:00"})
    now = dt.datetime.fromisoformat("2026-07-09T12:34:00+00:00")
    should_run, reason = healthcheck.should_collect_live("https://example.test", min_interval_min=50, now=now)
    assert should_run is False
    assert "34 min old" in reason


def test_should_collect_live_runs_when_live_is_stale(monkeypatch):
    monkeypatch.setattr(healthcheck, "_get", lambda _url: {"generated_at": "2026-07-09T12:00:00+00:00"})
    now = dt.datetime.fromisoformat("2026-07-09T13:07:00+00:00")
    should_run, reason = healthcheck.should_collect_live("https://example.test", min_interval_min=50, now=now)
    assert should_run is True
    assert "67 min old" in reason
