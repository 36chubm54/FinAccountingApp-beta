from __future__ import annotations

import logging
import sqlite3
from datetime import date as dt_date
from typing import Any, cast

from app.data.protocols import DistributionRepositoryProtocol
from bridge.ledgera_bridge import RustDistributionCore, get_distribution_core
from domain.distribution import (
    DistributionItem,
    DistributionSubitem,
    FrozenDistributionRow,
    ItemResult,
    MonthlyDistribution,
    SubitemResult,
    ValidationError,
)
from services.planning.distribution.helpers import (
    FULL_PCT_MINOR,
    apply_pct,
    cutoff_month,
    fmt_amount,
    map_integrity_error,
    month_bounds,
    normalize_name,
    normalize_pct,
    row_to_item,
    row_to_subitem,
)
from services.support.sql_money import signed_minor_amount_expr
from utils.finance.money import minor_to_money

_RUST_DISTRIBUTION_CORE = get_distribution_core()
logger = logging.getLogger(__name__)


def _payload_int(payload: dict[str, object], key: str, default: int = 0) -> int:
    return int(cast(Any, payload.get(key, default)))


def _payload_float(payload: dict[str, object], key: str, default: float = 0.0) -> float:
    return float(cast(Any, payload.get(key, default)))


class DistributionService:
    """Reads monthly net cashflow and manages persisted distribution structure."""

    def __init__(self, repository: DistributionRepositoryProtocol) -> None:
        self._repo = repository
        self._ensure_snapshot_schema()

    def _rust_core(self, operation: str) -> tuple[RustDistributionCore | None, str | None]:
        db_path = self._db_path()
        if _RUST_DISTRIBUTION_CORE is not None and db_path:
            logger.debug("distribution_rust_path operation=%s", operation)
            return cast(RustDistributionCore, _RUST_DISTRIBUTION_CORE), db_path
        reason = "rust_core_unavailable" if _RUST_DISTRIBUTION_CORE is None else "db_path_missing"
        logger.debug("distribution_python_fallback operation=%s reason=%s", operation, reason)
        return None, None

    def _log_rust_read_fallback(self, operation: str, exc: Exception) -> None:
        logger.warning(
            "distribution_rust_read_fallback operation=%s exception_type=%s",
            operation,
            exc.__class__.__name__,
        )

    def _log_rust_mutation_failed(self, operation: str, exc: Exception) -> None:
        logger.warning(
            "distribution_rust_mutation_failed operation=%s exception_type=%s",
            operation,
            exc.__class__.__name__,
        )

    def create_item(
        self,
        name: str,
        *,
        group_name: str = "",
        sort_order: int = 0,
        pct: float = 0.0,
    ) -> DistributionItem:
        item_name = normalize_name(name, "Item name is required")
        pct_value, pct_minor = normalize_pct(pct)
        rust_core, db_path = self._rust_core("create_item")
        if rust_core is not None and db_path:
            try:
                return self._item_from_payload(
                    rust_core.distribution_create_item(
                        db_path,
                        item_name,
                        str(group_name or "").strip(),
                        int(sort_order),
                        pct_value,
                        pct_minor,
                    )
                )
            except Exception as exc:
                self._log_rust_mutation_failed("create_item", exc)
                raise
        try:
            self._repo.execute(
                """
                INSERT INTO distribution_items (name, group_name, sort_order, pct, pct_minor)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    item_name,
                    str(group_name or "").strip(),
                    int(sort_order),
                    pct_value,
                    pct_minor,
                ),
            )
            row = self._repo.query_one(
                "SELECT id FROM distribution_items WHERE rowid = last_insert_rowid()"
            )
            self._repo.commit()
        except sqlite3.IntegrityError as exc:
            raise map_integrity_error(exc, item_name, None) from exc
        if row is None:
            raise RuntimeError("Failed to retrieve inserted distribution item id")
        return self._load_item(int(row[0]))

    def get_items(self, active_only: bool = True) -> list[DistributionItem]:
        rust_core, db_path = self._rust_core("get_items")
        if rust_core is not None and db_path:
            try:
                return [
                    self._item_from_payload(row)
                    for row in rust_core.distribution_item_rows(db_path, bool(active_only))
                ]
            except Exception as exc:
                self._log_rust_read_fallback("get_items", exc)
        where = "WHERE is_active = 1" if active_only else ""
        rows = self._repo.query_all(
            f"""
            SELECT id, name, group_name, sort_order, pct, pct_minor, is_active
            FROM distribution_items
            {where}
            ORDER BY sort_order ASC, name COLLATE NOCASE ASC, id ASC
            """
        )
        return [row_to_item(row) for row in rows]

    def update_item_pct(self, item_id: int, new_pct: float) -> DistributionItem:
        pct_value, pct_minor = normalize_pct(new_pct)
        db_path = self._db_path()
        if _RUST_DISTRIBUTION_CORE is not None and db_path:
            rust_core = cast(RustDistributionCore, _RUST_DISTRIBUTION_CORE)
            return self._item_from_payload(
                rust_core.distribution_update_item_pct(
                    db_path,
                    int(item_id),
                    pct_value,
                    pct_minor,
                )
            )
        self._assert_item_exists(item_id)
        self._repo.execute(
            "UPDATE distribution_items SET pct = ?, pct_minor = ? WHERE id = ?",
            (pct_value, pct_minor, int(item_id)),
        )
        self._repo.commit()
        return self._load_item(item_id)

    def update_item_name(self, item_id: int, new_name: str) -> DistributionItem:
        item_name = normalize_name(new_name, "Item name is required")
        db_path = self._db_path()
        if _RUST_DISTRIBUTION_CORE is not None and db_path:
            rust_core = cast(RustDistributionCore, _RUST_DISTRIBUTION_CORE)
            return self._item_from_payload(
                rust_core.distribution_update_item_name(db_path, int(item_id), item_name)
            )
        self._assert_item_exists(item_id)
        try:
            self._repo.execute(
                "UPDATE distribution_items SET name = ? WHERE id = ?",
                (item_name, int(item_id)),
            )
            self._repo.commit()
        except sqlite3.IntegrityError as exc:
            raise map_integrity_error(exc, item_name, None) from exc
        return self._load_item(item_id)

    def update_item_order(self, item_id: int, new_order: int) -> None:
        db_path = self._db_path()
        if _RUST_DISTRIBUTION_CORE is not None and db_path:
            rust_core = cast(RustDistributionCore, _RUST_DISTRIBUTION_CORE)
            rust_core.distribution_update_item_order(db_path, int(item_id), int(new_order))
            return
        self._assert_item_exists(item_id)
        self._repo.execute(
            "UPDATE distribution_items SET sort_order = ? WHERE id = ?",
            (int(new_order), int(item_id)),
        )
        self._repo.commit()

    def delete_item(self, item_id: int) -> None:
        db_path = self._db_path()
        if _RUST_DISTRIBUTION_CORE is not None and db_path:
            rust_core = cast(RustDistributionCore, _RUST_DISTRIBUTION_CORE)
            rust_core.distribution_delete_item(db_path, int(item_id))
            return
        self._assert_item_exists(item_id)
        self._repo.execute("DELETE FROM distribution_items WHERE id = ?", (int(item_id),))
        self._repo.commit()

    def create_subitem(
        self,
        item_id: int,
        name: str,
        *,
        sort_order: int = 0,
        pct: float = 0.0,
    ) -> DistributionSubitem:
        subitem_name = normalize_name(name, "Subitem name is required")
        pct_value, pct_minor = normalize_pct(pct)
        db_path = self._db_path()
        if _RUST_DISTRIBUTION_CORE is not None and db_path:
            rust_core = cast(RustDistributionCore, _RUST_DISTRIBUTION_CORE)
            return self._subitem_from_payload(
                rust_core.distribution_create_subitem(
                    db_path,
                    int(item_id),
                    subitem_name,
                    int(sort_order),
                    pct_value,
                    pct_minor,
                )
            )
        self._assert_item_exists(item_id)
        try:
            self._repo.execute(
                """
                INSERT INTO distribution_subitems (item_id, name, sort_order, pct, pct_minor)
                VALUES (?, ?, ?, ?, ?)
                """,
                (int(item_id), subitem_name, int(sort_order), pct_value, pct_minor),
            )
            row = self._repo.query_one(
                "SELECT id FROM distribution_subitems WHERE rowid = last_insert_rowid()"
            )
            self._repo.commit()
        except sqlite3.IntegrityError as exc:
            raise map_integrity_error(exc, subitem_name, item_id) from exc
        if row is None:
            raise RuntimeError("Failed to retrieve inserted distribution subitem id")
        return self._load_subitem(int(row[0]))

    def get_subitems(self, item_id: int, active_only: bool = True) -> list[DistributionSubitem]:
        db_path = self._db_path()
        if _RUST_DISTRIBUTION_CORE is not None and db_path:
            try:
                rust_core = cast(RustDistributionCore, _RUST_DISTRIBUTION_CORE)
                return [
                    self._subitem_from_payload(row)
                    for row in rust_core.distribution_subitem_rows(
                        db_path,
                        int(item_id),
                        bool(active_only),
                    )
                ]
            except Exception:
                pass
        self._assert_item_exists(item_id)
        active_clause = "AND is_active = 1" if active_only else ""
        rows = self._repo.query_all(
            f"""
            SELECT id, item_id, name, sort_order, pct, pct_minor, is_active
            FROM distribution_subitems
            WHERE item_id = ? {active_clause}
            ORDER BY sort_order ASC, name COLLATE NOCASE ASC, id ASC
            """,
            (int(item_id),),
        )
        return [row_to_subitem(row) for row in rows]

    def export_structure(
        self,
    ) -> tuple[list[DistributionItem], dict[int, list[DistributionSubitem]]]:
        items = self.get_items(active_only=False)
        subitems_by_item = {
            int(item.id): self.get_subitems(item.id, active_only=False) for item in items
        }
        return items, subitems_by_item

    def replace_structure(
        self,
        items: list[DistributionItem],
        subitems_by_item: dict[int, list[DistributionSubitem]],
    ) -> None:
        db_path = self._db_path()
        if _RUST_DISTRIBUTION_CORE is not None and db_path:
            rust_core = cast(RustDistributionCore, _RUST_DISTRIBUTION_CORE)
            rust_core.distribution_replace_structure(
                db_path,
                [
                    (
                        int(item.id),
                        str(item.name),
                        str(item.group_name or ""),
                        int(item.sort_order),
                        float(item.pct),
                        int(item.pct_minor),
                        bool(item.is_active),
                    )
                    for item in items
                ],
                [
                    (
                        int(subitem.id),
                        int(subitem.item_id),
                        str(subitem.name),
                        int(subitem.sort_order),
                        float(subitem.pct),
                        int(subitem.pct_minor),
                        bool(subitem.is_active),
                    )
                    for subitems in subitems_by_item.values()
                    for subitem in subitems
                ],
            )
            return
        with self._repo.transaction():
            self._repo.execute("DELETE FROM distribution_subitems")
            self._repo.execute("DELETE FROM distribution_items")
            for item in sorted(
                items,
                key=lambda value: (
                    int(value.sort_order),
                    str(value.name).casefold(),
                    int(value.id),
                ),
            ):
                self._repo.execute(
                    """
                    INSERT INTO distribution_items (
                        id, name, group_name, sort_order, pct, pct_minor, is_active
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        int(item.id),
                        str(item.name),
                        str(item.group_name or ""),
                        int(item.sort_order),
                        float(item.pct),
                        int(item.pct_minor),
                        int(bool(item.is_active)),
                    ),
                )
            for item in sorted(
                items,
                key=lambda value: (
                    int(value.sort_order),
                    str(value.name).casefold(),
                    int(value.id),
                ),
            ):
                for subitem in sorted(
                    subitems_by_item.get(int(item.id), []),
                    key=lambda value: (
                        int(value.sort_order),
                        str(value.name).casefold(),
                        int(value.id),
                    ),
                ):
                    self._repo.execute(
                        """
                        INSERT INTO distribution_subitems (
                            id, item_id, name, sort_order, pct, pct_minor, is_active
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            int(subitem.id),
                            int(subitem.item_id),
                            str(subitem.name),
                            int(subitem.sort_order),
                            float(subitem.pct),
                            int(subitem.pct_minor),
                            int(bool(subitem.is_active)),
                        ),
                    )
            if items:
                self._repo.set_sqlite_sequence(
                    "distribution_items",
                    max(int(item.id) for item in items),
                )
            if any(subitems_by_item.values()):
                self._repo.set_sqlite_sequence(
                    "distribution_subitems",
                    max(
                        int(subitem.id)
                        for subitems in subitems_by_item.values()
                        for subitem in subitems
                    ),
                )

    def update_subitem_pct(self, subitem_id: int, new_pct: float) -> DistributionSubitem:
        pct_value, pct_minor = normalize_pct(new_pct)
        db_path = self._db_path()
        if _RUST_DISTRIBUTION_CORE is not None and db_path:
            rust_core = cast(RustDistributionCore, _RUST_DISTRIBUTION_CORE)
            return self._subitem_from_payload(
                rust_core.distribution_update_subitem_pct(
                    db_path,
                    int(subitem_id),
                    pct_value,
                    pct_minor,
                )
            )
        self._assert_subitem_exists(subitem_id)
        self._repo.execute(
            "UPDATE distribution_subitems SET pct = ?, pct_minor = ? WHERE id = ?",
            (pct_value, pct_minor, int(subitem_id)),
        )
        self._repo.commit()
        return self._load_subitem(subitem_id)

    def update_subitem_name(self, subitem_id: int, new_name: str) -> DistributionSubitem:
        subitem_name = normalize_name(new_name, "Subitem name is required")
        db_path = self._db_path()
        if _RUST_DISTRIBUTION_CORE is not None and db_path:
            rust_core = cast(RustDistributionCore, _RUST_DISTRIBUTION_CORE)
            return self._subitem_from_payload(
                rust_core.distribution_update_subitem_name(
                    db_path,
                    int(subitem_id),
                    subitem_name,
                )
            )
        row = self._repo.query_one(
            "SELECT item_id FROM distribution_subitems WHERE id = ?",
            (int(subitem_id),),
        )
        if row is None:
            raise ValueError(f"Distribution subitem not found: {subitem_id}")
        item_id = int(row[0])
        try:
            self._repo.execute(
                "UPDATE distribution_subitems SET name = ? WHERE id = ?",
                (subitem_name, int(subitem_id)),
            )
            self._repo.commit()
        except sqlite3.IntegrityError as exc:
            raise map_integrity_error(exc, subitem_name, item_id) from exc
        return self._load_subitem(subitem_id)

    def update_subitem_order(self, subitem_id: int, new_order: int) -> None:
        db_path = self._db_path()
        if _RUST_DISTRIBUTION_CORE is not None and db_path:
            rust_core = cast(RustDistributionCore, _RUST_DISTRIBUTION_CORE)
            rust_core.distribution_update_subitem_order(
                db_path,
                int(subitem_id),
                int(new_order),
            )
            return
        self._assert_subitem_exists(subitem_id)
        self._repo.execute(
            "UPDATE distribution_subitems SET sort_order = ? WHERE id = ?",
            (int(new_order), int(subitem_id)),
        )
        self._repo.commit()

    def delete_subitem(self, subitem_id: int) -> None:
        db_path = self._db_path()
        if _RUST_DISTRIBUTION_CORE is not None and db_path:
            rust_core = cast(RustDistributionCore, _RUST_DISTRIBUTION_CORE)
            rust_core.distribution_delete_subitem(db_path, int(subitem_id))
            return
        self._assert_subitem_exists(subitem_id)
        self._repo.execute("DELETE FROM distribution_subitems WHERE id = ?", (int(subitem_id),))
        self._repo.commit()

    def validate(self) -> list[ValidationError]:
        db_path = self._db_path()
        if _RUST_DISTRIBUTION_CORE is not None and db_path:
            try:
                rust_core = cast(RustDistributionCore, _RUST_DISTRIBUTION_CORE)
                return [
                    ValidationError(
                        level=str(row.get("level", "")),
                        message=str(row.get("message", "")),
                    )
                    for row in rust_core.distribution_validate_structure(db_path)
                ]
            except Exception:
                pass

        errors: list[ValidationError] = []

        row = self._repo.query_one(
            "SELECT COALESCE(SUM(pct_minor), 0) FROM distribution_items WHERE is_active = 1"
        )
        total_pct_minor = int(row[0]) if row is not None else 0
        if total_pct_minor != FULL_PCT_MINOR:
            errors.append(
                ValidationError(
                    level="error",
                    message=(
                        f"Sum of top-level item percentages is "
                        f"{minor_to_money(total_pct_minor):.2f}% (must be 100.00%)"
                    ),
                )
            )

        for item in self.get_items(active_only=True):
            row = self._repo.query_one(
                """
                SELECT COALESCE(SUM(pct_minor), 0), COUNT(*)
                FROM distribution_subitems
                WHERE item_id = ? AND is_active = 1
                """,
                (int(item.id),),
            )
            if row is None or int(row[1]) == 0:
                continue
            sub_total_minor = int(row[0])
            if sub_total_minor != FULL_PCT_MINOR:
                errors.append(
                    ValidationError(
                        level="error",
                        message=(
                            f"Sum of subitem percentages for '{item.name}' is "
                            f"{minor_to_money(sub_total_minor):.2f}% (must be 100.00%)"
                        ),
                    )
                )

        return errors

    def get_net_income_for_month(self, month: str) -> tuple[float, int]:
        start_date, end_date = month_bounds(month)
        db_path = self._db_path()
        if _RUST_DISTRIBUTION_CORE is not None and db_path:
            try:
                rust_core = cast(RustDistributionCore, _RUST_DISTRIBUTION_CORE)
                return rust_core.distribution_net_income_for_period(db_path, start_date, end_date)
            except Exception:
                pass
        row = self._repo.query_one(
            f"""
            SELECT COALESCE(SUM({signed_minor_amount_expr("amount_base")}), 0)
            FROM records
            WHERE transfer_id IS NULL
              AND date >= ?
              AND date <= ?
            """,
            (start_date, end_date),
        )
        net_minor = int(row[0]) if row is not None else 0
        return minor_to_money(net_minor), net_minor

    def get_monthly_distribution(self, month: str) -> MonthlyDistribution:
        start_date, end_date = month_bounds(month)
        db_path = self._db_path()
        if _RUST_DISTRIBUTION_CORE is not None and db_path:
            try:
                rust_core = cast(RustDistributionCore, _RUST_DISTRIBUTION_CORE)
                return self._monthly_distribution_from_payload(
                    rust_core.distribution_monthly_payload(
                        db_path,
                        month,
                        start_date,
                        end_date,
                    )
                )
            except Exception:
                pass

        net_income_base, net_income_minor = self.get_net_income_for_month(month)
        item_results: list[ItemResult] = []

        for item in self.get_items(active_only=True):
            item_minor = apply_pct(net_income_minor, item.pct_minor)
            subitem_results: list[SubitemResult] = []
            for subitem in self.get_subitems(item.id, active_only=True):
                sub_minor = apply_pct(item_minor, subitem.pct_minor)
                subitem_results.append(
                    SubitemResult(
                        subitem=subitem,
                        amount_base=minor_to_money(sub_minor),
                        amount_minor=sub_minor,
                    )
                )
            item_results.append(
                ItemResult(
                    item=item,
                    amount_base=minor_to_money(item_minor),
                    amount_minor=item_minor,
                    subitem_results=tuple(subitem_results),
                )
            )

        return MonthlyDistribution(
            month=month,
            net_income_base=net_income_base,
            net_income_minor=net_income_minor,
            item_results=tuple(item_results),
            is_negative=net_income_minor < 0,
        )

    def get_distribution_history(
        self,
        start_month: str,
        end_month: str,
    ) -> list[MonthlyDistribution]:
        month_bounds(start_month)
        month_bounds(end_month)
        if start_month > end_month:
            raise ValueError("start_month must be <= end_month")
        db_path = self._db_path()
        if _RUST_DISTRIBUTION_CORE is not None and db_path:
            try:
                rust_core = cast(RustDistributionCore, _RUST_DISTRIBUTION_CORE)
                return [
                    self.get_monthly_distribution(month)
                    for month in rust_core.distribution_history_months(
                        db_path, start_month, end_month
                    )
                ]
            except Exception:
                pass
        rows = self._repo.query_all(
            """
            SELECT DISTINCT substr(date, 1, 7) AS month
            FROM records
            WHERE transfer_id IS NULL
              AND substr(date, 1, 7) >= ?
              AND substr(date, 1, 7) <= ?
            ORDER BY month ASC
            """,
            (start_month, end_month),
        )
        return [self.get_monthly_distribution(str(row[0])) for row in rows]

    def get_available_months(self) -> list[str]:
        db_path = self._db_path()
        if _RUST_DISTRIBUTION_CORE is not None and db_path:
            try:
                rust_core = cast(RustDistributionCore, _RUST_DISTRIBUTION_CORE)
                return rust_core.distribution_available_months(db_path)
            except Exception:
                pass
        rows = self._repo.query_all(
            """
            SELECT DISTINCT substr(date, 1, 7) AS month
            FROM records
            WHERE transfer_id IS NULL
            ORDER BY month ASC
            """
        )
        return [str(row[0]) for row in rows]

    def is_month_fixed(self, month: str) -> bool:
        month_bounds(month)
        db_path = self._db_path()
        if _RUST_DISTRIBUTION_CORE is not None and db_path:
            try:
                rust_core = cast(RustDistributionCore, _RUST_DISTRIBUTION_CORE)
                return rust_core.distribution_is_month_fixed(db_path, month)
            except Exception:
                pass
        row = self._repo.query_one(
            "SELECT 1 FROM distribution_snapshots WHERE month = ?",
            (month,),
        )
        return row is not None

    def freeze_month(self, month: str, *, auto_fixed: bool = False) -> FrozenDistributionRow:
        distribution = self.get_monthly_distribution(month)
        items = self.get_items(active_only=True)
        column_order, headings_by_column = self._build_live_column_meta(items)
        values_by_column = self._distribution_row_values_map(distribution, items)
        values_by_column["month"] = month
        values_by_column["fixed"] = "Yes"
        frozen_row = FrozenDistributionRow(
            month=month,
            column_order=tuple(column_order),
            headings_by_column=dict(headings_by_column),
            values_by_column=dict(values_by_column),
            is_negative=distribution.is_negative,
            auto_fixed=bool(auto_fixed),
        )
        db_path = self._db_path()
        if _RUST_DISTRIBUTION_CORE is not None and db_path:
            rust_core = cast(RustDistributionCore, _RUST_DISTRIBUTION_CORE)
            rust_core.distribution_write_frozen_row(
                db_path,
                month,
                list(frozen_row.column_order),
                list(frozen_row.headings_by_column.items()),
                list(frozen_row.values_by_column.items()),
                bool(frozen_row.is_negative),
                bool(frozen_row.auto_fixed),
            )
            return frozen_row
        with self._repo.transaction():
            self._repo.execute(
                """
                INSERT OR REPLACE INTO distribution_snapshots (month, is_negative, auto_fixed)
                VALUES (?, ?, ?)
                """,
                (month, int(distribution.is_negative), int(bool(auto_fixed))),
            )
            self._repo.execute(
                "DELETE FROM distribution_snapshot_values WHERE snapshot_month = ?",
                (month,),
            )
            for column_index, column_id in enumerate(column_order):
                self._repo.execute(
                    """
                    INSERT INTO distribution_snapshot_values (
                        snapshot_month, column_key, column_label, column_order, value_text
                    )
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        month,
                        column_id,
                        headings_by_column.get(column_id, column_id),
                        column_index,
                        values_by_column.get(column_id, "-"),
                    ),
                )
        return frozen_row

    def freeze_closed_months(self, *, as_of: str | dt_date | None = None) -> list[str]:
        cutoff = cutoff_month(as_of)
        rows = self._repo.query_all(
            """
            SELECT DISTINCT substr(date, 1, 7) AS month
            FROM records
            WHERE transfer_id IS NULL
              AND substr(date, 1, 7) < ?
            ORDER BY month ASC
            """,
            (cutoff,),
        )
        frozen_months: list[str] = []
        for row in rows:
            month = str(row[0])
            if self.is_month_fixed(month):
                continue
            self.freeze_month(month, auto_fixed=True)
            frozen_months.append(month)
        return frozen_months

    def unfreeze_month(self, month: str) -> None:
        month_bounds(month)
        db_path = self._db_path()
        if _RUST_DISTRIBUTION_CORE is not None and db_path:
            rust_core = cast(RustDistributionCore, _RUST_DISTRIBUTION_CORE)
            rust_core.distribution_unfreeze_month(db_path, month)
            return
        if self.is_month_auto_fixed(month):
            raise ValueError(f"Month {month} is auto-fixed and cannot be unfixed")
        self._repo.execute("DELETE FROM distribution_snapshots WHERE month = ?", (month,))
        self._repo.commit()

    def toggle_month_fixed(self, month: str) -> bool:
        if self.is_month_fixed(month):
            self.unfreeze_month(month)
            return False
        self.freeze_month(month)
        return True

    def is_month_auto_fixed(self, month: str) -> bool:
        month_bounds(month)
        db_path = self._db_path()
        if _RUST_DISTRIBUTION_CORE is not None and db_path:
            try:
                rust_core = cast(RustDistributionCore, _RUST_DISTRIBUTION_CORE)
                return rust_core.distribution_is_month_auto_fixed(db_path, month)
            except Exception:
                pass
        row = self._repo.query_one(
            "SELECT auto_fixed FROM distribution_snapshots WHERE month = ?",
            (month,),
        )
        return row is not None and bool(row[0])

    def get_frozen_rows(
        self,
        start_month: str | None = None,
        end_month: str | None = None,
    ) -> list[FrozenDistributionRow]:
        if start_month is not None:
            month_bounds(start_month)
        if end_month is not None:
            month_bounds(end_month)
        if start_month is not None and end_month is not None and start_month > end_month:
            raise ValueError("start_month must be <= end_month")
        db_path = self._db_path()
        if _RUST_DISTRIBUTION_CORE is not None and db_path:
            try:
                rust_core = cast(RustDistributionCore, _RUST_DISTRIBUTION_CORE)
                return [
                    self._frozen_row_from_payload(row)
                    for row in rust_core.distribution_frozen_rows(
                        db_path,
                        start_month,
                        end_month,
                    )
                ]
            except Exception:
                pass
        clauses: list[str] = []
        params: list[str] = []
        if start_month is not None:
            clauses.append("month >= ?")
            params.append(start_month)
        if end_month is not None:
            clauses.append("month <= ?")
            params.append(end_month)
        where_clause = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        snapshot_rows = self._repo.query_all(
            f"""
            SELECT month, is_negative, auto_fixed
            FROM distribution_snapshots
            {where_clause}
            ORDER BY month ASC
            """,
            tuple(params),
        )
        if not snapshot_rows:
            return []

        value_rows = self._repo.query_all(
            f"""
            SELECT snapshot_month, column_key, column_label, column_order, value_text
            FROM distribution_snapshot_values
            WHERE snapshot_month IN (
                SELECT month FROM distribution_snapshots
                {where_clause}
            )
            ORDER BY snapshot_month ASC, column_order ASC
            """,
            tuple(params),
        )

        values_by_month: dict[str, dict[str, str]] = {}
        headings_by_month: dict[str, dict[str, str]] = {}
        order_by_month: dict[str, list[str]] = {}
        for snapshot_month, column_key, column_label, _column_order, value_text in value_rows:
            month_key = str(snapshot_month)
            values_by_month.setdefault(month_key, {})[str(column_key)] = str(value_text)
            headings_by_month.setdefault(month_key, {})[str(column_key)] = str(column_label)
            order_by_month.setdefault(month_key, []).append(str(column_key))

        frozen_rows: list[FrozenDistributionRow] = []
        for month_value, is_negative, auto_fixed in snapshot_rows:
            month_key = str(month_value)
            frozen_rows.append(
                FrozenDistributionRow(
                    month=month_key,
                    column_order=tuple(order_by_month.get(month_key, [])),
                    headings_by_column=dict(headings_by_month.get(month_key, {})),
                    values_by_column=dict(values_by_month.get(month_key, {})),
                    is_negative=bool(is_negative),
                    auto_fixed=bool(auto_fixed),
                )
            )
        return frozen_rows

    def replace_frozen_rows(self, rows: list[FrozenDistributionRow]) -> None:
        db_path = self._db_path()
        if _RUST_DISTRIBUTION_CORE is not None and db_path:
            rust_core = cast(RustDistributionCore, _RUST_DISTRIBUTION_CORE)
            rust_core.distribution_replace_frozen_rows(
                db_path,
                [
                    (
                        row.month,
                        list(row.column_order),
                        list(row.headings_by_column.items()),
                        list(row.values_by_column.items()),
                        bool(row.is_negative),
                        bool(row.auto_fixed),
                    )
                    for row in rows
                ],
            )
            return
        with self._repo.transaction():
            self._repo.execute("DELETE FROM distribution_snapshot_values")
            self._repo.execute("DELETE FROM distribution_snapshots")
            for frozen_row in sorted(rows, key=lambda item: item.month):
                month_bounds(frozen_row.month)
                self._repo.execute(
                    """
                    INSERT INTO distribution_snapshots (month, is_negative, auto_fixed)
                    VALUES (?, ?, ?)
                    """,
                    (frozen_row.month, int(frozen_row.is_negative), int(frozen_row.auto_fixed)),
                )
                for column_index, column_id in enumerate(frozen_row.column_order):
                    self._repo.execute(
                        """
                        INSERT INTO distribution_snapshot_values (
                            snapshot_month, column_key, column_label, column_order, value_text
                        )
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        (
                            frozen_row.month,
                            column_id,
                            frozen_row.headings_by_column.get(column_id, column_id),
                            column_index,
                            frozen_row.values_by_column.get(column_id, "-"),
                        ),
                    )

    def _load_item(self, item_id: int) -> DistributionItem:
        row = self._repo.query_one(
            """
            SELECT id, name, group_name, sort_order, pct, pct_minor, is_active
            FROM distribution_items
            WHERE id = ?
            """,
            (int(item_id),),
        )
        if row is None:
            raise ValueError(f"Distribution item not found: {item_id}")
        return row_to_item(row)

    def _load_subitem(self, subitem_id: int) -> DistributionSubitem:
        row = self._repo.query_one(
            """
            SELECT id, item_id, name, sort_order, pct, pct_minor, is_active
            FROM distribution_subitems
            WHERE id = ?
            """,
            (int(subitem_id),),
        )
        if row is None:
            raise ValueError(f"Distribution subitem not found: {subitem_id}")
        return row_to_subitem(row)

    def _assert_item_exists(self, item_id: int) -> None:
        row = self._repo.query_one(
            "SELECT id FROM distribution_items WHERE id = ?",
            (int(item_id),),
        )
        if row is None:
            raise ValueError(f"Distribution item not found: {item_id}")

    def _assert_subitem_exists(self, subitem_id: int) -> None:
        row = self._repo.query_one(
            "SELECT id FROM distribution_subitems WHERE id = ?",
            (int(subitem_id),),
        )
        if row is None:
            raise ValueError(f"Distribution subitem not found: {subitem_id}")

    def _build_live_column_meta(
        self,
        items: list[DistributionItem],
    ) -> tuple[list[str], dict[str, str]]:
        column_ids = ["month", "fixed", "net_income"]
        headings = {
            "month": "Month",
            "fixed": "Fixed",
            "net_income": "Net income",
        }
        for item in items:
            item_key = f"item_{item.id}"
            column_ids.append(item_key)
            headings[item_key] = item.name
            for subitem in self.get_subitems(item.id):
                sub_key = f"sub_{subitem.id}"
                column_ids.append(sub_key)
                headings[sub_key] = f"  {subitem.name}"
        return column_ids, headings

    def _distribution_row_values_map(
        self,
        distribution: MonthlyDistribution,
        items: list[DistributionItem],
    ) -> dict[str, str]:
        item_results = {result.item.id: result for result in distribution.item_results}
        values = {
            "month": distribution.month,
            "fixed": "",
            "net_income": fmt_amount(distribution.net_income_base),
        }
        for item in items:
            result = item_results.get(item.id)
            item_key = f"item_{item.id}"
            if result is None:
                values[item_key] = "-"
                continue
            values[item_key] = fmt_amount(result.amount_base)
            sub_results = {sub.subitem.id: sub for sub in result.subitem_results}
            for subitem in self.get_subitems(item.id):
                sub_key = f"sub_{subitem.id}"
                sub_result = sub_results.get(subitem.id)
                values[sub_key] = "-" if sub_result is None else fmt_amount(sub_result.amount_base)
        return values

    def _db_path(self) -> str | None:
        db_path = getattr(self._repo, "db_path", None)
        return db_path if isinstance(db_path, str) and db_path else None

    def _item_from_payload(self, payload: dict[str, object]) -> DistributionItem:
        return DistributionItem(
            id=_payload_int(payload, "id"),
            name=str(payload.get("name", "")),
            group_name=str(payload.get("group_name", "")),
            sort_order=_payload_int(payload, "sort_order"),
            pct=_payload_float(payload, "pct"),
            pct_minor=_payload_int(payload, "pct_minor"),
            is_active=bool(payload.get("is_active", False)),
        )

    def _subitem_from_payload(self, payload: dict[str, object]) -> DistributionSubitem:
        return DistributionSubitem(
            id=_payload_int(payload, "id"),
            item_id=_payload_int(payload, "item_id"),
            name=str(payload.get("name", "")),
            sort_order=_payload_int(payload, "sort_order"),
            pct=_payload_float(payload, "pct"),
            pct_minor=_payload_int(payload, "pct_minor"),
            is_active=bool(payload.get("is_active", False)),
        )

    def _frozen_row_from_payload(self, payload: dict[str, object]) -> FrozenDistributionRow:
        column_order = tuple(
            str(value) for value in cast(list[object], payload.get("column_order", []))
        )
        headings_raw = cast(dict[str, object], payload.get("headings_by_column", {}))
        values_raw = cast(dict[str, object], payload.get("values_by_column", {}))
        return FrozenDistributionRow(
            month=str(payload.get("month", "")),
            column_order=column_order,
            headings_by_column={str(key): str(value) for key, value in headings_raw.items()},
            values_by_column={str(key): str(value) for key, value in values_raw.items()},
            is_negative=bool(payload.get("is_negative", False)),
            auto_fixed=bool(payload.get("auto_fixed", False)),
        )

    def _monthly_distribution_from_payload(self, payload: dict[str, object]) -> MonthlyDistribution:
        item_results: list[ItemResult] = []
        for item_payload in cast(list[dict[str, object]], payload.get("items", [])):
            item = DistributionItem(
                id=_payload_int(item_payload, "id"),
                name=str(item_payload.get("name", "")),
                group_name=str(item_payload.get("group_name", "")),
                sort_order=_payload_int(item_payload, "sort_order"),
                pct=_payload_float(item_payload, "pct"),
                pct_minor=_payload_int(item_payload, "pct_minor"),
                is_active=bool(item_payload.get("is_active", False)),
            )
            subitem_results: list[SubitemResult] = []
            for subitem_payload in cast(list[dict[str, object]], item_payload.get("subitems", [])):
                subitem = DistributionSubitem(
                    id=_payload_int(subitem_payload, "id"),
                    item_id=_payload_int(subitem_payload, "item_id"),
                    name=str(subitem_payload.get("name", "")),
                    sort_order=_payload_int(subitem_payload, "sort_order"),
                    pct=_payload_float(subitem_payload, "pct"),
                    pct_minor=_payload_int(subitem_payload, "pct_minor"),
                    is_active=bool(subitem_payload.get("is_active", False)),
                )
                subitem_results.append(
                    SubitemResult(
                        subitem=subitem,
                        amount_base=_payload_float(subitem_payload, "amount_base"),
                        amount_minor=_payload_int(subitem_payload, "amount_minor"),
                    )
                )
            item_results.append(
                ItemResult(
                    item=item,
                    amount_base=_payload_float(item_payload, "amount_base"),
                    amount_minor=_payload_int(item_payload, "amount_minor"),
                    subitem_results=tuple(subitem_results),
                )
            )
        return MonthlyDistribution(
            month=str(payload.get("month", "")),
            net_income_base=_payload_float(payload, "net_income_base"),
            net_income_minor=_payload_int(payload, "net_income_minor"),
            item_results=tuple(item_results),
            is_negative=bool(payload.get("is_negative", False)),
        )

    def _ensure_snapshot_schema(self) -> None:
        snapshot_columns = {
            str(row[1]) for row in self._repo.query_all("PRAGMA table_info(distribution_snapshots)")
        }
        if "auto_fixed" in snapshot_columns:
            return
        self._repo.execute(
            """
            ALTER TABLE distribution_snapshots
            ADD COLUMN auto_fixed INTEGER NOT NULL DEFAULT 0 CHECK(auto_fixed IN (0, 1))
            """
        )
        self._repo.commit()
