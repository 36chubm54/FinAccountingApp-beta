from __future__ import annotations

import os
import sqlite3
from pathlib import Path

os.environ.setdefault("LEDGERA_ENABLE_RUST_CORE", "1")

from infrastructure.sqlite_repository import SQLiteRecordRepository
from services.analytics import metrics as metrics_module
from services.analytics.metrics import MetricsService
from tests.test_metrics_service import (
    _init_db,
    _insert_record,
    _insert_record_tag,
    _insert_tag,
    _insert_wallet,
    _schema_path,
)


def _build_metrics_repo(tmp_path: Path) -> SQLiteRecordRepository:
    db_path = tmp_path / "metrics_core.db"
    _init_db(db_path)
    conn = sqlite3.connect(db_path)
    try:
        _insert_wallet(conn, 1)
        _insert_record(
            conn,
            record_type="income",
            date="2026-01-01",
            wallet_id=1,
            amount_base=1000.0,
            category="Salary",
        )
        _insert_record(
            conn,
            record_type="expense",
            date="2026-01-02",
            wallet_id=1,
            amount_base=250.0,
            category="Food",
        )
        first_expense_id = int(conn.execute("SELECT MAX(id) FROM records").fetchone()[0])
        _insert_record(
            conn,
            record_type="mandatory_expense",
            date="2026-02-03",
            wallet_id=1,
            amount_base=100.0,
            category="Rent",
        )
        second_expense_id = int(conn.execute("SELECT MAX(id) FROM records").fetchone()[0])
        _insert_tag(conn, 1, name="food", color="#F2994A")
        _insert_tag(conn, 2, name="fixed", color="#5B8DEF")
        _insert_record_tag(conn, record_id=first_expense_id, tag_id=1)
        _insert_record_tag(conn, record_id=second_expense_id, tag_id=2)
    finally:
        conn.close()
    return SQLiteRecordRepository(str(db_path), schema_path=_schema_path())


def test_metrics_service_rust_path_matches_python_fallback(tmp_path: Path) -> None:
    repo = _build_metrics_repo(tmp_path)
    try:
        rust_service = MetricsService(repo)
        rust_values = (
            rust_service.get_savings_rate("2026-01-01", "2026-02-28"),
            rust_service.get_burn_rate("2026-01-01", "2026-01-31"),
            rust_service.get_spending_by_category("2026-01-01", "2026-02-28"),
            rust_service.get_income_by_category("2026-01-01", "2026-02-28"),
            rust_service.get_spending_by_tag("2026-01-01", "2026-02-28"),
            rust_service.get_tag_coverage("2026-01-01", "2026-02-28"),
            rust_service.get_monthly_summary("2026-01-01", "2026-02-28"),
        )

        rust_core = metrics_module._RUST_METRICS_CORE
        metrics_module._RUST_METRICS_CORE = None
        try:
            fallback_service = MetricsService(repo)
            fallback_values = (
                fallback_service.get_savings_rate("2026-01-01", "2026-02-28"),
                fallback_service.get_burn_rate("2026-01-01", "2026-01-31"),
                fallback_service.get_spending_by_category("2026-01-01", "2026-02-28"),
                fallback_service.get_income_by_category("2026-01-01", "2026-02-28"),
                fallback_service.get_spending_by_tag("2026-01-01", "2026-02-28"),
                fallback_service.get_tag_coverage("2026-01-01", "2026-02-28"),
                fallback_service.get_monthly_summary("2026-01-01", "2026-02-28"),
            )
        finally:
            metrics_module._RUST_METRICS_CORE = rust_core

        assert rust_values == fallback_values
    finally:
        repo.close()


def test_metrics_service_rust_path_matches_fallback_for_edge_cases(tmp_path: Path) -> None:
    db_path = tmp_path / "metrics_edges.db"
    _init_db(db_path)
    conn = sqlite3.connect(db_path)
    try:
        _insert_wallet(conn, 1)
        _insert_record(
            conn,
            record_type="expense",
            date="2026-03-01",
            wallet_id=1,
            amount_base=0.0,
            category="Zero",
        )
        zero_record_id = int(conn.execute("SELECT MAX(id) FROM records").fetchone()[0])
        _insert_record(
            conn,
            record_type="expense",
            date="2026-03-02",
            wallet_id=1,
            amount_base=25.0,
            category="Small",
        )
        _insert_tag(conn, 1, name="edge", color="")
        _insert_record_tag(conn, record_id=zero_record_id, tag_id=1)
    finally:
        conn.close()

    repo = SQLiteRecordRepository(str(db_path), schema_path=_schema_path())
    try:
        rust_service = MetricsService(repo)
        rust_values = (
            rust_service.get_burn_rate("2026-03-01", "2026-02-28"),
            rust_service.get_spending_by_category("2026-03-01", "2026-03-31", limit=0),
            rust_service.get_tag_coverage("2026-03-01", "2026-03-31"),
            rust_service.get_tag_coverage("2026-04-01", "2026-04-30"),
        )

        rust_core = metrics_module._RUST_METRICS_CORE
        metrics_module._RUST_METRICS_CORE = None
        try:
            fallback_service = MetricsService(repo)
            fallback_values = (
                fallback_service.get_burn_rate("2026-03-01", "2026-02-28"),
                fallback_service.get_spending_by_category("2026-03-01", "2026-03-31", limit=0),
                fallback_service.get_tag_coverage("2026-03-01", "2026-03-31"),
                fallback_service.get_tag_coverage("2026-04-01", "2026-04-30"),
            )
        finally:
            metrics_module._RUST_METRICS_CORE = rust_core

        assert rust_values == fallback_values
    finally:
        repo.close()
