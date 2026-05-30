from __future__ import annotations

import importlib
import os
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


class RustMetricsCore(Protocol):
    def metrics_burn_rate(
        self, db_path: str, start_date: str, end_date: str, days: int
    ) -> float: ...

    def metrics_income_by_category(
        self, db_path: str, start_date: str, end_date: str, limit: int | None = None
    ) -> list[dict[str, object]]: ...

    def metrics_monthly_summary(
        self, db_path: str, start_date: str | None = None, end_date: str | None = None
    ) -> list[dict[str, object]]: ...

    def metrics_period_snapshot(
        self,
        db_path: str,
        start_date: str,
        end_date: str,
        days: int,
        category_limit: int | None = None,
        tag_limit: int | None = None,
    ) -> dict[str, object]: ...

    def metrics_period_snapshot_compact(
        self,
        db_path: str,
        start_date: str,
        end_date: str,
        days: int,
        category_limit: int | None = None,
        tag_limit: int | None = None,
    ) -> tuple[
        float,
        float,
        list[tuple[str, float, int]],
        list[tuple[str, float, int]],
        list[tuple[str, str, float, int]],
        tuple[int, int, float],
        list[tuple[str, float, float, float, float]],
        list[tuple[str, float, float, float]],
    ]: ...

    def metrics_refresh_snapshot_compact(
        self,
        db_path: str,
        start_date: str,
        end_date: str,
        days: int,
        category_limit: int | None = None,
        tag_limit: int | None = None,
    ) -> tuple[
        float,
        float,
        list[tuple[str, float, int]],
        list[tuple[str, float, int]],
        list[tuple[str, str, float, int]],
        list[tuple[str, float, float, float, float]],
    ]: ...

    def metrics_savings_rate(self, db_path: str, start_date: str, end_date: str) -> float: ...

    def metrics_spending_by_category(
        self, db_path: str, start_date: str, end_date: str, limit: int | None = None
    ) -> list[dict[str, object]]: ...

    def metrics_spending_by_tag(
        self, db_path: str, start_date: str, end_date: str, limit: int | None = None
    ) -> list[dict[str, object]]: ...

    def metrics_tag_coverage(
        self, db_path: str, start_date: str, end_date: str
    ) -> dict[str, object]: ...


class RustTimelineCore(Protocol):
    def timeline_cumulative_income_expense(self, db_path: str) -> list[dict[str, object]]: ...

    def timeline_monthly_cashflow(
        self, db_path: str, start_date: str | None = None, end_date: str | None = None
    ) -> list[dict[str, object]]: ...

    def timeline_net_worth_monthly_deltas(self, db_path: str) -> list[dict[str, object]]: ...


class RustCurrencyCore(Protocol):
    def currency_default_rates_for_base(
        self, base_currency: str, rates: dict[str, float]
    ) -> dict[str, float]: ...

    def currency_rate_for(
        self, currency: str, base_currency: str, rates: dict[str, float]
    ) -> float: ...

    def currency_resolve_provider_order(
        self,
        base_currency: str,
        provider_mode: str,
        primary_provider: str,
        fallback_provider: str,
        commercial_fallback_provider: str,
        enable_cbr: bool,
        provider_order: list[str] | None = None,
    ) -> list[str]: ...


class RustDistributionCore(Protocol):
    def distribution_available_months(self, db_path: str) -> list[str]: ...

    def distribution_create_item(
        self,
        db_path: str,
        name: str,
        group_name: str,
        sort_order: int,
        pct: float,
        pct_minor: int,
    ) -> dict[str, object]: ...

    def distribution_create_subitem(
        self,
        db_path: str,
        item_id: int,
        name: str,
        sort_order: int,
        pct: float,
        pct_minor: int,
    ) -> dict[str, object]: ...

    def distribution_delete_item(self, db_path: str, item_id: int) -> None: ...

    def distribution_delete_subitem(self, db_path: str, subitem_id: int) -> None: ...

    def distribution_frozen_rows(
        self, db_path: str, start_month: str | None = None, end_month: str | None = None
    ) -> list[dict[str, object]]: ...

    def distribution_history_months(
        self, db_path: str, start_month: str, end_month: str
    ) -> list[str]: ...

    def distribution_is_month_auto_fixed(self, db_path: str, month: str) -> bool: ...

    def distribution_is_month_fixed(self, db_path: str, month: str) -> bool: ...

    def distribution_item_rows(
        self, db_path: str, active_only: bool
    ) -> list[dict[str, object]]: ...

    def distribution_monthly_payload(
        self, db_path: str, month: str, start_date: str, end_date: str
    ) -> dict[str, object]: ...

    def distribution_net_income_for_period(
        self, db_path: str, start_date: str, end_date: str
    ) -> tuple[float, int]: ...

    def distribution_validate_structure(self, db_path: str) -> list[dict[str, object]]: ...

    def distribution_replace_frozen_rows(
        self,
        db_path: str,
        rows: list[
            tuple[
                str,
                list[str],
                list[tuple[str, str]],
                list[tuple[str, str]],
                bool,
                bool,
            ]
        ],
    ) -> None: ...

    def distribution_replace_structure(
        self,
        db_path: str,
        items: list[tuple[int, str, str, int, float, int, bool]],
        subitems: list[tuple[int, int, str, int, float, int, bool]],
    ) -> None: ...

    def distribution_subitem_rows(
        self, db_path: str, item_id: int, active_only: bool
    ) -> list[dict[str, object]]: ...

    def distribution_unfreeze_month(self, db_path: str, month: str) -> None: ...

    def distribution_update_item_name(
        self, db_path: str, item_id: int, name: str
    ) -> dict[str, object]: ...

    def distribution_update_item_order(
        self, db_path: str, item_id: int, sort_order: int
    ) -> None: ...

    def distribution_update_item_pct(
        self, db_path: str, item_id: int, pct: float, pct_minor: int
    ) -> dict[str, object]: ...

    def distribution_update_subitem_name(
        self, db_path: str, subitem_id: int, name: str
    ) -> dict[str, object]: ...

    def distribution_update_subitem_order(
        self, db_path: str, subitem_id: int, sort_order: int
    ) -> None: ...

    def distribution_update_subitem_pct(
        self, db_path: str, subitem_id: int, pct: float, pct_minor: int
    ) -> dict[str, object]: ...

    def distribution_write_frozen_row(
        self,
        db_path: str,
        month: str,
        column_order: list[str],
        headings_by_column: list[tuple[str, str]],
        values_by_column: list[tuple[str, str]],
        is_negative: bool,
        auto_fixed: bool,
    ) -> None: ...


class RustBudgetPlanningCore(Protocol):
    def budget_batch_spent_minor(
        self, db_path: str, budgets: list[tuple[int, str, str, str, str, bool]]
    ) -> list[tuple[int, int]]: ...

    def budget_create(
        self,
        db_path: str,
        category: str,
        scope_type: str,
        scope_value: str,
        start_date: str,
        end_date: str,
        limit_base: float,
        limit_base_minor: int,
        include_mandatory: bool,
    ) -> dict[str, object]: ...

    def budget_delete(self, db_path: str, budget_id: int) -> None: ...

    def budget_overlap_exists(
        self,
        db_path: str,
        scope_type: str,
        scope_value: str,
        start_date: str,
        end_date: str,
        exclude_id: int | None = None,
    ) -> bool: ...

    def budget_replace_rows(
        self,
        db_path: str,
        rows: list[tuple[int, str, str, str, float, int, bool, str, str]],
    ) -> None: ...

    def budget_rows(self, db_path: str) -> list[dict[str, object]]: ...

    def budget_spent_minor(
        self,
        db_path: str,
        scope_type: str,
        scope_value: str,
        start_date: str,
        end_date: str,
        include_mandatory: bool,
    ) -> int: ...

    def budget_update_limit(
        self,
        db_path: str,
        budget_id: int,
        limit_base: float,
        limit_base_minor: int,
    ) -> dict[str, object]: ...


class RustDebtCore(Protocol):
    def debt_create_obligation(
        self,
        db_path: str,
        debt_payload: dict[str, object],
        open_record_payload: dict[str, object],
    ) -> dict[str, object]: ...

    def debt_delete(self, db_path: str, debt_id: int) -> None: ...

    def debt_delete_payment(
        self, db_path: str, payment_id: int, delete_linked_record: bool
    ) -> dict[str, object]: ...

    def debt_payment_rows(
        self, db_path: str, debt_id: int | None = None
    ) -> list[dict[str, object]]: ...

    def debt_payment_total_minor(self, db_path: str, debt_id: int) -> int: ...

    def debt_recalculate_payload(self, db_path: str, debt_id: int) -> dict[str, object]: ...

    def debt_register_payment(
        self,
        db_path: str,
        debt_id: int,
        payment_payload: dict[str, object],
        payment_record_payload: dict[str, object] | None = None,
    ) -> dict[str, object]: ...

    def debt_replace_rows(
        self,
        db_path: str,
        debts: list[dict[str, object]],
        payments: list[dict[str, object]],
    ) -> None: ...

    def debt_rows(self, db_path: str) -> list[dict[str, object]]: ...

    def debt_validate_payment_amount(
        self, remaining_amount_minor: int, payment_amount_minor: int
    ) -> int: ...


class RustSyncCore(Protocol):
    pass


class RustStorageControlCore(Protocol):
    def storage_clear_read_cache(self) -> None: ...


_EXTENSION_IMPORT = "ledgera_core.ledgera_core"
_ENABLE_RUST_CORE_ENV = "LEDGERA_ENABLE_RUST_CORE"
_FORCE_PYTHON_FALLBACK_ENV = "LEDGERA_FORCE_PYTHON_FALLBACK"

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
_METRICS_SYMBOLS = (
    "metrics_burn_rate",
    "metrics_income_by_category",
    "metrics_monthly_summary",
    "metrics_period_snapshot",
    "metrics_period_snapshot_compact",
    "metrics_refresh_snapshot_compact",
    "metrics_savings_rate",
    "metrics_spending_by_category",
    "metrics_spending_by_tag",
    "metrics_tag_coverage",
)
_STORAGE_CONTROL_SYMBOLS = ("storage_clear_read_cache",)
_TIMELINE_SYMBOLS = (
    "timeline_cumulative_income_expense",
    "timeline_monthly_cashflow",
    "timeline_net_worth_monthly_deltas",
)
_CURRENCY_SYMBOLS = (
    "currency_default_rates_for_base",
    "currency_rate_for",
    "currency_resolve_provider_order",
)
_DISTRIBUTION_SYMBOLS = (
    "distribution_available_months",
    "distribution_create_item",
    "distribution_create_subitem",
    "distribution_delete_item",
    "distribution_delete_subitem",
    "distribution_frozen_rows",
    "distribution_history_months",
    "distribution_is_month_auto_fixed",
    "distribution_is_month_fixed",
    "distribution_item_rows",
    "distribution_monthly_payload",
    "distribution_net_income_for_period",
    "distribution_replace_frozen_rows",
    "distribution_replace_structure",
    "distribution_subitem_rows",
    "distribution_unfreeze_month",
    "distribution_update_item_name",
    "distribution_update_item_order",
    "distribution_update_item_pct",
    "distribution_update_subitem_name",
    "distribution_update_subitem_order",
    "distribution_update_subitem_pct",
    "distribution_validate_structure",
    "distribution_write_frozen_row",
)
_BUDGET_PLANNING_SYMBOLS = (
    "budget_batch_spent_minor",
    "budget_create",
    "budget_delete",
    "budget_overlap_exists",
    "budget_replace_rows",
    "budget_rows",
    "budget_spent_minor",
    "budget_update_limit",
)
_DEBT_SYMBOLS = (
    "debt_create_obligation",
    "debt_delete",
    "debt_delete_payment",
    "debt_payment_rows",
    "debt_payment_total_minor",
    "debt_recalculate_payload",
    "debt_register_payment",
    "debt_replace_rows",
    "debt_rows",
    "debt_validate_payment_amount",
)
_SYNC_SYMBOLS = ("sync_start_daemon", "sync_stop_daemon")


def is_python_fallback_forced() -> bool:
    value = os.environ.get(_FORCE_PYTHON_FALLBACK_ENV, "")
    return value.strip().lower() in {"1", "true", "yes", "on"}


def is_rust_core_enabled() -> bool:
    value = os.environ.get(_ENABLE_RUST_CORE_ENV, "")
    return value.strip().lower() in {"1", "true", "yes", "on"}


def load_extension_module() -> ModuleType | None:
    if is_python_fallback_forced() or not is_rust_core_enabled():
        return None
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


def get_metrics_core() -> RustMetricsCore | None:
    module = load_extension_module()
    if not _has_symbols(module, _METRICS_SYMBOLS):
        return None
    return cast(RustMetricsCore, module)


def get_timeline_core() -> RustTimelineCore | None:
    module = load_extension_module()
    if not _has_symbols(module, _TIMELINE_SYMBOLS):
        return None
    return cast(RustTimelineCore, module)


def get_currency_core() -> RustCurrencyCore | None:
    module = load_extension_module()
    if not _has_symbols(module, _CURRENCY_SYMBOLS):
        return None
    return cast(RustCurrencyCore, module)


def get_distribution_core() -> RustDistributionCore | None:
    module = load_extension_module()
    if not _has_symbols(module, _DISTRIBUTION_SYMBOLS):
        return None
    return cast(RustDistributionCore, module)


def get_budget_planning_core() -> RustBudgetPlanningCore | None:
    module = load_extension_module()
    if not _has_symbols(module, _BUDGET_PLANNING_SYMBOLS):
        return None
    return cast(RustBudgetPlanningCore, module)


def get_debt_core() -> RustDebtCore | None:
    module = load_extension_module()
    if not _has_symbols(module, _DEBT_SYMBOLS):
        return None
    return cast(RustDebtCore, module)


def get_sync_core() -> RustSyncCore | None:
    module = load_extension_module()
    if not _has_symbols(module, _SYNC_SYMBOLS):
        return None
    return cast(RustSyncCore, module)


def get_storage_control_core() -> RustStorageControlCore | None:
    module = load_extension_module()
    if not _has_symbols(module, _STORAGE_CONTROL_SYMBOLS):
        return None
    return cast(RustStorageControlCore, module)


__all__ = [
    "RustBalanceCore",
    "RustCurrencyCore",
    "RustBudgetPlanningCore",
    "RustDebtCore",
    "RustDistributionCore",
    "RustMetricsCore",
    "RustMoneyCore",
    "RustRepositoryReadCore",
    "RustSyncCore",
    "RustTimelineCore",
    "RustStorageControlCore",
    "get_balance_core",
    "get_budget_planning_core",
    "get_currency_core",
    "get_debt_core",
    "get_distribution_core",
    "get_metrics_core",
    "get_money_core",
    "get_repository_read_core",
    "get_storage_control_core",
    "get_sync_core",
    "get_timeline_core",
    "is_python_fallback_forced",
    "is_rust_core_enabled",
    "load_extension_module",
]
