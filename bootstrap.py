from __future__ import annotations

from pathlib import Path

from backup import create_backup, export_to_json
from config import JSON_PATH, SQLITE_PATH
from infrastructure.repositories import RecordRepository
from infrastructure.sqlite_repository import SQLiteRecordRepository


def _resolve_schema_path(schema_path: str) -> str:
    candidate = Path(schema_path)
    if candidate.is_absolute():
        return str(candidate)
    return str((Path(__file__).resolve().parent / "db" / candidate.name).resolve())


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


def _ensure_system_wallet(sqlite_repo: SQLiteRecordRepository) -> None:
    row = sqlite_repo._conn.execute(
        "SELECT id FROM wallets WHERE system = 1 OR id = 1 ORDER BY id LIMIT 1"
    ).fetchone()
    if row is not None:
        return
    sqlite_repo.save_initial_balance(0.0)


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
    db_path = Path(SQLITE_PATH)
    db_existed = db_path.exists()
    create_backup(JSON_PATH)

    repository = SQLiteRecordRepository(
        SQLITE_PATH,
        schema_path=_resolve_schema_path("db/schema.sql"),
    )

    if db_existed:
        print("[bootstrap] Storage selected: SQLite")
        print("[bootstrap] Existing SQLite database detected")
    else:
        print("[bootstrap] Storage selected: SQLite")
        print("[bootstrap] SQLite database created and schema initialized")

    _ensure_system_wallet(repository)
    if not _is_migration_verified(repository):
        _mark_migration_verified(repository)
    _validate_sqlite_integrity_only(repository)
    export_to_json(SQLITE_PATH, JSON_PATH, schema_path=_resolve_schema_path("db/schema.sql"))
    return repository
