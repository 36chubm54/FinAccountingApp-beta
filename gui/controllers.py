from __future__ import annotations

import logging
from collections.abc import Iterable
from dataclasses import dataclass, replace
from hashlib import sha1

from app.record_service import RecordService
from app.services import CurrencyService
from app.use_cases import (
    AddMandatoryExpenseToReport,
    CalculateNetWorth,
    CalculateWalletBalance,
    CreateExpense,
    CreateIncome,
    CreateMandatoryExpense,
    CreateMandatoryExpenseRecord,
    CreateTransfer,
    CreateWallet,
    DeleteAllMandatoryExpenses,
    DeleteAllRecords,
    DeleteMandatoryExpense,
    DeleteRecord,
    DeleteTransfer,
    GenerateReport,
    GetActiveWallets,
    GetMandatoryExpenses,
    GetWallets,
    SoftDeleteWallet,
)
from domain.import_policy import ImportPolicy
from domain.records import IncomeRecord, MandatoryExpenseRecord, Record
from domain.reports import Report
from domain.transfers import Transfer
from domain.validation import parse_ymd
from domain.wallets import Wallet
from infrastructure.repositories import RecordRepository
from services.import_service import ImportService

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RecordListItem:
    record_id: str
    repository_index: int
    domain_record_id: int | None
    label: str


class FinancialController:
    def __init__(self, repository: RecordRepository, currency_service: CurrencyService) -> None:
        self._repository = repository
        self._currency = currency_service
        self._record_service = RecordService(repository)
        self.supports_bulk_import_replace = True

    def build_record_list_items(self) -> list[RecordListItem]:
        records = self._repository.load_all()
        return self._build_list_items(records)

    def delete_record(self, repository_index: int) -> bool:
        return DeleteRecord(self._repository).execute(repository_index)

    def delete_transfer(self, transfer_id: int) -> None:
        DeleteTransfer(self._repository).execute(transfer_id)

    def transfer_id_by_repository_index(self, repository_index: int) -> int | None:
        records = self._repository.load_all()
        if 0 <= repository_index < len(records):
            return records[repository_index].transfer_id
        return None

    def delete_all_records(self) -> None:
        DeleteAllRecords(self._repository).execute()

    def update_record_amount_kzt(self, record_id: int, new_amount_kzt: float) -> None:
        self._record_service.update_amount_kzt(record_id, new_amount_kzt)

    def get_record_amount_kzt(self, record_id: int) -> float:
        record = self._repository.get_by_id(int(record_id))
        return float(record.amount_kzt or 0.0)

    def set_system_initial_balance(self, balance: float) -> None:
        self._repository.save_initial_balance(float(balance))

    def get_system_initial_balance(self) -> float:
        return self._repository.load_initial_balance()

    def get_currency_rate(self, currency: str) -> float:
        return float(self._currency.get_rate(currency))

    def create_income(
        self,
        *,
        date: str,
        wallet_id: int,
        amount: float,
        currency: str,
        category: str,
        description: str = "",
        amount_kzt: float | None = None,
        rate_at_operation: float | None = None,
    ) -> None:
        CreateIncome(self._repository, self._currency).execute(
            date=date,
            wallet_id=wallet_id,
            amount=amount,
            currency=currency,
            category=category,
            description=description,
            amount_kzt=amount_kzt,
            rate_at_operation=rate_at_operation,
        )

    def create_expense(
        self,
        *,
        date: str,
        wallet_id: int,
        amount: float,
        currency: str,
        category: str,
        description: str = "",
        amount_kzt: float | None = None,
        rate_at_operation: float | None = None,
    ) -> None:
        CreateExpense(self._repository, self._currency).execute(
            date=date,
            wallet_id=wallet_id,
            amount=amount,
            currency=currency,
            category=category,
            description=description,
            amount_kzt=amount_kzt,
            rate_at_operation=rate_at_operation,
        )

    def generate_report(self) -> Report:
        return GenerateReport(self._repository).execute()

    def generate_report_for_wallet(self, wallet_id: int | None):
        return GenerateReport(self._repository).execute(wallet_id=wallet_id)

    def create_mandatory_expense(
        self,
        *,
        amount: float,
        currency: str,
        category: str,
        description: str,
        period: str,
        amount_kzt: float | None = None,
        rate_at_operation: float | None = None,
    ) -> None:
        CreateMandatoryExpense(self._repository, self._currency).execute(
            amount=amount,
            currency=currency,
            category=category,
            description=description,
            period=period,
            amount_kzt=amount_kzt,
            rate_at_operation=rate_at_operation,
        )

    def create_mandatory_expense_record(
        self,
        *,
        date: str,
        wallet_id: int,
        amount: float,
        currency: str,
        category: str,
        description: str,
        period: str,
        amount_kzt: float | None = None,
        rate_at_operation: float | None = None,
    ) -> None:
        CreateMandatoryExpenseRecord(self._repository, self._currency).execute(
            date=date,
            wallet_id=wallet_id,
            amount=amount,
            currency=currency,
            category=category,
            description=description,
            period=period,
            amount_kzt=amount_kzt,
            rate_at_operation=rate_at_operation,
        )

    def load_mandatory_expenses(self) -> list[MandatoryExpenseRecord]:
        return GetMandatoryExpenses(self._repository).execute()

    def create_wallet(
        self,
        *,
        name: str,
        currency: str,
        initial_balance: float,
        allow_negative: bool,
    ):
        if not name.strip():
            raise ValueError("Wallet name is required")
        if len((currency or "").strip()) != 3:
            raise ValueError("Wallet currency must be a 3-letter code")
        return CreateWallet(self._repository).execute(
            name=name.strip(),
            currency=currency.strip().upper(),
            initial_balance=float(initial_balance),
            allow_negative=allow_negative,
        )

    def load_wallets(self):
        return GetWallets(self._repository).execute()

    def set_wallet_allow_negative_for_import(self, wallet_id: int, allow_negative: bool) -> None:
        wallets = self._repository.load_wallets()
        wallet = next((item for item in wallets if item.id == int(wallet_id)), None)
        if wallet is None:
            raise ValueError(f"Wallet not found: {wallet_id}")
        if wallet.allow_negative == bool(allow_negative):
            return
        self._repository.save_wallet(replace(wallet, allow_negative=bool(allow_negative)))

    def load_active_wallets(self):
        return GetActiveWallets(self._repository).execute()

    def soft_delete_wallet(self, wallet_id: int) -> None:
        SoftDeleteWallet(self._repository).execute(wallet_id)

    def wallet_balance(self, wallet_id: int) -> float:
        return CalculateWalletBalance(self._repository).execute(wallet_id)

    def net_worth_fixed(self) -> float:
        return CalculateNetWorth(self._repository, self._currency).execute_fixed()

    def net_worth_current(self) -> float:
        return CalculateNetWorth(self._repository, self._currency).execute_current()

    def create_transfer(
        self,
        *,
        from_wallet_id: int,
        to_wallet_id: int,
        transfer_date: str,
        amount: float,
        currency: str,
        description: str = "",
        commission_amount: float = 0.0,
        commission_currency: str | None = None,
        amount_kzt: float | None = None,
        rate_at_operation: float | None = None,
    ) -> int:
        parse_ymd(transfer_date)
        if from_wallet_id == to_wallet_id:
            raise ValueError("Source and destination wallets must be different")
        if amount <= 0:
            raise ValueError("Transfer amount must be positive")
        if commission_amount < 0:
            raise ValueError("Commission cannot be negative")
        if not (currency or "").strip():
            raise ValueError("Currency is required")
        if commission_amount > 0 and not (commission_currency or currency).strip():
            raise ValueError("Commission currency is required")
        return CreateTransfer(self._repository, self._currency).execute(
            from_wallet_id=int(from_wallet_id),
            to_wallet_id=int(to_wallet_id),
            transfer_date=transfer_date,
            amount_original=float(amount),
            currency=currency.strip().upper(),
            description=description.strip(),
            commission_amount=float(commission_amount),
            commission_currency=(commission_currency or currency).strip().upper(),
            amount_kzt=amount_kzt,
            rate_at_operation=rate_at_operation,
        )

    def add_mandatory_to_report(
        self, mandatory_index: int, record_date: str, wallet_id: int
    ) -> bool:
        return AddMandatoryExpenseToReport(self._repository).execute(
            mandatory_index, record_date, wallet_id
        )

    def delete_mandatory_expense(self, index: int) -> bool:
        return DeleteMandatoryExpense(self._repository).execute(index)

    def delete_all_mandatory_expenses(self) -> None:
        DeleteAllMandatoryExpenses(self._repository).execute()

    def reset_operations_for_import(self, *, initial_balance: float) -> None:
        self._repository.replace_records_and_transfers([], [])
        self._repository.save_initial_balance(float(initial_balance))

    def reset_mandatory_for_import(self) -> None:
        self._repository.delete_all_mandatory_expenses()

    def reset_all_for_import(self, *, wallets: list[Wallet], initial_balance: float) -> None:
        self._repository.replace_all_data(
            wallets=wallets,
            records=[],
            mandatory_expenses=[],
            transfers=[],
        )
        self._repository.save_initial_balance(float(initial_balance))

    def replace_all_for_import(
        self,
        *,
        wallets: list[Wallet] | None,
        initial_balance: float,
        records: list[Record],
        transfers: list[Transfer],
        mandatory_templates: list[MandatoryExpenseRecord],
        preserve_existing_mandatory: bool,
    ) -> None:
        target_wallets = list(wallets) if wallets else list(self._repository.load_wallets())
        target_wallets = self._wallets_with_system_initial_balance(
            target_wallets, float(initial_balance)
        )

        mandatory_payload: list[MandatoryExpenseRecord] = []
        if preserve_existing_mandatory:
            mandatory_payload.extend(self._repository.load_mandatory_expenses())
        mandatory_payload.extend(mandatory_templates)

        self._repository.replace_all_data(
            wallets=target_wallets,
            records=records,
            mandatory_expenses=mandatory_payload,
            transfers=transfers,
        )

    def run_import_transaction(self, operation):
        wallets_snapshot = self._repository.load_wallets()
        records_snapshot = self._repository.load_all()
        mandatory_snapshot = self._repository.load_mandatory_expenses()
        transfers_snapshot = self._repository.load_transfers()
        try:
            return operation()
        except Exception as import_error:
            logger.exception("Import failed, rolling back repository state")
            try:
                self._repository.replace_all_data(
                    wallets=wallets_snapshot,
                    records=records_snapshot,
                    mandatory_expenses=mandatory_snapshot,
                    transfers=transfers_snapshot,
                )
            except Exception:
                logger.exception("Rollback failed after import error")
            raise import_error

    def normalize_operation_ids_for_import(self) -> None:
        records = sorted(self._repository.load_all(), key=lambda item: int(item.id))
        transfers = sorted(self._repository.load_transfers(), key=lambda item: int(item.id))
        transfer_id_map = {int(item.id): index for index, item in enumerate(transfers, start=1)}
        normalized_transfers = [
            replace(transfer, id=transfer_id_map[int(transfer.id)]) for transfer in transfers
        ]
        normalized_records: list[Record] = []
        for index, record in enumerate(records, start=1):
            mapped_transfer_id = None
            if record.transfer_id is not None:
                mapped_transfer_id = transfer_id_map[int(record.transfer_id)]
            normalized_records.append(replace(record, id=index, transfer_id=mapped_transfer_id))
        self._repository.replace_records_and_transfers(normalized_records, normalized_transfers)

    def import_records(
        self, fmt: str, filepath: str, policy: ImportPolicy, *, force: bool = False
    ) -> tuple[int, int, list[str]]:
        if fmt not in {"CSV", "XLSX", "JSON"}:
            raise ValueError(f"Unsupported format: {fmt}")
        service = ImportService(self, policy=policy)
        if force:
            return service.import_file(filepath, force=True)
        return service.import_file(filepath)

    def import_mandatory(self, fmt: str, filepath: str) -> tuple[int, int, list[str]]:
        if fmt not in {"CSV", "XLSX", "JSON"}:
            raise ValueError(f"Unsupported format: {fmt}")
        return ImportService(self, policy=ImportPolicy.FULL_BACKUP).import_mandatory_file(filepath)

    @staticmethod
    def _ensure_import_valid(summary: tuple[int, int, list[str]]) -> None:
        _, skipped, errors = summary
        if skipped > 0:
            details = "; ".join(errors[:3]) if errors else "invalid rows"
            raise ValueError(f"Import aborted: {skipped} invalid rows ({details})")

    @staticmethod
    def _rebuild_transfers(records: Iterable[Record]) -> list[Transfer]:
        grouped: dict[int, list[Record]] = {}
        for record in records:
            if record.transfer_id is not None:
                grouped.setdefault(record.transfer_id, []).append(record)

        transfers: list[Transfer] = []
        for transfer_id, linked in sorted(grouped.items()):
            if len(linked) != 2:
                raise ValueError(
                    f"Transfer integrity violated for #{transfer_id}: expected 2 linked records"
                )
            source = next((item for item in linked if not isinstance(item, IncomeRecord)), None)
            target = next((item for item in linked if isinstance(item, IncomeRecord)), None)
            if source is None or target is None:
                raise ValueError(
                    f"Transfer integrity violated for #{transfer_id}: "
                    "requires one expense and one income"
                )
            transfers.append(
                Transfer(
                    id=transfer_id,
                    from_wallet_id=source.wallet_id,
                    to_wallet_id=target.wallet_id,
                    date=source.date,
                    amount_original=float(source.amount_original or 0.0),
                    currency=str(source.currency or "KZT").upper(),
                    rate_at_operation=float(source.rate_at_operation),
                    amount_kzt=float(source.amount_kzt or 0.0),
                    description=str(source.description or ""),
                )
            )
        return transfers

    @staticmethod
    def _build_list_items(records: Iterable[Record]) -> list[RecordListItem]:
        items: list[RecordListItem] = []
        by_transfer: dict[int, list[tuple[int, Record]]] = {}
        plain: list[tuple[int, Record]] = []
        for repository_index, record in enumerate(records):
            if record.transfer_id is not None:
                by_transfer.setdefault(record.transfer_id, []).append((repository_index, record))
            else:
                plain.append((repository_index, record))

        for repository_index, record in plain:
            amount_original = float(record.amount_original or 0.0)
            amount_kzt = float(record.amount_kzt or 0.0)
            if isinstance(record, IncomeRecord):
                record_type = "Income"
            elif isinstance(record, MandatoryExpenseRecord):
                record_type = "Mandatory Expense"
            else:
                record_type = "Expense"
            signature = (
                f"{record.date}|{record_type}|{record.category}|"
                f"{amount_original}|{record.currency}|{amount_kzt}|{repository_index}"
            )
            record_id = sha1(signature.encode("utf-8")).hexdigest()[:12]
            label = (
                f"[{repository_index}] {record.date} - {record_type} - {record.category} - "
                f"{amount_original:.2f} {record.currency} "
                f"(={amount_kzt:.2f} KZT)"
            )
            items.append(
                RecordListItem(
                    record_id=record_id,
                    repository_index=repository_index,
                    domain_record_id=int(getattr(record, "id", 0) or 0),
                    label=label,
                )
            )

        for transfer_id, grouped in by_transfer.items():
            repository_index = min(index for index, _ in grouped)
            source = next((r for _, r in grouped if not isinstance(r, IncomeRecord)), grouped[0][1])
            target = next((r for _, r in grouped if isinstance(r, IncomeRecord)), grouped[0][1])
            commission = sum(
                float(r.amount_kzt or 0.0)
                for _, r in grouped
                if r.category == "Commission" and not isinstance(r, IncomeRecord)
            )
            signature = f"transfer|{transfer_id}|{repository_index}"
            record_id = sha1(signature.encode("utf-8")).hexdigest()[:12]
            amount_original = float(source.amount_original or 0.0)
            amount_kzt = float(source.amount_kzt or 0.0)
            date_value = source.date if isinstance(source.date, str) else source.date.isoformat()
            label = (
                f"[{repository_index}] {date_value} - Transfer #{transfer_id} - "
                f"{amount_original:.2f} {source.currency} (={amount_kzt:.2f} KZT) "
                f"W{source.wallet_id} -> W{target.wallet_id}"
            )
            if commission > 0:
                label += f" | Commission: {commission:.2f} KZT"
            items.append(
                RecordListItem(
                    record_id=record_id,
                    repository_index=repository_index,
                    domain_record_id=int(getattr(source, "id", 0) or 0),
                    label=label,
                )
            )

        items.sort(key=lambda item: item.repository_index)
        return items

    @staticmethod
    def _reindex_records_for_import(records: Iterable[Record]) -> list[Record]:
        reindexed: list[Record] = []
        for index, record in enumerate(records, start=1):
            try:
                reindexed.append(replace(record, id=index))
            except TypeError:
                reindexed.append(record)
        return reindexed

    @staticmethod
    def _wallets_with_system_initial_balance(
        wallets: list[Wallet], initial_balance: float
    ) -> list[Wallet]:
        updated_wallets = list(wallets)
        target_index: int | None = None
        for index, wallet in enumerate(updated_wallets):
            if int(wallet.id) == 1:
                target_index = index
                break
        if target_index is None:
            for index, wallet in enumerate(updated_wallets):
                if bool(wallet.system):
                    target_index = index
                    break
        if target_index is not None:
            target_wallet = updated_wallets[target_index]
            updated_wallets[target_index] = replace(
                target_wallet,
                initial_balance=float(initial_balance),
                system=True,
            )
            return updated_wallets

        base_currency = updated_wallets[0].currency if updated_wallets else "KZT"
        system_wallet = Wallet(
            id=1,
            name="Main wallet",
            currency=str(base_currency or "KZT").upper(),
            initial_balance=float(initial_balance),
            system=True,
            allow_negative=False,
            is_active=True,
        )
        return [system_wallet, *updated_wallets]
