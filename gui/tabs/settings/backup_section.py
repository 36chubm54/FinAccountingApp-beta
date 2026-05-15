from __future__ import annotations

import os
import tkinter as tk
from collections.abc import Callable
from tkinter import filedialog, ttk
from typing import Any

from domain.import_policy import ImportPolicy
from domain.import_result import ImportResult
from gui.helpers import open_in_file_manager
from gui.i18n import tr
from gui.ui_dialogs import messagebox_compat as messagebox
from gui.ui_theme import PAD_SM, PAD_XS, create_card_section

from .wallets_section import MessageBoxLike


def build_backup_section(
    left_panel: tk.Frame | ttk.Frame,
    *,
    parent: tk.Frame | ttk.Frame,
    context: Any,
    refresh_wallets: Callable[[], None],
    messagebox_module: MessageBoxLike = messagebox,
    row_index: int = 2,
) -> None:
    pad_x = PAD_SM
    pad_y = PAD_XS

    backup_card = create_card_section(left_panel, tr("settings.backup", "Резервная копия (JSON)"))
    backup_card.grid(row=row_index, column=0, sticky="ew")
    backup_frame = backup_card.winfo_children()[-1]
    backup_frame.grid_columnconfigure(0, weight=1)
    backup_frame.grid_columnconfigure(1, weight=1)

    def _refresh_mandatory_if_available() -> None:
        refresh_mandatory = getattr(context, "refresh_mandatory", None)
        if callable(refresh_mandatory):
            refresh_mandatory()

    def import_backup() -> None:
        filepath = filedialog.askopenfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            title=tr("settings.backup.import.title", "Импорт полной копии"),
        )
        if not filepath:
            return

        if not messagebox_module.askyesno(
            tr("common.confirm", "Подтверждение"),
            tr(
                "settings.backup.import.confirm",
                "Это заменит все кошельки, записи, переводы, обязательные расходы, "
                "бюджеты и данные распределения. Продолжить?",
            ),
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
            messagebox_module.showinfo(
                tr("common.done", "Готово"),
                tr(
                    "settings.backup.import.success",
                    "Резервная копия импортирована. Импортировано сущностей: {count}.{details}",
                    count=result.imported,
                    details=details,
                ),
            )
            _refresh_mandatory_if_available()
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
                    if messagebox_module.askyesno(
                        tr("settings.backup.readonly.title", "Снимок только для чтения"),
                        tr(
                            "settings.backup.readonly.confirm",
                            "Резервная копия доступна только для чтения. "
                            "Импортировать с принудительным режимом?",
                        ),
                    ):
                        run_import(True)
                    return
                messagebox_module.showerror(
                    tr("common.error", "Ошибка"),
                    tr(
                        "settings.backup.import.error",
                        "Не удалось импортировать резервную копию: {error}",
                        error=exc,
                    ),
                )

            context._run_background(
                current_task,
                on_success=on_success,
                on_error=on_error,
                busy_message=tr("settings.backup.import.busy", "Импортируем полную копию..."),
            )

        run_import(False)

    def export_backup() -> None:
        filepath = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            title=tr("settings.backup.export.title", "Экспорт полной копии"),
        )
        if not filepath:
            return

        def task() -> None:
            from gui.exporters import export_full_backup

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
            messagebox_module.showinfo(
                tr("common.done", "Готово"),
                tr(
                    "settings.backup.export.success",
                    "Полная копия экспортирована в {filepath}",
                    filepath=filepath,
                ),
            )
            open_in_file_manager(os.path.dirname(filepath))

        context._run_background(
            task,
            on_success=on_success,
            busy_message=tr("settings.backup.export.busy", "Экспортируем полную копию..."),
        )

    ttk.Button(
        backup_frame,
        text=tr("settings.backup.export.button", "Экспорт полной копии"),
        command=export_backup,
    ).grid(row=0, column=0, sticky="ew", padx=pad_x, pady=pad_y)
    ttk.Button(
        backup_frame,
        text=tr("settings.backup.import.button", "Импорт полной копии"),
        command=import_backup,
    ).grid(row=0, column=1, sticky="ew", padx=pad_x, pady=pad_y)
