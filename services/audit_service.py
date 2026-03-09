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
        findings += self._check_transfer_amount_alignment()
        findings += self._check_amount_consistency()
        findings += self._check_amount_positivity()
        findings += self._check_rate_positivity()
        findings += self._check_date_validity()
        findings += self._check_currency_codes()
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

    def _check_transfer_amount_alignment(self) -> list[AuditFinding]:
        grouped: dict[int, list[dict[str, Any]]] = {}
        for record in self._record_rows:
            transfer_id = record.get("transfer_id")
            if transfer_id is None:
                continue
            if str(record.get("category", "") or "").strip().lower() == "commission":
                continue
            grouped.setdefault(int(transfer_id), []).append(record)

        findings: list[AuditFinding] = []
        for transfer in self._transfer_rows:
            transfer_id = int(transfer["id"])
            linked = grouped.get(transfer_id, [])
            if len(linked) != 2:
                continue
            expense = next((record for record in linked if str(record["type"]) == "expense"), None)
            income = next((record for record in linked if str(record["type"]) == "income"), None)
            if expense is None or income is None:
                continue

            mismatches: list[str] = []
            if float(transfer["amount_original"]) != float(expense["amount_original"]) or float(
                transfer["amount_original"]
            ) != float(income["amount_original"]):
                mismatches.append("amount_original mismatch")
            if str(transfer["currency"]) != str(expense["currency"]) or str(
                transfer["currency"]
            ) != str(income["currency"]):
                mismatches.append("currency mismatch")
            if (
                abs(float(transfer["rate_at_operation"]) - float(expense["rate_at_operation"]))
                > 1e-9
                or abs(float(transfer["rate_at_operation"]) - float(income["rate_at_operation"]))
                > 1e-9
            ):
                mismatches.append("rate_at_operation mismatch")
            if (
                abs(float(transfer["amount_kzt"]) - float(expense["amount_kzt"])) > 0.01
                or abs(float(transfer["amount_kzt"]) - float(income["amount_kzt"])) > 0.01
            ):
                mismatches.append("amount_kzt mismatch")
            if mismatches:
                findings.append(
                    AuditFinding(
                        check="transfer_amount_alignment",
                        severity=AuditSeverity.ERROR,
                        message=f"Transfer id={transfer_id} does not match linked records.",
                        detail=", ".join(mismatches),
                    )
                )

        if findings:
            return findings
        return [
            AuditFinding(
                check="transfer_amount_alignment",
                severity=AuditSeverity.OK,
                message="All transfers match their linked records.",
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

    def _check_amount_positivity(self) -> list[AuditFinding]:
        findings: list[AuditFinding] = []
        for record in self._record_rows:
            if float(record["amount_original"]) <= 0:
                findings.append(
                    AuditFinding(
                        check="amount_positivity",
                        severity=AuditSeverity.ERROR,
                        message=f"Record id={record['id']} has non-positive amount_original.",
                        detail=f"amount_original={record['amount_original']}",
                    )
                )
            if float(record["amount_kzt"]) <= 0:
                findings.append(
                    AuditFinding(
                        check="amount_positivity",
                        severity=AuditSeverity.ERROR,
                        message=f"Record id={record['id']} has non-positive amount_kzt.",
                        detail=f"amount_kzt={record['amount_kzt']}",
                    )
                )

        for transfer in self._transfer_rows:
            if float(transfer["amount_original"]) <= 0:
                findings.append(
                    AuditFinding(
                        check="amount_positivity",
                        severity=AuditSeverity.ERROR,
                        message=f"Transfer id={transfer['id']} has non-positive amount_original.",
                        detail=f"amount_original={transfer['amount_original']}",
                    )
                )
            if float(transfer["amount_kzt"]) <= 0:
                findings.append(
                    AuditFinding(
                        check="amount_positivity",
                        severity=AuditSeverity.ERROR,
                        message=f"Transfer id={transfer['id']} has non-positive amount_kzt.",
                        detail=f"amount_kzt={transfer['amount_kzt']}",
                    )
                )

        for expense in self._mandatory_expense_rows:
            if float(expense["amount_original"]) <= 0:
                findings.append(
                    AuditFinding(
                        check="amount_positivity",
                        severity=AuditSeverity.ERROR,
                        message=(
                            f"Mandatory expense id={expense['id']} "
                            "has non-positive amount_original."
                        ),
                        detail=f"amount_original={expense['amount_original']}",
                    )
                )
            if float(expense["amount_kzt"]) <= 0:
                findings.append(
                    AuditFinding(
                        check="amount_positivity",
                        severity=AuditSeverity.ERROR,
                        message=(
                            f"Mandatory expense id={expense['id']} has non-positive amount_kzt."
                        ),
                        detail=f"amount_kzt={expense['amount_kzt']}",
                    )
                )

        if findings:
            return findings
        return [
            AuditFinding(
                check="amount_positivity",
                severity=AuditSeverity.OK,
                message="All amounts are positive.",
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
        select_list = (
            "id, amount_original, amount_kzt, category, description, date"
            if has_date
            else "id, amount_original, amount_kzt, category, description"
        )
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
                amount_original,
                currency,
                rate_at_operation,
                amount_kzt
            FROM transfers
            ORDER BY id
            """
        )
        return [dict(row) for row in rows]
