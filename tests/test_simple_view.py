from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_dashboard_loads_isolated_simple_view():
    html = (ROOT / "public" / "index.html").read_text(encoding="utf-8")
    script = (ROOT / "public" / "simple-view.js").read_text(encoding="utf-8")

    assert '<script src="./simple-view.js?v=20260825-connected-panel" defer></script>' in html
    assert "simple-board-mode" in script
    assert "family-board-mode" in script
    assert "expert-board-mode" in script
    assert "fable_board_mode" in script


def test_simple_view_is_decision_first_and_keeps_no_go_reasons_collapsed():
    script = (ROOT / "public" / "simple-view.js").read_text(encoding="utf-8")

    assert "SORTIE POSSIBLE" in script
    assert "SORTIE PRUDENTE" in script
    assert "SORTIE DÉCONSEILLÉE" in script
    assert 'id="simple-reasons" class="simple-reasons" hidden' in script
    assert 'aria-expanded="false"' in script
    assert "diagnostics.first_blocker" in script
    assert "hasMarineDataError" in script
    assert "Données de vagues indisponibles" in script
    assert "Wave data unavailable" in script
    assert "بيانات الأمواج غير متاحة" in script
    assert 'class="simple-data-state marine" role="alert"' in script


def test_simple_view_has_mobile_navigation_and_three_day_overview():
    script = (ROOT / "public" / "simple-view.js").read_text(encoding="utf-8")

    assert "simple-bottom-nav" in script
    assert "simple-day-track" in script
    assert "[0, 1, 2].map" in script
    assert "@media(max-width:520px)" in script
    assert "env(safe-area-inset-bottom)" in script
    assert 'id="simple-navigation"' in script
    assert "simple-window-card" in script


def test_three_day_selector_precedes_and_controls_all_selected_day_widgets():
    script = (ROOT / "public" / "simple-view.js").read_text(encoding="utf-8")

    assert script.index('id="simple-three-days"') < script.index('id="simple-decision"')
    assert 'role="tablist"' in script
    assert 'role="tab"' in script
    assert 'aria-selected="${selected}"' in script
    assert 'id="simple-selected-day-content"' in script
    assert 'role="tabpanel"' in script
    assert 'class="simple-day-context ${selectedTone}"' in script
    assert 'data-selected-tone="${selectedTone}"' in script
    assert '.simple-day[aria-selected="true"]::after' in script
    assert 'border:2px solid var(--selection-color)' in script
    assert "['ArrowLeft', 'ArrowRight', 'Home', 'End']" in script


def test_simple_view_refreshes_from_published_dashboard_contract():
    script = (ROOT / "public" / "simple-view.js").read_text(encoding="utf-8")

    assert "fetch('windows.json'" in script
    assert "fetch('status.json'" in script
    assert "fetch('recommendations.json'" in script
    assert "fetch('rules.normalized.json'" in script
    assert "document.addEventListener('fable:dashboard-updated', refresh)" in script


def test_simple_view_product_memory_preserves_future_phases():
    memory = (ROOT / "docs" / "SIMPLE-VIEW-PHASE-1.md").read_text(encoding="utf-8")

    assert "Phase 2" in memory
    assert "Phase 3" in memory
    assert "Phase 4" in memory
    assert "Ne pas afficher les raisons du NO-GO par défaut" in memory


def test_simple_view_phase_two_has_timeline_trends_and_data_states():
    script = (ROOT / "public" / "simple-view.js").read_text(encoding="utf-8")

    assert "simple-timeline" in script
    assert "renderConditions" in script
    assert "wind_speed_10m" in script
    assert "simple-spark" in script
    assert "simple-chart-threshold" in script
    assert "family_max_kmh" in script
    assert "family_max_hs_m" in script
    assert "navigationVerdictForDay" in script
    assert "result?.state === 'STALE'" in script
    assert "Prévisions indisponibles" in script


def test_simple_view_phase_three_supports_rtl_keyboard_and_small_screens():
    script = (ROOT / "public" / "simple-view.js").read_text(encoding="utf-8")

    assert "الوضع المبسّط" in script
    assert 'html[dir="rtl"] .simple-shell' in script
    assert "@media(max-width:350px)" in script
    assert "@media(forced-colors:active)" in script
    assert "prefers-reduced-motion:reduce" in script
    assert ":focus-visible" in script
    assert 'aria-current="date"' in script
    assert "fable:languagechange" in script
    assert "ar-TN" in script


def test_simple_view_phase_four_is_an_explicit_reversible_offer():
    script = (ROOT / "public" / "simple-view.js").read_text(encoding="utf-8")

    assert "Essayer la Vue Simple" in script
    assert "Try Simple View" in script
    assert "جرّب الوضع المبسّط" in script
    assert "localStorage.setItem(MODE_KEY, 'family')" in script
    assert "fable:simple-view-ready" in script


def test_simple_view_is_default_and_deep_links_are_explicit():
    script = (ROOT / "public" / "simple-view.js").read_text(encoding="utf-8")

    assert "if (!savedMode || savedMode === SIMPLE_MODE)" in script
    assert "fable_simple_default_v1" in script
    assert "if (!localStorage.getItem(SIMPLE_DEFAULT_KEY))" in script
    assert "getElementById('simple-conditions')" in script
    assert "openSelectedMap()" in script
    assert "window.panToFile?.(slug)" in script
    assert "setMode('family', false)" in script


def test_simple_view_three_day_action_and_safe_activities_are_rendered():
    script = (ROOT / "public" / "simple-view.js").read_text(encoding="utf-8")

    assert 'id="simple-three-days"' in script
    assert "getElementById('simple-three-days')" in script
    assert "renderActivities(best)" in script
    assert "String(record.category || 'family').toLowerCase() === 'family'" in script
    assert "record.start === best.windowItem.start" in script
    assert "Aucune activité compatible dans une fenêtre Famille validée." in script


def test_simple_view_uses_unified_selected_day_verdicts_without_cross_day_fallback():
    script = (ROOT / "public" / "simple-view.js").read_text(encoding="utf-8")
    verdicts = (ROOT / "public" / "js" / "navigation-verdicts.js").read_text(encoding="utf-8")

    assert "navigationVerdictForDay" in script
    assert "OFF_HOURS" in script
    assert "TRAVEL_ONLY" in script
    assert "Fenêtre hors horaires disponible" in script
    assert "preferred[0] || rows[0]" not in script
    assert "selectedDay:dayKey(offset)" in script
    assert "getNavigationWindowsForDay" in verdicts
    assert "['family', 'off_hours']" in verdicts
