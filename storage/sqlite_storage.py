from __future__ import annotations

import sqlite3
from datetime import date as dt_date
from pathlib import Path

from domain.records import ExpenseRecord, IncomeRecord, MandatoryExpenseRecord, Record
from domain.transfers import Transfer
from domain.wallets import Wallet

from .base import Storage


class SQLiteStorage(Storage):
    """SQLite-backed storage adapter without domain/business logic."""

    def __init__(self, db_path: str = "records.db") -> None:
        self._db_path = db_path
        # GUI import/export tasks run via background worker threads.
        # A single operation is executed at a time, so cross-thread access is serialized.
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON;")
        self._conn.execute("PRAGMA journal_mode = WAL;")

    def close(self) -> None:
        self._conn.close()

    def initialize_schema(self, schema_path: str | None = None) -> None:
        if schema_path is None:
            schema_path = str(Path(__file__).resolve().parents[1] / "db" / "schema.sql")
        schema = Path(schema_path).read_text(encoding="utf-8")
        self._conn.executescript(schema)
        self._conn.commit()

    def execute(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        return self._conn.execute(sql, params)

    def query_one(self, sql: str, params: tuple = ()):
        return self._conn.execute(sql, params).fetchone()

    def query_all(self, sql: str, params: tuple = ()) -> list[sqlite3.Row]:
        return self._conn.execute(sql, params).fetchall()

    def begin(self) -> None:
        self._conn.execute("BEGIN")

    def commit(self) -> None:
        self._conn.commit()

    def rollback(self) -> None:
        self._conn.rollback()

    def connection_is_available(self) -> bool:
        self._conn.execute("SELECT 1")
        return True

    def get_wallets(self) -> list[Wallet]:
        rows = self._conn.execute(
            """
            SELECT id, name, currency, initial_balance, system, allow_negative, is_active
            FROM wallets
            ORDER BY id
            """
        ).fetchall()
        return [
            Wallet(
                id=int(row["id"]),
                name=str(row["name"]),
                currency=str(row["currency"]),
                initial_balance=float(row["initial_balance"]),
                system=bool(row["system"]),
                allow_negative=bool(row["allow_negative"]),
                is_active=bool(row["is_active"]),
            )
            for row in rows
        ]

    def save_wallet(self, wallet: Wallet) -> None:
        row = self._conn.execute(
            "SELECT 1 FROM wallets WHERE id = ?",
            (int(wallet.id),),
        ).fetchone()
        if row is not None:
            self._conn.execute(
                """
                UPDATE wallets
                SET
                    name = ?,
                    currency = ?,
                    initial_balance = ?,
                    system = ?,
                    allow_negative = ?,
                    is_active = ?
                WHERE id = ?
                """,
                (
                    wallet.name,
                    wallet.currency.upper(),
                    float(wallet.initial_balance),
                    int(bool(wallet.system)),
                    int(bool(wallet.allow_negative)),
                    int(bool(wallet.is_active)),
                    int(wallet.id),
                ),
            )
        else:
            cursor = self._conn.execute(
                """
                INSERT INTO wallets (
                    name,
                    currency,
                    initial_balance,
                    system,
                    allow_negative,
                    is_active
                )
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
            wallet_id = cursor.lastrowid
            if wallet_id is None:
                raise RuntimeError("Failed to obtain lastrowid for wallets insert")
        self._conn.commit()

    def get_records(self) -> list[Record]:
        rows = self._conn.execute(
            """
            SELECT
                id,
                type,
                date,
                wallet_id,
                transfer_id,
                amount_original,
                currency,
                rate_at_operation,
                amount_kzt,
                category,
                description,
                period
            FROM records
            ORDER BY id
            """
        ).fetchall()
        records: list[Record] = []
        for row in rows:
            payload = {
                "id": int(row["id"]),
                "date": str(row["date"]),
                "wallet_id": int(row["wallet_id"]),
                "transfer_id": int(row["transfer_id"]) if row["transfer_id"] is not None else None,
                "amount_original": float(row["amount_original"]),
                "currency": str(row["currency"]).upper(),
                "rate_at_operation": float(row["rate_at_operation"]),
                "amount_kzt": float(row["amount_kzt"]),
                "category": str(row["category"]),
                "description": str(row["description"] or ""),
            }
            record_type = str(row["type"])
            if record_type == "income":
                records.append(IncomeRecord(**payload))
            elif record_type == "expense":
                records.append(ExpenseRecord(**payload))
            elif record_type == "mandatory_expense":
                records.append(
                    MandatoryExpenseRecord(
                        **payload,
                        period=str(row["period"] or "monthly"),  # type: ignore[arg-type]
                    )
                )
        return records

    def save_record(self, record: Record) -> None:
        period = record.period if isinstance(record, MandatoryExpenseRecord) else None
        row = self._conn.execute(
            "SELECT 1 FROM records WHERE id = ?",
            (int(record.id),),
        ).fetchone()
        if row is not None:
            self._conn.execute(
                """
                UPDATE records
                SET
                    type = ?,
                    date = ?,
                    wallet_id = ?,
                    transfer_id = ?,
                    amount_original = ?,
                    currency = ?,
                    rate_at_operation = ?,
                    amount_kzt = ?,
                    category = ?,
                    description = ?,
                    period = ?
                WHERE id = ?
                """,
                (
                    self._record_type(record),
                    self._date_as_text(record.date),
                    int(record.wallet_id),
                    int(record.transfer_id) if record.transfer_id is not None else None,
                    float(record.amount_original or 0.0),
                    str(record.currency).upper(),
                    float(record.rate_at_operation),
                    float(record.amount_kzt or 0.0),
                    str(record.category),
                    str(record.description or ""),
                    str(period) if period is not None else None,
                    int(record.id),
                ),
            )
        else:
            cursor = self._conn.execute(
                """
                INSERT INTO records (
                    type,
                    date,
                    wallet_id,
                    transfer_id,
                    amount_original,
                    currency,
                    rate_at_operation,
                    amount_kzt,
                    category,
                    description,
                    period
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    self._record_type(record),
                    self._date_as_text(record.date),
                    int(record.wallet_id),
                    int(record.transfer_id) if record.transfer_id is not None else None,
                    float(record.amount_original or 0.0),
                    str(record.currency).upper(),
                    float(record.rate_at_operation),
                    float(record.amount_kzt or 0.0),
                    str(record.category),
                    str(record.description or ""),
                    str(period) if period is not None else None,
                ),
            )
            record_id = cursor.lastrowid
            if record_id is None:
                raise RuntimeError("Failed to obtain lastrowid for records insert")
        self._conn.commit()

    def get_transfers(self) -> list[Transfer]:
        rows = self._conn.execute(
            """
            SELECT
                id,
                from_wallet_id,
                to_wallet_id,
                date,
                amount_original,
                currency,
                rate_at_operation,
                amount_kzt,
                description
            FROM transfers
            ORDER BY id
            """
        ).fetchall()
        return [
            Transfer(
                id=int(row["id"]),
                from_wallet_id=int(row["from_wallet_id"]),
                to_wallet_id=int(row["to_wallet_id"]),
                date=str(row["date"]),
                amount_original=float(row["amount_original"]),
                currency=str(row["currency"]).upper(),
                rate_at_operation=float(row["rate_at_operation"]),
                amount_kzt=float(row["amount_kzt"]),
                description=str(row["description"] or ""),
            )
            for row in rows
        ]

    def save_transfer(self, transfer: Transfer) -> None:
        row = self._conn.execute(
            "SELECT 1 FROM transfers WHERE id = ?",
            (int(transfer.id),),
        ).fetchone()
        if row is not None:
            self._conn.execute(
                """
                UPDATE transfers
                SET
                    from_wallet_id = ?,
                    to_wallet_id = ?,
                    date = ?,
                    amount_original = ?,
                    currency = ?,
                    rate_at_operation = ?,
                    amount_kzt = ?,
                    description = ?
                WHERE id = ?
                """,
                (
                    int(transfer.from_wallet_id),
                    int(transfer.to_wallet_id),
                    self._date_as_text(transfer.date),
                    float(transfer.amount_original),
                    str(transfer.currency).upper(),
                    float(transfer.rate_at_operation),
                    float(transfer.amount_kzt),
                    str(transfer.description or ""),
                    int(transfer.id),
                ),
            )
        else:
            cursor = self._conn.execute(
                """
                INSERT INTO transfers (
                    from_wallet_id,
                    to_wallet_id,
                    date,
                    amount_original,
                    currency,
                    rate_at_operation,
                    amount_kzt,
                    description
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    int(transfer.from_wallet_id),
                    int(transfer.to_wallet_id),
                    self._date_as_text(transfer.date),
                    float(transfer.amount_original),
                    str(transfer.currency).upper(),
                    float(transfer.rate_at_operation),
                    float(transfer.amount_kzt),
                    str(transfer.description or ""),
                ),
            )
            transfer_id = cursor.lastrowid
            if transfer_id is None:
                raise RuntimeError("Failed to obtain lastrowid for transfers insert")
        self._conn.commit()

    def get_mandatory_expenses(self) -> list[MandatoryExpenseRecord]:
        columns = {
            str(row["name"])
            for row in self._conn.execute("PRAGMA table_info(mandatory_expenses)").fetchall()
        }
        has_date = "date" in columns
        has_auto_pay = "auto_pay" in columns
        select_columns = """
                id,
                wallet_id,
                amount_original,
                currency,
                rate_at_operation,
                amount_kzt,
                category,
                description,
                period
        """
        if has_date:
            select_columns += ",\n                date"
        if has_auto_pay:
            select_columns += ",\n                auto_pay"
        rows = self._conn.execute(
            f"""
            SELECT
{select_columns}
            FROM mandatory_expenses
            ORDER BY id
            """
        ).fetchall()
        return [
            MandatoryExpenseRecord(
                id=int(row["id"]),
                wallet_id=int(row["wallet_id"]),
                amount_original=float(row["amount_original"]),
                currency=str(row["currency"]).upper(),
                rate_at_operation=float(row["rate_at_operation"]),
                amount_kzt=float(row["amount_kzt"]),
                category=str(row["category"]),
                description=str(row["description"] or ""),
                period=str(row["period"] or "monthly"),  # type: ignore[arg-type]
                date=str(row["date"]) if has_date and row["date"] else "",
                auto_pay=bool(row["auto_pay"]) if has_auto_pay else False,
            )
            for row in rows
        ]

    @staticmethod
    def _record_type(record: Record) -> str:
        if isinstance(record, MandatoryExpenseRecord):
            return "mandatory_expense"
        if isinstance(record, IncomeRecord):
            return "income"
        return "expense"

    @staticmethod
    def _date_as_text(value: dt_date | str) -> str:
        if isinstance(value, dt_date):
            return value.isoformat()
        return str(value)
