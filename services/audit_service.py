from __future__ import annotations

from collections import Counter
from datetime import date
from typing import Any

from domain.audit import AuditFinding, AuditReport, AuditSeverity
from domain.validation import ensure_not_future, parse_ymd
from infrastructure.sqlite_repository import SQLiteRecordRepository


class AuditService:
    def __init__(self, repository: SQLiteRecordRepository) -> None:
        self._repo = repository
        self._record_rows: list[dict[str, Any]] = []
        self._wallet_rows: list[dict[str, Any]] = []
        self._transfer_rows: list[dict[str, Any]] = []
        self._mandatory_expense_rows: list[dict[str, Any]] = []

    def run(self) -> AuditReport:
        self._wallet_rows = self._read_wallet_rows()
        self._record_rows = self._read_record_rows()
        self._transfer_rows = self._read_transfer_rows()
        self._mandatory_expense_rows = self._read_mandatory_expense_rows()

        findings: list[AuditFinding] = []
        findings += self._check_transfer_pair_integrity()
        findings += self._check_orphan_records()
        findings += self._check_amount_consistency()
        findings += self._check_rate_positivity()
        findings += self._check_date_validity()
        findings += self._check_wallet_references()
        findings += self._check_currency_codes()
        findings += self._check_record_types()
        findings += self._check_mandatory_expense_no_date()
        return AuditReport(findings=tuple(findings), db_path=self._repo.db_path)

    def _check_transfer_pair_integrity(self) -> list[AuditFinding]:
        transfer_ids = {int(transfer["id"]) for transfer in self._transfer_rows}
        grouped: dict[int, list[dict[str, Any]]] = {}
        findings: list[AuditFinding] = []

        for record in self._record_rows:
            transfer_id = record.get("transfer_id")
            if transfer_id is None:
                continue
            grouped.setdefault(int(transfer_id), []).append(record)

        for transfer_id in sorted(transfer_ids):
            linked = [
                record
                for record in grouped.get(transfer_id, [])
                if str(record.get("category", "") or "").strip().lower() != "commission"
            ]
            type_counter = Counter(str(record.get("type", "") or "").strip() for record in linked)
            if (
                len(linked) != 2
                or type_counter.get("expense", 0) != 1
                or type_counter.get("income", 0) != 1
            ):
                findings.append(
                    AuditFinding(
                        check="transfer_pair_integrity",
                        severity=AuditSeverity.ERROR,
                        message=f"Transfer id={transfer_id} has invalid linked record pair.",
                        detail=(
                            f"linked={len(linked)}, "
                            f"expense={type_counter.get('expense', 0)}, "
                            f"income={type_counter.get('income', 0)}"
                        ),
                    )
                )

        for transfer_id in sorted(grouped):
            if transfer_id in transfer_ids:
                continue
            findings.append(
                AuditFinding(
                    check="transfer_pair_integrity",
                    severity=AuditSeverity.ERROR,
                    message=f"Transfer id={transfer_id} is referenced by records but missing.",
                )
            )

        if findings:
            return findings
        return [
            AuditFinding(
                check="transfer_pair_integrity",
                severity=AuditSeverity.OK,
                message="All transfer pairs valid.",
            )
        ]

    def _check_orphan_records(self) -> list[AuditFinding]:
        wallet_ids = {int(wallet["id"]) for wallet in self._wallet_rows}
        findings = [
            AuditFinding(
                check="orphan_records",
                severity=AuditSeverity.ERROR,
                message=f"Record id={record['id']} references missing wallet.",
                detail=f"wallet_id={record['wallet_id']}",
            )
            for record in self._record_rows
            if int(record["wallet_id"]) not in wallet_ids
        ]
        if findings:
            return findings
        return [
            AuditFinding(
                check="orphan_records",
                severity=AuditSeverity.OK,
                message="No orphan records found.",
            )
        ]

    def _check_amount_consistency(self) -> list[AuditFinding]:
        findings: list[AuditFinding] = []
        for record in self._record_rows:
            expected = float(record["amount_original"] or 0.0) * float(record["rate_at_operation"])
            actual = float(record["amount_kzt"] or 0.0)
            delta = actual - expected
            if abs(delta) > 0.01:
                findings.append(
                    AuditFinding(
                        check="amount_consistency",
                        severity=AuditSeverity.WARNING,
                        message=f"Record id={record['id']} has inconsistent amount_kzt.",
                        detail=f"delta {delta:.2f} KZT",
                    )
                )
        if findings:
            return findings
        return [
            AuditFinding(
                check="amount_consistency",
                severity=AuditSeverity.OK,
                message="All record amounts are consistent.",
            )
        ]

    def _check_rate_positivity(self) -> list[AuditFinding]:
        findings = [
            AuditFinding(
                check="rate_positivity",
                severity=AuditSeverity.ERROR,
                message=f"Record id={record['id']} has non-positive rate_at_operation.",
                detail=f"rate_at_operation={record['rate_at_operation']}",
            )
            for record in self._record_rows
            if float(record["rate_at_operation"]) <= 0
        ]
        if findings:
            return findings
        return [
            AuditFinding(
                check="rate_positivity",
                severity=AuditSeverity.OK,
                message="All rates positive.",
            )
        ]

    def _check_date_validity(self) -> list[AuditFinding]:
        findings: list[AuditFinding] = []
        for record in self._record_rows:
            raw_date = (
                record["date"].isoformat()
                if isinstance(record["date"], date)
                else str(record["date"])
            )
            try:
                parsed = parse_ymd(raw_date)
                ensure_not_future(parsed)
            except ValueError as error:
                findings.append(
                    AuditFinding(
                        check="date_validity",
                        severity=AuditSeverity.ERROR,
                        message=f"Record id={record['id']} has invalid date.",
                        detail=f"{raw_date}: {error}",
                    )
                )
        if findings:
            return findings
        return [
            AuditFinding(
                check="date_validity",
                severity=AuditSeverity.OK,
                message="All record dates are valid.",
            )
        ]

    def _check_wallet_references(self) -> list[AuditFinding]:
        wallet_ids = {int(wallet["id"]) for wallet in self._wallet_rows}
        findings: list[AuditFinding] = []
        for transfer in self._transfer_rows:
            missing = []
            if int(transfer["from_wallet_id"]) not in wallet_ids:
                missing.append(f"from_wallet_id={transfer['from_wallet_id']}")
            if int(transfer["to_wallet_id"]) not in wallet_ids:
                missing.append(f"to_wallet_id={transfer['to_wallet_id']}")
            if missing:
                findings.append(
                    AuditFinding(
                        check="wallet_references",
                        severity=AuditSeverity.ERROR,
                        message=f"Transfer id={transfer['id']} references missing wallet.",
                        detail=", ".join(missing),
                    )
                )
        if findings:
            return findings
        return [
            AuditFinding(
                check="wallet_references",
                severity=AuditSeverity.OK,
                message="All transfer wallet references are valid.",
            )
        ]

    def _check_currency_codes(self) -> list[AuditFinding]:
        findings: list[AuditFinding] = []
        for record in self._record_rows:
            if not str(record.get("currency", "") or "").strip():
                findings.append(
                    AuditFinding(
                        check="currency_codes",
                        severity=AuditSeverity.WARNING,
                        message=f"Record id={record['id']} has empty currency code.",
                    )
                )
        for transfer in self._transfer_rows:
            if not str(transfer.get("currency", "") or "").strip():
                findings.append(
                    AuditFinding(
                        check="currency_codes",
                        severity=AuditSeverity.WARNING,
                        message=f"Transfer id={transfer['id']} has empty currency code.",
                    )
                )
        if findings:
            return findings
        return [
            AuditFinding(
                check="currency_codes",
                severity=AuditSeverity.OK,
                message="All currency codes are present.",
            )
        ]

    def _check_record_types(self) -> list[AuditFinding]:
        valid_types = {"income", "expense", "mandatory_expense"}
        findings = [
            AuditFinding(
                check="record_types",
                severity=AuditSeverity.ERROR,
                message=f"Record id={record['id']} has invalid type.",
                detail=f"type={record['type']}",
            )
            for record in self._record_rows
            if str(record["type"]) not in valid_types
        ]
        if findings:
            return findings
        return [
            AuditFinding(
                check="record_types",
                severity=AuditSeverity.OK,
                message="All record types are valid.",
            )
        ]

    def _check_mandatory_expense_no_date(self) -> list[AuditFinding]:
        findings: list[AuditFinding] = []
        for row in self._mandatory_expense_rows:
            date_value = row.get("date")
            if date_value is None:
                continue
            if str(date_value).strip():
                findings.append(
                    AuditFinding(
                        check="mandatory_expense_no_date",
                        severity=AuditSeverity.WARNING,
                        message=f"Mandatory expense id={row['id']} stores unexpected date value.",
                        detail=f"date={date_value}",
                    )
                )
        if findings:
            return findings
        return [
            AuditFinding(
                check="mandatory_expense_no_date",
                severity=AuditSeverity.OK,
                message="Mandatory expense templates do not store dates.",
            )
        ]

    def _read_mandatory_expense_rows(self) -> list[dict[str, Any]]:
        # Read-only helper for schema inspection and template row fetch.
        columns = self._repo.query_all("PRAGMA table_info(mandatory_expenses)")
        has_date = any(str(column[1]) == "date" for column in columns)
        select_list = "id, date" if has_date else "id"
        rows = self._repo.query_all(f"SELECT {select_list} FROM mandatory_expenses ORDER BY id")
        return [dict(row) for row in rows]

    def _read_wallet_rows(self) -> list[dict[str, Any]]:
        rows = self._repo.query_all("SELECT id FROM wallets ORDER BY id")
        return [dict(row) for row in rows]

    def _read_record_rows(self) -> list[dict[str, Any]]:
        rows = self._repo.query_all(
            """
            SELECT
                id,
                type,
                date,
                wallet_id,
                transfer_id,
                amount_original,
                currency,
                rate_at_operation,
                amount_kzt,
                category
            FROM records
            ORDER BY id
            """
        )
        return [dict(row) for row in rows]

    def _read_transfer_rows(self) -> list[dict[str, Any]]:
        rows = self._repo.query_all(
            """
            SELECT
                id,
                from_wallet_id,
                to_wallet_id,
                currency
            FROM transfers
            ORDER BY id
            """
        )
        return [dict(row) for row in rows]
