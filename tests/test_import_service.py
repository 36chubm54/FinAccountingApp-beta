from unittest.mock import Mock, patch

import pytest

from domain.import_policy import ImportPolicy
from domain.wallets import Wallet
from services.import_parser import ParsedImportData
from services.import_service import ImportService


def _finance_mock() -> Mock:
    service = Mock()
    service.run_import_transaction.side_effect = lambda operation: operation()
    service.get_system_initial_balance.return_value = 0.0
    service.get_currency_rate.return_value = 1.0
    service.load_wallets.return_value = [
        Wallet(id=1, name="Main", currency="KZT", initial_balance=0.0, system=True),
        Wallet(id=2, name="Cash", currency="KZT", initial_balance=0.0),
    ]
    return service


def test_import_service_groups_two_transfer_records_into_single_transfer() -> None:
    finance_service = _finance_mock()
    payload = ParsedImportData(
        path="data.csv",
        file_type="csv",
        rows=[
            {
                "date": "2026-01-01",
                "type": "income",
                "wallet_id": "1",
                "category": "Salary",
                "amount_original": "100",
                "currency": "KZT",
                "rate_at_operation": "1",
                "amount_kzt": "100",
            },
            {
                "date": "2026-01-02",
                "type": "expense",
                "wallet_id": "1",
                "transfer_id": "55",
                "category": "Transfer",
                "amount_original": "10",
                "currency": "KZT",
                "rate_at_operation": "1",
                "amount_kzt": "10",
            },
            {
                "date": "2026-01-02",
                "type": "income",
                "wallet_id": "2",
                "transfer_id": "55",
                "category": "Transfer",
                "amount_original": "10",
                "currency": "KZT",
                "rate_at_operation": "1",
                "amount_kzt": "10",
            },
        ],
    )

    with patch("services.import_service.parse_import_file", return_value=payload):
        summary = ImportService(finance_service, policy=ImportPolicy.FULL_BACKUP).import_file(
            "data.csv"
        )

    assert summary == (3, 0, [])
    finance_service.reset_operations_for_import.assert_called_once_with(initial_balance=0.0)
    finance_service.create_income.assert_called_once()
    finance_service.create_transfer.assert_called_once()
    finance_service.create_expense.assert_not_called()


def test_import_service_raises_on_missing_wallet_and_does_not_apply_changes() -> None:
    finance_service = _finance_mock()
    payload = ParsedImportData(
        path="data.csv",
        file_type="csv",
        rows=[
            {
                "date": "2026-01-01",
                "type": "income",
                "wallet_id": "999",
                "category": "Salary",
                "amount_original": "100",
                "currency": "KZT",
                "rate_at_operation": "1",
                "amount_kzt": "100",
            }
        ],
    )

    with patch("services.import_service.parse_import_file", return_value=payload):
        with pytest.raises(ValueError, match="Import aborted"):
            ImportService(finance_service, policy=ImportPolicy.FULL_BACKUP).import_file("data.csv")

    finance_service.reset_operations_for_import.assert_not_called()
    finance_service.create_income.assert_not_called()
    finance_service.create_expense.assert_not_called()
    finance_service.create_transfer.assert_not_called()


def test_import_service_mandatory_import_uses_finance_service_only() -> None:
    finance_service = _finance_mock()
    payload = ParsedImportData(
        path="mandatory.csv",
        file_type="csv",
        rows=[
            {
                "type": "mandatory_expense",
                "category": "Rent",
                "amount_original": "50",
                "currency": "KZT",
                "rate_at_operation": "1",
                "amount_kzt": "50",
                "description": "Monthly",
                "period": "monthly",
            }
        ],
    )

    with patch("services.import_service.parse_import_file", return_value=payload):
        summary = ImportService(finance_service).import_mandatory_file("mandatory.csv")

    assert summary == (1, 0, [])
    finance_service.reset_mandatory_for_import.assert_called_once_with()
    finance_service.create_mandatory_expense.assert_called_once()


def test_import_service_fills_empty_mandatory_description() -> None:
    finance_service = _finance_mock()
    payload = ParsedImportData(
        path="data.csv",
        file_type="csv",
        rows=[
            {
                "date": "2026-01-01",
                "type": "mandatory_expense",
                "wallet_id": "1",
                "category": "Rent",
                "amount_original": "50",
                "currency": "KZT",
                "rate_at_operation": "1",
                "amount_kzt": "50",
                "description": "",
                "period": "monthly",
            }
        ],
    )

    with patch("services.import_service.parse_import_file", return_value=payload):
        summary = ImportService(finance_service, policy=ImportPolicy.FULL_BACKUP).import_file(
            "data.csv"
        )

    assert summary == (1, 0, [])
    finance_service.create_mandatory_expense_record.assert_called_once_with(
        date="2026-01-01",
        wallet_id=1,
        amount=50.0,
        currency="KZT",
        category="Rent",
        description="Imported Rent",
        period="monthly",
        amount_kzt=50.0,
        rate_at_operation=1.0,
    )


def test_import_service_json_backup_imports_mandatory_templates() -> None:
    finance_service = _finance_mock()
    payload = ParsedImportData(
        path="data_backup.json",
        file_type="json",
        rows=[],
        mandatory_rows=[
            {
                "category": "Subscriptions",
                "amount_original": "12",
                "currency": "USD",
                "rate_at_operation": "500",
                "amount_kzt": "6000",
                "description": "Music",
                "period": "monthly",
            }
        ],
        wallets=[
            {
                "id": 1,
                "name": "Main",
                "currency": "KZT",
                "initial_balance": 10.0,
                "system": True,
                "allow_negative": False,
                "is_active": True,
            }
        ],
        initial_balance=10.0,
    )

    with patch("services.import_service.parse_import_file", return_value=payload):
        summary = ImportService(finance_service, policy=ImportPolicy.FULL_BACKUP).import_file(
            "data_backup.json"
        )

    assert summary == (1, 0, [])
    finance_service.reset_all_for_import.assert_called_once()
    finance_service.create_mandatory_expense.assert_called_once_with(
        amount=12.0,
        currency="USD",
        category="Subscriptions",
        description="Music",
        period="monthly",
        amount_kzt=6000.0,
        rate_at_operation=500.0,
    )


def test_import_service_full_backup_passes_fixed_rate_values() -> None:
    finance_service = _finance_mock()
    payload = ParsedImportData(
        path="data.csv",
        file_type="csv",
        rows=[
            {
                "date": "2026-01-01",
                "type": "income",
                "wallet_id": "1",
                "category": "Salary",
                "amount_original": "100",
                "currency": "USD",
                "rate_at_operation": "530",
                "amount_kzt": "53000",
                "description": "Payroll",
            }
        ],
    )

    with patch("services.import_service.parse_import_file", return_value=payload):
        summary = ImportService(finance_service, policy=ImportPolicy.FULL_BACKUP).import_file(
            "data.csv"
        )

    assert summary == (1, 0, [])
    finance_service.create_income.assert_called_once_with(
        date="2026-01-01",
        wallet_id=1,
        amount=100.0,
        currency="USD",
        category="Salary",
        description="Payroll",
        amount_kzt=53000.0,
        rate_at_operation=530.0,
    )


def test_import_service_current_rate_does_not_pass_fixed_values() -> None:
    finance_service = _finance_mock()
    payload = ParsedImportData(
        path="data.csv",
        file_type="csv",
        rows=[
            {
                "date": "2026-01-01",
                "type": "income",
                "wallet_id": "1",
                "category": "Salary",
                "amount_original": "100",
                "currency": "USD",
                "description": "Payroll",
            }
        ],
    )

    with patch("services.import_service.parse_import_file", return_value=payload):
        summary = ImportService(finance_service, policy=ImportPolicy.CURRENT_RATE).import_file(
            "data.csv"
        )

    assert summary == (1, 0, [])
    finance_service.create_income.assert_called_once()
    kwargs = finance_service.create_income.call_args.kwargs
    assert kwargs["amount_kzt"] is None
    assert kwargs["rate_at_operation"] is None
