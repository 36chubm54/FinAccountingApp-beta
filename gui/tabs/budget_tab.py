"""Budget tab - budget planning and spend tracking."""

from __future__ import annotations

import logging
import tkinter as tk
from collections.abc import Callable
from dataclasses import dataclass
from tkinter import messagebox, simpledialog, ttk
from typing import Any, Protocol

from domain.budget import Budget, BudgetResult, BudgetStatus, PaceStatus
from gui.tooltip import Tooltip

logger = logging.getLogger(__name__)

_PACE_FILL = {
    PaceStatus.ON_TRACK: "#10b981",
    PaceStatus.OVERPACE: "#f59e0b",
    PaceStatus.OVERSPENT: "#ef4444",
}
_TRACK_BG = "#e5e7eb"
_TIME_COLOR = "#3b82f6"


class BudgetTabContext(Protocol):
    controller: Any

    def _refresh_charts(self) -> None: ...


@dataclass(slots=True)
class BudgetTabBindings:
    category_combo: ttk.Combobox
    start_date_entry: ttk.Entry
    end_date_entry: ttk.Entry
    limit_entry: ttk.Entry
    include_mandatory_var: tk.BooleanVar
    budget_tree: ttk.Treeview
    progress_canvas: tk.Canvas
    status_label: ttk.Label
    refresh: Callable[[], None]


def _draw_progress_bars(canvas: tk.Canvas, results: list[BudgetResult]) -> None:
    canvas.delete("all")
    if not results:
        return

    width = max(canvas.winfo_width(), 400)
    bar_h = 12
    gap = 7
    pad_l = 115
    pad_r = 48
    bar_w = max(40, width - pad_l - pad_r)

    total_h = len(results) * (bar_h + gap) + gap
    canvas.configure(height=max(40, total_h))

    for index, result in enumerate(results):
        y = gap + index * (bar_h + gap)
        canvas.create_text(
            pad_l - 6,
            y + bar_h // 2,
            text=result.budget.category[:15],
            anchor="e",
            fill="#374151",
            font=("Segoe UI", 9),
        )
        canvas.create_rectangle(
            pad_l,
            y,
            pad_l + bar_w,
            y + bar_h,
            fill=_TRACK_BG,
            outline="",
        )

        fill_w = min(bar_w, max(0, int(bar_w * result.usage_pct / 100.0)))
        if fill_w > 0:
            fill_color = (
                "#9ca3af"
                if result.status != BudgetStatus.ACTIVE
                else _PACE_FILL.get(result.pace_status, "#10b981")
            )
            canvas.create_rectangle(
                pad_l,
                y,
                pad_l + fill_w,
                y + bar_h,
                fill=fill_color,
                outline="",
            )

        if result.status == BudgetStatus.ACTIVE:
            tx = pad_l + max(0, min(bar_w, int(bar_w * result.time_pct / 100.0)))
            canvas.create_line(tx, y - 1, tx, y + bar_h + 1, fill=_TIME_COLOR, width=2)

        canvas.create_text(
            pad_l + bar_w + 6,
            y + bar_h // 2,
            text=f"{result.usage_pct:.0f}%",
            anchor="w",
            fill="#374151",
            font=("Segoe UI", 9),
        )


def build_budget_tab(
    parent: tk.Frame | ttk.Frame,
    *,
    context: BudgetTabContext,
) -> BudgetTabBindings:
    parent.grid_columnconfigure(0, weight=1)
    parent.grid_rowconfigure(1, weight=1)

    form_frame = ttk.LabelFrame(parent, text="New Budget")
    form_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=8)
    for col in (1, 3, 5):
        form_frame.grid_columnconfigure(col, weight=1)

    ttk.Label(form_frame, text="Category:").grid(row=0, column=0, sticky="w", padx=6, pady=4)
    category_combo = ttk.Combobox(form_frame, state="normal", width=20)
    category_combo.grid(row=0, column=1, sticky="ew", padx=6, pady=4)

    ttk.Label(form_frame, text="From (YYYY-MM-DD):").grid(
        row=0, column=2, sticky="w", padx=6, pady=4
    )
    start_date_entry = ttk.Entry(form_frame, width=12)
    start_date_entry.grid(row=0, column=3, sticky="ew", padx=6, pady=4)

    ttk.Label(form_frame, text="To (YYYY-MM-DD):").grid(row=0, column=4, sticky="w", padx=6, pady=4)
    end_date_entry = ttk.Entry(form_frame, width=12)
    end_date_entry.grid(row=0, column=5, sticky="ew", padx=6, pady=4)

    ttk.Label(form_frame, text="Limit (KZT):").grid(row=1, column=0, sticky="w", padx=6, pady=4)
    limit_entry = ttk.Entry(form_frame, width=16)
    limit_entry.grid(row=1, column=1, sticky="ew", padx=6, pady=4)

    include_mandatory_var = tk.BooleanVar(value=False)
    include_mandatory_check = ttk.Checkbutton(
        form_frame,
        text="Include mandatory expenses",
        variable=include_mandatory_var,
    )
    include_mandatory_check.grid(row=1, column=2, columnspan=2, sticky="w", padx=6, pady=4)
    Tooltip(
        include_mandatory_check,
        "Counts records with type 'mandatory_expense' only when they were added to Records,\n"
        "their category matches the budget category, "
        "and their date falls inside the budget period.",
    )

    list_frame = ttk.Frame(parent)
    list_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 8))
    list_frame.grid_columnconfigure(0, weight=1)
    list_frame.grid_rowconfigure(0, weight=1)

    columns = (
        "category",
        "period",
        "include",
        "limit",
        "spent",
        "remaining",
        "usage",
        "pace",
        "status",
    )
    budget_tree = ttk.Treeview(list_frame, columns=columns, show="headings", height=10)

    budget_tree.heading("category", text="Category")
    budget_tree.heading("period", text="Period")
    budget_tree.heading("include", text="Include mandatory")
    budget_tree.heading("limit", text="Limit KZT")
    budget_tree.heading("spent", text="Spent KZT")
    budget_tree.heading("remaining", text="Remaining")
    budget_tree.heading("usage", text="Usage %")
    budget_tree.heading("pace", text="Pace")
    budget_tree.heading("status", text="Status")
    budget_tree.column("category", width=110, anchor="w")
    budget_tree.column("period", width=185, anchor="w")
    budget_tree.column("include", width=120, anchor="center", stretch=False)
    budget_tree.column("limit", width=100, anchor="e")
    budget_tree.column("spent", width=100, anchor="e")
    budget_tree.column("remaining", width=100, anchor="e")
    budget_tree.column("usage", width=65, anchor="center")
    budget_tree.column("pace", width=85, anchor="center")
    budget_tree.column("status", width=70, anchor="center")

    budget_tree.tag_configure("overspent", foreground="#ef4444")
    budget_tree.tag_configure("overpace", foreground="#f59e0b")
    budget_tree.tag_configure("on_track", foreground="#10b981")
    budget_tree.tag_configure("future", foreground="#6b7280")
    budget_tree.tag_configure("expired", foreground="#9ca3af")

    budget_tree.grid(row=0, column=0, sticky="nsew")
    scroll = ttk.Scrollbar(list_frame, orient="vertical", command=budget_tree.yview)
    scroll.grid(row=0, column=1, sticky="ns")
    budget_tree.configure(yscrollcommand=scroll.set)

    progress_canvas = tk.Canvas(list_frame, height=40, bg="white", highlightthickness=0)
    progress_canvas.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(2, 0))

    btn_frame = ttk.Frame(list_frame)
    btn_frame.grid(row=2, column=0, columnspan=2, sticky="w", pady=4)
    status_label = ttk.Label(list_frame, text="")
    status_label.grid(row=3, column=0, columnspan=2, sticky="w", padx=4)

    def _clear_form() -> None:
        category_combo.set("")
        start_date_entry.delete(0, tk.END)
        end_date_entry.delete(0, tk.END)
        limit_entry.delete(0, tk.END)
        include_mandatory_var.set(False)

    def _row_tag(result: BudgetResult) -> str:
        if result.status == BudgetStatus.FUTURE:
            return "future"
        if result.status == BudgetStatus.EXPIRED:
            return "expired"
        return result.pace_status.value

    def _refresh() -> None:
        try:
            categories = set(context.controller.get_expense_categories())
            categories.update(context.controller.get_mandatory_expense_categories())
            category_combo["values"] = sorted(categories, key=lambda value: value.casefold())
        except Exception:
            logger.debug("Failed to refresh budget category suggestions", exc_info=True)

        try:
            results = context.controller.get_budget_results()
        except Exception as err:
            logger.warning("Budget refresh error: %s", err)
            return

        budget_tree.delete(*budget_tree.get_children())
        for result in results:
            budget = result.budget
            budget_tree.insert(
                "",
                "end",
                iid=str(budget.id),
                values=(
                    budget.category,
                    f"{budget.start_date}  ->  {budget.end_date}",
                    "Yes" if budget.include_mandatory else "No",
                    f"{budget.limit_kzt:,.0f}",
                    f"{result.spent_kzt:,.0f}",
                    f"{result.remaining_kzt:,.0f}",
                    f"{result.usage_pct:.1f}%",
                    result.pace_status.value,
                    result.status.value,
                ),
                tags=(_row_tag(result),),
            )

        progress_canvas.after(50, lambda: _draw_progress_bars(progress_canvas, results))
        active_count = sum(1 for item in results if item.status == BudgetStatus.ACTIVE)
        status_label.config(text=f"{active_count} active  /  {len(results)} total")

    def _find_selected_budget() -> Budget | None:
        selection = budget_tree.selection()
        if not selection:
            return None
        try:
            budget_id = int(selection[0])
        except (TypeError, ValueError):
            return None
        budgets = context.controller.get_budgets()
        return next((budget for budget in budgets if int(budget.id) == budget_id), None)

    def _add_budget() -> None:
        category = category_combo.get().strip()
        start_date = start_date_entry.get().strip()
        end_date = end_date_entry.get().strip()
        raw_limit = limit_entry.get().strip()

        if not category:
            messagebox.showerror("Error", "Category is required.")
            return
        if not start_date or not end_date:
            messagebox.showerror("Error", "Both From and To dates are required (YYYY-MM-DD).")
            return
        try:
            limit_kzt = float(raw_limit.replace(" ", "").replace(",", "."))
            if limit_kzt <= 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Error", "Limit must be a positive number.")
            return

        try:
            context.controller.create_budget(
                category=category,
                start_date=start_date,
                end_date=end_date,
                limit_kzt=limit_kzt,
                include_mandatory=include_mandatory_var.get(),
            )
        except ValueError as error:
            messagebox.showerror("Budget Error", str(error))
            return

        _clear_form()
        _refresh()

    def _delete_budget() -> None:
        target = _find_selected_budget()
        if target is None:
            messagebox.showerror("Error", "Select a budget to delete.")
            return
        if not messagebox.askyesno(
            "Confirm Delete",
            f"Delete budget '{target.category}'\n{target.start_date} -> {target.end_date}?",
        ):
            return
        try:
            context.controller.delete_budget(target.id)
        except ValueError as error:
            messagebox.showerror("Error", str(error))
            return
        _refresh()

    def _edit_limit() -> None:
        target = _find_selected_budget()
        if target is None:
            messagebox.showerror("Error", "Select a budget to edit.")
            return
        new_limit_str = simpledialog.askstring(
            "Edit Limit",
            f"New limit (KZT) for '{target.category}':",
            initialvalue=f"{target.limit_kzt:,.0f}",
            parent=parent,
        )
        if not new_limit_str:
            return
        normalized = new_limit_str.replace(" ", "")
        if "," in normalized and "." not in normalized:
            normalized = normalized.replace(",", ".")
        else:
            normalized = normalized.replace(",", "")
        try:
            context.controller.update_budget_limit(target.id, float(normalized))
        except (ValueError, TypeError) as error:
            messagebox.showerror("Error", f"Invalid limit: {error}")
            return
        _refresh()

    ttk.Button(form_frame, text="Add", command=_add_budget).grid(row=1, column=4, padx=6, pady=4)
    ttk.Button(form_frame, text="Clear", command=_clear_form).grid(row=1, column=5, padx=6, pady=4)
    ttk.Button(btn_frame, text="Edit Limit", command=_edit_limit).pack(side=tk.LEFT, padx=4)
    ttk.Button(btn_frame, text="Delete", command=_delete_budget).pack(side=tk.LEFT, padx=4)
    ttk.Button(btn_frame, text="Refresh", command=_refresh).pack(side=tk.LEFT, padx=4)

    parent.after(100, _refresh)
    return BudgetTabBindings(
        category_combo=category_combo,
        start_date_entry=start_date_entry,
        end_date_entry=end_date_entry,
        limit_entry=limit_entry,
        include_mandatory_var=include_mandatory_var,
        budget_tree=budget_tree,
        progress_canvas=progress_canvas,
        status_label=status_label,
        refresh=_refresh,
    )
