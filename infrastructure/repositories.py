import json
import logging
import os
import shutil
import tempfile
import threading
import time
from abc import ABC, abstractmethod
from dataclasses import replace as dc_replace
from datetime import date as dt_date
from typing import TypeVar, cast

from domain.errors import DomainError
from domain.records import ExpenseRecord, IncomeRecord, MandatoryExpenseRecord, Record
from domain.transfers import Transfer
from domain.wallets import Wallet

T = TypeVar("T", bound=Record)

logger = logging.getLogger(__name__)
SYSTEM_WALLET_ID = 1


class RecordRepository(ABC):
    @abstractmethod
    def load_active_wallets(self) -> list[Wallet]:
        """Load active wallets only."""
        pass

    @abstractmethod
    def create_wallet(
        self,
        *,
        name: str,
        currency: str,
        initial_balance: float,
        allow_negative: bool = False,
        system: bool = False,
    ) -> Wallet:
        """Create and persist a wallet."""
        pass

    @abstractmethod
    def save_wallet(self, wallet: Wallet) -> None:
        """Save wallet data."""
        pass

    @abstractmethod
    def soft_delete_wallet(self, wallet_id: int) -> bool:
        """Mark wallet as inactive."""
        pass

    @abstractmethod
    def load_wallets(self) -> list[Wallet]:
        """Load all wallets."""
        pass

    @abstractmethod
    def get_system_wallet(self) -> Wallet:
        """Return system wallet."""
        pass

    @abstractmethod
    def save_transfer(self, transfer: Transfer) -> None:
        """Persist transfer aggregate."""
        pass

    @abstractmethod
    def load_transfers(self) -> list[Transfer]:
        """Load transfers."""
        pass

    @abstractmethod
    def replace_records_and_transfers(
        self, records: list[Record], transfers: list[Transfer]
    ) -> None:
        """Atomically replace records and transfers only."""
        pass

    @abstractmethod
    def save(self, record: Record) -> None:
        pass

    @abstractmethod
    def load_all(self) -> list[Record]:
        pass

    @abstractmethod
    def list_all(self) -> list[Record]:
        """List all records (SQL-ready alias)."""
        pass

    @abstractmethod
    def get_by_id(self, record_id: int) -> Record:
        """Return record by id or raise ValueError."""
        pass

    @abstractmethod
    def replace(self, record: Record) -> None:
        """Replace record by id."""
        pass

    @abstractmethod
    def delete_by_index(self, index: int) -> bool:
        """Delete record by index. Returns True if deleted, False if index out of range."""
        pass

    @abstractmethod
    def delete_all(self) -> None:
        """Delete all records."""
        pass

    @abstractmethod
    def save_initial_balance(self, balance: float) -> None:
        """Save initial balance."""
        pass

    @abstractmethod
    def load_initial_balance(self) -> float:
        """Load initial balance. Returns 0.0 if not set."""
        pass

    @abstractmethod
    def save_mandatory_expense(self, expense: MandatoryExpenseRecord) -> None:
        """Save mandatory expense."""
        pass

    @abstractmethod
    def load_mandatory_expenses(self) -> list[MandatoryExpenseRecord]:
        """Load all mandatory expenses."""
        pass

    @abstractmethod
    def delete_mandatory_expense_by_index(self, index: int) -> bool:
        """Delete mandatory expense by index. Returns True if deleted."""
        pass

    @abstractmethod
    def delete_all_mandatory_expenses(self) -> None:
        """Delete all mandatory expenses."""
        pass

    @abstractmethod
    def replace_records(self, records: list[Record], initial_balance: float) -> None:
        """Atomically replace all records and (legacy) system-wallet balance."""
        pass

    @abstractmethod
    def replace_mandatory_expenses(self, expenses: list[MandatoryExpenseRecord]) -> None:
        """Atomically replace mandatory expenses."""
        pass

    @abstractmethod
    def replace_all_data(
        self,
        *,
        initial_balance: float = 0.0,
        wallets: list[Wallet] | None = None,
        records: list[Record],
        mandatory_expenses: list[MandatoryExpenseRecord],
        transfers: list[Transfer] | None = None,
    ) -> None:
        """Atomically replace full repository dataset."""
        pass


class JsonFileRecordRepository(RecordRepository):
    _path_locks: dict[str, threading.RLock] = {}
    _path_locks_guard = threading.Lock()

    def __init__(self, file_path: str = "data.json"):
        self._file_path = file_path
        abs_path = os.path.abspath(file_path)
        with self._path_locks_guard:
            if abs_path not in self._path_locks:
                self._path_locks[abs_path] = threading.RLock()
            self._lock = self._path_locks[abs_path]

    @staticmethod
    def _wallet_to_dict(wallet: Wallet) -> dict:
        return {
            "id": int(wallet.id),
            "name": str(wallet.name),
            "currency": str(wallet.currency or "KZT").upper(),
            "initial_balance": float(wallet.initial_balance),
            "system": bool(wallet.system),
            "allow_negative": bool(wallet.allow_negative),
            "is_active": bool(wallet.is_active),
        }

    @classmethod
    def _build_system_wallet(cls, currency: str, initial_balance: float) -> dict:
        return cls._wallet_to_dict(
            Wallet(
                id=SYSTEM_WALLET_ID,
                name="Main wallet",
                currency=currency,
                initial_balance=float(initial_balance),
                system=True,
                allow_negative=False,
                is_active=True,
            )
        )

    @staticmethod
    def _resolve_base_currency(records: list) -> str:
        for item in records:
            if isinstance(item, dict):
                currency = str(item.get("currency", "") or "").strip().upper()
                if currency:
                    return currency
        return "KZT"

    @staticmethod
    def _is_transfer_commission(item: dict) -> bool:
        return str(item.get("category", "") or "").strip().lower() == "commission"

    def _validate_transfer_integrity(self, data: dict) -> None:
        records = [item for item in data.get("records", []) if isinstance(item, dict)]
        transfers = [item for item in data.get("transfers", []) if isinstance(item, dict)]

        records_by_transfer: dict[int, list[dict]] = {}
        for record in records:
            transfer_raw = record.get("transfer_id")
            if transfer_raw in (None, ""):
                continue
            transfer_id = self._as_strict_int(transfer_raw)
            if transfer_id is None:
                raise DomainError(f"Invalid transfer_id in record: {transfer_raw}")
            if transfer_id <= 0:
                raise DomainError(f"Invalid transfer_id in record: {transfer_raw}")
            records_by_transfer.setdefault(transfer_id, []).append(record)

        transfer_ids: set[int] = set()
        for transfer in transfers:
            transfer_id = self._as_strict_int(transfer.get("id"))
            if transfer_id is None:
                raise DomainError(f"Invalid transfer id: {transfer.get('id')}")
            if transfer_id > 0:
                transfer_ids.add(transfer_id)

        # Records referencing missing transfers are forbidden.
        for transfer_id in records_by_transfer:
            if transfer_id not in transfer_ids:
                raise DomainError(f"Dangling records detected for missing transfer #{transfer_id}")

        # Each transfer must have exactly 2 linked records: one expense and one income.
        for transfer in transfers:
            transfer_id = self._as_strict_int(transfer.get("id"))
            if transfer_id is None:
                raise DomainError(f"Invalid transfer id: {transfer.get('id')}")
            linked = records_by_transfer.get(transfer_id, [])
            if len(linked) != 2:
                raise DomainError(
                    f"Transfer integrity violated for #{transfer_id}: "
                    f"expected 2 linked records, got {len(linked)}"
                )
            record_types = {str(item.get("type", "") or "").lower() for item in linked}
            if record_types != {"expense", "income"}:
                raise DomainError(
                    f"Transfer integrity violated for #{transfer_id}: "
                    f"requires one income and one expense"
                )

    def _load_data(self) -> dict:
        with self._lock:
            try:
                with open(self._file_path, encoding="utf-8") as f:
                    data = json.load(f)
            except (FileNotFoundError, json.JSONDecodeError):
                logger.warning(
                    "Failed to load JSON data from %s, using empty dataset",
                    self._file_path,
                )
                return {
                    "wallets": [self._build_system_wallet("KZT", 0.0)],
                    "records": [],
                    "mandatory_expenses": [],
                    "transfers": [],
                }
        if isinstance(data, list):
            # Migrate old format
            logger.info("Migrating JSON repository format: list -> object")
            data = {"records": data}
        if not isinstance(data, dict):
            logger.info("Migrating JSON repository format: invalid root -> default object")
            data = {
                "wallets": [self._build_system_wallet("KZT", 0.0)],
                "records": [],
                "mandatory_expenses": [],
                "transfers": [],
            }

        migrated = False
        if "records" not in data or not isinstance(data.get("records"), list):
            data["records"] = []
            migrated = True
        if "mandatory_expenses" not in data or not isinstance(data.get("mandatory_expenses"), list):
            data["mandatory_expenses"] = []
            migrated = True
        if "transfers" not in data or not isinstance(data.get("transfers"), list):
            data["transfers"] = []
            migrated = True

        legacy_initial_balance = float(self._as_float(data.get("initial_balance"), 0.0))
        wallets = data.get("wallets")
        if not isinstance(wallets, list):
            wallets = []
            migrated = True

        if not wallets:
            base_currency = self._resolve_base_currency(data["records"])
            wallets = [self._build_system_wallet(base_currency, legacy_initial_balance)]
            data["wallets"] = wallets
            migrated = True
        else:
            normalized_wallets: list[dict] = []
            has_system_wallet = False
            for index, wallet_item in enumerate(wallets):
                if not isinstance(wallet_item, dict):
                    logger.warning("Skipping non-dict wallet at index %s", index)
                    migrated = True
                    continue
                wallet_id = self._as_strict_int(wallet_item.get("id"))
                if wallet_id is None:
                    migrated = True
                    continue
                if wallet_id <= 0:
                    migrated = True
                    continue
                wallet_payload = {
                    "id": wallet_id,
                    "name": str(wallet_item.get("name", "") or f"Wallet {wallet_id}"),
                    "currency": str(wallet_item.get("currency", "KZT") or "KZT").upper(),
                    "initial_balance": self._as_float(wallet_item.get("initial_balance"), 0.0),
                    "system": bool(wallet_item.get("system", False)),
                    "allow_negative": bool(wallet_item.get("allow_negative", False)),
                    "is_active": bool(wallet_item.get("is_active", True)),
                }
                if wallet_id == SYSTEM_WALLET_ID:
                    has_system_wallet = True
                    wallet_payload["system"] = True
                normalized_wallets.append(wallet_payload)
            wallets = normalized_wallets
            if not has_system_wallet:
                base_currency = self._resolve_base_currency(data["records"])
                wallets.insert(0, self._build_system_wallet(base_currency, legacy_initial_balance))
                migrated = True
            elif legacy_initial_balance != 0.0:
                for wallet_item in wallets:
                    if int(wallet_item.get("id", 0)) == SYSTEM_WALLET_ID:
                        wallet_item["initial_balance"] = (
                            self._as_float(wallet_item.get("initial_balance"), 0.0)
                            + legacy_initial_balance
                        )
                        break
                migrated = True
            data["wallets"] = wallets

        if "initial_balance" in data:
            data.pop("initial_balance", None)
            migrated = True

        seen_record_ids: set[int] = set()
        next_record_id = self._next_record_id_from_items(data["records"])
        for item in data["records"]:
            if isinstance(item, dict):
                raw_id = self._as_strict_int(item.get("id"), 0) or 0
                if raw_id <= 0 or raw_id in seen_record_ids:
                    item["id"] = next_record_id
                    next_record_id += 1
                    migrated = True
                seen_record_ids.add(int(item["id"]))
            if isinstance(item, dict) and "wallet_id" not in item:
                item["wallet_id"] = SYSTEM_WALLET_ID
                migrated = True
            if isinstance(item, dict) and "transfer_id" not in item:
                item["transfer_id"] = None
                migrated = True
            if (
                isinstance(item, dict)
                and item.get("transfer_id") not in (None, "")
                and self._is_transfer_commission(item)
            ):
                transfer_id = self._as_strict_int(item.get("transfer_id"))
                if transfer_id is None:
                    item["transfer_id"] = None
                    migrated = True
                    continue
                if transfer_id > 0:
                    description = str(item.get("description", "") or "")
                    marker = f"[transfer:{transfer_id}]"
                    if marker not in description:
                        item["description"] = f"{description} {marker}".strip()
                    item["transfer_id"] = None
                    migrated = True

        normalized_mandatory_id = 1
        seen_mandatory_ids: set[int] = set()
        for item in data["mandatory_expenses"]:
            if not isinstance(item, dict):
                continue
            if "date" in item:
                item.pop("date", None)
                migrated = True
            raw_id = self._as_int(item.get("id"), 0)
            if raw_id != normalized_mandatory_id or raw_id in seen_mandatory_ids:
                item["id"] = normalized_mandatory_id
                migrated = True
            seen_mandatory_ids.add(int(item["id"]))
            normalized_mandatory_id += 1

        self._validate_transfer_integrity(data)

        if migrated:
            try:
                self._save_data(data)
            except Exception:
                logger.exception("Failed to persist repository migration for %s", self._file_path)
        return data

    def _save_data(self, data: dict) -> None:
        payload = dict(data)
        payload.pop("initial_balance", None)
        with self._lock:
            directory = os.path.dirname(self._file_path) or "."
            fd, tmp_path = tempfile.mkstemp(prefix=".records_", suffix=".json", dir=directory)
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    json.dump(payload, f, indent=2, ensure_ascii=False)
                self._replace_with_retry(tmp_path)
            except PermissionError as e:
                error_path = self._file_path + ".error"
                shutil.copy2(tmp_path, error_path)
                raise Exception(
                    f"Failed to save data to {self._file_path}. "
                    f"Temporary file saved to {error_path}"
                ) from e
            finally:
                try:
                    if os.path.exists(tmp_path):
                        os.remove(tmp_path)
                except Exception:
                    logger.exception("Failed to cleanup temporary file during save: %s", tmp_path)

    @staticmethod
    def _is_retryable_windows_permission_error(error: PermissionError) -> bool:
        return int(getattr(error, "winerror", 0) or 0) in {5, 32}

    def _replace_with_retry(self, tmp_path: str) -> None:
        delays = (0.01, 0.02, 0.05)
        for attempt, delay in enumerate(delays, start=1):
            try:
                os.replace(tmp_path, self._file_path)
                return
            except PermissionError as error:
                if not self._is_retryable_windows_permission_error(error):
                    raise
                if attempt == len(delays):
                    raise
                time.sleep(delay)

    @staticmethod
    def _as_float(value, default: float = 0.0) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _as_int(value, default: int = 0) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _as_strict_int(value, default: int | None = None) -> int | None:
        try:
            parsed = float(value)
        except (TypeError, ValueError, OverflowError):
            return default
        if not parsed.is_integer():
            return default
        return int(parsed)

    @classmethod
    def _require_strict_int(cls, value, field_name: str) -> int:
        parsed = cls._as_strict_int(value)
        if parsed is None:
            raise ValueError(f"Invalid integer value for {field_name}: {value}")
        return parsed

    @staticmethod
    def _next_record_id_from_items(items: list[dict]) -> int:
        max_id = 0
        for item in items:
            if not isinstance(item, dict):
                continue
            parsed_id = JsonFileRecordRepository._as_strict_int(item.get("id"))
            if parsed_id is not None:
                max_id = max(max_id, parsed_id)
        return max_id + 1

    @staticmethod
    def _next_mandatory_id_from_items(items: list[dict]) -> int:
        max_id = 0
        for item in items:
            if not isinstance(item, dict):
                continue
            parsed_id = JsonFileRecordRepository._as_strict_int(item.get("id"))
            if parsed_id is not None:
                max_id = max(max_id, parsed_id)
        return max_id + 1

    def _ensure_unique_record_id(self, record: T, data: dict) -> T:
        if isinstance(record, MandatoryExpenseRecord):
            existing_ids = {
                self._as_int(item.get("id"), 0)
                for item in data.get("mandatory_expenses", [])
                if isinstance(item, dict)
            }
        else:
            existing_ids = {
                self._as_int(item.get("id"), 0)
                for item in data.get("records", [])
                if isinstance(item, dict)
            }
        record_id = int(getattr(record, "id", 0) or 0)
        if record_id > 0 and record_id not in existing_ids:
            return record
        next_id = max(existing_ids or {0}) + 1
        return cast(T, dc_replace(record, id=next_id))

    def _record_to_dict(self, record: Record, record_type: str) -> dict:
        record_date = record.date.isoformat() if isinstance(record.date, dt_date) else record.date
        payload = {
            "id": int(getattr(record, "id", 0) or 0),
            "type": record_type,
            "date": record_date,
            "wallet_id": int(getattr(record, "wallet_id", SYSTEM_WALLET_ID)),
            "transfer_id": getattr(record, "transfer_id", None),
            "amount_original": record.amount_original,
            "currency": record.currency,
            "rate_at_operation": record.rate_at_operation,
            "amount_kzt": record.amount_kzt,
            "category": record.category,
            "description": str(getattr(record, "description", "") or ""),
        }
        if isinstance(record, MandatoryExpenseRecord):
            payload["period"] = record.period
        return payload

    def _parse_record_common(self, item: dict) -> dict:
        # Lazy migration for legacy records without amount_kzt.
        if "amount_kzt" in item:
            amount_kzt = self._as_float(item.get("amount_kzt", 0.0), 0.0)
            amount_original = self._as_float(item.get("amount_original", amount_kzt), amount_kzt)
            currency = str(item.get("currency", "KZT") or "KZT").upper()
            rate_at_operation = self._as_float(item.get("rate_at_operation", 1.0), 1.0)
        else:
            legacy_amount = self._as_float(item.get("amount", 0.0), 0.0)
            amount_original = legacy_amount
            amount_kzt = legacy_amount
            currency = "KZT"
            rate_at_operation = 1.0

        return {
            "id": self._require_strict_int(item.get("id"), "record.id"),
            "date": str(item.get("date", "") or ""),
            "wallet_id": self._require_strict_int(
                item.get("wallet_id", SYSTEM_WALLET_ID), "record.wallet_id"
            ),
            "transfer_id": (
                self._require_strict_int(item.get("transfer_id"), "record.transfer_id")
                if item.get("transfer_id") not in (None, "")
                else None
            ),
            "amount_original": amount_original,
            "currency": currency,
            "rate_at_operation": rate_at_operation,
            "amount_kzt": amount_kzt,
            "category": str(item.get("category", "General") or "General"),
            "description": str(item.get("description", "") or ""),
        }

    def load_wallets(self) -> list[Wallet]:
        data = self._load_data()
        wallets: list[Wallet] = []
        for index, item in enumerate(data.get("wallets", [])):
            if not isinstance(item, dict):
                logger.warning("Skipping non-dict wallet at index %s", index)
                continue
            wallet_id = self._as_strict_int(item.get("id"))
            if wallet_id is None:
                logger.warning("Skipping wallet with invalid id at index %s", index)
                continue
            if wallet_id <= 0:
                continue
            wallets.append(
                Wallet(
                    id=wallet_id,
                    name=str(item.get("name", "") or f"Wallet {wallet_id}"),
                    currency=str(item.get("currency", "KZT") or "KZT").upper(),
                    initial_balance=self._as_float(item.get("initial_balance"), 0.0),
                    system=bool(item.get("system", wallet_id == SYSTEM_WALLET_ID)),
                    allow_negative=bool(item.get("allow_negative", False)),
                    is_active=bool(item.get("is_active", True)),
                )
            )
        return wallets

    def load_active_wallets(self) -> list[Wallet]:
        return [wallet for wallet in self.load_wallets() if wallet.is_active]

    def create_wallet(
        self,
        *,
        name: str,
        currency: str,
        initial_balance: float,
        allow_negative: bool = False,
        system: bool = False,
    ) -> Wallet:
        with self._lock:
            data = self._load_data()
            existing_ids = [
                self._require_strict_int(item.get("id"), "wallet.id")
                for item in data.get("wallets", [])
                if isinstance(item, dict)
            ]
            next_id = max(existing_ids, default=0) + 1
            wallet = Wallet(
                id=next_id,
                name=str(name or f"Wallet {next_id}"),
                currency=str(currency or "KZT").upper(),
                initial_balance=float(initial_balance),
                system=bool(system),
                allow_negative=bool(allow_negative),
                is_active=True,
            )
            data["wallets"].append(self._wallet_to_dict(wallet))
            self._save_data(data)
            return wallet

    def save_wallet(self, wallet: Wallet) -> None:
        with self._lock:
            data = self._load_data()
            wallets = data.get("wallets", [])
            updated = False
            for index, item in enumerate(wallets):
                if isinstance(item, dict) and int(item.get("id", 0)) == wallet.id:
                    wallets[index] = self._wallet_to_dict(wallet)
                    updated = True
                    break
            if not updated:
                wallets.append(self._wallet_to_dict(wallet))
            data["wallets"] = wallets
            self._save_data(data)

    def soft_delete_wallet(self, wallet_id: int) -> bool:
        with self._lock:
            data = self._load_data()
            wallets = data.get("wallets", [])
            for item in wallets:
                if isinstance(item, dict) and int(item.get("id", 0)) == int(wallet_id):
                    if bool(item.get("system", False)):
                        return False
                    item["is_active"] = False
                    data["wallets"] = wallets
                    self._save_data(data)
                    return True
            return False

    def get_system_wallet(self) -> Wallet:
        wallets = self.load_wallets()
        for wallet in wallets:
            if wallet.id == SYSTEM_WALLET_ID or wallet.system:
                return wallet
        return Wallet(
            id=SYSTEM_WALLET_ID,
            name="Main wallet",
            currency="KZT",
            initial_balance=0.0,
            system=True,
            allow_negative=False,
            is_active=True,
        )

    @staticmethod
    def _transfer_to_dict(transfer: Transfer) -> dict:
        return {
            "id": int(transfer.id),
            "from_wallet_id": int(transfer.from_wallet_id),
            "to_wallet_id": int(transfer.to_wallet_id),
            "date": transfer.date.isoformat()
            if isinstance(transfer.date, dt_date)
            else transfer.date,
            "amount_original": float(transfer.amount_original),
            "currency": str(transfer.currency).upper(),
            "rate_at_operation": float(transfer.rate_at_operation),
            "amount_kzt": float(transfer.amount_kzt),
            "description": str(transfer.description or ""),
        }

    def save_transfer(self, transfer: Transfer) -> None:
        with self._lock:
            data = self._load_data()
            transfers = data.get("transfers", [])
            replaced = False
            for index, item in enumerate(transfers):
                if isinstance(item, dict) and int(item.get("id", 0)) == transfer.id:
                    transfers[index] = self._transfer_to_dict(transfer)
                    replaced = True
                    break
            if not replaced:
                transfers.append(self._transfer_to_dict(transfer))
            data["transfers"] = transfers
            self._save_data(data)

    def load_transfers(self) -> list[Transfer]:
        data = self._load_data()
        transfers: list[Transfer] = []
        for index, item in enumerate(data.get("transfers", [])):
            if not isinstance(item, dict):
                logger.warning("Skipping non-dict transfer at index %s", index)
                continue
            try:
                transfers.append(
                    Transfer(
                        id=self._require_strict_int(item.get("id"), "transfer.id"),
                        from_wallet_id=self._require_strict_int(
                            item.get("from_wallet_id"), "transfer.from_wallet_id"
                        ),
                        to_wallet_id=self._require_strict_int(
                            item.get("to_wallet_id"), "transfer.to_wallet_id"
                        ),
                        date=str(item.get("date", "") or ""),
                        amount_original=self._as_float(item.get("amount_original"), 0.0),
                        currency=str(item.get("currency", "KZT") or "KZT").upper(),
                        rate_at_operation=self._as_float(item.get("rate_at_operation"), 1.0),
                        amount_kzt=self._as_float(item.get("amount_kzt"), 0.0),
                        description=str(item.get("description", "") or ""),
                    )
                )
            except Exception:
                logger.exception("Skipping invalid transfer at index %s", index)
        return transfers

    def save(self, record: Record) -> None:
        with self._lock:
            data = self._load_data()
            record = self._ensure_unique_record_id(record, data)
            if isinstance(record, MandatoryExpenseRecord):
                record_data = self._record_to_dict(record, "mandatory_expense")
            else:
                record_data = self._record_to_dict(
                    record, "income" if isinstance(record, IncomeRecord) else "expense"
                )
            data["records"].append(record_data)
            self._save_data(data)

    def load_all(self) -> list[Record]:
        data = self._load_data()
        records = []
        for index, item in enumerate(data.get("records", [])):
            if not isinstance(item, dict):
                logger.warning("Skipping non-dict record at index %s", index)
                continue
            try:
                typ = item.get("type", "income")
                common = self._parse_record_common(item)

                if typ == "income":
                    record = IncomeRecord(**common)
                elif typ == "expense":
                    record = ExpenseRecord(**common)
                elif typ == "mandatory_expense":
                    period = str(item.get("period", "monthly") or "monthly")
                    record = MandatoryExpenseRecord(
                        **common,
                        period=period,  # type: ignore[arg-type]
                    )
                else:
                    logger.warning("Unknown record type '%s' at index %s, skipping", typ, index)
                    continue
                records.append(record)
            except Exception as e:
                logger.exception("Skipping invalid record at index %s: %s", index, e)
                continue
        return records

    def list_all(self) -> list[Record]:
        return self.load_all()

    def get_by_id(self, record_id: int) -> Record:
        record_id = int(record_id)
        for record in self.load_all():
            if int(getattr(record, "id", 0)) == record_id:
                return record
        raise ValueError(f"Record not found: {record_id}")

    def replace(self, record: Record) -> None:
        target_id = int(getattr(record, "id", 0))
        if target_id <= 0:
            raise ValueError("Record id must be positive")
        with self._lock:
            data = self._load_data()
            updated = False
            for index, item in enumerate(data.get("records", [])):
                if isinstance(item, dict) and self._as_int(item.get("id"), 0) == target_id:
                    record_type = (
                        "mandatory_expense"
                        if isinstance(record, MandatoryExpenseRecord)
                        else ("income" if isinstance(record, IncomeRecord) else "expense")
                    )
                    data["records"][index] = self._record_to_dict(record, record_type)
                    updated = True
                    break
            if not updated:
                raise ValueError(f"Record not found: {target_id}")
            self._save_data(data)

    def delete_by_index(self, index: int) -> bool:
        """Delete record by index. Returns True if deleted, False if index out of range."""
        with self._lock:
            data = self._load_data()
            if 0 <= index < len(data["records"]):
                data["records"].pop(index)
                self._save_data(data)
                return True
            return False

    def delete_all(self) -> None:
        """Delete all records."""
        with self._lock:
            data = self._load_data()
            data["records"] = []
            self._save_data(data)

    def save_initial_balance(self, balance: float) -> None:
        """Save initial balance to the system wallet (legacy API)."""
        with self._lock:
            data = self._load_data()
            wallets = data.get("wallets", [])
            updated = False
            for wallet in wallets:
                if isinstance(wallet, dict) and int(wallet.get("id", 0)) == SYSTEM_WALLET_ID:
                    wallet["initial_balance"] = float(balance)
                    wallet["system"] = True
                    updated = True
                    break
            if not updated:
                base_currency = self._resolve_base_currency(data.get("records", []))
                wallets.insert(0, self._build_system_wallet(base_currency, float(balance)))
            data["wallets"] = wallets
            self._save_data(data)

    def load_initial_balance(self) -> float:
        """Load system-wallet initial balance (legacy API)."""
        return self.get_system_wallet().initial_balance

    def save_mandatory_expense(self, expense: MandatoryExpenseRecord) -> None:
        """Save mandatory expense."""
        with self._lock:
            data = self._load_data()
            next_id = self._next_mandatory_id_from_items(data.get("mandatory_expenses", []))
            expense = dc_replace(expense, id=next_id)
            if "mandatory_expenses" not in data:
                data["mandatory_expenses"] = []
            expense_data = self._record_to_dict(expense, "mandatory_expense")
            expense_data.pop("type", None)
            expense_data.pop("date", None)
            data["mandatory_expenses"].append(expense_data)
            self._save_data(data)

    def load_mandatory_expenses(self) -> list[MandatoryExpenseRecord]:
        """Load all mandatory expenses."""
        data = self._load_data()
        expenses = []
        for index, item in enumerate(data.get("mandatory_expenses", [])):
            if not isinstance(item, dict):
                logger.warning("Skipping non-dict mandatory expense at index %s", index)
                continue
            try:
                common = self._parse_record_common(item)
                expense = MandatoryExpenseRecord(
                    **common,
                    period=str(item.get("period", "monthly") or "monthly"),  # type: ignore[arg-type]
                )
                expenses.append(expense)
            except Exception:
                logger.exception(
                    "Skipping invalid mandatory expense at index %s",
                    index,
                )
        return expenses

    def delete_mandatory_expense_by_index(self, index: int) -> bool:
        """Delete mandatory expense by index. Returns True if deleted."""
        with self._lock:
            data = self._load_data()
            if "mandatory_expenses" in data and 0 <= index < len(data["mandatory_expenses"]):
                data["mandatory_expenses"].pop(index)
                self._save_data(data)
                return True
            return False

    def delete_all_mandatory_expenses(self) -> None:
        """Delete all mandatory expenses."""
        with self._lock:
            data = self._load_data()
            data["mandatory_expenses"] = []
            self._save_data(data)

    def replace_records(self, records: list[Record], initial_balance: float) -> None:
        with self._lock:
            data = self._load_data()
            wallets = data.get("wallets", [])
            updated = False
            for wallet in wallets:
                if isinstance(wallet, dict) and int(wallet.get("id", 0)) == SYSTEM_WALLET_ID:
                    wallet["initial_balance"] = float(initial_balance)
                    wallet["system"] = True
                    updated = True
                    break
            if not updated:
                base_currency = self._resolve_base_currency(data.get("records", []))
                wallets.insert(0, self._build_system_wallet(base_currency, float(initial_balance)))
            data["wallets"] = wallets
            data["records"] = []
            for record in records:
                if isinstance(record, MandatoryExpenseRecord):
                    data["records"].append(self._record_to_dict(record, "mandatory_expense"))
                else:
                    record_type = "income" if isinstance(record, IncomeRecord) else "expense"
                    data["records"].append(self._record_to_dict(record, record_type))
            self._save_data(data)

    def replace_mandatory_expenses(self, expenses: list[MandatoryExpenseRecord]) -> None:
        with self._lock:
            data = self._load_data()
            data["mandatory_expenses"] = []
            for index, expense in enumerate(expenses, start=1):
                payload = self._record_to_dict(dc_replace(expense, id=index), "mandatory_expense")
                payload.pop("type", None)
                payload.pop("date", None)
                data["mandatory_expenses"].append(payload)
            self._save_data(data)

    def replace_records_and_transfers(
        self, records: list[Record], transfers: list[Transfer]
    ) -> None:
        with self._lock:
            data = self._load_data()
            data["records"] = []
            for record in records:
                if isinstance(record, MandatoryExpenseRecord):
                    data["records"].append(self._record_to_dict(record, "mandatory_expense"))
                else:
                    record_type = "income" if isinstance(record, IncomeRecord) else "expense"
                    data["records"].append(self._record_to_dict(record, record_type))
            data["transfers"] = [self._transfer_to_dict(transfer) for transfer in transfers]
            self._validate_transfer_integrity(data)
            self._save_data(data)

    def replace_all_data(
        self,
        *,
        initial_balance: float = 0.0,
        wallets: list[Wallet] | None = None,
        records: list[Record],
        mandatory_expenses: list[MandatoryExpenseRecord],
        transfers: list[Transfer] | None = None,
    ) -> None:
        with self._lock:
            normalized_wallets = list(wallets or [])
            if not normalized_wallets:
                base_currency = "KZT"
                for record in records:
                    currency = str(getattr(record, "currency", "") or "").upper()
                    if currency:
                        base_currency = currency
                        break
                normalized_wallets = [
                    Wallet(
                        id=SYSTEM_WALLET_ID,
                        name="Main wallet",
                        currency=base_currency,
                        initial_balance=float(initial_balance),
                        system=True,
                        allow_negative=False,
                        is_active=True,
                    )
                ]
            data = {
                "wallets": [self._wallet_to_dict(wallet) for wallet in normalized_wallets],
                "records": [],
                "mandatory_expenses": [],
                "transfers": [self._transfer_to_dict(transfer) for transfer in (transfers or [])],
            }
            for record in records:
                if isinstance(record, MandatoryExpenseRecord):
                    data["records"].append(self._record_to_dict(record, "mandatory_expense"))
                else:
                    record_type = "income" if isinstance(record, IncomeRecord) else "expense"
                    data["records"].append(self._record_to_dict(record, record_type))
            for expense in mandatory_expenses:
                payload = self._record_to_dict(expense, "mandatory_expense")
                payload.pop("type", None)
                payload.pop("date", None)
                data["mandatory_expenses"].append(payload)
            self._validate_transfer_integrity(data)
            self._save_data(data)
