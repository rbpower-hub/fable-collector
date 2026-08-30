from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_dashboard_loads_shared_navigation_context_before_views():
    html = (ROOT / "public" / "index.html").read_text(encoding="utf-8")

    context_tag = '<script src="./navigation-context.js?v=20260830-context-v1"></script>'
    simple_tag = '<script src="./simple-view.js?v=20260830-context-v1" defer></script>'
    assert context_tag in html
    assert simple_tag in html
    assert html.index(context_tag) < html.index(simple_tag)


def test_three_views_delegate_selection_to_the_same_context():
    simple = (ROOT / "public" / "simple-view.js").read_text(encoding="utf-8")
    family = (ROOT / "public" / "family-view.js").read_text(encoding="utf-8")
    expert = (ROOT / "public" / "index.html").read_text(encoding="utf-8")
    activities = (ROOT / "public" / "activity-board.js").read_text(encoding="utf-8")

    assert "FABLENavigationContext?.selectWindow" in simple
    assert "FABLENavigationContext?.selectWindow" in family
    assert "FABLENavigationContext?.selectWindow" in expert
    assert "FABLENavigationContext?.setPort" in activities
    assert "fable:navigation-context-changed" in simple
    assert "fable:navigation-context-changed" in family
    assert "fable:navigation-context-changed" in activities


def test_refresh_revalidates_selection_and_restores_exact_corridor():
    expert = (ROOT / "public" / "index.html").read_text(encoding="utf-8")
    context = (ROOT / "public" / "navigation-context.js").read_text(encoding="utf-8")

    assert "FABLENavigationContext?.reconcile?.(winData" in expert
    assert "start:selectedWindow.start" in expert
    assert "end:selectedWindow.end" in expert
    assert "direction:selectedWindow.direction || ''" in expert
    assert "windowRecordIndex.get(`${slug}|${start}|${end}|${direction}`)" in expert
    assert "Sans windows.json exploitable" in context
    assert "fable_navigation_window_v1" in context
    assert "const WINDOW_STORAGE_KEY = 'fable_selected_window'" not in context
