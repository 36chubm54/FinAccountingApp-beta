"""MetricsService computes financial metrics from records on demand."""

from __future__ import annotations

from dataclasses import dataclass

from infrastructure.sqlite_repository import SQLiteRecordRepository


@dataclass(frozen=True)
class CategorySpend:
    """Aggregated spend or income for a single category."""

    category: str
    total_kzt: float
    record_count: int


@dataclass(frozen=True)
class MonthlySummary:
    """Income, expenses, cashflow, and savings rate for a single calendar month."""

    month: str  # "YYYY-MM"
    income: float
    expenses: float
    cashflow: float  # income - expenses
    savings_rate: float  # cashflow / income * 100, or 0.0 if income == 0


class MetricsService:
    """
    MetricsService computes financial metrics from records on demand.

    Read-only analytical service. All metrics are derived live from
    the records table via SQL aggregates. Never writes to the database.

    Example usage:
        repo = SQLiteRecordRepository("finance.db")
        svc = MetricsService(repo)
        rate = svc.get_savings_rate("2026-01-01", "2026-01-31")
        # 23.4  (percent)
    """

    def __init__(self, repository: SQLiteRecordRepository) -> None:
        self._repo = repository

    def get_savings_rate(self, start_date: str, end_date: str) -> float:
        """
        Savings rate (%) for the date range [start_date, end_date].

        savings_rate = (income - expenses) / income * 100
        Returns 0.0 if income is zero (no division by zero).
        Transfer records excluded (transfer_id IS NULL).
        """
        income = self._sum_income(start_date, end_date)
        expenses = self._sum_expenses(start_date, end_date)
        if income <= 0.0:
            return 0.0
        return round((income - expenses) / income * 100, 2)

    def get_burn_rate(self, start_date: str, end_date: str) -> float:
        """
        Average daily expense (KZT) for the date range [start_date, end_date].

        burn_rate = total_expenses / number_of_days_in_range
        Transfer records excluded (transfer_id IS NULL).
        Returns 0.0 if range is empty.
        """
        from domain.validation import parse_ymd

        d_start = parse_ymd(start_date)
        d_end = parse_ymd(end_date)
        days = (d_end - d_start).days + 1
        if days <= 0:
            return 0.0
        expenses = self._sum_expenses(start_date, end_date)
        return round(expenses / days, 2)

    def get_spending_by_category(
        self,
        start_date: str,
        end_date: str,
        *,
        limit: int | None = None,
    ) -> list[CategorySpend]:
        """
        Total expenses per category, sorted by total descending.

        Includes type IN ('expense', 'mandatory_expense').
        Excludes Transfer records (transfer_id IS NULL).
        Optional limit truncates the result list.
        """
        limit_clause = f"LIMIT {int(limit)}" if limit is not None else ""
        rows = self._repo.query_all(
            f"""
            SELECT
                category,
                COALESCE(SUM(amount_kzt), 0.0) AS total_kzt,
                COUNT(*)                        AS record_count
            FROM records
            WHERE type IN ('expense', 'mandatory_expense')
              AND transfer_id IS NULL
              AND date >= ? AND date <= ?
            GROUP BY category
            ORDER BY total_kzt DESC
            {limit_clause}
            """,
            (str(start_date), str(end_date)),
        )
        return [
            CategorySpend(
                category=str(row[0]),
                total_kzt=round(float(row[1]), 2),
                record_count=int(row[2]),
            )
            for row in rows
        ]

    def get_income_by_category(
        self,
        start_date: str,
        end_date: str,
        *,
        limit: int | None = None,
    ) -> list[CategorySpend]:
        """
        Total income per category, sorted by total descending.

        Excludes Transfer records (transfer_id IS NULL).
        Optional limit truncates the result list.
        """
        limit_clause = f"LIMIT {int(limit)}" if limit is not None else ""
        rows = self._repo.query_all(
            f"""
            SELECT
                category,
                COALESCE(SUM(amount_kzt), 0.0) AS total_kzt,
                COUNT(*)                        AS record_count
            FROM records
            WHERE type = 'income'
              AND transfer_id IS NULL
              AND date >= ? AND date <= ?
            GROUP BY category
            ORDER BY total_kzt DESC
            {limit_clause}
            """,
            (str(start_date), str(end_date)),
        )
        return [
            CategorySpend(
                category=str(row[0]),
                total_kzt=round(float(row[1]), 2),
                record_count=int(row[2]),
            )
            for row in rows
        ]

    def get_top_expense_categories(
        self,
        start_date: str,
        end_date: str,
        *,
        top_n: int = 5,
    ) -> list[CategorySpend]:
        """
        Top N expense categories by total spend, descending.

        Convenience wrapper around get_spending_by_category with a fixed limit.
        """
        return self.get_spending_by_category(start_date, end_date, limit=top_n)

    def get_monthly_summary(
        self,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> list[MonthlySummary]:
        """
        Per-month income, expenses, cashflow, and savings rate.

        Transfer records excluded (transfer_id IS NULL).
        Optional date range filter.
        Returns list sorted by month ascending.
        """
        params: list[str] = []
        date_filter = "transfer_id IS NULL"
        if start_date is not None:
            date_filter += " AND date >= ?"
            params.append(str(start_date))
        if end_date is not None:
            date_filter += " AND date <= ?"
            params.append(str(end_date))

        rows = self._repo.query_all(
            f"""
            SELECT
                strftime('%Y-%m', date) AS month,
                COALESCE(SUM(CASE type WHEN 'income' THEN amount_kzt ELSE 0 END), 0.0)
                    AS income,
                COALESCE(SUM(CASE WHEN type IN ('expense', 'mandatory_expense')
                               THEN amount_kzt ELSE 0 END), 0.0)
                    AS expenses
            FROM records
            WHERE {date_filter}
            GROUP BY strftime('%Y-%m', date)
            ORDER BY month
            """,
            tuple(params),
        )
        result: list[MonthlySummary] = []
        for row in rows:
            income = round(float(row[1]), 2)
            expenses = round(float(row[2]), 2)
            cashflow = round(income - expenses, 2)
            savings_rate = round(cashflow / income * 100, 2) if income > 0 else 0.0
            result.append(
                MonthlySummary(
                    month=str(row[0]),
                    income=income,
                    expenses=expenses,
                    cashflow=cashflow,
                    savings_rate=savings_rate,
                )
            )
        return result

    def _sum_income(self, start_date: str, end_date: str) -> float:
        """Total income (KZT) in [start_date, end_date], transfers excluded."""
        row = self._repo.query_one(
            """
            SELECT COALESCE(SUM(amount_kzt), 0.0)
            FROM records
            WHERE type = 'income'
              AND transfer_id IS NULL
              AND date >= ? AND date <= ?
            """,
            (str(start_date), str(end_date)),
        )
        return float(row[0]) if row else 0.0

    def _sum_expenses(self, start_date: str, end_date: str) -> float:
        """Total expenses (KZT) in [start_date, end_date], transfers excluded."""
        row = self._repo.query_one(
            """
            SELECT COALESCE(SUM(amount_kzt), 0.0)
            FROM records
            WHERE type IN ('expense', 'mandatory_expense')
              AND transfer_id IS NULL
              AND date >= ? AND date <= ?
            """,
            (str(start_date), str(end_date)),
        )
        return float(row[0]) if row else 0.0
