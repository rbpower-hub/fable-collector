from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_window_annotation_badges_only_mutate_when_text_changes():
    script = (ROOT / "public" / "reasons-debug.js").read_text(encoding="utf-8")

    assert "function setBadgeText(badge, value)" in script
    assert "badge.textContent !== value" in script
    assert "setBadgeText(badge, `OFFSHORE ${direction}`)" in script
    assert 'setBadgeText(badge, "FAMILY GO PRUDENT")' in script
    assert "if (badge) badge.textContent = `OFFSHORE ${direction}`" not in script
    assert 'if (badge) badge.textContent = "FAMILY GO PRUDENT"' not in script
