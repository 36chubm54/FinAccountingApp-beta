"""Distribution tab - structure editor and monthly distribution table."""

from __future__ import annotations

import logging
import tkinter as tk
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date as dt_date
from tkinter import messagebox, simpledialog, ttk
from typing import Any, Protocol

from domain.distribution import DistributionItem, FrozenDistributionRow, MonthlyDistribution
from gui.tooltip import Tooltip

logger = logging.getLogger(__name__)


class DistributionTabContext(Protocol):
    controller: Any

    def _refresh_charts(self) -> None: ...


@dataclass(slots=True)
class DistributionTabBindings:
    structure_tree: ttk.Treeview
    validation_label: ttk.Label
    period_from_var: tk.StringVar
    period_to_var: tk.StringVar
    results_tree: ttk.Treeview
    status_label: ttk.Label
    refresh: Callable[[], None]


def build_distribution_tab(
    parent: tk.Frame | ttk.Frame,
    *,
    context: DistributionTabContext,
) -> DistributionTabBindings:
    parent.grid_columnconfigure(0, weight=1)
    parent.grid_rowconfigure(0, weight=1)

    content = ttk.Frame(parent)
    content.grid(row=0, column=0, sticky="nsew", padx=10, pady=8)
    content.grid_columnconfigure(0, minsize=400, weight=0)
    content.grid_columnconfigure(1, weight=1)
    content.grid_rowconfigure(0, weight=1)

    left_frame = ttk.Frame(content, width=400, padding=(0, 0, 8, 0))
    left_frame.grid(row=0, column=0, sticky="nsew")
    left_frame.grid_columnconfigure(0, weight=1)
    left_frame.grid_rowconfigure(1, weight=1)

    right_frame = ttk.Frame(content)
    right_frame.grid(row=0, column=1, sticky="nsew")
    right_frame.grid_columnconfigure(0, weight=1)
    right_frame.grid_rowconfigure(1, weight=1)

    ttk.Label(left_frame, text="Distribution Structure", font=("Segoe UI", 11, "bold")).grid(
        row=0, column=0, sticky="w", padx=8, pady=(0, 6)
    )

    structure_wrap = ttk.Frame(left_frame)
    structure_wrap.grid(row=1, column=0, sticky="nsew", padx=8)
    structure_wrap.grid_columnconfigure(0, weight=1)
    structure_wrap.grid_rowconfigure(0, weight=1)

    structure_tree = ttk.Treeview(
        structure_wrap,
        columns=("pct", "group"),
        show="tree headings",
        height=18,
    )
    structure_tree.heading("#0", text="Name")
    structure_tree.heading("pct", text="%")
    structure_tree.heading("group", text="Group")
    structure_tree.column("#0", width=240, anchor="w", stretch=False)
    structure_tree.column("pct", width=70, anchor="center", stretch=False)
    structure_tree.column("group", width=140, anchor="w", stretch=False)
    structure_tree.tag_configure("group_header", foreground="#1f4e79", font=("Segoe UI", 9, "bold"))
    structure_tree.tag_configure("item", foreground="#111827")
    structure_tree.tag_configure("subitem", foreground="#2563eb")
    structure_tree.grid(row=0, column=0, sticky="nsew")

    structure_scroll = ttk.Scrollbar(
        structure_wrap,
        orient="vertical",
        command=structure_tree.yview,
    )
    structure_scroll.grid(row=0, column=1, sticky="ns")
    structure_tree.configure(yscrollcommand=structure_scroll.set)

    validation_label = ttk.Label(left_frame, text="", justify=tk.LEFT, wraplength=320)
    validation_label.grid(row=2, column=0, sticky="w", padx=8, pady=(6, 2))

    buttons = ttk.Frame(left_frame)
    buttons.grid(row=3, column=0, sticky="w", padx=8, pady=(4, 0))

    title_row = ttk.Frame(right_frame)
    title_row.grid(row=0, column=0, sticky="ew", padx=8, pady=(0, 6))
    title_row.grid_columnconfigure(0, weight=1)
    ttk.Label(title_row, text="Distribution Table", font=("Segoe UI", 11, "bold")).grid(
        row=0, column=0, sticky="w"
    )

    toolbar = ttk.Frame(title_row)
    toolbar.grid(row=0, column=1, sticky="e")
    period_from_var = tk.StringVar(value=_default_start())
    period_to_var = tk.StringVar(value=_default_end())

    ttk.Label(toolbar, text="From:").pack(side=tk.LEFT)
    ttk.Entry(toolbar, textvariable=period_from_var, width=9).pack(side=tk.LEFT, padx=(4, 8))
    ttk.Label(toolbar, text="To:").pack(side=tk.LEFT)
    ttk.Entry(toolbar, textvariable=period_to_var, width=9).pack(side=tk.LEFT, padx=(4, 8))

    results_wrap = ttk.Frame(right_frame)
    results_wrap.grid(row=1, column=0, sticky="nsew", padx=8)
    results_wrap.grid_columnconfigure(0, weight=1)
    results_wrap.grid_rowconfigure(0, weight=1)

    results_tree = ttk.Treeview(
        results_wrap,
        columns=("month", "fixed", "net_income"),
        show="headings",
    )
    results_tree.grid(row=0, column=0, sticky="nsew")
    results_scroll_y = ttk.Scrollbar(results_wrap, orient="vertical", command=results_tree.yview)
    results_scroll_y.grid(row=0, column=1, sticky="ns")
    results_scroll_x = ttk.Scrollbar(
        results_wrap,
        orient="horizontal",
        command=results_tree.xview,
    )
    results_scroll_x.grid(row=1, column=0, sticky="ew")
    results_tree.configure(
        yscrollcommand=results_scroll_y.set,
        xscrollcommand=results_scroll_x.set,
    )
    results_tree.tag_configure("neg_row", background="#fee2e2")
    results_tree.tag_configure("odd_row", background="#f8fafc")
    results_tree.tag_configure("even_row", background="#ffffff")

    footer_row = ttk.Frame(right_frame)
    footer_row.grid(row=2, column=0, sticky="ew", padx=8, pady=(6, 0))
    footer_row.grid_columnconfigure(1, weight=1)
    fix_button = ttk.Button(footer_row, text="Fix Row")
    fix_button.grid(row=0, column=0, sticky="w")
    status_label = ttk.Label(footer_row, text="")
    status_label.grid(row=0, column=1, sticky="w", padx=(12, 0))
    Tooltip(
        status_label,
        (
            "Shows the visible month range and how many rows are currently fixed.\n"
            "Closed past months are auto-fixed when snapshots are queried.\n"
            "Auto-fixed rows are protected and cannot be unfixed manually."
        ),
    )

    def _block_separator_resize(event: tk.Event) -> str | None:
        if isinstance(event.widget, ttk.Treeview):
            region = event.widget.identify_region(event.x, event.y)
            if region == "separator":
                return "break"
        return None

    def _bind_fixed_width_columns(tree: ttk.Treeview) -> None:
        tree.bind("<Button-1>", _block_separator_resize, add="+")

    def _accelerated_units(delta: int, *, multiplier: int = 10) -> int:
        if delta == 0:
            return 0
        base_units = max(1, abs(int(delta)) // 120)
        return base_units * multiplier

    def _scroll_results_horizontally(direction: int, units: int) -> str:
        results_tree.xview_scroll(direction * units, "units")
        return "break"

    def _on_results_shift_mousewheel(event: tk.Event) -> str:
        delta = int(getattr(event, "delta", 0))
        units = _accelerated_units(delta)
        if units <= 0:
            return "break"
        direction = -1 if delta > 0 else 1
        return _scroll_results_horizontally(direction, units)

    def _on_results_shift_button4(_event: tk.Event) -> str:
        return _scroll_results_horizontally(-1, 3)

    def _on_results_shift_button5(_event: tk.Event) -> str:
        return _scroll_results_horizontally(1, 3)

    for widget in (results_tree, results_scroll_x):
        widget.bind("<Shift-MouseWheel>", _on_results_shift_mousewheel, add="+")
        widget.bind("<Shift-Button-4>", _on_results_shift_button4, add="+")
        widget.bind("<Shift-Button-5>", _on_results_shift_button5, add="+")

    _bind_fixed_width_columns(structure_tree)
    _bind_fixed_width_columns(results_tree)

    def _build_live_column_meta(items: list[DistributionItem]) -> tuple[list[str], dict[str, str]]:
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
            for subitem in context.controller.get_distribution_subitems(item.id):
                sub_key = f"sub_{subitem.id}"
                column_ids.append(sub_key)
                headings[sub_key] = f"  {subitem.name}"
        return column_ids, headings

    def _compose_column_meta(
        items: list[DistributionItem],
        visible_fixed_rows: list[FrozenDistributionRow],
    ) -> tuple[list[str], dict[str, str]]:
        column_ids, headings = _build_live_column_meta(items)
        for frozen_row in visible_fixed_rows:
            for column_id in frozen_row.column_order:
                if column_id not in headings:
                    column_ids.append(column_id)
                    headings[column_id] = frozen_row.headings_by_column.get(column_id, column_id)
        return column_ids, headings

    def _selected_item_id() -> int | None:
        selection = structure_tree.selection()
        if not selection:
            return None
        iid = selection[0]
        if iid.startswith("item_"):
            return int(iid.split("_", 1)[1])
        if iid.startswith("sub_"):
            parent_iid = structure_tree.parent(iid)
            if parent_iid.startswith("item_"):
                return int(parent_iid.split("_", 1)[1])
        return None

    def _refresh_validation() -> None:
        errors = context.controller.validate_distribution()
        if not errors:
            validation_label.config(
                text="Structure is valid: top-level items and subitems sum to 100.00%",
                foreground="#166534",
            )
            return
        validation_label.config(
            text="\n".join(f"- {error.message}" for error in errors),
            foreground="#991b1b",
        )

    def _refresh_structure() -> None:
        structure_tree.delete(*structure_tree.get_children())
        try:
            items = context.controller.get_distribution_items()
        except Exception as exc:
            logger.warning("Failed to refresh distribution structure: %s", exc)
            validation_label.config(text=str(exc), foreground="#991b1b")
            return

        grouped: dict[str, list[DistributionItem]] = defaultdict(list)
        for item in items:
            grouped[item.group_name or "Ungrouped"].append(item)

        for group_name in sorted(grouped, key=str.casefold):
            group_items = grouped[group_name]
            parent_iid = ""
            if len(group_items) > 1 or group_name != "Ungrouped":
                parent_iid = structure_tree.insert(
                    "",
                    "end",
                    text=group_name,
                    values=("", ""),
                    tags=("group_header",),
                    open=True,
                )
            for item in group_items:
                item_node = structure_tree.insert(
                    parent_iid,
                    "end",
                    iid=f"item_{item.id}",
                    text=item.name,
                    values=(f"{item.pct:.2f}%", item.group_name or ""),
                    tags=("item",),
                    open=True,
                )
                for subitem in context.controller.get_distribution_subitems(item.id):
                    structure_tree.insert(
                        item_node,
                        "end",
                        iid=f"sub_{subitem.id}",
                        text=subitem.name,
                        values=(f"{subitem.pct:.2f}%", ""),
                        tags=("subitem",),
                    )

        _refresh_validation()

    def _configure_results_columns(column_ids: list[str], headings: dict[str, str]) -> None:
        results_tree.configure(columns=column_ids, displaycolumns=column_ids)
        for column_id in column_ids:
            is_month = column_id == "month"
            is_sub = column_id.startswith("sub_")
            is_fixed = column_id == "fixed"
            width = 92 if is_sub else (60 if is_month else (50 if is_fixed else 90))
            anchor = "center" if is_fixed else ("w" if is_month else "e")
            results_tree.heading(column_id, text=headings[column_id])
            results_tree.column(column_id, width=width, anchor=anchor, stretch=False)

    def _distribution_row_values_map(
        distribution: MonthlyDistribution,
        items: list[DistributionItem],
    ) -> dict[str, str]:
        item_results = {result.item.id: result for result in distribution.item_results}
        values = {
            "month": distribution.month,
            "fixed": "",
            "net_income": _fmt_amount(distribution.net_income_kzt),
        }
        for item in items:
            result = item_results.get(item.id)
            item_key = f"item_{item.id}"
            if result is None:
                values[item_key] = "-"
                continue
            values[item_key] = _fmt_amount(result.amount_kzt)
            sub_results = {sub.subitem.id: sub for sub in result.subitem_results}
            for subitem in context.controller.get_distribution_subitems(item.id):
                sub_key = f"sub_{subitem.id}"
                sub_result = sub_results.get(subitem.id)
                values[sub_key] = "-" if sub_result is None else _fmt_amount(sub_result.amount_kzt)
        return values

    def _row_values_for_columns(
        column_ids: list[str], values_by_column: dict[str, str]
    ) -> list[str]:
        return [values_by_column.get(column_id, "-") for column_id in column_ids]

    def _refresh_results() -> None:
        start_month = (period_from_var.get() or "").strip() or _default_start()
        end_month = (period_to_var.get() or "").strip() or _default_end()

        try:
            items = context.controller.get_distribution_items()
            history = context.controller.get_distribution_history(start_month, end_month)
            visible_fixed_rows = context.controller.get_frozen_distribution_rows(
                start_month,
                end_month,
            )
        except Exception as exc:
            logger.warning("Failed to refresh distribution results: %s", exc)
            status_label.config(text=str(exc), foreground="#991b1b")
            results_tree.delete(*results_tree.get_children())
            return

        live_history_by_month = {distribution.month: distribution for distribution in history}
        visible_fixed_rows_by_month = {row.month: row for row in visible_fixed_rows}
        visible_months = sorted(set(live_history_by_month) | set(visible_fixed_rows_by_month))

        if not items and not visible_fixed_rows:
            results_tree.delete(*results_tree.get_children())
            results_tree.configure(
                columns=("month", "fixed", "net_income"),
                displaycolumns=("month", "fixed", "net_income"),
            )
            results_tree.heading("month", text="Month")
            results_tree.heading("fixed", text="Fixed")
            results_tree.heading("net_income", text="Net income")
            results_tree.column("month", width=60, anchor="w", stretch=False)
            results_tree.column("fixed", width=50, anchor="center", stretch=False)
            results_tree.column("net_income", width=90, anchor="e", stretch=False)
            status_label.config(
                text="No distribution items yet. Add structure on the left to populate the table.",
                foreground="",
            )
            fix_button.configure(state=tk.DISABLED, text="Fix Row")
            return

        column_ids, headings = _compose_column_meta(items, visible_fixed_rows)
        _configure_results_columns(column_ids, headings)
        results_tree.delete(*results_tree.get_children())
        for index, month in enumerate(visible_months):
            frozen_row = visible_fixed_rows_by_month.get(month)
            live_distribution = live_history_by_month.get(month)
            if frozen_row is not None:
                is_negative = frozen_row.is_negative
                values_by_column = dict(frozen_row.values_by_column)
            elif live_distribution is not None:
                is_negative = live_distribution.is_negative
                values_by_column = _distribution_row_values_map(live_distribution, items)
            else:
                continue

            values_by_column["month"] = month
            values_by_column["fixed"] = "✓" if frozen_row is not None else ""
            tag = "neg_row" if is_negative else ("odd_row" if index % 2 == 0 else "even_row")
            results_tree.insert(
                "",
                "end",
                iid=month,
                values=_row_values_for_columns(column_ids, values_by_column),
                tags=(tag,),
            )

        fixed_count = sum(1 for row in visible_fixed_rows if row.month in visible_months)
        status_text = f"Showing {len(visible_months)} month(s) from {start_month} to {end_month}"
        if fixed_count:
            status_text += f" | fixed: {fixed_count}"
        status_label.config(text=f"{status_text} ⓘ", foreground="")
        _update_fix_button_state()

    def _selected_result_month() -> str | None:
        selection = results_tree.selection()
        if not selection:
            return None
        return selection[0]

    def _update_fix_button_state(_event: tk.Event | None = None) -> None:
        month = _selected_result_month()
        if month is None:
            fix_button.configure(text="Fix Row", state=tk.DISABLED)
            return
        if context.controller.is_distribution_month_auto_fixed(month):
            fix_button.configure(text="Auto Fixed", state=tk.DISABLED)
            return
        button_text = (
            "Unfix Row" if context.controller.is_distribution_month_fixed(month) else "Fix Row"
        )
        fix_button.configure(text=button_text, state=tk.NORMAL)

    def _toggle_fixed_row() -> None:
        month = _selected_result_month()
        if month is None:
            messagebox.showerror("Selection Required", "Select a month row in the table first.")
            return
        try:
            context.controller.toggle_distribution_month_fixed(month)
        except ValueError as exc:
            messagebox.showinfo("Distribution", str(exc), parent=parent)
            _update_fix_button_state()
            return
        _refresh_results()
        if results_tree.exists(month):
            results_tree.selection_set(month)
            results_tree.focus(month)
        _update_fix_button_state()

    def _refresh_all() -> None:
        _refresh_structure()
        _refresh_results()

    def _ask_pct(title: str, prompt: str, *, initialvalue: str = "0.00") -> float | None:
        raw_value = simpledialog.askstring(title, prompt, parent=parent, initialvalue=initialvalue)
        if raw_value is None:
            return None
        normalized = raw_value.replace(" ", "").replace(",", ".")
        try:
            return float(normalized)
        except ValueError:
            messagebox.showerror("Invalid Percentage", "Percentage must be a number.")
            return None

    def _add_item() -> None:
        name = simpledialog.askstring("New Item", "Item name:", parent=parent)
        if not name:
            return
        group_name = simpledialog.askstring("Group", "Optional group name:", parent=parent)
        pct = _ask_pct("Percentage", "Percent of total monthly cashflow:")
        if pct is None:
            return
        try:
            context.controller.create_distribution_item(
                name,
                group_name=group_name or "",
                pct=pct,
            )
        except ValueError as exc:
            messagebox.showerror("Distribution Error", str(exc))
            return
        _refresh_all()

    def _add_subitem() -> None:
        item_id = _selected_item_id()
        if item_id is None:
            messagebox.showerror("Selection Required", "Select a top-level item first.")
            return
        name = simpledialog.askstring("New Subitem", "Subitem name:", parent=parent)
        if not name:
            return
        pct = _ask_pct("Percentage", "Percent of the parent item:")
        if pct is None:
            return
        try:
            context.controller.create_distribution_subitem(item_id, name, pct=pct)
        except ValueError as exc:
            messagebox.showerror("Distribution Error", str(exc))
            return
        _refresh_all()

    def _edit_pct() -> None:
        selection = structure_tree.selection()
        if not selection:
            messagebox.showerror("Selection Required", "Select an item or subitem first.")
            return
        iid = selection[0]
        if not (iid.startswith("item_") or iid.startswith("sub_")):
            messagebox.showerror(
                "Selection Required", "Select an item or subitem, not a group header."
            )
            return
        current_value = str(structure_tree.item(iid, "values")[0]).rstrip("%").strip() or "0.00"
        pct = _ask_pct("Edit Percentage", "New percentage:", initialvalue=current_value)
        if pct is None:
            return
        try:
            if iid.startswith("item_"):
                context.controller.update_distribution_item_pct(int(iid.split("_", 1)[1]), pct)
            else:
                context.controller.update_distribution_subitem_pct(int(iid.split("_", 1)[1]), pct)
        except ValueError as exc:
            messagebox.showerror("Distribution Error", str(exc))
            return
        _refresh_all()

    def _rename() -> None:
        selection = structure_tree.selection()
        if not selection:
            messagebox.showerror("Selection Required", "Select an item or subitem first.")
            return
        iid = selection[0]
        if not (iid.startswith("item_") or iid.startswith("sub_")):
            messagebox.showerror(
                "Selection Required", "Select an item or subitem, not a group header."
            )
            return
        current_name = structure_tree.item(iid, "text").strip()
        new_name = simpledialog.askstring(
            "Rename",
            "New name:",
            parent=parent,
            initialvalue=current_name,
        )
        if not new_name:
            return
        try:
            if iid.startswith("item_"):
                context.controller.update_distribution_item_name(
                    int(iid.split("_", 1)[1]), new_name
                )
            else:
                context.controller.update_distribution_subitem_name(
                    int(iid.split("_", 1)[1]),
                    new_name,
                )
        except ValueError as exc:
            messagebox.showerror("Distribution Error", str(exc))
            return
        _refresh_all()

    def _delete_selected() -> None:
        selection = structure_tree.selection()
        if not selection:
            messagebox.showerror("Selection Required", "Select an item or subitem to delete.")
            return
        iid = selection[0]
        if not (iid.startswith("item_") or iid.startswith("sub_")):
            messagebox.showerror("Selection Required", "Group headers cannot be deleted directly.")
            return
        name = structure_tree.item(iid, "text").strip()
        message = f"Delete '{name}'?"
        if iid.startswith("item_"):
            message += "\nAll child subitems will be deleted as well."
        if not messagebox.askyesno("Confirm Delete", message, parent=parent):
            return
        try:
            if iid.startswith("item_"):
                context.controller.delete_distribution_item(int(iid.split("_", 1)[1]))
            else:
                context.controller.delete_distribution_subitem(int(iid.split("_", 1)[1]))
        except ValueError as exc:
            messagebox.showerror("Distribution Error", str(exc))
            return
        _refresh_all()

    ttk.Button(buttons, text="+ Item", command=_add_item).pack(side=tk.LEFT, padx=(0, 4))
    ttk.Button(buttons, text="+ Subitem", command=_add_subitem).pack(side=tk.LEFT, padx=4)
    ttk.Button(buttons, text="Edit %", command=_edit_pct).pack(side=tk.LEFT, padx=4)
    ttk.Button(buttons, text="Rename", command=_rename).pack(side=tk.LEFT, padx=4)
    ttk.Button(buttons, text="Delete", command=_delete_selected).pack(side=tk.LEFT, padx=4)
    ttk.Button(toolbar, text="Refresh", command=_refresh_all).pack(side=tk.LEFT, padx=(4, 0))
    fix_button.configure(command=_toggle_fixed_row, state=tk.DISABLED)
    results_tree.bind("<<TreeviewSelect>>", _update_fix_button_state, add="+")

    parent.after(100, _refresh_all)
    return DistributionTabBindings(
        structure_tree=structure_tree,
        validation_label=validation_label,
        period_from_var=period_from_var,
        period_to_var=period_to_var,
        results_tree=results_tree,
        status_label=status_label,
        refresh=_refresh_all,
    )


def _fmt_amount(value: float) -> str:
    if abs(value) < 0.005:
        return "-"
    return f"{value:,.0f}"


def _default_start() -> str:
    today = dt_date.today()
    return f"{today.year:04d}-01"


def _default_end() -> str:
    today = dt_date.today()
    return f"{today.year:04d}-{today.month:02d}"
