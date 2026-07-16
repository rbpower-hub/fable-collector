from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_stale_and_missing_badges_use_darkened_alert_background():
    hero = (ROOT / "public" / "verdict-hero.js").read_text(encoding="utf-8")

    assert "background:color-mix(in srgb,var(--bad) 72%,#000);color:#fff" in hero
