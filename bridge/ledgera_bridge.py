from __future__ import annotations

import importlib
from types import ModuleType
from typing import Protocol, cast


class RustMoneyCore(Protocol):
    def build_rate(self, amount_original: object, amount_base: object, currency: str) -> float: ...

    def minor_to_money(self, value: object) -> float: ...

    def money_diff_text(self, left: object, right: object) -> str: ...

    def money_abs(self, value: object) -> float: ...

    def quantize_money_text(self, value: object) -> str: ...

    def quantize_rate_text(self, value: object) -> str: ...

    def rate_diff_text(self, left: object, right: object) -> str: ...

    def rate_to_text(self, value: object) -> str: ...

    def to_minor_units(self, value: object) -> int: ...

    def to_money_float(self, value: object) -> float: ...

    def to_rate_float(self, value: object) -> float: ...


class RustBalanceCore(Protocol):
    def cashflow_sum(
        self, db_path: str, record_type: str, start_date: str, end_date: str
    ) -> float: ...

    def wallet_balance_parts(
        self, db_path: str, wallet_id: int, up_to_date: str | None = None
    ) -> tuple[float, str, float] | None: ...

    def wallet_balance_rows(
        self, db_path: str, up_to_date: str | None = None
    ) -> list[tuple[int, str, str, float, float]]: ...


class RustRepositoryReadCore(Protocol):
    def mandatory_expense_row(self, db_path: str, expense_id: int) -> dict[str, object] | None: ...

    def mandatory_expense_rows(self, db_path: str) -> list[dict[str, object]]: ...

    def record_get_row(self, db_path: str, record_id: int) -> dict[str, object] | None: ...

    def record_list_rows(self, db_path: str) -> list[dict[str, object]]: ...

    def record_rows_by_tag(self, db_path: str, tag_name: str) -> list[dict[str, object]]: ...

    def transfer_id_by_record_index(self, db_path: str, index: int) -> int | None: ...

    def transfer_list_rows(self, db_path: str) -> list[dict[str, object]]: ...

    def wallet_list_rows(self, db_path: str) -> list[dict[str, object]]: ...


_EXTENSION_IMPORT = "ledgera_core.ledgera_core"

_MONEY_SYMBOLS = (
    "build_rate",
    "minor_to_money",
    "money_diff_text",
    "money_abs",
    "quantize_money_text",
    "quantize_rate_text",
    "rate_diff_text",
    "rate_to_text",
    "to_minor_units",
    "to_money_float",
    "to_rate_float",
)
_BALANCE_SYMBOLS = ("cashflow_sum", "wallet_balance_parts", "wallet_balance_rows")
_REPOSITORY_SYMBOLS = (
    "mandatory_expense_row",
    "mandatory_expense_rows",
    "record_get_row",
    "record_list_rows",
    "record_rows_by_tag",
    "transfer_id_by_record_index",
    "transfer_list_rows",
    "wallet_list_rows",
)


def load_extension_module() -> ModuleType | None:
    try:
        return importlib.import_module(_EXTENSION_IMPORT)
    except Exception:
        return None


def _has_symbols(module: ModuleType | None, required: tuple[str, ...]) -> bool:
    return module is not None and all(callable(getattr(module, name, None)) for name in required)


def get_money_core() -> RustMoneyCore | None:
    module = load_extension_module()
    if not _has_symbols(module, _MONEY_SYMBOLS):
        return None
    return cast(RustMoneyCore, module)


def get_balance_core() -> RustBalanceCore | None:
    module = load_extension_module()
    if not _has_symbols(module, _BALANCE_SYMBOLS):
        return None
    return cast(RustBalanceCore, module)


def get_repository_read_core() -> RustRepositoryReadCore | None:
    module = load_extension_module()
    if not _has_symbols(module, _REPOSITORY_SYMBOLS):
        return None
    return cast(RustRepositoryReadCore, module)


__all__ = [
    "RustBalanceCore",
    "RustMoneyCore",
    "RustRepositoryReadCore",
    "get_balance_core",
    "get_money_core",
    "get_repository_read_core",
    "load_extension_module",
]
