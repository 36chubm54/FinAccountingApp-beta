from __future__ import annotations

from domain.records import Record
from domain.wallets import Wallet
from infrastructure.repositories import RecordRepository


def build_rate(amount: float, amount_kzt: float, currency: str) -> float:
    if currency.upper() == "KZT":
        return 1.0
    if amount == 0:
        return 1.0
    return amount_kzt / amount


def commission_marker(transfer_id: int) -> str:
    return f"[transfer:{transfer_id}]"


def is_commission_for_transfer(record: Record, transfer_id: int) -> bool:
    if record.transfer_id is not None:
        return False
    if str(record.category or "").strip().lower() != "commission":
        return False
    marker = commission_marker(transfer_id)
    return marker in str(getattr(record, "description", "") or "")


def wallet_balance_kzt(wallet: Wallet, records: list[Record]) -> float:
    total = float(wallet.initial_balance)
    for record in records:
        if record.wallet_id == wallet.id:
            total += record.signed_amount_kzt()
    return total


def wallet_by_id(repository: RecordRepository, wallet_id: int) -> Wallet:
    wallet = next((w for w in repository.load_wallets() if w.id == wallet_id), None)
    if wallet is None:
        raise ValueError(f"Wallet not found: {wallet_id}")
    return wallet
