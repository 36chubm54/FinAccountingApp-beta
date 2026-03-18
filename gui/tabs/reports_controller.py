from __future__ import annotations

from datetime import date

from domain.reports import Report
from domain.validation import parse_ymd
from gui.controllers import FinancialController
from services.report_service import (
    ReportFilters,
    ReportsResult,
    ReportSummary,
    build_monthly_rows,
    build_operations_rows,
    extract_categories,
)


class ReportsController:
    def __init__(self, controller: FinancialController, currency_service) -> None:
        self._controller = controller
        self._currency = currency_service

    def load_active_wallets(self):
        return self._controller.load_active_wallets()

    def generate(self, filters: ReportFilters) -> ReportsResult:
        report = self._controller.generate_report_for_wallet(filters.wallet_id)
        report = self._apply_filters(report, filters)

        operations = build_operations_rows(report)
        categories = extract_categories(operations)

        summary_year, summary_up_to_month = _infer_summary_year_month(filters.period_start)
        monthly = build_monthly_rows(report, year=summary_year, up_to_month=summary_up_to_month)

        summary = ReportSummary(
            net_worth_fixed=float(self._controller.net_worth_fixed()),
            net_worth_current=float(self._controller.net_worth_current()),
            initial_balance=float(report.initial_balance),
            records_total_fixed=float(report.net_profit_fixed()),
            final_balance_fixed=float(report.total_fixed()),
            final_balance_current=float(report.total_current(self._currency)),
            fx_difference=float(report.fx_difference(self._currency)),
            records_count=len(report.display_records()),
            balance_label=str(report.balance_label),
        )

        return ReportsResult(
            report=report,
            filters=filters,
            summary=summary,
            operations=operations,
            monthly=monthly,
            categories=categories,
        )

    @staticmethod
    def _apply_filters(report: Report, filters: ReportFilters) -> Report:
        if filters.period_start:
            period_end = filters.period_end or date.today().isoformat()
            report = report.filter_by_period_range(filters.period_start, period_end)
        elif filters.period_end:
            raise ValueError("Period start is required when period end is provided.")

        if filters.category:
            report = report.filter_by_category(filters.category)

        return report


def _infer_summary_year_month(period_start: str) -> tuple[int | None, int | None]:
    period_start = (period_start or "").strip()
    if not period_start:
        return None, None
    try:
        parts = period_start.split("-")
        if parts and parts[0].isdigit():
            year = int(parts[0])
        else:
            return None, None
        month = None
        if len(parts) > 1 and parts[1].isdigit():
            month = int(parts[1])
        # Validate year/month via parse_ymd when possible (day/month ranges).
        if len(parts) == 1:
            parse_ymd(f"{year}-01-01")
        elif len(parts) == 2 and month is not None:
            parse_ymd(f"{year}-{month:02d}-01")
        return year, month
    except Exception:
        return None, None
