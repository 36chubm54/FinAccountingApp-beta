"""
Settings tab — management of wallets and mandatory expenses (CRUD, import/export), backup, audit.
"""

from __future__ import annotations

import os
import tkinter as tk
from collections.abc import Callable
from tkinter import filedialog, messagebox, ttk
from typing import Any, Protocol

from domain.import_policy import ImportPolicy
from domain.import_result import ImportResult
from gui.helpers import open_in_file_manager
from gui.tabs.settings_support import safe_destroy, show_audit_report_dialog


class SettingsTabContext(Protocol):
    controller: Any
    repository: Any
    refresh_operation_wallet_menu: Callable[[], None] | None
    refresh_transfer_wallet_menus: Callable[[], None] | None
    refresh_wallets: Callable[[], None] | None

    def _refresh_list(self) -> None: ...

    def _refresh_charts(self) -> None: ...

    def _refresh_budgets(self) -> None: ...

    def _refresh_all(self) -> None: ...

    def _run_background(
        self,
        task: Callable[[], Any],
        *,
        on_success: Callable[[Any], None],
        on_error: Callable[[BaseException], None] | None = None,
        busy_message: str = "Processing...",
    ) -> None: ...


def build_settings_tab(
    parent: tk.Frame | ttk.Frame,
    context: SettingsTabContext,
    import_formats: dict[str, dict[str, str]],
) -> None:
    pad_x = 8
    pad_y = 6

    parent.grid_columnconfigure(0, weight=0)
    parent.grid_columnconfigure(1, weight=1)
    parent.grid_rowconfigure(0, weight=1)

    left_panel = ttk.Frame(parent)
    left_panel.grid(row=0, column=0, sticky="ns", padx=10, pady=10)

    right_panel = ttk.Frame(parent)
    right_panel.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)
    right_panel.grid_rowconfigure(0, weight=1)
    right_panel.grid_columnconfigure(0, weight=1)

    wallets_frame = ttk.LabelFrame(left_panel, text="Wallets")
    wallets_frame.grid(row=0, column=0, sticky="nsew", pady=(0, 10))
    wallets_frame.grid_columnconfigure(0, weight=1)
    wallets_frame.grid_rowconfigure(1, weight=1)

    form = ttk.Frame(wallets_frame)
    form.grid(row=0, column=0, sticky="ew", padx=pad_x, pady=pad_y)
    form.grid_columnconfigure(1, weight=1)

    ttk.Label(form, text="Name:").grid(row=0, column=0, sticky="w")
    wallet_name_entry = ttk.Entry(form)
    wallet_name_entry.grid(row=0, column=1, sticky="ew", pady=2)

    ttk.Label(form, text="Currency:").grid(row=1, column=0, sticky="w")
    wallet_currency_entry = ttk.Entry(form, width=8)
    wallet_currency_entry.insert(0, "KZT")
    wallet_currency_entry.grid(row=1, column=1, sticky="ew", pady=2)

    ttk.Label(form, text="Initial balance:").grid(row=2, column=0, sticky="w")
    wallet_initial_entry = ttk.Entry(form)
    wallet_initial_entry.insert(0, "0")
    wallet_initial_entry.grid(row=2, column=1, sticky="ew", pady=2)

    wallet_allow_negative_var = tk.BooleanVar(value=False)
    ttk.Checkbutton(form, text="Allow negative", variable=wallet_allow_negative_var).grid(
        row=3,
        column=0,
        columnspan=2,
        sticky="w",
        pady=2,
    )

    list_frame = ttk.Frame(wallets_frame)
    list_frame.grid(row=1, column=0, sticky="nsew", padx=pad_x)
    list_frame.grid_rowconfigure(0, weight=1)
    list_frame.grid_columnconfigure(0, weight=1)

    wallet_columns = (
        "id",
        "name",
        "currency",
        "initial_balance",
        "balance",
        "allow_negative",
        "active",
    )
    wallet_tree = ttk.Treeview(
        list_frame,
        columns=wallet_columns,
        show="headings",
        selectmode="browse",
        height=8,
    )
    for col, text, width, minwidth, stretch, anchor in (
        ("id", "ID", 30, 30, False, "e"),
        ("name", "Name", 80, 80, False, "w"),
        ("currency", "Currency", 45, 45, False, "center"),
        ("initial_balance", "Initial balance", 85, 85, False, "e"),
        ("balance", "Balance", 85, 85, False, "e"),
        ("allow_negative", "Allow negative", 95, 95, False, "center"),
        ("active", "Active", 55, 55, False, "center"),
    ):
        wallet_tree.heading(col, text=text)
        wallet_tree.column(col, width=width, minwidth=minwidth, stretch=stretch, anchor=anchor)  # type: ignore
    wallet_tree.grid(row=0, column=0, sticky="nsew")

    wallet_scroll = ttk.Scrollbar(list_frame, orient="vertical", command=wallet_tree.yview)
    wallet_scroll.grid(row=0, column=1, sticky="ns")
    wallet_xscroll = ttk.Scrollbar(list_frame, orient="horizontal", command=wallet_tree.xview)
    wallet_xscroll.grid(row=1, column=0, sticky="ew")
    wallet_tree.config(
        yscrollcommand=wallet_scroll.set,
        xscrollcommand=wallet_xscroll.set,
    )

    def refresh_wallets() -> None:
        for iid in wallet_tree.get_children():
            wallet_tree.delete(iid)
        for wallet in context.controller.load_wallets():
            try:
                balance = context.controller.wallet_balance(wallet.id)
            except ValueError:
                balance = wallet.initial_balance
            wallet_tree.insert(
                "",
                tk.END,
                values=(
                    int(wallet.id),
                    str(wallet.name),
                    str(wallet.currency),
                    f"{wallet.initial_balance:.2f}",
                    f"{balance:.2f}",
                    "Yes" if wallet.allow_negative else "No",
                    "Yes" if wallet.is_active else "No",
                ),
            )

        if context.refresh_transfer_wallet_menus is not None:
            try:
                context.refresh_transfer_wallet_menus()
            except tk.TclError:
                pass

        if context.refresh_operation_wallet_menu is not None:
            try:
                context.refresh_operation_wallet_menu()
            except tk.TclError:
                pass

    context.refresh_wallets = refresh_wallets

    def create_wallet() -> None:
        try:
            initial_balance = float(wallet_initial_entry.get().strip() or "0")
        except ValueError:
            messagebox.showerror("Error", "Invalid wallet initial balance.")
            return

        try:
            wallet = context.controller.create_wallet(
                name=wallet_name_entry.get().strip(),
                currency=(wallet_currency_entry.get() or "KZT").strip(),
                initial_balance=initial_balance,
                allow_negative=wallet_allow_negative_var.get(),
            )
            messagebox.showinfo("Success", f"Wallet created: [{wallet.id}] {wallet.name}")
            wallet_name_entry.delete(0, tk.END)
            wallet_initial_entry.delete(0, tk.END)
            wallet_initial_entry.insert(0, "0")
            refresh_wallets()
        except Exception as error:
            messagebox.showerror("Error", f"Failed to create wallet: {str(error)}")

    ttk.Button(form, text="Create wallet", command=create_wallet).grid(
        row=4,
        column=0,
        columnspan=2,
        sticky="ew",
        pady=(6, 0),
    )

    def delete_wallet() -> None:
        selection = wallet_tree.selection()
        if not selection:
            messagebox.showerror("Error", "Select wallet to delete.")
            return
        try:
            values = wallet_tree.item(selection[0], "values")
            wallet_id = int(values[0])
        except Exception:
            messagebox.showerror("Error", "Failed to parse selected wallet id.")
            return

        try:
            context.controller.soft_delete_wallet(wallet_id)
            messagebox.showinfo("Success", "Wallet was soft-deleted.")
            refresh_wallets()
        except Exception as error:
            messagebox.showerror("Error", str(error))

    wallet_actions = ttk.Frame(wallets_frame)
    wallet_actions.grid(row=2, column=0, sticky="ew", padx=pad_x, pady=pad_y)
    wallet_actions.grid_columnconfigure(0, weight=1)
    wallet_actions.grid_columnconfigure(1, weight=1)

    ttk.Button(wallet_actions, text="Delete wallet", command=delete_wallet).grid(
        row=0,
        column=0,
        sticky="ew",
        padx=(0, 4),
    )
    ttk.Button(wallet_actions, text="Refresh", command=refresh_wallets).grid(
        row=0,
        column=1,
        sticky="ew",
        padx=(4, 0),
    )

    refresh_wallets()

    mand_frame = ttk.LabelFrame(right_panel, text="Mandatory expenses")
    mand_frame.grid(row=0, column=0, sticky="nsew")
    mand_frame.grid_rowconfigure(0, weight=1)
    mand_frame.grid_columnconfigure(0, weight=1)

    mand_list_frame = ttk.Frame(mand_frame)
    mand_list_frame.grid(row=0, column=0, columnspan=2, sticky="nsew", padx=pad_x, pady=pad_y)
    mand_list_frame.grid_rowconfigure(0, weight=1)
    mand_list_frame.grid_columnconfigure(0, weight=1)

    mand_tree = ttk.Treeview(
        mand_list_frame,
        show="headings",
        selectmode="browse",
        columns=(
            "index",
            "amount",
            "currency",
            "kzt",
            "category",
            "description",
            "period",
            "date",
            "autopay",
        ),
        height=10,
    )
    for col, text, width, minwidth, stretch, anchor in (
        ("index", "#", 30, 40, False, "e"),
        ("amount", "Amount", 70, 90, False, "e"),
        ("currency", "Cur", 50, 50, False, "center"),
        ("kzt", "KZT", 80, 90, False, "e"),
        ("category", "Category", 100, 120, False, "w"),
        ("description", "Description", 200, 160, True, "w"),
        ("period", "Period", 80, 70, False, "w"),
        ("date", "Date", 80, 90, False, "w"),
        ("autopay", "Autopay", 70, 60, False, "center"),
    ):
        mand_tree.heading(col, text=text)
        mand_tree.column(col, width=width, minwidth=minwidth, stretch=stretch, anchor=anchor)  # type: ignore[arg-type]
    mand_tree.grid(row=0, column=0, sticky="nsew")

    mand_scroll = ttk.Scrollbar(mand_list_frame, orient="vertical", command=mand_tree.yview)
    mand_scroll.grid(row=0, column=1, sticky="ns")
    mand_tree.config(yscrollcommand=mand_scroll.set)

    mand_xscroll = ttk.Scrollbar(mand_list_frame, orient="horizontal", command=mand_tree.xview)
    mand_xscroll.grid(row=1, column=0, sticky="ew")
    mand_tree.config(xscrollcommand=mand_xscroll.set)

    def _block_separator_resize(event: tk.Event) -> str | None:
        if isinstance(event.widget, ttk.Treeview):
            region = event.widget.identify_region(event.x, event.y)
            if region == "separator":
                return "break"
        return None

    def _mandatory_scroll_units(delta: int, *, multiplier: int = 12) -> int:
        if delta == 0:
            return 0
        base_units = max(1, abs(int(delta)) // 120)
        return base_units * multiplier

    def _scroll_mandatory_horizontally(direction: int, units: int) -> str:
        mand_tree.xview_scroll(direction * units, "units")
        return "break"

    def _on_mandatory_shift_mousewheel(event: tk.Event) -> str:
        delta = int(getattr(event, "delta", 0))
        units = _mandatory_scroll_units(delta)
        if units <= 0:
            return "break"
        direction = -1 if delta > 0 else 1
        return _scroll_mandatory_horizontally(direction, units)

    def _on_mandatory_shift_button4(_event: tk.Event) -> str:
        return _scroll_mandatory_horizontally(-1, 3)

    def _on_mandatory_shift_button5(_event: tk.Event) -> str:
        return _scroll_mandatory_horizontally(1, 3)

    for widget in (mand_tree, mand_xscroll):
        widget.bind("<Shift-MouseWheel>", _on_mandatory_shift_mousewheel, add="+")
        widget.bind("<Shift-Button-4>", _on_mandatory_shift_button4, add="+")
        widget.bind("<Shift-Button-5>", _on_mandatory_shift_button5, add="+")

    mand_tree.bind("<Button-1>", _block_separator_resize, add="+")

    def refresh_mandatory() -> None:
        for iid in mand_tree.get_children():
            mand_tree.delete(iid)
        expenses = context.controller.load_mandatory_expenses()
        for idx, expense in enumerate(expenses):
            date_value = (
                expense.date.isoformat()
                if getattr(expense.date, "isoformat", None) is not None
                else str(expense.date or "")
            )
            values = (
                str(idx),
                f"{float(expense.amount_original or 0.0):.2f}",
                str(expense.currency or "KZT").upper(),
                f"{float(expense.amount_kzt or 0.0):.2f}",
                str(expense.category or ""),
                str(expense.description or ""),
                str(expense.period or ""),
                str(date_value),
                "✓" if bool(expense.auto_pay) else "",
            )
            mand_tree.insert("", "end", iid=str(idx), values=values)

    current_panel: dict[str, tk.Frame | ttk.Frame | None] = {
        "add": None,
        "report": None,
        "edit": None,
    }

    def close_inline_panels() -> None:
        for key in ("add", "report", "edit"):
            panel = current_panel[key]
            if panel is not None:
                safe_destroy(panel)
                current_panel[key] = None

    def add_mandatory_inline() -> None:
        close_inline_panels()

        add_panel = tk.Frame(mand_frame)
        add_panel.grid(row=2, column=0, columnspan=2, pady=6, sticky="ew")
        current_panel["add"] = add_panel

        ttk.Label(add_panel, text="Amount:").grid(row=0, column=0, sticky="w")
        amount_entry = ttk.Entry(add_panel)
        amount_entry.grid(row=0, column=1)

        ttk.Label(add_panel, text="Currency (default KZT):").grid(row=1, column=0, sticky="w")
        currency_entry = ttk.Entry(add_panel)
        currency_entry.insert(0, "KZT")
        currency_entry.grid(row=1, column=1)

        ttk.Label(add_panel, text="Wallet:").grid(row=2, column=0, sticky="w")
        mandatory_wallet_var = tk.StringVar(value="")
        mandatory_wallet_menu = ttk.OptionMenu(add_panel, mandatory_wallet_var, "")
        mandatory_wallet_menu.grid(row=2, column=1, sticky="ew")
        mandatory_wallet_map: dict[str, int] = {
            f"[{wallet.id}] {wallet.name} ({wallet.currency})": wallet.id
            for wallet in context.controller.load_active_wallets()
        }
        wallet_labels = list(mandatory_wallet_map.keys()) or [""]
        wallet_menu = mandatory_wallet_menu["menu"]
        wallet_menu.delete(0, "end")
        for label in wallet_labels:
            wallet_menu.add_command(
                label=label, command=lambda value=label: mandatory_wallet_var.set(value)
            )
        mandatory_wallet_var.set(wallet_labels[0])

        ttk.Label(add_panel, text="Category (default Mandatory):").grid(row=3, column=0, sticky="w")
        category_entry = ttk.Entry(add_panel)
        category_entry.insert(0, "Mandatory")
        category_entry.grid(row=3, column=1)

        ttk.Label(add_panel, text="Description:").grid(row=4, column=0, sticky="w")
        description_entry = ttk.Entry(add_panel)
        description_entry.grid(row=4, column=1)

        ttk.Label(add_panel, text="Period:").grid(row=5, column=0, sticky="w")
        period_var = tk.StringVar(value="monthly")
        ttk.OptionMenu(add_panel, period_var, "daily", "daily", "weekly", "monthly", "yearly").grid(
            row=5,
            column=1,
        )

        ttk.Label(add_panel, text="Date (YYYY-MM-DD, optional):").grid(row=6, column=0, sticky="w")
        date_entry = ttk.Entry(add_panel)
        date_entry.grid(row=6, column=1)

        def save() -> None:
            try:
                amount = float(amount_entry.get())
                description = description_entry.get()
                if not description:
                    messagebox.showerror("Error", "Description is required.")
                    return
                date_val = date_entry.get().strip()
                if date_val:
                    try:
                        from domain.validation import parse_ymd

                        parse_ymd(date_val)
                    except ValueError:
                        messagebox.showerror("Error", "Invalid date format. Use YYYY-MM-DD.")
                        return
                wallet_id = mandatory_wallet_map.get(mandatory_wallet_var.get())
                if wallet_id is None:
                    messagebox.showerror("Error", "Wallet is required.")
                    return
                context.controller.create_mandatory_expense(
                    amount=amount,
                    currency=(currency_entry.get() or "KZT").strip(),
                    wallet_id=wallet_id,
                    category=(category_entry.get() or "Mandatory").strip(),
                    description=description,
                    period=period_var.get(),
                    date=date_val,
                )
                messagebox.showinfo("Success", "Mandatory expense added.")
                safe_destroy(add_panel)
                current_panel["add"] = None
                context._refresh_charts()
                refresh_mandatory()
                context._refresh_budgets()
            except Exception as error:
                messagebox.showerror("Error", f"Failed to add expense: {str(error)}")

        def cancel() -> None:
            try:
                safe_destroy(add_panel)
            finally:
                current_panel["add"] = None

        ttk.Button(add_panel, text="Save", command=save).grid(row=7, column=0, padx=6)
        ttk.Button(add_panel, text="Cancel", command=cancel).grid(row=7, column=1, padx=6)

    def edit_mandatory_inline() -> None:
        selection = mand_tree.selection()
        if not selection:
            messagebox.showerror("Error", "Select a required expense to edit.")
            return
        try:
            index = int(selection[0])
        except Exception:
            messagebox.showerror("Error", "Invalid selection.")
            return
        expenses = context.controller.load_mandatory_expenses()
        if not (0 <= index < len(expenses)):
            return
        expense = expenses[index]

        close_inline_panels()

        edit_panel = ttk.Frame(mand_frame)
        edit_panel.grid(row=2, column=0, columnspan=2, pady=6, sticky="ew")
        current_panel["edit"] = edit_panel
        edit_panel.grid_columnconfigure(1, weight=1)

        ttk.Label(edit_panel, text="Amount KZT:").grid(row=0, column=0, sticky="w")
        amount_kzt_entry = ttk.Entry(edit_panel)
        amount_kzt_entry.insert(0, str(expense.amount_kzt))
        amount_kzt_entry.grid(row=0, column=1)

        ttk.Label(edit_panel, text="Wallet:").grid(row=1, column=0, sticky="w")
        edit_wallet_var = tk.StringVar(value="")
        edit_wallet_menu = ttk.OptionMenu(edit_panel, edit_wallet_var, "")
        edit_wallet_menu.grid(row=1, column=1, sticky="ew")
        edit_wallet_map: dict[str, int] = {
            f"[{wallet.id}] {wallet.name} ({wallet.currency})": wallet.id
            for wallet in context.controller.load_active_wallets()
        }
        edit_wallet_labels = list(edit_wallet_map.keys()) or [""]
        wallet_menu = edit_wallet_menu["menu"]
        wallet_menu.delete(0, "end")
        for label in edit_wallet_labels:
            wallet_menu.add_command(
                label=label, command=lambda value=label: edit_wallet_var.set(value)
            )
        current_wallet_label = next(
            (label for label, wid in edit_wallet_map.items() if int(wid) == int(expense.wallet_id)),
            edit_wallet_labels[0],
        )
        edit_wallet_var.set(current_wallet_label)

        ttk.Label(edit_panel, text="Period:").grid(row=2, column=0, sticky="w")
        edit_period_var = tk.StringVar(value=str(expense.period or "monthly"))
        ttk.OptionMenu(
            edit_panel,
            edit_period_var,
            str(expense.period or "monthly"),
            "daily",
            "weekly",
            "monthly",
            "yearly",
        ).grid(row=2, column=1, sticky="ew")

        ttk.Label(edit_panel, text="Date (YYYY-MM-DD, optional):").grid(row=3, column=0, sticky="w")
        date_entry = ttk.Entry(edit_panel)
        date_entry.insert(
            0,
            expense.date.isoformat()
            if hasattr(expense.date, "isoformat")
            else str(expense.date or ""),
        )
        date_entry.grid(row=3, column=1)

        def save_edit() -> None:
            expense_id = int(expense.id)
            raw_amount = amount_kzt_entry.get().strip()
            current_amount = str(expense.amount_kzt)
            if raw_amount != current_amount:
                try:
                    context.controller.update_mandatory_expense_amount_kzt(
                        expense_id, float(raw_amount)
                    )
                except ValueError as error:
                    messagebox.showerror("Amount error", str(error))
                    return

            new_wallet_id = edit_wallet_map.get(edit_wallet_var.get())
            if new_wallet_id is None:
                messagebox.showerror("Error", "Wallet is required.")
                return
            if int(new_wallet_id) != int(expense.wallet_id):
                try:
                    context.controller.update_mandatory_expense_wallet_id(
                        expense_id, int(new_wallet_id)
                    )
                except ValueError as error:
                    messagebox.showerror("Wallet error", str(error))
                    return

            new_period = str(edit_period_var.get() or "").strip().lower()
            if new_period and str(new_period) != str(expense.period):
                try:
                    context.controller.update_mandatory_expense_period(expense_id, new_period)
                except ValueError as error:
                    messagebox.showerror("Period error", str(error))
                    return

            current_date = (
                expense.date.isoformat()
                if hasattr(expense.date, "isoformat")
                else str(expense.date or "")
            )
            new_date = date_entry.get().strip()
            if new_date != current_date:
                try:
                    context.controller.update_mandatory_expense_date(expense_id, new_date)
                except ValueError as error:
                    messagebox.showerror("Date error", str(error))
                    return

            safe_destroy(edit_panel)
            current_panel["edit"] = None
            refresh_mandatory()
            context._refresh_charts()
            context._refresh_budgets()
            messagebox.showinfo("Success", "Mandatory expense updated.")

        def cancel_edit() -> None:
            try:
                safe_destroy(edit_panel)
            finally:
                current_panel["edit"] = None

        ttk.Button(edit_panel, text="Save", command=lambda: save_edit()).grid(
            row=4, column=0, padx=6
        )
        ttk.Button(edit_panel, text="Cancel", command=cancel_edit).grid(row=4, column=1, padx=6)

    def add_to_records_inline() -> None:
        selection = mand_tree.selection()
        if not selection:
            selection = mand_tree.selection()
            messagebox.showerror("Error", "Select a required expense to add to records.")
            return
        close_inline_panels()

        add_to_report_panel = tk.Frame(mand_frame)
        add_to_report_panel.grid(row=2, column=0, columnspan=2, pady=6, sticky="ew")
        current_panel["report"] = add_to_report_panel

        ttk.Label(add_to_report_panel, text="Date (YYYY-MM-DD):").grid(row=0, column=0, sticky="w")
        date_entry = ttk.Entry(add_to_report_panel)
        date_entry.grid(row=0, column=1)

        ttk.Label(add_to_report_panel, text="Wallet:").grid(row=1, column=0, sticky="w")
        mandatory_wallet_var = tk.StringVar(value="")
        mandatory_wallet_menu = ttk.OptionMenu(add_to_report_panel, mandatory_wallet_var, "")
        mandatory_wallet_menu.grid(row=1, column=1, sticky="ew")

        mandatory_wallet_map: dict[str, int] = {
            f"[{wallet.id}] {wallet.name} ({wallet.currency})": wallet.id
            for wallet in context.controller.load_active_wallets()
        }
        wallet_labels = list(mandatory_wallet_map.keys()) or [""]
        wallet_menu = mandatory_wallet_menu["menu"]
        wallet_menu.delete(0, "end")
        for label in wallet_labels:
            wallet_menu.add_command(
                label=label, command=lambda value=label: mandatory_wallet_var.set(value)
            )
        mandatory_wallet_var.set(wallet_labels[0])

        selection = mand_tree.selection()
        if selection:
            try:
                index = int(selection[0])
            except Exception:
                index = -1
        else:
            index = -1

        def save() -> None:
            try:
                from domain.validation import ensure_not_future, parse_ymd

                date_value = date_entry.get()
                entered_date = parse_ymd(date_value)
                ensure_not_future(entered_date)
                wallet_id = mandatory_wallet_map.get(mandatory_wallet_var.get())
                if wallet_id is None:
                    messagebox.showerror("Error", "Wallet is required.")
                    return

                context.controller.add_mandatory_to_report(index, date_value, wallet_id)
                messagebox.showinfo(
                    "Success", f"Mandatory expense added to report for {date_value}."
                )
                safe_destroy(add_to_report_panel)
                current_panel["report"] = None
                refresh_mandatory()
                refresh_wallets()
                context._refresh_list()
                context._refresh_charts()
                context._refresh_budgets()
                context._refresh_all()
            except ValueError as error:
                messagebox.showerror("Error", f"Invalid date: {str(error)}. Use YYYY-MM-DD.")

        def cancel() -> None:
            try:
                safe_destroy(add_to_report_panel)
            finally:
                current_panel["report"] = None

        ttk.Button(add_to_report_panel, text="Save", command=save).grid(row=2, column=0, padx=6)
        ttk.Button(add_to_report_panel, text="Cancel", command=cancel).grid(row=2, column=1, padx=6)

    def delete_mandatory() -> None:
        selection = mand_tree.selection()
        if not selection:
            messagebox.showerror("Error", "Select mandatory expense to delete.")
            return
        try:
            index = int(selection[0])
        except Exception:
            messagebox.showerror("Error", "Invalid selection.")
            return
        if context.controller.delete_mandatory_expense(index):
            messagebox.showinfo("Success", "Mandatory expense deleted.")
            refresh_mandatory()
        else:
            messagebox.showerror("Error", "Failed to delete mandatory expense.")

    def delete_all_mandatory() -> None:
        if not messagebox.askyesno(
            "Confirm Delete All",
            "Delete ALL mandatory expenses? This action cannot be undone.",
        ):
            return
        context.controller.delete_all_mandatory_expenses()
        messagebox.showinfo("Success", "All mandatory expenses deleted.")
        refresh_mandatory()

    actions = ttk.Frame(mand_frame)
    actions.grid(row=1, column=0, columnspan=2, sticky="ew", padx=pad_x, pady=(0, pad_y))

    format_var = tk.StringVar(value="CSV")

    ttk.Button(actions, text="Add", command=add_mandatory_inline).grid(row=0, column=0)
    ttk.Button(actions, text="Edit", command=edit_mandatory_inline).grid(row=0, column=1, padx=6)
    ttk.Button(actions, text="Add to Records", command=add_to_records_inline).grid(
        row=0, column=2, padx=6
    )
    ttk.Button(actions, text="Delete", command=delete_mandatory).grid(row=0, column=3)
    ttk.Button(actions, text="Delete All", command=delete_all_mandatory).grid(
        row=0, column=4, padx=6
    )
    ttk.Button(actions, text="Refresh", command=refresh_mandatory).grid(row=0, column=5, padx=6)
    ttk.OptionMenu(actions, format_var, "CSV", "CSV", "XLSX").grid(row=0, column=6, padx=6)

    def import_mand() -> None:
        fmt = format_var.get()
        cfg = import_formats.get(fmt)
        if not cfg:
            messagebox.showerror("Error", f"Unsupported format: {fmt}")
            return

        filepath = filedialog.askopenfilename(
            defaultextension=cfg["ext"],
            filetypes=[(f"{cfg['desc']} files", f"*{cfg['ext']}"), ("All files", "*.*")],
            title=f"Select {cfg['desc']} file to import mandatory expenses",
        )
        if not filepath:
            return

        if not messagebox.askyesno(
            "Confirm Import",
            "This will replace all existing mandatory expenses with data from:\n"
            f"{filepath}\n\nContinue?",
        ):
            return

        def task() -> ImportResult:
            return context.controller.import_mandatory(fmt, filepath)

        def on_success(result: ImportResult) -> None:
            details = ""
            if result.skipped:
                details = f"\nSkipped: {result.skipped} rows.\nFirst errors:\n- " + "\n- ".join(
                    result.errors[:5]
                )

            messagebox.showinfo(
                "Success",
                f"Successfully imported {result.imported} "
                f"mandatory expenses from {cfg['desc']} file."
                "\nAll existing mandatory expenses have been replaced." + details,
            )
            refresh_mandatory()

        def on_error(exc: BaseException) -> None:
            if isinstance(exc, FileNotFoundError):
                messagebox.showerror("Error", f"File not found: {filepath}")
                return
            messagebox.showerror("Error", f"Failed to import {fmt}: {str(exc)}")

        context._run_background(
            task,
            on_success=on_success,
            on_error=on_error,
            busy_message=f"Importing {cfg['desc']} mandatory expenses...",
        )

    def export_mand() -> None:
        fmt = format_var.get()
        expenses = context.controller.load_mandatory_expenses()
        if not expenses:
            messagebox.showinfo("No Expenses", "No mandatory expenses to export.")
            return

        filepath = filedialog.asksaveasfilename(
            defaultextension=f".{fmt.lower()}",
            title="Save Mandatory Expenses",
        )
        if not filepath:
            return

        def task() -> None:
            from gui.exporters import export_mandatory_expenses

            export_mandatory_expenses(expenses, filepath, fmt.lower())

        def on_success(_: Any) -> None:
            messagebox.showinfo("Success", f"Mandatory expenses exported to {filepath}")
            open_in_file_manager(os.path.dirname(filepath))

        context._run_background(
            task,
            on_success=on_success,
            busy_message=f"Exporting {fmt} mandatory expenses...",
        )

    ttk.Button(actions, text="Import", command=import_mand).grid(row=0, column=7)
    ttk.Button(actions, text="Export", command=export_mand).grid(row=0, column=8)

    backup_frame = ttk.LabelFrame(left_panel, text="Backup (JSON)")
    backup_frame.grid(row=2, column=0, sticky="ew")
    backup_frame.grid_columnconfigure(0, weight=1)
    backup_frame.grid_columnconfigure(1, weight=1)

    def import_backup() -> None:
        filepath = filedialog.askopenfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            title="Import Full Backup",
        )
        if not filepath:
            return

        if not messagebox.askyesno(
            "Confirm Backup Import",
            "This will replace all wallets, records, transfers, mandatory expenses, budgets, "
            "and distribution data. Continue?",
        ):
            return

        def task(force: bool) -> ImportResult:
            return context.controller.import_records(
                "JSON",
                filepath,
                ImportPolicy.FULL_BACKUP,
                force=force,
            )

        def on_success(result: ImportResult) -> None:
            details = ""
            if result.skipped:
                details = f"\nSkipped: {result.skipped}\n- " + "\n- ".join(result.errors[:5])
            messagebox.showinfo(
                "Success", f"Backup imported. Imported entities: {result.imported}.{details}"
            )
            refresh_mandatory()
            refresh_wallets()
            context._refresh_list()
            context._refresh_charts()
            context._refresh_budgets()
            context._refresh_all()

        def run_import(force: bool) -> None:
            def current_task() -> ImportResult:
                return task(force)

            def on_error(exc: BaseException) -> None:
                try:
                    from utils.backup_utils import BackupReadonlyError

                    is_readonly = isinstance(exc, BackupReadonlyError)
                except ImportError:
                    is_readonly = False

                if is_readonly and not force:
                    if messagebox.askyesno(
                        "Readonly Snapshot",
                        "Backup is readonly snapshot. Import with force override?",
                    ):
                        run_import(True)
                    return
                messagebox.showerror("Error", f"Failed to import backup: {str(exc)}")

            context._run_background(
                current_task,
                on_success=on_success,
                on_error=on_error,
                busy_message="Importing full backup...",
            )

        run_import(False)

    def export_backup() -> None:
        filepath = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            title="Export Full Backup",
        )
        if not filepath:
            return

        wallets = context.repository.load_wallets()
        records = context.repository.load_all()
        mandatory_expenses = context.repository.load_mandatory_expenses()
        budgets = context.controller.get_budgets()
        debts = context.controller.get_debts()
        debt_payments = []
        for debt in debts:
            debt_payments.extend(context.controller.get_debt_history(debt.id))
        assets = context.controller.get_assets(active_only=False)
        asset_snapshots = []
        for asset in assets:
            asset_snapshots.extend(context.controller.get_asset_history(asset.id))
        goals = context.controller.get_goals()
        distribution_items, distribution_subitems_by_item = (
            context.controller.export_distribution_structure()
        )
        distribution_subitems = [
            subitem
            for item_id in sorted(distribution_subitems_by_item)
            for subitem in distribution_subitems_by_item[item_id]
        ]
        distribution_snapshots = context.controller.get_frozen_distribution_rows()
        transfers = context.repository.load_transfers()

        def task() -> None:
            from gui.exporters import export_full_backup

            export_full_backup(
                filepath,
                wallets=wallets,
                records=records,
                mandatory_expenses=mandatory_expenses,
                budgets=budgets,
                debts=debts,
                debt_payments=debt_payments,
                assets=assets,
                asset_snapshots=asset_snapshots,
                goals=goals,
                distribution_items=distribution_items,
                distribution_subitems=distribution_subitems,
                distribution_snapshots=distribution_snapshots,
                transfers=transfers,
                storage_mode="sqlite",
            )

        def on_success(_: Any) -> None:
            messagebox.showinfo("Success", f"Full backup exported to {filepath}")
            open_in_file_manager(os.path.dirname(filepath))

        context._run_background(
            task,
            on_success=on_success,
            busy_message="Exporting full backup...",
        )

    ttk.Button(backup_frame, text="Export Full Backup", command=export_backup).grid(
        row=0,
        column=0,
        sticky="ew",
        padx=pad_x,
        pady=pad_y,
    )
    ttk.Button(backup_frame, text="Import Full Backup", command=import_backup).grid(
        row=0,
        column=1,
        sticky="ew",
        padx=pad_x,
        pady=pad_y,
    )

    audit_frame = ttk.LabelFrame(left_panel, text="Finance Audit")
    audit_frame.grid(row=3, column=0, sticky="ew", pady=(10, 0))
    audit_frame.grid_columnconfigure(0, weight=1)

    def _on_run_audit() -> None:
        try:
            report = context.controller.run_audit()
            show_audit_report_dialog(report, parent)
        except Exception as error:
            messagebox.showerror("Audit Error", str(error))

    ttk.Button(audit_frame, text="Run Audit", command=_on_run_audit).grid(
        row=0,
        column=0,
        sticky="ew",
        padx=pad_x,
        pady=pad_y,
    )

    refresh_mandatory()
