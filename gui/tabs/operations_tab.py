from __future__ import annotations

import os
import tkinter as tk
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from tkinter import VERTICAL, filedialog, messagebox, ttk
from typing import Any, Protocol

from domain.import_policy import ImportPolicy
from domain.import_result import ImportResult
from gui.helpers import open_in_file_manager


class OperationsTabContext(Protocol):
    controller: Any
    repository: Any
    _record_id_to_repo_index: dict[str, int]
    _record_id_to_domain_id: dict[str, int]

    def _refresh_list(self) -> None: ...

    def _refresh_charts(self) -> None: ...

    def _refresh_wallets(self) -> None: ...

    def _run_background(
        self,
        task: Callable[[], Any],
        *,
        on_success: Callable[[Any], None],
        on_error: Callable[[BaseException], None] | None = None,
        busy_message: str = "Processing...",
    ) -> None: ...

    def _import_policy_from_ui(self, mode_label: str) -> ImportPolicy: ...


@dataclass(slots=True)
class OperationsTabBindings:
    records_tree: ttk.Treeview
    refresh_operation_wallet_menu: Callable[[], None]
    refresh_transfer_wallet_menus: Callable[[], None]


def show_import_preview_dialog(
    parent: tk.Misc,
    *,
    filepath: str,
    policy_label: str,
    preview: ImportResult,
    force: bool = False,
) -> bool:
    dialog = tk.Toplevel(parent)
    dialog.title("Import Preview (Dry-Run)")
    dialog.transient(parent.winfo_toplevel())
    dialog.resizable(False, False)

    result = {"confirmed": False}
    content = ttk.Frame(dialog, padding=12)
    content.grid(row=0, column=0, sticky="nsew")
    content.grid_columnconfigure(0, weight=1)

    ttk.Label(content, text="Import Preview (Dry-Run)", font=("Segoe UI", 11, "bold")).grid(
        row=0, column=0, sticky="w"
    )
    ttk.Label(content, text=f"File: {Path(filepath).name}").grid(
        row=1, column=0, sticky="w", pady=(8, 0)
    )
    ttk.Label(content, text=f"Policy: {policy_label}").grid(row=2, column=0, sticky="w")

    if force:
        ttk.Label(
            content,
            text="Readonly snapshot: force override is active.",
            foreground="#b45309",
        ).grid(row=3, column=0, sticky="w", pady=(8, 0))
        stats_row = 4
    else:
        stats_row = 3

    stats = ttk.Frame(content)
    stats.grid(row=stats_row, column=0, sticky="ew", pady=(10, 0))
    stats.grid_columnconfigure(1, weight=1)
    ttk.Label(stats, text="Records to import:").grid(row=0, column=0, sticky="w")
    ttk.Label(stats, text=str(preview.imported)).grid(row=0, column=1, sticky="e")
    ttk.Label(stats, text="Skipped rows:").grid(row=1, column=0, sticky="w")
    ttk.Label(stats, text=str(preview.skipped)).grid(row=1, column=1, sticky="e")
    ttk.Label(stats, text="Errors:").grid(row=2, column=0, sticky="w")
    ttk.Label(stats, text=str(len(preview.errors))).grid(row=2, column=1, sticky="e")

    ttk.Label(content, text="Errors:").grid(row=stats_row + 1, column=0, sticky="w", pady=(10, 4))
    errors_frame = ttk.Frame(content)
    errors_frame.grid(row=stats_row + 2, column=0, sticky="ew")
    errors_frame.grid_columnconfigure(0, weight=1)
    errors_tree = ttk.Treeview(
        errors_frame,
        show="tree",
        selectmode="none",
        height=min(max(len(preview.errors), 1), 5),
    )
    errors_tree.grid(row=0, column=0, sticky="nsew")
    errors_scroll = ttk.Scrollbar(errors_frame, orient=VERTICAL, command=errors_tree.yview)
    errors_scroll.grid(row=0, column=1, sticky="ns")
    errors_tree.config(yscrollcommand=errors_scroll.set)
    for error in preview.errors or ["No validation errors."]:
        errors_tree.insert("", "end", text=error)

    buttons = ttk.Frame(content)
    buttons.grid(row=stats_row + 3, column=0, sticky="e", pady=(12, 0))

    def close() -> None:
        dialog.destroy()

    def proceed() -> None:
        result["confirmed"] = True
        dialog.destroy()

    ttk.Button(buttons, text="Cancel", command=close).pack(side=tk.LEFT, padx=(0, 8))
    if preview.imported > 0:
        ttk.Button(buttons, text="Proceed with Import", command=proceed).pack(side=tk.LEFT)

    dialog.protocol("WM_DELETE_WINDOW", close)
    dialog.update_idletasks()

    parent_window = parent.winfo_toplevel()
    parent_x = parent_window.winfo_rootx()
    parent_y = parent_window.winfo_rooty()
    parent_w = parent_window.winfo_width()
    parent_h = parent_window.winfo_height()
    width = dialog.winfo_width()
    height = dialog.winfo_height()
    pos_x = parent_x + max((parent_w - width) // 2, 0)
    pos_y = parent_y + max((parent_h - height) // 2, 0)
    dialog.geometry(f"+{pos_x}+{pos_y}")

    dialog.grab_set()
    parent.wait_window(dialog)
    return bool(result["confirmed"])


def build_operations_tab(
    parent: tk.Frame | ttk.Frame,
    context: OperationsTabContext,
    import_formats: dict[str, dict[str, str]],
) -> OperationsTabBindings:
    parent.grid_columnconfigure(0, weight=0)
    parent.grid_columnconfigure(1, weight=1)
    parent.grid_rowconfigure(0, weight=1)

    left_frame = tk.Frame(parent)
    left_frame.grid(row=0, column=0, sticky="nsw", padx=10, pady=10)

    form_frame = ttk.LabelFrame(left_frame, text="Add operation")
    form_frame.grid(row=0, column=0, sticky="ew", pady=(0, 10))
    form_frame.grid_columnconfigure(1, weight=1)

    ttk.Label(form_frame, text="Type:").grid(row=0, column=0, sticky="w", padx=6, pady=4)
    type_var = tk.StringVar(value="Income")
    ttk.OptionMenu(form_frame, type_var, "Income", "Income", "Expense").grid(
        row=0, column=1, sticky="ew", padx=6, pady=4
    )

    ttk.Label(form_frame, text="Date (YYYY-MM-DD):").grid(
        row=1, column=0, sticky="w", padx=6, pady=4
    )
    date_entry = ttk.Entry(form_frame)
    date_entry.grid(row=1, column=1, sticky="ew", padx=6, pady=4)

    ttk.Label(form_frame, text="Amount:").grid(row=2, column=0, sticky="w", padx=6, pady=4)
    amount_entry = ttk.Entry(form_frame)
    amount_entry.grid(row=2, column=1, sticky="ew", padx=6, pady=4)

    ttk.Label(form_frame, text="Currency:").grid(row=3, column=0, sticky="w", padx=6, pady=4)
    currency_entry = ttk.Entry(form_frame)
    currency_entry.insert(0, "KZT")
    currency_entry.grid(row=3, column=1, sticky="ew", padx=6, pady=4)

    ttk.Label(form_frame, text="Category:").grid(row=4, column=0, sticky="w", padx=6, pady=4)
    category_combo = ttk.Combobox(form_frame, state="normal")
    category_combo.insert(0, "General")
    category_combo.grid(row=4, column=1, sticky="ew", padx=6, pady=4)

    ttk.Label(form_frame, text="Description (optional):").grid(
        row=5, column=0, sticky="w", padx=6, pady=4
    )
    description_entry = ttk.Entry(form_frame)
    description_entry.grid(row=5, column=1, sticky="ew", padx=6, pady=4)

    ttk.Label(form_frame, text="Wallet:").grid(row=6, column=0, sticky="w", padx=6, pady=4)
    operation_wallet_var = tk.StringVar(value="")
    operation_wallet_menu = ttk.OptionMenu(form_frame, operation_wallet_var, "")
    operation_wallet_menu.grid(row=6, column=1, sticky="ew", padx=6, pady=4)
    operation_wallet_map: dict[str, int] = {}

    def _refresh_category_combo() -> None:
        try:
            if type_var.get() == "Income":
                category_combo["values"] = context.controller.get_income_categories()
            else:
                category_combo["values"] = context.controller.get_expense_categories()
        except Exception:
            pass
        category_combo.set("General")

    def _on_type_change(*_args: object) -> None:
        _refresh_category_combo()

    def refresh_operation_wallet_menu() -> None:
        nonlocal operation_wallet_map
        wallets = context.controller.load_active_wallets()
        operation_wallet_map = {
            f"[{wallet.id}] {wallet.name} ({wallet.currency})": wallet.id for wallet in wallets
        }
        labels = list(operation_wallet_map.keys()) or [""]
        menu = operation_wallet_menu["menu"]
        menu.delete(0, "end")
        for label in labels:
            menu.add_command(
                label=label, command=lambda value=label: operation_wallet_var.set(value)
            )
        if operation_wallet_var.get() not in operation_wallet_map:
            operation_wallet_var.set(labels[0])

    refresh_operation_wallet_menu()

    list_frame = ttk.LabelFrame(parent, text="List of operations")
    list_frame.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)
    list_frame.grid_rowconfigure(0, weight=1)
    list_frame.grid_columnconfigure(0, weight=1)

    records_tree = ttk.Treeview(
        list_frame,
        show="headings",
        selectmode="browse",
        columns=(
            "index",
            "date",
            "type",
            "category",
            "amount",
            "currency",
            "kzt",
            "wallets",
        ),
    )
    records_tree.heading("index", text="#")
    records_tree.heading("date", text="Date")
    records_tree.heading("type", text="Type")
    records_tree.heading("category", text="Category")
    records_tree.heading("amount", text="Amount")
    records_tree.heading("currency", text="Cur")
    records_tree.heading("kzt", text="KZT")
    records_tree.heading("wallets", text="Wallets")
    records_tree.column("index", width=40, minwidth=50, stretch=False, anchor="e")
    records_tree.column("date", width=80, minwidth=90, stretch=False)
    records_tree.column("type", width=120, minwidth=110, stretch=False)
    records_tree.column("category", width=160, minwidth=140, stretch=True)
    records_tree.column("amount", width=70, minwidth=90, stretch=False, anchor="e")
    records_tree.column("currency", width=60, minwidth=50, stretch=False, anchor="center")
    records_tree.column("kzt", width=100, minwidth=90, stretch=False, anchor="e")
    records_tree.column("wallets", width=80, minwidth=110, stretch=False, anchor="center")
    records_tree.grid(row=0, column=0, sticky="nsew", padx=6, pady=6)

    scrollbar = ttk.Scrollbar(list_frame, orient=VERTICAL, command=records_tree.yview)
    scrollbar.grid(row=0, column=1, sticky="ns", pady=6)
    records_tree.config(yscrollcommand=scrollbar.set)

    def save_record() -> None:
        date_str = date_entry.get().strip()
        if not date_str:
            messagebox.showerror("Error", "Date is required.")
            return
        try:
            from domain.validation import ensure_not_future, parse_ymd

            entered_date = parse_ymd(date_str)
            ensure_not_future(entered_date)
        except ValueError as error:
            messagebox.showerror("Error", f"Invalid date: {str(error)}. Use YYYY-MM-DD.")
            return

        amount_str = amount_entry.get().strip()
        if not amount_str:
            messagebox.showerror("Error", "Amount is required.")
            return
        try:
            amount = float(amount_str)
        except ValueError:
            messagebox.showerror("Error", "Invalid amount.")
            return

        currency = (currency_entry.get() or "KZT").strip()
        category = (category_combo.get() or "General").strip()
        description = description_entry.get().strip()
        wallet_id = operation_wallet_map.get(operation_wallet_var.get())
        if wallet_id is None:
            messagebox.showerror("Error", "Wallet is required.")
            return

        try:
            if type_var.get() == "Income":
                context.controller.create_income(
                    date=date_str,
                    wallet_id=wallet_id,
                    amount=amount,
                    currency=currency,
                    category=category,
                    description=description,
                )
                messagebox.showinfo("Success", "Income record added.")
            else:
                context.controller.create_expense(
                    date=date_str,
                    wallet_id=wallet_id,
                    amount=amount,
                    currency=currency,
                    category=category,
                    description=description,
                )
                messagebox.showinfo("Success", "Expense record added.")

            date_entry.delete(0, tk.END)
            amount_entry.delete(0, tk.END)
            category_combo.delete(0, tk.END)
            description_entry.delete(0, tk.END)
            _refresh_category_combo()
            context._refresh_list()
            context._refresh_charts()
            context._refresh_wallets()
        except Exception as error:
            messagebox.showerror("Error", f"Failed to add record: {str(error)}")

    ttk.Button(form_frame, text="Save", command=save_record).grid(
        row=7, column=0, columnspan=2, pady=8
    )

    def delete_selected() -> None:
        selection = records_tree.selection()
        if not selection:
            messagebox.showerror("Error", "Please select a record to delete.")
            return
        record_id = selection[0]
        repository_index = context._record_id_to_repo_index.get(record_id)
        if repository_index is None:
            messagebox.showerror("Error", "Selected record is no longer available.")
            context._refresh_list()
            return
        try:
            transfer_id = context.controller.transfer_id_by_repository_index(repository_index)
            if transfer_id is not None:
                context.controller.delete_transfer(transfer_id)
                messagebox.showinfo("Success", f"Deleted transfer #{transfer_id}.")
            elif context.controller.delete_record(repository_index):
                messagebox.showinfo("Success", f"Deleted record at index {repository_index}.")
            else:
                messagebox.showerror("Error", "Failed to delete record.")
                return
            context._refresh_list()
            context._refresh_charts()
            context._refresh_wallets()
        except Exception as error:
            messagebox.showerror("Error", f"Failed to delete: {str(error)}")

    edit_panel_state: dict[str, ttk.Frame | None] = {"panel": None}

    def edit_selected_record_inline() -> None:
        selection = records_tree.selection()
        if not selection:
            messagebox.showerror("Error", "Please select a record to edit.")
            return

        ui_record_id = selection[0]
        domain_record_id = context._record_id_to_domain_id.get(ui_record_id)
        if domain_record_id is None:
            messagebox.showerror("Error", "Selected record cannot be edited.")
            return

        try:
            record = context.controller.get_record_for_edit(domain_record_id)
        except Exception:
            messagebox.showerror("Error", "Cannot load record for editing.")
            return

        if record.transfer_id is not None:
            messagebox.showerror("Error", "Transfer-linked records cannot be edited.")
            return
        if str(getattr(record, "category", "") or "").strip().lower() == "transfer":
            messagebox.showerror("Error", "Transfer records cannot be edited.")
            return

        if edit_panel_state["panel"] is not None:
            try:
                edit_panel_state["panel"].destroy()
            except Exception:
                pass
            edit_panel_state["panel"] = None

        edit_panel = ttk.Frame(list_frame)
        edit_panel.grid(row=2, column=0, columnspan=2, sticky="ew", padx=6, pady=(0, 6))
        edit_panel_state["panel"] = edit_panel

        ttk.Label(edit_panel, text="Amount (KZT):").grid(row=0, column=0, sticky="w", padx=4)
        amount_entry = ttk.Entry(edit_panel)
        amount_entry.grid(row=0, column=1, sticky="ew", padx=4)
        ttk.Label(edit_panel, text="Date (YYYY-MM-DD):").grid(row=1, column=0, sticky="w", padx=4)
        date_edit_entry = ttk.Entry(edit_panel)
        date_edit_entry.grid(row=1, column=1, sticky="ew", padx=4)
        ttk.Label(edit_panel, text="Wallet:").grid(row=2, column=0, sticky="w", padx=4)
        wallet_edit_var = tk.StringVar(value="")
        wallet_edit_menu = ttk.OptionMenu(edit_panel, wallet_edit_var, "")
        wallet_edit_menu.grid(row=2, column=1, sticky="ew", padx=4)
        ttk.Label(edit_panel, text="Category:").grid(row=3, column=0, sticky="w", padx=4)
        category_edit_combo = ttk.Combobox(edit_panel, state="normal")
        category_edit_combo.grid(row=3, column=1, sticky="ew", padx=4)
        ttk.Label(edit_panel, text="Description (optional):").grid(
            row=4, column=0, sticky="w", padx=4
        )
        description_edit_entry = ttk.Entry(edit_panel)
        description_edit_entry.grid(row=4, column=1, sticky="ew", padx=4)
        edit_panel.grid_columnconfigure(1, weight=1)

        # Fill the fields with post data
        amount_entry.insert(0, f"{float(record.amount_kzt or 0.0):.2f}")
        date_value = (
            record.date.isoformat() if hasattr(record.date, "isoformat") else str(record.date)
        )
        date_edit_entry.insert(0, date_value)
        try:
            if record.type == "income":
                category_edit_combo["values"] = context.controller.get_income_categories()
            elif record.type == "expense":
                category_edit_combo["values"] = context.controller.get_expense_categories()
            else:
                category_edit_combo["values"] = (
                    context.controller.get_mandatory_expense_categories()
                )
        except Exception:
            pass
        category_edit_combo.insert(0, str(record.category or ""))
        description_edit_entry.insert(0, str(record.description or ""))

        wallet_edit_map: dict[str, int] = {
            f"[{wallet.id}] {wallet.name} ({wallet.currency})": wallet.id
            for wallet in context.controller.load_wallets()
        }
        wallet_labels = list(wallet_edit_map.keys()) or [""]
        wallet_menu = wallet_edit_menu["menu"]
        wallet_menu.delete(0, "end")
        for label in wallet_labels:
            wallet_menu.add_command(
                label=label,
                command=lambda value=label: wallet_edit_var.set(value),
            )
        current_wallet_label = next(
            (label for label, wid in wallet_edit_map.items() if int(wid) == int(record.wallet_id)),
            wallet_labels[0],
        )
        wallet_edit_var.set(current_wallet_label)

        def save_edit() -> None:
            try:
                new_amount_kzt = float(amount_entry.get().strip())
            except ValueError:
                messagebox.showerror("Error", "Invalid amount.")
                return
            new_date = date_edit_entry.get().strip()
            if not new_date:
                messagebox.showerror("Error", "Date is required.")
                return
            new_category = category_edit_combo.get().strip()
            if not new_category:
                messagebox.showerror("Error", "Category is required.")
                return
            new_wallet_id = wallet_edit_map.get(wallet_edit_var.get())
            if new_wallet_id is None:
                messagebox.showerror("Error", "Wallet is required.")
                return
            try:
                context.controller.update_record_inline(
                    domain_record_id,
                    new_amount_kzt=new_amount_kzt,
                    new_category=new_category,
                    new_description=description_edit_entry.get().strip(),
                    new_date=new_date,
                    new_wallet_id=new_wallet_id,
                )
                messagebox.showinfo(
                    "Success",
                    "Record updated. date, wallet, amount_kzt, category, "
                    "and description were saved.",
                )
                context._refresh_list()
                context._refresh_charts()
                cancel_edit()
            except Exception as error:
                messagebox.showerror("Error", f"Failed to update record: {str(error)}")

        def cancel_edit() -> None:
            if edit_panel_state["panel"] is not None:
                try:
                    edit_panel_state["panel"].destroy()
                except Exception:
                    pass
                edit_panel_state["panel"] = None

        ttk.Button(edit_panel, text="Save", command=save_edit).grid(row=5, column=2, padx=4)
        ttk.Button(edit_panel, text="Cancel", command=cancel_edit).grid(row=5, column=3, padx=4)

    def delete_all() -> None:
        confirm = messagebox.askyesno(
            "Confirm Delete All",
            "Are you sure you want to delete ALL records? This action cannot be undone.",
        )
        if confirm:
            context.controller.delete_all_records()
            messagebox.showinfo("Success", "All records have been deleted.")
            context._refresh_list()
            context._refresh_charts()

    wallet_id_map: dict[str, int] = {}

    transfer_frame = ttk.LabelFrame(left_frame, text="Transfer")
    transfer_frame.grid(row=1, column=0, sticky="ew")
    transfer_frame.grid_columnconfigure(1, weight=1)

    ttk.Label(transfer_frame, text="From wallet:").grid(row=0, column=0, sticky="w", padx=4, pady=2)
    transfer_from_var = tk.StringVar(value="")
    transfer_from_menu = ttk.OptionMenu(transfer_frame, transfer_from_var, "")
    transfer_from_menu.grid(row=0, column=1, sticky="ew", padx=4, pady=2)

    ttk.Label(transfer_frame, text="To wallet:").grid(row=1, column=0, sticky="w", padx=4, pady=2)
    transfer_to_var = tk.StringVar(value="")
    transfer_to_menu = ttk.OptionMenu(transfer_frame, transfer_to_var, "")
    transfer_to_menu.grid(row=1, column=1, sticky="ew", padx=4, pady=2)

    ttk.Label(transfer_frame, text="Date:").grid(row=2, column=0, sticky="w", padx=4, pady=2)
    transfer_date_entry = ttk.Entry(transfer_frame)
    transfer_date_entry.grid(row=2, column=1, sticky="ew", padx=4, pady=2)
    transfer_date_entry.insert(0, date.today().isoformat())

    ttk.Label(transfer_frame, text="Amount:").grid(row=3, column=0, sticky="w", padx=4, pady=2)
    transfer_amount_entry = ttk.Entry(transfer_frame)
    transfer_amount_entry.grid(row=3, column=1, sticky="ew", padx=4, pady=2)

    ttk.Label(transfer_frame, text="Currency:").grid(row=4, column=0, sticky="w", padx=4, pady=2)
    transfer_currency_entry = ttk.Entry(transfer_frame)
    transfer_currency_entry.insert(0, "KZT")
    transfer_currency_entry.grid(row=4, column=1, sticky="ew", padx=4, pady=2)

    ttk.Label(transfer_frame, text="Commission:").grid(row=5, column=0, sticky="w", padx=4, pady=2)
    transfer_commission_entry = ttk.Entry(transfer_frame)
    transfer_commission_entry.insert(0, "0")
    transfer_commission_entry.grid(row=5, column=1, sticky="ew", padx=4, pady=2)

    ttk.Label(transfer_frame, text="Commission currency:").grid(
        row=6, column=0, sticky="w", padx=4, pady=2
    )
    transfer_commission_currency_entry = ttk.Entry(transfer_frame)
    transfer_commission_currency_entry.insert(0, "KZT")
    transfer_commission_currency_entry.grid(row=6, column=1, sticky="ew", padx=4, pady=2)

    ttk.Label(transfer_frame, text="Description:").grid(row=7, column=0, sticky="w", padx=4, pady=2)
    transfer_description_entry = ttk.Entry(transfer_frame)
    transfer_description_entry.grid(row=7, column=1, sticky="ew", padx=4, pady=2)

    def refresh_transfer_wallet_menus() -> None:
        nonlocal wallet_id_map
        wallets = context.controller.load_active_wallets()
        wallet_id_map = {
            f"[{wallet.id}] {wallet.name} ({wallet.currency})": wallet.id for wallet in wallets
        }
        labels = list(wallet_id_map.keys()) or [""]

        for menu_widget, var in (
            (transfer_from_menu, transfer_from_var),
            (transfer_to_menu, transfer_to_var),
        ):
            menu = menu_widget["menu"]
            menu.delete(0, "end")
            for label in labels:
                menu.add_command(label=label, command=lambda value=label, v=var: v.set(value))
            if not var.get() or var.get() not in wallet_id_map:
                var.set(labels[0])

        if len(labels) > 1 and transfer_to_var.get() == transfer_from_var.get():
            transfer_to_var.set(labels[1])

    def create_transfer() -> None:
        from_wallet_id = wallet_id_map.get(transfer_from_var.get())
        to_wallet_id = wallet_id_map.get(transfer_to_var.get())
        if from_wallet_id is None or to_wallet_id is None:
            messagebox.showerror("Error", "Please select source and destination wallets.")
            return

        date_str = transfer_date_entry.get().strip()
        if not date_str:
            messagebox.showerror("Error", "Transfer date is required.")
            return
        try:
            from domain.validation import ensure_not_future, parse_ymd

            entered_date = parse_ymd(date_str)
            ensure_not_future(entered_date)
        except ValueError as error:
            messagebox.showerror("Error", f"Invalid date: {str(error)}. Use YYYY-MM-DD.")
            return

        amount_str = transfer_amount_entry.get().strip()
        if not amount_str:
            messagebox.showerror("Error", "Transfer amount is required.")
            return

        try:
            transfer_amount = float(amount_str)
            commission_amount = float((transfer_commission_entry.get() or "0").strip())
        except ValueError:
            messagebox.showerror("Error", "Transfer amount/commission must be numeric.")
            return

        try:
            transfer_id = context.controller.create_transfer(
                from_wallet_id=from_wallet_id,
                to_wallet_id=to_wallet_id,
                transfer_date=date_str,
                amount=transfer_amount,
                currency=(transfer_currency_entry.get() or "KZT").strip(),
                description=transfer_description_entry.get().strip(),
                commission_amount=commission_amount,
                commission_currency=(transfer_commission_currency_entry.get() or "").strip(),
            )
            messagebox.showinfo("Success", f"Transfer created (id={transfer_id}).")
            transfer_amount_entry.delete(0, tk.END)
            transfer_description_entry.delete(0, tk.END)
            transfer_commission_entry.delete(0, tk.END)
            transfer_commission_entry.insert(0, "0")
            context._refresh_list()
            context._refresh_charts()
            context._refresh_wallets()
        except Exception as error:
            messagebox.showerror("Error", f"Failed to create transfer: {str(error)}")

    ttk.Button(transfer_frame, text="Create transfer", command=create_transfer).grid(
        row=8, column=0, columnspan=2, pady=6
    )
    refresh_transfer_wallet_menus()

    import_mode_var = tk.StringVar(value="Full Backup")
    import_format_var = tk.StringVar(value="CSV")

    def import_records_data() -> None:
        policy = context._import_policy_from_ui(import_mode_var.get())
        fmt = import_format_var.get()
        cfg = import_formats.get(fmt)
        if not cfg:
            messagebox.showerror("Error", f"Unsupported import format: {fmt}")
            return

        filepath = filedialog.askopenfilename(
            defaultextension=cfg["ext"],
            filetypes=[(f"{fmt} files", f"*{cfg['ext']}"), ("All files", "*.*")],
            title=f"Select {cfg['desc']} file to import",
        )
        if not filepath:
            return

        if policy == ImportPolicy.CURRENT_RATE:
            messagebox.showwarning(
                "Current Rate Import",
                "For CURRENT_RATE mode, exchange rates will be fixed at import time.",
            )

        def preview_task() -> ImportResult:
            return context.controller.import_records(fmt, filepath, policy, dry_run=True)

        def commit_task() -> ImportResult:
            return context.controller.import_records(fmt, filepath, policy, dry_run=False)

        def on_commit_success(result: ImportResult) -> None:
            details = ""
            if result.skipped or result.errors:
                details = f"\nSkipped: {result.skipped} rows.\nFirst errors:\n- " + "\n- ".join(
                    result.errors[:5]
                )
            messagebox.showinfo(
                "Success",
                f"Successfully imported {result.imported} records from {cfg['desc']} file."
                "\nAll existing records have been replaced." + details,
            )
            context._refresh_list()
            context._refresh_charts()
            context._refresh_wallets()

        def on_error(exc: BaseException) -> None:
            if isinstance(exc, FileNotFoundError):
                messagebox.showerror("Error", f"File not found: {filepath}")
                return
            messagebox.showerror("Error", f"Failed to import {cfg['desc']}: {str(exc)}")

        def on_preview_success(preview: ImportResult) -> None:
            confirmed = show_import_preview_dialog(
                parent=parent,
                filepath=filepath,
                policy_label=import_mode_var.get(),
                preview=preview,
                force=False,
            )
            if not confirmed:
                return
            context._run_background(
                commit_task,
                on_success=on_commit_success,
                on_error=on_error,
                busy_message=f"Importing {cfg['desc']}...",
            )

        context._run_background(
            preview_task,
            on_success=on_preview_success,
            on_error=on_error,
            busy_message=f"Validating {cfg['desc']} import...",
        )

    def export_records_data() -> None:
        fmt = import_format_var.get()
        cfg = import_formats.get(fmt)
        if not cfg or fmt == "JSON":
            messagebox.showerror("Error", "Unsupported export format for records.")
            return
        filepath = filedialog.asksaveasfilename(
            defaultextension=cfg["ext"],
            filetypes=[(f"{cfg['desc']} files", f"*{cfg['ext']}"), ("All files", "*.*")],
            title=f"Save records as {cfg['desc']}",
        )
        if not filepath:
            return

        records = context.repository.load_all()
        transfers = context.repository.load_transfers()

        def task() -> None:
            from gui.exporters import export_records

            export_records(records, filepath, fmt.lower(), transfers=transfers)

        def on_success(_: Any) -> None:
            messagebox.showinfo("Success", f"Records exported to {filepath}")
            open_in_file_manager(os.path.dirname(filepath))

        context._run_background(
            task,
            on_success=on_success,
            busy_message=f"Exporting {cfg['desc']}...",
        )

    btn_frame = tk.Frame(list_frame)
    btn_frame.grid(row=1, column=0, columnspan=2, pady=6)

    ttk.Button(btn_frame, text="Delete Selected", command=delete_selected).pack(
        side=tk.LEFT, padx=6
    )
    ttk.Button(btn_frame, text="Edit", command=edit_selected_record_inline).pack(
        side=tk.LEFT, padx=6
    )
    ttk.Button(btn_frame, text="Delete All", command=delete_all).pack(side=tk.LEFT, padx=6)
    ttk.Button(btn_frame, text="Refresh", command=context._refresh_list).pack(side=tk.LEFT, padx=6)

    ttk.OptionMenu(
        btn_frame,
        import_mode_var,
        "Full Backup",
        "Full Backup",
        "Current Rate",
        "Legacy Import",
    ).pack(side=tk.LEFT, padx=6)
    ttk.OptionMenu(btn_frame, import_format_var, "CSV", "CSV", "XLSX").pack(side=tk.LEFT, padx=6)
    ttk.Button(btn_frame, text="Import", command=import_records_data).pack(side=tk.LEFT, padx=6)
    ttk.Button(btn_frame, text="Export Data", command=export_records_data).pack(
        side=tk.LEFT, padx=6
    )

    context._refresh_list()

    type_var.trace_add("write", _on_type_change)
    parent.after(150, _refresh_category_combo)

    return OperationsTabBindings(
        records_tree=records_tree,
        refresh_operation_wallet_menu=refresh_operation_wallet_menu,
        refresh_transfer_wallet_menus=refresh_transfer_wallet_menus,
    )
