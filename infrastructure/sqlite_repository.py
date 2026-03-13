from __future__ import annotations

from contextlib import contextmanager
from datetime import date as dt_date

from domain.records import IncomeRecord, MandatoryExpenseRecord, Record
from domain.transfers import Transfer
from domain.wallets import Wallet
from infrastructure.repositories import RecordRepository
from storage.sqlite_storage import SQLiteStorage

SYSTEM_WALLET_ID = 1


class SQLiteRecordRepository(RecordRepository):
    """RecordRepository implementation backed by SQLite."""

    def __init__(self, db_path: str = "finance.db", schema_path: str | None = None) -> None:
        self._storage = SQLiteStorage(db_path)
        self._storage.initialize_schema(schema_path)
        self._conn = self._storage._conn
        self._normalize_existing_ids_from_one_if_needed()

    def close(self) -> None:
        self._storage.close()

    @property
    def db_path(self) -> str:
        return str(self._storage._db_path)

    def ensure_schema_meta(self) -> None:
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
            """
        )
        self._conn.commit()

    def get_schema_meta(self, key: str) -> str | None:
        self.ensure_schema_meta()
        row = self._conn.execute(
            "SELECT value FROM schema_meta WHERE key = ?",
            (str(key),),
        ).fetchone()
        if row is None:
            return None
        return str(row[0])

    def set_schema_meta(self, key: str, value: str) -> None:
        self.ensure_schema_meta()
        self._conn.execute(
            """
            INSERT OR REPLACE INTO schema_meta (key, value)
            VALUES (?, ?)
            """,
            (str(key), str(value)),
        )
        self._conn.commit()

    def has_system_wallet_row(self) -> bool:
        row = self._conn.execute(
            "SELECT id FROM wallets WHERE system = 1 OR id = 1 ORDER BY id LIMIT 1"
        ).fetchone()
        return row is not None

    def foreign_key_issues(self) -> list:
        return self._conn.execute("PRAGMA foreign_key_check").fetchall()

    def query_all(self, sql: str, params: tuple = ()) -> list:
        return self._conn.execute(sql, params).fetchall()

    def query_one(self, sql: str, params: tuple = ()):
        return self._conn.execute(sql, params).fetchone()

    def query_iter(self, sql: str, params: tuple = (), *, chunk_size: int = 1000):
        cursor = self._conn.execute(sql, params)
        while True:
            rows = cursor.fetchmany(chunk_size)
            if not rows:
                break
            yield from rows

    def execute(self, sql: str, params: tuple = ()) -> None:
        self._conn.execute(sql, params)

    def commit(self) -> None:
        self._conn.commit()

    @contextmanager
    def transaction(self):
        # Public transaction helper mainly for tests and one-off maintenance scripts.
        # Prefer repository-level methods for production code.
        with self._conn:
            yield

    @staticmethod
    def _date_as_text(value: dt_date | str) -> str:
        if isinstance(value, dt_date):
            return value.isoformat()
        return str(value)

    @staticmethod
    def _record_type(record: Record) -> str:
        if isinstance(record, MandatoryExpenseRecord):
            return "mandatory_expense"
        if isinstance(record, IncomeRecord):
            return "income"
        return "expense"

    @staticmethod
    def _require_lastrowid(lastrowid: int | None, table: str) -> int:
        if lastrowid is None:
            raise RuntimeError(f"Failed to obtain lastrowid for {table} insert")
        return int(lastrowid)

    def _validate_transfer_integrity(
        self, records: list[Record], transfers: list[Transfer]
    ) -> None:
        transfer_ids = {transfer.id for transfer in transfers}
        grouped: dict[int, list[Record]] = {}
        for record in records:
            if record.transfer_id is None:
                continue
            if record.transfer_id not in transfer_ids:
                raise ValueError(f"Dangling transfer link in record #{record.id}")
            grouped.setdefault(record.transfer_id, []).append(record)
        for transfer in transfers:
            linked = grouped.get(transfer.id, [])
            if len(linked) != 2:
                raise ValueError(
                    f"Transfer integrity violated for #{transfer.id}: {len(linked)} records"
                )
            if {record.type for record in linked} != {"income", "expense"}:
                raise ValueError(
                    f"Transfer integrity violated for #{transfer.id}: invalid record types"
                )

    def _reset_autoincrement(self, table: str) -> None:
        self._conn.execute("DELETE FROM sqlite_sequence WHERE name = ?", (table,))

    def _reset_autoincrement_many(self, tables: tuple[str, ...]) -> None:
        for table in tables:
            self._reset_autoincrement(table)

    def _ids_are_normalized_from_one(self, table: str) -> bool:
        rows = self._conn.execute(f"SELECT id FROM {table} ORDER BY id").fetchall()
        return all(int(row[0]) == index for index, row in enumerate(rows, start=1))

    def _normalize_existing_ids_from_one_if_needed(self) -> None:
        tables = ("wallets", "records", "transfers", "mandatory_expenses")
        if all(self._ids_are_normalized_from_one(table) for table in tables):
            return
        wallets = self._storage.get_wallets()
        records = self._storage.get_records()
        transfers = self._storage.get_transfers()
        mandatory_expenses = self._storage.get_mandatory_expenses()
        self.replace_all_data(
            wallets=wallets,
            records=records,
            mandatory_expenses=mandatory_expenses,
            transfers=transfers,
        )

    def _insert_wallet_row(self, wallet: Wallet) -> int:
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
                str(wallet.name),
                str(wallet.currency).upper(),
                float(wallet.initial_balance),
                int(bool(wallet.system)),
                int(bool(wallet.allow_negative)),
                int(bool(wallet.is_active)),
            ),
        )
        return self._require_lastrowid(cursor.lastrowid, "wallets")

    def _update_wallet_row(self, wallet_id: int, wallet: Wallet) -> None:
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
                str(wallet.name),
                str(wallet.currency).upper(),
                float(wallet.initial_balance),
                int(bool(wallet.system)),
                int(bool(wallet.allow_negative)),
                int(bool(wallet.is_active)),
                int(wallet_id),
            ),
        )

    def _insert_transfer_row(
        self,
        transfer: Transfer,
        *,
        from_wallet_id: int | None = None,
        to_wallet_id: int | None = None,
    ) -> int:
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
                int(from_wallet_id if from_wallet_id is not None else transfer.from_wallet_id),
                int(to_wallet_id if to_wallet_id is not None else transfer.to_wallet_id),
                self._date_as_text(transfer.date),
                float(transfer.amount_original),
                str(transfer.currency).upper(),
                float(transfer.rate_at_operation),
                float(transfer.amount_kzt),
                str(transfer.description or ""),
            ),
        )
        return self._require_lastrowid(cursor.lastrowid, "transfers")

    def _update_transfer_row(
        self,
        transfer_id: int,
        transfer: Transfer,
        *,
        from_wallet_id: int | None = None,
        to_wallet_id: int | None = None,
    ) -> None:
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
                int(from_wallet_id if from_wallet_id is not None else transfer.from_wallet_id),
                int(to_wallet_id if to_wallet_id is not None else transfer.to_wallet_id),
                self._date_as_text(transfer.date),
                float(transfer.amount_original),
                str(transfer.currency).upper(),
                float(transfer.rate_at_operation),
                float(transfer.amount_kzt),
                str(transfer.description or ""),
                int(transfer_id),
            ),
        )

    def _insert_record_row(
        self,
        record: Record,
        *,
        wallet_id: int | None = None,
        transfer_id: int | None = None,
    ) -> int:
        period = record.period if isinstance(record, MandatoryExpenseRecord) else None
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
                int(wallet_id if wallet_id is not None else record.wallet_id),
                int(transfer_id) if transfer_id is not None else None,
                float(record.amount_original or 0.0),
                str(record.currency).upper(),
                float(record.rate_at_operation),
                float(record.amount_kzt or 0.0),
                str(record.category),
                str(record.description or ""),
                str(period) if period is not None else None,
            ),
        )
        return self._require_lastrowid(cursor.lastrowid, "records")

    def _update_record_row(
        self,
        record_id: int,
        record: Record,
        *,
        wallet_id: int | None = None,
        transfer_id: int | None = None,
    ) -> None:
        period = record.period if isinstance(record, MandatoryExpenseRecord) else None
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
                int(wallet_id if wallet_id is not None else record.wallet_id),
                int(transfer_id) if transfer_id is not None else None,
                float(record.amount_original or 0.0),
                str(record.currency).upper(),
                float(record.rate_at_operation),
                float(record.amount_kzt or 0.0),
                str(record.category),
                str(record.description or ""),
                str(period) if period is not None else None,
                int(record_id),
            ),
        )

    def _insert_mandatory_row(self, expense: MandatoryExpenseRecord, *, wallet_id: int) -> int:
        cursor = self._conn.execute(
            """
            INSERT INTO mandatory_expenses (
                wallet_id,
                amount_original,
                currency,
                rate_at_operation,
                amount_kzt,
                category,
                description,
                period,
                date,
                auto_pay
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                int(wallet_id),
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
        return self._require_lastrowid(cursor.lastrowid, "mandatory_expenses")

    def _upsert_system_wallet_balance(self, balance: float) -> None:
        row = self._conn.execute(
            "SELECT id FROM wallets WHERE id = ?",
            (SYSTEM_WALLET_ID,),
        ).fetchone()
        if row is not None:
            self._conn.execute(
                "UPDATE wallets SET initial_balance = ?, system = 1 WHERE id = ?",
                (float(balance), SYSTEM_WALLET_ID),
            )
            return

        fallback_row = self._conn.execute(
            "SELECT id FROM wallets WHERE system = 1 ORDER BY id LIMIT 1"
        ).fetchone()
        if fallback_row is not None:
            self._conn.execute(
                "UPDATE wallets SET initial_balance = ?, system = 1 WHERE id = ?",
                (float(balance), int(fallback_row[0])),
            )
            return

        wallet = Wallet(
            id=SYSTEM_WALLET_ID,
            name="Main wallet",
            currency="KZT",
            initial_balance=float(balance),
            system=True,
            allow_negative=False,
            is_active=True,
        )
        self._insert_wallet_row(wallet)

    def load_active_wallets(self) -> list[Wallet]:
        return [wallet for wallet in self.load_wallets() if wallet.is_active]

    def create_wallet(
        self,
        *,
        name: str,
        currency: str,
        initial_balance: float,
        allow_negative: bool = False,
        system: bool = False,
    ) -> Wallet:
        with self._conn:
            draft = Wallet(
                id=SYSTEM_WALLET_ID,
                name=str(name or "Wallet"),
                currency=str(currency or "KZT").upper(),
                initial_balance=float(initial_balance),
                system=bool(system),
                allow_negative=bool(allow_negative),
                is_active=True,
            )
            wallet_id = self._insert_wallet_row(draft)
            return Wallet(
                id=wallet_id,
                name=draft.name,
                currency=draft.currency,
                initial_balance=draft.initial_balance,
                system=draft.system,
                allow_negative=draft.allow_negative,
                is_active=draft.is_active,
            )

    def save_wallet(self, wallet: Wallet) -> None:
        with self._conn:
            row = self._conn.execute(
                "SELECT 1 FROM wallets WHERE id = ?",
                (int(wallet.id),),
            ).fetchone()
            if row is not None:
                self._update_wallet_row(int(wallet.id), wallet)
            else:
                self._insert_wallet_row(wallet)

    def soft_delete_wallet(self, wallet_id: int) -> bool:
        wallet_id = int(wallet_id)
        with self._conn:
            row = self._conn.execute(
                "SELECT system FROM wallets WHERE id = ?",
                (wallet_id,),
            ).fetchone()
            if row is None:
                return False
            if bool(row[0]):
                return False
            self._conn.execute("UPDATE wallets SET is_active = 0 WHERE id = ?", (wallet_id,))
            return True

    def load_wallets(self) -> list[Wallet]:
        return self._storage.get_wallets()

    def get_system_wallet(self) -> Wallet:
        for wallet in self.load_wallets():
            if wallet.system or wallet.id == SYSTEM_WALLET_ID:
                return wallet
        return Wallet(
            id=SYSTEM_WALLET_ID,
            name="Main wallet",
            currency="KZT",
            initial_balance=0.0,
            system=True,
            allow_negative=False,
            is_active=True,
        )

    def save_transfer(self, transfer: Transfer) -> None:
        with self._conn:
            row = self._conn.execute(
                "SELECT 1 FROM transfers WHERE id = ?",
                (int(transfer.id),),
            ).fetchone()
            if row is not None:
                self._update_transfer_row(int(transfer.id), transfer)
            else:
                self._insert_transfer_row(transfer)

    def load_transfers(self) -> list[Transfer]:
        return self._storage.get_transfers()

    def replace_records_and_transfers(
        self, records: list[Record], transfers: list[Transfer]
    ) -> None:
        self._validate_transfer_integrity(records, transfers)

        with self._conn:
            self._conn.execute("DELETE FROM records")
            self._conn.execute("DELETE FROM transfers")
            self._reset_autoincrement_many(("records", "transfers"))

            transfer_id_map: dict[int, int] = {}
            for transfer in sorted(transfers, key=lambda item: item.id):
                new_transfer_id = self._insert_transfer_row(transfer)
                transfer_id_map[int(transfer.id)] = new_transfer_id

            for record in sorted(records, key=lambda item: item.id):
                transfer_id = None
                if record.transfer_id is not None:
                    original_transfer_id = int(record.transfer_id)
                    if original_transfer_id not in transfer_id_map:
                        raise ValueError(
                            f"Record #{record.id} references missing transfer "
                            f"#{original_transfer_id}"
                        )
                    transfer_id = int(transfer_id_map[original_transfer_id])
                self._insert_record_row(record, transfer_id=transfer_id)

    def save(self, record: Record) -> None:
        with self._conn:
            transfer_id = int(record.transfer_id) if record.transfer_id is not None else None
            self._insert_record_row(record, transfer_id=transfer_id)

    def load_all(self) -> list[Record]:
        return self._storage.get_records()

    def list_all(self) -> list[Record]:
        return self.load_all()

    def get_by_id(self, record_id: int) -> Record:
        record_id = int(record_id)
        for record in self.load_all():
            if int(getattr(record, "id", 0)) == record_id:
                return record
        raise ValueError(f"Record not found: {record_id}")

    def replace(self, record: Record) -> None:
        record_id = int(getattr(record, "id", 0) or 0)
        if record_id <= 0:
            raise ValueError("Record id must be positive")
        if not self._conn.execute("SELECT 1 FROM records WHERE id = ?", (record_id,)).fetchone():
            raise ValueError(f"Record not found: {record_id}")
        with self._conn:
            transfer_id = int(record.transfer_id) if record.transfer_id is not None else None
            self._update_record_row(record_id, record, transfer_id=transfer_id)

    def delete_by_index(self, index: int) -> bool:
        records = self.load_all()
        if not (0 <= int(index) < len(records)):
            return False
        target = records[int(index)]
        with self._conn:
            self._conn.execute("DELETE FROM records WHERE id = ?", (int(target.id),))
        return True

    def delete_all(self) -> None:
        with self._conn:
            self._conn.execute("DELETE FROM records")
            self._reset_autoincrement("records")

    def save_initial_balance(self, balance: float) -> None:
        with self._conn:
            self._upsert_system_wallet_balance(float(balance))

    def load_initial_balance(self) -> float:
        return float(self.get_system_wallet().initial_balance)

    def save_mandatory_expense(self, expense: MandatoryExpenseRecord) -> None:
        with self._conn:
            if not self.has_system_wallet_row():
                self._upsert_system_wallet_balance(0.0)
            wallet_id = int(expense.wallet_id)
            wallet_exists = self._conn.execute(
                "SELECT 1 FROM wallets WHERE id = ?",
                (wallet_id,),
            ).fetchone()
            if wallet_exists is None:
                wallet_id = int(self.get_system_wallet().id)
            self._insert_mandatory_row(expense, wallet_id=wallet_id)

    def load_mandatory_expenses(self) -> list[MandatoryExpenseRecord]:
        return self._storage.get_mandatory_expenses()

    def get_mandatory_expense_by_id(self, expense_id: int) -> MandatoryExpenseRecord:
        expense = next(
            (item for item in self.load_mandatory_expenses() if int(item.id) == int(expense_id)),
            None,
        )
        if expense is None:
            raise ValueError(f"Mandatory expense не найден: {expense_id}")
        return expense

    def update_mandatory_expense(self, expense: MandatoryExpenseRecord) -> None:
        expense_id = int(getattr(expense, "id", 0) or 0)
        if expense_id <= 0:
            raise ValueError("id обязательного расхода должен быть положительным")
        with self._conn:
            self._conn.execute(
                """
                UPDATE mandatory_expenses
                SET wallet_id         = ?,
                    amount_original   = ?,
                    currency          = ?,
                    rate_at_operation = ?,
                    amount_kzt        = ?,
                    category          = ?,
                    description       = ?,
                    period            = ?,
                    date              = ?,
                    auto_pay          = ?
                WHERE id = ?
                """,
                (
                    int(expense.wallet_id),
                    float(expense.amount_original or 0.0),
                    str(expense.currency).upper(),
                    float(expense.rate_at_operation),
                    float(expense.amount_kzt or 0.0),
                    str(expense.category),
                    str(expense.description or ""),
                    str(expense.period),
                    str(expense.date) if expense.date else None,
                    int(bool(expense.auto_pay)),
                    expense_id,
                ),
            )

    def delete_mandatory_expense_by_index(self, index: int) -> bool:
        expenses = self.load_mandatory_expenses()
        if not (0 <= int(index) < len(expenses)):
            return False
        target = expenses[int(index)]
        with self._conn:
            self._conn.execute("DELETE FROM mandatory_expenses WHERE id = ?", (int(target.id),))
        return True

    def delete_all_mandatory_expenses(self) -> None:
        with self._conn:
            self._conn.execute("DELETE FROM mandatory_expenses")
            self._reset_autoincrement("mandatory_expenses")

    def replace_records(self, records: list[Record], initial_balance: float) -> None:
        with self._conn:
            self._upsert_system_wallet_balance(float(initial_balance))
            self._conn.execute("DELETE FROM records")
            self._reset_autoincrement("records")
            for record in sorted(records, key=lambda item: item.id):
                transfer_id = int(record.transfer_id) if record.transfer_id is not None else None
                self._insert_record_row(record, transfer_id=transfer_id)

    def replace_mandatory_expenses(self, expenses: list[MandatoryExpenseRecord]) -> None:
        with self._conn:
            self._conn.execute("DELETE FROM mandatory_expenses")
            self._reset_autoincrement("mandatory_expenses")
            for expense in sorted(expenses, key=lambda item: item.id):
                self._insert_mandatory_row(expense, wallet_id=int(expense.wallet_id))

    def replace_all_data(
        self,
        *,
        initial_balance: float = 0.0,
        wallets: list[Wallet] | None = None,
        records: list[Record],
        mandatory_expenses: list[MandatoryExpenseRecord],
        transfers: list[Transfer] | None = None,
    ) -> None:
        normalized_wallets = list(wallets or [])
        if not normalized_wallets:
            normalized_wallets = [
                Wallet(
                    id=SYSTEM_WALLET_ID,
                    name="Main wallet",
                    currency="KZT",
                    initial_balance=float(initial_balance),
                    system=True,
                    allow_negative=False,
                    is_active=True,
                )
            ]
        normalized_transfers = list(transfers or [])
        self._validate_transfer_integrity(records, normalized_transfers)

        with self._conn:
            self._conn.execute("DELETE FROM records")
            self._conn.execute("DELETE FROM mandatory_expenses")
            self._conn.execute("DELETE FROM transfers")
            self._conn.execute("DELETE FROM wallets")
            self._reset_autoincrement_many(
                ("records", "mandatory_expenses", "transfers", "wallets")
            )

            wallet_id_map: dict[int, int] = {}
            for wallet in sorted(normalized_wallets, key=lambda item: item.id):
                new_wallet_id = self._insert_wallet_row(wallet)
                wallet_id_map[int(wallet.id)] = new_wallet_id

            transfer_id_map: dict[int, int] = {}
            for transfer in sorted(normalized_transfers, key=lambda item: item.id):
                from_wallet_id = wallet_id_map.get(int(transfer.from_wallet_id))
                to_wallet_id = wallet_id_map.get(int(transfer.to_wallet_id))
                if from_wallet_id is None or to_wallet_id is None:
                    raise ValueError(f"Transfer #{transfer.id} references missing wallet")
                new_transfer_id = self._insert_transfer_row(
                    transfer,
                    from_wallet_id=from_wallet_id,
                    to_wallet_id=to_wallet_id,
                )
                transfer_id_map[int(transfer.id)] = new_transfer_id

            for record in sorted(records, key=lambda item: item.id):
                wallet_id = wallet_id_map.get(int(record.wallet_id))
                if wallet_id is None:
                    raise ValueError(f"Record #{record.id} references missing wallet")
                transfer_id = None
                if record.transfer_id is not None:
                    transfer_id = transfer_id_map.get(int(record.transfer_id))
                    if transfer_id is None:
                        raise ValueError(
                            f"Record #{record.id} references missing transfer #{record.transfer_id}"
                        )
                self._insert_record_row(record, wallet_id=wallet_id, transfer_id=transfer_id)

            for expense in sorted(mandatory_expenses, key=lambda item: item.id):
                wallet_id = wallet_id_map.get(int(expense.wallet_id))
                if wallet_id is None:
                    raise ValueError(f"Mandatory expense #{expense.id} references missing wallet")
                self._insert_mandatory_row(expense, wallet_id=wallet_id)
