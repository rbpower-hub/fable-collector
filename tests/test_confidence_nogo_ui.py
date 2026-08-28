from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read_public(name: str) -> str:
    return (ROOT / "public" / name).read_text(encoding="utf-8")


def test_forecast_quality_uses_bars_without_dot_scores():
    simple = read_public("simple-view.js")
    hero = read_public("verdict-hero.js")
    family = read_public("family-content-gate.js")
    expert = read_public("index.html")

    for source in (simple, hero, family, expert):
        assert "quality-bars" in source
        assert "●●●" not in source
        assert "●●○" not in source
        assert "●○○" not in source

    assert "simple-confidence-ring" not in simple
    assert "const confScore" not in expert
    assert "confScore!=null" not in expert
    assert "Qualité des prévisions" in simple
    assert "Qualité des prévisions" in hero
    assert "Qualité des prévisions" in family
    assert "Qualité des prévisions :" in expert


def test_no_go_reasons_have_text_statuses_and_keep_engine_reason():
    simple = read_public("simple-view.js")
    expert = read_public("index.html")

    assert "diagnostics.first_blocker" in simple
    assert "Pourquoi NO-GO" in simple
    assert 'class="simple-reason-status"' in simple
    assert "Cause principale" in simple

    assert 'id="reasons-title">Pourquoi NO-GO' in expert
    assert 'class="reason-status"' in expert
    assert "reason_blocking" in expert
    assert "reason_watch" in expert
    assert "r.composite.summary" in expert
    assert "const familyRaw = String(r.family||'').trim()" in expert


def test_expert_reason_keeps_slashes_inside_units():
    expert = read_public("index.html")

    assert "split(/;|·|\\||\\/|—|--|, /)" not in expert
    assert "|\\s+\\/\\s+/" in expert
    assert "preserves units such as km/h" in expert


def test_arabic_quality_translation_preserves_bar_markup():
    locale = read_public("arabic-locale.js")

    assert "جودة التوقعات" in locale
    assert "dataset.qualityLevel" in locale
    assert "querySelector('.quality-label')" in locale
    assert "setText(reliability, AR.reliability" not in locale
