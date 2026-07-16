from pathlib import Path

from fable.dashboard_patch import patch_dashboard_index

ROOT = Path(__file__).resolve().parents[1]


def test_arabic_locale_scripts_are_injected_once(tmp_path):
    source = ROOT / "public" / "index.html"
    target = tmp_path / "index.html"
    target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")

    assert patch_dashboard_index(target) is True
    html = target.read_text(encoding="utf-8")
    assert html.count('<script src="./locale-transition.js"></script>') == 1
    assert html.count('<script src="./arabic-locale.js"></script>') == 1

    assert patch_dashboard_index(target) is False
    stable = target.read_text(encoding="utf-8")
    assert stable.count('<script src="./arabic-locale.js"></script>') == 1


def test_persisted_arabic_locale_survives_native_dashboard_startup(tmp_path):
    source = ROOT / "public" / "index.html"
    target = tmp_path / "index.html"
    target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")

    assert patch_dashboard_index(target) is True
    app = (tmp_path / "js" / "app.js").read_text(encoding="utf-8")

    assert "const languages = ['fr','en','ar'];" in app
    assert "if(!languages.includes(LANG)) LANG='fr';" in app
    assert "document.documentElement.dir  = l === 'ar' ? 'rtl' : 'ltr';" in app
    assert "const languages = ['fr','en'];" not in app


def test_arabic_locale_adds_rtl_and_tunisia_aware_family_copy():
    script = (ROOT / "public" / "arabic-locale.js").read_text(encoding="utf-8")

    assert "button.dataset.lang = 'ar'" in script
    assert "document.documentElement.dir = selected === 'ar' ? 'rtl' : 'ltr'" in script
    assert "toLocaleString('ar-TN'" in script
    assert "timeZone: TUNIS_TZ" in script
    assert "يمكن القيام بخروج عائلي اليوم" in script
    assert "بيانات الأمواج غير متاحة" in script
    assert "موثوقية محدودة" in script
    assert "validateDictionary" in script
    assert "console.warn(`[FABLE i18n] missing ar key" in script


def test_leaving_arabic_restores_native_fr_en_renderer():
    script = (ROOT / "public" / "locale-transition.js").read_text(encoding="utf-8")

    assert "localStorage.getItem('lang') === 'ar'" in script
    assert "['fr', 'en'].includes" in script
    assert "window.location.reload()" in script
