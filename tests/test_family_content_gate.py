from pathlib import Path

from fable.dashboard_patch import patch_dashboard_index

ROOT = Path(__file__).resolve().parents[1]


def test_family_content_gate_is_injected_once(tmp_path):
    source = ROOT / "public" / "index.html"
    target = tmp_path / "index.html"
    target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")

    assert patch_dashboard_index(target) is True
    html = target.read_text(encoding="utf-8")
    assert html.count('<script src="./family-content-gate.js"></script>') == 1

    assert patch_dashboard_index(target) is False
    assert target.read_text(encoding="utf-8").count('<script src="./family-content-gate.js"></script>') == 1


def test_family_mode_hides_technical_and_long_trip_content():
    script = (ROOT / "public" / "family-content-gate.js").read_text(encoding="utf-8")

    assert "body.family-board-mode .expert-only" in script
    assert "body.expert-board-mode .family-only" in script
    assert "kind.includes('one_way')" in script
    assert "kind.includes('offshore')" in script
    assert "Boolean(site.beta)" in script
    assert "closest('details')?.classList.add('expert-only')" in script
    assert "technicalSmall(node)" in script


def test_family_mode_replaces_jargon_with_reliability_and_safe_warnings():
    script = (ROOT / "public" / "family-content-gate.js").read_text(encoding="utf-8")

    assert "fiabilité très bonne" in script
    assert "fiabilité bonne" in script
    assert "à reconfirmer avant de partir" in script
    assert "modèles météo d’accord" in script
    assert "Données de vagues indisponibles — fenêtres non confirmées" in script
    assert "warning.title = String(marineError)" in script
    assert "family-long-trips" in script
