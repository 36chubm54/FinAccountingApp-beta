from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass, replace
from typing import Any

from app.finance_service import FinanceService
from domain.import_policy import ImportPolicy
from domain.import_result import ImportResult
from domain.records import ExpenseRecord, IncomeRecord, MandatoryExpenseRecord, Record
from domain.transfers import Transfer
from domain.wallets import Wallet
from services.import_parser import ParsedImportData, parse_import_file
from utils.csv_utils import parse_transfer_row
from utils.import_core import (
    as_float,
    parse_import_row,
    parse_optional_strict_int,
    safe_type,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ImportCounters:
    wallets: int = 0
    records: int = 0
    transfers: int = 0


@dataclass(frozen=True)
class PreparedImportPayload:
    parsed: ParsedImportData
    initial_balance: float
    wallets: list[Wallet]
    parsed_records: list[Record]
    parsed_mandatory_templates: list[MandatoryExpenseRecord]
    raw_transfer_ops: list[dict[str, Any]]
    imported: int
    skipped: int
    errors: list[str]


class ImportService:
    def __init__(
        self,
        finance_service: FinanceService,
        *,
        policy: ImportPolicy = ImportPolicy.FULL_BACKUP,
    ) -> None:
        self._finance_service = finance_service
        self._policy = policy

    def import_file(self, path: str, *, force: bool = False, dry_run: bool = False) -> ImportResult:
        parsed = parse_import_file(path, force=force)
        prepared = self._prepare_records_payload(parsed)
        if dry_run:
            return ImportResult(
                imported=prepared.imported,
                skipped=prepared.skipped,
                errors=tuple(prepared.errors),
                dry_run=True,
            )
        return self._finance_service.run_import_transaction(
            lambda: self._commit_prepared_records_payload(prepared)
        )

    def import_mandatory_file(self, path: str) -> ImportResult:
        parsed = parse_import_file(path)
        return self._finance_service.run_import_transaction(
            lambda: self._import_mandatory_payload(parsed)
        )

    def _prepare_records_payload(self, parsed: ParsedImportData) -> PreparedImportPayload:
        initial_balance = (
            float(parsed.initial_balance)
            if parsed.initial_balance is not None
            else float(self._finance_service.get_system_initial_balance())
        )
        wallets = self._wallets_from_payload(parsed.wallets) if parsed.wallets else []
        if wallets:
            wallets, wallet_id_map = self._normalize_wallet_ids(wallets)
            parsed = self._remap_parsed_wallet_ids(parsed, wallet_id_map)
        _ = len(wallets)

        wallet_ids = (
            {wallet.id for wallet in wallets}
            if wallets
            else {wallet.id for wallet in self._finance_service.load_wallets()}
        )
        get_rate = (
            self._finance_service.get_currency_rate
            if self._policy == ImportPolicy.CURRENT_RATE
            else None
        )

        raw_transfer_ops: list[dict[str, Any]] = []
        parsed_records: list[Record] = []
        parsed_mandatory_templates: list[MandatoryExpenseRecord] = []
        errors: list[str] = []
        skipped = 0
        imported = 0
        seen_initial_balance = parsed.initial_balance is not None

        next_transfer_id = 1
        for index, row in enumerate(parsed.rows, start=2):
            row_type = safe_type(str(row.get("type", "") or "")).lower()
            row_label = f"row {index}"
            if row_type == "transfer":
                parsed_row, transfer, next_transfer_id, error = parse_transfer_row(
                    {str(k): str(v) if v is not None else "" for k, v in row.items()},
                    row_label=row_label,
                    policy=self._policy,
                    get_rate=get_rate,
                    next_transfer_id=next_transfer_id,
                    wallet_ids=wallet_ids,
                )
                if error:
                    skipped += 1
                    errors.append(error)
                    continue
                if transfer is None or parsed_row is None:
                    skipped += 1
                    errors.append(f"{row_label}: failed to parse transfer row")
                    continue
                raw_transfer_ops.append(
                    {
                        "transfer_id": int(transfer.id),
                        "from_wallet_id": transfer.from_wallet_id,
                        "to_wallet_id": transfer.to_wallet_id,
                        "transfer_date": str(transfer.date),
                        "amount": float(transfer.amount_original),
                        "amount_kzt": float(transfer.amount_kzt),
                        "currency": str(transfer.currency).upper(),
                        "rate_at_operation": float(transfer.rate_at_operation),
                        "description": str(transfer.description or ""),
                    }
                )
                imported += 1
                continue

            record, parsed_balance, error = parse_import_row(
                row,
                row_label=row_label,
                policy=self._policy,
                get_rate=get_rate,
                mandatory_only=False,
            )
            if error:
                skipped += 1
                errors.append(error)
                continue
            if parsed_balance is not None:
                if seen_initial_balance:
                    skipped += 1
                    errors.append(f"{row_label}: duplicate initial_balance row")
                    continue
                initial_balance = float(parsed_balance)
                seen_initial_balance = True
                continue
            if record is None:
                continue
            if record.wallet_id not in wallet_ids:
                skipped += 1
                errors.append(f"{row_label}: wallet not found ({record.wallet_id})")
                continue
            parsed_records.append(record)
            imported += 1

        for index, row in enumerate(parsed.mandatory_rows, start=2):
            payload = dict(row)
            if not str(payload.get("type", "") or "").strip():
                payload["type"] = "mandatory_expense"
            record, _, error = parse_import_row(
                payload,
                row_label=f"mandatory[{index}]",
                policy=self._policy,
                get_rate=get_rate,
                mandatory_only=True,
            )
            if error:
                skipped += 1
                errors.append(error)
                continue
            if isinstance(record, MandatoryExpenseRecord):
                parsed_mandatory_templates.append(record)
                imported += 1

        return PreparedImportPayload(
            parsed=parsed,
            initial_balance=initial_balance,
            wallets=wallets,
            parsed_records=parsed_records,
            parsed_mandatory_templates=parsed_mandatory_templates,
            raw_transfer_ops=raw_transfer_ops,
            imported=imported,
            skipped=skipped,
            errors=errors,
        )

    def _commit_prepared_records_payload(self, prepared: PreparedImportPayload) -> ImportResult:
        parsed = prepared.parsed
        initial_balance = prepared.initial_balance
        wallets = list(prepared.wallets)
        imported_wallets = len(wallets)
        parsed_records = list(prepared.parsed_records)
        parsed_mandatory_templates = list(prepared.parsed_mandatory_templates)
        raw_transfer_ops = list(prepared.raw_transfer_ops)
        imported = prepared.imported
        skipped = prepared.skipped
        errors = tuple(prepared.errors)

        if (
            imported == 0
            and not wallets
            and not parsed_mandatory_templates
            and not raw_transfer_ops
        ):
            return ImportResult(imported=0, skipped=skipped, errors=errors)

        replace_all_for_import = getattr(self._finance_service, "replace_all_for_import", None)
        fast_replace_enabled = (
            getattr(self._finance_service, "supports_bulk_import_replace", False) is True
        )
        if (
            fast_replace_enabled
            and callable(replace_all_for_import)
            and self._policy != ImportPolicy.CURRENT_RATE
        ):
            target_wallets = wallets if wallets else None
            if target_wallets:
                wallet_ids = {wallet.id for wallet in target_wallets}
            else:
                wallet_ids = {wallet.id for wallet in self._finance_service.load_wallets()}

            self._ensure_wallets_exist(parsed_records, raw_transfer_ops, wallet_ids)
            records, transfers, counters = self._build_import_operations(
                parsed_records=parsed_records,
                transfer_rows=raw_transfer_ops,
                counters=ImportCounters(wallets=imported_wallets),
            )
            mandatory_templates = self._normalize_mandatory_templates(parsed_mandatory_templates)
            replace_all_for_import(
                wallets=target_wallets,
                initial_balance=initial_balance,
                records=records,
                transfers=transfers,
                mandatory_templates=mandatory_templates,
                preserve_existing_mandatory=not bool(target_wallets),
            )
            logger.info(
                "Import completed (bulk) file=%s wallets=%s records=%s transfers=%s",
                parsed.path,
                counters.wallets,
                counters.records,
                counters.transfers,
            )
            return ImportResult(imported=imported, skipped=skipped, errors=errors)

        if wallets:
            self._finance_service.reset_all_for_import(
                wallets=wallets, initial_balance=initial_balance
            )
            wallet_ids = {wallet.id for wallet in wallets}
        else:
            self._finance_service.reset_operations_for_import(initial_balance=initial_balance)
            wallet_ids = {wallet.id for wallet in self._finance_service.load_wallets()}

        self._ensure_wallets_exist(parsed_records, raw_transfer_ops, wallet_ids)
        counters = ImportCounters(wallets=imported_wallets)
        counters = self._apply_operations_with_relaxed_wallet_limits(
            parsed_records=parsed_records,
            transfer_rows=raw_transfer_ops,
            counters=counters,
        )
        self._apply_mandatory_templates(parsed_mandatory_templates)

        logger.info(
            "Import completed file=%s wallets=%s records=%s transfers=%s",
            parsed.path,
            counters.wallets,
            counters.records,
            counters.transfers,
        )
        self._finance_service.normalize_operation_ids_for_import()
        return ImportResult(imported=imported, skipped=skipped, errors=errors)

    def _build_import_operations(
        self,
        *,
        parsed_records: list[Record],
        transfer_rows: list[dict[str, Any]],
        counters: ImportCounters,
    ) -> tuple[list[Record], list[Transfer], ImportCounters]:
        records: list[Record] = []
        transfers: list[Transfer] = []
        next_record_id = 1
        next_transfer_id = 1

        for record in self._sort_records_for_import(parsed_records):
            if record.transfer_id is not None:
                continue
            records.append(replace(record, id=next_record_id, transfer_id=None))
            next_record_id += 1

        transfer_records: dict[int, list[Record]] = defaultdict(list)
        for record in parsed_records:
            if record.transfer_id is not None:
                transfer_records[int(record.transfer_id)].append(record)

        transfers_count = counters.transfers
        for _transfer_id, linked in sorted(
            transfer_records.items(), key=lambda item: self._record_sort_key(item[1][0])
        ):
            if len(linked) != 2:
                raise ValueError(
                    f"Transfer integrity violated: expected 2 linked records (got {len(linked)})"
                )
            source = next((item for item in linked if isinstance(item, ExpenseRecord)), None)
            target = next((item for item in linked if isinstance(item, IncomeRecord)), None)
            if source is None or target is None:
                raise ValueError("Transfer integrity violated: requires one expense and one income")
            if source.wallet_id == target.wallet_id:
                raise ValueError("Transfer integrity violated: wallets must be different")

            transfer = Transfer(
                id=next_transfer_id,
                from_wallet_id=int(source.wallet_id),
                to_wallet_id=int(target.wallet_id),
                date=str(source.date),
                amount_original=float(source.amount_original or 0.0),
                currency=str(source.currency).upper(),
                rate_at_operation=float(source.rate_at_operation),
                amount_kzt=float(source.amount_kzt or 0.0),
                description=str(source.description or ""),
            )
            transfers.append(transfer)
            records.append(
                ExpenseRecord(
                    id=next_record_id,
                    date=str(source.date),
                    wallet_id=int(source.wallet_id),
                    transfer_id=int(transfer.id),
                    amount_original=float(source.amount_original or 0.0),
                    currency=str(source.currency).upper(),
                    rate_at_operation=float(source.rate_at_operation),
                    amount_kzt=float(source.amount_kzt or 0.0),
                    category="Transfer",
                )
            )
            next_record_id += 1
            records.append(
                IncomeRecord(
                    id=next_record_id,
                    date=str(source.date),
                    wallet_id=int(target.wallet_id),
                    transfer_id=int(transfer.id),
                    amount_original=float(source.amount_original or 0.0),
                    currency=str(source.currency).upper(),
                    rate_at_operation=float(source.rate_at_operation),
                    amount_kzt=float(source.amount_kzt or 0.0),
                    category="Transfer",
                )
            )
            next_record_id += 1
            next_transfer_id += 1
            transfers_count += 1

        grouped_ids = {
            int(record.transfer_id)
            for record in parsed_records
            if isinstance(record.transfer_id, int) and record.transfer_id > 0
        }
        for transfer_row in sorted(transfer_rows, key=self._transfer_row_sort_key):
            if int(transfer_row["transfer_id"]) in grouped_ids:
                continue
            transfer = Transfer(
                id=next_transfer_id,
                from_wallet_id=int(transfer_row["from_wallet_id"]),
                to_wallet_id=int(transfer_row["to_wallet_id"]),
                date=str(transfer_row["transfer_date"]),
                amount_original=float(transfer_row["amount"]),
                currency=str(transfer_row["currency"]).upper(),
                rate_at_operation=float(transfer_row["rate_at_operation"]),
                amount_kzt=float(transfer_row["amount_kzt"]),
                description=str(transfer_row.get("description", "")),
            )
            transfers.append(transfer)
            records.append(
                ExpenseRecord(
                    id=next_record_id,
                    date=str(transfer.date),
                    wallet_id=int(transfer.from_wallet_id),
                    transfer_id=int(transfer.id),
                    amount_original=float(transfer.amount_original),
                    currency=str(transfer.currency).upper(),
                    rate_at_operation=float(transfer.rate_at_operation),
                    amount_kzt=float(transfer.amount_kzt),
                    category="Transfer",
                )
            )
            next_record_id += 1
            records.append(
                IncomeRecord(
                    id=next_record_id,
                    date=str(transfer.date),
                    wallet_id=int(transfer.to_wallet_id),
                    transfer_id=int(transfer.id),
                    amount_original=float(transfer.amount_original),
                    currency=str(transfer.currency).upper(),
                    rate_at_operation=float(transfer.rate_at_operation),
                    amount_kzt=float(transfer.amount_kzt),
                    category="Transfer",
                )
            )
            next_record_id += 1
            next_transfer_id += 1
            transfers_count += 1

        return (
            records,
            transfers,
            ImportCounters(
                wallets=counters.wallets,
                records=len(records),
                transfers=transfers_count,
            ),
        )

    def _normalize_mandatory_templates(
        self, templates: list[MandatoryExpenseRecord]
    ) -> list[MandatoryExpenseRecord]:
        normalized: list[MandatoryExpenseRecord] = []
        for index, template in enumerate(templates, start=1):
            description = self._normalize_mandatory_description(
                str(template.description or ""),
                str(template.category),
            )
            normalized.append(
                MandatoryExpenseRecord(
                    id=index,
                    wallet_id=int(template.wallet_id),
                    date=str(template.date or ""),
                    amount_original=float(template.amount_original or 0.0),
                    currency=str(template.currency).upper(),
                    rate_at_operation=float(template.rate_at_operation),
                    amount_kzt=float(template.amount_kzt or 0.0),
                    category=str(template.category),
                    description=description,
                    period=str(template.period),  # type: ignore[arg-type]
                    auto_pay=bool(str(template.date or "").strip()),
                )
            )
        return normalized

    def _apply_operations_with_relaxed_wallet_limits(
        self,
        *,
        parsed_records: list[Record],
        transfer_rows: list[dict[str, Any]],
        counters: ImportCounters,
    ) -> ImportCounters:
        wallet_ids: set[int] = set()
        for record in parsed_records:
            wallet_ids.add(int(record.wallet_id))
        for transfer in transfer_rows:
            wallet_ids.add(int(transfer["from_wallet_id"]))
            wallet_ids.add(int(transfer["to_wallet_id"]))

        wallets = {wallet.id: wallet for wallet in self._finance_service.load_wallets()}
        changed_wallet_ids: set[int] = set()
        for wallet_id in sorted(wallet_ids):
            wallet = wallets.get(wallet_id)
            if wallet is None or wallet.allow_negative:
                continue
            self._finance_service.set_wallet_allow_negative_for_import(wallet_id, True)
            changed_wallet_ids.add(wallet_id)

        try:
            result = self._apply_records(parsed_records, counters)
            result = self._apply_grouped_transfers(parsed_records, result)
            result = self._apply_transfer_rows(transfer_rows, result, parsed_records)
            return result
        finally:
            for wallet_id in sorted(changed_wallet_ids):
                self._finance_service.set_wallet_allow_negative_for_import(wallet_id, False)

    def _apply_mandatory_templates(self, templates: list[MandatoryExpenseRecord]) -> None:
        wallet_ids = {int(wallet.id) for wallet in self._finance_service.load_wallets()}
        for template in templates:
            if int(template.wallet_id) not in wallet_ids:
                raise ValueError(
                    f"Mandatory template references missing wallet: {template.wallet_id}"
                )
            description = self._normalize_mandatory_description(
                str(template.description or ""),
                str(template.category),
            )
            self._finance_service.create_mandatory_expense(
                amount=float(template.amount_original or 0.0),
                currency=str(template.currency).upper(),
                wallet_id=int(template.wallet_id),
                category=str(template.category),
                description=description,
                period=str(template.period),
                date=str(template.date or ""),
                amount_kzt=self._fixed_amount_kzt(template.amount_kzt),
                rate_at_operation=self._fixed_rate(template.rate_at_operation),
            )

    def _import_mandatory_payload(self, parsed: ParsedImportData) -> ImportResult:
        source_rows = parsed.mandatory_rows if parsed.file_type == "json" else parsed.rows
        self._finance_service.reset_mandatory_for_import()
        get_rate = (
            self._finance_service.get_currency_rate
            if self._policy == ImportPolicy.CURRENT_RATE
            else None
        )
        wallet_ids = {int(wallet.id) for wallet in self._finance_service.load_wallets()}

        imported = 0
        skipped = 0
        errors: list[str] = []
        for index, row in enumerate(source_rows, start=2):
            record, _, error = parse_import_row(
                row,
                row_label=f"row {index}",
                policy=self._policy,
                get_rate=get_rate,
                mandatory_only=True,
            )
            if error:
                skipped += 1
                errors.append(error)
                continue
            if not isinstance(record, MandatoryExpenseRecord):
                skipped += 1
                errors.append(f"row {index}: expected mandatory expense")
                continue
            if int(record.wallet_id) not in wallet_ids:
                skipped += 1
                errors.append(f"row {index}: wallet not found ({int(record.wallet_id)})")
                continue
            description = self._normalize_mandatory_description(
                str(record.description or ""),
                str(record.category),
            )
            self._finance_service.create_mandatory_expense(
                amount=float(record.amount_original or 0.0),
                currency=str(record.currency).upper(),
                wallet_id=int(record.wallet_id),
                category=str(record.category),
                description=description,
                period=str(record.period),
                date=str(record.date or ""),
                amount_kzt=self._fixed_amount_kzt(record.amount_kzt),
                rate_at_operation=self._fixed_rate(record.rate_at_operation),
            )
            imported += 1
        logger.info(
            "Mandatory import completed file=%s wallets=0 records=0 transfers=0 templates=%s",
            parsed.path,
            imported,
        )
        return ImportResult(imported=imported, skipped=skipped, errors=tuple(errors))

    def _apply_records(
        self, parsed_records: list[Record], counters: ImportCounters
    ) -> ImportCounters:
        records_count = counters.records
        for record in self._sort_records_for_import(parsed_records):
            if record.transfer_id is not None:
                continue
            if isinstance(record, IncomeRecord):
                self._finance_service.create_income(
                    date=str(record.date),
                    wallet_id=int(record.wallet_id),
                    amount=float(record.amount_original or 0.0),
                    currency=str(record.currency).upper(),
                    category=str(record.category),
                    description=str(record.description or ""),
                    amount_kzt=self._fixed_amount_kzt(record.amount_kzt),
                    rate_at_operation=self._fixed_rate(record.rate_at_operation),
                )
                records_count += 1
                continue
            if isinstance(record, MandatoryExpenseRecord):
                description = self._normalize_mandatory_description(
                    str(record.description or ""),
                    str(record.category),
                )
                self._finance_service.create_mandatory_expense_record(
                    date=str(record.date),
                    wallet_id=int(record.wallet_id),
                    amount=float(record.amount_original or 0.0),
                    currency=str(record.currency).upper(),
                    category=str(record.category),
                    description=description,
                    period=str(record.period),
                    amount_kzt=self._fixed_amount_kzt(record.amount_kzt),
                    rate_at_operation=self._fixed_rate(record.rate_at_operation),
                )
                records_count += 1
                continue
            self._finance_service.create_expense(
                date=str(record.date),
                wallet_id=int(record.wallet_id),
                amount=float(record.amount_original or 0.0),
                currency=str(record.currency).upper(),
                category=str(record.category),
                description=str(record.description or ""),
                amount_kzt=self._fixed_amount_kzt(record.amount_kzt),
                rate_at_operation=self._fixed_rate(record.rate_at_operation),
            )
            records_count += 1
        return ImportCounters(
            wallets=counters.wallets,
            records=records_count,
            transfers=counters.transfers,
        )

    def _apply_grouped_transfers(
        self,
        parsed_records: list[Record],
        counters: ImportCounters,
    ) -> ImportCounters:
        transfer_records: dict[int, list[Record]] = defaultdict(list)
        for record in parsed_records:
            if record.transfer_id is None:
                continue
            transfer_records[int(record.transfer_id)].append(record)

        transfers_count = counters.transfers
        for transfer_id, linked in sorted(
            transfer_records.items(), key=lambda item: self._record_sort_key(item[1][0])
        ):
            if len(linked) != 2:
                raise ValueError(
                    f"Transfer integrity violated for #{transfer_id}: expected 2 linked records"
                )
            source = next((item for item in linked if isinstance(item, ExpenseRecord)), None)
            target = next((item for item in linked if isinstance(item, IncomeRecord)), None)
            if source is None or target is None:
                raise ValueError(
                    f"Transfer integrity violated for #{transfer_id}: "
                    "requires one expense and one income"
                )
            if source.wallet_id == target.wallet_id:
                raise ValueError(
                    f"Transfer integrity violated for #{transfer_id}: wallets must be different"
                )
            if str(source.date) != str(target.date):
                raise ValueError(f"Transfer integrity violated for #{transfer_id}: date mismatch")
            if str(source.currency).upper() != str(target.currency).upper():
                raise ValueError(
                    f"Transfer integrity violated for #{transfer_id}: currency mismatch"
                )
            source_amount = float(source.amount_original or 0.0)
            target_amount = float(target.amount_original or 0.0)
            if abs(source_amount - target_amount) > 1e-9:
                raise ValueError(
                    f"Transfer integrity violated for #{transfer_id}: amount_original mismatch"
                )

            self._finance_service.create_transfer(
                from_wallet_id=int(source.wallet_id),
                to_wallet_id=int(target.wallet_id),
                transfer_date=str(source.date),
                amount=source_amount,
                currency=str(source.currency).upper(),
                description=str(source.description or ""),
                amount_kzt=self._fixed_amount_kzt(source.amount_kzt),
                rate_at_operation=self._fixed_rate(source.rate_at_operation),
            )
            transfers_count += 1
        return ImportCounters(
            wallets=counters.wallets,
            records=counters.records,
            transfers=transfers_count,
        )

    def _apply_transfer_rows(
        self,
        transfer_rows: list[dict[str, Any]],
        counters: ImportCounters,
        parsed_records: list[Record],
    ) -> ImportCounters:
        transfers_count = counters.transfers
        grouped_ids = {
            int(record.transfer_id)
            for record in parsed_records
            if isinstance(record.transfer_id, int) and record.transfer_id > 0
        }
        for transfer in sorted(transfer_rows, key=self._transfer_row_sort_key):
            if int(transfer["transfer_id"]) in grouped_ids:
                continue
            self._finance_service.create_transfer(
                from_wallet_id=int(transfer["from_wallet_id"]),
                to_wallet_id=int(transfer["to_wallet_id"]),
                transfer_date=str(transfer["transfer_date"]),
                amount=float(transfer["amount"]),
                currency=str(transfer["currency"]).upper(),
                description=str(transfer.get("description", "")),
                amount_kzt=self._fixed_amount_kzt(float(transfer["amount_kzt"])),
                rate_at_operation=self._fixed_rate(float(transfer["rate_at_operation"])),
            )
            transfers_count += 1
        return ImportCounters(
            wallets=counters.wallets,
            records=counters.records,
            transfers=transfers_count,
        )

    @staticmethod
    def _ensure_wallets_exist(
        parsed_records: list[Record],
        transfer_rows: list[dict[str, Any]],
        wallet_ids: set[int],
    ) -> None:
        for record in parsed_records:
            if int(record.wallet_id) not in wallet_ids:
                raise ValueError(f"Wallet not found during import: {record.wallet_id}")
        for transfer in transfer_rows:
            from_wallet_id = int(transfer["from_wallet_id"])
            to_wallet_id = int(transfer["to_wallet_id"])
            if from_wallet_id not in wallet_ids:
                raise ValueError(f"Wallet not found during import: {from_wallet_id}")
            if to_wallet_id not in wallet_ids:
                raise ValueError(f"Wallet not found during import: {to_wallet_id}")

    @staticmethod
    def _wallets_from_payload(raw_wallets: list[dict[str, Any]]) -> list[Wallet]:
        wallets: list[Wallet] = []
        for item in raw_wallets:
            wallet_id = parse_optional_strict_int(item.get("id"))
            if item.get("id") not in (None, "") and wallet_id is None:
                raise ValueError(f"Invalid wallet id in import payload: {item.get('id')}")
            wallet_id = wallet_id or 0
            if wallet_id <= 0:
                continue
            wallets.append(
                Wallet(
                    id=wallet_id,
                    name=str(item.get("name", "") or f"Wallet {wallet_id}"),
                    currency=str(item.get("currency", "KZT") or "KZT").upper(),
                    initial_balance=float(as_float(item.get("initial_balance"), 0.0) or 0.0),
                    system=bool(item.get("system", wallet_id == 1)),
                    allow_negative=bool(item.get("allow_negative", False)),
                    is_active=bool(item.get("is_active", True)),
                )
            )
        if not wallets:
            wallets = [
                Wallet(
                    id=1,
                    name="Main wallet",
                    currency="KZT",
                    initial_balance=0.0,
                    system=True,
                    allow_negative=False,
                    is_active=True,
                )
            ]
        return wallets

    @staticmethod
    def _normalize_wallet_ids(wallets: list[Wallet]) -> tuple[list[Wallet], dict[int, int]]:
        normalized: list[Wallet] = []
        wallet_id_map: dict[int, int] = {}
        for new_id, wallet in enumerate(sorted(wallets, key=lambda item: int(item.id)), start=1):
            wallet_id_map[int(wallet.id)] = new_id
            normalized.append(
                replace(
                    wallet,
                    id=new_id,
                    system=bool(wallet.system) or new_id == 1,
                )
            )
        if normalized and not any(wallet.system for wallet in normalized):
            normalized[0] = replace(normalized[0], system=True)
        return normalized, wallet_id_map

    @classmethod
    def _remap_parsed_wallet_ids(
        cls,
        parsed: ParsedImportData,
        wallet_id_map: dict[int, int],
    ) -> ParsedImportData:
        rows = [
            cls._remap_wallet_ids_in_row(
                row,
                wallet_id_map,
                fields=("wallet_id", "from_wallet_id", "to_wallet_id"),
            )
            for row in parsed.rows
        ]
        mandatory_rows = [
            cls._remap_wallet_ids_in_row(row, wallet_id_map, fields=("wallet_id",))
            for row in parsed.mandatory_rows
        ]
        wallets = [
            cls._remap_wallet_ids_in_row(wallet, wallet_id_map, fields=("id",))
            for wallet in parsed.wallets
        ]
        return ParsedImportData(
            path=parsed.path,
            file_type=parsed.file_type,
            rows=rows,
            mandatory_rows=mandatory_rows,
            wallets=wallets,
            initial_balance=parsed.initial_balance,
        )

    @staticmethod
    def _remap_wallet_ids_in_row(
        row: dict[str, Any],
        wallet_id_map: dict[int, int],
        *,
        fields: tuple[str, ...],
    ) -> dict[str, Any]:
        remapped = dict(row)
        for field in fields:
            value = remapped.get(field)
            mapped = ImportService._map_wallet_id(value, wallet_id_map)
            if mapped is not None:
                remapped[field] = mapped
        return remapped

    @staticmethod
    def _map_wallet_id(value: Any, wallet_id_map: dict[int, int]) -> int | None:
        wallet_id = parse_optional_strict_int(value)
        if value not in (None, "") and wallet_id is None:
            raise ValueError(f"Invalid wallet id in import payload: {value}")
        wallet_id = wallet_id or 0
        if wallet_id <= 0:
            return None
        return wallet_id_map.get(wallet_id, wallet_id)

    @staticmethod
    def _build_error(errors: list[str]) -> str:
        details = "; ".join(errors[:3])
        if len(errors) > 3:
            details += f"; ... and {len(errors) - 3} more"
        return f"Import aborted: {len(errors)} invalid rows ({details})"

    @staticmethod
    def _normalize_mandatory_description(description: str, category: str) -> str:
        normalized = description.strip()
        if normalized:
            return normalized
        category_name = (category or "").strip()
        if category_name:
            return f"Imported {category_name}"
        return "Imported mandatory expense"

    def _fixed_amount_kzt(self, amount_kzt: float | None) -> float | None:
        if self._policy == ImportPolicy.CURRENT_RATE:
            return None
        if amount_kzt is None:
            return None
        return float(amount_kzt)

    def _fixed_rate(self, rate_at_operation: float | None) -> float | None:
        if self._policy == ImportPolicy.CURRENT_RATE:
            return None
        if rate_at_operation is None:
            return None
        return float(rate_at_operation)

    @staticmethod
    def _record_sort_key(record: Record) -> tuple[str, int, int]:
        date_value = str(record.date)
        if isinstance(record, IncomeRecord):
            priority = 0
        elif isinstance(record, MandatoryExpenseRecord):
            priority = 1
        else:
            priority = 2
        return (date_value, priority, int(record.id))

    @classmethod
    def _sort_records_for_import(cls, records: list[Record]) -> list[Record]:
        return sorted(records, key=cls._record_sort_key)

    @staticmethod
    def _transfer_row_sort_key(transfer: dict[str, Any]) -> tuple[str, int]:
        return (str(transfer.get("transfer_date", "")), int(transfer.get("transfer_id", 0)))
