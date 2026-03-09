from __future__ import annotations

import os
import tkinter as tk
from collections.abc import Callable
from tkinter import Listbox, filedialog, messagebox, scrolledtext, ttk
from typing import Any, Protocol

from domain.audit import AuditFinding, AuditReport
from domain.import_policy import ImportPolicy
from domain.import_result import ImportResult
from gui.helpers import open_in_file_manager


class SettingsTabContext(Protocol):
    controller: Any
    repository: Any
    refresh_operation_wallet_menu: Callable[[], None] | None
    refresh_transfer_wallet_menus: Callable[[], None] | None

    def _refresh_list(self) -> None: ...

    def _refresh_charts(self) -> None: ...

    def _run_background(
        self,
        task: Callable[[], Any],
        *,
        on_success: Callable[[Any], None],
        on_error: Callable[[BaseException], None] | None = None,
        busy_message: str = "Processing...",
    ) -> None: ...


def _format_audit_finding(finding: AuditFinding, *, passed: bool = False) -> str:
    suffix = f" — {finding.detail}" if finding.detail else ""
    prefix = "✔ " if passed else ""
    return f"{prefix}[{finding.check}] {finding.message}{suffix}"


def _populate_audit_section(
    widget: scrolledtext.ScrolledText,
    findings: tuple[AuditFinding, ...],
    *,
    passed: bool = False,
    background: str | None = None,
) -> None:
    if background is not None:
        widget.configure(background=background)
    widget.configure(state="normal")
    widget.delete("1.0", tk.END)
    if findings:
        lines = [_format_audit_finding(finding, passed=passed) for finding in findings]
        widget.insert("1.0", "\n".join(lines))
    else:
        widget.insert("1.0", "(none)")
    widget.configure(state="disabled")


def show_audit_report_dialog(report: AuditReport, parent: tk.Misc) -> None:
    dialog = tk.Toplevel(parent)
    dialog.title("Data Audit Report")
    dialog.minsize(560, 480)
    dialog.transient(parent.winfo_toplevel())

    frame = ttk.Frame(dialog, padding=12)
    frame.pack(fill="both", expand=True)
    frame.grid_columnconfigure(0, weight=1)
    frame.grid_rowconfigure(3, weight=1)
    frame.grid_rowconfigure(4, weight=1)
    frame.grid_rowconfigure(5, weight=1)

    ttk.Label(frame, text=f"Database: {os.path.basename(report.db_path)}").grid(
        row=0, column=0, sticky="w"
    )
    ttk.Label(frame, text=report.summary()).grid(row=1, column=0, sticky="w", pady=(4, 10))

    errors_frame = ttk.LabelFrame(frame, text=f"Errors ({len(report.errors)})")
    errors_frame.grid(row=3, column=0, sticky="nsew", pady=(0, 8))
    errors_frame.grid_columnconfigure(0, weight=1)
    errors_frame.grid_rowconfigure(0, weight=1)

    warnings_frame = ttk.LabelFrame(frame, text=f"Warnings ({len(report.warnings)})")
    warnings_frame.grid(row=4, column=0, sticky="nsew", pady=(0, 8))
    warnings_frame.grid_columnconfigure(0, weight=1)
    warnings_frame.grid_rowconfigure(0, weight=1)

    passed_frame = ttk.LabelFrame(frame, text=f"Passed ({len(report.passed)})")
    passed_frame.grid(row=5, column=0, sticky="nsew", pady=(0, 10))
    passed_frame.grid_columnconfigure(0, weight=1)
    passed_frame.grid_rowconfigure(0, weight=1)

    errors_text = scrolledtext.ScrolledText(errors_frame, height=7, wrap="word")
    errors_text.grid(row=0, column=0, sticky="nsew")
    warnings_text = scrolledtext.ScrolledText(warnings_frame, height=7, wrap="word")
    warnings_text.grid(row=0, column=0, sticky="nsew")
    passed_text = scrolledtext.ScrolledText(passed_frame, height=8, wrap="word")
    passed_text.grid(row=0, column=0, sticky="nsew")

    _populate_audit_section(
        errors_text,
        report.errors,
        background="#ffe6e6" if report.errors else None,
    )
    _populate_audit_section(
        warnings_text,
        report.warnings,
        background="#fff9e6" if report.warnings else None,
    )
    _populate_audit_section(
        passed_text,
        report.passed,
        passed=True,
        background="#e6f9e6" if report.is_clean else None,
    )

    close_button = ttk.Button(frame, text="Close", command=dialog.destroy)
    close_button.grid(row=6, column=0, sticky="e")

    dialog.update_idletasks()
    root = parent.winfo_toplevel()
    root_x = root.winfo_rootx()
    root_y = root.winfo_rooty()
    root_w = root.winfo_width()
    root_h = root.winfo_height()
    dialog_w = max(dialog.winfo_width(), 560)
    dialog_h = max(dialog.winfo_height(), 480)
    pos_x = root_x + max((root_w - dialog_w) // 2, 0)
    pos_y = root_y + max((root_h - dialog_h) // 2, 0)
    dialog.geometry(f"{dialog_w}x{dialog_h}+{pos_x}+{pos_y}")
    dialog.grab_set()
    close_button.focus_set()


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

    wallet_listbox = Listbox(list_frame, height=8)
    wallet_listbox.grid(row=0, column=0, sticky="nsew")

    wallet_scroll = ttk.Scrollbar(list_frame, orient="vertical", command=wallet_listbox.yview)
    wallet_scroll.grid(row=0, column=1, sticky="ns")
    wallet_listbox.config(yscrollcommand=wallet_scroll.set)

    def refresh_wallets() -> None:
        wallet_listbox.delete(0, tk.END)
        for wallet in context.controller.load_wallets():
            try:
                balance = context.controller.wallet_balance(wallet.id)
            except Exception:
                balance = wallet.initial_balance
            wallet_listbox.insert(
                tk.END,
                f"[{wallet.id}] {wallet.name} | {wallet.currency} | "
                f"Initial={wallet.initial_balance:.2f} | Balance={balance:.2f} | "
                f"allow_negative={wallet.allow_negative} | active={wallet.is_active}",
            )

        if context.refresh_transfer_wallet_menus is not None:
            try:
                context.refresh_transfer_wallet_menus()
            except Exception:
                pass

        if context.refresh_operation_wallet_menu is not None:
            try:
                context.refresh_operation_wallet_menu()
            except Exception:
                pass

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
            context._refresh_charts()
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
        selection = wallet_listbox.curselection()
        if not selection:
            messagebox.showerror("Error", "Select wallet to delete.")
            return
        row = wallet_listbox.get(selection[0])
        try:
            wallet_id = int(row.split("]")[0].strip().lstrip("["))
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

    mand_listbox = tk.Listbox(mand_frame)
    mand_listbox.grid(row=0, column=0, sticky="nsew", padx=pad_x, pady=pad_y)

    mand_scroll = ttk.Scrollbar(mand_frame, orient="vertical", command=mand_listbox.yview)
    mand_scroll.grid(row=0, column=1, sticky="ns", pady=pad_y)
    mand_listbox.config(yscrollcommand=mand_scroll.set)

    def refresh_mandatory() -> None:
        mand_listbox.delete(0, tk.END)
        expenses = context.controller.load_mandatory_expenses()
        for idx, expense in enumerate(expenses):
            mand_listbox.insert(
                tk.END,
                f"[{idx}] {expense.amount_original:.2f} {expense.currency} "
                f"(={expense.amount_kzt:.2f} KZT) - {expense.category} - "
                f"{expense.description} ({expense.period})",
            )

    current_panel: dict[str, tk.Frame | None] = {"add": None, "report": None}

    def close_inline_panels() -> None:
        for key in ("add", "report"):
            panel = current_panel[key]
            if panel is not None:
                try:
                    panel.destroy()
                except Exception:
                    pass
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

        ttk.Label(add_panel, text="Category (default Mandatory):").grid(row=2, column=0, sticky="w")
        category_entry = ttk.Entry(add_panel)
        category_entry.insert(0, "Mandatory")
        category_entry.grid(row=2, column=1)

        ttk.Label(add_panel, text="Description:").grid(row=3, column=0, sticky="w")
        description_entry = ttk.Entry(add_panel)
        description_entry.grid(row=3, column=1)

        ttk.Label(add_panel, text="Period:").grid(row=4, column=0, sticky="w")
        period_var = tk.StringVar(value="monthly")
        ttk.OptionMenu(add_panel, period_var, "daily", "daily", "weekly", "monthly", "yearly").grid(
            row=4,
            column=1,
        )

        def save() -> None:
            try:
                amount = float(amount_entry.get())
                description = description_entry.get()
                if not description:
                    messagebox.showerror("Error", "Description is required.")
                    return
                context.controller.create_mandatory_expense(
                    amount=amount,
                    currency=(currency_entry.get() or "KZT").strip(),
                    category=(category_entry.get() or "Mandatory").strip(),
                    description=description,
                    period=period_var.get(),
                )
                messagebox.showinfo("Success", "Mandatory expense added.")
                add_panel.destroy()
                current_panel["add"] = None
                context._refresh_charts()
                refresh_mandatory()
            except Exception as error:
                messagebox.showerror("Error", f"Failed to add expense: {str(error)}")

        def cancel() -> None:
            try:
                add_panel.destroy()
            finally:
                current_panel["add"] = None

        ttk.Button(add_panel, text="Save", command=save).grid(row=5, column=0, padx=6)
        ttk.Button(add_panel, text="Cancel", command=cancel).grid(row=5, column=1, padx=6)

    def add_to_records_inline() -> None:
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

        selection = mand_listbox.curselection()
        index = selection[0] if selection else -1

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

                if context.controller.add_mandatory_to_report(index, date_value, wallet_id):
                    messagebox.showinfo(
                        "Success", f"Mandatory expense added to report for {date_value}."
                    )
                    add_to_report_panel.destroy()
                    current_panel["report"] = None
                    refresh_mandatory()
                    refresh_wallets()
                    context._refresh_list()
                    context._refresh_charts()
                else:
                    messagebox.showerror(
                        "Error",
                        "Please select a mandatory expense to add to records."
                        "\nThen click 'Add to Records' and try again.",
                    )
            except ValueError as error:
                messagebox.showerror("Error", f"Invalid date: {str(error)}. Use YYYY-MM-DD.")

        def cancel() -> None:
            try:
                add_to_report_panel.destroy()
            finally:
                current_panel["report"] = None

        ttk.Button(add_to_report_panel, text="Save", command=save).grid(row=2, column=0, padx=6)
        ttk.Button(add_to_report_panel, text="Cancel", command=cancel).grid(row=2, column=1, padx=6)

    def delete_mandatory() -> None:
        selection = mand_listbox.curselection()
        if not selection:
            messagebox.showerror("Error", "Select mandatory expense to delete.")
            return
        index = selection[0]
        if context.controller.delete_mandatory_expense(index):
            messagebox.showinfo("Success", "Mandatory expense deleted.")
            refresh_mandatory()
            context._refresh_charts()
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
        context._refresh_charts()

    actions = ttk.Frame(mand_frame)
    actions.grid(row=1, column=0, columnspan=2, sticky="ew", padx=pad_x, pady=(0, pad_y))

    format_var = tk.StringVar(value="CSV")

    ttk.Button(actions, text="Add", command=add_mandatory_inline).grid(row=0, column=0)
    ttk.Button(actions, text="Add to Records", command=add_to_records_inline).grid(
        row=0, column=1, padx=6
    )
    ttk.Button(actions, text="Delete", command=delete_mandatory).grid(row=0, column=2)
    ttk.Button(actions, text="Delete All", command=delete_all_mandatory).grid(
        row=0, column=3, padx=6
    )
    ttk.Button(actions, text="Refresh", command=refresh_mandatory).grid(row=0, column=4, padx=6)
    ttk.OptionMenu(actions, format_var, "CSV", "CSV", "XLSX").grid(row=0, column=5, padx=6)

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
            context._refresh_charts()

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

    ttk.Button(actions, text="Import", command=import_mand).grid(row=0, column=6)
    ttk.Button(actions, text="Export", command=export_mand).grid(row=0, column=7)

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
            "This will replace all wallets, records, transfers and mandatory expenses. Continue?",
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
            context._refresh_list()
            context._refresh_charts()

        def run_import(force: bool) -> None:
            def current_task() -> ImportResult:
                return task(force)

            def on_error(exc: BaseException) -> None:
                try:
                    from utils.backup_utils import BackupReadonlyError

                    is_readonly = isinstance(exc, BackupReadonlyError)
                except Exception:
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
        transfers = context.repository.load_transfers()

        def task() -> None:
            from gui.exporters import export_full_backup

            export_full_backup(
                filepath,
                wallets=wallets,
                records=records,
                mandatory_expenses=mandatory_expenses,
                transfers=transfers,
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
