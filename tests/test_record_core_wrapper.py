from __future__ import annotations

from pathlib import Path

from domain.records import MandatoryExpenseRecord
from infrastructure.sqlite import records_wallets as records_wallets_module
from tests.test_balance_service import _build_repo, _record, _transfer, _wallet


def test_sqlite_repo_load_all_rust_path_matches_python_fallback(tmp_path: Path) -> None:
    repo = _build_repo(
        tmp_path,
        wallets=[
            _wallet(1, name="Cash", initial_balance=1000.0),
            _wallet(2, name="Card", initial_balance=0.0),
        ],
        transfers=[
            _transfer(7, from_wallet_id=1, to_wallet_id=2, date="2026-01-10", amount_base=50.0)
        ],
        records=[
            _record(1, record_type="income", date="2026-01-01", wallet_id=1, amount_base=200.0),
            _record(
                2,
                record_type="expense",
                date="2026-01-10",
                wallet_id=1,
                amount_base=50.0,
                category="Transfer",
                transfer_id=7,
            ),
            _record(
                3,
                record_type="income",
                date="2026-01-10",
                wallet_id=2,
                amount_base=50.0,
                category="Transfer",
                transfer_id=7,
            ),
            _record(
                4,
                record_type="mandatory_expense",
                date="2026-01-11",
                wallet_id=1,
                amount_base=30.0,
                category="Mandatory",
            ),
        ],
    )
    try:
        repo.replace_record_tags(1, ("salary", "work"))
        repo.replace_record_tags(4, ("rent",))
        repo.execute(
            """
            INSERT INTO debts (
                id, contact_name, kind, total_amount_minor, remaining_amount_minor,
                currency, interest_rate, status, created_at, closed_at
            ) VALUES (9, 'Alice', 'debt', 50000, 20000, 'KZT', 0.0, 'open', '2026-01-01', NULL)
            """
        )
        repo.execute("UPDATE records SET related_debt_id = ? WHERE id = ?", (9, 3))
        repo.commit()

        rust_records = repo.load_all()

        rust_core = records_wallets_module._RUST_RECORD_CORE
        records_wallets_module._RUST_RECORD_CORE = None
        try:
            fallback_records = repo.load_all()
        finally:
            records_wallets_module._RUST_RECORD_CORE = rust_core

        assert [(record.id, record.type) for record in rust_records] == [
            (1, "income"),
            (2, "expense"),
            (3, "income"),
            (4, "mandatory_expense"),
        ]
        assert rust_records == fallback_records
        assert rust_records[0].tags == ("salary", "work")
        assert rust_records[2].related_debt_id == 9
        assert rust_records[1].transfer_id == fallback_records[1].transfer_id == 1
        assert isinstance(rust_records[3], MandatoryExpenseRecord)
        assert rust_records[3].tags == ("rent",)
    finally:
        repo.close()


def test_sqlite_repo_get_by_id_and_get_records_by_tag_match_python_fallback(tmp_path: Path) -> None:
    repo = _build_repo(
        tmp_path,
        wallets=[_wallet(1, name="Cash", initial_balance=0.0)],
        records=[
            _record(1, record_type="income", date="2026-01-01", wallet_id=1, amount_base=200.0),
            _record(2, record_type="expense", date="2026-01-02", wallet_id=1, amount_base=50.0),
            _record(3, record_type="expense", date="2026-01-03", wallet_id=1, amount_base=30.0),
        ],
    )
    try:
        repo.replace_record_tags(1, ("salary", "work"))
        repo.replace_record_tags(2, ("food",))
        repo.replace_record_tags(3, ("food", "home"))

        rust_record = repo.get_by_id(2)
        rust_food = repo.get_records_by_tag("food")

        rust_core = records_wallets_module._RUST_RECORD_CORE
        records_wallets_module._RUST_RECORD_CORE = None
        try:
            fallback_record = repo.get_by_id(2)
            fallback_food = repo.get_records_by_tag("food")
        finally:
            records_wallets_module._RUST_RECORD_CORE = rust_core

        assert rust_record == fallback_record
        assert rust_record.tags == ("food",)
        assert rust_food == fallback_food
        assert [record.id for record in rust_food] == [2, 3]
        assert rust_food[1].tags == ("food", "home")
    finally:
        repo.close()
