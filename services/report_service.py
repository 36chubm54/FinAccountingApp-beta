from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date as dt_date

from domain.records import IncomeRecord, MandatoryExpenseRecord, Record
from domain.reports import Report


@dataclass(frozen=True, slots=True)
class ReportFilters:
    wallet_id: int | None
    period_start: str
    period_end: str
    category: str
    totals_mode: str  # "fixed" | "current"


@dataclass(frozen=True, slots=True)
class ReportSummary:
    net_worth_fixed: float
    net_worth_current: float
    initial_balance: float
    records_total_fixed: float
    final_balance_fixed: float
    final_balance_current: float
    fx_difference: float
    records_count: int
    balance_label: str


@dataclass(frozen=True, slots=True)
class ReportOperationRow:
    date: str
    type_label: str
    kind: str
    category: str
    amount_kzt: float


@dataclass(frozen=True, slots=True)
class CategoryGroupRow:
    category: str
    operations_count: int
    total_kzt: float


@dataclass(frozen=True, slots=True)
class MonthlySummaryRow:
    month: str
    income: float
    expense: float


@dataclass(frozen=True, slots=True)
class ReportsResult:
    report: Report
    filters: ReportFilters
    summary: ReportSummary
    operations: list[ReportOperationRow]
    monthly: list[MonthlySummaryRow]
    categories: list[str]


def report_record_type_label(record: Record) -> str:
    if isinstance(record, IncomeRecord):
        return "Income"
    if isinstance(record, MandatoryExpenseRecord):
        return "Mandatory Expense"
    return "Expense"


def report_record_kind(record: Record) -> str:
    if getattr(record, "transfer_id", None) is not None:
        return "transfer"
    if isinstance(record, IncomeRecord):
        return "income"
    if isinstance(record, MandatoryExpenseRecord):
        return "mandatory"
    return "expense"


def _display_date(value: str | dt_date) -> str:
    return value.isoformat() if isinstance(value, dt_date) else str(value or "")


def build_operations_rows(report: Report) -> list[ReportOperationRow]:
    rows: list[ReportOperationRow] = []
    for record in report.sorted_display_records():
        rows.append(
            ReportOperationRow(
                date=_display_date(record.date),
                type_label=report_record_type_label(record),
                kind=report_record_kind(record),
                category=str(record.category or ""),
                amount_kzt=float(record.signed_amount_kzt()),
            )
        )
    return rows


def build_category_group_rows(rows: Iterable[ReportOperationRow]) -> list[CategoryGroupRow]:
    totals_by_category: dict[str, float] = {}
    counts_by_category: dict[str, int] = {}
    for row in rows:
        key = str(row.category or "").strip() or "<Empty>"
        totals_by_category[key] = float(totals_by_category.get(key, 0.0)) + float(row.amount_kzt)
        counts_by_category[key] = int(counts_by_category.get(key, 0)) + 1
    return [
        CategoryGroupRow(
            category=category,
            operations_count=int(counts_by_category.get(category, 0)),
            total_kzt=float(totals_by_category[category]),
        )
        for category in sorted(totals_by_category, key=lambda value: value.casefold())
    ]


def build_monthly_rows(
    report: Report, *, year: int | None = None, up_to_month: int | None = None
) -> list[MonthlySummaryRow]:
    _, rows = report.monthly_income_expense_rows(year=year, up_to_month=up_to_month)
    return [MonthlySummaryRow(month=m, income=float(i), expense=float(e)) for m, i, e in rows]


def extract_categories(rows: Iterable[ReportOperationRow]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for row in rows:
        key = str(row.category or "").strip()
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(key)
    out.sort(key=lambda s: s.casefold())
    return out


#
# NOTE:
# CSV report export is implemented in `utils/csv_utils.report_to_csv(report, filepath)`
# to keep report read/write format consistent with legacy imports.
#
