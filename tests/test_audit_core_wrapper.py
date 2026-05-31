from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import pytest

from domain.audit import AuditReport
from infrastructure.sqlite_repository import SQLiteRecordRepository
from services.analytics.audit import service as audit_service_module
from tests.test_audit_engine import (
    _clean_asset_snapshots,
    _clean_assets,
    _clean_goals,
    _clean_mandatory_expenses,
    _clean_records,
    _clean_transfers,
    _schema_path,
    _wallets,
    build_test_db,
)


class _FakeAuditCore:
    def audit_run(self, db_path: str, today: str | None = None) -> list[dict[str, object]]:
        assert db_path
        assert today is not None
        return [
            {
                "check": "system_wallet_sanity",
                "severity": "ok",
                "message": "System wallet sanity OK.",
                "detail": "",
            }
        ]


def _repo_for_db(db_path: Path) -> SQLiteRecordRepository:
    return SQLiteRecordRepository(str(db_path), schema_path=_schema_path())


def _build_db(
    db_path: Path,
    *,
    records: list[dict[str, Any]] | None = None,
) -> None:
    build_test_db(
        db_path,
        wallets=_wallets(),
        records=records if records is not None else _clean_records(),
        transfers=_clean_transfers(),
        mandatory_expenses=_clean_mandatory_expenses(),
        assets=_clean_assets(),
        asset_snapshots=_clean_asset_snapshots(),
        goals=_clean_goals(),
    )


def _finding_tuples(report: AuditReport) -> tuple[tuple[str, str, str, str], ...]:
    return tuple(
        (
            finding.check,
            finding.severity.value,
            finding.message,
            finding.detail,
        )
        for finding in report.findings
    )


def test_audit_service_reconstructs_rust_payload(monkeypatch, tmp_path: Path) -> None:
    db_path = tmp_path / "audit.db"
    _build_db(db_path)
    repo = _repo_for_db(db_path)
    monkeypatch.setattr(audit_service_module, "_RUST_AUDIT_CORE", _FakeAuditCore())

    try:
        report = audit_service_module.AuditService(repo).run()
    finally:
        repo.close()

    assert report.db_path == str(db_path)
    assert _finding_tuples(report) == (
        (
            "system_wallet_sanity",
            "ok",
            "System wallet sanity OK.",
            "",
        ),
    )


def test_audit_service_falls_back_when_rust_payload_is_invalid(
    monkeypatch, tmp_path: Path, caplog
) -> None:
    class _InvalidAuditCore:
        def audit_run(self, db_path: str, today: str | None = None) -> list[dict[str, object]]:
            return [{"check": "bad", "severity": "not-a-severity"}]

    db_path = tmp_path / "audit.db"
    _build_db(db_path)
    repo = _repo_for_db(db_path)
    monkeypatch.setattr(audit_service_module, "_RUST_AUDIT_CORE", _InvalidAuditCore())
    caplog.set_level(logging.DEBUG, logger=audit_service_module.__name__)

    try:
        report = audit_service_module.AuditService(repo).run()
    finally:
        repo.close()

    assert len(report.findings) == 15
    assert all(finding.severity.value == "ok" for finding in report.findings)
    assert "Rust audit core failed; falling back to Python audit path." in caplog.text


def test_audit_rust_path_matches_python_fallback(monkeypatch, tmp_path: Path) -> None:
    from bridge import ledgera_bridge

    monkeypatch.setenv("LEDGERA_ENABLE_RUST_CORE", "1")
    monkeypatch.delenv("LEDGERA_FORCE_PYTHON_FALLBACK", raising=False)
    rust_core = ledgera_bridge.get_audit_core()
    if rust_core is None:
        pytest.skip("ledgera_core audit_run export is not available")

    records = _clean_records()
    records[0] = {**records[0], "amount_base": 210.05}
    db_path = tmp_path / "audit.db"
    _build_db(db_path, records=records)
    repo = _repo_for_db(db_path)

    try:
        monkeypatch.setattr(audit_service_module, "_RUST_AUDIT_CORE", rust_core)
        rust_report = audit_service_module.AuditService(repo).run()
        monkeypatch.setattr(audit_service_module, "_RUST_AUDIT_CORE", None)
        python_report = audit_service_module.AuditService(repo).run()
    finally:
        repo.close()

    assert _finding_tuples(rust_report) == _finding_tuples(python_report)
