import os
import sqlite3
from pathlib import Path
from typing import Protocol, cast

import ledgera_core as _ledgera_core
import pytest


class _LedgeraCoreModule(Protocol):
    def build_rate(self, amount_original: object, amount_base: object, currency: str) -> float: ...

    def convert_amount(self, amount: float, rate: float) -> float: ...

    def calculate_daily_burn(self, total_spent: float, days_passed: int) -> float: ...

    def currency_default_rates_for_base(
        self, base_currency: str, rates: dict[str, float]
    ) -> dict[str, float]: ...

    def currency_rate_for(
        self, currency: str, base_currency: str, rates: dict[str, float]
    ) -> float: ...

    def currency_resolve_provider_order(
        self,
        base_currency: str,
        provider_mode: str,
        primary_provider: str,
        fallback_provider: str,
        commercial_fallback_provider: str,
        enable_cbr: bool,
        provider_order: list[str] | None = None,
    ) -> list[str]: ...

    def budget_spent_minor(
        self,
        db_path: str,
        scope_type: str,
        scope_value: str,
        start_date: str,
        end_date: str,
        include_mandatory: bool,
    ) -> int: ...

    def budget_create(
        self,
        db_path: str,
        category: str,
        scope_type: str,
        scope_value: str,
        start_date: str,
        end_date: str,
        limit_base: float,
        limit_base_minor: int,
        include_mandatory: bool,
    ) -> dict[str, object]: ...

    def budget_delete(self, db_path: str, budget_id: int) -> None: ...

    def budget_replace_rows(
        self, db_path: str, rows: list[tuple[int, str, str, str, float, int, bool, str, str]]
    ) -> None: ...

    def budget_rows(self, db_path: str) -> list[dict[str, object]]: ...

    def budget_update_limit(
        self, db_path: str, budget_id: int, limit_base: float, limit_base_minor: int
    ) -> dict[str, object]: ...

    def debt_recalculate_payload(self, db_path: str, debt_id: int) -> dict[str, object]: ...

    def debt_create_obligation(
        self,
        db_path: str,
        debt_payload: dict[str, object],
        open_record_payload: dict[str, object],
    ) -> dict[str, object]: ...

    def debt_delete(self, db_path: str, debt_id: int) -> None: ...

    def debt_delete_payment(
        self, db_path: str, payment_id: int, delete_linked_record: bool
    ) -> dict[str, object]: ...

    def debt_payment_rows(
        self, db_path: str, debt_id: int | None = None
    ) -> list[dict[str, object]]: ...

    def debt_register_payment(
        self,
        db_path: str,
        debt_id: int,
        payment_payload: dict[str, object],
        payment_record_payload: dict[str, object] | None = None,
    ) -> dict[str, object]: ...

    def debt_replace_rows(
        self, db_path: str, debts: list[dict[str, object]], payments: list[dict[str, object]]
    ) -> None: ...

    def debt_rows(self, db_path: str) -> list[dict[str, object]]: ...

    def debt_validate_payment_amount(
        self, remaining_amount_minor: int, payment_amount_minor: int
    ) -> int: ...

    def distribution_available_months(self, db_path: str) -> list[str]: ...

    def distribution_create_item(
        self, db_path: str, name: str, group_name: str, sort_order: int, pct: float, pct_minor: int
    ) -> dict[str, object]: ...

    def distribution_monthly_payload(
        self, db_path: str, month: str, start_date: str, end_date: str
    ) -> dict[str, object]: ...

    def distribution_validate_structure(self, db_path: str) -> list[dict[str, object]]: ...

    def metrics_tag_coverage(
        self, db_path: str, start_date: str, end_date: str
    ) -> dict[str, object]: ...

    def metrics_period_snapshot(
        self,
        db_path: str,
        start_date: str,
        end_date: str,
        days: int,
        category_limit: int | None = None,
        tag_limit: int | None = None,
    ) -> dict[str, object]: ...

    def metrics_period_snapshot_compact(
        self,
        db_path: str,
        start_date: str,
        end_date: str,
        days: int,
        category_limit: int | None = None,
        tag_limit: int | None = None,
    ) -> tuple[object, ...]: ...

    def metrics_refresh_snapshot_compact(
        self,
        db_path: str,
        start_date: str,
        end_date: str,
        days: int,
        category_limit: int | None = None,
        tag_limit: int | None = None,
    ) -> tuple[object, ...]: ...

    def minor_to_money(self, value: object) -> float: ...

    def money_diff_text(self, left: object, right: object) -> str: ...

    def money_abs(self, value: object) -> float: ...

    def quantize_money_text(self, value: object) -> str: ...

    def quantize_rate_text(self, value: object) -> str: ...

    def rate_diff_text(self, left: object, right: object) -> str: ...

    def rate_to_text(self, value: object) -> str: ...

    def to_minor_units(self, value: object) -> int: ...

    def to_money_float(self, value: object) -> float: ...

    def to_rate_float(self, value: object) -> float: ...

    def storage_clear_read_cache(self) -> None: ...

    def sync_discover_peers(
        self, timeout_ms: int, discovery_port: int = 37639
    ) -> list[dict[str, object]]: ...

    def sync_push_once(
        self, config: dict[str, object], peer_host: str, peer_port: int
    ) -> dict[str, object]: ...

    def sync_start_daemon(self, config: dict[str, object]) -> dict[str, object]: ...

    def sync_status(self) -> dict[str, object]: ...

    def sync_stop_daemon(self) -> dict[str, object]: ...


ledgera_core = cast(_LedgeraCoreModule, _ledgera_core)


def _assert_callable_export(name: str) -> None:
    export = getattr(_ledgera_core, name, None)
    if not callable(export):
        pytest.skip(f"ledgera_core extension does not expose alpha.2 export: {name}")


def test_convert_amount():
    assert ledgera_core.convert_amount(100.0, 5.25) == pytest.approx(525.0)


def test_calculate_daily_burn():
    assert ledgera_core.calculate_daily_burn(100.0, 10) == pytest.approx(10.0)


def test_money_helpers_match_expected_rounding():
    assert ledgera_core.to_money_float("1.005") == pytest.approx(1.01)
    assert ledgera_core.to_rate_float("1.2345675") == pytest.approx(1.234568)
    assert ledgera_core.to_minor_units("123.455") == 12346
    assert ledgera_core.minor_to_money("12346") == pytest.approx(123.46)
    assert ledgera_core.money_abs("-10.004") == pytest.approx(10.0)


def test_build_rate_preserves_python_contract():
    assert ledgera_core.build_rate("10.00", "5000.00", "USD") == pytest.approx(500.0)
    assert ledgera_core.build_rate("0", "5000.00", "USD") == pytest.approx(1.0)
    assert ledgera_core.build_rate("10.00", "5000.00", "KZT") == pytest.approx(1.0)


def test_decimal_parity_text_helpers():
    assert ledgera_core.quantize_money_text("1.005") == "1.01"
    assert ledgera_core.quantize_money_text("-1.005") == "-1.01"
    assert ledgera_core.quantize_rate_text("1.2345675") == "1.234568"
    assert ledgera_core.rate_to_text("1.2") == "1.200000"
    assert ledgera_core.money_diff_text("10.005", "1.00") == "9.01"
    assert ledgera_core.rate_diff_text("1.2345675", "0.2345674") == "1.000001"


def test_currency_parity_helpers():
    _assert_callable_export("currency_rate_for")
    _assert_callable_export("currency_default_rates_for_base")
    _assert_callable_export("currency_resolve_provider_order")
    _assert_callable_export("storage_clear_read_cache")

    default_rates = {"USD": 500.0, "EUR": 590.0, "RUB": 6.5}
    assert ledgera_core.currency_rate_for("KZT", "KZT", default_rates) == pytest.approx(1.0)
    assert ledgera_core.currency_rate_for("usd", "KZT", default_rates) == pytest.approx(500.0)
    with pytest.raises(ValueError, match="Currency is required"):
        ledgera_core.currency_rate_for("", "KZT", default_rates)
    with pytest.raises(ValueError, match="unsupported currency"):
        ledgera_core.currency_rate_for(" usd ", "KZT", default_rates)
    assert ledgera_core.currency_default_rates_for_base("USD", default_rates)[
        "KZT"
    ] == pytest.approx(0.002)
    assert ledgera_core.currency_resolve_provider_order(
        "KZT",
        "personal",
        "nbk",
        "exchange_rate",
        "exchange_rate",
        False,
        None,
    ) == ["nbk", "exchange_rate", "static"]


def test_metrics_refresh_snapshot_compact_smoke():
    _assert_callable_export("metrics_refresh_snapshot_compact")
    db_dir = Path.cwd() / "tests" / "_tmp"
    db_dir.mkdir(exist_ok=True)
    db_path = db_dir / f"refresh_snapshot_{os.getpid()}.db"
    db_path.unlink(missing_ok=True)
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(
            """
            CREATE TABLE records (
                id INTEGER PRIMARY KEY,
                type TEXT NOT NULL,
                date TEXT NOT NULL,
                wallet_id INTEGER NOT NULL DEFAULT 1,
                transfer_id INTEGER,
                related_debt_id INTEGER,
                amount_original REAL NOT NULL DEFAULT 0,
                amount_original_minor INTEGER,
                currency TEXT NOT NULL DEFAULT 'KZT',
                rate_at_operation REAL NOT NULL DEFAULT 1.0,
                rate_at_operation_text TEXT NOT NULL DEFAULT '1.000000',
                amount_base REAL NOT NULL,
                amount_base_minor INTEGER,
                category TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                period TEXT
            );
            CREATE TABLE tags (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                color TEXT
            );
            CREATE TABLE record_tags (
                record_id INTEGER NOT NULL,
                tag_id INTEGER NOT NULL
            );
            """
        )
        conn.executemany(
            "INSERT INTO records "
            "(type, date, transfer_id, amount_base, amount_base_minor, category) "
            "VALUES (?, ?, NULL, ?, ?, ?)",
            [
                ("income", "2026-01-01", 100.0, 10000, "Salary"),
                ("expense", "2026-01-02", 25.0, 2500, "Food"),
                ("mandatory_expense", "2026-01-03", 10.0, 1000, "Rent"),
            ],
        )
        conn.commit()
    finally:
        conn.close()

    snapshot = ledgera_core.metrics_refresh_snapshot_compact(
        str(db_path),
        "2026-01-01",
        "2026-01-31",
        31,
        None,
        None,
    )

    assert snapshot[0] == pytest.approx(65.0)
    assert snapshot[1] == pytest.approx(1.13)
    assert snapshot[2] == [("Food", 25.0, 1), ("Rent", 10.0, 1)]
    assert snapshot[3] == [("Salary", 100.0, 1)]
    assert snapshot[4] == []
    assert snapshot[5] == [("2026-01", 100.0, 35.0, 65.0, 65.0)]
    ledgera_core.storage_clear_read_cache()
    db_path.unlink(missing_ok=True)


def test_planning_parity_exports_smoke():
    _assert_callable_export("distribution_available_months")
    _assert_callable_export("distribution_create_item")
    _assert_callable_export("distribution_monthly_payload")
    _assert_callable_export("distribution_validate_structure")
    _assert_callable_export("budget_create")
    _assert_callable_export("budget_delete")
    _assert_callable_export("budget_replace_rows")
    _assert_callable_export("budget_rows")
    _assert_callable_export("budget_spent_minor")
    _assert_callable_export("budget_update_limit")
    _assert_callable_export("debt_create_obligation")
    _assert_callable_export("debt_delete")
    _assert_callable_export("debt_delete_payment")
    _assert_callable_export("debt_payment_rows")
    _assert_callable_export("debt_recalculate_payload")
    _assert_callable_export("debt_register_payment")
    _assert_callable_export("debt_replace_rows")
    _assert_callable_export("debt_rows")
    _assert_callable_export("debt_validate_payment_amount")

    db_dir = Path.cwd() / "tests" / "_tmp"
    db_dir.mkdir(exist_ok=True)
    db_path = db_dir / f"planning_{os.getpid()}.db"
    db_path.unlink(missing_ok=True)
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(
            """
            CREATE TABLE records (
                id INTEGER PRIMARY KEY,
                type TEXT NOT NULL,
                date TEXT NOT NULL,
                wallet_id INTEGER NOT NULL DEFAULT 1,
                transfer_id INTEGER,
                related_debt_id INTEGER,
                amount_original REAL NOT NULL DEFAULT 0,
                amount_original_minor INTEGER,
                currency TEXT NOT NULL DEFAULT 'KZT',
                rate_at_operation REAL NOT NULL DEFAULT 1.0,
                rate_at_operation_text TEXT NOT NULL DEFAULT '1.000000',
                amount_base REAL NOT NULL,
                amount_base_minor INTEGER,
                category TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                period TEXT
            );
            CREATE TABLE distribution_items (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                group_name TEXT NOT NULL DEFAULT '',
                sort_order INTEGER NOT NULL DEFAULT 0,
                pct REAL NOT NULL DEFAULT 0,
                pct_minor INTEGER NOT NULL DEFAULT 0,
                is_active INTEGER NOT NULL DEFAULT 1
            );
            CREATE TABLE distribution_subitems (
                id INTEGER PRIMARY KEY,
                item_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                sort_order INTEGER NOT NULL DEFAULT 0,
                pct REAL NOT NULL DEFAULT 0,
                pct_minor INTEGER NOT NULL DEFAULT 0,
                is_active INTEGER NOT NULL DEFAULT 1
            );
            CREATE TABLE budgets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT NOT NULL,
                scope_type TEXT NOT NULL,
                scope_value TEXT NOT NULL,
                start_date TEXT NOT NULL,
                end_date TEXT NOT NULL,
                limit_base REAL NOT NULL,
                limit_base_minor INTEGER NOT NULL,
                include_mandatory INTEGER NOT NULL
            );
            CREATE TABLE debts (
                id INTEGER PRIMARY KEY,
                contact_name TEXT NOT NULL,
                kind TEXT NOT NULL,
                total_amount_minor INTEGER NOT NULL,
                remaining_amount_minor INTEGER NOT NULL,
                currency TEXT NOT NULL,
                interest_rate REAL NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                closed_at TEXT
            );
            CREATE TABLE debt_payments (
                id INTEGER PRIMARY KEY,
                debt_id INTEGER NOT NULL,
                record_id INTEGER,
                operation_type TEXT NOT NULL,
                principal_paid_minor INTEGER NOT NULL,
                is_write_off INTEGER NOT NULL,
                payment_date TEXT NOT NULL
            );
            CREATE TABLE tags (id INTEGER PRIMARY KEY, name TEXT NOT NULL);
            CREATE TABLE record_tags (record_id INTEGER NOT NULL, tag_id INTEGER NOT NULL);
            """
        )
        conn.execute(
            "INSERT INTO records (type, date, transfer_id, amount_base, amount_base_minor, category) "  # noqa: E501
            "VALUES ('income', '2026-03-01', NULL, 100.0, 10000, 'Salary')"
        )
        conn.execute(
            "INSERT INTO records (type, date, transfer_id, amount_base, amount_base_minor, category) "  # noqa: E501
            "VALUES ('expense', '2026-03-02', NULL, 25.0, 2500, 'Food')"
        )
        conn.execute(
            "INSERT INTO distribution_items "
            "(id, name, group_name, sort_order, pct, pct_minor, is_active) "
            "VALUES (1, 'Needs', '', 0, 100.0, 10000, 1)"
        )
        conn.execute(
            "INSERT INTO distribution_subitems "
            "(id, item_id, name, sort_order, pct, pct_minor, is_active) "
            "VALUES (1, 1, 'Food', 0, 100.0, 10000, 1)"
        )
        conn.execute(
            "INSERT INTO debts "
            "(id, contact_name, kind, total_amount_minor, remaining_amount_minor, currency, "
            "interest_rate, status, created_at, closed_at) "
            "VALUES (1, 'Alice', 'debt', 10000, 10000, 'KZT', 0.0, 'open', '2026-03-01', NULL)"
        )
        conn.execute(
            "INSERT INTO debt_payments "
            "(id, debt_id, record_id, operation_type, principal_paid_minor, is_write_off, payment_date) "  # noqa: E501
            "VALUES (1, 1, NULL, 'debt_repay', 2500, 0, '2026-03-03')"
        )
        conn.commit()
    finally:
        conn.close()

    assert ledgera_core.distribution_available_months(str(db_path)) == ["2026-03"]
    assert ledgera_core.distribution_validate_structure(str(db_path)) == []
    distribution = ledgera_core.distribution_monthly_payload(
        str(db_path),
        "2026-03",
        "2026-03-01",
        "2026-03-31",
    )
    assert distribution["net_income_minor"] == 7500
    assert (
        ledgera_core.budget_spent_minor(
            str(db_path),
            "category",
            "Food",
            "2026-03-01",
            "2026-03-31",
            False,
        )
        == 2500
    )
    budget = ledgera_core.budget_create(
        str(db_path),
        "Travel",
        "category",
        "Travel",
        "2026-04-01",
        "2026-04-30",
        100.0,
        10000,
        False,
    )
    assert budget["id"] == 1
    assert ledgera_core.budget_rows(str(db_path))[0]["category"] == "Travel"
    updated_budget = ledgera_core.budget_update_limit(str(db_path), 1, 150.0, 15000)
    assert updated_budget["limit_base_minor"] == 15000
    ledgera_core.budget_delete(str(db_path), 1)
    assert ledgera_core.budget_rows(str(db_path)) == []
    assert ledgera_core.debt_validate_payment_amount(7500, 2500) == 2500
    assert ledgera_core.debt_recalculate_payload(str(db_path), 1)["remaining_amount_minor"] == 7500
    created_debt = ledgera_core.debt_create_obligation(
        str(db_path),
        {
            "id": 0,
            "contact_name": "Bob",
            "kind": "loan",
            "total_amount_minor": 5000,
            "remaining_amount_minor": 5000,
            "currency": "KZT",
            "interest_rate": 0.0,
            "status": "open",
            "created_at": "2026-04-01",
            "closed_at": None,
        },
        {
            "type": "expense",
            "date": "2026-04-01",
            "wallet_id": 1,
            "amount_original": 50.0,
            "amount_original_minor": 5000,
            "currency": "KZT",
            "rate_at_operation": 1.0,
            "rate_at_operation_text": "1.000000",
            "amount_base": 50.0,
            "amount_base_minor": 5000,
            "category": "Loan",
            "description": "Bob",
            "period": None,
        },
    )
    created_debt_id = int(cast(int, created_debt["id"]))
    payment = ledgera_core.debt_register_payment(
        str(db_path),
        created_debt_id,
        {
            "id": 0,
            "debt_id": created_debt_id,
            "record_id": None,
            "operation_type": "loan_collect",
            "principal_paid_minor": 5000,
            "is_write_off": False,
            "payment_date": "2026-04-02",
        },
        {
            "type": "income",
            "date": "2026-04-02",
            "wallet_id": 1,
            "amount_original": 50.0,
            "amount_original_minor": 5000,
            "currency": "KZT",
            "rate_at_operation": 1.0,
            "rate_at_operation_text": "1.000000",
            "amount_base": 50.0,
            "amount_base_minor": 5000,
            "category": "Loan payment",
            "description": "Bob",
            "period": None,
        },
    )
    assert payment["record_id"] is not None
    assert ledgera_core.debt_rows(str(db_path))[-1]["status"] == "closed"
    ledgera_core.debt_delete_payment(str(db_path), int(cast(int, payment["id"])), True)
    assert ledgera_core.debt_payment_rows(str(db_path), created_debt_id) == []
    ledgera_core.storage_clear_read_cache()
    db_path.unlink(missing_ok=True)


def test_sync_exports_smoke():
    _assert_callable_export("sync_discover_peers")
    _assert_callable_export("sync_push_once")
    _assert_callable_export("sync_start_daemon")
    _assert_callable_export("sync_status")
    _assert_callable_export("sync_stop_daemon")

    status = ledgera_core.sync_status()
    assert status["running"] in {True, False}
    stopped = ledgera_core.sync_stop_daemon()
    assert stopped["running"] is False
