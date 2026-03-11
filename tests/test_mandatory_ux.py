from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from app.record_service import RecordService
from app.services import CurrencyService
from app.use_cases import ApplyMandatoryAutoPayments, CreateMandatoryExpense
from domain.records import MandatoryExpenseRecord
from gui.controllers import FinancialController
from infrastructure.sqlite_repository import SQLiteRecordRepository


def _schema_path() -> str:
    return str(Path(__file__).resolve().parents[1] / "db" / "schema.sql")


def test_create_mandatory_without_date(tmp_path: Path) -> None:
    db_path = tmp_path / "mandatory_no_date.db"
    repo = SQLiteRecordRepository(str(db_path), schema_path=_schema_path())
    try:
        CreateMandatoryExpense(repo, CurrencyService(use_online=False)).execute(
            amount=100.0,
            currency="KZT",
            category="Mandatory",
            description="Rent",
            period="monthly",
        )
        expense = repo.load_mandatory_expenses()[0]
        assert expense.date == ""
        assert expense.auto_pay is False
    finally:
        repo.close()


def test_create_mandatory_with_date(tmp_path: Path) -> None:
    db_path = tmp_path / "mandatory_with_date.db"
    repo = SQLiteRecordRepository(str(db_path), schema_path=_schema_path())
    try:
        CreateMandatoryExpense(repo, CurrencyService(use_online=False)).execute(
            amount=100.0,
            currency="KZT",
            category="Mandatory",
            description="Rent",
            period="monthly",
            date="2026-03-09",
        )
        expense = repo.load_mandatory_expenses()[0]
        assert str(expense.date) == "2026-03-09"
        assert expense.auto_pay is True
    finally:
        repo.close()


def test_with_updated_amount_kzt_recalculates_rate() -> None:
    expense = MandatoryExpenseRecord(
        amount_original=10.0,
        currency="USD",
        rate_at_operation=500.0,
        amount_kzt=5000.0,
        category="Mandatory",
        description="Rent",
        period="monthly",
    )

    updated = expense.with_updated_amount_kzt(6000.0)

    assert updated is not expense
    assert updated.amount_kzt == 6000.0
    assert updated.rate_at_operation == 600.0
    assert expense.amount_kzt == 5000.0


def test_with_updated_date_empty_disables_auto_pay() -> None:
    expense = MandatoryExpenseRecord(
        date="2026-03-09",
        amount_original=10.0,
        currency="KZT",
        rate_at_operation=1.0,
        amount_kzt=10.0,
        category="Mandatory",
        description="Rent",
        period="monthly",
        auto_pay=True,
    )

    updated = expense.with_updated_date("")

    assert updated.date == ""
    assert updated.auto_pay is False


def test_with_updated_date_value_enables_auto_pay() -> None:
    expense = MandatoryExpenseRecord(
        amount_original=10.0,
        currency="KZT",
        rate_at_operation=1.0,
        amount_kzt=10.0,
        category="Mandatory",
        description="Rent",
        period="monthly",
    )

    updated = expense.with_updated_date("2026-03-09")

    assert str(updated.date) == "2026-03-09"
    assert updated.auto_pay is True


def test_update_mandatory_amount_kzt_persists(tmp_path: Path) -> None:
    db_path = tmp_path / "mandatory_amount_update.db"
    repo = SQLiteRecordRepository(str(db_path), schema_path=_schema_path())
    try:
        CreateMandatoryExpense(repo, CurrencyService(use_online=False)).execute(
            amount=10.0,
            currency="USD",
            category="Mandatory",
            description="Rent",
            period="monthly",
            amount_kzt=5000.0,
            rate_at_operation=500.0,
        )
        expense = repo.load_mandatory_expenses()[0]
        RecordService(repo).update_mandatory_amount_kzt(expense.id, 6000.0)

        stored = repo.get_mandatory_expense_by_id(expense.id)
        assert stored.amount_kzt == 6000.0
        assert stored.rate_at_operation == 600.0
    finally:
        repo.close()


def test_update_mandatory_date_persists(tmp_path: Path) -> None:
    db_path = tmp_path / "mandatory_date_update.db"
    repo = SQLiteRecordRepository(str(db_path), schema_path=_schema_path())
    try:
        CreateMandatoryExpense(repo, CurrencyService(use_online=False)).execute(
            amount=100.0,
            currency="KZT",
            category="Mandatory",
            description="Rent",
            period="monthly",
        )
        expense = repo.load_mandatory_expenses()[0]
        RecordService(repo).update_mandatory_date(expense.id, "2026-03-09")

        stored = repo.get_mandatory_expense_by_id(expense.id)
        assert str(stored.date) == "2026-03-09"
        assert stored.auto_pay is True
    finally:
        repo.close()


def test_update_mandatory_amount_kzt_negative_raises(tmp_path: Path) -> None:
    db_path = tmp_path / "mandatory_amount_invalid.db"
    repo = SQLiteRecordRepository(str(db_path), schema_path=_schema_path())
    try:
        CreateMandatoryExpense(repo, CurrencyService(use_online=False)).execute(
            amount=100.0,
            currency="KZT",
            category="Mandatory",
            description="Rent",
            period="monthly",
        )
        expense = repo.load_mandatory_expenses()[0]
        with pytest.raises(ValueError):
            RecordService(repo).update_mandatory_amount_kzt(expense.id, -1.0)
    finally:
        repo.close()


def test_update_mandatory_date_invalid_format_raises(tmp_path: Path) -> None:
    db_path = tmp_path / "mandatory_date_invalid.db"
    repo = SQLiteRecordRepository(str(db_path), schema_path=_schema_path())
    try:
        CreateMandatoryExpense(repo, CurrencyService(use_online=False)).execute(
            amount=100.0,
            currency="KZT",
            category="Mandatory",
            description="Rent",
            period="monthly",
        )
        expense = repo.load_mandatory_expenses()[0]
        with pytest.raises(ValueError):
            RecordService(repo).update_mandatory_date(expense.id, "09-03-2026")
    finally:
        repo.close()


def test_audit_reports_10_checks_on_clean_db(tmp_path: Path) -> None:
    db_path = tmp_path / "mandatory_audit.db"
    repo = SQLiteRecordRepository(str(db_path), schema_path=_schema_path())
    try:
        controller = FinancialController(repo, CurrencyService(use_online=False))
        report = controller.run_audit()
        assert len(report.findings) == 10
        assert len(report.passed) == 9
    finally:
        repo.close()


def test_auto_pay_creates_monthly_record_once(tmp_path: Path) -> None:
    db_path = tmp_path / "mandatory_autopay_once.db"
    repo = SQLiteRecordRepository(str(db_path), schema_path=_schema_path())
    try:
        CreateMandatoryExpense(repo, CurrencyService(use_online=False)).execute(
            amount=100.0,
            currency="KZT",
            category="Mandatory",
            description="Rent",
            period="monthly",
            date="2026-01-15",
        )

        created = ApplyMandatoryAutoPayments(repo).execute(today=date(2026, 3, 20))
        created_again = ApplyMandatoryAutoPayments(repo).execute(today=date(2026, 3, 20))

        records = repo.load_all()
        mandatory_records = [
            record for record in records if isinstance(record, MandatoryExpenseRecord)
        ]
        assert created == 1
        assert created_again == 0
        assert len(mandatory_records) == 1
        assert str(mandatory_records[0].date) == "2026-03-15"
    finally:
        repo.close()


def test_auto_pay_skips_before_due_day(tmp_path: Path) -> None:
    db_path = tmp_path / "mandatory_autopay_skip.db"
    repo = SQLiteRecordRepository(str(db_path), schema_path=_schema_path())
    try:
        CreateMandatoryExpense(repo, CurrencyService(use_online=False)).execute(
            amount=100.0,
            currency="KZT",
            category="Mandatory",
            description="Rent",
            period="monthly",
            date="2026-01-25",
        )

        created = ApplyMandatoryAutoPayments(repo).execute(today=date(2026, 3, 20))

        assert created == 0
        assert repo.load_all() == []
    finally:
        repo.close()


def test_auto_pay_clamps_to_last_day_of_month(tmp_path: Path) -> None:
    db_path = tmp_path / "mandatory_autopay_clamp.db"
    repo = SQLiteRecordRepository(str(db_path), schema_path=_schema_path())
    try:
        CreateMandatoryExpense(repo, CurrencyService(use_online=False)).execute(
            amount=100.0,
            currency="KZT",
            category="Mandatory",
            description="Rent",
            period="monthly",
            date="2026-01-31",
        )

        created = ApplyMandatoryAutoPayments(repo).execute(today=date(2026, 2, 28))

        mandatory_records = [
            record for record in repo.load_all() if isinstance(record, MandatoryExpenseRecord)
        ]
        assert created == 1
        assert str(mandatory_records[0].date) == "2026-02-28"
    finally:
        repo.close()
