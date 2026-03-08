from __future__ import annotations

from pathlib import Path

import pytest

from app.services import CurrencyService
from domain.import_policy import ImportPolicy
from domain.import_result import ImportResult
from gui.controllers import FinancialController
from infrastructure.sqlite_repository import SQLiteRecordRepository
from utils.backup_utils import export_full_backup_to_json
from utils.csv_utils import export_records_to_csv
from utils.excel_utils import export_records_to_xlsx


def _schema_path() -> str:
    return str(Path(__file__).resolve().parents[1] / "db" / "schema.sql")


def _make_repo(db_path: Path) -> SQLiteRecordRepository:
    return SQLiteRecordRepository(str(db_path), schema_path=_schema_path())


def _make_controller(db_path: Path) -> tuple[SQLiteRecordRepository, FinancialController]:
    repo = _make_repo(db_path)
    controller = FinancialController(repo, CurrencyService())
    controller.set_system_initial_balance(1000.0)
    source_wallet = controller.create_wallet(
        name="Cash",
        currency="KZT",
        initial_balance=500.0,
        allow_negative=False,
    )
    target_wallet = controller.create_wallet(
        name="Card",
        currency="KZT",
        initial_balance=200.0,
        allow_negative=False,
    )
    controller.create_income(
        date="2026-03-01",
        wallet_id=source_wallet.id,
        amount=300.0,
        currency="KZT",
        category="Salary",
        description="March salary",
    )
    controller.create_expense(
        date="2026-03-02",
        wallet_id=source_wallet.id,
        amount=120.0,
        currency="KZT",
        category="Food",
        description="Groceries",
    )
    controller.create_mandatory_expense_record(
        date="2026-03-03",
        wallet_id=source_wallet.id,
        amount=80.0,
        currency="KZT",
        category="Rent",
        description="Monthly rent",
        period="monthly",
    )
    controller.create_transfer(
        from_wallet_id=source_wallet.id,
        to_wallet_id=target_wallet.id,
        transfer_date="2026-03-04",
        amount=150.0,
        currency="KZT",
        description="Move to card",
    )
    return repo, controller


def _seed_destination_wallets(controller: FinancialController) -> None:
    controller.set_system_initial_balance(0.0)
    controller.create_wallet(
        name="Cash",
        currency="KZT",
        initial_balance=500.0,
        allow_negative=False,
    )
    controller.create_wallet(
        name="Card",
        currency="KZT",
        initial_balance=200.0,
        allow_negative=False,
    )


def _export_fixture(source_repo: SQLiteRecordRepository, path: Path, fmt: str) -> None:
    records = source_repo.load_all()
    transfers = source_repo.load_transfers()
    if fmt == "json":
        export_full_backup_to_json(
            str(path),
            wallets=source_repo.load_wallets(),
            records=records,
            mandatory_expenses=source_repo.load_mandatory_expenses(),
            transfers=transfers,
        )
        return
    if fmt == "csv":
        export_records_to_csv(records, str(path), transfers=transfers)
        return
    if fmt == "xlsx":
        export_records_to_xlsx(records, str(path), transfers=transfers)
        return
    raise ValueError(fmt)


def _snapshot_records(
    repo: SQLiteRecordRepository,
) -> list[tuple[int, str, int, int | None, float]]:
    return [
        (
            int(record.id),
            str(record.type),
            int(record.wallet_id),
            int(record.transfer_id) if record.transfer_id is not None else None,
            float(record.amount_kzt or 0.0),
        )
        for record in repo.load_all()
    ]


def _snapshot_transfers(repo: SQLiteRecordRepository) -> list[tuple[int, int, int, float]]:
    return [
        (
            int(transfer.id),
            int(transfer.from_wallet_id),
            int(transfer.to_wallet_id),
            float(transfer.amount_kzt),
        )
        for transfer in repo.load_transfers()
    ]


def _snapshot_wallets(repo: SQLiteRecordRepository) -> list[tuple[int, str, float, bool]]:
    return [
        (
            int(wallet.id),
            str(wallet.name),
            float(wallet.initial_balance),
            bool(wallet.system),
        )
        for wallet in repo.load_wallets()
    ]


def _runtime_record_types(repo: SQLiteRecordRepository) -> list[str]:
    rows = repo._conn.execute("SELECT type FROM records ORDER BY id").fetchall()
    return [str(row[0]) for row in rows]


@pytest.mark.parametrize(
    ("fmt", "extension"),
    [("JSON", ".json"), ("CSV", ".csv"), ("XLSX", ".xlsx")],
)
def test_sqlite_import_pipeline_supports_all_formats_and_preserves_net_worth(
    tmp_path: Path,
    fmt: str,
    extension: str,
) -> None:
    source_repo, source_controller = _make_controller(tmp_path / f"source_{extension}.db")
    target_repo = _make_repo(tmp_path / f"target_{extension}.db")
    target_controller = FinancialController(target_repo, CurrencyService())
    export_path = tmp_path / f"import{extension}"

    try:
        _export_fixture(source_repo, export_path, fmt.lower())
        if fmt != "JSON":
            _seed_destination_wallets(target_controller)

        force = fmt == "JSON"
        result = target_controller.import_records(
            fmt,
            str(export_path),
            ImportPolicy.FULL_BACKUP,
            force=force,
        )

        expected_imported = 5 if fmt == "JSON" else 4
        expected_net_worth = 1800.0 if fmt == "JSON" else 800.0

        assert result == ImportResult(
            imported=expected_imported,
            skipped=0,
            errors=[],
        )

        assert _runtime_record_types(target_repo) == [
            "income",
            "expense",
            "mandatory_expense",
            "expense",
            "income",
        ]
        assert len(target_repo.load_transfers()) == 1
        assert target_controller.net_worth_fixed() == expected_net_worth
    finally:
        source_repo.close()
        target_repo.close()


@pytest.mark.parametrize(
    ("fmt", "extension"),
    [("JSON", ".json"), ("CSV", ".csv"), ("XLSX", ".xlsx")],
)
def test_sqlite_import_rollback_keeps_database_unchanged_on_failure(
    tmp_path: Path,
    fmt: str,
    extension: str,
) -> None:
    source_repo, _ = _make_controller(tmp_path / f"rollback_source_{extension}.db")
    target_repo = _make_repo(tmp_path / f"rollback_target_{extension}.db")
    target_controller = FinancialController(target_repo, CurrencyService())
    export_path = tmp_path / f"rollback{extension}"

    try:
        _seed_destination_wallets(target_controller)
        target_controller.create_income(
            date="2026-03-05",
            wallet_id=2,
            amount=50.0,
            currency="KZT",
            category="Baseline",
        )
        before_records = _snapshot_records(target_repo)
        before_transfers = _snapshot_transfers(target_repo)
        before_wallets = _snapshot_wallets(target_repo)
        before_net_worth = target_controller.net_worth_fixed()

        _export_fixture(source_repo, export_path, fmt.lower())
        if fmt == "JSON":
            payload = export_path.read_text(encoding="utf-8")
            export_path.write_text(
                payload.replace('"wallet_id": 2,', '"wallet_id": 999,', 1),
                encoding="utf-8",
            )
        elif fmt == "CSV":
            payload = export_path.read_text(encoding="utf-8")
            export_path.write_text(
                payload.replace("2026-03-01,income,2,", "2026-03-01,income,999,", 1),
                encoding="utf-8",
            )
        else:
            from openpyxl import load_workbook

            workbook = load_workbook(export_path)
            try:
                worksheet = workbook.active
                if worksheet is None:
                    raise ValueError("Workbook has no active worksheet")
                worksheet["C2"] = 999
                workbook.save(export_path)
            finally:
                workbook.close()

        if fmt == "JSON":
            with pytest.raises(
                Exception, match="checksum mismatch|Import aborted|Wallet not found"
            ):
                target_controller.import_records(
                    fmt,
                    str(export_path),
                    ImportPolicy.FULL_BACKUP,
                    force=True,
                )

            assert _snapshot_records(target_repo) == before_records
            assert _snapshot_transfers(target_repo) == before_transfers
            assert _snapshot_wallets(target_repo) == before_wallets
            assert target_controller.net_worth_fixed() == before_net_worth
        else:
            result = target_controller.import_records(
                fmt,
                str(export_path),
                ImportPolicy.FULL_BACKUP,
                force=False,
            )

            assert result.imported == 3
            assert result.skipped == 1
            assert any("wallet not found" in error for error in result.errors)
            assert _snapshot_records(target_repo) != before_records
    finally:
        source_repo.close()
        target_repo.close()


def test_sqlite_transfer_delete_cascades_linked_records(tmp_path: Path) -> None:
    repo, controller = _make_controller(tmp_path / "cascade.db")
    try:
        transfer = repo.load_transfers()[0]
        linked_ids = [
            record.id
            for record in repo.load_all()
            if int(record.transfer_id or 0) == int(transfer.id)
        ]
        assert len(linked_ids) == 2

        with repo._conn:
            repo._conn.execute("DELETE FROM transfers WHERE id = ?", (int(transfer.id),))

        remaining_linked = repo._conn.execute(
            "SELECT COUNT(*) FROM records WHERE transfer_id = ?",
            (int(transfer.id),),
        ).fetchone()
        assert remaining_linked is not None
        assert int(remaining_linked[0]) == 0
        assert controller.net_worth_fixed() == 1800.0
    finally:
        repo.close()
