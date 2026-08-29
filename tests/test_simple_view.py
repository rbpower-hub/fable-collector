from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_dashboard_loads_isolated_simple_view():
    html = (ROOT / "public" / "index.html").read_text(encoding="utf-8")
    script = (ROOT / "public" / "simple-view.js").read_text(encoding="utf-8")

    assert '<script src="./simple-view.js?v=20260829-selected-port-v1" defer></script>' in html
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


def test_simple_view_separates_forecast_quality_from_the_decision():
    script = (ROOT / "public" / "simple-view.js").read_text(encoding="utf-8")

    assert "Qualité des prévisions" in script
    assert "Forecast quality" in script
    assert "جودة التوقعات" in script
    assert "qualityUnassessed:'Non évaluée'" in script
    assert "function forecastQuality(best)" in script
    assert "return {level:'unassessed', label:c.qualityUnassessed}" in script
    assert 'data-quality-level="${esc(quality.level)}"' in script
    assert 'class="quality-bars" aria-hidden="true"' in script
    assert "simple-confidence-ring" not in script
    assert "confidenceScore" not in script
    assert "confidenceWord" not in script
    assert "${score}%" not in script
    assert "--score" not in script


def test_simple_view_has_mobile_navigation_and_three_day_overview():
    script = (ROOT / "public" / "simple-view.js").read_text(encoding="utf-8")

    assert "simple-bottom-nav" in script
    assert "simple-day-track" in script
    assert "[0, 1, 2].map" in script
    assert "@media(max-width:520px)" in script
    assert "env(safe-area-inset-bottom)" in script
    assert 'id="simple-navigation"' in script
    assert "simple-window-card" in script
    assert 'body.simple-board-mode #family-verdict-hero' in script
    assert 'body.simple-board-mode #family-planning-host' in script


def test_simple_navigation_expands_inline_and_more_menu_has_real_actions():
    script = (ROOT / "public" / "simple-view.js").read_text(encoding="utf-8")

    assert 'data-simple-action="window-details"' in script
    assert 'class="simple-window-details" hidden' in script
    assert 'data-simple-action="map-window"' in script
    assert "if (action === 'window-details')" in script
    assert 'id="simple-more-menu"' in script
    assert 'data-simple-action="conditions"' in script
    assert 'data-simple-action="activities"' in script
    assert 'data-simple-action="family"' in script
    assert "if (action === 'more')" in script


def test_simple_navigation_cards_explain_quality_and_open_the_exact_route():
    html = (ROOT / "public" / "index.html").read_text(encoding="utf-8")
    script = (ROOT / "public" / "simple-view.js").read_text(encoding="utf-8")

    assert 'class="simple-window-quality"' in script
    assert 'class="simple-window-models"' in script
    assert 'class="simple-window-route"' in script
    assert "window.FABLEMapUI?.describeWindowRoute?.({" in script
    assert "window.FABLEMapUI.openWindow({file:slug, start:item.start, end:item.end" in script
    assert "function focusWindow(file, {start='', end='', direction='', scroll=true}={})" in html
    assert "openWindow({file, start='', end='', direction=''}={})" in html
    assert "describe(file){ return describeRoute(file); }" in html
    assert "describeWindow(options){ return describeWindow(options); }" in html
    assert "describeWindowRoute(options){ return describeWindowRoute(options); }" in html
    assert 'class="simple-window-route-meta"' in script
    assert 'data-simple-route-winds="${index}"' in script


def test_simple_forecast_keeps_loading_when_a_day_has_no_validated_window():
    script = (ROOT / "public" / "simple-view.js").read_text(encoding="utf-8")

    assert "state.windows?.home_slug || destinations[0]?.dest_slug" in script


def test_simple_view_keeps_in_progress_windows_visible_without_promoting_them_to_go():
    script = (ROOT / "public" / "simple-view.js").read_text(encoding="utf-8")
    verdicts = (ROOT / "public" / "js" / "navigation-verdicts.js").read_text(encoding="utf-8")

    assert "late_rows" in verdicts
    assert "isInProgressButTooShort" in verdicts
    assert "En cours" in script
    assert "Temps restant" in script
    assert "La durée familiale complète n’est plus réalisable" in script
    assert "displayRows(result)" in script
    assert 'class="simple-window-status"' in script
    assert ".simple-window-badge.in-progress" in script


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


def test_simple_view_keeps_hourly_explorer_out_of_the_core_presentation():
    script = (ROOT / "public" / "simple-view.js").read_text(encoding="utf-8")
    chart = (ROOT / "public" / "js" / "hourly-chart.js").read_text(encoding="utf-8")

    assert "import('./js/hourly-chart.js')" not in script
    assert "renderHourlyExplorer" not in script
    assert "hourlyAssessment" not in script
    assert "renderTimeline(result?.rows || [], result?.counts || {})" in script
    assert "renderConditions(contextRow)" in script
    # Le composant expérimental reste disponible hors de la Vue Simple et les
    # contrats moteur hourly/*.json continuent d'être testés séparément.
    assert 'data-hourly-destination' in chart
    assert 'data-hourly-mode="curves"' in chart
    assert 'data-hourly-mode="table"' in chart
    assert 'data-hourly-range="72h"' in chart
    assert "display_speed_kmh" in chart
    assert "display_gust_kmh" in chart
    assert "display_hs_m" in chart
    assert "hourly-ribbon" in chart
    assert "hourly-prudent" in chart
    assert "hourly-watch" in chart
    assert "hourly-no_go" in chart
    assert "Une heure favorable ne valide pas une sortie complète." in chart


def test_simple_view_weather_context_and_mobile_hierarchy():
    script = (ROOT / "public" / "simple-view.js").read_text(encoding="utf-8")

    assert "simple-overline" not in script
    assert "temperature_2m" in script
    assert "apparent_temperature" in script
    assert "relative_humidity_2m" in script
    assert "cloud_cover" in script
    assert "uv_index" in script
    assert "simple-weather-grid" in script
    assert "function weatherIcon(kind)" in script
    assert 'data-weather-kind="${kind}"' in script
    assert '.simple-weather-icon svg{display:block;width:25px;height:25px}' in script
    assert "item('temperature'" in script
    assert "item('uv'" in script
    assert "item('sky'" in script
    assert "item('rain'" in script
    assert "@media(max-width:640px){.simple-hero-grid{grid-template-columns:1fr" in script
    assert ".simple-confidence{display:none}" not in script
    assert '[data-theme="nautical"] .simple-action.primary{color:#fff}' in script
    assert "outbound:'Aller', return:'Retour', departure:'Départ', arrival:'Arrivée', beta:'Bêta'" in script
    assert "value !== null && value !== undefined" in script


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
    assert "window.FABLEMapUI?.open?.(slug)" in script
    assert "simple-map-open" in script
    assert "setMode('family', false)" in script


def test_simple_view_three_day_action_and_safe_activities_are_rendered():
    script = (ROOT / "public" / "simple-view.js").read_text(encoding="utf-8")

    assert 'id="simple-three-days"' in script
    assert "getElementById('simple-three-days')" in script
    assert "renderActivities(best)" in script
    # La section filtrait sur la categorie `family`. Or `family` et `off_hours`
    # sortent des memes seuils meteo : window_detect ne les distingue que par la
    # lumiere du jour. Le filtre par categorie etait donc un proxy, et il cachait
    # les activites d'une journee dont les seules fenetres sont hors horaires.
    # Le vrai garde-fou est cote moteur, par activite : voir `requires_daylight`.
    assert "String(record.category || 'family').toLowerCase() === 'family'" not in script
    # Ce qui reste indispensable : l'activite appartient bien a la fenetre
    # validee affichee, meme destination, memes bornes.
    assert "record.dest_slug === best.destination.dest_slug" in script
    assert "record.start === best.windowItem.start" in script
    assert "record.end === best.windowItem.end" in script
    assert "Aucune activité compatible dans une fenêtre Famille validée." in script


def test_daylight_gate_lives_in_the_engine_not_in_the_view():
    """La vue n'est pas le bon endroit pour une regle de securite.

    `family` et `off_hours` partagent les memes seuils meteo ; seule la lumiere
    les separe. C'est donc a l'activite de declarer si elle a besoin du jour.
    """
    source = (ROOT / "fable" / "recommendations.py").read_text(encoding="utf-8")
    assert "requires_daylight" in source
    assert "min_daylight_share" in source

    activities = ROOT / "knowledge" / "activities"
    needing_light = {"family-swim", "snorkeling", "paddle-kayak", "nature-watch"}
    for name in needing_light:
        text = (activities / f"{name}.yaml").read_text(encoding="utf-8")
        assert "requires_daylight: true" in text, name
    # La peche au lever du jour reste legitime : elle ne declare pas la contrainte.
    for name in ("bottom-fishing", "light-jigging", "coastal-trolling", "soft-lure-fishing"):
        text = (activities / f"{name}.yaml").read_text(encoding="utf-8")
        assert "requires_daylight" not in text, name


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
    assert "['family', 'off_hours', 'watch']" in verdicts
    assert "watch_windows" in verdicts or "watch_windows" in (
        ROOT / "public" / "js" / "navigation-windows.js"
    ).read_text(encoding="utf-8")


def test_simple_view_counts_options_with_the_category_breakdown():
    """L'en-tête annonçait 7 options là où la carte du jour annonçait 2.

    `navigationWindowCounts` fait `family = total - longTrip` : il suppose une
    liste déjà filtrée sur la catégorie famille. La liste passée ici contient
    aussi les créneaux hors horaires et watch.
    """
    script = (ROOT / "public" / "simple-view.js").read_text(encoding="utf-8")

    assert "navigationWindowBreakdown?.(rows)" in script
    assert "navigationWindowCounts?.(rows)" not in script


def test_simple_view_orders_navigation_rows_by_usefulness():
    """La liste est coupée à cinq lignes.

    En ordre chronologique, une journée portant cinq créneaux hors horaires à
    05:00 puis deux fenêtres FAMILY GO à 11:00 n'affichait aucune fenêtre
    familiale : elles étaient poussées hors de la coupe.
    """
    script = (ROOT / "public" / "simple-view.js").read_text(encoding="utf-8")

    assert "function rowRank(" in script
    assert "ROW_RANK = {family: 0, prudent: 1, off_hours: 2, watch: 3}" in script
    # L'ordre d'utilité s'applique avant l'ordre horaire.
    assert "rowRank(a) - rowRank(b)" in script
    assert "rows.slice(0, 5)" in script


def test_simple_view_names_the_port_of_each_activity():
    """La section ne disait pas à quel port l'activité se rapportait."""
    script = (ROOT / "public" / "simple-view.js").read_text(encoding="utf-8")

    # Le lien activité -> recommandation est conservé jusqu'au rendu.
    assert "(item) => ({item, record})" in script
    assert "const port = record.dest_name || record.dest_slug" in script
    assert "📍 ${esc(port)}" in script
