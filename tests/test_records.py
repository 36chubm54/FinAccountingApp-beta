from datetime import date

import pytest

from domain.records import ExpenseRecord, IncomeRecord, MandatoryExpenseRecord, Record


class TestIncomeRecord:
    def test_creation_with_category(self):
        record = IncomeRecord(date="2025-01-01", _amount_init=100.0, category="Salary")
        assert record.date == date(2025, 1, 1)
        assert record.amount == 100.0
        assert record.category == "Salary"

    # Category is required in the dataclass, no default value

    def test_signed_amount_positive(self):
        record = IncomeRecord(date="2025-01-01", _amount_init=100.0, category="Salary")
        assert record.signed_amount() == 100.0

    def test_signed_amount_with_negative_amount(self):
        record = IncomeRecord(date="2025-01-01", _amount_init=-50.0, category="Salary")
        assert record.signed_amount() == -50.0

    def test_immutable(self):
        record = IncomeRecord(date="2025-01-01", _amount_init=100.0, category="Salary")
        with pytest.raises(AttributeError):
            record.amount = 200.0  # type: ignore

    def test_date_is_normalized_to_iso(self):
        record = IncomeRecord(date=" 2025-01-01 ", _amount_init=100.0, category="Salary")
        assert record.date == date(2025, 1, 1)

    def test_malformed_date_raises(self):
        with pytest.raises(ValueError):
            IncomeRecord(date="2025/01/01", _amount_init=10.0, category="Salary")


class TestExpenseRecord:
    def test_creation_with_category(self):
        record = ExpenseRecord(date="2025-01-01", _amount_init=50.0, category="Food")
        assert record.date == date(2025, 1, 1)
        assert record.amount == 50.0
        assert record.category == "Food"

    # Category is required in the dataclass, no default value

    def test_signed_amount_negative(self):
        record = ExpenseRecord(date="2025-01-01", _amount_init=50.0, category="Food")
        assert record.signed_amount() == -50.0

    def test_signed_amount_absolute_value(self):
        record = ExpenseRecord(date="2025-01-01", _amount_init=-100.0, category="Food")
        assert record.signed_amount() == -100.0

    def test_immutable(self):
        record = ExpenseRecord(date="2025-01-01", _amount_init=50.0, category="Food")
        with pytest.raises(AttributeError):
            record.amount = 30.0  # type: ignore


class TestMandatoryExpenseRecord:
    def test_creation(self):
        record = MandatoryExpenseRecord(
            date="2025-01-01",
            _amount_init=100.0,
            category="Mandatory",
            description="Rent payment",
            period="monthly",
        )
        assert record.date == date(2025, 1, 1)
        assert record.amount == 100.0
        assert record.category == "Mandatory"
        assert record.description == "Rent payment"
        assert record.period == "monthly"

    def test_signed_amount_negative(self):
        record = MandatoryExpenseRecord(
            date="2025-01-01",
            _amount_init=100.0,
            category="Mandatory",
            description="Rent payment",
            period="monthly",
        )
        assert record.signed_amount() == -100.0

    def test_signed_amount_absolute_value(self):
        record = MandatoryExpenseRecord(
            date="2025-01-01",
            _amount_init=-50.0,
            category="Mandatory",
            description="Test",
            period="weekly",
        )
        assert record.signed_amount() == -50.0

    def test_immutable(self):
        record = MandatoryExpenseRecord(
            date="2025-01-01",
            _amount_init=100.0,
            category="Mandatory",
            description="Rent payment",
            period="monthly",
        )
        with pytest.raises(AttributeError):
            record.amount = 200.0  # type: ignore

    def test_period_validation(self):
        # Test that period accepts valid values
        for period in ["daily", "weekly", "monthly", "yearly"]:
            record = MandatoryExpenseRecord(
                date="2025-01-01",
                _amount_init=100.0,
                category="Mandatory",
                description="Test",
                period=period,  # type: ignore
            )
            assert record.period == period

    def test_type_is_mandatory_expense(self):
        record = MandatoryExpenseRecord(
            date="",
            _amount_init=100.0,
            category="Mandatory",
            description="Test",
            period="monthly",
        )
        assert record.type == "mandatory_expense"


class TestRecord:
    def test_record_is_abstract(self):
        # Record is abstract and cannot be instantiated directly
        with pytest.raises(TypeError):
            Record(date="2025-01-01", amount=100.0, category="Test")  # type: ignore
