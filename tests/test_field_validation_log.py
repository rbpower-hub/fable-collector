from pathlib import Path

from fable.dashboard_patch import patch_dashboard_index

ROOT = Path(__file__).resolve().parents[1]


def test_field_validation_link_is_injected_once(tmp_path):
    source = ROOT / "public" / "index.html"
    target = tmp_path / "index.html"
    target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")

    assert patch_dashboard_index(target) is True
    html = target.read_text(encoding="utf-8")
    tag = '<script src="./field-validation-link.js"></script>'
    assert html.count(tag) == 1

    assert patch_dashboard_index(target) is False
    assert target.read_text(encoding="utf-8").count(tag) == 1


def test_field_journal_is_local_exportable_and_safety_locked():
    page = (ROOT / "public" / "field-log.html").read_text(encoding="utf-8")
    script = (ROOT / "public" / "field-log.js").read_text(encoding="utf-8")

    assert "ne modifie jamais automatiquement les seuils" in page
    assert "ne doit jamais servir à tester une sortie classée NO-GO" in page
    assert "fable_field_logs_v1" in script
    assert "Exporter JSON" in page
    assert "Exporter CSV" in page
    assert "conservative_observation" in script
    assert "false_go" in script
    assert "localStorage.setItem" in script
    assert "windows.json" in script
    assert "status.json" in script


def test_field_journal_link_is_accessible():
    script = (ROOT / "public" / "field-validation-link.js").read_text(encoding="utf-8")

    assert "Journal de sortie et validation terrain" in script
    assert "aria-label" in script
    assert "./field-log.html" in script
