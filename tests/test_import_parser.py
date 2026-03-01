from pathlib import Path

import pytest

from services import import_parser


def test_parse_import_file_rejects_large_file(monkeypatch, tmp_path: Path) -> None:
    csv_path = tmp_path / "big.csv"
    csv_path.write_text("date,type\n2026-01-01,income\n", encoding="utf-8")
    monkeypatch.setattr(import_parser, "MAX_IMPORT_FILE_SIZE", 8)

    with pytest.raises(ValueError, match="too large"):
        import_parser.parse_import_file(str(csv_path))


def test_parse_import_file_rejects_csv_row_limit(monkeypatch, tmp_path: Path) -> None:
    csv_path = tmp_path / "rows.csv"
    csv_path.write_text(
        "date,type,wallet_id,category,amount_original,currency,rate_at_operation,amount_kzt\n"
        "2026-01-01,income,1,Salary,10,USD,500,5000\n"
        "2026-01-02,income,1,Salary,10,USD,500,5000\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(import_parser, "MAX_IMPORT_ROWS", 1)

    with pytest.raises(ValueError, match="row limit"):
        import_parser.parse_import_file(str(csv_path))
