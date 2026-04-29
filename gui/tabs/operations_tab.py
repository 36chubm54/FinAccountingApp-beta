"""Operations tab — CRUD operations for financial records and transfers, import and export"""

from __future__ import annotations

import logging
import os
import tkinter as tk
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from tkinter import filedialog, ttk
from typing import Any, Protocol

from domain.errors import DomainError
from domain.import_policy import ImportPolicy
from domain.import_result import ImportResult
from gui.helpers import open_in_file_manager
from gui.i18n import tr
from gui.logging_utils import log_ui_error
from gui.tabs.operations_support import (
    refresh_operation_views,
    safe_destroy,
    show_import_preview_dialog,
)
from gui.ui_helpers import (
    ask_confirm,
    attach_treeview_scrollbars,
    show_error,
    show_info,
    show_warning,
)

logger = logging.getLogger(__name__)


class OperationsTabContext(Protocol):
    controller: Any
    repository: Any
    _record_id_to_repo_index: dict[str, int]
    _record_id_to_domain_id: dict[str, int]

    def _refresh_list(self) -> None: ...

    def _refresh_charts(self) -> None: ...

    def _refresh_wallets(self) -> None: ...

    def _refresh_budgets(self) -> None: ...

    def _refresh_all(self) -> None: ...

    def _run_background(
        self,
        task: Callable[[], Any],
        *,
        on_success: Callable[[Any], None],
        on_error: Callable[[BaseException], None] | None = None,
        busy_message: str = tr("app.busy.default", "Выполняется операция..."),
    ) -> None: ...

    def _import_policy_from_ui(self, mode_label: str) -> ImportPolicy: ...


@dataclass(slots=True)
class OperationsTabBindings:
    records_tree: ttk.Treeview
    refresh_operation_wallet_menu: Callable[[], None]
    refresh_transfer_wallet_menus: Callable[[], None]
    set_type_income: Callable[[], None]
    set_type_expense: Callable[[], None]
    save_record: Callable[[], None]
    select_first: Callable[[], None]
    select_last: Callable[[], None]
    delete_selected: Callable[[], None]
    delete_all: Callable[[], None]
    edit_selected: Callable[[], None]
    inline_editor_active: Callable[[], bool]


def build_operations_tab(
    parent: tk.Frame | ttk.Frame,
    context: OperationsTabContext,
    import_formats: dict[str, dict[str, str]],
) -> OperationsTabBindings:
    parent.grid_columnconfigure(0, weight=2, uniform="operations")
    parent.grid_columnconfigure(1, weight=5, uniform="operations")
    parent.grid_rowconfigure(0, weight=1)

    left_frame = ttk.Frame(parent)
    left_frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
    left_frame.grid_columnconfigure(0, weight=1)

    form_frame = ttk.LabelFrame(left_frame, text=tr("operations.new", "Новая операция"))
    form_frame.grid(row=0, column=0, sticky="ew", pady=(0, 10))
    form_frame.grid_columnconfigure(1, weight=1)

    income_label = tr("operations.type.income", "Доход")
    expense_label = tr("operations.type.expense", "Расход")
    ttk.Label(form_frame, text=tr("common.type", "Тип:")).grid(
        row=0, column=0, sticky="w", padx=6, pady=4
    )
    type_options = [income_label, expense_label]
    type_combo = ttk.Combobox(form_frame, values=type_options, state="readonly")
    type_combo.set(income_label)
    type_combo.grid(row=0, column=1, sticky="ew", padx=6, pady=4)

    ttk.Label(form_frame, text=tr("common.date", "Дата:")).grid(
        row=1, column=0, sticky="w", padx=6, pady=4
    )
    date_entry = ttk.Entry(form_frame)
    date_entry.grid(row=1, column=1, sticky="ew", padx=6, pady=4)
    date_entry.insert(0, date.today().isoformat())

    ttk.Label(form_frame, text=tr("common.amount", "Сумма:")).grid(
        row=2, column=0, sticky="w", padx=6, pady=4
    )
    amount_entry = ttk.Entry(form_frame)
    amount_entry.grid(row=2, column=1, sticky="ew", padx=6, pady=4)

    ttk.Label(form_frame, text=tr("common.currency", "Валюта:")).grid(
        row=3, column=0, sticky="w", padx=6, pady=4
    )
    currency_entry = ttk.Entry(form_frame)
    currency_entry.insert(0, "KZT")
    currency_entry.grid(row=3, column=1, sticky="ew", padx=6, pady=4)

    ttk.Label(form_frame, text=tr("common.category", "Категория:")).grid(
        row=4, column=0, sticky="w", padx=6, pady=4
    )
    category_combo = ttk.Combobox(form_frame, state="normal")
    category_combo.insert(0, "General")
    category_combo.grid(row=4, column=1, sticky="ew", padx=6, pady=4)

    ttk.Label(form_frame, text=tr("common.description", "Описание:")).grid(
        row=5, column=0, sticky="w", padx=6, pady=4
    )
    description_entry = ttk.Entry(form_frame)
    description_entry.grid(row=5, column=1, sticky="ew", padx=6, pady=4)

    ttk.Label(form_frame, text=tr("common.wallet", "Кошелек:")).grid(
        row=6, column=0, sticky="w", padx=6, pady=4
    )
    operation_wallet_var = tk.StringVar(value="")
    operation_wallet_menu = ttk.Combobox(
        form_frame,
        textvariable=operation_wallet_var,
        values=[],
        state="readonly",
    )
    operation_wallet_menu.grid(row=6, column=1, sticky="ew", padx=6, pady=4)
    operation_wallet_map: dict[str, int] = {}

    def _refresh_category_combo() -> None:
        try:
            if type_combo.get() == income_label:
                category_combo["values"] = context.controller.get_income_categories()
            else:
                category_combo["values"] = context.controller.get_expense_categories()
        except (ValueError, RuntimeError):
            pass
        category_combo.set("General")

    def _on_type_change(*_args: object) -> None:
        _refresh_category_combo()

    def _set_type_income() -> None:
        type_combo.set(income_label)
        _on_type_change()

    def _set_type_expense() -> None:
        type_combo.set(expense_label)
        _on_type_change()

    def refresh_operation_wallet_menu() -> None:
        nonlocal operation_wallet_map
        wallets = context.controller.load_active_wallets()
        operation_wallet_map = {
            f"[{wallet.id}] {wallet.name} ({wallet.currency})": wallet.id for wallet in wallets
        }
        labels = list(operation_wallet_map.keys()) or [""]
        operation_wallet_menu["values"] = labels
        if operation_wallet_var.get() not in operation_wallet_map:
            operation_wallet_var.set(labels[0])

    refresh_operation_wallet_menu()

    list_frame = ttk.LabelFrame(parent, text=tr("operations.journal", "Журнал операций"))
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
    for col, text, width, minwidth, stretch, anchor in (
        ("index", "#", 50, 50, False, "e"),
        ("date", tr("common.date", "Дата"), 100, 100, False, "w"),
        ("type", tr("common.type_short", "Тип"), 110, 110, False, "w"),
        ("category", tr("common.category_short", "Категория"), 180, 180, True, "w"),
        ("amount", tr("common.amount", "Сумма"), 90, 90, False, "e"),
        ("currency", tr("operations.currency_short", "Вал."), 60, 60, False, "center"),
        ("kzt", "KZT", 100, 90, False, "e"),
        ("wallets", tr("operations.wallets", "Кошельки"), 120, 110, False, "center"),
    ):
        records_tree.heading(col, text=text)
        records_tree.column(col, width=width, minwidth=minwidth, stretch=stretch, anchor=anchor)  # type: ignore[arg-type]
    records_tree.grid(row=0, column=0, sticky="nsew", padx=6, pady=6)

    attach_treeview_scrollbars(list_frame, records_tree, row=0, column=0, horizontal=True, pady=6)

    def save_record() -> None:
        date_str = date_entry.get().strip()
        if not date_str:
            show_error(tr("operations.error.date_required", "Укажите дату."))
            return
        try:
            from domain.validation import ensure_not_future, parse_ymd

            entered_date = parse_ymd(date_str)
            ensure_not_future(entered_date)
        except ValueError as error:
            show_error(
                tr(
                    "operations.error.invalid_date",
                    "Некорректная дата: {error}. Используйте формат ГГГГ-ММ-ДД.",
                    error=error,
                )
            )
            return

        amount_str = amount_entry.get().strip()
        if not amount_str:
            show_error(tr("operations.error.amount_required", "Укажите сумму."))
            return
        try:
            amount = float(amount_str)
        except ValueError:
            show_error(tr("operations.error.amount_number", "Сумма должна быть числом."))
            return

        currency = (currency_entry.get() or "KZT").strip()
        category = (category_combo.get() or "General").strip()
        description = description_entry.get().strip()
        wallet_id = operation_wallet_map.get(operation_wallet_var.get())
        if wallet_id is None:
            show_error(tr("operations.error.wallet_required", "Выберите кошелек."))
            return

        try:
            if type_combo.get() == income_label:
                context.controller.create_income(
                    date=date_str,
                    wallet_id=wallet_id,
                    amount=amount,
                    currency=currency,
                    category=category,
                    description=description,
                )
                show_info(tr("operations.save_success.income", "Доход успешно добавлен."))
            else:
                context.controller.create_expense(
                    date=date_str,
                    wallet_id=wallet_id,
                    amount=amount,
                    currency=currency,
                    category=category,
                    description=description,
                )
                show_info(tr("operations.save_success.expense", "Расход успешно добавлен."))

            amount_entry.delete(0, tk.END)
            category_combo.delete(0, tk.END)
            description_entry.delete(0, tk.END)
            _refresh_category_combo()
            refresh_operation_views(context)
        except (DomainError, ValueError, TypeError, RuntimeError) as error:
            log_ui_error(logger, "UI_OPS_CREATE_RECORD_FAILED", error, wallet_id=wallet_id)
            show_error(
                tr(
                    "operations.error.save_failed",
                    "Не удалось сохранить операцию: {error}",
                    error=error,
                )
            )

    def _bind_focus_navigation(
        widgets: list[tk.Misc],
        *,
        submit_action: Callable[[], None] | None = None,
    ) -> None:
        def _focus_relative(index: int) -> str:
            widgets[index % len(widgets)].focus_set()
            return "break"

        for index, widget in enumerate(widgets):
            widget.bind("<Up>", lambda _event, i=index - 1: _focus_relative(i), add="+")
            widget.bind("<Down>", lambda _event, i=index + 1: _focus_relative(i), add="+")
            if isinstance(widget, ttk.Button):
                widget.bind("<Left>", lambda _event, i=index - 1: _focus_relative(i), add="+")
                widget.bind("<Right>", lambda _event, i=index + 1: _focus_relative(i), add="+")
                widget.bind(
                    "<Return>", lambda _event: (_event.widget.invoke(), "break")[1], add="+"
                )
                widget.bind(
                    "<KP_Enter>", lambda _event: (_event.widget.invoke(), "break")[1], add="+"
                )
            elif callable(submit_action):
                widget.bind("<Return>", lambda _event: (submit_action(), "break")[1], add="+")
                widget.bind("<KP_Enter>", lambda _event: (submit_action(), "break")[1], add="+")

    creator_widgets = [
        date_entry,
        amount_entry,
        currency_entry,
        category_combo,
        description_entry,
        operation_wallet_menu,
    ]
    save_button = ttk.Button(
        form_frame,
        text=tr("common.save", "Сохранить"),
        style="Primary.TButton",
        command=save_record,
    )
    save_button.grid(row=7, column=0, columnspan=2, pady=8)
    _bind_focus_navigation([*creator_widgets, save_button], submit_action=save_record)

    def select_first_record() -> None:
        children = records_tree.get_children()
        if not children:
            return
        first = children[0]
        records_tree.selection_set(first)
        records_tree.focus(first)
        records_tree.see(first)

    def select_last_record() -> None:
        children = records_tree.get_children()
        if not children:
            return
        last = children[-1]
        records_tree.selection_set(last)
        records_tree.focus(last)
        records_tree.see(last)

    def delete_selected() -> None:
        selection = records_tree.selection()
        if not selection:
            show_error(tr("operations.error.select_first", "Сначала выберите запись."))
            return
        record_id = selection[0]
        repository_index = context._record_id_to_repo_index.get(record_id)
        if repository_index is None:
            show_error(tr("operations.error.unavailable", "Выбранная запись больше недоступна."))
            context._refresh_list()
            return
        try:
            transfer_id = context.controller.transfer_id_by_repository_index(repository_index)
            if transfer_id is not None:
                context.controller.delete_transfer(transfer_id)
                show_info(
                    tr("operations.transfer.deleted", "Перевод #{id} удален.", id=transfer_id)
                )
            elif context.controller.delete_record(repository_index):
                show_info(tr("operations.deleted", "Запись удалена."))
            else:
                show_error(tr("operations.error.delete_failed", "Не удалось удалить запись."))
                return
            refresh_operation_views(context)
            _refresh_category_combo()
        except (DomainError, ValueError, TypeError, RuntimeError) as error:
            log_ui_error(
                logger,
                "UI_OPS_DELETE_RECORD_FAILED",
                error,
                record_ui_id=record_id,
                repository_index=repository_index,
            )
            show_error(
                tr(
                    "operations.error.delete_failed_with_error",
                    "Не удалось удалить запись: {error}",
                    error=error,
                )
            )

    edit_panel_state: dict[str, Any] = {"panel": None}

    def inline_editor_active() -> bool:
        panel = edit_panel_state.get("panel")
        if panel is None:
            return False
        try:
            return bool(panel.winfo_exists())
        except (tk.TclError, RuntimeError, AttributeError):
            return False

    def edit_selected_record_inline() -> None:
        selection = records_tree.selection()
        if not selection:
            show_error(tr("operations.error.select_first", "Сначала выберите запись."))
            return

        ui_record_id = selection[0]
        domain_record_id = context._record_id_to_domain_id.get(ui_record_id)
        if domain_record_id is None:
            show_error(tr("operations.error.edit_forbidden", "Эту запись нельзя редактировать."))
            return

        try:
            record = context.controller.get_record_for_edit(domain_record_id)
        except (ValueError, TypeError, RuntimeError):
            show_error(
                tr(
                    "operations.error.edit_load_failed",
                    "Не удалось загрузить запись для редактирования.",
                )
            )
            return

        if record.transfer_id is not None:
            show_error(
                tr(
                    "operations.error.transfer_edit_forbidden",
                    "Записи, связанные с переводом, редактировать нельзя.",
                )
            )
            return
        if str(getattr(record, "category", "") or "").strip().lower() == "transfer":
            show_error(
                tr(
                    "operations.error.transfer_row_edit_forbidden",
                    "Строки перевода редактировать нельзя.",
                )
            )
            return

        if edit_panel_state["panel"] is not None:
            try:
                edit_panel_state["panel"].destroy()
            except (tk.TclError, RuntimeError):
                pass
            edit_panel_state["panel"] = None

        edit_panel = ttk.Frame(list_frame, style="InlinePanel.TFrame", padding=(8, 6))
        edit_panel.grid(row=3, column=0, columnspan=2, padx=6, sticky="ew")
        edit_panel_state["panel"] = edit_panel

        ttk.Label(edit_panel, text=tr("operations.edit.amount", "Сумма (KZT):")).grid(
            row=0, column=0, sticky="w"
        )
        amount_entry = ttk.Entry(edit_panel)
        amount_entry.grid(row=0, column=1, sticky="ew")
        ttk.Label(edit_panel, text=tr("common.date", "Дата:")).grid(row=1, column=0, sticky="w")
        date_edit_entry = ttk.Entry(edit_panel)
        date_edit_entry.grid(row=1, column=1, sticky="ew")
        ttk.Label(edit_panel, text=tr("common.wallet", "Кошелек:")).grid(
            row=2, column=0, sticky="w"
        )
        wallet_edit_var = tk.StringVar(value="")
        wallet_edit_menu = ttk.Combobox(
            edit_panel,
            textvariable=wallet_edit_var,
            values=[],
            state="readonly",
        )
        wallet_edit_menu.grid(row=2, column=1, sticky="ew")
        ttk.Label(edit_panel, text=tr("common.category", "Категория:")).grid(
            row=3, column=0, sticky="w"
        )
        category_edit_combo = ttk.Combobox(edit_panel, state="normal")
        category_edit_combo.grid(row=3, column=1, sticky="ew")
        ttk.Label(edit_panel, text=tr("common.description", "Описание:")).grid(
            row=4, column=0, sticky="w"
        )
        description_edit_entry = ttk.Entry(edit_panel)
        description_edit_entry.grid(row=4, column=1, sticky="ew")
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
        except (ValueError, RuntimeError):
            pass
        category_edit_combo.insert(0, str(record.category or ""))
        description_edit_entry.insert(0, str(record.description or ""))

        wallet_edit_map: dict[str, int] = {
            f"[{wallet.id}] {wallet.name} ({wallet.currency})": wallet.id
            for wallet in context.controller.load_wallets()
        }
        wallet_labels = list(wallet_edit_map.keys()) or [""]
        wallet_edit_menu["values"] = wallet_labels
        current_wallet_label = next(
            (label for label, wid in wallet_edit_map.items() if int(wid) == int(record.wallet_id)),
            wallet_labels[0],
        )
        wallet_edit_var.set(current_wallet_label)

        def save_edit() -> None:
            try:
                new_amount_kzt = float(amount_entry.get().strip())
            except ValueError:
                show_error(tr("operations.error.amount_number", "Сумма должна быть числом."))
                return
            new_date = date_edit_entry.get().strip()
            if not new_date:
                show_error(tr("operations.error.date_required", "Укажите дату."))
                return
            new_category = category_edit_combo.get().strip()
            if not new_category:
                show_error(tr("operations.error.category_required", "Укажите категорию."))
                return
            new_wallet_id = wallet_edit_map.get(wallet_edit_var.get())
            if new_wallet_id is None:
                show_error(tr("operations.error.wallet_required", "Выберите кошелек."))
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
                show_info(tr("operations.updated", "Запись обновлена."))
                refresh_operation_views(context)
                _refresh_category_combo()
                cancel_edit()
            except (DomainError, ValueError, TypeError, RuntimeError) as error:
                log_ui_error(
                    logger,
                    "UI_OPS_EDIT_RECORD_FAILED",
                    error,
                    record_id=domain_record_id,
                    new_wallet_id=new_wallet_id,
                )
                show_error(
                    tr(
                        "operations.error.update_failed",
                        "Не удалось обновить запись: {error}",
                        error=error,
                    )
                )

        def cancel_edit() -> None:
            if edit_panel_state["panel"] is not None:
                safe_destroy(edit_panel_state["panel"])
                edit_panel_state["panel"] = None

        edit_buttons = ttk.Frame(edit_panel, style="InlinePanel.TFrame")
        edit_buttons.grid(row=5, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        edit_buttons.grid_columnconfigure(0, weight=1)
        edit_buttons.grid_columnconfigure(1, weight=1)
        save_button = ttk.Button(
            edit_buttons,
            text=tr("common.save", "Сохранить"),
            style="Primary.TButton",
            command=save_edit,
        )
        save_button.grid(row=0, column=0, sticky="ew", padx=(0, 6))
        cancel_button = ttk.Button(
            edit_buttons, text=tr("common.cancel", "Отмена"), command=cancel_edit
        )
        cancel_button.grid(row=0, column=1, sticky="ew", padx=(6, 0))

        navigation_widgets: list[tk.Misc] = [
            amount_entry,
            date_edit_entry,
            wallet_edit_menu,
            category_edit_combo,
            description_edit_entry,
            save_button,
            cancel_button,
        ]

        def _focus_relative(index: int) -> str:
            navigation_widgets[index % len(navigation_widgets)].focus_set()
            return "break"

        def _bind_editor_navigation(widget: tk.Misc, index: int) -> None:
            widget.bind("<Up>", lambda _event, i=index - 1: _focus_relative(i), add="+")
            widget.bind("<Down>", lambda _event, i=index + 1: _focus_relative(i), add="+")
            if isinstance(widget, ttk.Button):
                widget.bind("<Left>", lambda _event, i=index - 1: _focus_relative(i), add="+")
                widget.bind("<Right>", lambda _event, i=index + 1: _focus_relative(i), add="+")
                widget.bind(
                    "<Return>", lambda _event: (_event.widget.invoke(), "break")[1], add="+"
                )
                widget.bind(
                    "<KP_Enter>", lambda _event: (_event.widget.invoke(), "break")[1], add="+"
                )
            else:
                widget.bind("<Return>", lambda _event: (save_edit(), "break")[1], add="+")
                widget.bind("<KP_Enter>", lambda _event: (save_edit(), "break")[1], add="+")
            widget.bind("<Escape>", lambda _event: (cancel_edit(), "break")[1], add="+")

        for index, widget in enumerate(navigation_widgets):
            _bind_editor_navigation(widget, index)

        amount_entry.focus_set()

    def delete_all() -> None:
        confirm = ask_confirm(
            tr(
                "operations.delete_all.confirm",
                "Удалить все записи? Это действие нельзя отменить.",
            ),
            title=tr("operations.delete_all.title", "Подтвердите удаление"),
        )
        if confirm:
            context.controller.delete_all_records()
            show_info(tr("operations.deleted_all_done", "Все записи удалены."))
            refresh_operation_views(context)
            _refresh_category_combo()

    wallet_id_map: dict[str, int] = {}

    transfer_frame = ttk.LabelFrame(
        left_frame,
        text=tr("operations.transfer", "Перевод между кошельками"),
    )
    transfer_frame.grid(row=1, column=0, sticky="ew")
    transfer_frame.grid_columnconfigure(1, weight=1)

    ttk.Label(transfer_frame, text=tr("operations.transfer.from", "Из кошелька:")).grid(
        row=0, column=0, sticky="w", padx=4, pady=2
    )
    transfer_from_var = tk.StringVar(value="")
    transfer_from_menu = ttk.Combobox(
        transfer_frame,
        textvariable=transfer_from_var,
        values=[],
        state="readonly",
    )
    transfer_from_menu.grid(row=0, column=1, sticky="ew", padx=4, pady=2)

    ttk.Label(transfer_frame, text=tr("operations.transfer.to", "В кошелек:")).grid(
        row=1, column=0, sticky="w", padx=4, pady=2
    )
    transfer_to_var = tk.StringVar(value="")
    transfer_to_menu = ttk.Combobox(
        transfer_frame,
        textvariable=transfer_to_var,
        values=[],
        state="readonly",
    )
    transfer_to_menu.grid(row=1, column=1, sticky="ew", padx=4, pady=2)

    ttk.Label(transfer_frame, text=tr("common.date", "Дата:")).grid(
        row=2, column=0, sticky="w", padx=4, pady=2
    )
    transfer_date_entry = ttk.Entry(transfer_frame)
    transfer_date_entry.grid(row=2, column=1, sticky="ew", padx=4, pady=2)
    transfer_date_entry.insert(0, date.today().isoformat())

    ttk.Label(transfer_frame, text=tr("common.amount", "Сумма:")).grid(
        row=3, column=0, sticky="w", padx=4, pady=2
    )
    transfer_amount_entry = ttk.Entry(transfer_frame)
    transfer_amount_entry.grid(row=3, column=1, sticky="ew", padx=4, pady=2)

    ttk.Label(transfer_frame, text=tr("common.currency", "Валюта:")).grid(
        row=4, column=0, sticky="w", padx=4, pady=2
    )
    transfer_currency_entry = ttk.Entry(transfer_frame)
    transfer_currency_entry.insert(0, "KZT")
    transfer_currency_entry.grid(row=4, column=1, sticky="ew", padx=4, pady=2)

    ttk.Label(transfer_frame, text=tr("operations.transfer.commission", "Комиссия:")).grid(
        row=5, column=0, sticky="w", padx=4, pady=2
    )
    transfer_commission_entry = ttk.Entry(transfer_frame)
    transfer_commission_entry.insert(0, "0")
    transfer_commission_entry.grid(row=5, column=1, sticky="ew", padx=4, pady=2)

    ttk.Label(
        transfer_frame, text=tr("operations.transfer.commission_currency", "Валюта комиссии:")
    ).grid(row=6, column=0, sticky="w", padx=4, pady=2)
    transfer_commission_currency_entry = ttk.Entry(transfer_frame)
    transfer_commission_currency_entry.insert(0, "KZT")
    transfer_commission_currency_entry.grid(row=6, column=1, sticky="ew", padx=4, pady=2)

    ttk.Label(transfer_frame, text=tr("common.description", "Описание:")).grid(
        row=7, column=0, sticky="w", padx=4, pady=2
    )
    transfer_description_entry = ttk.Entry(transfer_frame)
    transfer_description_entry.grid(row=7, column=1, sticky="ew", padx=4, pady=2)

    def refresh_transfer_wallet_menus() -> None:
        nonlocal wallet_id_map
        wallets = context.controller.load_active_wallets()
        wallet_id_map = {
            f"[{wallet.id}] {wallet.name} ({wallet.currency})": wallet.id for wallet in wallets
        }
        labels = list(wallet_id_map.keys()) or [""]

        for combo_widget, var in (
            (transfer_from_menu, transfer_from_var),
            (transfer_to_menu, transfer_to_var),
        ):
            combo_widget["values"] = labels
            if not var.get() or var.get() not in wallet_id_map:
                var.set(labels[0])

        if len(labels) > 1 and transfer_to_var.get() == transfer_from_var.get():
            transfer_to_var.set(labels[1])

    def create_transfer() -> None:
        from_wallet_id = wallet_id_map.get(transfer_from_var.get())
        to_wallet_id = wallet_id_map.get(transfer_to_var.get())
        if from_wallet_id is None or to_wallet_id is None:
            show_error(
                tr(
                    "operations.transfer.error.wallets_required",
                    "Выберите кошелек отправителя и получателя.",
                )
            )
            return

        date_str = transfer_date_entry.get().strip()
        if not date_str:
            show_error(tr("operations.transfer.error.date_required", "Укажите дату перевода."))
            return
        try:
            from domain.validation import ensure_not_future, parse_ymd

            entered_date = parse_ymd(date_str)
            ensure_not_future(entered_date)
        except ValueError as error:
            show_error(
                tr(
                    "operations.error.invalid_date",
                    "Некорректная дата: {error}. Используйте формат ГГГГ-ММ-ДД.",
                    error=error,
                )
            )
            return

        amount_str = transfer_amount_entry.get().strip()
        if not amount_str:
            show_error(tr("operations.transfer.error.amount_required", "Укажите сумму перевода."))
            return

        try:
            transfer_amount = float(amount_str)
            commission_amount = float((transfer_commission_entry.get() or "0").strip())
        except ValueError:
            show_error(
                tr(
                    "operations.transfer.error.amount_number",
                    "Сумма перевода и комиссия должны быть числами.",
                )
            )
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
            show_info(
                tr("operations.transfer.created", "Перевод создан (id={id}).", id=transfer_id)
            )
            transfer_amount_entry.delete(0, tk.END)
            transfer_description_entry.delete(0, tk.END)
            transfer_commission_entry.delete(0, tk.END)
            transfer_commission_entry.insert(0, "0")
            refresh_operation_views(context)
            _refresh_category_combo()
        except (DomainError, ValueError, TypeError, RuntimeError) as error:
            log_ui_error(
                logger,
                "UI_OPS_CREATE_TRANSFER_FAILED",
                error,
                from_wallet_id=from_wallet_id,
                to_wallet_id=to_wallet_id,
            )
            show_error(
                tr(
                    "operations.transfer.error.create_failed",
                    "Не удалось создать перевод: {error}",
                    error=error,
                )
            )

    transfer_creator_widgets = [
        transfer_from_menu,
        transfer_to_menu,
        transfer_date_entry,
        transfer_amount_entry,
        transfer_currency_entry,
        transfer_commission_entry,
        transfer_commission_currency_entry,
        transfer_description_entry,
    ]
    transfer_create_button = ttk.Button(
        transfer_frame,
        text=tr("operations.transfer.create", "Создать перевод"),
        command=create_transfer,
        style="Primary.TButton",
    )
    transfer_create_button.grid(row=8, column=0, columnspan=2, pady=6)
    _bind_focus_navigation(
        [*transfer_creator_widgets, transfer_create_button], submit_action=create_transfer
    )
    refresh_transfer_wallet_menus()

    import_mode_keys = [
        "operations.mode.replace",
        "operations.mode.current_rate",
        "operations.mode.legacy",
    ]
    import_mode_labels = [
        tr("operations.mode.replace", "Полная замена"),
        tr("operations.mode.current_rate", "По текущему курсу"),
        tr("operations.mode.legacy", "Наследуемый импорт"),
    ]
    import_mode_label_var = tk.StringVar(value=import_mode_labels[0])
    import_mode_key_var = tk.StringVar(value=import_mode_keys[0])
    import_format_var = tk.StringVar(value="CSV")

    def import_records_data() -> None:
        policy = context._import_policy_from_ui(import_mode_key_var.get())
        fmt = import_format_var.get()
        cfg = import_formats.get(fmt)
        if not cfg:
            show_error(
                tr(
                    "operations.error.import_format",
                    "Неподдерживаемый формат импорта: {fmt}",
                    fmt=fmt,
                )
            )
            return

        filepath = filedialog.askopenfilename(
            defaultextension=cfg["ext"],
            filetypes=[(f"{fmt} files", f"*{cfg['ext']}"), ("All files", "*.*")],
            title=tr(
                "operations.import.select_file",
                "Выберите файл {format} для импорта",
                format=cfg["desc"],
            ),
        )
        if not filepath:
            return

        if policy == ImportPolicy.CURRENT_RATE:
            show_warning(
                tr(
                    "operations.import.current_rate.body",
                    "В режиме CURRENT_RATE курсы валют будут зафиксированы на момент импорта.",
                ),
                title=tr("operations.import.current_rate.title", "Импорт по текущему курсу"),
            )

        def preview_task() -> ImportResult:
            return context.controller.import_records(fmt, filepath, policy, dry_run=True)

        def commit_task() -> ImportResult:
            return context.controller.import_records(fmt, filepath, policy, dry_run=False)

        def on_commit_success(result: ImportResult) -> None:
            details = ""
            if result.skipped or result.errors:
                details = f"\nПропущено строк: {result.skipped}.\nПервые ошибки:\n- " + "\n- ".join(
                    result.errors[:5]
                )
            show_info(
                tr(
                    "operations.import.success",
                    "Импортировано записей: {count} ({format}).\nТекущие записи были заменены.",
                    count=result.imported,
                    format=cfg["desc"],
                )
                + details,
                title=tr("common.done", "Готово"),
            )
            refresh_operation_views(context)
            _refresh_category_combo()

        def on_error(exc: BaseException) -> None:
            if isinstance(exc, FileNotFoundError):
                show_error(
                    tr("common.file_not_found", "Файл не найден: {filepath}", filepath=filepath)
                )
                return
            show_error(
                tr(
                    "operations.import.error",
                    "Не удалось импортировать {format}: {error}",
                    format=cfg["desc"],
                    error=exc,
                )
            )

        def on_preview_success(preview: ImportResult) -> None:
            confirmed = show_import_preview_dialog(
                parent=parent,
                filepath=filepath,
                policy_label=import_mode_label_var.get(),
                preview=preview,
                force=False,
            )
            if not confirmed:
                return
            context._run_background(
                commit_task,
                on_success=on_commit_success,
                on_error=on_error,
                busy_message=tr(
                    "operations.busy.import",
                    "Импортируем {format}...",
                    format=cfg["desc"],
                ),
            )

        context._run_background(
            preview_task,
            on_success=on_preview_success,
            on_error=on_error,
            busy_message=tr(
                "operations.busy.validate",
                "Проверяем импорт {format}...",
                format=cfg["desc"],
            ),
        )

    def export_records_data() -> None:
        fmt = import_format_var.get()
        cfg = import_formats.get(fmt)
        if not cfg or fmt == "JSON":
            show_error(
                tr(
                    "operations.export.unsupported",
                    "Этот формат не поддерживается для экспорта операций.",
                )
            )
            return
        filepath = filedialog.asksaveasfilename(
            defaultextension=cfg["ext"],
            filetypes=[(f"{cfg['desc']} files", f"*{cfg['ext']}"), ("All files", "*.*")],
            title=tr(
                "operations.export.save_as", "Сохранить операции как {format}", format=cfg["desc"]
            ),
        )
        if not filepath:
            return

        records = context.repository.load_all()
        transfers = context.repository.load_transfers()

        def task() -> None:
            from gui.exporters import export_records

            export_records(records, filepath, fmt.lower(), transfers=transfers)

        def on_success(_: Any) -> None:
            show_info(
                tr(
                    "operations.export.success",
                    "Операции экспортированы в:\n{filepath}",
                    filepath=filepath,
                )
            )
            open_in_file_manager(os.path.dirname(filepath))

        context._run_background(
            task,
            on_success=on_success,
            busy_message=tr(
                "operations.busy.export",
                "Экспортируем {format}...",
                format=cfg["desc"],
            ),
        )

    actions_frame = ttk.Frame(list_frame)
    actions_frame.grid(row=2, column=0, columnspan=2, sticky="ew", pady=6)
    actions_frame.grid_columnconfigure(0, weight=1)
    actions_frame.grid_columnconfigure(1, weight=1)

    primary_actions = ttk.Frame(actions_frame)
    primary_actions.grid(row=0, column=0, sticky="ew", pady=(0, 6), padx=(0, 6))
    import_actions = ttk.Frame(actions_frame)
    import_actions.grid(row=0, column=1, sticky="ew", padx=(6, 0))
    for idx in range(4):
        primary_actions.grid_columnconfigure(idx, weight=1)
    for idx in range(6):
        import_actions.grid_columnconfigure(idx, weight=1)

    ttk.Button(
        primary_actions,
        text=tr("common.delete", "Удалить"),
        command=delete_selected,
    ).grid(row=0, column=0, sticky="ew", padx=(0, 6))
    ttk.Button(
        primary_actions,
        text=tr("common.edit", "Редактировать"),
        command=edit_selected_record_inline,
    ).grid(row=0, column=1, sticky="ew", padx=6)
    ttk.Button(
        primary_actions,
        text=tr("common.refresh", "Обновить"),
        command=context._refresh_list,
    ).grid(row=0, column=2, sticky="ew", padx=6)
    ttk.Button(
        primary_actions,
        text=tr("operations.delete_all", "Удалить все"),
        command=delete_all,
    ).grid(row=0, column=3, sticky="ew", padx=(6, 0))

    ttk.Label(import_actions, text=tr("common.format", "Формат:")).grid(row=0, column=0, sticky="w")
    ttk.Combobox(
        import_actions,
        textvariable=import_format_var,
        values=["CSV", "XLSX"],
        state="readonly",
    ).grid(row=0, column=1, sticky="ew", padx=(6, 8))
    ttk.Label(import_actions, text=tr("common.mode", "Режим:")).grid(row=0, column=2, sticky="w")
    import_mode_combo = ttk.Combobox(
        import_actions,
        textvariable=import_mode_label_var,
        values=import_mode_labels,
        state="readonly",
    )
    import_mode_combo.grid(row=0, column=3, sticky="ew", padx=(6, 8))

    def _sync_import_mode_key(_event: Any | None = None) -> None:
        idx = import_mode_combo.current()
        if idx < 0:
            idx = 0
        import_mode_key_var.set(import_mode_keys[idx])

    import_mode_combo.bind("<<ComboboxSelected>>", _sync_import_mode_key)
    _sync_import_mode_key()
    ttk.Button(
        import_actions,
        text=tr("operations.import", "Импорт"),
        command=import_records_data,
    ).grid(row=0, column=4, sticky="ew", padx=(0, 6))
    ttk.Button(
        import_actions,
        text=tr("operations.export", "Экспорт"),
        command=export_records_data,
    ).grid(row=0, column=5, sticky="ew")

    context._refresh_list()

    type_combo.bind("<<ComboboxSelected>>", _on_type_change)
    _refresh_category_combo()

    return OperationsTabBindings(
        records_tree=records_tree,
        refresh_operation_wallet_menu=refresh_operation_wallet_menu,
        refresh_transfer_wallet_menus=refresh_transfer_wallet_menus,
        set_type_income=_set_type_income,
        set_type_expense=_set_type_expense,
        save_record=save_record,
        select_first=select_first_record,
        select_last=select_last_record,
        delete_selected=delete_selected,
        delete_all=delete_all,
        edit_selected=edit_selected_record_inline,
        inline_editor_active=inline_editor_active,
    )
