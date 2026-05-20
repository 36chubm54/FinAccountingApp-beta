from __future__ import annotations

from gui.i18n import parse_language_file


def test_report_export_warning_key_exists_in_ru_and_en_locales() -> None:
    ru_catalog = parse_language_file("locales/ru.txt")
    en_catalog = parse_language_file("locales/en.txt")

    assert "reports.export.warning" in ru_catalog
    assert "reports.export.warning" in en_catalog
    assert ru_catalog["reports.export.warning"]
    assert en_catalog["reports.export.warning"]
