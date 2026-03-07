from __future__ import annotations

from argparse import Namespace
from pathlib import Path

from domain.records import ExpenseRecord, IncomeRecord, MandatoryExpenseRecord
from domain.transfers import Transfer
from domain.wallets import Wallet
from infrastructure.repositories import JsonFileRecordRepository
from migrate_json_to_sqlite import run_dry_run, run_migration
from storage.sqlite_storage import SQLiteStorage


def _build_json_fixture(json_path: str) -> None:
    repo = JsonFileRecordRepository(json_path)
    wallets = [
        Wallet(id=1, name="Main wallet", currency="KZT", initial_balance=1000.0, system=True),
        Wallet(id=2, name="Card", currency="KZT", initial_balance=500.0),
    ]
    transfer = Transfer(
        id=1,
        from_wallet_id=1,
        to_wallet_id=2,
        date="2026-02-01",
        amount_original=100.0,
        currency="KZT",
        rate_at_operation=1.0,
        amount_kzt=100.0,
        description="move",
    )
    records = [
        ExpenseRecord(
            id=1,
            date="2026-02-01",
            wallet_id=1,
            transfer_id=1,
            amount_original=100.0,
            currency="KZT",
            rate_at_operation=1.0,
            amount_kzt=100.0,
            category="Transfer",
        ),
        IncomeRecord(
            id=2,
            date="2026-02-01",
            wallet_id=2,
            transfer_id=1,
            amount_original=100.0,
            currency="KZT",
            rate_at_operation=1.0,
            amount_kzt=100.0,
            category="Transfer",
        ),
    ]
    mandatory_expenses = [
        MandatoryExpenseRecord(
            id=1,
            date="",
            wallet_id=1,
            amount_original=50.0,
            currency="KZT",
            rate_at_operation=1.0,
            amount_kzt=50.0,
            category="Mandatory",
            description="Rent",
            period="monthly",
        )
    ]
    repo.replace_all_data(
        initial_balance=0.0,
        wallets=wallets,
        records=records,
        mandatory_expenses=mandatory_expenses,
        transfers=[transfer],
    )


def test_dry_run_does_not_insert(tmp_path) -> None:
    json_path = tmp_path / "data.json"
    sqlite_path = tmp_path / "records.db"
    schema_path = Path(__file__).resolve().parents[1] / "db" / "schema.sql"
    _build_json_fixture(str(json_path))

    args = Namespace(
        json_path=str(json_path),
        sqlite_path=str(sqlite_path),
        schema_path=str(schema_path),
        dry_run=True,
    )

    code = run_dry_run(args)
    assert code == 0

    sqlite_storage = SQLiteStorage(str(sqlite_path))
    sqlite_storage.initialize_schema(str(schema_path))
    assert sqlite_storage.query_one("SELECT COUNT(*) FROM wallets")[0] == 0
    assert sqlite_storage.query_one("SELECT COUNT(*) FROM transfers")[0] == 0
    assert sqlite_storage.query_one("SELECT COUNT(*) FROM records")[0] == 0
    assert sqlite_storage.query_one("SELECT COUNT(*) FROM mandatory_expenses")[0] == 0
    sqlite_storage.close()


def test_migration_moves_all_data_and_preserves_ids(tmp_path) -> None:
    json_path = tmp_path / "data.json"
    sqlite_path = tmp_path / "records.db"
    schema_path = Path(__file__).resolve().parents[1] / "db" / "schema.sql"
    _build_json_fixture(str(json_path))

    args = Namespace(
        json_path=str(json_path),
        sqlite_path=str(sqlite_path),
        schema_path=str(schema_path),
        dry_run=False,
    )

    code = run_migration(args)
    assert code == 0

    sqlite_storage = SQLiteStorage(str(sqlite_path))
    sqlite_storage.initialize_schema(str(schema_path))
    assert sqlite_storage.query_one("SELECT COUNT(*) FROM wallets")[0] == 2
    assert sqlite_storage.query_one("SELECT COUNT(*) FROM transfers")[0] == 1
    assert sqlite_storage.query_one("SELECT COUNT(*) FROM records")[0] == 2
    assert sqlite_storage.query_one("SELECT COUNT(*) FROM mandatory_expenses")[0] == 1

    wallet_ids = [row[0] for row in sqlite_storage.query_all("SELECT id FROM wallets ORDER BY id")]
    transfer_ids = [
        row[0] for row in sqlite_storage.query_all("SELECT id FROM transfers ORDER BY id")
    ]
    record_ids = [row[0] for row in sqlite_storage.query_all("SELECT id FROM records ORDER BY id")]
    mandatory_ids = [
        row[0] for row in sqlite_storage.query_all("SELECT id FROM mandatory_expenses ORDER BY id")
    ]

    assert wallet_ids == [1, 2]
    assert transfer_ids == [1]
    assert record_ids == [1, 2]
    assert mandatory_ids == [1]
    sqlite_storage.close()


def test_migration_is_safe_to_rerun_on_equivalent_dataset(tmp_path) -> None:
    json_path = tmp_path / "records.json"
    sqlite_path = tmp_path / "records.db"
    schema_path = Path(__file__).resolve().parents[1] / "db" / "schema.sql"
    _build_json_fixture(str(json_path))

    args = Namespace(
        json_path=str(json_path),
        sqlite_path=str(sqlite_path),
        schema_path=str(schema_path),
        dry_run=False,
    )

    first_code = run_migration(args)
    second_code = run_migration(args)

    assert first_code == 0
    assert second_code == 0

    sqlite_storage = SQLiteStorage(str(sqlite_path))
    sqlite_storage.initialize_schema(str(schema_path))
    assert sqlite_storage.query_one("SELECT COUNT(*) FROM wallets")[0] == 2
    assert sqlite_storage.query_one("SELECT COUNT(*) FROM transfers")[0] == 1
    assert sqlite_storage.query_one("SELECT COUNT(*) FROM records")[0] == 2
    assert sqlite_storage.query_one("SELECT COUNT(*) FROM mandatory_expenses")[0] == 1
    sqlite_storage.close()
