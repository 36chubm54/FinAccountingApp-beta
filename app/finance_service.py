from __future__ import annotations

from collections.abc import Callable
from typing import Protocol, TypeVar

from domain.budget import Budget
from domain.wallets import Wallet

T = TypeVar("T")


class FinanceService(Protocol):
    def create_income(
        self,
        *,
        date: str,
        wallet_id: int,
        amount: float,
        currency: str,
        category: str,
        description: str = "",
        amount_kzt: float | None = None,
        rate_at_operation: float | None = None,
    ) -> None: ...

    def create_expense(
        self,
        *,
        date: str,
        wallet_id: int,
        amount: float,
        currency: str,
        category: str,
        description: str = "",
        amount_kzt: float | None = None,
        rate_at_operation: float | None = None,
    ) -> None: ...

    def create_transfer(
        self,
        *,
        from_wallet_id: int,
        to_wallet_id: int,
        transfer_date: str,
        amount: float,
        currency: str,
        description: str = "",
        commission_amount: float = 0.0,
        commission_currency: str | None = None,
        amount_kzt: float | None = None,
        rate_at_operation: float | None = None,
    ) -> int: ...

    def create_mandatory_expense(
        self,
        *,
        amount: float,
        currency: str,
        wallet_id: int,
        category: str,
        description: str,
        period: str,
        date: str = "",
        amount_kzt: float | None = None,
        rate_at_operation: float | None = None,
    ) -> None: ...

    def create_mandatory_expense_record(
        self,
        *,
        date: str,
        wallet_id: int,
        amount: float,
        currency: str,
        category: str,
        description: str,
        period: str,
        amount_kzt: float | None = None,
        rate_at_operation: float | None = None,
    ) -> None: ...

    def load_wallets(self) -> list[Wallet]: ...

    def set_wallet_allow_negative_for_import(
        self, wallet_id: int, allow_negative: bool
    ) -> None: ...

    def get_system_initial_balance(self) -> float: ...

    def get_currency_rate(self, currency: str) -> float: ...

    def reset_operations_for_import(self, *, initial_balance: float) -> None: ...

    def reset_mandatory_for_import(self) -> None: ...

    def reset_all_for_import(self, *, wallets: list[Wallet], initial_balance: float) -> None: ...

    def replace_budgets(self, budgets: list[Budget]) -> None: ...

    def run_import_transaction(self, operation: Callable[[], T]) -> T: ...

    def normalize_operation_ids_for_import(self) -> None: ...
