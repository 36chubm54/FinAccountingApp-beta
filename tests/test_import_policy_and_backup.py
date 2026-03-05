import os
import tempfile
import json

import pytest

from domain.import_policy import ImportPolicy
from domain.records import ExpenseRecord, IncomeRecord, MandatoryExpenseRecord
from domain.wallets import Wallet
from utils.backup_utils import (
    BackupFormatError,
    BackupIntegrityError,
    BackupReadonlyError,
    export_full_backup_to_json,
    import_full_backup_from_json,
)
from utils.csv_utils import import_records_from_csv


class DummyCurrency:
    def get_rate(self, currency: str) -> float:
        rates = {"USD": 500.0, "EUR": 600.0, "KZT": 1.0}
        return rates[currency]


def test_current_rate_policy_fills_missing_fx_fields():
    csv_content = """
date,type,wallet_id,category,amount_original,currency
2025-01-01,income,1,Salary,100,USD
"""
    with tempfile.NamedTemporaryFile(
        mode="w", delete=False, suffix=".csv", encoding="utf-8"
    ) as tmp:
        tmp.write(csv_content)
        path = tmp.name
    try:
        records, initial_balance, summary = import_records_from_csv(
            path,
            policy=ImportPolicy.CURRENT_RATE,
            currency_service=DummyCurrency(),
        )
        assert initial_balance == 0.0
        assert summary[0] == 1
        assert summary[1] == 0
        assert len(records) == 1
        assert records[0].rate_at_operation == 500.0
        assert records[0].amount_kzt == 50000.0
    finally:
        os.unlink(path)


def test_current_rate_policy_overrides_existing_fx_fields():
    csv_content = """
date,type,wallet_id,category,amount_original,currency,rate_at_operation,amount_kzt
2025-01-01,income,1,Salary,100,USD,450,45000
"""
    with tempfile.NamedTemporaryFile(
        mode="w", delete=False, suffix=".csv", encoding="utf-8"
    ) as tmp:
        tmp.write(csv_content)
        path = tmp.name
    try:
        records, _, summary = import_records_from_csv(
            path,
            policy=ImportPolicy.CURRENT_RATE,
            currency_service=DummyCurrency(),
        )
        assert summary[0] == 1
        assert records[0].rate_at_operation == 500.0
        assert records[0].amount_kzt == 50000.0
    finally:
        os.unlink(path)


def test_legacy_policy_imports_old_amount_column():
    csv_content = """date,type,category,amount
2025-01-02,expense,Food,2500
"""
    with tempfile.NamedTemporaryFile(
        mode="w", delete=False, suffix=".csv", encoding="utf-8"
    ) as tmp:
        tmp.write(csv_content)
        path = tmp.name
    try:
        records, _, summary = import_records_from_csv(path, policy=ImportPolicy.LEGACY)
        assert summary[0] == 1
        assert isinstance(records[0], ExpenseRecord)
        assert records[0].currency == "KZT"
        assert records[0].rate_at_operation == 1.0
        assert records[0].amount_kzt == 2500.0
    finally:
        os.unlink(path)


def test_import_validation_skips_invalid_rows():
    csv_content = """
date,type,wallet_id,category,amount_original,currency,rate_at_operation,amount_kzt
bad-date,income,1,Salary,10,USD,500,5000
2025-01-02,expense,1,Food,-5,KZT,1,5
2025-01-03,income,1,Salary,10,USDX,500,5000
2025-01-04,income,1,Salary,10,USD,500,5000
"""
    with tempfile.NamedTemporaryFile(
        mode="w", delete=False, suffix=".csv", encoding="utf-8"
    ) as tmp:
        tmp.write(csv_content)
        path = tmp.name
    try:
        records, _, summary = import_records_from_csv(path, policy=ImportPolicy.FULL_BACKUP)
        assert len(records) == 1
        assert isinstance(records[0], IncomeRecord)
        assert summary[0] == 1
        assert summary[1] == 3
        assert len(summary[2]) == 3
    finally:
        os.unlink(path)


def test_full_backup_roundtrip():
    records = [
        IncomeRecord(
            date="2025-01-01",
            amount_original=100.0,
            currency="USD",
            rate_at_operation=500.0,
            amount_kzt=50000.0,
            category="Salary",
        )
    ]
    mandatory = [
        MandatoryExpenseRecord(
            date="",
            amount_original=50.0,
            currency="KZT",
            rate_at_operation=1.0,
            amount_kzt=50.0,
            category="Mandatory",
            description="Rent",
            period="monthly",
        )
    ]
    with tempfile.NamedTemporaryFile(delete=False, suffix=".json") as tmp:
        path = tmp.name
    try:
        export_full_backup_to_json(
            path,
            wallets=[
                Wallet(
                    id=1,
                    name="Main wallet",
                    currency="KZT",
                    initial_balance=123.0,
                    system=True,
                )
            ],
            records=records,
            mandatory_expenses=mandatory,
        )
        wallets, imported_records, imported_mandatory, transfers, summary = (
            import_full_backup_from_json(path, force=True)
        )
        assert wallets[0].initial_balance == 123.0
        assert len(imported_records) == 1
        assert len(imported_mandatory) == 1
        assert transfers == []
        assert summary[1] == 0
    finally:
        os.unlink(path)


def test_snapshot_checksum_mismatch_raises_integrity_error() -> None:
    records = [
        IncomeRecord(
            date="2025-01-01",
            wallet_id=1,
            amount_original=10.0,
            currency="USD",
            rate_at_operation=500.0,
            amount_kzt=5000.0,
            category="Salary",
        )
    ]
    with tempfile.NamedTemporaryFile(delete=False, suffix=".json") as tmp:
        path = tmp.name
    try:
        export_full_backup_to_json(
            path,
            wallets=[Wallet(id=1, name="Main wallet", currency="KZT", initial_balance=0.0, system=True)],
            records=records,
            mandatory_expenses=[],
            transfers=[],
            readonly=True,
        )
        with open(path, encoding="utf-8") as fp:
            payload = json.load(fp)
        payload["data"]["records"][0]["amount_original"] = 999.0
        with open(path, "w", encoding="utf-8") as fp:
            json.dump(payload, fp, ensure_ascii=False, indent=2)

        with pytest.raises(BackupIntegrityError):
            import_full_backup_from_json(path, force=True)
    finally:
        os.unlink(path)


def test_snapshot_readonly_requires_force() -> None:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".json") as tmp:
        path = tmp.name
    try:
        export_full_backup_to_json(
            path,
            wallets=[Wallet(id=1, name="Main wallet", currency="KZT", initial_balance=1.0, system=True)],
            records=[],
            mandatory_expenses=[],
            transfers=[],
            readonly=True,
        )
        with pytest.raises(BackupReadonlyError):
            import_full_backup_from_json(path)
    finally:
        os.unlink(path)


def test_snapshot_readonly_force_import_succeeds() -> None:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".json") as tmp:
        path = tmp.name
    try:
        export_full_backup_to_json(
            path,
            wallets=[Wallet(id=1, name="Main wallet", currency="KZT", initial_balance=42.0, system=True)],
            records=[],
            mandatory_expenses=[],
            transfers=[],
            readonly=True,
        )
        wallets, records, mandatory, transfers, summary = import_full_backup_from_json(
            path,
            force=True,
        )
        assert len(wallets) == 1
        assert wallets[0].initial_balance == 42.0
        assert records == []
        assert mandatory == []
        assert transfers == []
        assert summary[1] == 0
    finally:
        os.unlink(path)


def test_legacy_json_without_meta_imports_normally() -> None:
    payload = {
        "wallets": [
            {
                "id": 1,
                "name": "Main wallet",
                "currency": "KZT",
                "initial_balance": 5.0,
                "system": True,
                "allow_negative": False,
                "is_active": True,
            }
        ],
        "records": [],
        "mandatory_expenses": [],
        "transfers": [],
    }
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".json", encoding="utf-8") as tmp:
        json.dump(payload, tmp, ensure_ascii=False)
        path = tmp.name
    try:
        wallets, _, _, _, summary = import_full_backup_from_json(path)
        assert wallets[0].initial_balance == 5.0
        assert summary[1] == 0
    finally:
        os.unlink(path)


def test_snapshot_invalid_structure_raises_backup_format_error() -> None:
    payload = {"meta": {"readonly": True, "checksum": "abc"}, "data": []}
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".json", encoding="utf-8") as tmp:
        json.dump(payload, tmp, ensure_ascii=False)
        path = tmp.name
    try:
        with pytest.raises(BackupFormatError):
            import_full_backup_from_json(path, force=True)
    finally:
        os.unlink(path)
