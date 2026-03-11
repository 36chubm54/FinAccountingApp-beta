from __future__ import annotations

from collections import Counter
from typing import Any

from domain.audit import AuditFinding, AuditReport, AuditSeverity
from domain.validation import ensure_not_future, parse_ymd
from infrastructure.sqlite_repository import SQLiteRecordRepository


class AuditService:
    def __init__(self, repository: SQLiteRecordRepository) -> None:
        self._repo = repository
        self._wallet_rows: list[dict[str, Any]] = []
        self._transfer_rows: list[dict[str, Any]] = []
        self._mandatory_expense_rows: list[dict[str, Any]] = []

        # Derived data collected during a single DB scan.
        # This keeps memory usage bounded as the DB grows.
        self._transfer_linked_records: dict[int, list[dict[str, Any]]] = {}
        self._record_amount_consistency_findings: list[AuditFinding] = []
        self._record_amount_positivity_findings: list[AuditFinding] = []
        self._record_rate_positivity_findings: list[AuditFinding] = []
        self._record_date_validity_findings: list[AuditFinding] = []
        self._record_currency_code_findings: list[AuditFinding] = []

    def run(self) -> AuditReport:
        self._wallet_rows = self._read_wallet_rows()
        self._transfer_rows = self._read_transfer_rows()
        self._mandatory_expense_rows = self._read_mandatory_expense_rows()
        self._scan_record_rows()

        findings: list[AuditFinding] = []
        findings += self._check_system_wallet_sanity()
        findings += self._check_transfer_pair_integrity()
        findings += self._check_transfer_amount_alignment()
        findings += self._check_transfer_record_invariants()
        findings += self._check_amount_consistency()
        findings += self._check_amount_positivity()
        findings += self._check_rate_positivity()
        findings += self._check_date_validity()
        findings += self._check_currency_codes()
        findings += self._check_mandatory_template_date_and_autopay()
        return AuditReport(findings=tuple(findings), db_path=self._repo.db_path)

    def _scan_record_rows(self) -> None:
        self._transfer_linked_records = {}
        self._record_amount_consistency_findings = []
        self._record_amount_positivity_findings = []
        self._record_rate_positivity_findings = []
        self._record_date_validity_findings = []
        self._record_currency_code_findings = []

        for row in self._repo.query_iter(
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
        ):
            record_id = int(row["id"])
            amount_original = float(row["amount_original"] or 0.0)
            rate_at_operation = float(row["rate_at_operation"] or 0.0)
            amount_kzt = float(row["amount_kzt"] or 0.0)

            expected = amount_original * rate_at_operation
            delta = amount_kzt - expected
            if abs(delta) > 0.01:
                self._record_amount_consistency_findings.append(
                    AuditFinding(
                        check="amount_consistency",
                        severity=AuditSeverity.WARNING,
                        message=f"Record id={record_id} has inconsistent amount_kzt.",
                        detail=f"delta {delta:.2f} KZT",
                    )
                )

            if amount_original <= 0:
                self._record_amount_positivity_findings.append(
                    AuditFinding(
                        check="amount_positivity",
                        severity=AuditSeverity.ERROR,
                        message=f"Record id={record_id} has non-positive amount_original.",
                        detail=f"amount_original={amount_original}",
                    )
                )
            if amount_kzt <= 0:
                self._record_amount_positivity_findings.append(
                    AuditFinding(
                        check="amount_positivity",
                        severity=AuditSeverity.ERROR,
                        message=f"Record id={record_id} has non-positive amount_kzt.",
                        detail=f"amount_kzt={amount_kzt}",
                    )
                )

            if rate_at_operation <= 0:
                self._record_rate_positivity_findings.append(
                    AuditFinding(
                        check="rate_positivity",
                        severity=AuditSeverity.ERROR,
                        message=f"Record id={record_id} has non-positive rate_at_operation.",
                        detail=f"rate_at_operation={rate_at_operation}",
                    )
                )

            raw_date = str(row["date"])
            try:
                parsed = parse_ymd(raw_date)
                ensure_not_future(parsed)
            except ValueError as error:
                self._record_date_validity_findings.append(
                    AuditFinding(
                        check="date_validity",
                        severity=AuditSeverity.ERROR,
                        message=f"Record id={record_id} has invalid date.",
                        detail=f"{raw_date}: {error}",
                    )
                )

            if not str(row["currency"] or "").strip():
                self._record_currency_code_findings.append(
                    AuditFinding(
                        check="currency_codes",
                        severity=AuditSeverity.WARNING,
                        message=f"Record id={record_id} has empty currency code.",
                    )
                )

            transfer_id = row["transfer_id"]
            if transfer_id is not None:
                transfer_id_int = int(transfer_id)
                self._transfer_linked_records.setdefault(transfer_id_int, []).append(
                    {
                        "id": record_id,
                        "type": str(row["type"]),
                        "date": raw_date,
                        "wallet_id": int(row["wallet_id"]),
                        "transfer_id": transfer_id_int,
                        "amount_original": amount_original,
                        "currency": str(row["currency"]),
                        "rate_at_operation": rate_at_operation,
                        "amount_kzt": amount_kzt,
                        "category": str(row["category"] or ""),
                    }
                )

    def _check_system_wallet_sanity(self) -> list[AuditFinding]:
        wallet_by_id = {int(row.get("id", 0) or 0): row for row in self._wallet_rows}
        system_wallet = wallet_by_id.get(1)

        findings: list[AuditFinding] = []
        if system_wallet is None:
            findings.append(
                AuditFinding(
                    check="system_wallet_sanity",
                    severity=AuditSeverity.ERROR,
                    message="System wallet id=1 is missing.",
                )
            )
        else:
            if int(system_wallet.get("system", 0) or 0) != 1:
                findings.append(
                    AuditFinding(
                        check="system_wallet_sanity",
                        severity=AuditSeverity.ERROR,
                        message="System wallet id=1 must have system=1.",
                        detail=f"system={system_wallet.get('system')}",
                    )
                )

        system_wallet_ids = [
            int(row.get("id", 0) or 0)
            for row in self._wallet_rows
            if int(row.get("system", 0) or 0) == 1
        ]
        if len(system_wallet_ids) > 1:
            findings.append(
                AuditFinding(
                    check="system_wallet_sanity",
                    severity=AuditSeverity.WARNING,
                    message="Multiple system wallets detected.",
                    detail=f"ids={sorted(system_wallet_ids)}",
                )
            )

        if findings:
            return findings
        return [
            AuditFinding(
                check="system_wallet_sanity",
                severity=AuditSeverity.OK,
                message="System wallet sanity OK.",
            )
        ]

    def _check_transfer_pair_integrity(self) -> list[AuditFinding]:
        transfer_ids = {int(transfer["id"]) for transfer in self._transfer_rows}
        findings: list[AuditFinding] = []

        for transfer_id in sorted(transfer_ids):
            linked = [
                record
                for record in self._transfer_linked_records.get(transfer_id, [])
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

        for transfer_id in sorted(self._transfer_linked_records):
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
        findings: list[AuditFinding] = []
        for transfer in self._transfer_rows:
            transfer_id = int(transfer["id"])
            linked = [
                record
                for record in self._transfer_linked_records.get(transfer_id, [])
                if str(record.get("category", "") or "").strip().lower() != "commission"
            ]
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

    def _check_transfer_record_invariants(self) -> list[AuditFinding]:
        transfers = {int(row.get("id", 0) or 0): row for row in self._transfer_rows}
        findings: list[AuditFinding] = []

        for transfer_id, linked_records in self._transfer_linked_records.items():
            transfer = transfers.get(int(transfer_id))
            if transfer is None:
                continue

            for record in linked_records:
                category = str(record.get("category", "") or "").strip()
                category_lc = category.lower()
                if category_lc == "commission":
                    continue
                if category_lc != "transfer":
                    findings.append(
                        AuditFinding(
                            check="transfer_record_invariants",
                            severity=AuditSeverity.ERROR,
                            message=(
                                f"Record id={record['id']} is transfer-linked but has "
                                "non-Transfer category."
                            ),
                            detail=f"category={category!r}",
                        )
                    )

                record_type = str(record.get("type", "") or "").strip().lower()
                if record_type == "expense":
                    expected_wallet_id = int(transfer.get("from_wallet_id", 0) or 0)
                elif record_type == "income":
                    expected_wallet_id = int(transfer.get("to_wallet_id", 0) or 0)
                else:
                    continue

                actual_wallet_id = int(record.get("wallet_id", 0) or 0)
                if expected_wallet_id > 0 and actual_wallet_id != expected_wallet_id:
                    findings.append(
                        AuditFinding(
                            check="transfer_record_invariants",
                            severity=AuditSeverity.ERROR,
                            message=f"Record id={record['id']} has mismatched transfer wallet.",
                            detail=f"expected_wallet_id={expected_wallet_id}, "
                            f"wallet_id={actual_wallet_id}",
                        )
                    )

                raw_record_date = str(record.get("date", "") or "")
                raw_transfer_date = str(transfer.get("date", "") or "")
                if raw_transfer_date and raw_record_date and raw_transfer_date != raw_record_date:
                    findings.append(
                        AuditFinding(
                            check="transfer_record_invariants",
                            severity=AuditSeverity.ERROR,
                            message=f"Record id={record['id']} has mismatched transfer date.",
                            detail=f"transfer_date={raw_transfer_date!r}, "
                            f"record_date={raw_record_date!r}",
                        )
                    )

        if findings:
            return findings
        return [
            AuditFinding(
                check="transfer_record_invariants",
                severity=AuditSeverity.OK,
                message="All transfer-linked record invariants satisfied.",
            )
        ]

    def _check_amount_consistency(self) -> list[AuditFinding]:
        if self._record_amount_consistency_findings:
            return list(self._record_amount_consistency_findings)
        return [
            AuditFinding(
                check="amount_consistency",
                severity=AuditSeverity.OK,
                message="All record amounts are consistent.",
            )
        ]

    def _check_amount_positivity(self) -> list[AuditFinding]:
        findings: list[AuditFinding] = list(self._record_amount_positivity_findings)

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
        if self._record_rate_positivity_findings:
            return list(self._record_rate_positivity_findings)
        return [
            AuditFinding(
                check="rate_positivity",
                severity=AuditSeverity.OK,
                message="All rates positive.",
            )
        ]

    def _check_date_validity(self) -> list[AuditFinding]:
        if self._record_date_validity_findings:
            return list(self._record_date_validity_findings)
        return [
            AuditFinding(
                check="date_validity",
                severity=AuditSeverity.OK,
                message="All record dates are valid.",
            )
        ]

    def _check_currency_codes(self) -> list[AuditFinding]:
        findings: list[AuditFinding] = list(self._record_currency_code_findings)
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

    def _check_mandatory_template_date_and_autopay(self) -> list[AuditFinding]:
        findings: list[AuditFinding] = []
        for expense in self._mandatory_expense_rows:
            raw_date = expense.get("date")
            normalized_date = str(raw_date or "").strip()
            if normalized_date:
                try:
                    parse_ymd(normalized_date)
                except ValueError as error:
                    findings.append(
                        AuditFinding(
                            check="mandatory_template_date_and_autopay",
                            severity=AuditSeverity.ERROR,
                            message=f"Mandatory expense id={expense['id']} has invalid date.",
                            detail=f"{normalized_date}: {error}",
                        )
                    )

            expected_auto_pay = bool(normalized_date)
            actual_auto_pay = bool(int(expense.get("auto_pay", 0) or 0))
            if expected_auto_pay != actual_auto_pay:
                findings.append(
                    AuditFinding(
                        check="mandatory_template_date_and_autopay",
                        severity=AuditSeverity.ERROR,
                        message=(
                            f"Mandatory expense id={expense['id']} has inconsistent auto_pay."
                        ),
                        detail=(
                            f"date={normalized_date!r}, "
                            f"auto_pay={int(expense.get('auto_pay', 0) or 0)}"
                        ),
                    )
                )

        if findings:
            return findings
        return [
            AuditFinding(
                check="mandatory_template_date_and_autopay",
                severity=AuditSeverity.OK,
                message="All mandatory template dates and auto_pay flags consistent.",
            )
        ]

    def _read_mandatory_expense_rows(self) -> list[dict[str, Any]]:
        rows = self._repo.query_all(
            """
            SELECT id, amount_original, amount_kzt, category, description, date, auto_pay
            FROM mandatory_expenses
            ORDER BY id
            """
        )
        return [dict(row) for row in rows]

    def _read_wallet_rows(self) -> list[dict[str, Any]]:
        rows = self._repo.query_all("SELECT id, system, is_active FROM wallets ORDER BY id")
        return [dict(row) for row in rows]

    def _read_transfer_rows(self) -> list[dict[str, Any]]:
        rows = self._repo.query_all(
            """
            SELECT
                id,
                from_wallet_id,
                to_wallet_id,
                date,
                amount_original,
                currency,
                rate_at_operation,
                amount_kzt
            FROM transfers
            ORDER BY id
            """
        )
        return [dict(row) for row in rows]
