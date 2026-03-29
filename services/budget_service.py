"""BudgetService - budget management and spend tracking."""

from __future__ import annotations

from datetime import date as dt_date

from domain.budget import Budget, BudgetResult, compute_pace_status
from domain.validation import parse_ymd
from infrastructure.sqlite_repository import SQLiteRecordRepository
from services.sqlite_money_sql import minor_amount_expr
from utils.money import minor_to_money, to_minor_units, to_money_float


class BudgetService:
    """Reads records and manages persisted budgets."""

    def __init__(self, repository: SQLiteRecordRepository) -> None:
        self._repo = repository

    def create_budget(
        self,
        category: str,
        start_date: str,
        end_date: str,
        limit_kzt: float,
        *,
        include_mandatory: bool = False,
    ) -> Budget:
        category = str(category or "").strip()
        if not category:
            raise ValueError("Category is required")

        start = parse_ymd(start_date)
        end = parse_ymd(end_date)
        if start > end:
            raise ValueError("start_date must be <= end_date")

        limit_value = to_money_float(limit_kzt)
        if limit_value <= 0:
            raise ValueError("Budget limit must be positive")

        start_text = start.isoformat()
        end_text = end.isoformat()
        self._check_overlap(category, start_text, end_text, exclude_id=None)

        self._repo.execute(
            """
            INSERT INTO budgets (
                category, start_date, end_date, limit_kzt, limit_kzt_minor, include_mandatory
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                category,
                start_text,
                end_text,
                limit_value,
                to_minor_units(limit_value),
                int(bool(include_mandatory)),
            ),
        )
        row = self._repo.query_one("SELECT id FROM budgets WHERE rowid = last_insert_rowid()")
        self._repo.commit()
        if row is None:
            raise RuntimeError("Failed to retrieve inserted budget id")
        return self._load_budget_by_id(int(row[0]))

    def get_budgets(self) -> list[Budget]:
        rows = self._repo.query_all(
            """
            SELECT id, category, start_date, end_date,
                   limit_kzt, limit_kzt_minor, include_mandatory
            FROM budgets
            ORDER BY start_date DESC, category ASC, id DESC
            """
        )
        return [self._row_to_budget(row) for row in rows]

    def delete_budget(self, budget_id: int) -> None:
        row = self._repo.query_one("SELECT id FROM budgets WHERE id = ?", (int(budget_id),))
        if row is None:
            raise ValueError(f"Budget not found: {budget_id}")
        self._repo.execute("DELETE FROM budgets WHERE id = ?", (int(budget_id),))
        self._repo.commit()

    def update_budget_limit(self, budget_id: int, new_limit_kzt: float) -> Budget:
        limit_value = to_money_float(new_limit_kzt)
        if limit_value <= 0:
            raise ValueError("Budget limit must be positive")
        row = self._repo.query_one("SELECT id FROM budgets WHERE id = ?", (int(budget_id),))
        if row is None:
            raise ValueError(f"Budget not found: {budget_id}")
        self._repo.execute(
            "UPDATE budgets SET limit_kzt = ?, limit_kzt_minor = ? WHERE id = ?",
            (limit_value, to_minor_units(limit_value), int(budget_id)),
        )
        self._repo.commit()
        return self._load_budget_by_id(int(budget_id))

    def replace_budgets(self, budgets: list[Budget]) -> None:
        with self._repo.transaction():
            self._repo.execute("DELETE FROM budgets")
            for budget in sorted(budgets, key=lambda item: int(item.id)):
                self._repo.execute(
                    """
                    INSERT INTO budgets (
                        id, category, start_date, end_date,
                        limit_kzt, limit_kzt_minor, include_mandatory
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        int(budget.id),
                        str(budget.category),
                        str(budget.start_date),
                        str(budget.end_date),
                        float(budget.limit_kzt),
                        int(budget.limit_kzt_minor),
                        int(bool(budget.include_mandatory)),
                    ),
                )
            self._repo.execute("DELETE FROM sqlite_sequence WHERE name = ?", ("budgets",))
            if budgets:
                max_budget_id = max(int(budget.id) for budget in budgets)
                self._repo.execute(
                    "INSERT INTO sqlite_sequence(name, seq) VALUES(?, ?)",
                    ("budgets", max_budget_id),
                )

    def get_budget_result(self, budget: Budget, today: dt_date | None = None) -> BudgetResult:
        today = today or dt_date.today()
        type_filter = (
            "type IN ('expense', 'mandatory_expense')"
            if budget.include_mandatory
            else "type = 'expense'"
        )
        row = self._repo.query_one(
            f"""
            SELECT COALESCE(SUM({minor_amount_expr("amount_kzt")}), 0)
            FROM records
            WHERE {type_filter}
              AND category = ?
              AND transfer_id IS NULL
              AND date >= ?
              AND date <= ?
            """,
            (budget.category, budget.start_date, budget.end_date),
        )
        spent_minor = int(row[0]) if row is not None else 0
        spent_kzt = minor_to_money(spent_minor)
        limit_minor = budget.limit_kzt_minor
        usage_pct = round(spent_minor / limit_minor * 100.0, 1) if limit_minor > 0 else 0.0
        time_pct = budget.time_pct(today)
        return BudgetResult(
            budget=budget,
            spent_kzt=spent_kzt,
            spent_minor=spent_minor,
            status=budget.status(today),
            pace_status=compute_pace_status(spent_minor, limit_minor, usage_pct, time_pct),
            usage_pct=usage_pct,
            time_pct=time_pct,
            remaining_kzt=to_money_float(budget.limit_kzt - spent_kzt),
        )

    def get_all_results(self, today: dt_date | None = None) -> list[BudgetResult]:
        today = today or dt_date.today()
        budgets = self.get_budgets()
        if not budgets:
            return []

        spent_minor_by_budget: dict[int, int] = {budget.id: 0 for budget in budgets}
        rows = self._repo.query_all(
            f"""
            SELECT
                b.id,
                COALESCE(SUM({minor_amount_expr("r.amount_kzt")}), 0)
            FROM budgets AS b
            LEFT JOIN records AS r
              ON r.category = b.category
             AND r.transfer_id IS NULL
             AND r.date >= b.start_date
             AND r.date <= b.end_date
             AND (
                    (b.include_mandatory = 1 AND r.type IN ('expense', 'mandatory_expense'))
                 OR (b.include_mandatory = 0 AND r.type = 'expense')
             )
            GROUP BY b.id
            """
        )
        for budget_id, spent_minor in rows:
            spent_minor_by_budget[int(budget_id)] = int(spent_minor or 0)

        results: list[BudgetResult] = []
        for budget in budgets:
            spent_minor = int(spent_minor_by_budget.get(budget.id, 0))
            spent_kzt = minor_to_money(spent_minor)
            limit_minor = budget.limit_kzt_minor
            usage_pct = round(spent_minor / limit_minor * 100.0, 1) if limit_minor > 0 else 0.0
            time_pct = budget.time_pct(today)
            results.append(
                BudgetResult(
                    budget=budget,
                    spent_kzt=spent_kzt,
                    spent_minor=spent_minor,
                    status=budget.status(today),
                    pace_status=compute_pace_status(spent_minor, limit_minor, usage_pct, time_pct),
                    usage_pct=usage_pct,
                    time_pct=time_pct,
                    remaining_kzt=to_money_float(budget.limit_kzt - spent_kzt),
                )
            )
        return results

    def _check_overlap(
        self,
        category: str,
        start_date: str,
        end_date: str,
        exclude_id: int | None,
    ) -> None:
        params: list[object] = [category, end_date, start_date]
        exclude_clause = ""
        if exclude_id is not None:
            exclude_clause = "AND id != ?"
            params.append(int(exclude_id))
        row = self._repo.query_one(
            f"""
            SELECT id, start_date, end_date
            FROM budgets
            WHERE category = ?
              AND start_date <= ?
              AND end_date >= ?
              {exclude_clause}
            LIMIT 1
            """,
            tuple(params),
        )
        if row is not None:
            raise ValueError(
                f"Budget for '{category}' already exists for overlapping period {row[1]} - {row[2]}"
            )

    def _load_budget_by_id(self, budget_id: int) -> Budget:
        row = self._repo.query_one(
            """
            SELECT id, category, start_date, end_date,
                   limit_kzt, limit_kzt_minor, include_mandatory
            FROM budgets
            WHERE id = ?
            """,
            (int(budget_id),),
        )
        if row is None:
            raise ValueError(f"Budget not found: {budget_id}")
        return self._row_to_budget(row)

    @staticmethod
    def _row_to_budget(row: tuple) -> Budget:
        return Budget(
            id=int(row[0]),
            category=str(row[1]),
            start_date=str(row[2]),
            end_date=str(row[3]),
            limit_kzt=float(row[4]),
            limit_kzt_minor=int(row[5]),
            include_mandatory=bool(row[6]),
        )
