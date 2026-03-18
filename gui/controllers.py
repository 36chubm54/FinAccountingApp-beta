from __future__ import annotations

import logging
from dataclasses import replace

from app.record_service import RecordService
from app.services import CurrencyService
from app.use_cases import (
    AddMandatoryExpenseToReport,
    ApplyMandatoryAutoPayments,
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
    RunAudit,
    SoftDeleteWallet,
)
from domain.audit import AuditReport
from domain.import_policy import ImportPolicy
from domain.import_result import ImportResult
from domain.records import MandatoryExpenseRecord, Record
from domain.reports import Report
from domain.transfers import Transfer
from domain.validation import parse_ymd
from domain.wallets import Wallet
from gui.controller_support import (
    RecordListItem,
    build_list_items,
    wallets_with_system_initial_balance,
)
from infrastructure.repositories import RecordRepository
from infrastructure.sqlite_repository import SQLiteRecordRepository
from services.audit_service import AuditService
from services.balance_service import BalanceService, CashflowResult, WalletBalance
from services.import_service import ImportService
from services.metrics_service import MetricsService
from services.timeline_service import TimelineService

logger = logging.getLogger(__name__)


class FinancialController:
    def __init__(self, repository: RecordRepository, currency_service: CurrencyService) -> None:
        self._repository = repository
        self._currency = currency_service
        self._record_service = RecordService(repository)
        self.supports_bulk_import_replace = True

    def build_record_list_items(self) -> list[RecordListItem]:
        records = self._repository.load_all()
        return build_list_items(records)

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

    def update_record_inline(
        self,
        record_id: int,
        *,
        new_amount_kzt: float,
        new_category: str,
        new_description: str = "",
        new_date: str | None = None,
        new_wallet_id: int | None = None,
    ) -> None:
        self._record_service.update_record_inline(
            record_id,
            new_amount_kzt=new_amount_kzt,
            new_category=new_category,
            new_description=new_description,
            new_date=new_date,
            new_wallet_id=new_wallet_id,
        )

    def get_record_amount_kzt(self, record_id: int) -> float:
        record = self._repository.get_by_id(int(record_id))
        return float(record.amount_kzt or 0.0)

    def get_record_for_edit(self, record_id: int) -> Record:
        return self._repository.get_by_id(int(record_id))

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
        wallet_id: int = 1,
        category: str,
        description: str,
        period: str,
        date: str = "",
        amount_kzt: float | None = None,
        rate_at_operation: float | None = None,
    ) -> None:
        CreateMandatoryExpense(self._repository, self._currency).execute(
            amount=amount,
            currency=currency,
            wallet_id=wallet_id,
            category=category,
            description=description,
            period=period,
            date=date,
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

    def update_mandatory_expense_amount_kzt(self, expense_id: int, new_amount_kzt: float) -> None:
        self._record_service.update_mandatory_amount_kzt(expense_id, new_amount_kzt)

    def update_mandatory_expense_date(self, expense_id: int, new_date: str) -> None:
        self._record_service.update_mandatory_date(expense_id, new_date)

    def update_mandatory_expense_wallet_id(self, expense_id: int, new_wallet_id: int) -> None:
        self._record_service.update_mandatory_wallet_id(expense_id, new_wallet_id)

    def update_mandatory_expense_period(self, expense_id: int, new_period: str) -> None:
        self._record_service.update_mandatory_period(expense_id, new_period)

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

    def apply_mandatory_auto_payments(self) -> list[MandatoryExpenseRecord]:
        return ApplyMandatoryAutoPayments(self._repository).execute()

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
        target_wallets = wallets_with_system_initial_balance(target_wallets, float(initial_balance))

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
        def record_sort_key(record: Record) -> tuple[str, int]:
            # Keep operations grouped by date while preserving stable intra-day order
            # as they were written by the import pipeline / transfer creation.
            return (str(record.date), int(record.id))

        records = sorted(self._repository.load_all(), key=record_sort_key)
        transfers = sorted(
            self._repository.load_transfers(), key=lambda item: (str(item.date), int(item.id))
        )
        transfer_id_map = {int(item.id): index for index, item in enumerate(transfers, start=1)}
        normalized_transfers = [
            replace(transfer, id=transfer_id_map[int(transfer.id)]) for transfer in transfers
        ]
        normalized_records: list[Record] = []
        for index, record in enumerate(records, start=1):
            mapped_transfer_id = None
            if record.transfer_id is not None:
                mapped_transfer_id = transfer_id_map.get(int(record.transfer_id))
            normalized_records.append(replace(record, id=index, transfer_id=mapped_transfer_id))
        self._repository.replace_records_and_transfers(normalized_records, normalized_transfers)

    def import_records(
        self,
        fmt: str,
        filepath: str,
        policy: ImportPolicy,
        *,
        force: bool = False,
        dry_run: bool = False,
    ) -> ImportResult:
        if fmt not in {"CSV", "XLSX", "JSON"}:
            raise ValueError(f"Unsupported format: {fmt}")
        service = ImportService(self, policy=policy)
        return service.import_file(filepath, force=force, dry_run=dry_run)

    def import_mandatory(self, fmt: str, filepath: str) -> ImportResult:
        if fmt not in {"CSV", "XLSX", "JSON"}:
            raise ValueError(f"Unsupported format: {fmt}")
        return ImportService(self, policy=ImportPolicy.FULL_BACKUP).import_mandatory_file(filepath)

    def run_audit(self) -> AuditReport:
        if not isinstance(self._repository, SQLiteRecordRepository):
            raise TypeError("Audit is supported only for SQLite repository")
        use_case = RunAudit(AuditService(self._repository))
        return use_case.execute()

    def _balance_service(self) -> BalanceService:
        if not isinstance(self._repository, SQLiteRecordRepository):
            raise TypeError("Balance Engine is supported only for SQLite repository")
        return BalanceService(self._repository)

    def get_wallet_balance(self, wallet_id: int, date: str | None = None) -> float:
        return self._balance_service().get_wallet_balance(wallet_id, date=date)

    def get_wallet_balances(self, date: str | None = None) -> list[WalletBalance]:
        return self._balance_service().get_wallet_balances(date=date)

    def get_total_balance(self, date: str | None = None) -> float:
        return self._balance_service().get_total_balance(date=date)

    def get_cashflow(self, start_date: str, end_date: str) -> CashflowResult:
        return self._balance_service().get_cashflow(start_date, end_date)

    def get_income(self, start_date: str, end_date: str) -> float:
        return self._balance_service().get_income(start_date, end_date)

    def get_expenses(self, start_date: str, end_date: str) -> float:
        return self._balance_service().get_expenses(start_date, end_date)

    def _timeline_service(self) -> TimelineService:
        if not isinstance(self._repository, SQLiteRecordRepository):
            raise TypeError("Timeline Engine is supported only for SQLite repository")
        return TimelineService(self._repository)

    def get_net_worth_timeline(self) -> list:
        """Net worth (KZT) at end of each month. Returns list[MonthlyNetWorth]."""
        return self._timeline_service().get_net_worth_timeline()

    def get_monthly_cashflow(
        self,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> list:
        """Monthly income/expense/cashflow. Returns list[MonthlyCashflow]."""
        return self._timeline_service().get_monthly_cashflow(
            start_date=start_date,
            end_date=end_date,
        )

    def get_cumulative_income_expense(self) -> list:
        """Cumulative income and expenses per month. Returns list[MonthlyCumulative]."""
        return self._timeline_service().get_cumulative_income_expense()

    def _metrics_service(self) -> MetricsService:
        if not isinstance(self._repository, SQLiteRecordRepository):
            raise TypeError("Metrics Engine is supported only for SQLite repository")
        return MetricsService(self._repository)

    def get_savings_rate(self, start_date: str, end_date: str) -> float:
        """Savings rate (%) for [start_date, end_date]."""
        return self._metrics_service().get_savings_rate(start_date, end_date)

    def get_burn_rate(self, start_date: str, end_date: str) -> float:
        """Average daily expense (KZT) for [start_date, end_date]."""
        return self._metrics_service().get_burn_rate(start_date, end_date)

    def get_spending_by_category(
        self, start_date: str, end_date: str, *, limit: int | None = None
    ) -> list:
        """Expenses per category, sorted descending. Returns list[CategorySpend]."""
        return self._metrics_service().get_spending_by_category(start_date, end_date, limit=limit)

    def get_income_by_category(
        self, start_date: str, end_date: str, *, limit: int | None = None
    ) -> list:
        """Income per category, sorted descending. Returns list[CategorySpend]."""
        return self._metrics_service().get_income_by_category(start_date, end_date, limit=limit)

    def get_top_expense_categories(self, start_date: str, end_date: str, *, top_n: int = 5) -> list:
        """Top N expense categories by total. Returns list[CategorySpend]."""
        return self._metrics_service().get_top_expense_categories(start_date, end_date, top_n=top_n)

    def get_monthly_summary(
        self,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> list:
        """Per-month income/expenses/cashflow/savings_rate. Returns list[MonthlySummary]."""
        return self._metrics_service().get_monthly_summary(start_date=start_date, end_date=end_date)

    def get_year_income(self, year: int, *, up_to_date: str | None = None) -> float:
        """Total income (KZT) for the given calendar year, optionally up to a date."""
        start = f"{int(year):04d}-01-01"
        end = f"{int(year):04d}-12-31"
        if up_to_date is not None:
            end = self._min_date_iso(end, str(up_to_date))
        if parse_ymd(end) < parse_ymd(start):
            return 0.0
        return self.get_income(start, end)

    def get_average_monthly_income(self, year: int, *, up_to_date: str | None = None) -> float:
        """
        Average monthly income (KZT) for the given calendar year (year-to-date if up_to_date set).
        """
        start = f"{int(year):04d}-01-01"
        end = f"{int(year):04d}-12-31"
        if up_to_date is not None:
            end = self._min_date_iso(end, str(up_to_date))
        if parse_ymd(end) < parse_ymd(start):
            return 0.0
        months = self._month_count_in_range(start, end)
        if months <= 0:
            return 0.0
        return round(self.get_income(start, end) / months, 2)

    def get_average_monthly_expenses(self, start_date: str, end_date: str) -> float:
        """Average monthly expenses (KZT) for [start_date, end_date], inclusive."""
        months = self._month_count_in_range(start_date, end_date)
        if months <= 0:
            return 0.0
        return round(self.get_expenses(start_date, end_date) / months, 2)

    def get_average_annual_expenses(self, start_date: str, end_date: str) -> float:
        """
        Annualized expenses (KZT/year) based on average monthly expenses for [start_date, end_date].
        """
        return round(self.get_average_monthly_expenses(start_date, end_date) * 12, 2)

    def convert_kzt_to_usd(self, amount_kzt: float) -> float:
        """Convert a KZT amount to USD using the configured USD rate (KZT per 1 USD)."""
        try:
            rate = float(self._currency.get_rate("USD"))
        except Exception:
            return 0.0
        if rate <= 0:
            return 0.0
        return round(float(amount_kzt) / rate, 2)

    def get_time_costs(self, start_date: str, end_date: str) -> tuple[float, float, float]:
        """
        Cost of day/hour/minute (KZT) based on annualized expenses for [start_date, end_date].
        """
        annual = float(self.get_average_annual_expenses(start_date, end_date))
        per_day = annual / 365 if annual > 0 else 0.0
        per_hour = per_day / 24
        per_minute = per_hour / 60
        return (round(per_day, 2), round(per_hour, 2), round(per_minute, 2))

    def _month_count_in_range(self, start_date: str, end_date: str) -> int:
        d1 = parse_ymd(start_date)
        d2 = parse_ymd(end_date)
        if d2 < d1:
            return 0
        return (d2.year - d1.year) * 12 + (d2.month - d1.month) + 1

    def _min_date_iso(self, a: str, b: str) -> str:
        return a if parse_ymd(a) <= parse_ymd(b) else b
