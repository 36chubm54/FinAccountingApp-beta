from __future__ import annotations

from pathlib import Path

from backup import create_backup, export_to_json
from domain.records import IncomeRecord, MandatoryExpenseRecord
from domain.wallets import Wallet
from infrastructure.repositories import JsonFileRecordRepository
from infrastructure.sqlite_repository import SQLiteRecordRepository


def _schema_path() -> str:
    return str(Path(__file__).resolve().parents[1] / "db" / "schema.sql")


def test_create_backup_creates_timestamped_copy(tmp_path) -> None:
    src = tmp_path / "data.json"
    src.write_text('{"records": []}', encoding="utf-8")

    backup_path = create_backup(str(src))
    assert backup_path is not None
    backup = Path(backup_path)
    assert backup.exists()
    assert backup.name.startswith("data_backup_")
    assert backup.suffix == ".json"


def test_export_to_json_from_sqlite(tmp_path) -> None:
    sqlite_path = tmp_path / "finance.db"
    json_path = tmp_path / "data.json"
    schema = _schema_path()

    repo = SQLiteRecordRepository(str(sqlite_path), schema_path=schema)
    repo.save_wallet(
        Wallet(
            id=1,
            name="Main wallet",
            currency="KZT",
            initial_balance=1000.0,
            system=True,
            allow_negative=False,
            is_active=True,
        )
    )
    repo.save(
        IncomeRecord(
            id=1,
            date="2026-02-28",
            wallet_id=1,
            amount_original=100.0,
            currency="KZT",
            rate_at_operation=1.0,
            amount_kzt=100.0,
            category="Salary",
        )
    )
    repo.save_mandatory_expense(
        MandatoryExpenseRecord(
            id=1,
            wallet_id=1,
            date="2026-03-12",
            amount_original=25.0,
            currency="KZT",
            rate_at_operation=1.0,
            amount_kzt=25.0,
            category="Mandatory",
            description="Gym",
            period="monthly",
            auto_pay=True,
        )
    )
    repo.close()

    export_to_json(str(sqlite_path), str(json_path), schema_path=schema)

    repo = JsonFileRecordRepository(str(json_path))
    wallets = repo.load_wallets()
    records = repo.load_all()
    mandatory = repo.load_mandatory_expenses()
    assert len(wallets) == 1
    assert len(records) == 1
    assert len(mandatory) == 1
    assert wallets[0].id == 1
    assert records[0].id == 1
    assert str(mandatory[0].date) == "2026-03-12"
    assert mandatory[0].auto_pay is True


def test_prune_backups(tmp_path):
    """Test that _prune_backups keeps only the most recent files."""

    from backup import _prune_backups

    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()
    source_stem = "data"
    source_suffix = ".json"

    # Create 4 backup files with timestamps (oldest to newest)
    timestamps = [
        "20250101_120000",  # oldest
        "20250102_120000",
        "20250103_120000",
        "20250104_120000",  # newest
    ]
    for ts in timestamps:
        path = backup_dir / f"{source_stem}_backup_{ts}{source_suffix}"
        path.write_text('{"test": 1}')

    # Also create a stray file that doesn't match the pattern
    stray = backup_dir / "other_backup_20250101_120000.json"
    stray.write_text("{}")

    # Keep last 2
    _prune_backups(backup_dir, source_stem=source_stem, source_suffix=source_suffix, keep_last=2)

    remaining = list(backup_dir.glob(f"{source_stem}_backup_*{source_suffix}"))
    assert len(remaining) == 2
    # Should keep the two newest timestamps
    remaining_names = [p.name for p in remaining]
    assert "data_backup_20250103_120000.json" in remaining_names
    assert "data_backup_20250104_120000.json" in remaining_names
    # Stray file should remain untouched
    assert stray.exists()
