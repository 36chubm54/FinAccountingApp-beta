from collections.abc import Iterable
from datetime import date as dt_date

from prettytable import PrettyTable

from .records import IncomeRecord, MandatoryExpenseRecord, Record
from .validation import parse_report_period_end, parse_report_period_start, parse_ymd


class Report:
    def __init__(
        self,
        records: Iterable[Record],
        initial_balance: float = 0.0,
        wallet_id: int | None = 1,
        balance_label: str = "Initial balance",
        opening_start_date: str | None = None,
        period_start_date: str | None = None,
        period_end_date: str | None = None,
    ):
        if wallet_id is None:
            self._records = list(records)
        else:
            self._records = [record for record in records if record.wallet_id == wallet_id]
        self._wallet_id = wallet_id
        self._initial_balance = initial_balance
        self._balance_label = balance_label
        self._opening_start_date = opening_start_date
        self._period_start_date = period_start_date
        self._period_end_date = period_end_date

    def total_fixed(self) -> float:
        """Accounting total by operation-time rates."""
        return self._initial_balance + sum(r.signed_amount_kzt() for r in self._profit_records())

    def total(self) -> float:
        """Backward-compatible alias."""
        return self.total_fixed()

    def total_current(self, currency_service) -> float:
        total = self._initial_balance
        for record in self._profit_records():
            converted = float(currency_service.convert(record.amount_original, record.currency))
            sign = 1.0 if record.signed_amount_kzt() >= 0 else -1.0
            total += sign * abs(converted)
        return total

    def fx_difference(self, currency_service) -> float:
        return self.total_current(currency_service) - self.total_fixed()

    def filter_by_period(self, prefix: str) -> "Report":
        start_date = parse_report_period_start(prefix)
        end_date = parse_report_period_end(prefix)
        start = parse_ymd(start_date)
        end = parse_ymd(end_date)
        filtered: list[Record] = []
        for record in self._records:
            record_date = self._record_date(record)
            if record_date is not None and start <= record_date <= end:
                filtered.append(record)
        return Report(
            filtered,
            self.opening_balance(start_date),
            wallet_id=self._wallet_id,
            balance_label="Opening balance",
            opening_start_date=start_date,
            period_start_date=start_date,
            period_end_date=end_date,
        )

    def filter_by_period_range(self, start_prefix: str, end_prefix: str | None = None) -> "Report":
        start_date = parse_report_period_start(start_prefix)
        if end_prefix:
            end_date = parse_report_period_end(end_prefix)
        else:
            end_date = dt_date.today().isoformat()
        if end_date < start_date:
            raise ValueError("Period end date cannot be earlier than period start date")
        start = parse_ymd(start_date)
        end = parse_ymd(end_date)
        filtered: list[Record] = []
        for record in self._records:
            record_date = self._record_date(record)
            if record_date is not None and start <= record_date <= end:
                filtered.append(record)
        return Report(
            filtered,
            self.opening_balance(start_date),
            wallet_id=self._wallet_id,
            balance_label="Opening balance",
            opening_start_date=start_date,
            period_start_date=start_date,
            period_end_date=end_date,
        )

    def filter_by_category(self, category: str) -> "Report":
        filtered = [r for r in self._records if r.category == category]
        return Report(
            filtered,
            0.0,
            wallet_id=self._wallet_id,
            balance_label=self._balance_label,
            opening_start_date=self._opening_start_date,
            period_start_date=self._period_start_date,
            period_end_date=self._period_end_date,
        )

    def grouped_by_category(self) -> dict[str, "Report"]:
        groups: dict[str, list[Record]] = {}
        for record in self._display_records():
            if record.category not in groups:
                groups[record.category] = []
            groups[record.category].append(record)
        return {cat: Report(recs, 0.0, wallet_id=None) for cat, recs in groups.items()}

    def sorted_by_date(self) -> "Report":
        return Report(
            sorted(self._records, key=self._sort_key),
            self._initial_balance,
            wallet_id=self._wallet_id,
            balance_label=self._balance_label,
            opening_start_date=self._opening_start_date,
            period_start_date=self._period_start_date,
            period_end_date=self._period_end_date,
        )

    def records(self) -> list[Record]:
        return list(self._records)

    @property
    def initial_balance(self) -> float:
        return self._initial_balance

    @property
    def balance_label(self) -> str:
        return self._balance_label

    @property
    def opening_start_date(self) -> str | None:
        return self._opening_start_date

    @property
    def is_opening_balance(self) -> bool:
        return self._opening_start_date is not None

    @property
    def period_start_date(self) -> str | None:
        return self._period_start_date

    @property
    def period_end_date(self) -> str | None:
        return self._period_end_date

    @property
    def statement_title(self) -> str:
        if self._period_start_date and self._period_end_date:
            return f"Transaction statement ({self._period_start_date} - {self._period_end_date})"
        return "Transaction statement"

    def opening_balance(self, start_date: str | dt_date) -> float:
        start = parse_ymd(start_date)
        total = self._initial_balance
        for record in self._profit_records():
            record_date = self._record_date(record)
            if record_date is not None and record_date < start:
                total += record.signed_amount()
        return total

    def net_profit_fixed(self) -> float:
        return sum(r.signed_amount_kzt() for r in self._profit_records())

    @staticmethod
    def _record_date(record: Record) -> dt_date | None:
        if not record.date:
            return None
        if isinstance(record.date, dt_date):
            return record.date
        return parse_ymd(record.date)

    @staticmethod
    def _parse_year_month(date_str: str | dt_date) -> tuple[int, int] | None:
        try:
            if not date_str:
                return None
            parsed = parse_ymd(date_str)
            return parsed.year, parsed.month
        except Exception:
            return None

    def _year_months(self) -> list[tuple[int, int]]:
        year_months: list[tuple[int, int]] = []
        for record in self._records:
            parsed = self._parse_year_month(record.date)
            if parsed:
                year_months.append(parsed)
        return year_months

    def monthly_income_expense_rows(
        self, year: int | None = None, up_to_month: int | None = None
    ) -> tuple[int, list[tuple[str, float, float]]]:
        year_months = self._year_months()
        today = dt_date.today()

        if year is None:
            if year_months:
                year, _ = max(year_months)
            else:
                year, _ = today.year, today.month

        if up_to_month is None:
            months_in_year = [m for y, m in year_months if y == year]
            if months_in_year:
                up_to_month = max(months_in_year)
            else:
                up_to_month = today.month if year == today.year else 12

        up_to_month = max(1, min(12, up_to_month))

        aggregates: dict[tuple[int, int], tuple[float, float]] = {}
        for record in self._display_records():
            parsed = self._parse_year_month(record.date)
            if not parsed:
                continue
            rec_year, rec_month = parsed
            if rec_year != year or not (1 <= rec_month <= up_to_month):
                continue
            income_total, expense_total = aggregates.get((rec_year, rec_month), (0.0, 0.0))
            if isinstance(record, IncomeRecord):
                income_total += record.amount
            else:
                expense_total += abs(record.amount)
            aggregates[(rec_year, rec_month)] = (income_total, expense_total)

        rows: list[tuple[str, float, float]] = []
        for month in range(1, up_to_month + 1):
            income_total, expense_total = aggregates.get((year, month), (0.0, 0.0))
            rows.append((f"{year}-{month:02d}", income_total, expense_total))

        return year, rows

    def monthly_income_expense_table(
        self, year: int | None = None, up_to_month: int | None = None
    ) -> str:
        year, rows = self.monthly_income_expense_rows(year, up_to_month)
        table = PrettyTable()
        table.field_names = ["Month", "Income (KZT)", "Expense (KZT)"]

        total_income = 0.0
        total_expense = 0.0
        for month_label, income, expense in rows:
            total_income += income
            total_expense += expense
            table.add_row([month_label, f"{income:.2f}", f"{expense:.2f}"])

        table.add_row(["TOTAL", f"{total_income:.2f}", f"{total_expense:.2f}"], divider=True)
        return str(table)

    def as_table(self, summary_mode: str = "full") -> str:
        table = PrettyTable()
        table.field_names = ["Date", "Type", "Category", "Amount (KZT)"]

        if self._initial_balance != 0:
            balance_str = (
                f"{self._initial_balance:.2f}"
                if self._initial_balance >= 0
                else f"({abs(self._initial_balance):.2f})"
            )
            table.add_row(["", self._balance_label, "", balance_str], divider=True)

        sorted_records = sorted(self._display_records(), key=self._sort_key)

        for record in sorted_records:
            if isinstance(record, IncomeRecord):
                record_type = "Income"
            elif isinstance(record, MandatoryExpenseRecord):
                record_type = "Mandatory Expense"
            else:
                record_type = "Expense"
            amount_value = record.amount
            amount_str = (
                f"{amount_value:.2f}" if amount_value >= 0 else f"({abs(amount_value):.2f})"
            )
            display_date = (
                record.date.isoformat() if isinstance(record.date, dt_date) else record.date
            )
            table.add_row([display_date, record_type, record.category, amount_str])

        records_total = self.net_profit_fixed()
        records_total_str = (
            f"{records_total:.2f}" if records_total >= 0 else f"({abs(records_total):.2f})"
        )
        final_balance = self.total_fixed()
        final_balance_str = (
            f"{final_balance:.2f}" if final_balance >= 0 else f"({abs(final_balance):.2f})"
        )

        if summary_mode == "total_only":
            table.add_row(["SUBTOTAL", "", "", final_balance_str], divider=True)
        else:
            table.add_row(["SUBTOTAL", "", "", records_total_str], divider=True)
            table.add_row(["FINAL BALANCE", "", "", final_balance_str], divider=True)

        return str(table)

    def to_csv(self, filepath: str) -> None:
        from utils.csv_utils import report_to_csv

        report_to_csv(self, filepath)

    @staticmethod
    def from_csv(filepath: str) -> "Report":
        from domain.import_policy import ImportPolicy
        from utils.csv_utils import import_records_from_csv

        records, initial_balance, _ = import_records_from_csv(filepath, ImportPolicy.LEGACY)
        return Report(records, initial_balance)

    @staticmethod
    def _sort_key(record: Record) -> tuple[int, dt_date]:
        parsed = Report._record_date(record)
        if parsed is None:
            return (1, dt_date.max)
        return (0, parsed)

    def _profit_records(self) -> list[Record]:
        if self._wallet_id is not None:
            return list(self._records)
        return [record for record in self._records if record.transfer_id is None]

    def _display_records(self) -> list[Record]:
        return self._profit_records()
