from __future__ import annotations

from pathlib import Path

import pytest

from gui.i18n import get_language, parse_language_file, set_language, tr


def test_parse_language_file_ignores_comments_and_blank_lines(tmp_path: Path) -> None:
    path = tmp_path / "sample.txt"
    path.write_text(
        "\n# comment\napp.title=Финансовый учет\n\ncommon.refresh=Обновить\n",
        encoding="utf-8",
    )

    data = parse_language_file(path)

    assert data == {
        "app.title": "Финансовый учет",
        "common.refresh": "Обновить",
    }


def test_parse_language_file_raises_on_duplicate_key(tmp_path: Path) -> None:
    path = tmp_path / "duplicate.txt"
    path.write_text("app.title=One\napp.title=Two\n", encoding="utf-8")

    with pytest.raises(ValueError, match="Duplicate locale key"):
        parse_language_file(path)


def test_set_language_and_translate_known_keys() -> None:
    set_language("ru")
    assert get_language() == "ru"
    assert tr("app.title") == "Финансовый учет"

    set_language("en")
    assert get_language() == "en"
    assert tr("app.title") == "Financial Accounting"

    set_language("ru")


def test_translate_falls_back_to_default_language_and_default_value() -> None:
    set_language("en")

    assert tr("budget.create") == "Create budget"
    assert tr("missing.key", default="fallback") == "fallback"

    set_language("ru")


def test_parse_language_file_unescapes_special_sequences(tmp_path: Path) -> None:
    path = tmp_path / "escape.txt"
    path.write_text(
        "key1=line1\\nline2\nkey2=tab\\tseparated\n",
        encoding="utf-8",
    )

    data = parse_language_file(path)

    assert data["key1"] == "line1\nline2"
    assert data["key2"] == "tab\tseparated"
