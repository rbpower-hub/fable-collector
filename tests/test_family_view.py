from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_family_view_keeps_expert_board_and_adds_four_tabs():
    script = (ROOT / "public" / "family-view.js").read_text(encoding="utf-8")

    assert "family-board-mode" in script
    assert "expert-board-mode" in script
    for tab in ("today", "activities", "map", "details"):
        assert tab in script

    assert ".card.radar" in script
    assert "raw-links-list" not in script  # existing expert data remains owned by index.html


def test_family_view_defaults_to_family_and_preserves_user_choice():
    script = (ROOT / "public" / "family-view.js").read_text(encoding="utf-8")

    assert "fable_board_mode" in script
    assert "localStorage.getItem(MODE_KEY) || 'family'" in script
    assert "fable_family_tab" in script
    assert "localStorage.getItem(TAB_KEY) || 'today'" in script


def test_family_view_summary_uses_backend_decisions():
    script = (ROOT / "public" / "family-view.js").read_text(encoding="utf-8")

    assert "fetch('windows.json'" in script
    assert "diagnostics.first_blocker" in script
    assert "tripMode === 'one_way_multi_day'" in script
    assert "recommendations.json" in script
