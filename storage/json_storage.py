from __future__ import annotations

from domain.records import MandatoryExpenseRecord, Record
from domain.transfers import Transfer
from domain.wallets import Wallet
from infrastructure.repositories import JsonFileRecordRepository

from .base import Storage


class JsonStorage(Storage):
    """Storage adapter over the existing JSON repository implementation."""

    def __init__(self, file_path: str = "data.json") -> None:
        self._repo = JsonFileRecordRepository(file_path=file_path)

    def get_wallets(self) -> list[Wallet]:
        return self._repo.load_wallets()

    def save_wallet(self, wallet: Wallet) -> None:
        self._repo.save_wallet(wallet)

    def get_records(self) -> list[Record]:
        return self._repo.load_all()

    def save_record(self, record: Record) -> None:
        self._repo.save(record)

    def get_transfers(self) -> list[Transfer]:
        return self._repo.load_transfers()

    def save_transfer(self, transfer: Transfer) -> None:
        self._repo.save_transfer(transfer)

    def get_mandatory_expenses(self) -> list[MandatoryExpenseRecord]:
        return self._repo.load_mandatory_expenses()

    def replace_all_data(
        self,
        *,
        initial_balance: float = 0.0,
        wallets: list[Wallet] | None = None,
        records: list[Record],
        mandatory_expenses: list[MandatoryExpenseRecord],
        transfers: list[Transfer] | None = None,
    ) -> None:
        self._repo.replace_all_data(
            initial_balance=initial_balance,
            wallets=wallets,
            records=records,
            mandatory_expenses=mandatory_expenses,
            transfers=transfers,
        )
