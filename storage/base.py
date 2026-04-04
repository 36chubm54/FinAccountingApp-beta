from __future__ import annotations

from typing import Protocol

from domain.records import MandatoryExpenseRecord, Record
from domain.transfers import Transfer
from domain.wallets import Wallet


class Storage(Protocol):
    """Low-level storage contract for persistence adapters."""

    def get_wallets(self) -> list[Wallet]: ...

    def save_wallet(self, wallet: Wallet) -> None: ...

    def get_records(self) -> list[Record]: ...

    def save_record(self, record: Record) -> None: ...

    def get_transfers(self) -> list[Transfer]: ...

    def save_transfer(self, transfer: Transfer) -> None: ...

    def get_mandatory_expenses(self) -> list[MandatoryExpenseRecord]: ...
