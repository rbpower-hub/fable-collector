import json
import xml.etree.ElementTree as ET
from pathlib import Path

from fable.dashboard_patch import patch_dashboard_index

ROOT = Path(__file__).resolve().parents[1]


def test_manifest_is_installable_and_has_required_icons():
    manifest = json.loads((ROOT / "public" / "manifest.webmanifest").read_text(encoding="utf-8"))

    assert manifest["name"].startswith("FABLE")
    assert manifest["short_name"] == "FABLE"
    assert manifest["display"] == "standalone"
    assert manifest["start_url"] == "./"
    sizes = {icon["sizes"] for icon in manifest["icons"]}
    assert {"192x192", "512x512"}.issubset(sizes)
    assert all("maskable" in icon["purpose"] for icon in manifest["icons"])


def test_original_compass_wave_icons_are_valid_svg():
    for filename, size in (("fable-192.svg", "192"), ("fable-512.svg", "512")):
        path = ROOT / "public" / "icons" / filename
        root = ET.fromstring(path.read_text(encoding="utf-8"))
        assert root.tag.endswith("svg")
        assert root.attrib["width"] == size
        assert root.attrib["height"] == size
        assert root.find("{http://www.w3.org/2000/svg}circle") is not None
        assert len(root.findall("{http://www.w3.org/2000/svg}path")) >= 3


def test_dashboard_publishes_manifest_and_defaults_new_users_to_nautical(tmp_path):
    source = ROOT / "public" / "index.html"
    target = tmp_path / "index.html"
    target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")

    assert patch_dashboard_index(target) is True
    html = target.read_text(encoding="utf-8")
    app = (tmp_path / "js" / "app.js").read_text(encoding="utf-8")

    assert '<html lang="fr" data-theme="nautical">' in html
    assert '<link rel="manifest" href="./manifest.webmanifest" />' in html
    assert '<link rel="apple-touch-icon" href="./icons/fable-192.svg" />' in html
    assert html.count('<script src="./pwa-install.js"></script>') == 1
    assert "if(!themes.includes(theme)) theme='nautical';" in app

    assert patch_dashboard_index(target) is False


def test_theme_color_tracks_active_theme():
    script = (ROOT / "public" / "pwa-install.js").read_text(encoding="utf-8")

    assert "dark: '#0b1020'" in script
    assert "nautical: '#0077b6'" in script
    assert "attributeFilter: ['data-theme']" in script
    assert "serviceWorker" not in script
