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
    assert "getDisplayedNavigationWindows(key, state.windows)" in script
    assert "renderLongTripLine(line, row)" in script
    assert "line.dataset.normalizedNavigation = 'true'" in script
    assert "aller simple — retour à planifier séparément" in script
    assert "offshore_one_way_beta" in script


def test_activity_cards_publish_stable_day_metadata():
    script = (ROOT / "public" / "activity-board.js").read_text(encoding="utf-8")

    assert 'data-family-day-key="${esc(dateKey)}"' in script
    assert 'data-start="${esc(rec.start || \'\')}"' in script
    assert "timeZone:TUNIS_TZ" in script
    assert "fable:activities-rendered" in script
    assert 'class="activity-port-tabs"' in script
    assert 'data-activity-port="${esc(slug)}"' in script
    assert "selectedDay()" in script
    assert "show every port" not in script
    assert "voir tous les ports" not in script
    assert "activity-score" not in script


def test_long_trip_activities_are_not_invented_from_a_crossing_window():
    script = (ROOT / "public" / "activity-board.js").read_text(encoding="utf-8")

    assert "Le créneau publié valide uniquement la traversée" in script
    assert "fenêtre météo locale distincte" in script


def test_off_hours_recommendations_are_not_rendered_as_family_activities():
    script = (ROOT / "public" / "activity-board.js").read_text(encoding="utf-8")

    assert "rec.category || sourceWindow.category || 'family'" in script
    assert ".toLowerCase() === 'family'" in script
    assert 'data-category="${esc(category)}"' in script


def test_activity_fallback_does_not_claim_specialized_safety():
    script = (ROOT / "public" / "js" / "day-selection.js").read_text(encoding="utf-8")

    assert "Aucune activité spécialisée ne passe ses propres limites de confort" in script
    assert "Une sortie familiale sur l’eau reste possible" in script
    assert "tripMode !== 'one_way_multi_day'" in script


def test_long_trip_cards_are_not_hidden_from_family_navigation():
    gate = (ROOT / "public" / "family-content-gate.js").read_text(encoding="utf-8")

    assert "line.classList.remove('expert-only')" in gate
    assert "line.classList.toggle('expert-only', isLongTrip(slug))" not in gate


def test_direction_is_part_of_the_annotation_identity():
    annotations = (ROOT / "public" / "reasons-debug.js").read_text(encoding="utf-8")

    assert "item.direction || \"\"" in annotations
    assert "node.dataset.direction || \"\"" in annotations


def test_activity_mutations_are_not_observed_as_feedback():
    script = (ROOT / "public" / "js" / "day-selection.js").read_text(encoding="utf-8")

    assert "!target?.closest?.('#fable-activities')" in script


def test_navigation_counts_keep_non_family_routes_and_port_filter():
    script = (ROOT / "public" / "js" / "day-selection.js").read_text(encoding="utf-8")

    assert "categories:['family', 'off_hours', 'watch']" in script
    assert "navigationWindowBreakdown(rows)" in script
    assert "FABLEActivityBoard?.getPortFilter?.()" in script


def test_failed_activity_refresh_drops_stale_payload():
    script = (ROOT / "public" / "activity-board.js").read_text(encoding="utf-8")

    catch_body = script.split("} catch {", 1)[1].split("}", 1)[0]
    assert "lastPayload = null" in catch_body
