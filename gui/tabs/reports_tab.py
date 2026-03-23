"""Reports tab — Summaries, Transaction Statements and Grouped Reports"""

from __future__ import annotations

import os
import tkinter as tk
from tkinter import VERTICAL, filedialog, messagebox, ttk
from typing import Any, Protocol

from gui.helpers import open_in_file_manager
from gui.record_colors import KIND_TO_FOREGROUND, foreground_for_kind
from gui.tabs.reports_controller import ReportsController
from gui.tooltip import Tooltip
from services.report_service import ReportFilters, build_category_group_rows
from utils.csv_utils import report_to_csv


class ReportsTabContext(Protocol):
    controller: Any
    currency: Any


def build_reports_tab(parent: tk.Frame | ttk.Frame, context: ReportsTabContext) -> None:
    ReportsFrame(parent, context).grid(row=0, column=0, sticky="nsew")
    parent.grid_rowconfigure(0, weight=1)
    parent.grid_columnconfigure(0, weight=1)


class ReportsFrame(ttk.Frame):
    def __init__(self, parent: tk.Misc, context: ReportsTabContext) -> None:
        super().__init__(parent, padding=10)
        self._context = context
        self._controller = ReportsController(context.controller, context.currency)
        self._last_result = None
        self._group_drill_category: str | None = None
        self._group_iid_to_category: dict[str, str] = {}

        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self._build_controls()
        self._build_body()
        self.operations_tree.bind("<Double-1>", self._on_operations_double_click)
        self._refresh_wallets()
        self._apply_group_ui_state()

    def _build_controls(self) -> None:
        controls = ttk.Frame(self)
        controls.grid(row=0, column=0, sticky="ew")
        controls.grid_columnconfigure(1, weight=1)
        controls.grid_columnconfigure(3, weight=1)
        controls.grid_columnconfigure(6, weight=1)

        self.period_start_var = tk.StringVar()
        self.period_end_var = tk.StringVar()
        self.category_var = tk.StringVar()
        self.wallet_var = tk.StringVar(value="All wallets")
        self.group_var = tk.BooleanVar(value=True)
        self.totals_mode_var = tk.StringVar(value="fixed")

        ttk.Label(controls, text="Period:").grid(row=0, column=0, sticky="w")
        ttk.Entry(controls, textvariable=self.period_start_var, width=16).grid(
            row=0, column=1, sticky="ew", padx=(6, 12)
        )

        ttk.Label(controls, text="Period end:").grid(row=0, column=2, sticky="w")
        ttk.Entry(controls, textvariable=self.period_end_var, width=16).grid(
            row=0, column=3, sticky="ew", padx=(6, 12)
        )

        ttk.Label(controls, text="Category:").grid(row=0, column=4, sticky="w")
        self.category_combo = ttk.Combobox(
            controls, textvariable=self.category_var, values=[], width=18
        )
        self.category_combo.grid(row=0, column=5, sticky="ew", padx=(6, 12))

        ttk.Label(controls, text="Wallet:").grid(row=0, column=6, sticky="w")
        self.wallet_menu = ttk.OptionMenu(controls, self.wallet_var, self.wallet_var.get())
        self.wallet_menu.grid(row=0, column=7, sticky="ew", padx=(6, 0))

        ttk.Checkbutton(
            controls,
            text="Group by category",
            variable=self.group_var,
            command=self._apply_group_ui_state,
        ).grid(row=1, column=0, columnspan=2, sticky="w", pady=(8, 0))

        self._group_status_var = tk.StringVar(value="")
        self.group_status_label = ttk.Label(controls, textvariable=self._group_status_var)
        self.group_status_label.grid(
            row=1, column=2, columnspan=2, sticky="w", padx=(12, 0), pady=(8, 0)
        )

        # Hint for grouped view
        self._group_status_tooltip = Tooltip(
            self.group_status_label,
            "Double clicking on a category opens its details. "
            "The 'Back' button returns to the summary.",
        )

        self.group_back_button = ttk.Button(controls, text="Back", command=self._on_group_back)
        self.group_back_button.grid(row=1, column=4, sticky="w", padx=(12, 0), pady=(6, 0))

        totals = ttk.Frame(controls)
        totals.grid(row=1, column=5, columnspan=3, sticky="e", pady=(6, 0))
        ttk.Label(totals, text="Totals mode:").grid(row=0, column=0, sticky="w", padx=(0, 8))
        ttk.Radiobutton(
            totals,
            text="On fixed rate",
            variable=self.totals_mode_var,
            value="fixed",
            command=self._refresh_summary_only,
        ).grid(row=0, column=1, sticky="w", padx=(0, 8))
        ttk.Radiobutton(
            totals,
            text="On current rate",
            variable=self.totals_mode_var,
            value="current",
            command=self._refresh_summary_only,
        ).grid(row=0, column=2, sticky="w")

        buttons = ttk.Frame(controls)
        buttons.grid(row=2, column=0, columnspan=8, sticky="w", pady=(10, 0))
        ttk.Button(buttons, text="Generate", command=self._on_generate).grid(
            row=0, column=0, padx=(0, 8)
        )

        self.export_button = ttk.Menubutton(buttons, text="Export")
        self.export_button.grid(row=0, column=1, padx=(0, 8))
        export_menu = tk.Menu(self.export_button, tearoff=False)
        export_menu.add_command(label="CSV", command=lambda: self._export("csv"))
        export_menu.add_command(label="XLSX", command=lambda: self._export("xlsx"))
        export_menu.add_command(label="PDF", command=lambda: self._export("pdf"))
        self.export_button["menu"] = export_menu

    def _build_body(self) -> None:
        body = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        body.grid(row=1, column=0, sticky="nsew", pady=(10, 0))

        left = ttk.Frame(body)
        left.grid_rowconfigure(1, weight=1)
        left.grid_columnconfigure(0, weight=1)
        body.add(left, weight=3)

        right = ttk.Frame(body)
        right.grid_rowconfigure(0, weight=1)
        right.grid_columnconfigure(0, weight=1)
        body.add(right, weight=2)

        # (B) Summary block
        self.summary_frame = ttk.Labelframe(left, text="Summary", padding=10)
        self.summary_frame.grid(row=0, column=0, sticky="ew")
        self.summary_frame.grid_columnconfigure(1, weight=1)
        self._summary_labels: dict[str, ttk.Label] = {}
        self._summary_values: dict[str, ttk.Label] = {}
        for row_index, (label_key, label_text) in enumerate(
            [
                ("net_worth_fixed", "Net Worth (fixed):"),
                ("net_worth_current", "Net Worth (current):"),
                ("initial_balance", "Initial balance:"),
                ("records_total", "Records Total:"),
                ("final_balance", "Final Balance:"),
                ("fx_difference", "FX Difference:"),
            ]
        ):
            label_widget = ttk.Label(self.summary_frame, text=label_text)
            label_widget.grid(row=row_index, column=0, sticky="w")
            value_label = ttk.Label(self.summary_frame, text="—")
            value_label.grid(row=row_index, column=1, sticky="e")
            self._summary_labels[label_key] = label_widget
            self._summary_values[label_key] = value_label

        # (C) Operations table
        self.operations_container = ttk.Labelframe(left, text="Operations", padding=6)
        self.operations_container.grid(row=1, column=0, sticky="nsew", pady=(10, 0))
        self.operations_container.grid_rowconfigure(0, weight=1)
        self.operations_container.grid_columnconfigure(0, weight=1)

        self.operations_tree = ttk.Treeview(
            self.operations_container,
            columns=("date", "type", "category", "amount"),
            show="headings",
            selectmode="browse",
        )
        self.operations_tree.heading("date", text="Date")
        self.operations_tree.heading("type", text="Type")
        self.operations_tree.heading("category", text="Category")
        self.operations_tree.heading("amount", text="Amount (KZT)")
        self.operations_tree.column("date", width=60, anchor="w")
        self.operations_tree.column("type", width=100, anchor="w")
        self.operations_tree.column("category", width=120, anchor="w")
        self.operations_tree.column("amount", width=70, anchor="e")
        self.operations_tree.grid(row=0, column=0, sticky="nsew")
        op_scroll = ttk.Scrollbar(
            self.operations_container, orient=VERTICAL, command=self.operations_tree.yview
        )
        op_scroll.grid(row=0, column=1, sticky="ns")
        self.operations_tree.config(yscrollcommand=op_scroll.set)
        for kind, color in KIND_TO_FOREGROUND.items():
            try:
                self.operations_tree.tag_configure(kind, foreground=color)
            except Exception:
                pass

        # (D) Monthly summary
        monthly_frame = ttk.Labelframe(right, text="Monthly summary", padding=6)
        monthly_frame.grid(row=0, column=0, sticky="nsew")
        monthly_frame.grid_rowconfigure(0, weight=1)
        monthly_frame.grid_columnconfigure(0, weight=1)

        self.monthly_tree = ttk.Treeview(
            monthly_frame,
            columns=("month", "income", "expense"),
            show="headings",
            selectmode="none",
        )
        self.monthly_tree.heading("month", text="Month")
        self.monthly_tree.heading("income", text="Income")
        self.monthly_tree.heading("expense", text="Expense")
        self.monthly_tree.column("month", width=90, anchor="w")
        self.monthly_tree.column("income", width=90, anchor="e")
        self.monthly_tree.column("expense", width=90, anchor="e")
        self.monthly_tree.grid(row=0, column=0, sticky="nsew")
        monthly_scroll = ttk.Scrollbar(
            monthly_frame, orient=VERTICAL, command=self.monthly_tree.yview
        )
        monthly_scroll.grid(row=0, column=1, sticky="ns")
        self.monthly_tree.config(yscrollcommand=monthly_scroll.set)

    def _refresh_wallets(self) -> None:
        selected = self.wallet_var.get()
        self._wallet_label_to_id: dict[str, int | None] = {"All wallets": None}
        for wallet in self._controller.load_active_wallets():
            self._wallet_label_to_id[f"[{wallet.id}] {wallet.name} ({wallet.currency})"] = wallet.id
        labels = list(self._wallet_label_to_id.keys())
        selected_label = selected if selected in self._wallet_label_to_id else "All wallets"
        menu = self.wallet_menu["menu"]
        menu.delete(0, "end")
        for label in labels:
            menu.add_command(label=label, command=tk._setit(self.wallet_var, label))
        self.wallet_var.set(selected_label)

    def _current_filters(self) -> ReportFilters:
        wallet_id = self._wallet_label_to_id.get(self.wallet_var.get(), None)
        return ReportFilters(
            wallet_id=wallet_id,
            period_start=self.period_start_var.get().strip(),
            period_end=self.period_end_var.get().strip(),
            category=self.category_var.get().strip(),
            totals_mode=self.totals_mode_var.get().strip() or "fixed",
        )

    def _on_generate(self) -> None:
        self._refresh_wallets()
        try:
            result = self._controller.generate(self._current_filters())
        except ValueError as error:
            messagebox.showerror("Error", str(error))
            return
        except Exception as error:
            messagebox.showerror("Error", f"Failed to generate report: {error}")
            return

        self._last_result = result
        self._group_drill_category = None
        self._refresh_summary_only()
        self._refresh_operations_table()
        self._refresh_monthly_table()
        self._refresh_category_sources()

    def _refresh_summary_only(self) -> None:
        result = self._last_result
        if result is None:
            return
        summary = result.summary
        wallet_specific = result.filters.wallet_id is not None
        self._summary_labels["net_worth_fixed"].config(
            text="Wallet Balance (fixed):" if wallet_specific else "Net Worth (fixed):"
        )
        self._summary_labels["net_worth_current"].config(
            text="Wallet Balance (current):" if wallet_specific else "Net Worth (current):"
        )
        self._summary_values["net_worth_fixed"].config(
            text=f"{_fmt_kzt(summary.net_worth_fixed)} KZT"
        )
        self._summary_values["net_worth_current"].config(
            text=f"{_fmt_kzt(summary.net_worth_current)} KZT"
        )
        self._summary_values["initial_balance"].config(
            text=f"{_fmt_kzt(summary.initial_balance)} KZT"
        )
        self._summary_values["records_total"].config(
            text=f"{_fmt_kzt(summary.records_total_fixed)} KZT"
        )
        if self.totals_mode_var.get() == "current":
            final_value = summary.final_balance_current
        else:
            final_value = summary.final_balance_fixed
        self._summary_values["final_balance"].config(text=f"{_fmt_kzt(final_value)} KZT")
        self._summary_values["fx_difference"].config(text=f"{_fmt_kzt(summary.fx_difference)} KZT")

    def _refresh_operations_table(self) -> None:
        for iid in self.operations_tree.get_children():
            self.operations_tree.delete(iid)
        result = self._last_result
        if result is None:
            return

        if not self.group_var.get():
            for row in result.operations:
                tags = (row.kind,) if foreground_for_kind(row.kind) else ()
                self.operations_tree.insert(
                    "",
                    "end",
                    values=(row.date, row.type_label, row.category, f"{row.amount_kzt:.2f}"),
                    tags=tags,
                )
            return

        self._group_iid_to_category = {}
        drill_category = (self._group_drill_category or "").strip()
        if drill_category:
            for row in result.operations:
                if row.category != drill_category:
                    continue
                tags = (row.kind,) if foreground_for_kind(row.kind) else ()
                self.operations_tree.insert(
                    "",
                    "end",
                    values=(row.date, row.type_label, row.category, f"{row.amount_kzt:.2f}"),
                    tags=tags,
                )
            return

        for index, row in enumerate(build_category_group_rows(result.operations), start=1):
            category = row.category
            iid = f"cat_{index}"
            self._group_iid_to_category[iid] = category if category != "<Empty>" else ""
            self.operations_tree.insert(
                "",
                "end",
                iid=iid,
                values=("", f"Ops: {row.operations_count}", category, f"{row.total_kzt:.2f}"),
            )

    def _refresh_monthly_table(self) -> None:
        for iid in self.monthly_tree.get_children():
            self.monthly_tree.delete(iid)
        result = self._last_result
        if result is None:
            return
        for row in result.monthly:
            self.monthly_tree.insert(
                "", "end", values=(row.month, f"{row.income:.2f}", f"{row.expense:.2f}")
            )

    def _refresh_category_sources(self) -> None:
        result = self._last_result
        if result is None:
            return
        values = [""] + result.categories
        self.category_combo["values"] = values

    def _apply_group_ui_state(self) -> None:
        enabled = bool(self.group_var.get())
        try:
            self.group_back_button.configure(state=("normal" if enabled else "disabled"))
        except Exception:
            pass
        if not enabled:
            self._group_drill_category = None
            self._group_status_var.set("")
        else:
            self._group_status_var.set(
                f"Category: {self._group_drill_category}"
                if self._group_drill_category
                else "Grouped view (double-click a category) ⓘ"
            )
        self._refresh_operations_table()

    def _on_group_back(self) -> None:
        if not self._group_drill_category:
            return
        self._group_drill_category = None
        self._apply_group_ui_state()

    def _on_operations_double_click(self, _event: tk.Event) -> None:
        if not self.group_var.get():
            return
        if self._group_drill_category:
            return
        selected = self.operations_tree.focus()
        if not selected:
            return
        category = self._group_iid_to_category.get(selected)
        if category is None:
            return
        self._group_drill_category = category
        self._apply_group_ui_state()

    def _apply_table_ui_state(self) -> None:
        self.operations_container.grid()

    def _export(self, fmt: str) -> None:
        result = self._last_result
        if result is None:
            messagebox.showerror("Error", "Please generate a report first.")
            return

        fmt = (fmt or "csv").strip().lower()
        if fmt not in ("csv", "xlsx", "pdf"):
            messagebox.showerror("Error", f"Unsupported export format: {fmt}")
            return

        drill_category = (self._group_drill_category or "").strip()
        export_category_only = bool(self.group_var.get()) and bool(drill_category)

        if fmt == "csv":
            filepath = filedialog.asksaveasfilename(
                defaultextension=".csv",
                filetypes=[("CSV", "*.csv")],
                title="Save CSV",
            )
        elif fmt == "xlsx":
            filepath = filedialog.asksaveasfilename(
                defaultextension=".xlsx",
                filetypes=[("Excel", "*.xlsx")],
                title="Save XLSX",
            )
        else:
            filepath = filedialog.asksaveasfilename(
                defaultextension=".pdf",
                filetypes=[("PDF", "*.pdf")],
                title="Save PDF",
            )
        if not filepath:
            return
        try:
            export_grouped_summary = bool(self.group_var.get()) and not drill_category
            if export_grouped_summary:
                from gui.exporters import export_grouped_report

                grouped_rows = [
                    (row.category, row.operations_count, row.total_kzt)
                    for row in build_category_group_rows(result.operations)
                ]
                export_grouped_report(
                    f"{result.report.statement_title} - Grouped by category",
                    grouped_rows,
                    filepath,
                    fmt,
                )
            else:
                report_to_export = (
                    result.report.filter_by_category(drill_category)
                    if export_category_only
                    else result.report
                )
                if fmt == "csv":
                    # Export report view
                    # (includes Opening/Initial balance and Total/Final balance rows)
                    report_to_csv(report_to_export, filepath)
                else:
                    from gui.exporters import export_report

                    export_report(report_to_export, filepath, fmt)
            messagebox.showinfo("Success", f"Exported to {filepath}")
            open_in_file_manager(os.path.dirname(filepath))
        except Exception as error:
            messagebox.showerror("Error", f"Failed to export: {error}")


def _fmt_kzt(value: float) -> str:
    # 1 000 000.00 style (space-grouped).
    try:
        return f"{float(value):,.2f}".replace(",", " ")
    except Exception:
        return "0.00"
