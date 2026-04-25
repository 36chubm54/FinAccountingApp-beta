import logging
import os
import tempfile
from datetime import date as dt_date

import domain.reports as reports_module
from domain.debt import Debt, DebtKind, DebtStatus
from domain.records import ExpenseRecord, IncomeRecord
from domain.reports import Report
from utils.debt_report_utils import debts_for_report_period
from utils.pdf_utils import _should_add_by_category_section, report_to_pdf


def test_report_pdf_roundtrip():
    records = [
        IncomeRecord(date="2025-01-01", _amount_init=100.0, category="Salary"),
        ExpenseRecord(date="2025-01-02", _amount_init=30.0, category="Food"),
    ]
    report = Report(records, initial_balance=25.0)

    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        path = tmp.name
    try:
        report_to_pdf(report, path)
        assert os.path.getsize(path) > 0
    finally:
        os.unlink(path)


def test_pdf_filtered_single_category_skips_duplicate_group_section():
    records = [
        IncomeRecord(date="2025-01-01", _amount_init=100.0, category="Salary"),
        ExpenseRecord(date="2025-01-02", _amount_init=30.0, category="Food"),
        IncomeRecord(date="2025-01-03", _amount_init=50.0, category="Salary"),
    ]
    filtered = Report(records, initial_balance=200.0).filter_by_category("Salary")
    groups = filtered.grouped_by_category()

    assert _should_add_by_category_section(filtered, groups) is False


def test_report_pdf_with_debts_section_builds_successfully():
    records = [
        IncomeRecord(date="2025-01-01", _amount_init=100.0, category="Salary"),
        ExpenseRecord(date="2025-01-02", _amount_init=30.0, category="Food"),
    ]
    report = Report(records, initial_balance=25.0)
    debts = [
        Debt(
            id=1,
            contact_name="Alex",
            kind=DebtKind.DEBT,
            total_amount_minor=10000,
            remaining_amount_minor=7500,
            currency="KZT",
            interest_rate=0.0,
            status=DebtStatus.OPEN,
            created_at="2026-03-01",
        )
    ]

    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        path = tmp.name
    try:
        report_to_pdf(report, path, debts=debts)
        assert os.path.getsize(path) > 0
    finally:
        os.unlink(path)


def test_pdf_debt_filter_skips_debts_outside_report_period(monkeypatch):
    class FakeDate(dt_date):
        @classmethod
        def today(cls):
            return cls(2026, 4, 15)

    monkeypatch.setattr(reports_module, "dt_date", FakeDate)

    report = Report(
        [IncomeRecord(date="2026-01-01", _amount_init=100.0, category="Salary")],
        initial_balance=25.0,
    ).filter_by_period_range("2026-04")
    debts = [
        Debt(
            id=1,
            contact_name="Alex",
            kind=DebtKind.DEBT,
            total_amount_minor=10000,
            remaining_amount_minor=7500,
            currency="KZT",
            interest_rate=0.0,
            status=DebtStatus.OPEN,
            created_at="2026-01-01",
            closed_at="2026-02-01",
        )
    ]

    assert debts_for_report_period(report, debts) == []


def test_report_pdf_logs_visible_group_warning(caplog, monkeypatch):
    report = Report(
        [IncomeRecord(date="2025-01-01", _amount_init=100.0, category="Salary")],
        initial_balance=25.0,
    )

    def _boom(_self):
        raise RuntimeError("grouping unavailable")

    monkeypatch.setattr(Report, "grouped_by_category", _boom)
    caplog.set_level(logging.WARNING)

    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        path = tmp.name
    try:
        report_to_pdf(report, path)
        assert os.path.getsize(path) > 0
        assert "Failed to build grouped report sections for PDF export" in caplog.text
        assert "grouping unavailable" in caplog.text
    finally:
        os.unlink(path)
