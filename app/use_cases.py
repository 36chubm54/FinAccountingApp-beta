import logging
from dataclasses import replace
from datetime import date as dt_date

from app.use_case_support import (
    build_rate,
    commission_marker,
    is_commission_for_transfer,
    wallet_balance_kzt,
    wallet_by_id,
)
from domain.errors import DomainError
from domain.import_policy import ImportPolicy
from domain.records import ExpenseRecord, IncomeRecord, MandatoryExpenseRecord
from domain.reports import Report
from domain.transfers import Transfer
from domain.wallets import Wallet
from infrastructure.repositories import RecordRepository

from .services import CurrencyService

logger = logging.getLogger(__name__)
SYSTEM_WALLET_ID = 1


class CreateIncome:
    def __init__(self, repository: RecordRepository, currency: CurrencyService):
        self._repository = repository
        self._currency = currency

    def execute(
        self,
        *,
        date: str,
        wallet_id: int,
        amount: float,
        currency: str,
        category: str = "General",
        description: str = "",
        amount_kzt: float | None = None,
        rate_at_operation: float | None = None,
    ) -> None:
        """Create and persist an income record."""
        wallet = wallet_by_id(self._repository, wallet_id)
        if not wallet.is_active:
            raise ValueError("Cannot create operation for inactive wallet")
        if amount_kzt is None:
            amount_kzt = self._currency.convert(amount, currency)
        if rate_at_operation is None:
            rate_at_operation = build_rate(amount, amount_kzt, currency)
        record = IncomeRecord(
            date=date,
            wallet_id=wallet_id,
            amount_original=amount,
            currency=currency.upper(),
            rate_at_operation=float(rate_at_operation),
            amount_kzt=amount_kzt,
            category=category,
            description=description,
        )
        self._repository.save(record)
        logger.info(
            "Income record created date=%s wallet_id=%s amount_kzt=%s category=%s",
            date,
            wallet_id,
            amount_kzt,
            category,
        )


class CreateExpense:
    def __init__(self, repository: RecordRepository, currency: CurrencyService):
        self._repository = repository
        self._currency = currency

    def execute(
        self,
        *,
        date: str,
        wallet_id: int,
        amount: float,
        currency: str,
        category: str = "General",
        description: str = "",
        amount_kzt: float | None = None,
        rate_at_operation: float | None = None,
    ) -> None:
        """Create and persist an expense record."""
        wallet = wallet_by_id(self._repository, wallet_id)
        if not wallet.is_active:
            raise ValueError("Cannot create operation for inactive wallet")
        if amount_kzt is None:
            amount_kzt = self._currency.convert(amount, currency)
        if rate_at_operation is None:
            rate_at_operation = build_rate(amount, amount_kzt, currency)
        if not wallet.allow_negative:
            balance = wallet_balance_kzt(wallet, self._repository.load_all())
            if balance - amount_kzt < 0:
                raise ValueError("Insufficient funds in wallet")
        record = ExpenseRecord(
            date=date,
            wallet_id=wallet_id,
            amount_original=amount,
            currency=currency.upper(),
            rate_at_operation=float(rate_at_operation),
            amount_kzt=amount_kzt,
            category=category,
            description=description,
        )
        self._repository.save(record)
        logger.info(
            "Expense record created date=%s wallet_id=%s amount_kzt=%s category=%s",
            date,
            wallet_id,
            amount_kzt,
            category,
        )


class GenerateReport:
    def __init__(self, repository: RecordRepository):
        self._repository = repository

    def execute(self, wallet_id: int | None = None) -> Report:
        wallets = self._repository.load_wallets()
        if not isinstance(wallets, list):
            return Report(
                self._repository.load_all(),
                self._repository.load_initial_balance(),
                wallet_id=wallet_id,
            )
        if wallet_id is None:
            initial_balance = sum(wallet.initial_balance for wallet in wallets)
        else:
            initial_balance = 0.0
            for wallet in wallets:
                if wallet.id == wallet_id:
                    initial_balance = wallet.initial_balance
                    break
        return Report(
            self._repository.load_all(),
            initial_balance,
            wallet_id=wallet_id,
        )


class CreateWallet:
    def __init__(self, repository: RecordRepository):
        self._repository = repository

    def execute(
        self,
        *,
        name: str,
        currency: str,
        initial_balance: float,
        allow_negative: bool = False,
    ) -> Wallet:
        wallet = self._repository.create_wallet(
            name=name,
            currency=currency,
            initial_balance=initial_balance,
            allow_negative=allow_negative,
        )
        logger.info(
            "Wallet created id=%s name=%s currency=%s allow_negative=%s",
            wallet.id,
            wallet.name,
            wallet.currency,
            wallet.allow_negative,
        )
        return wallet


class GetWallets:
    def __init__(self, repository: RecordRepository):
        self._repository = repository

    def execute(self) -> list[Wallet]:
        return self._repository.load_wallets()


class GetActiveWallets:
    def __init__(self, repository: RecordRepository):
        self._repository = repository

    def execute(self) -> list[Wallet]:
        return self._repository.load_active_wallets()


class SoftDeleteWallet:
    def __init__(self, repository: RecordRepository):
        self._repository = repository

    def execute(self, wallet_id: int) -> None:
        wallet = wallet_by_id(self._repository, wallet_id)
        if wallet.system:
            raise ValueError("System wallet cannot be deleted")
        balance = wallet_balance_kzt(wallet, self._repository.load_all())
        if abs(balance) > 1e-9:
            raise ValueError("Wallet with non-zero balance cannot be deleted")
        if not self._repository.soft_delete_wallet(wallet_id):
            raise ValueError("Wallet not found")
        logger.info("Wallet soft-deleted id=%s", wallet_id)


class CalculateWalletBalance:
    def __init__(self, repository: RecordRepository):
        self._repository = repository

    def execute(self, wallet_id: int) -> float:
        wallets = self._repository.load_wallets()
        wallet = next((w for w in wallets if w.id == wallet_id), None)
        if wallet is None:
            raise ValueError(f"Wallet not found: {wallet_id}")
        return wallet_balance_kzt(wallet, self._repository.load_all())


class CalculateNetWorth:
    def __init__(self, repository: RecordRepository, currency: CurrencyService):
        self._repository = repository
        self._currency = currency

    def execute_fixed(self) -> float:
        wallets = self._repository.load_active_wallets()
        records = self._repository.load_all()
        return sum(wallet_balance_kzt(wallet, records) for wallet in wallets)

    def execute_current(self) -> float:
        wallets = self._repository.load_active_wallets()
        records = self._repository.load_all()
        total = 0.0
        for wallet in wallets:
            total += float(self._currency.convert(wallet.initial_balance, wallet.currency))
        for record in records:
            if record.amount_original is not None:
                converted = float(self._currency.convert(record.amount_original, record.currency))
                sign = 1.0 if record.signed_amount_kzt() >= 0 else -1.0
                total += sign * abs(converted)
        return total


class CreateTransfer:
    def __init__(self, repository: RecordRepository, currency: CurrencyService):
        self._repository = repository
        self._currency = currency

    def execute(
        self,
        *,
        from_wallet_id: int,
        to_wallet_id: int,
        transfer_date: str | dt_date,
        amount_original: float,
        currency: str,
        description: str = "",
        commission_amount: float = 0.0,
        commission_currency: str | None = None,
        amount_kzt: float | None = None,
        rate_at_operation: float | None = None,
    ) -> int:
        if from_wallet_id == to_wallet_id:
            raise ValueError("Transfer wallets must be different")
        if amount_original <= 0:
            raise ValueError("Transfer amount must be positive")
        if commission_amount < 0:
            raise ValueError("Commission amount cannot be negative")

        wallets = {wallet.id: wallet for wallet in self._repository.load_wallets()}
        from_wallet = wallets.get(from_wallet_id)
        to_wallet = wallets.get(to_wallet_id)
        if from_wallet is None:
            raise ValueError(f"Wallet not found: {from_wallet_id}")
        if to_wallet is None:
            raise ValueError(f"Wallet not found: {to_wallet_id}")
        if not from_wallet.is_active or not to_wallet.is_active:
            raise ValueError("Transfers are allowed only between active wallets")

        if amount_kzt is None:
            transfer_kzt = float(self._currency.convert(amount_original, currency))
        else:
            transfer_kzt = float(amount_kzt)
        if rate_at_operation is None:
            transfer_rate = build_rate(amount_original, transfer_kzt, currency)
        else:
            transfer_rate = float(rate_at_operation)

        commission_ccy = (commission_currency or currency).upper()
        commission_kzt = 0.0
        commission_rate = 1.0
        if commission_amount > 0:
            commission_kzt = float(self._currency.convert(commission_amount, commission_ccy))
            commission_rate = build_rate(commission_amount, commission_kzt, commission_ccy)

        records = self._repository.load_all()
        from_balance = wallet_balance_kzt(from_wallet, records)
        projected_balance = from_balance - transfer_kzt - commission_kzt
        if not from_wallet.allow_negative and projected_balance < 0:
            raise ValueError("Insufficient funds in source wallet")
        next_record_id = max((int(record.id) for record in records), default=0) + 1

        transfer_id = max((t.id for t in self._repository.load_transfers()), default=0) + 1
        transfer = Transfer(
            id=transfer_id,
            from_wallet_id=from_wallet_id,
            to_wallet_id=to_wallet_id,
            date=transfer_date,
            amount_original=float(amount_original),
            currency=currency.upper(),
            rate_at_operation=transfer_rate,
            amount_kzt=transfer_kzt,
            description=description,
        )

        expense_record = ExpenseRecord(
            id=next_record_id,
            date=transfer_date,
            wallet_id=from_wallet_id,
            transfer_id=transfer_id,
            amount_original=float(amount_original),
            currency=currency.upper(),
            rate_at_operation=transfer_rate,
            amount_kzt=transfer_kzt,
            category="Transfer",
        )
        income_record = IncomeRecord(
            id=next_record_id + 1,
            date=transfer_date,
            wallet_id=to_wallet_id,
            transfer_id=transfer_id,
            amount_original=float(amount_original),
            currency=currency.upper(),
            rate_at_operation=transfer_rate,
            amount_kzt=transfer_kzt,
            category="Transfer",
        )
        updated_records = list(records) + [expense_record, income_record]
        updated_transfers = list(self._repository.load_transfers()) + [transfer]

        if commission_amount > 0:
            marker = commission_marker(transfer_id)
            commission_record = ExpenseRecord(
                id=next_record_id + 2,
                date=transfer_date,
                wallet_id=from_wallet_id,
                transfer_id=None,
                amount_original=float(commission_amount),
                currency=commission_ccy,
                rate_at_operation=commission_rate,
                amount_kzt=commission_kzt,
                category="Commission",
                description=marker,
            )
            updated_records.append(commission_record)
            logger.info(
                "Transfer commission record created transfer_id=%s wallet=%s amount_kzt=%.2f",
                transfer_id,
                from_wallet_id,
                commission_kzt,
            )

        self._repository.replace_records_and_transfers(updated_records, updated_transfers)
        logger.info(
            "Transfer records created transfer_id=%s from_wallet=%s to_wallet=%s amount_kzt=%.2f",
            transfer_id,
            from_wallet_id,
            to_wallet_id,
            transfer_kzt,
        )

        return transfer_id


class DeleteTransfer:
    def __init__(self, repository: RecordRepository):
        self._repository = repository

    def execute(self, transfer_id: int) -> None:
        transfers = self._repository.load_transfers()
        transfer = next((item for item in transfers if item.id == transfer_id), None)
        if transfer is None:
            raise DomainError(f"Transfer not found: {transfer_id}")

        records = self._repository.load_all()
        linked = [record for record in records if record.transfer_id == transfer_id]
        if len(linked) != 2:
            raise DomainError(
                f"Transfer integrity violated for #{transfer_id}: "
                f"expected 2 linked records, got {len(linked)}"
            )

        types = {record.type for record in linked}
        if types != {"expense", "income"}:
            raise DomainError(
                f"Transfer integrity violated for #{transfer_id}: "
                "requires one expense and one income"
            )

        new_records = [
            record
            for record in records
            if record.transfer_id != transfer_id
            and not is_commission_for_transfer(record, transfer_id)
        ]
        new_transfers = [item for item in transfers if item.id != transfer_id]

        self._repository.replace_records_and_transfers(new_records, new_transfers)
        logger.info(
            "Transfer deleted transfer_id=%s removed_records=%s",
            transfer_id,
            len(records) - len(new_records),
        )


class DeleteRecord:
    def __init__(self, repository: RecordRepository):
        self._repository = repository

    def execute(self, index: int) -> bool:
        """Delete record by index. Returns True if deleted successfully."""
        records = self._repository.load_all()
        try:
            if not (0 <= index < len(records)):
                return False
        except TypeError:
            # Backward-compatible path for mocked repositories in unit tests
            # that do not provide a list-like result for load_all().
            return self._repository.delete_by_index(index)
        record = records[index]
        if record.transfer_id is not None:
            DeleteTransfer(self._repository).execute(record.transfer_id)
            return True
        return self._repository.delete_by_index(index)


class DeleteAllRecords:
    def __init__(self, repository: RecordRepository):
        self._repository = repository

    def execute(self) -> None:
        """Delete all records."""
        self._repository.delete_all()


class ImportFromCSV:
    def __init__(self, repository: RecordRepository):
        self._repository = repository

    def execute(self, filepath: str) -> int:
        """Import records from CSV and atomically replace repository data."""
        from utils.csv_utils import import_records_from_csv

        records, initial_balance, summary = import_records_from_csv(
            filepath,
            policy=ImportPolicy.FULL_BACKUP,
            existing_initial_balance=self._repository.load_initial_balance(),
        )
        imported_count, skipped_count, _ = summary
        logger.info("CSV import parsed: imported=%s skipped=%s", imported_count, skipped_count)
        if skipped_count > 0:
            logger.warning("CSV import aborted due to validation errors: skipped=%s", skipped_count)
            raise ValueError("Import aborted: CSV contains invalid rows")
        transfers = []
        grouped: dict[int, list] = {}
        for record in records:
            transfer_id = getattr(record, "transfer_id", None)
            if isinstance(transfer_id, int) and transfer_id > 0:
                grouped.setdefault(transfer_id, []).append(record)
        for transfer_id, linked in grouped.items():
            source = next((item for item in linked if isinstance(item, ExpenseRecord)), None)
            target = next((item for item in linked if isinstance(item, IncomeRecord)), None)
            if source is None or target is None or len(linked) != 2:
                raise ValueError(f"Transfer integrity violated for #{transfer_id}")
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
        reindexed_records = []
        for index, record in enumerate(records, start=1):
            try:
                reindexed_records.append(replace(record, id=index))
            except TypeError:
                reindexed_records.append(record)
        records = reindexed_records
        self._repository.replace_records_and_transfers(records, transfers)
        self._repository.save_initial_balance(float(initial_balance))
        return imported_count


class CreateMandatoryExpense:
    def __init__(self, repository: RecordRepository, currency: CurrencyService):
        self._repository = repository
        self._currency = currency

    def execute(
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
        """Create and persist a mandatory expense template."""
        from domain.validation import ensure_valid_period

        ensure_valid_period(period)

        if amount_kzt is None:
            amount_kzt = self._currency.convert(amount, currency)
        if rate_at_operation is None:
            rate_at_operation = build_rate(amount, amount_kzt, currency)
        expense = MandatoryExpenseRecord(
            wallet_id=SYSTEM_WALLET_ID,
            amount_original=amount,
            currency=currency.upper(),
            rate_at_operation=float(rate_at_operation),
            amount_kzt=amount_kzt,
            category=category,
            description=description,
            period=period,  # type: ignore
        )
        self._repository.save_mandatory_expense(expense)
        logger.info(
            "Mandatory expense created amount=%s category=%s description=%s period=%s",
            amount,
            category,
            description,
            period,
        )


class CreateMandatoryExpenseRecord:
    def __init__(self, repository: RecordRepository, currency: CurrencyService):
        self._repository = repository
        self._currency = currency

    def execute(
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
        from domain.validation import ensure_valid_period

        ensure_valid_period(period)
        wallet = wallet_by_id(self._repository, wallet_id)
        if not wallet.is_active:
            raise ValueError("Cannot create operation for inactive wallet")

        if amount_kzt is None:
            amount_kzt = self._currency.convert(amount, currency)
        if rate_at_operation is None:
            rate_at_operation = build_rate(amount, amount_kzt, currency)
        if not wallet.allow_negative:
            balance = wallet_balance_kzt(wallet, self._repository.load_all())
            if balance - amount_kzt < 0:
                raise ValueError("Insufficient funds in wallet")

        record = MandatoryExpenseRecord(
            date=date,
            wallet_id=wallet_id,
            amount_original=amount,
            currency=currency.upper(),
            rate_at_operation=float(rate_at_operation),
            amount_kzt=amount_kzt,
            category=category,
            description=description,
            period=period,  # type: ignore[arg-type]
        )
        self._repository.save(record)


class GetMandatoryExpenses:
    def __init__(self, repository: RecordRepository):
        self._repository = repository

    def execute(self) -> list[MandatoryExpenseRecord]:
        """Return all mandatory expense templates."""
        return self._repository.load_mandatory_expenses()


class DeleteMandatoryExpense:
    def __init__(self, repository: RecordRepository):
        self._repository = repository

    def execute(self, index: int) -> bool:
        """Delete mandatory expense by index. Returns True if deleted."""
        return self._repository.delete_mandatory_expense_by_index(index)


class DeleteAllMandatoryExpenses:
    def __init__(self, repository: RecordRepository):
        self._repository = repository

    def execute(self) -> None:
        """Delete all mandatory expenses."""
        self._repository.delete_all_mandatory_expenses()


class AddMandatoryExpenseToReport:
    def __init__(self, repository: RecordRepository):
        self._repository = repository

    def execute(self, index: int, date: str, wallet_id: int) -> bool:
        """Add selected mandatory expense to records with provided date."""
        mandatory_expenses = self._repository.load_mandatory_expenses()
        if 0 <= index < len(mandatory_expenses):
            expense = mandatory_expenses[index]
            # Create a new record with the specified date
            record = MandatoryExpenseRecord(
                date=date,
                wallet_id=int(wallet_id),
                amount_original=expense.amount_original,
                currency=expense.currency,
                rate_at_operation=expense.rate_at_operation,
                amount_kzt=expense.amount_kzt,
                category=expense.category,
                description=expense.description,
                period=expense.period,
            )
            self._repository.save(record)
            logging.info(
                "Mandatory expense added to report date=%s wallet_id=%s amount_kzt=%s category=%s",
                date,
                wallet_id,
                record.amount_kzt,
                record.category,
            )
            return True
        return False
