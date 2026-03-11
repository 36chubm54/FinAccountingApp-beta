from __future__ import annotations

from pathlib import Path

import pytest

import bootstrap
from infrastructure.sqlite_repository import SQLiteRecordRepository
from storage.sqlite_storage import SQLiteStorage


def _schema_path() -> str:
    return str(Path(__file__).resolve().parents[1] / "db" / "schema.sql")


def _make_repo(db_path: Path) -> SQLiteRecordRepository:
    return SQLiteRecordRepository(str(db_path), schema_path=_schema_path())


def test_migration_verified_flag_roundtrip(tmp_path) -> None:
    repo = _make_repo(tmp_path / "finance.db")
    try:
        assert bootstrap._is_migration_verified(repo) is False
        bootstrap._mark_migration_verified(repo)
        assert bootstrap._is_migration_verified(repo) is True
    finally:
        repo.close()


def test_validate_sqlite_integrity_only_detects_broken_transfer(tmp_path) -> None:
    repo = _make_repo(tmp_path / "finance.db")
    try:
        repo.execute(
            """
            INSERT INTO wallets (name, currency, initial_balance, system, allow_negative, is_active)
            VALUES ('W1', 'KZT', 0, 1, 0, 1)
            """
        )
        repo.execute(
            """
            INSERT INTO wallets (name, currency, initial_balance, system, allow_negative, is_active)
            VALUES ('W2', 'KZT', 0, 0, 0, 1)
            """
        )
        repo.execute(
            """
            INSERT INTO transfers (
                from_wallet_id, to_wallet_id, date, amount_original, currency,
                rate_at_operation, amount_kzt, description
            )
            VALUES (1, 2, '2026-03-01', 100, 'KZT', 1, 100, '')
            """
        )
        repo.execute(
            """
            INSERT INTO records (
                type, date, wallet_id, transfer_id, amount_original, currency,
                rate_at_operation, amount_kzt, category, description, period
            )
            VALUES ('expense', '2026-03-01', 1, 1, 100, 'KZT', 1, 100, 'Transfer', '', NULL)
            """
        )
        repo.commit()

        with pytest.raises(RuntimeError, match="expected 2"):
            bootstrap._validate_sqlite_integrity_only(repo)
    finally:
        repo.close()


def test_bootstrap_marks_existing_sqlite_as_verified_without_json_compare(
    tmp_path, monkeypatch
) -> None:
    sqlite_path = tmp_path / "finance.db"
    storage = SQLiteStorage(str(sqlite_path))
    try:
        storage.initialize_schema(_schema_path())
        storage.execute(
            """
            INSERT INTO wallets (name, currency, initial_balance, system, allow_negative, is_active)
            VALUES ('Main wallet', 'KZT', 0, 1, 0, 1)
            """
        )
        storage.commit()
    finally:
        storage.close()

    monkeypatch.setattr(bootstrap, "SQLITE_PATH", str(sqlite_path))

    repository = bootstrap.bootstrap_repository()

    if isinstance(repository, SQLiteRecordRepository):
        try:
            row = repository.query_one(
                "SELECT value FROM schema_meta WHERE key='migration_verified'"
            )
            assert row is not None
            assert str(row[0]).lower() == "true"
        finally:
            repository.close()


def test_bootstrap_creates_sqlite_and_initializes_system_wallet(tmp_path, monkeypatch) -> None:
    sqlite_path = tmp_path / "finance.db"
    monkeypatch.setattr(bootstrap, "SQLITE_PATH", str(sqlite_path))

    repository = bootstrap.bootstrap_repository()

    if isinstance(repository, SQLiteRecordRepository):
        try:
            assert sqlite_path.exists()
            wallets = repository.load_wallets()
            assert len(wallets) == 1
            assert wallets[0].id == 1
            assert wallets[0].system is True
            assert wallets[0].name == "Main wallet"
        finally:
            repository.close()


def test_validate_sqlite_integrity_only_detects_wrong_transfer_types(tmp_path) -> None:
    repo = _make_repo(tmp_path / "finance.db")
    try:
        repo.execute(
            """
            INSERT INTO wallets (name, currency, initial_balance, system, allow_negative, is_active)
            VALUES ('W1', 'KZT', 0, 1, 0, 1)
            """
        )
        repo.execute(
            """
            INSERT INTO wallets (name, currency, initial_balance, system, allow_negative, is_active)
            VALUES ('W2', 'KZT', 0, 0, 0, 1)
            """
        )
        repo.execute(
            """
            INSERT INTO transfers (
                from_wallet_id, to_wallet_id, date, amount_original, currency,
                rate_at_operation, amount_kzt, description
            )
            VALUES (1, 2, '2026-03-01', 100, 'KZT', 1, 100, '')
            """
        )
        repo.execute(
            """
            INSERT INTO records (
                type, date, wallet_id, transfer_id, amount_original, currency,
                rate_at_operation, amount_kzt, category, description, period
            )
            VALUES ('expense', '2026-03-01', 1, 1, 100, 'KZT', 1, 100, 'Transfer', '', NULL)
            """
        )
        repo.execute(
            """
            INSERT INTO records (
                type, date, wallet_id, transfer_id, amount_original, currency,
                rate_at_operation, amount_kzt, category, description, period
            )
            VALUES ('expense', '2026-03-01', 2, 1, 100, 'KZT', 1, 100, 'Transfer', '', NULL)
            """
        )
        repo.commit()

        with pytest.raises(RuntimeError, match="invalid linked types"):
            bootstrap._validate_sqlite_integrity_only(repo)
    finally:
        repo.close()
