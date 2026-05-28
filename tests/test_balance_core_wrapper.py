from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("LEDGERA_ENABLE_RUST_CORE", "1")

from app.services import CurrencyService
from services.analytics import balance as balance_module
from services.analytics.balance import BalanceService
from tests.test_balance_service import _build_repo, _record, _transfer, _wallet


def test_balance_service_rust_path_matches_python_fallback_for_wallet_balance(
    tmp_path: Path,
) -> None:
    repo = _build_repo(
        tmp_path,
        wallets=[_wallet(1, initial_balance=1000.0)],
        records=[
            _record(1, record_type="income", date="2026-01-01", wallet_id=1, amount_base=200.0),
            _record(2, record_type="expense", date="2026-01-10", wallet_id=1, amount_base=50.0),
        ],
    )
    try:
        rust_service = BalanceService(repo)
        rust_value = rust_service.get_wallet_balance(1, date="2026-01-10")

        rust_core = balance_module._RUST_BALANCE_CORE
        balance_module._RUST_BALANCE_CORE = None
        try:
            fallback_value = BalanceService(repo).get_wallet_balance(1, date="2026-01-10")
        finally:
            balance_module._RUST_BALANCE_CORE = rust_core

        assert rust_value == fallback_value == 1150.0
    finally:
        repo.close()


def test_balance_service_rust_path_matches_python_fallback_for_wallet_list_and_total(
    tmp_path: Path,
) -> None:
    repo = _build_repo(
        tmp_path,
        wallets=[
            _wallet(1, name="Cash", initial_balance=100.0),
            _wallet(2, name="Card", initial_balance=200.0),
        ],
        transfers=[
            _transfer(1, from_wallet_id=1, to_wallet_id=2, date="2026-01-05", amount_base=25.0)
        ],
        records=[
            _record(1, record_type="income", date="2026-01-01", wallet_id=1, amount_base=50.0),
            _record(
                2,
                record_type="expense",
                date="2026-01-05",
                wallet_id=1,
                amount_base=25.0,
                category="Transfer",
                transfer_id=1,
            ),
            _record(
                3,
                record_type="income",
                date="2026-01-05",
                wallet_id=2,
                amount_base=25.0,
                category="Transfer",
                transfer_id=1,
            ),
        ],
    )
    try:
        rust_service = BalanceService(repo)
        rust_balances = rust_service.get_wallet_balances()
        rust_total = rust_service.get_total_balance()

        rust_core = balance_module._RUST_BALANCE_CORE
        balance_module._RUST_BALANCE_CORE = None
        try:
            fallback_service = BalanceService(repo)
            fallback_balances = fallback_service.get_wallet_balances()
            fallback_total = fallback_service.get_total_balance()
        finally:
            balance_module._RUST_BALANCE_CORE = rust_core

        assert rust_balances == fallback_balances
        assert rust_total == fallback_total == 350.0
    finally:
        repo.close()


def test_balance_service_rust_path_matches_python_fallback_for_cashflow(tmp_path: Path) -> None:
    repo = _build_repo(
        tmp_path,
        wallets=[_wallet(1, initial_balance=0.0), _wallet(2, initial_balance=0.0)],
        transfers=[
            _transfer(1, from_wallet_id=1, to_wallet_id=2, date="2026-03-10", amount_base=500.0)
        ],
        records=[
            _record(1, record_type="income", date="2026-03-01", wallet_id=1, amount_base=1000.0),
            _record(
                2,
                record_type="expense",
                date="2026-03-10",
                wallet_id=1,
                amount_base=500.0,
                category="Transfer",
                transfer_id=1,
            ),
            _record(
                3,
                record_type="income",
                date="2026-03-10",
                wallet_id=2,
                amount_base=500.0,
                category="Transfer",
                transfer_id=1,
            ),
            _record(4, record_type="expense", date="2026-03-15", wallet_id=1, amount_base=100.0),
        ],
    )
    try:
        rust_service = BalanceService(repo, CurrencyService())
        rust_income = rust_service.get_income("2026-03-01", "2026-03-31")
        rust_expenses = rust_service.get_expenses("2026-03-01", "2026-03-31")
        rust_cashflow = rust_service.get_cashflow("2026-03-01", "2026-03-31")

        rust_core = balance_module._RUST_BALANCE_CORE
        balance_module._RUST_BALANCE_CORE = None
        try:
            fallback_service = BalanceService(repo, CurrencyService())
            fallback_income = fallback_service.get_income("2026-03-01", "2026-03-31")
            fallback_expenses = fallback_service.get_expenses("2026-03-01", "2026-03-31")
            fallback_cashflow = fallback_service.get_cashflow("2026-03-01", "2026-03-31")
        finally:
            balance_module._RUST_BALANCE_CORE = rust_core

        assert rust_income == fallback_income == 1000.0
        assert rust_expenses == fallback_expenses == 100.0
        assert rust_cashflow == fallback_cashflow
        assert rust_cashflow.cashflow == 900.0
    finally:
        repo.close()
