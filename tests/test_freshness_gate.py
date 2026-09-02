from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_freshness_gate_uses_published_warning_and_hard_deadlines():
    script = (ROOT / "public" / "freshness-gate.js").read_text(encoding="utf-8")

    assert "const FALLBACK_LIMIT_MIN = 95" in script
    assert "const LEEWAY_MIN = 35" in script
    assert "cadence + LEEWAY_MIN" in script
    assert "status?.refresh_due_after" in script
    assert "status?.stale_after" in script
    assert "delayed:fresh && age_min > warning_min" in script
    assert "window.FABLEFreshness" in script


def test_stale_data_neutralizes_go_and_forces_family_hero():
    script = (ROOT / "public" / "freshness-gate.js").read_text(encoding="utf-8")

    assert ".go.stale" in script
    assert "badge.classList.toggle('stale', stale)" in script
    assert "Données périmées — ne pas se fier au tableau" in script
    assert "The board is no longer reliable" in script
    assert "stale-data-banner" in script
    assert "role', 'alert'" in script


def test_delayed_refresh_warns_without_neutralizing_go():
    script = (ROOT / "public" / "freshness-gate.js").read_text(encoding="utf-8")

    assert "Actualisation automatique retardée" in script
    assert "setBadgeState(stale)" in script
    assert "setBanner(freshness, currentStatus)" in script
    assert "fable-data-delayed" in script


def test_missing_status_is_fail_safe_stale():
    script = (ROOT / "public" / "freshness-gate.js").read_text(encoding="utf-8")

    assert "apply(response.ok ? await response.json() : null)" in script
    assert "catch {\n      apply(null);" in script
    assert "const stale = !state.fresh" in script
