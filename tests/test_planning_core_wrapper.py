from __future__ import annotations

import os
import sqlite3
from pathlib import Path

os.environ.setdefault("LEDGERA_ENABLE_RUST_CORE", "1")

from infrastructure.sqlite_repository import SQLiteRecordRepository
from services.planning.budget import BudgetService
from services.planning.budget import service as budget_module
from services.planning.debts import DebtService
from services.planning.debts import service as debts_module
from services.planning.distribution import DistributionService
from services.planning.distribution import service as distribution_module
from utils.finance.money import to_minor_units


def _schema_path() -> str:
    return str(Path(__file__).resolve().parents[1] / "db" / "schema.sql")


def _build_repo(tmp_path: Path, name: str = "planning_core.db") -> SQLiteRecordRepository:
    db_path = tmp_path / name
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(Path(_schema_path()).read_text(encoding="utf-8"))
        conn.execute(
            """
            INSERT INTO wallets (
                id, name, currency, initial_balance, initial_balance_minor,
                system, allow_negative, is_active
            )
            VALUES
                (1, 'Main', 'KZT', 1000, 100000, 1, 0, 1),
                (2, 'Flex', 'KZT', 0, 0, 0, 1, 1)
            """
        )
        conn.commit()
    finally:
        conn.close()
    return SQLiteRecordRepository(str(db_path), schema_path=_schema_path())


def _insert_record(
    conn: sqlite3.Connection,
    *,
    record_type: str,
    date: str,
    amount_base: float,
    category: str,
    transfer_id: int | None = None,
) -> int:
    conn.execute(
        """
        INSERT INTO records (
            type, date, wallet_id, transfer_id,
            amount_original, amount_original_minor,
            currency, rate_at_operation, rate_at_operation_text,
            amount_base, amount_base_minor, category, description, period
        )
        VALUES (?, ?, 1, ?, ?, ?, 'KZT', 1.0, '1.0', ?, ?, ?, '', ?)
        """,
        (
            record_type,
            date,
            transfer_id,
            amount_base,
            to_minor_units(amount_base),
            amount_base,
            to_minor_units(amount_base),
            category,
            "monthly" if record_type == "mandatory_expense" else None,
        ),
    )
    conn.commit()
    return int(conn.execute("SELECT last_insert_rowid()").fetchone()[0])


def test_distribution_service_rust_path_matches_python_fallback(tmp_path: Path) -> None:
    repo = _build_repo(tmp_path)
    try:
        service = DistributionService(repo)
        item = service.create_item("Needs", pct=100.0)
        service.create_subitem(item.id, "Rent", pct=100.0)
        with sqlite3.connect(repo.db_path) as conn:
            _insert_record(
                conn,
                record_type="income",
                date="2026-03-01",
                amount_base=1000.0,
                category="Salary",
            )
            _insert_record(
                conn,
                record_type="expense",
                date="2026-03-02",
                amount_base=250.0,
                category="Food",
            )
            _insert_record(
                conn,
                record_type="expense",
                date="2026-03-03",
                amount_base=100.0,
                category="Transfer",
                transfer_id=1,
            )

        rust_values = (
            service.validate(),
            service.get_net_income_for_month("2026-03"),
            service.get_available_months(),
            service.get_distribution_history("2026-03", "2026-03"),
            service.get_monthly_distribution("2026-03"),
        )

        rust_core = distribution_module._RUST_DISTRIBUTION_CORE
        distribution_module._RUST_DISTRIBUTION_CORE = None
        try:
            fallback = DistributionService(repo)
            fallback_values = (
                fallback.validate(),
                fallback.get_net_income_for_month("2026-03"),
                fallback.get_available_months(),
                fallback.get_distribution_history("2026-03", "2026-03"),
                fallback.get_monthly_distribution("2026-03"),
            )
        finally:
            distribution_module._RUST_DISTRIBUTION_CORE = rust_core

        assert rust_values == fallback_values
    finally:
        repo.close()


def _exercise_distribution_write_path(repo: SQLiteRecordRepository) -> tuple[object, ...]:
    service = DistributionService(repo)
    item = service.create_item("Needs", group_name="Core", pct=60.0)
    second = service.create_item("Savings", pct=40.0)
    item = service.update_item_name(item.id, "Essentials")
    item = service.update_item_pct(item.id, 70.0)
    service.update_item_order(second.id, -1)
    subitem = service.create_subitem(item.id, "Rent", pct=100.0)
    subitem = service.update_subitem_name(subitem.id, "Housing")
    subitem = service.update_subitem_pct(subitem.id, 80.0)
    service.update_subitem_order(subitem.id, 2)
    temporary = service.create_subitem(item.id, "Temporary", pct=20.0)
    service.delete_subitem(temporary.id)
    doomed = service.create_item("Delete me")
    service.delete_item(doomed.id)
    items, subitems_by_item = service.export_structure()
    service.replace_structure(items, subitems_by_item)

    with sqlite3.connect(repo.db_path) as conn:
        _insert_record(
            conn,
            record_type="income",
            date="2026-03-01",
            amount_base=1000.0,
            category="Salary",
        )
    frozen = service.freeze_month("2026-03")
    fixed_before = service.is_month_fixed("2026-03")
    auto_before = service.is_month_auto_fixed("2026-03")
    frozen_rows = service.get_frozen_rows("2026-03", "2026-03")
    service.unfreeze_month("2026-03")
    fixed_after = service.is_month_fixed("2026-03")
    service.replace_frozen_rows(frozen_rows)

    item_seq = repo.query_all(
        "SELECT name, seq FROM sqlite_sequence WHERE name = 'distribution_items'"
    )
    subitem_seq = repo.query_all(
        "SELECT name, seq FROM sqlite_sequence WHERE name = 'distribution_subitems'"
    )
    return (
        service.export_structure(),
        frozen,
        fixed_before,
        auto_before,
        frozen_rows,
        fixed_after,
        service.get_frozen_rows(),
        [(row["name"], int(row["seq"])) for row in item_seq],
        [(row["name"], int(row["seq"])) for row in subitem_seq],
    )


def test_distribution_write_path_rust_matches_python_fallback(tmp_path: Path) -> None:
    rust_repo = _build_repo(tmp_path, "distribution_rust_write.db")
    fallback_repo = _build_repo(tmp_path, "distribution_fallback_write.db")
    try:
        rust_values = _exercise_distribution_write_path(rust_repo)

        rust_core = distribution_module._RUST_DISTRIBUTION_CORE
        distribution_module._RUST_DISTRIBUTION_CORE = None
        try:
            fallback_values = _exercise_distribution_write_path(fallback_repo)
        finally:
            distribution_module._RUST_DISTRIBUTION_CORE = rust_core

        assert rust_values == fallback_values
    finally:
        rust_repo.close()
        fallback_repo.close()


def test_budget_service_rust_path_matches_python_fallback(tmp_path: Path) -> None:
    repo = _build_repo(tmp_path)
    try:
        with sqlite3.connect(repo.db_path) as conn:
            food_id = _insert_record(
                conn,
                record_type="expense",
                date="2026-03-05",
                amount_base=100.0,
                category="Food",
            )
            _insert_record(
                conn,
                record_type="mandatory_expense",
                date="2026-03-06",
                amount_base=50.0,
                category="Food",
            )
            conn.execute("INSERT INTO tags (id, name, color) VALUES (1, 'groceries', '')")
            conn.execute("INSERT INTO record_tags (record_id, tag_id) VALUES (?, 1)", (food_id,))
            conn.commit()

        service = BudgetService(repo)
        category_budget = service.create_budget(
            "Food",
            "2026-03-01",
            "2026-03-31",
            500.0,
            include_mandatory=True,
        )
        tag_budget = service.create_budget(
            "",
            "2026-03-01",
            "2026-03-31",
            300.0,
            scope_type="tag",
            scope_value="groceries",
        )
        rust_values = (
            service.get_budget_result(category_budget),
            service.get_budget_result(tag_budget),
            service.get_all_results(),
        )

        rust_core = budget_module._RUST_BUDGET_CORE
        budget_module._RUST_BUDGET_CORE = None
        try:
            fallback = BudgetService(repo)
            fallback_values = (
                fallback.get_budget_result(category_budget),
                fallback.get_budget_result(tag_budget),
                fallback.get_all_results(),
            )
        finally:
            budget_module._RUST_BUDGET_CORE = rust_core

        assert rust_values == fallback_values
    finally:
        repo.close()


def test_debt_service_rust_path_matches_python_fallback(tmp_path: Path) -> None:
    repo = _build_repo(tmp_path)
    try:
        service = DebtService(repo)
        debt = service.create_debt(
            contact_name="Alice",
            wallet_id=2,
            amount_base=500.0,
            created_at="2026-03-01",
        )
        service.register_payment(
            debt_id=debt.id,
            wallet_id=2,
            amount_base=200.0,
            payment_date="2026-03-05",
        )
        rust_value = service.recalculate_debt(debt.id)

        rust_core = debts_module._RUST_DEBT_CORE
        debts_module._RUST_DEBT_CORE = None
        try:
            fallback_value = DebtService(repo).recalculate_debt(debt.id)
        finally:
            debts_module._RUST_DEBT_CORE = rust_core

        assert rust_value == fallback_value
    finally:
        repo.close()
