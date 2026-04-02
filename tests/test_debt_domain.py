import pytest

from domain.debt import Debt, DebtKind, DebtOperationType, DebtPayment, DebtStatus


def test_debt_creation_accepts_valid_open_debt() -> None:
    debt = Debt(
        id=1,
        contact_name="Alice",
        kind=DebtKind.DEBT,
        total_amount_minor=50_000,
        remaining_amount_minor=15_000,
        currency="KZT",
        interest_rate=0.0,
        status=DebtStatus.OPEN,
        created_at="2026-03-30",
    )

    assert debt.kind is DebtKind.DEBT
    assert debt.status is DebtStatus.OPEN
    assert debt.remaining_amount_minor == 15_000


def test_closed_debt_requires_zero_remaining_amount() -> None:
    with pytest.raises(ValueError, match="Closed debt must have zero remaining amount"):
        Debt(
            id=1,
            contact_name="Alice",
            kind=DebtKind.LOAN,
            total_amount_minor=50_000,
            remaining_amount_minor=1,
            currency="KZT",
            interest_rate=5.0,
            status=DebtStatus.CLOSED,
            created_at="2026-03-30",
            closed_at="2026-04-01",
        )


def test_write_off_payment_requires_debt_forgive_operation_type() -> None:
    with pytest.raises(ValueError, match="Write-off payments must use DEBT_FORGIVE"):
        DebtPayment(
            id=1,
            debt_id=1,
            record_id=None,
            operation_type=DebtOperationType.DEBT_REPAY,
            principal_paid_minor=1_000,
            is_write_off=True,
            payment_date="2026-03-30",
        )


def test_debt_forgive_payment_must_be_marked_as_write_off() -> None:
    with pytest.raises(ValueError, match="DEBT_FORGIVE payments must be marked as write-off"):
        DebtPayment(
            id=1,
            debt_id=1,
            record_id=None,
            operation_type=DebtOperationType.DEBT_FORGIVE,
            principal_paid_minor=1_000,
            is_write_off=False,
            payment_date="2026-03-30",
        )
