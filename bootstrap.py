from __future__ import annotations

import math
from argparse import Namespace
from pathlib import Path
from typing import TYPE_CHECKING

from backup import create_backup, export_to_json
from config import JSON_PATH, SQLITE_PATH, USE_SQLITE
from infrastructure.repositories import JsonFileRecordRepository, RecordRepository
from migrate_json_to_sqlite import run_migration
from storage.json_storage import JsonStorage

if TYPE_CHECKING:
    from infrastructure.sqlite_repository import SQLiteRecordRepository

EPSILON = 0.00001


def _resolve_schema_path(schema_path: str) -> str:
    candidate = Path(schema_path)
    if candidate.is_absolute():
        return str(candidate)
    return str((Path(__file__).resolve().parent / "db" / candidate.name).resolve())


def _sqlite_has_data(sqlite_path: str, schema_path: str | None = None) -> bool:
    from storage.sqlite_storage import SQLiteStorage

    if schema_path is not None:
        schema_path = _resolve_schema_path(schema_path)
    storage = SQLiteStorage(sqlite_path)
    try:
        storage.initialize_schema(schema_path)
        conn = storage._conn
        for table in ("wallets", "records", "transfers", "mandatory_expenses"):
            if int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]) > 0:
                return True
        return False
    finally:
        storage.close()


def _wallet_balances_from_json(repository: RecordRepository) -> dict[int, float]:
    wallets = repository.load_wallets()
    records = repository.load_all()
    balances = {wallet.id: float(wallet.initial_balance) for wallet in wallets}
    for record in records:
        balances[int(record.wallet_id)] = balances.get(int(record.wallet_id), 0.0) + float(
            record.signed_amount_kzt()
        )
    return balances


def _wallet_balances_from_sqlite(sqlite_repo: SQLiteRecordRepository) -> dict[int, float]:
    conn = sqlite_repo._conn
    rows = conn.execute(
        """
        SELECT
            w.id AS wallet_id,
            w.initial_balance + COALESCE(
                SUM(CASE WHEN r.type = 'income' THEN r.amount_kzt ELSE -ABS(r.amount_kzt) END),
                0
            ) AS balance
        FROM wallets AS w
        LEFT JOIN records AS r ON r.wallet_id = w.id
        GROUP BY w.id, w.initial_balance
        ORDER BY w.id
        """
    ).fetchall()
    return {int(row[0]): float(row[1]) for row in rows}


def _validate_startup_integrity(
    json_path: str,
    sqlite_repo: SQLiteRecordRepository,
) -> None:
    json_storage = JsonStorage(json_path)
    json_wallets = json_storage.get_wallets()
    json_records = json_storage.get_records()
    json_transfers = json_storage.get_transfers()

    sqlite_wallets = sqlite_repo.load_wallets()
    sqlite_records = sqlite_repo.load_all()
    sqlite_transfers = sqlite_repo.load_transfers()

    if len(json_wallets) != len(sqlite_wallets):
        raise RuntimeError(
            f"Аварийный режим: wallets mismatch JSON={len(json_wallets)} "
            f"SQLite={len(sqlite_wallets)}"
        )
    if len(json_records) != len(sqlite_records):
        raise RuntimeError(
            f"Аварийный режим: records mismatch JSON={len(json_records)} "
            f"SQLite={len(sqlite_records)}"
        )
    if len(json_transfers) != len(sqlite_transfers):
        raise RuntimeError(
            f"Аварийный режим: transfers mismatch JSON={len(json_transfers)} "
            f"SQLite={len(sqlite_transfers)}"
        )

    json_repo = JsonFileRecordRepository(json_path)
    json_balances = _wallet_balances_from_json(json_repo)
    sqlite_balances = _wallet_balances_from_sqlite(sqlite_repo)

    net_worth_json = sum(json_balances.values())
    net_worth_sqlite = sum(sqlite_balances.values())
    if not math.isclose(net_worth_json, net_worth_sqlite, abs_tol=EPSILON):
        raise RuntimeError(
            f"Аварийный режим: net worth mismatch JSON={net_worth_json} SQLite={net_worth_sqlite}"
        )
    print("[bootstrap] JSON vs SQLite integrity check passed")


def _ensure_schema_meta(sqlite_repo: SQLiteRecordRepository) -> None:
    sqlite_repo._conn.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_meta (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
        """
    )
    sqlite_repo._conn.commit()


def _is_migration_verified(sqlite_repo: SQLiteRecordRepository) -> bool:
    _ensure_schema_meta(sqlite_repo)
    row = sqlite_repo._conn.execute(
        "SELECT value FROM schema_meta WHERE key = 'migration_verified'"
    ).fetchone()
    if row is None:
        return False
    value = row[0] if isinstance(row, tuple) else row["value"]
    return str(value).strip().lower() == "true"


def _mark_migration_verified(sqlite_repo: SQLiteRecordRepository) -> None:
    _ensure_schema_meta(sqlite_repo)
    sqlite_repo._conn.execute(
        """
        INSERT OR REPLACE INTO schema_meta (key, value)
        VALUES ('migration_verified', 'true')
        """
    )
    sqlite_repo._conn.commit()


def _validate_sqlite_integrity_only(sqlite_repo: SQLiteRecordRepository) -> None:
    conn = sqlite_repo._conn

    fk_issues = conn.execute("PRAGMA foreign_key_check").fetchall()
    if fk_issues:
        raise RuntimeError(f"Аварийный режим: foreign key violations found ({len(fk_issues)})")

    bad_transfers = conn.execute(
        """
        SELECT t.id, COUNT(r.id) AS linked_records
        FROM transfers AS t
        LEFT JOIN records AS r ON r.transfer_id = t.id
        GROUP BY t.id
        HAVING COUNT(r.id) != 2
        """
    ).fetchall()
    if bad_transfers:
        transfer_id, count = bad_transfers[0]
        raise RuntimeError(
            f"Аварийный режим: transfer #{int(transfer_id)} has {int(count)} records (expected 2)"
        )

    wrong_transfer_types = conn.execute(
        """
        SELECT
            t.id,
            SUM(CASE WHEN r.type = 'income' THEN 1 ELSE 0 END) AS income_count,
            SUM(CASE WHEN r.type = 'expense' THEN 1 ELSE 0 END) AS expense_count
        FROM transfers AS t
        JOIN records AS r ON r.transfer_id = t.id
        GROUP BY t.id
        HAVING income_count != 1 OR expense_count != 1
        """
    ).fetchone()
    if wrong_transfer_types is not None:
        transfer_id, income_count, expense_count = wrong_transfer_types
        raise RuntimeError(
            "Аварийный режим: transfer "
            f"#{int(transfer_id)} has invalid linked types "
            f"(income={int(income_count)}, expense={int(expense_count)})"
        )

    orphan_records = conn.execute(
        """
        SELECT r.id
        FROM records AS r
        LEFT JOIN wallets AS w ON w.id = r.wallet_id
        WHERE w.id IS NULL
        LIMIT 1
        """
    ).fetchone()
    if orphan_records is not None:
        raise RuntimeError(
            f"Аварийный режим: record #{int(orphan_records[0])} references missing wallet"
        )

    negative_violation = conn.execute(
        """
        SELECT reason FROM (
            SELECT 'wallet.initial_balance < 0' 
            AS reason FROM wallets WHERE initial_balance < 0
            UNION ALL
            SELECT 'record.amount_original < 0' 
            AS reason FROM records WHERE amount_original < 0
            UNION ALL
            SELECT 'record.amount_kzt < 0' 
            AS reason FROM records WHERE amount_kzt < 0
            UNION ALL
            SELECT 'record.rate_at_operation <= 0' 
            AS reason FROM records WHERE rate_at_operation <= 0
            UNION ALL
            SELECT 'transfer.amount_original <= 0' 
            AS reason FROM transfers WHERE amount_original <= 0
            UNION ALL
            SELECT 'transfer.amount_kzt <= 0' 
            AS reason FROM transfers WHERE amount_kzt <= 0
            UNION ALL
            SELECT 'transfer.rate_at_operation <= 0' 
            AS reason FROM transfers WHERE rate_at_operation <= 0
            UNION ALL
            SELECT 'mandatory.amount_original < 0' 
            AS reason FROM mandatory_expenses WHERE amount_original < 0
            UNION ALL
            SELECT 'mandatory.amount_kzt < 0' 
            AS reason FROM mandatory_expenses WHERE amount_kzt < 0
            UNION ALL
            SELECT 'mandatory.rate_at_operation <= 0' 
            AS reason FROM mandatory_expenses WHERE rate_at_operation <= 0
        )
        LIMIT 1
        """
    ).fetchone()
    if negative_violation is not None:
        raise RuntimeError(
            f"Аварийный режим: SQLite CHECK-like violation detected: {negative_violation[0]}"
        )

    print("[bootstrap] SQLite integrity check passed")


def bootstrap_repository() -> RecordRepository:
    if not USE_SQLITE:
        print("[bootstrap] Storage selected: JSON")
        return JsonFileRecordRepository(JSON_PATH)

    from infrastructure.sqlite_repository import SQLiteRecordRepository

    print("[bootstrap] Storage selected: SQLite")
    create_backup(JSON_PATH)

    db_has_data = _sqlite_has_data(SQLITE_PATH)
    migration_ran_now = False
    if not db_has_data and Path(JSON_PATH).exists():
        print("[bootstrap] SQLite empty, starting one-time migration from JSON")
        code = run_migration(
            Namespace(
                json_path=JSON_PATH,
                sqlite_path=SQLITE_PATH,
                schema_path=_resolve_schema_path("db/schema.sql"),
                dry_run=False,
            )
        )
        if code != 0:
            raise RuntimeError("Аварийный режим: migration to SQLite failed")
        migration_ran_now = True
    elif db_has_data:
        print("[bootstrap] SQLite already has data, migration skipped")
    else:
        print("[bootstrap] JSON source file not found, migration skipped")

    repository = SQLiteRecordRepository(
        SQLITE_PATH, schema_path=_resolve_schema_path("db/schema.sql")
    )

    migration_verified = _is_migration_verified(repository)
    if not migration_verified:
        if migration_ran_now:
            if Path(JSON_PATH).exists():
                _validate_startup_integrity(JSON_PATH, repository)
            _mark_migration_verified(repository)
            print("[bootstrap] Migration marked as verified")
        elif db_has_data:
            print("[bootstrap] Existing SQLite data detected, migration marked as verified")
            _mark_migration_verified(repository)
        elif Path(JSON_PATH).exists():
            _validate_startup_integrity(JSON_PATH, repository)
            _mark_migration_verified(repository)
            print("[bootstrap] Migration marked as verified")

    _validate_sqlite_integrity_only(repository)
    export_to_json(SQLITE_PATH, JSON_PATH, schema_path=_resolve_schema_path("db/schema.sql"))
    return repository
