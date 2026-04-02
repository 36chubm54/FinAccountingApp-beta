"""Debt domain models."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .validation import parse_ymd


class DebtKind(Enum):
    DEBT = "debt"
    LOAN = "loan"


class DebtStatus(Enum):
    OPEN = "open"
    CLOSED = "closed"


class DebtOperationType(Enum):
    DEBT_TAKE = "debt_take"
    DEBT_REPAY = "debt_repay"
    LOAN_GIVE = "loan_give"
    LOAN_COLLECT = "loan_collect"
    DEBT_FORGIVE = "debt_forgive"


@dataclass(frozen=True)
class Debt:
    id: int
    contact_name: str
    kind: DebtKind
    total_amount_minor: int
    remaining_amount_minor: int
    currency: str
    interest_rate: float
    status: DebtStatus
    created_at: str
    closed_at: str | None = None

    def __post_init__(self) -> None:
        if int(self.id) <= 0:
            raise ValueError("Debt id must be positive")
        if not str(self.contact_name or "").strip():
            raise ValueError("Contact name is required")
        if int(self.total_amount_minor) <= 0:
            raise ValueError("Total amount must be positive")
        if int(self.remaining_amount_minor) < 0:
            raise ValueError("Remaining amount cannot be negative")
        if int(self.remaining_amount_minor) > int(self.total_amount_minor):
            raise ValueError("Remaining amount cannot exceed total amount")
        if not str(self.currency or "").strip():
            raise ValueError("Currency is required")
        if float(self.interest_rate) < 0:
            raise ValueError("Interest rate cannot be negative")
        parse_ymd(self.created_at)
        if self.closed_at:
            parse_ymd(self.closed_at)
        if self.status is DebtStatus.CLOSED and int(self.remaining_amount_minor) != 0:
            raise ValueError("Closed debt must have zero remaining amount")


@dataclass(frozen=True)
class DebtPayment:
    id: int
    debt_id: int
    record_id: int | None
    operation_type: DebtOperationType
    principal_paid_minor: int
    is_write_off: bool
    payment_date: str

    def __post_init__(self) -> None:
        if int(self.id) <= 0:
            raise ValueError("Debt payment id must be positive")
        if int(self.debt_id) <= 0:
            raise ValueError("Debt payment debt_id must be positive")
        if self.record_id is not None and int(self.record_id) <= 0:
            raise ValueError("Debt payment record_id must be positive")
        if int(self.principal_paid_minor) <= 0:
            raise ValueError("Principal paid must be positive")
        parse_ymd(self.payment_date)
        if self.is_write_off and self.operation_type is not DebtOperationType.DEBT_FORGIVE:
            raise ValueError("Write-off payments must use DEBT_FORGIVE operation type")
        if not self.is_write_off and self.operation_type is DebtOperationType.DEBT_FORGIVE:
            raise ValueError("DEBT_FORGIVE payments must be marked as write-off")
