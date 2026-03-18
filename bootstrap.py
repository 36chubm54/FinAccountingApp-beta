from __future__ import annotations

import logging
import threading
from pathlib import Path

from backup import create_backup, export_to_json
from config import JSON_BACKUP_KEEP_LAST, JSON_PATH, LAZY_EXPORT_SIZE_THRESHOLD, SQLITE_PATH
from infrastructure.repositories import RecordRepository
from infrastructure.sqlite_repository import SQLiteRecordRepository


def _resolve_schema_path(schema_path: str) -> str:
    candidate = Path(schema_path)
    if candidate.is_absolute():
        return str(candidate)
    return str((Path(__file__).resolve().parent / candidate).resolve())


def _ensure_schema_meta(sqlite_repo: SQLiteRecordRepository) -> None:
    sqlite_repo.ensure_schema_meta()


def _is_migration_verified(sqlite_repo: SQLiteRecordRepository) -> bool:
    _ensure_schema_meta(sqlite_repo)
    value = sqlite_repo.get_schema_meta("migration_verified")
    if value is None:
        return False
    return str(value).strip().lower() == "true"


def _mark_migration_verified(sqlite_repo: SQLiteRecordRepository) -> None:
    _ensure_schema_meta(sqlite_repo)
    sqlite_repo.set_schema_meta("migration_verified", "true")


def _ensure_system_wallet(sqlite_repo: SQLiteRecordRepository) -> None:
    if sqlite_repo.has_system_wallet_row():
        return
    sqlite_repo.save_initial_balance(0.0)


def _validate_sqlite_integrity_only(sqlite_repo: SQLiteRecordRepository) -> None:
    fk_issues = sqlite_repo.foreign_key_issues()
    if fk_issues:
        raise RuntimeError(f"Аварийный режим: foreign key violations found ({len(fk_issues)})")

    bad_transfers = sqlite_repo.query_all(
        """
        SELECT t.id, COUNT(r.id) AS linked_records
        FROM transfers AS t
        LEFT JOIN records AS r ON r.transfer_id = t.id
        GROUP BY t.id
        HAVING COUNT(r.id) != 2
        """
    )
    if bad_transfers:
        transfer_id, count = bad_transfers[0]
        raise RuntimeError(
            f"Аварийный режим: transfer #{int(transfer_id)} has {int(count)} records (expected 2)"
        )

    wrong_transfer_types = sqlite_repo.query_one(
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
    )
    if wrong_transfer_types is not None:
        transfer_id, income_count, expense_count = wrong_transfer_types
        raise RuntimeError(
            "Аварийный режим: transfer "
            f"#{int(transfer_id)} has invalid linked types "
            f"(income={int(income_count)}, expense={int(expense_count)})"
        )

    orphan_records = sqlite_repo.query_one(
        """
        SELECT r.id
        FROM records AS r
        LEFT JOIN wallets AS w ON w.id = r.wallet_id
        WHERE w.id IS NULL
        LIMIT 1
        """
    )
    if orphan_records is not None:
        raise RuntimeError(
            f"Аварийный режим: record #{int(orphan_records[0])} references missing wallet"
        )

    negative_violation = sqlite_repo.query_one(
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
    )
    if negative_violation is not None:
        raise RuntimeError(
            f"Аварийный режим: SQLite CHECK-like violation detected: {negative_violation[0]}"
        )

    logging.info("[bootstrap] SQLite integrity check passed")


def _should_export_json() -> bool:
    """Return True if JSON export is needed (data.json missing or outdated)."""
    json_path = Path(JSON_PATH)
    sqlite_path = Path(SQLITE_PATH)

    if not json_path.exists():
        logging.info("[bootstrap] JSON file missing, export required")
        return True

    if not sqlite_path.exists():
        # Should not happen because bootstrap creates SQLite if missing
        return False

    json_mtime = json_path.stat().st_mtime
    sqlite_mtime = sqlite_path.stat().st_mtime

    if sqlite_mtime > json_mtime:
        logging.info("[bootstrap] SQLite database newer than JSON, export required")
        return True

    logging.info("[bootstrap] JSON file is up‑to‑date, skipping export")
    return False


def _export_in_background() -> None:
    """Perform JSON export in a background thread (non‑blocking)."""

    def _export():
        try:
            export_to_json(
                SQLITE_PATH,
                JSON_PATH,
                schema_path=_resolve_schema_path("db/schema.sql"),
            )
            logging.info("[bootstrap] Background JSON export completed")
        except Exception as e:
            logging.error("[bootstrap] Background JSON export failed: %s", e)

    thread = threading.Thread(target=_export, daemon=True)
    thread.start()
    logging.info("[bootstrap] Started background JSON export thread")


def bootstrap_repository() -> RecordRepository:
    db_path = Path(SQLITE_PATH)
    db_existed = db_path.exists()
    create_backup(JSON_PATH, keep_last=JSON_BACKUP_KEEP_LAST)

    repository = SQLiteRecordRepository(
        SQLITE_PATH,
        schema_path=_resolve_schema_path("db/schema.sql"),
    )

    if db_existed:
        logging.info("[bootstrap] Existing SQLite database detected")
    else:
        logging.info("[bootstrap] SQLite database created and schema initialized")

    _ensure_system_wallet(repository)
    if not _is_migration_verified(repository):
        _mark_migration_verified(repository)
    _validate_sqlite_integrity_only(repository)

    # Lazy export: only if needed, and possibly in background for large DB
    if _should_export_json():
        sqlite_size = db_path.stat().st_size if db_path.exists() else 0
        if sqlite_size > LAZY_EXPORT_SIZE_THRESHOLD:
            logging.info(
                "[bootstrap] SQLite database is large (%d bytes), "
                "scheduling JSON export in background",
                sqlite_size,
            )
            _export_in_background()
        else:
            export_to_json(
                SQLITE_PATH,
                JSON_PATH,
                schema_path=_resolve_schema_path("db/schema.sql"),
            )
            logging.info("[bootstrap] JSON export completed synchronously")
    else:
        logging.info("[bootstrap] Skipping JSON export (already up‑to‑date)")

    return repository
