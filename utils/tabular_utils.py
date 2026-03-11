from __future__ import annotations

from collections.abc import Iterable
from datetime import date as dt_date

from domain.records import MandatoryExpenseRecord, Record
from domain.transfers import Transfer
from utils.import_core import record_type_name


def resolve_get_rate(currency_service):
    if currency_service is None:
        from app.services import CurrencyService

        currency_service = CurrencyService()
    return currency_service.get_rate


def report_record_type_label(record: Record) -> str:
    record_type = record_type_name(record)
    if record_type == "income":
        return "Income"
    if record_type == "mandatory_expense":
        return "Mandatory Expense"
    return "Expense"


def record_export_rows(
    records: Iterable[Record],
    *,
    transfers: Iterable[Transfer] = (),
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []

    for record in records:
        if record.transfer_id is not None:
            continue
        rows.append(
            {
                "date": record.date.isoformat()
                if isinstance(record.date, dt_date)
                else record.date,
                "type": record_type_name(record),
                "wallet_id": int(getattr(record, "wallet_id", 1)),
                "category": record.category,
                "amount_original": record.amount_original,
                "currency": record.currency,
                "rate_at_operation": record.rate_at_operation,
                "amount_kzt": record.amount_kzt,
                "description": str(getattr(record, "description", "") or ""),
                "period": getattr(record, "period", "")
                if isinstance(record, MandatoryExpenseRecord)
                else "",
                "transfer_id": "",
                "from_wallet_id": "",
                "to_wallet_id": "",
            }
        )

    transfer_map = {transfer.id: transfer for transfer in transfers}
    for transfer_id in sorted(transfer_map):
        transfer = transfer_map[transfer_id]
        rows.append(
            {
                "date": transfer.date.isoformat()
                if isinstance(transfer.date, dt_date)
                else transfer.date,
                "type": "transfer",
                "wallet_id": "",
                "category": "Transfer",
                "amount_original": transfer.amount_original,
                "currency": transfer.currency,
                "rate_at_operation": transfer.rate_at_operation,
                "amount_kzt": transfer.amount_kzt,
                "description": transfer.description,
                "period": "",
                "transfer_id": transfer.id,
                "from_wallet_id": transfer.from_wallet_id,
                "to_wallet_id": transfer.to_wallet_id,
            }
        )
    return rows


def mandatory_expense_export_rows(
    expenses: Iterable[MandatoryExpenseRecord],
) -> list[dict[str, object]]:
    return [
        {
            "type": "mandatory_expense",
            "date": expense.date.isoformat()
            if isinstance(expense.date, dt_date)
            else expense.date,
            "category": expense.category,
            "amount_original": expense.amount_original,
            "currency": expense.currency,
            "rate_at_operation": expense.rate_at_operation,
            "amount_kzt": expense.amount_kzt,
            "description": expense.description,
            "period": expense.period,
        }
        for expense in expenses
    ]
