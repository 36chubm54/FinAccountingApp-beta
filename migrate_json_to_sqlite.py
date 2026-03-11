from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

from domain.records import MandatoryExpenseRecord, Record
from domain.wallets import Wallet
from storage.json_storage import JsonStorage
from storage.sqlite_storage import SQLiteStorage

EPSILON = 0.00001
PROJECT_ROOT = Path(__file__).resolve().parent


def _resolve_schema_path(schema_path: str) -> str:
    candidate = Path(schema_path)
    if candidate.is_absolute():
        return str(candidate)
    return str((Path(__file__).resolve().parent / candidate).resolve())


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Migrate financial data from JSON storage to SQLite storage."
    )
    parser.add_argument(
        "--json-path",
        default=str(PROJECT_ROOT / "data.json"),
        help="Path to source JSON file (default: <project>/data.json)",
    )
    parser.add_argument(
        "--sqlite-path",
        default=str(PROJECT_ROOT / "finance.db"),
        help="Path to target SQLite database (default: <project>/finance.db)",
    )
    parser.add_argument(
        "--schema-path",
        default=str(PROJECT_ROOT / "db" / "schema.sql"),
        help="Path to SQLite schema.sql (default: <project>/db/schema.sql)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate source and target connection without inserting data",
    )
    return parser.parse_args()


def _require_existing_wallet(wallets: list[Wallet], wallet_id: int, owner: str) -> None:
    if wallet_id <= 0:
        raise ValueError(f"{owner}: wallet_id must be positive, got {wallet_id}")
    wallet_ids = {wallet.id for wallet in wallets}
    if wallet_id not in wallet_ids:
        raise ValueError(f"{owner}: wallet_id={wallet_id} does not exist")


def _validate_source_integrity(
    wallets: list[Wallet],
    records: list[Record],
    transfers: list,
    mandatory_expenses: list[MandatoryExpenseRecord],
) -> None:
    wallet_ids = {wallet.id for wallet in wallets}
    if not wallet_ids:
        raise ValueError("Source JSON has no wallets")

    transfer_ids = {transfer.id for transfer in transfers}
    linked_records_by_transfer: dict[int, list[Record]] = {}

    for transfer in transfers:
        if transfer.id <= 0:
            raise ValueError(f"Transfer id must be positive, got {transfer.id}")
        if transfer.from_wallet_id not in wallet_ids or transfer.to_wallet_id not in wallet_ids:
            raise ValueError(
                f"Transfer #{transfer.id} has missing wallet links: "
                f"from={transfer.from_wallet_id} to={transfer.to_wallet_id}"
            )

    for record in records:
        _require_existing_wallet(wallets, int(record.wallet_id), f"Record #{record.id}")
        if record.transfer_id is not None:
            if record.transfer_id not in transfer_ids:
                raise ValueError(
                    f"Record #{record.id} references missing transfer_id={record.transfer_id}"
                )
            linked_records_by_transfer.setdefault(record.transfer_id, []).append(record)

    for transfer_id, linked_records in linked_records_by_transfer.items():
        if len(linked_records) != 2:
            raise ValueError(
                f"Transfer #{transfer_id} must have exactly 2 records, got {len(linked_records)}"
            )
        linked_types = {record.type for record in linked_records}
        if linked_types != {"income", "expense"}:
            raise ValueError(
                f"Transfer #{transfer_id} must have one income and one expense, got {linked_types}"
            )

    for transfer in transfers:
        linked_records = linked_records_by_transfer.get(transfer.id, [])
        if len(linked_records) != 2:
            raise ValueError(
                f"Transfer #{transfer.id} has invalid linked record count: {len(linked_records)}"
            )

    for expense in mandatory_expenses:
        _require_existing_wallet(wallets, int(expense.wallet_id), f"MandatoryExpense #{expense.id}")


def _check_target_is_empty(sqlite_storage: SQLiteStorage) -> None:
    tables = ("wallets", "transfers", "records", "mandatory_expenses")
    for table in tables:
        count = int(sqlite_storage.query_one(f"SELECT COUNT(*) FROM {table}")[0])
        if count > 0:
            raise RuntimeError(
                f"Target SQLite is not empty: table '{table}' already contains {count} rows"
            )


def _has_any_data(sqlite_storage: SQLiteStorage) -> bool:
    for table in ("wallets", "transfers", "records", "mandatory_expenses"):
        if int(sqlite_storage.query_one(f"SELECT COUNT(*) FROM {table}")[0]) > 0:
            return True
    return False


def _all_positive_unique_ids(items: list, id_getter) -> bool:
    ids = [int(id_getter(item)) for item in items]
    return all(value > 0 for value in ids) and len(ids) == len(set(ids))


def _set_sqlite_sequence(sqlite_storage: SQLiteStorage, table: str) -> None:
    max_id = int(sqlite_storage.query_one(f"SELECT COALESCE(MAX(id), 0) FROM {table}")[0])
    sqlite_storage.execute(
        """
        INSERT OR REPLACE INTO sqlite_sequence(name, seq) VALUES(?, ?)
        """,
        (table, max_id),
    )


def _insert_wallets(sqlite_storage: SQLiteStorage, wallets: list[Wallet]) -> dict[int, int]:
    mapping: dict[int, int] = {}
    preserve_ids = _all_positive_unique_ids(wallets, lambda wallet: wallet.id)
    for wallet in wallets:
        if preserve_ids:
            cursor = sqlite_storage.execute(
                """
                INSERT INTO wallets (
                    id, name, currency, initial_balance, system, allow_negative, is_active)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    int(wallet.id),
                    wallet.name,
                    wallet.currency.upper(),
                    float(wallet.initial_balance),
                    int(bool(wallet.system)),
                    int(bool(wallet.allow_negative)),
                    int(bool(wallet.is_active)),
                ),
            )
            mapping[int(wallet.id)] = int(wallet.id)
        else:
            cursor = sqlite_storage.execute(
                """
                INSERT INTO wallets (
                    name, currency, initial_balance, system, allow_negative, is_active)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    wallet.name,
                    wallet.currency.upper(),
                    float(wallet.initial_balance),
                    int(bool(wallet.system)),
                    int(bool(wallet.allow_negative)),
                    int(bool(wallet.is_active)),
                ),
            )
            lastrowid = cursor.lastrowid
            if lastrowid is None:
                raise RuntimeError("Failed to insert wallet: no row ID returned")
            mapping[int(wallet.id)] = int(lastrowid)
    if preserve_ids:
        _set_sqlite_sequence(sqlite_storage, "wallets")
    return mapping


def _insert_transfers(
    sqlite_storage: SQLiteStorage, transfers: list, wallet_map: dict[int, int]
) -> dict[int, int]:
    mapping: dict[int, int] = {}
    preserve_ids = _all_positive_unique_ids(transfers, lambda transfer: transfer.id)
    for transfer in transfers:
        from_wallet_id = wallet_map[int(transfer.from_wallet_id)]
        to_wallet_id = wallet_map[int(transfer.to_wallet_id)]
        if preserve_ids:
            cursor = sqlite_storage.execute(
                """
                INSERT INTO transfers (
                    id, from_wallet_id, to_wallet_id, date, amount_original, currency,
                    rate_at_operation, amount_kzt, description
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    int(transfer.id),
                    from_wallet_id,
                    to_wallet_id,
                    (
                        transfer.date.isoformat()
                        if hasattr(transfer.date, "isoformat")
                        else str(transfer.date)
                    ),
                    float(transfer.amount_original),
                    transfer.currency.upper(),
                    float(transfer.rate_at_operation),
                    float(transfer.amount_kzt),
                    transfer.description or "",
                ),
            )
            mapping[int(transfer.id)] = int(transfer.id)
        else:
            cursor = sqlite_storage.execute(
                """
                INSERT INTO transfers (
                    from_wallet_id, to_wallet_id, date, amount_original, currency,
                    rate_at_operation, amount_kzt, description
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    from_wallet_id,
                    to_wallet_id,
                    (
                        transfer.date.isoformat()
                        if hasattr(transfer.date, "isoformat")
                        else str(transfer.date)
                    ),
                    float(transfer.amount_original),
                    transfer.currency.upper(),
                    float(transfer.rate_at_operation),
                    float(transfer.amount_kzt),
                    transfer.description or "",
                ),
            )
            lastrowid = cursor.lastrowid
            if lastrowid is None:
                raise RuntimeError("Failed to insert transfer: no row ID returned")
            mapping[int(transfer.id)] = int(lastrowid)
    if preserve_ids:
        _set_sqlite_sequence(sqlite_storage, "transfers")
    return mapping


def _record_row_payload(
    record: Record, wallet_map: dict[int, int], transfer_map: dict[int, int]
) -> tuple:
    transfer_id = None
    if record.transfer_id is not None:
        transfer_id = transfer_map[int(record.transfer_id)]
    period = record.period if isinstance(record, MandatoryExpenseRecord) else None
    return (
        (
            record.date.isoformat()
            if hasattr(record.date, "isoformat") and not isinstance(record.date, str)
            else str(record.date)
        ),
        wallet_map[int(record.wallet_id)],
        transfer_id,
        float(record.amount_original or 0.0),
        str(record.currency).upper(),
        float(record.rate_at_operation),
        float(record.amount_kzt or 0.0),
        str(record.category),
        str(record.description or ""),
        str(period) if period is not None else None,
        "mandatory_expense" if isinstance(record, MandatoryExpenseRecord) else str(record.type),
    )


def _insert_records(
    sqlite_storage: SQLiteStorage,
    records: list[Record],
    wallet_map: dict[int, int],
    transfer_map: dict[int, int],
) -> dict[int, int]:
    mapping: dict[int, int] = {}
    preserve_ids = _all_positive_unique_ids(records, lambda record: record.id)
    for record in records:
        payload = _record_row_payload(record, wallet_map, transfer_map)
        if preserve_ids:
            cursor = sqlite_storage.execute(
                """
                INSERT INTO records (
                    id, type, date, wallet_id, transfer_id, amount_original,
                    currency, rate_at_operation, amount_kzt, category, description, period
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    int(record.id),
                    payload[10],
                    payload[0],
                    payload[1],
                    payload[2],
                    payload[3],
                    payload[4],
                    payload[5],
                    payload[6],
                    payload[7],
                    payload[8],
                    payload[9],
                ),
            )
            mapping[int(record.id)] = int(record.id)
        else:
            cursor = sqlite_storage.execute(
                """
                INSERT INTO records (
                    type, date, wallet_id, transfer_id, amount_original,
                    currency, rate_at_operation, amount_kzt, category, description, period
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    payload[10],
                    payload[0],
                    payload[1],
                    payload[2],
                    payload[3],
                    payload[4],
                    payload[5],
                    payload[6],
                    payload[7],
                    payload[8],
                    payload[9],
                ),
            )
            lastrowid = cursor.lastrowid
            if lastrowid is None:
                raise RuntimeError("Failed to insert record: no row ID returned")
            mapping[int(record.id)] = int(lastrowid)
    if preserve_ids:
        _set_sqlite_sequence(sqlite_storage, "records")
    return mapping


def _insert_mandatory_expenses(
    sqlite_storage: SQLiteStorage,
    expenses: list[MandatoryExpenseRecord],
    wallet_map: dict[int, int],
) -> dict[int, int]:
    mapping: dict[int, int] = {}
    preserve_ids = _all_positive_unique_ids(expenses, lambda expense: expense.id)
    for expense in expenses:
        if preserve_ids:
            cursor = sqlite_storage.execute(
                """
                INSERT INTO mandatory_expenses (
                    id, wallet_id, amount_original, currency, rate_at_operation,
                    amount_kzt, category, description, period, date, auto_pay
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    int(expense.id),
                    wallet_map[int(expense.wallet_id)],
                    float(expense.amount_original or 0.0),
                    str(expense.currency).upper(),
                    float(expense.rate_at_operation),
                    float(expense.amount_kzt or 0.0),
                    str(expense.category),
                    str(expense.description or ""),
                    str(expense.period),
                    str(expense.date) if expense.date else None,
                    int(bool(expense.auto_pay)),
                ),
            )
            mapping[int(expense.id)] = int(expense.id)
        else:
            cursor = sqlite_storage.execute(
                """
                INSERT INTO mandatory_expenses (
                    wallet_id, amount_original, currency, rate_at_operation,
                    amount_kzt, category, description, period, date, auto_pay
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    wallet_map[int(expense.wallet_id)],
                    float(expense.amount_original or 0.0),
                    str(expense.currency).upper(),
                    float(expense.rate_at_operation),
                    float(expense.amount_kzt or 0.0),
                    str(expense.category),
                    str(expense.description or ""),
                    str(expense.period),
                    str(expense.date) if expense.date else None,
                    int(bool(expense.auto_pay)),
                ),
            )
            lastrowid = cursor.lastrowid
            if lastrowid is None:
                raise RuntimeError("Failed to insert mandatory expense: no row ID returned")
            mapping[int(expense.id)] = int(lastrowid)
    if preserve_ids:
        _set_sqlite_sequence(sqlite_storage, "mandatory_expenses")
    return mapping


def _counts_from_sqlite(sqlite_storage: SQLiteStorage) -> dict[str, int]:
    return {
        "wallets": int(sqlite_storage.query_one("SELECT COUNT(*) FROM wallets")[0]),
        "transfers": int(sqlite_storage.query_one("SELECT COUNT(*) FROM transfers")[0]),
        "records": int(sqlite_storage.query_one("SELECT COUNT(*) FROM records")[0]),
        "mandatory_expenses": int(
            sqlite_storage.query_one("SELECT COUNT(*) FROM mandatory_expenses")[0]
        ),
    }


def _wallet_balances_from_json(wallets: list[Wallet], records: list[Record]) -> dict[int, float]:
    result = {wallet.id: float(wallet.initial_balance) for wallet in wallets}
    for record in records:
        result[int(record.wallet_id)] = result.get(int(record.wallet_id), 0.0) + float(
            record.signed_amount_kzt()
        )
    return result


def _wallet_balances_from_sqlite(sqlite_storage: SQLiteStorage) -> dict[int, float]:
    rows = sqlite_storage.query_all(
        """
        SELECT
            w.id AS wallet_id,
            w.initial_balance
            + COALESCE(
                SUM(
                    CASE
                        WHEN r.type = 'income' THEN r.amount_kzt
                        ELSE -ABS(r.amount_kzt)
                    END
                ),
                0
            ) AS balance
        FROM wallets AS w
        LEFT JOIN records AS r ON r.wallet_id = w.id
        GROUP BY w.id, w.initial_balance
        ORDER BY w.id
        """
    )
    return {int(row[0]): float(row[1]) for row in rows}


def validate_migration(
    sqlite_storage: SQLiteStorage,
    wallets: list[Wallet],
    records: list[Record],
    transfers: list,
    mandatory_expenses: list[MandatoryExpenseRecord],
    wallet_map: dict[int, int],
    record_map: dict[int, int],
    transfer_map: dict[int, int],
    mandatory_map: dict[int, int],
) -> tuple[bool, list[str]]:
    errors: list[str] = []

    expected_counts = {
        "wallets": len(wallets),
        "transfers": len(transfers),
        "records": len(records),
        "mandatory_expenses": len(mandatory_expenses),
    }
    actual_counts = _counts_from_sqlite(sqlite_storage)

    for name, expected in expected_counts.items():
        actual = actual_counts[name]
        if expected != actual:
            errors.append(f"Count mismatch for {name}: json={expected}, sqlite={actual}")

    json_balances = _wallet_balances_from_json(wallets, records)
    sqlite_balances = _wallet_balances_from_sqlite(sqlite_storage)
    for old_wallet_id, json_balance in sorted(json_balances.items()):
        sqlite_wallet_id = wallet_map.get(old_wallet_id)
        if sqlite_wallet_id is None:
            errors.append(f"Wallet id mapping missing for source wallet #{old_wallet_id}")
            continue
        sqlite_balance = sqlite_balances.get(sqlite_wallet_id)
        if sqlite_balance is None:
            errors.append(
                f"Wallet #{old_wallet_id} -> #{sqlite_wallet_id} is absent in SQLite balance set"
            )
            continue
        if not math.isclose(json_balance, sqlite_balance, abs_tol=EPSILON):
            errors.append(
                f"Wallet balance mismatch for wallet #{old_wallet_id} -> #{sqlite_wallet_id}: "
                f"json={json_balance}, sqlite={sqlite_balance}"
            )

    net_worth_json = sum(json_balances.values())
    net_worth_sqlite = sum(sqlite_balances.values())
    if not math.isclose(net_worth_json, net_worth_sqlite, abs_tol=EPSILON):
        errors.append(f"Net worth mismatch: json={net_worth_json}, sqlite={net_worth_sqlite}")

    if len(record_map) != len(records):
        errors.append("Record id mapping is incomplete")
    if len(transfer_map) != len(transfers):
        errors.append("Transfer id mapping is incomplete")
    if len(mandatory_map) != len(mandatory_expenses):
        errors.append("Mandatory expense id mapping is incomplete")

    return (len(errors) == 0, errors)


def _validate_existing_target_equivalence(
    sqlite_storage: SQLiteStorage,
    wallets: list[Wallet],
    records: list[Record],
    transfers: list,
    mandatory_expenses: list[MandatoryExpenseRecord],
) -> tuple[bool, list[str]]:
    identity_map = {int(wallet.id): int(wallet.id) for wallet in wallets}
    return validate_migration(
        sqlite_storage=sqlite_storage,
        wallets=wallets,
        records=records,
        transfers=transfers,
        mandatory_expenses=mandatory_expenses,
        wallet_map=identity_map,
        record_map={int(record.id): int(record.id) for record in records},
        transfer_map={int(transfer.id): int(transfer.id) for transfer in transfers},
        mandatory_map={int(expense.id): int(expense.id) for expense in mandatory_expenses},
    )


def run_dry_run(args: argparse.Namespace) -> int:
    print("== DRY RUN: JSON -> SQLite migration check ==")
    json_storage = JsonStorage(file_path=args.json_path)
    sqlite_storage = SQLiteStorage(db_path=args.sqlite_path)
    try:
        schema_path = _resolve_schema_path(args.schema_path)
        if not Path(schema_path).exists():
            raise FileNotFoundError(f"schema.sql not found: {schema_path}")
        sqlite_storage.connection_is_available()
        print(f"[ok] SQLite connection is available: {args.sqlite_path}")
        print(f"[ok] Schema path resolved: {schema_path}")

        wallets = json_storage.get_wallets()
        transfers = json_storage.get_transfers()
        records = json_storage.get_records()
        mandatory_expenses = json_storage.get_mandatory_expenses()

        _validate_source_integrity(wallets, records, transfers, mandatory_expenses)

        print(f"[ok] JSON source loaded: {args.json_path}")
        print(f"  wallets: {len(wallets)}")
        print(f"  transfers: {len(transfers)}")
        print(f"  records: {len(records)}")
        print(f"  mandatory_expenses: {len(mandatory_expenses)}")
        print("[ok] Integrity checks passed")
        print("[dry-run] No INSERT and no explicit COMMIT executed")
        return 0
    except Exception as exc:
        print(f"[error] Dry-run failed: {exc}")
        return 1
    finally:
        sqlite_storage.close()


def run_migration(args: argparse.Namespace) -> int:
    print("== MIGRATION: JSON -> SQLite ==")
    json_storage = JsonStorage(file_path=args.json_path)
    sqlite_storage = SQLiteStorage(db_path=args.sqlite_path)

    try:
        schema_path = _resolve_schema_path(args.schema_path)
        if not Path(schema_path).exists():
            raise FileNotFoundError(f"schema.sql not found: {schema_path}")

        wallets = json_storage.get_wallets()
        transfers = json_storage.get_transfers()
        records = json_storage.get_records()
        mandatory_expenses = json_storage.get_mandatory_expenses()

        _validate_source_integrity(wallets, records, transfers, mandatory_expenses)
        print("[ok] Source data integrity passed")

        sqlite_storage.initialize_schema(schema_path)
        if _has_any_data(sqlite_storage):
            valid_existing, existing_errors = _validate_existing_target_equivalence(
                sqlite_storage,
                wallets=wallets,
                records=records,
                transfers=transfers,
                mandatory_expenses=mandatory_expenses,
            )
            if valid_existing:
                print("[ok] Target SQLite already contains equivalent data, migration skipped")
                return 0
            details = "; ".join(existing_errors[:3]) if existing_errors else "dataset mismatch"
            raise RuntimeError(
                f"Target SQLite is not empty and differs from source JSON: {details}"
            )

        sqlite_storage.begin()
        print("[tx] Transaction started")

        print("[1/4] Migrating wallets...")
        wallet_map = _insert_wallets(sqlite_storage, wallets)
        print("[2/4] Migrating transfers...")
        transfer_map = _insert_transfers(sqlite_storage, transfers, wallet_map)
        print("[3/4] Migrating records...")
        record_map = _insert_records(sqlite_storage, records, wallet_map, transfer_map)
        print("[4/4] Migrating mandatory_expenses...")
        mandatory_map = _insert_mandatory_expenses(sqlite_storage, mandatory_expenses, wallet_map)

        valid, errors = validate_migration(
            sqlite_storage=sqlite_storage,
            wallets=wallets,
            records=records,
            transfers=transfers,
            mandatory_expenses=mandatory_expenses,
            wallet_map=wallet_map,
            record_map=record_map,
            transfer_map=transfer_map,
            mandatory_map=mandatory_map,
        )
        if not valid:
            print("[error] Validation failed, rollback started")
            for line in errors:
                print(f"  - {line}")
            sqlite_storage.rollback()
            print("[tx] Rollback complete")
            return 1

        sqlite_storage.commit()
        print("[tx] Commit complete")
        print("[ok] Migration finished successfully")
        return 0
    except Exception as exc:
        try:
            sqlite_storage.rollback()
            print("[tx] Rollback complete")
        except Exception:
            print("[warn] Rollback failed")
        print(f"[error] Migration failed: {exc}")
        return 1
    finally:
        sqlite_storage.close()


def main() -> int:
    args = parse_args()
    if args.dry_run:
        return run_dry_run(args)
    return run_migration(args)


if __name__ == "__main__":
    sys.exit(main())
