from __future__ import annotations

import re
import sqlite3
from pathlib import Path

from app.services import CurrencyService
from domain.audit import AuditSeverity
from gui.controllers import FinancialController
from infrastructure.sqlite_repository import SQLiteRecordRepository


def _schema_path() -> str:
    return str(Path(__file__).resolve().parents[1] / "db" / "schema.sql")


def build_test_db(
    path: Path,
    *,
    wallets: list[dict],
    records: list[dict],
    transfers: list[dict],
    mandatory_expenses: list[dict],
) -> None:
    conn = sqlite3.connect(path)
    try:
        conn.executescript(Path(_schema_path()).read_text(encoding="utf-8"))
        conn.execute("PRAGMA foreign_keys = OFF")
        conn.execute("PRAGMA ignore_check_constraints = ON")

        for wallet in wallets:
            conn.execute(
                """
                INSERT INTO wallets (
                    id, name, currency, initial_balance, system, allow_negative, is_active
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    wallet["id"],
                    wallet["name"],
                    wallet["currency"],
                    wallet.get("initial_balance", 0.0),
                    wallet.get("system", 0),
                    wallet.get("allow_negative", 0),
                    wallet.get("is_active", 1),
                ),
            )

        for transfer in transfers:
            conn.execute(
                """
                INSERT INTO transfers (
                    id, from_wallet_id, to_wallet_id, date, amount_original, currency,
                    rate_at_operation, amount_kzt, description
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    transfer["id"],
                    transfer["from_wallet_id"],
                    transfer["to_wallet_id"],
                    transfer["date"],
                    transfer["amount_original"],
                    transfer["currency"],
                    transfer["rate_at_operation"],
                    transfer["amount_kzt"],
                    transfer.get("description", ""),
                ),
            )

        for record in records:
            conn.execute(
                """
                INSERT INTO records (
                    id, type, date, wallet_id, transfer_id, amount_original, currency,
                    rate_at_operation, amount_kzt, category, description, period
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record["id"],
                    record["type"],
                    record["date"],
                    record["wallet_id"],
                    record.get("transfer_id"),
                    record["amount_original"],
                    record["currency"],
                    record["rate_at_operation"],
                    record["amount_kzt"],
                    record.get("category", "General"),
                    record.get("description", ""),
                    record.get("period"),
                ),
            )

        for expense in mandatory_expenses:
            conn.execute(
                """
                INSERT INTO mandatory_expenses (
                    id, wallet_id, amount_original, currency, rate_at_operation, amount_kzt,
                    category, description, period, date, auto_pay
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    expense["id"],
                    expense["wallet_id"],
                    expense["amount_original"],
                    expense["currency"],
                    expense["rate_at_operation"],
                    expense["amount_kzt"],
                    expense.get("category", "Mandatory"),
                    expense.get("description", "Template"),
                    expense.get("period", "monthly"),
                    expense.get("date"),
                    expense.get("auto_pay", 0),
                ),
            )

        conn.commit()
    finally:
        conn.close()


def _wallets() -> list[dict]:
    return [
        {
            "id": 1,
            "name": "Main wallet",
            "currency": "KZT",
            "initial_balance": 1000.0,
            "system": 1,
            "allow_negative": 0,
            "is_active": 1,
        },
        {
            "id": 2,
            "name": "Card",
            "currency": "KZT",
            "initial_balance": 500.0,
            "system": 0,
            "allow_negative": 0,
            "is_active": 1,
        },
    ]


def _clean_transfers() -> list[dict]:
    return [
        {
            "id": 1,
            "from_wallet_id": 1,
            "to_wallet_id": 2,
            "date": "2026-03-04",
            "amount_original": 100.0,
            "currency": "KZT",
            "rate_at_operation": 1.0,
            "amount_kzt": 100.0,
            "description": "Transfer",
        }
    ]


def _clean_records() -> list[dict]:
    return [
        {
            "id": 1,
            "type": "income",
            "date": "2026-03-02",
            "wallet_id": 1,
            "amount_original": 200.0,
            "currency": "KZT",
            "rate_at_operation": 1.0,
            "amount_kzt": 200.0,
            "category": "Salary",
        },
        {
            "id": 2,
            "type": "expense",
            "date": "2026-03-03",
            "wallet_id": 1,
            "amount_original": 50.0,
            "currency": "KZT",
            "rate_at_operation": 1.0,
            "amount_kzt": 50.0,
            "category": "Food",
        },
        {
            "id": 3,
            "type": "expense",
            "date": "2026-03-04",
            "wallet_id": 1,
            "transfer_id": 1,
            "amount_original": 100.0,
            "currency": "KZT",
            "rate_at_operation": 1.0,
            "amount_kzt": 100.0,
            "category": "Transfer",
        },
        {
            "id": 4,
            "type": "income",
            "date": "2026-03-04",
            "wallet_id": 2,
            "transfer_id": 1,
            "amount_original": 100.0,
            "currency": "KZT",
            "rate_at_operation": 1.0,
            "amount_kzt": 100.0,
            "category": "Transfer",
        },
    ]


def _clean_mandatory_expenses() -> list[dict]:
    return [
        {
            "id": 1,
            "wallet_id": 1,
            "amount_original": 75.0,
            "currency": "KZT",
            "rate_at_operation": 1.0,
            "amount_kzt": 75.0,
            "category": "Mandatory",
            "description": "Rent",
            "period": "monthly",
        }
    ]


def _make_controller(db_path: Path) -> tuple[SQLiteRecordRepository, FinancialController]:
    repo = SQLiteRecordRepository(str(db_path), schema_path=_schema_path())
    return repo, FinancialController(repo, CurrencyService(use_online=False))


def _run_audit(
    tmp_path: Path,
    *,
    wallets: list[dict] | None = None,
    records: list[dict] | None = None,
    transfers: list[dict] | None = None,
    mandatory_expenses: list[dict] | None = None,
):
    db_path = tmp_path / "audit.db"
    build_test_db(
        db_path,
        wallets=wallets if wallets is not None else _wallets(),
        records=records if records is not None else _clean_records(),
        transfers=transfers if transfers is not None else _clean_transfers(),
        mandatory_expenses=(
            mandatory_expenses if mandatory_expenses is not None else _clean_mandatory_expenses()
        ),
    )
    repo, controller = _make_controller(db_path)
    return repo, controller.run_audit()


def _findings_by_check(report, check: str):
    return [finding for finding in report.findings if finding.check == check]


def test_clean_db_all_checks_pass(tmp_path: Path) -> None:
    repo, report = _run_audit(tmp_path)
    try:
        assert report.is_clean is True
        assert len(report.findings) == 10
        assert len(report.passed) == 10
        assert all(finding.severity == AuditSeverity.OK for finding in report.findings)
    finally:
        repo.close()


def test_transfer_with_single_linked_record_reports_error(tmp_path: Path) -> None:
    records = _clean_records()[:-1]
    repo, report = _run_audit(tmp_path, records=records)
    try:
        findings = _findings_by_check(report, "transfer_pair_integrity")
        assert any(finding.severity == AuditSeverity.ERROR for finding in findings)
    finally:
        repo.close()


def test_transfer_with_three_non_commission_records_reports_error(tmp_path: Path) -> None:
    records = _clean_records() + [
        {
            "id": 5,
            "type": "expense",
            "date": "2026-03-04",
            "wallet_id": 1,
            "transfer_id": 1,
            "amount_original": 1.0,
            "currency": "KZT",
            "rate_at_operation": 1.0,
            "amount_kzt": 1.0,
            "category": "Transfer",
        }
    ]
    repo, report = _run_audit(tmp_path, records=records)
    try:
        findings = _findings_by_check(report, "transfer_pair_integrity")
        assert any(finding.severity == AuditSeverity.ERROR for finding in findings)
    finally:
        repo.close()


def test_commission_record_is_excluded_from_transfer_pair_count(tmp_path: Path) -> None:
    records = _clean_records() + [
        {
            "id": 5,
            "type": "expense",
            "date": "2026-03-04",
            "wallet_id": 1,
            "transfer_id": 1,
            "amount_original": 2.0,
            "currency": "KZT",
            "rate_at_operation": 1.0,
            "amount_kzt": 2.0,
            "category": "Commission",
        }
    ]
    repo, report = _run_audit(tmp_path, records=records)
    try:
        findings = _findings_by_check(report, "transfer_pair_integrity")
        assert findings[0].severity == AuditSeverity.OK
    finally:
        repo.close()


def test_transfer_amount_alignment_reports_error(tmp_path: Path) -> None:
    transfers = _clean_transfers()
    transfers[0]["amount_kzt"] = 101.0
    repo, report = _run_audit(tmp_path, transfers=transfers)
    try:
        findings = _findings_by_check(report, "transfer_amount_alignment")
        assert any(finding.severity == AuditSeverity.ERROR for finding in findings)
    finally:
        repo.close()


def test_amount_inconsistency_reports_warning(tmp_path: Path) -> None:
    records = _clean_records()
    records[0]["amount_kzt"] = 200.05
    repo, report = _run_audit(tmp_path, records=records)
    try:
        findings = _findings_by_check(report, "amount_consistency")
        assert any(finding.severity == AuditSeverity.WARNING for finding in findings)
    finally:
        repo.close()


def test_zero_rate_reports_error(tmp_path: Path) -> None:
    records = _clean_records()
    records[0]["rate_at_operation"] = 0.0
    repo, report = _run_audit(tmp_path, records=records)
    try:
        findings = _findings_by_check(report, "rate_positivity")
        assert any(finding.severity == AuditSeverity.ERROR for finding in findings)
    finally:
        repo.close()


def test_negative_rate_reports_error(tmp_path: Path) -> None:
    records = _clean_records()
    records[0]["rate_at_operation"] = -1.0
    repo, report = _run_audit(tmp_path, records=records)
    try:
        findings = _findings_by_check(report, "rate_positivity")
        assert any(finding.severity == AuditSeverity.ERROR for finding in findings)
    finally:
        repo.close()


def test_non_positive_amount_reports_error(tmp_path: Path) -> None:
    mandatory_expenses = _clean_mandatory_expenses()
    mandatory_expenses[0]["amount_kzt"] = 0.0
    repo, report = _run_audit(tmp_path, mandatory_expenses=mandatory_expenses)
    try:
        findings = _findings_by_check(report, "amount_positivity")
        assert any(finding.severity == AuditSeverity.ERROR for finding in findings)
    finally:
        repo.close()


def test_future_date_reports_error(tmp_path: Path) -> None:
    records = _clean_records()
    records[0]["date"] = "2099-01-01"
    repo, report = _run_audit(tmp_path, records=records)
    try:
        findings = _findings_by_check(report, "date_validity")
        assert any(finding.severity == AuditSeverity.ERROR for finding in findings)
    finally:
        repo.close()


def test_invalid_date_format_reports_error(tmp_path: Path) -> None:
    records = _clean_records()
    records[0]["date"] = "not-a-date"
    repo, report = _run_audit(tmp_path, records=records)
    try:
        findings = _findings_by_check(report, "date_validity")
        assert any(finding.severity == AuditSeverity.ERROR for finding in findings)
    finally:
        repo.close()


def test_empty_currency_on_record_reports_warning(tmp_path: Path) -> None:
    records = _clean_records()
    records[0]["currency"] = ""
    repo, report = _run_audit(tmp_path, records=records)
    try:
        findings = _findings_by_check(report, "currency_codes")
        assert any(finding.severity == AuditSeverity.WARNING for finding in findings)
    finally:
        repo.close()


def test_system_wallet_flag_reports_error(tmp_path: Path) -> None:
    wallets = [
        {
            "id": 1,
            "name": "Main wallet",
            "currency": "KZT",
            "initial_balance": 0.0,
            "system": 0,
            "allow_negative": 0,
            "is_active": 1,
        }
    ]
    repo, report = _run_audit(
        tmp_path,
        wallets=wallets,
        records=[],
        transfers=[],
        mandatory_expenses=[],
    )
    try:
        findings = _findings_by_check(report, "system_wallet_sanity")
        assert any(finding.severity == AuditSeverity.ERROR for finding in findings)
    finally:
        repo.close()


def test_transfer_linked_record_wrong_category_reports_error(tmp_path: Path) -> None:
    records = _clean_records()
    records[2]["category"] = "Food"
    repo, report = _run_audit(tmp_path, records=records)
    try:
        findings = _findings_by_check(report, "transfer_record_invariants")
        assert any(finding.severity == AuditSeverity.ERROR for finding in findings)
    finally:
        repo.close()


def test_transfer_linked_record_wallet_mismatch_reports_error(tmp_path: Path) -> None:
    records = _clean_records()
    records[2]["wallet_id"] = 2
    repo, report = _run_audit(tmp_path, records=records)
    try:
        findings = _findings_by_check(report, "transfer_record_invariants")
        assert any(finding.severity == AuditSeverity.ERROR for finding in findings)
    finally:
        repo.close()


def test_mandatory_autopay_mismatch_reports_error(tmp_path: Path) -> None:
    mandatory_expenses = _clean_mandatory_expenses()
    mandatory_expenses[0]["date"] = "2026-03-05"
    mandatory_expenses[0]["auto_pay"] = 0
    repo, report = _run_audit(tmp_path, mandatory_expenses=mandatory_expenses)
    try:
        findings = _findings_by_check(report, "mandatory_template_date_and_autopay")
        assert any(finding.severity == AuditSeverity.ERROR for finding in findings)
    finally:
        repo.close()


def test_mandatory_invalid_date_reports_error(tmp_path: Path) -> None:
    mandatory_expenses = _clean_mandatory_expenses()
    mandatory_expenses[0]["date"] = "not-a-date"
    mandatory_expenses[0]["auto_pay"] = 1
    repo, report = _run_audit(tmp_path, mandatory_expenses=mandatory_expenses)
    try:
        findings = _findings_by_check(report, "mandatory_template_date_and_autopay")
        assert any(finding.severity == AuditSeverity.ERROR for finding in findings)
    finally:
        repo.close()


def test_audit_report_summary_format(tmp_path: Path) -> None:
    records = _clean_records()
    records[0]["rate_at_operation"] = 0.0
    repo, report = _run_audit(tmp_path, records=records)
    try:
        assert re.search(
            r"\d+ error\(s\), \d+ warning\(s\), \d+ check\(s\) passed\.", report.summary()
        )
    finally:
        repo.close()


def test_audit_report_is_clean_false_when_errors_exist(tmp_path: Path) -> None:
    records = _clean_records()
    records[0]["amount_kzt"] = 0.0
    repo, report = _run_audit(tmp_path, records=records)
    try:
        assert report.is_clean is False
    finally:
        repo.close()


def test_audit_does_not_write_to_db(tmp_path: Path) -> None:
    repo, report = _run_audit(tmp_path)
    try:
        before = {
            "wallets": int(repo.query_one("SELECT COUNT(*) FROM wallets")[0]),
            "records": int(repo.query_one("SELECT COUNT(*) FROM records")[0]),
            "transfers": int(repo.query_one("SELECT COUNT(*) FROM transfers")[0]),
            "mandatory_expenses": int(repo.query_one("SELECT COUNT(*) FROM mandatory_expenses")[0]),
        }
        _ = report
        second_report = FinancialController(repo, CurrencyService(use_online=False)).run_audit()
        after = {
            "wallets": int(repo.query_one("SELECT COUNT(*) FROM wallets")[0]),
            "records": int(repo.query_one("SELECT COUNT(*) FROM records")[0]),
            "transfers": int(repo.query_one("SELECT COUNT(*) FROM transfers")[0]),
            "mandatory_expenses": int(repo.query_one("SELECT COUNT(*) FROM mandatory_expenses")[0]),
        }
        assert second_report.findings
        assert before == after
    finally:
        repo.close()
