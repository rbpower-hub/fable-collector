from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_dashboard_loads_isolated_simple_view():
    html = (ROOT / "public" / "index.html").read_text(encoding="utf-8")
    script = (ROOT / "public" / "simple-view.js").read_text(encoding="utf-8")

    assert '<script src="./simple-view.js" defer></script>' in html
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


def test_simple_view_has_mobile_navigation_and_three_day_overview():
    script = (ROOT / "public" / "simple-view.js").read_text(encoding="utf-8")

    assert "simple-bottom-nav" in script
    assert "simple-day-track" in script
    assert "[0, 1, 2].map" in script
    assert "@media(max-width:520px)" in script
    assert "env(safe-area-inset-bottom)" in script


def test_simple_view_refreshes_from_published_dashboard_contract():
    script = (ROOT / "public" / "simple-view.js").read_text(encoding="utf-8")

    assert "fetch('windows.json'" in script
    assert "fetch('status.json'" in script
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
    assert "stale_after" in script
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
