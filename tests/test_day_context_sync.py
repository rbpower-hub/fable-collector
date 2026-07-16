from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_day_selection_filters_all_family_context_panels():
    script = (ROOT / "public" / "js" / "day-selection.js").read_text(encoding="utf-8")

    assert "function syncNavigationWindows()" in script
    assert "function syncWarnings()" in script
    assert "function syncActivityCards()" in script
    assert "data-day-warning-context" in script
    assert "navigation-day-empty" in script
    assert "activity-fallback" in script
    assert "Africa/Tunis" in script
    assert "fable:day-selected" in script


def test_activity_cards_publish_stable_day_metadata():
    script = (ROOT / "public" / "activity-board.js").read_text(encoding="utf-8")

    assert 'data-family-day-key="${esc(dateKey)}"' in script
    assert 'data-start="${esc(rec.start || \'\')}"' in script
    assert "timeZone:TUNIS_TZ" in script
    assert "fable:activities-rendered" in script


def test_activity_fallback_does_not_claim_specialized_safety():
    script = (ROOT / "public" / "js" / "day-selection.js").read_text(encoding="utf-8")

    assert "Aucune activité spécialisée ne passe ses propres limites de confort" in script
    assert "Une sortie familiale sur l’eau reste possible" in script
    assert "tripMode !== 'one_way_multi_day'" in script


def test_activity_mutations_are_not_observed_as_feedback():
    script = (ROOT / "public" / "js" / "day-selection.js").read_text(encoding="utf-8")

    assert "!target?.closest?.('#fable-activities')" in script
