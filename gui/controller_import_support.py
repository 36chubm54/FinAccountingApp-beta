from __future__ import annotations

import logging
import sqlite3
from collections import defaultdict, deque
from collections.abc import Callable
from dataclasses import replace
from typing import cast

from domain.debt import Debt, DebtPayment
from domain.records import ExpenseRecord, MandatoryExpenseRecord, Record
from domain.transfers import Transfer
from domain.wallets import Wallet
from infrastructure.repositories import RecordRepository
from utils.money import to_minor_units


def run_import_transaction(repository: RecordRepository, operation, logger: logging.Logger):
    sqlite_conn = getattr(repository, "_conn", None)
    sqlite_snapshot: sqlite3.Connection | None = None
    if isinstance(sqlite_conn, sqlite3.Connection):
        sqlite_snapshot = sqlite3.connect(":memory:")
        sqlite_conn.backup(sqlite_snapshot)
        try:
            return operation()
        except Exception as import_error:
            logger.exception("Import failed, restoring SQLite snapshot")
            try:
                sqlite_conn.rollback()
                sqlite_snapshot.backup(sqlite_conn)
                sqlite_conn.commit()
            except Exception:
                logger.exception("SQLite snapshot restore failed after import error")
            raise import_error
        finally:
            sqlite_snapshot.close()

    wallets_snapshot = repository.load_wallets()
    records_snapshot = repository.load_all()
    mandatory_snapshot = repository.load_mandatory_expenses()
    transfers_snapshot = repository.load_transfers()
    debts_snapshot = None
    debt_payments_snapshot = None
    load_debts = cast(Callable[[], list[Debt]] | None, getattr(repository, "load_debts", None))
    load_debt_payments = cast(
        Callable[[], list[DebtPayment]] | None,
        getattr(repository, "load_debt_payments", None),
    )
    if callable(load_debts) and callable(load_debt_payments):
        try:
            debts_snapshot = list(load_debts())
            debt_payments_snapshot = list(load_debt_payments())
        except TypeError:
            debts_snapshot = None
            debt_payments_snapshot = None
    try:
        return operation()
    except Exception as import_error:
        logger.exception("Import failed, rolling back repository state")
        try:
            if debts_snapshot is not None and debt_payments_snapshot is not None:
                repository.replace_all_data(
                    wallets=wallets_snapshot,
                    records=records_snapshot,
                    mandatory_expenses=mandatory_snapshot,
                    transfers=transfers_snapshot,
                    debts=debts_snapshot,
                    debt_payments=debt_payments_snapshot,
                )
            else:
                repository.replace_all_data(
                    wallets=wallets_snapshot,
                    records=records_snapshot,
                    mandatory_expenses=mandatory_snapshot,
                    transfers=transfers_snapshot,
                )
        except Exception:
            logger.exception("Rollback failed after import error")
        raise import_error


def normalize_operation_ids_for_import(repository: RecordRepository) -> None:
    records = list(repository.load_all())
    transfers = sorted(repository.load_transfers(), key=lambda item: (str(item.date), int(item.id)))
    transfer_id_map = {int(item.id): index for index, item in enumerate(transfers, start=1)}
    normalized_transfers: list[Transfer] = [
        replace(transfer, id=transfer_id_map[int(transfer.id)]) for transfer in transfers
    ]
    normalized_records: list[Record] = []
    record_id_map: dict[int, int] = {}
    for index, record in enumerate(records, start=1):
        mapped_transfer_id = None
        if record.transfer_id is not None:
            mapped_transfer_id = transfer_id_map.get(int(record.transfer_id))
        record_id_map[int(record.id)] = index
        normalized_records.append(replace(record, id=index, transfer_id=mapped_transfer_id))

    load_debts = cast(Callable[[], list[Debt]] | None, getattr(repository, "load_debts", None))
    load_debt_payments = cast(
        Callable[[], list[DebtPayment]] | None,
        getattr(repository, "load_debt_payments", None),
    )
    if callable(load_debts) and callable(load_debt_payments):
        debt_payments: list[DebtPayment] | None = None
        debts: list[Debt] | None = None
        wallets: list[Wallet] | None = None
        mandatory_expenses: list[MandatoryExpenseRecord] = []
        try:
            debt_payments = list(load_debt_payments())
            debts = list(load_debts())
            wallets = list(repository.load_wallets())
            mandatory_expenses = list(repository.load_mandatory_expenses())
        except TypeError:
            debt_payments = None
        if debt_payments is None or debts is None:
            repository.replace_records_and_transfers(normalized_records, normalized_transfers)
            return

        debt_kind_by_id = {int(debt.id): debt.kind for debt in debts}
        payment_record_candidates: dict[tuple[int, str, int, str, str], deque[int]] = defaultdict(
            deque
        )
        for record in records:
            related_debt_id = getattr(record, "related_debt_id", None)
            if related_debt_id is None:
                continue
            record_type = "expense" if isinstance(record, ExpenseRecord) else "income"
            payment_record_candidates[
                (
                    int(related_debt_id),
                    str(record.date),
                    to_minor_units(float(record.amount_kzt or 0.0)),
                    record_type,
                    str(record.category or ""),
                )
            ].append(int(record.id))

        normalized_debt_payments: list[DebtPayment] = []
        for payment in debt_payments:
            mapped_record_id = None
            if payment.record_id is not None:
                mapped_record_id = record_id_map.get(int(payment.record_id))
            if mapped_record_id is None:
                debt_kind = debt_kind_by_id.get(int(payment.debt_id))
                if debt_kind is not None and not payment.is_write_off:
                    expected_record_type = "expense" if debt_kind.value == "debt" else "income"
                    expected_category = (
                        "Debt payment" if debt_kind.value == "debt" else "Loan payment"
                    )
                    original_record_id = None
                    candidates = payment_record_candidates.get(
                        (
                            int(payment.debt_id),
                            str(payment.payment_date),
                            int(payment.principal_paid_minor),
                            expected_record_type,
                            expected_category,
                        )
                    )
                    if candidates:
                        original_record_id = candidates.popleft()
                    if original_record_id is not None:
                        mapped_record_id = record_id_map.get(original_record_id)
            normalized_debt_payments.append(replace(payment, record_id=mapped_record_id))
        repository.replace_all_data(
            wallets=wallets,
            records=normalized_records,
            mandatory_expenses=mandatory_expenses,
            transfers=normalized_transfers,
            debts=debts,
            debt_payments=normalized_debt_payments,
        )
        return

    repository.replace_records_and_transfers(normalized_records, normalized_transfers)
