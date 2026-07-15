from pathlib import Path

from fable.dashboard_patch import patch_dashboard_index

ROOT = Path(__file__).resolve().parents[1]


def test_family_reasons_layer_is_injected_once(tmp_path):
    source = ROOT / "public" / "index.html"
    target = tmp_path / "index.html"
    target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")

    assert patch_dashboard_index(target) is True
    html = target.read_text(encoding="utf-8")
    assert html.count('<script src="./family-reasons.js"></script>') == 1

    assert patch_dashboard_index(target) is False
    assert target.read_text(encoding="utf-8").count('<script src="./family-reasons.js"></script>') == 1


def test_family_reasons_preserve_raw_diagnostics_for_expert_view():
    layer = (ROOT / "public" / "family-reasons.js").read_text(encoding="utf-8")
    translations = (ROOT / "public" / "js" / "reasons-i18n.js").read_text(encoding="utf-8")

    assert "original.classList.add('expert-only')" in layer
    assert "friendly-reason family-only" in layer
    assert "line.dataset.rawReason = raw" in layer
    assert "line.title = raw" in layer
    assert "unknown" not in translations.lower() or "phrase = cleaned" in translations
    assert "Orages prévus — sortie impossible" in translations
    assert "Vagues courtes et inconfortables" in translations
    assert "No long-enough daytime slot" in translations
