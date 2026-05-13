from __future__ import annotations

import logging
import os
import tkinter as tk
from collections.abc import Callable
from dataclasses import dataclass
from tkinter import filedialog, ttk
from typing import Any, Protocol

from domain.errors import DomainError
from domain.import_result import ImportResult
from gui.helpers import open_in_file_manager
from gui.i18n import tr
from gui.logging_utils import log_ui_error
from gui.tabs.settings_support import safe_destroy
from gui.ui_dialogs import messagebox_compat as messagebox
from gui.ui_helpers import (
    attach_treeview_scrollbars,
    enable_treeview_column_autosize,
    parse_numeric_input,
)
from gui.ui_theme import PAD_SM, PAD_XS, create_card_section, enable_treeview_zebra

logger = logging.getLogger(__name__)


class MessageBoxLike(Protocol):
    def showerror(self, title: str, message: str) -> Any: ...

    def showinfo(self, title: str, message: str) -> Any: ...

    def askyesno(self, title: str, message: str) -> bool: ...


@dataclass(slots=True)
class MandatoryAddFormFields:
    panel: ttk.Frame
    amount_entry: ttk.Entry
    currency_entry: ttk.Entry
    wallet_var: tk.StringVar
    wallet_map: dict[str, int]
    category_entry: ttk.Entry
    description_entry: ttk.Entry
    period_var: tk.StringVar
    date_entry: ttk.Entry


@dataclass(slots=True)
class MandatoryEditFormFields:
    panel: ttk.Frame
    amount_base_entry: ttk.Entry
    wallet_var: tk.StringVar
    wallet_map: dict[str, int]
    period_var: tk.StringVar
    date_entry: ttk.Entry


@dataclass(slots=True)
class MandatoryAddToRecordsFields:
    panel: ttk.Frame
    wallet_var: tk.StringVar
    wallet_map: dict[str, int]
    date_entry: ttk.Entry


def _create_mandatory_inline_panel(parent: tk.Misc) -> ttk.Frame:
    panel = ttk.Frame(parent, style="InlinePanel.TFrame", padding=(PAD_SM, PAD_XS))
    panel.grid(row=2, column=0, columnspan=2, pady=PAD_SM, sticky="ew")
    _configure_inline_panel_grid(panel)
    return panel


def _mandatory_wallet_map(controller: Any) -> dict[str, int]:
    return {
        f"[{wallet.id}] {wallet.name} ({wallet.currency})": wallet.id
        for wallet in controller.load_active_wallets()
    }


def _build_mandatory_wallet_selector(
    panel: ttk.Frame,
    *,
    row_index: int,
    controller: Any,
    selected_wallet_id: int | None = None,
) -> tuple[tk.StringVar, ttk.Combobox, dict[str, int]]:
    ttk.Label(panel, text=tr("common.wallet", "Кошелек:")).grid(
        row=row_index, column=0, sticky="w"
    )
    wallet_var = tk.StringVar(value="")
    wallet_menu = ttk.Combobox(
        panel,
        textvariable=wallet_var,
        values=[],
        state="readonly",
    )
    wallet_menu.grid(row=row_index, column=1, sticky="ew")
    wallet_map = _mandatory_wallet_map(controller)
    wallet_labels = list(wallet_map.keys()) or [""]
    wallet_menu["values"] = wallet_labels
    if selected_wallet_id is None:
        wallet_var.set(wallet_labels[0])
    else:
        current_wallet_label = next(
            (
                label
                for label, wallet_id in wallet_map.items()
                if int(wallet_id) == int(selected_wallet_id)
            ),
            wallet_labels[0],
        )
        wallet_var.set(current_wallet_label)
    return wallet_var, wallet_menu, wallet_map


def _build_add_mandatory_panel(
    parent: tk.Misc,
    *,
    controller: Any,
    base_currency_code: str,
) -> MandatoryAddFormFields:
    panel = _create_mandatory_inline_panel(parent)

    ttk.Label(panel, text=tr("settings.mandatory.field.amount", "Сумма:")).grid(
        row=0, column=0, sticky="w"
    )
    amount_entry = ttk.Entry(panel)
    amount_entry.grid(row=0, column=1, sticky="ew", pady=2)

    ttk.Label(
        panel,
        text=tr(
            "settings.mandatory.field.currency_default",
            "Валюта (по умолчанию валюта базы):",
        ),
    ).grid(row=1, column=0, sticky="w")
    currency_entry = ttk.Entry(panel)
    currency_entry.insert(0, base_currency_code)
    currency_entry.grid(row=1, column=1, sticky="ew", pady=2)

    wallet_var, _wallet_menu, wallet_map = _build_mandatory_wallet_selector(
        panel,
        row_index=2,
        controller=controller,
    )

    ttk.Label(
        panel,
        text=tr(
            "settings.mandatory.field.category_default", "Категория (по умолчанию Mandatory):"
        ),
    ).grid(row=3, column=0, sticky="w")
    category_entry = ttk.Entry(panel)
    category_entry.insert(0, "Mandatory")
    category_entry.grid(row=3, column=1, sticky="ew", pady=2)

    ttk.Label(panel, text=tr("common.description", "Описание:")).grid(
        row=4, column=0, sticky="w"
    )
    description_entry = ttk.Entry(panel)
    description_entry.grid(row=4, column=1, sticky="ew", pady=2)

    ttk.Label(panel, text=tr("common.period", "Период:")).grid(row=5, column=0, sticky="w")
    period_var = tk.StringVar(value="monthly")
    period_combo = ttk.Combobox(
        panel,
        textvariable=period_var,
        values=["daily", "weekly", "monthly", "yearly"],
        state="readonly",
    )
    period_combo.grid(row=5, column=1, sticky="ew", pady=2)

    ttk.Label(
        panel,
        text=tr("settings.mandatory.field.date_optional", "Дата (YYYY-MM-DD, необязательно):"),
    ).grid(row=6, column=0, sticky="w")
    date_entry = ttk.Entry(panel)
    date_entry.grid(row=6, column=1, sticky="ew", pady=2)

    return MandatoryAddFormFields(
        panel=panel,
        amount_entry=amount_entry,
        currency_entry=currency_entry,
        wallet_var=wallet_var,
        wallet_map=wallet_map,
        category_entry=category_entry,
        description_entry=description_entry,
        period_var=period_var,
        date_entry=date_entry,
    )


def _build_edit_mandatory_panel(
    parent: tk.Misc,
    *,
    controller: Any,
    expense: Any,
) -> MandatoryEditFormFields:
    panel = _create_mandatory_inline_panel(parent)

    ttk.Label(
        panel,
        text=tr("settings.mandatory.field.amount_base", "Сумма в валюте базы:"),
    ).grid(row=0, column=0, sticky="w")
    amount_base_entry = ttk.Entry(panel)
    amount_base_entry.insert(0, str(expense.amount_base))
    amount_base_entry.grid(row=0, column=1, sticky="ew", pady=2)

    wallet_var, _wallet_menu, wallet_map = _build_mandatory_wallet_selector(
        panel,
        row_index=1,
        controller=controller,
        selected_wallet_id=int(expense.wallet_id),
    )

    ttk.Label(panel, text=tr("common.period", "Период:")).grid(row=2, column=0, sticky="w")
    period_var = tk.StringVar(value=str(expense.period or "monthly"))
    period_combo = ttk.Combobox(
        panel,
        textvariable=period_var,
        values=["daily", "weekly", "monthly", "yearly"],
        state="readonly",
    )
    period_combo.grid(row=2, column=1, sticky="ew")

    ttk.Label(
        panel,
        text=tr("settings.mandatory.field.date_optional", "Дата (YYYY-MM-DD, необязательно):"),
    ).grid(row=3, column=0, sticky="w")
    date_entry = ttk.Entry(panel)
    date_entry.insert(0, _mandatory_date_text(expense))
    date_entry.grid(row=3, column=1, sticky="ew", pady=2)

    return MandatoryEditFormFields(
        panel=panel,
        amount_base_entry=amount_base_entry,
        wallet_var=wallet_var,
        wallet_map=wallet_map,
        period_var=period_var,
        date_entry=date_entry,
    )


def _build_add_to_records_panel(
    parent: tk.Misc,
    *,
    controller: Any,
) -> MandatoryAddToRecordsFields:
    panel = _create_mandatory_inline_panel(parent)

    ttk.Label(
        panel,
        text=tr("settings.mandatory.field.date_required", "Дата (YYYY-MM-DD):"),
    ).grid(row=0, column=0, sticky="w")
    date_entry = ttk.Entry(panel)
    date_entry.grid(row=0, column=1, sticky="ew", pady=2)

    wallet_var, _wallet_menu, wallet_map = _build_mandatory_wallet_selector(
        panel,
        row_index=1,
        controller=controller,
    )
    return MandatoryAddToRecordsFields(
        panel=panel,
        wallet_var=wallet_var,
        wallet_map=wallet_map,
        date_entry=date_entry,
    )


def _configure_inline_panel_grid(panel: ttk.Frame) -> None:
    panel.grid_columnconfigure(0, minsize=280)
    panel.grid_columnconfigure(1, weight=1, minsize=320)


def _build_inline_action_buttons(
    panel: ttk.Frame,
    *,
    row_index: int,
    on_save: Callable[[], None],
    on_cancel: Callable[[], None],
) -> None:
    buttons = ttk.Frame(panel, style="InlinePanel.TFrame")
    buttons.grid(row=row_index, column=0, columnspan=2, sticky="ew", pady=(8, 0))
    buttons.grid_columnconfigure(0, weight=1)
    buttons.grid_columnconfigure(1, weight=1)
    ttk.Button(
        buttons,
        text=tr("common.save", "Сохранить"),
        style="Primary.TButton",
        command=on_save,
    ).grid(row=0, column=0, sticky="ew", padx=(0, 6))
    ttk.Button(buttons, text=tr("common.cancel", "Отмена"), command=on_cancel).grid(
        row=0, column=1, sticky="ew", padx=(6, 0)
    )


def _selected_mandatory_index(
    mand_tree: ttk.Treeview,
    *,
    messagebox_module: MessageBoxLike,
    missing_message: str,
) -> int | None:
    selection = mand_tree.selection()
    if not selection:
        messagebox_module.showerror(tr("common.error", "Ошибка"), missing_message)
        return None
    try:
        return int(selection[0])
    except (TypeError, ValueError):
        messagebox_module.showerror(
            tr("common.error", "Ошибка"),
            tr("common.invalid_selection", "Некорректный выбор."),
        )
        return None


def _build_mandatory_actions_row(
    parent: tk.Misc,
    *,
    format_var: tk.StringVar,
    on_create: Callable[[], None],
    on_edit: Callable[[], None],
    on_add_to_records: Callable[[], None],
    on_delete: Callable[[], None],
    on_delete_all: Callable[[], None],
    on_refresh: Callable[[], None],
    on_import: Callable[[], None],
    on_export: Callable[[], None],
    pad_x: int,
    pad_y: int,
) -> None:
    actions = ttk.Frame(parent)
    actions.grid(row=1, column=0, columnspan=2, sticky="ew", padx=pad_x, pady=(0, pad_y))
    for idx in range(5):
        actions.grid_columnconfigure(idx, weight=1)

    ttk.Button(actions, text=tr("common.create", "Создать"), command=on_create).grid(
        row=0, column=0, sticky="ew", padx=(0, 6), pady=(0, 6)
    )
    ttk.Button(actions, text=tr("common.edit", "Редактировать"), command=on_edit).grid(
        row=0, column=1, sticky="ew", padx=6, pady=(0, 6)
    )
    ttk.Button(
        actions,
        text=tr("settings.mandatory.add_to_records", "Добавить в записи"),
        command=on_add_to_records,
    ).grid(row=0, column=2, sticky="ew", padx=6, pady=(0, 6))
    ttk.Button(actions, text=tr("common.delete", "Удалить"), command=on_delete).grid(
        row=0, column=3, sticky="ew", padx=6, pady=(0, 6)
    )
    ttk.Button(
        actions,
        text=tr("settings.mandatory.delete_all", "Удалить все"),
        command=on_delete_all,
    ).grid(row=0, column=4, sticky="ew", padx=(6, 0), pady=(0, 6))
    ttk.Button(actions, text=tr("common.refresh", "Обновить"), command=on_refresh).grid(
        row=1, column=0, sticky="ew", padx=(0, 6)
    )
    ttk.Combobox(
        actions,
        textvariable=format_var,
        values=["CSV", "XLSX"],
        state="readonly",
    ).grid(row=1, column=1, sticky="ew", padx=6)
    ttk.Button(actions, text=tr("operations.import", "Импорт"), command=on_import).grid(
        row=1, column=2, sticky="ew", padx=6
    )
    ttk.Button(actions, text=tr("operations.export", "Экспорт"), command=on_export).grid(
        row=1, column=3, sticky="ew", padx=6
    )


def _build_mandatory_tree(parent: tk.Misc) -> tuple[ttk.Treeview, ttk.Scrollbar | None]:
    mand_tree = ttk.Treeview(
        parent,
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
    enable_treeview_zebra(mand_tree)
    for col, text, width, minwidth, stretch, anchor in (
        ("index", "#", 40, 40, False, "e"),
        ("amount", tr("settings.mandatory.amount", "Сумма"), 90, 90, False, "e"),
        ("currency", tr("settings.mandatory.currency_short", "Вал."), 60, 60, False, "center"),
        ("kzt", "KZT", 90, 90, False, "e"),
        ("category", tr("settings.mandatory.category", "Категория"), 120, 120, False, "w"),
        ("description", tr("settings.mandatory.description", "Описание"), 200, 160, True, "w"),
        ("period", tr("settings.mandatory.period", "Период"), 90, 80, False, "w"),
        ("date", tr("settings.mandatory.date", "Дата"), 100, 100, False, "w"),
        ("autopay", tr("settings.mandatory.autopay", "Автоплатеж"), 120, 100, False, "center"),
    ):
        mand_tree.heading(col, text=text)
        mand_tree.column(col, width=width, minwidth=minwidth, stretch=stretch, anchor=anchor)  # type: ignore[arg-type]
    enable_treeview_column_autosize(
        mand_tree,
        columns=("category", "description"),
        max_width=360,
    )
    mand_tree.grid(row=0, column=0, sticky="nsew")
    _mand_scroll, mand_xscroll = attach_treeview_scrollbars(
        parent, mand_tree, row=0, column=0, horizontal=True
    )
    return mand_tree, mand_xscroll


def _bind_mandatory_horizontal_scroll(
    mand_tree: ttk.Treeview,
    mand_xscroll: ttk.Scrollbar | None,
) -> None:
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
        if widget is not None:
            widget.bind("<Shift-MouseWheel>", _on_mandatory_shift_mousewheel, add="+")
            widget.bind("<Shift-Button-4>", _on_mandatory_shift_button4, add="+")
            widget.bind("<Shift-Button-5>", _on_mandatory_shift_button5, add="+")


def _mandatory_date_text(expense: Any) -> str:
    return (
        expense.date.isoformat()
        if getattr(expense.date, "isoformat", None) is not None
        else str(expense.date or "")
    )


def _populate_mandatory_tree(
    mand_tree: ttk.Treeview,
    *,
    context: Any,
    base_currency_code: str,
) -> None:
    mand_tree.heading("kzt", text=context.controller.get_display_currency_code())
    for iid in mand_tree.get_children():
        mand_tree.delete(iid)
    expenses = context.controller.load_mandatory_expenses()
    for idx, expense in enumerate(expenses):
        values = (
            str(idx),
            f"{float(expense.amount_original or 0.0):,.2f}",
            str(expense.currency or base_currency_code).upper(),
            context.controller.format_display_amount(float(expense.amount_base or 0.0)),
            str(expense.category or ""),
            str(expense.description or ""),
            str(expense.period or ""),
            _mandatory_date_text(expense),
            "✓" if bool(expense.auto_pay) else "",
        )
        mand_tree.insert("", "end", iid=str(idx), values=values)


def build_mandatory_section(
    parent_panel: tk.Frame | ttk.Frame,
    *,
    context: Any,
    import_formats: dict[str, dict[str, str]],
    refresh_wallets: Callable[[], None],
    base_currency_code: str,
    messagebox_module: MessageBoxLike = messagebox,
    row_index: int = 1,
) -> Callable[[], None]:
    pad_x = PAD_SM
    pad_y = PAD_XS

    mand_card = create_card_section(parent_panel, tr("settings.mandatory", "Обязательные расходы"))
    mand_card.grid(row=row_index, column=0, sticky="nsew")
    mand_frame = mand_card.winfo_children()[-1]
    mand_frame.grid_rowconfigure(0, weight=1)
    mand_frame.grid_columnconfigure(0, weight=1)

    mand_list_frame = ttk.Frame(mand_frame)
    mand_list_frame.grid(row=0, column=0, columnspan=2, sticky="nsew", padx=pad_x, pady=pad_y)
    mand_list_frame.grid_rowconfigure(0, weight=1)
    mand_list_frame.grid_columnconfigure(0, weight=1)
    mand_tree, mand_xscroll = _build_mandatory_tree(mand_list_frame)
    _bind_mandatory_horizontal_scroll(mand_tree, mand_xscroll)

    def refresh_mandatory() -> None:
        _populate_mandatory_tree(
            mand_tree,
            context=context,
            base_currency_code=base_currency_code,
        )

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

        form = _build_add_mandatory_panel(
            mand_frame,
            controller=context.controller,
            base_currency_code=base_currency_code,
        )
        current_panel["add"] = form.panel

        def save() -> None:
            wallet_id = None
            try:
                amount = float(form.amount_entry.get())
                description = form.description_entry.get()
                if not description:
                    messagebox_module.showerror(
                        tr("common.error", "Ошибка"),
                        tr(
                            "settings.mandatory.error.description_required", "Описание обязательно."
                        ),
                    )
                    return
                date_val = form.date_entry.get().strip()
                if date_val:
                    try:
                        from domain.validation import parse_ymd

                        parse_ymd(date_val)
                    except ValueError:
                        messagebox_module.showerror(
                            tr("common.error", "Ошибка"),
                            tr(
                                "settings.mandatory.error.invalid_date",
                                "Некорректная дата. Используйте YYYY-MM-DD.",
                            ),
                        )
                        return
                wallet_id = form.wallet_map.get(form.wallet_var.get())
                if wallet_id is None:
                    messagebox_module.showerror(
                        tr("common.error", "Ошибка"),
                        tr("settings.mandatory.error.wallet_required", "Кошелек обязателен."),
                    )
                    return
                context.controller.create_mandatory_expense(
                    amount=amount,
                    currency=(form.currency_entry.get() or base_currency_code).strip(),
                    wallet_id=wallet_id,
                    category=(form.category_entry.get() or "Mandatory").strip(),
                    description=description,
                    period=form.period_var.get(),
                    date=date_val,
                )
                messagebox_module.showinfo(
                    tr("common.done", "Готово"),
                    tr("settings.mandatory.added", "Обязательный расход добавлен."),
                )
                safe_destroy(form.panel)
                current_panel["add"] = None
                context._refresh_charts()
                refresh_mandatory()
                context._refresh_budgets()
            except (DomainError, ValueError, TypeError, RuntimeError) as error:
                log_ui_error(
                    logger,
                    "UI_SETTINGS_MANDATORY_CREATE_FAILED",
                    error,
                    wallet_id=wallet_id,
                )
                messagebox_module.showerror(
                    tr("common.error", "Ошибка"),
                    tr(
                        "settings.mandatory.error.add_failed",
                        "Не удалось добавить расход: {error}",
                        error=error,
                    ),
                )

        def cancel() -> None:
            try:
                safe_destroy(form.panel)
            finally:
                current_panel["add"] = None

        _build_inline_action_buttons(
            form.panel,
            row_index=7,
            on_save=save,
            on_cancel=cancel,
        )

    def edit_mandatory_inline() -> None:
        index = _selected_mandatory_index(
            mand_tree,
            messagebox_module=messagebox_module,
            missing_message=tr(
                "settings.mandatory.error.select_edit",
                "Выберите обязательный расход для редактирования.",
            ),
        )
        if index is None:
            return
        expenses = context.controller.load_mandatory_expenses()
        if not (0 <= index < len(expenses)):
            return
        expense = expenses[index]

        close_inline_panels()

        form = _build_edit_mandatory_panel(
            mand_frame,
            controller=context.controller,
            expense=expense,
        )
        current_panel["edit"] = form.panel

        def save_edit() -> None:
            expense_id = int(expense.id)
            raw_amount = form.amount_base_entry.get().strip()
            current_amount = str(expense.amount_base)
            if raw_amount != current_amount:
                try:
                    context.controller.update_mandatory_expense_amount_base(
                        expense_id, parse_numeric_input(raw_amount)
                    )
                except ValueError as error:
                    messagebox_module.showerror(
                        tr("settings.mandatory.error.amount_title", "Ошибка суммы"), str(error)
                    )
                    return

            new_wallet_id = form.wallet_map.get(form.wallet_var.get())
            if new_wallet_id is None:
                messagebox_module.showerror(
                    tr("common.error", "Ошибка"),
                    tr("settings.mandatory.error.wallet_required", "Кошелек обязателен."),
                )
                return
            if int(new_wallet_id) != int(expense.wallet_id):
                try:
                    context.controller.update_mandatory_expense_wallet_id(
                        expense_id, int(new_wallet_id)
                    )
                except ValueError as error:
                    messagebox_module.showerror(
                        tr("settings.mandatory.error.wallet_title", "Ошибка кошелька"), str(error)
                    )
                    return

            new_period = str(form.period_var.get() or "").strip().lower()
            if new_period and str(new_period) != str(expense.period):
                try:
                    context.controller.update_mandatory_expense_period(expense_id, new_period)
                except ValueError as error:
                    messagebox_module.showerror(
                        tr("settings.mandatory.error.period_title", "Ошибка периода"), str(error)
                    )
                    return

            current_date = (
                _mandatory_date_text(expense)
            )
            new_date = form.date_entry.get().strip()
            if new_date != current_date:
                try:
                    context.controller.update_mandatory_expense_date(expense_id, new_date)
                except ValueError as error:
                    messagebox_module.showerror(
                        tr("settings.mandatory.error.date_title", "Ошибка даты"), str(error)
                    )
                    return

            safe_destroy(form.panel)
            current_panel["edit"] = None
            refresh_mandatory()
            context._refresh_charts()
            context._refresh_budgets()
            messagebox_module.showinfo(
                tr("common.done", "Готово"),
                tr("settings.mandatory.updated", "Обязательный расход обновлен."),
            )

        def cancel_edit() -> None:
            try:
                safe_destroy(form.panel)
            finally:
                current_panel["edit"] = None

        _build_inline_action_buttons(
            form.panel,
            row_index=4,
            on_save=save_edit,
            on_cancel=cancel_edit,
        )

    def add_to_records_inline() -> None:
        index = _selected_mandatory_index(
            mand_tree,
            messagebox_module=messagebox_module,
            missing_message=tr(
                "settings.mandatory.error.select_add_to_records",
                "Выберите обязательный расход для добавления в записи.",
            ),
        )
        if index is None:
            return
        close_inline_panels()

        form = _build_add_to_records_panel(
            mand_frame,
            controller=context.controller,
        )
        current_panel["report"] = form.panel

        def save() -> None:
            try:
                from domain.validation import ensure_not_future, parse_ymd

                date_value = form.date_entry.get()
                entered_date = parse_ymd(date_value)
                ensure_not_future(entered_date)
                wallet_id = form.wallet_map.get(form.wallet_var.get())
                if wallet_id is None:
                    messagebox_module.showerror(
                        tr("common.error", "Ошибка"),
                        tr("settings.mandatory.error.wallet_required", "Кошелек обязателен."),
                    )
                    return

                context.controller.add_mandatory_to_report(index, date_value, wallet_id)
                messagebox_module.showinfo(
                    tr("common.done", "Готово"),
                    tr(
                        "settings.mandatory.added_to_records",
                        "Обязательный расход добавлен в записи за {date}.",
                        date=date_value,
                    ),
                )
                safe_destroy(form.panel)
                current_panel["report"] = None
                refresh_mandatory()
                refresh_wallets()
                context._refresh_list()
                context._refresh_charts()
                context._refresh_budgets()
                context._refresh_all()
            except ValueError as error:
                messagebox_module.showerror(
                    tr("common.error", "Ошибка"),
                    tr(
                        "settings.mandatory.error.invalid_date_with_hint",
                        "Некорректная дата: {error}. Используйте YYYY-MM-DD.",
                        error=error,
                    ),
                )

        def cancel() -> None:
            try:
                safe_destroy(form.panel)
            finally:
                current_panel["report"] = None

        _build_inline_action_buttons(
            form.panel,
            row_index=2,
            on_save=save,
            on_cancel=cancel,
        )

    def delete_mandatory() -> None:
        index = _selected_mandatory_index(
            mand_tree,
            messagebox_module=messagebox_module,
            missing_message=tr(
                "settings.mandatory.error.select_delete",
                "Выберите обязательный расход для удаления.",
            ),
        )
        if index is None:
            return
        if context.controller.delete_mandatory_expense(index):
            messagebox_module.showinfo(
                tr("common.done", "Готово"),
                tr("settings.mandatory.deleted", "Обязательный расход удален."),
            )
            refresh_mandatory()
        else:
            messagebox_module.showerror(
                tr("common.error", "Ошибка"),
                tr(
                    "settings.mandatory.error.delete_failed",
                    "Не удалось удалить обязательный расход.",
                ),
            )

    def delete_all_mandatory() -> None:
        if not messagebox_module.askyesno(
            tr("common.confirm", "Подтверждение"),
            tr(
                "settings.mandatory.confirm_delete_all",
                "Удалить ВСЕ обязательные расходы? Это действие нельзя отменить.",
            ),
        ):
            return
        context.controller.delete_all_mandatory_expenses()
        messagebox_module.showinfo(
            tr("common.done", "Готово"),
            tr("settings.mandatory.deleted_all", "Все обязательные расходы удалены."),
        )
        refresh_mandatory()

    format_var = tk.StringVar(value="CSV")

    def import_mand() -> None:
        fmt = format_var.get()
        cfg = import_formats.get(fmt)
        if not cfg:
            messagebox_module.showerror(
                tr("common.error", "Ошибка"),
                tr("common.unsupported_format", "Неподдерживаемый формат: {fmt}", fmt=fmt),
            )
            return

        filepath = filedialog.askopenfilename(
            defaultextension=cfg["ext"],
            filetypes=[(f"{cfg['desc']} files", f"*{cfg['ext']}"), ("All files", "*.*")],
            title=tr(
                "settings.mandatory.import.select_file",
                "Выберите файл {desc} для импорта обязательных расходов",
                desc=cfg["desc"],
            ),
        )
        if not filepath:
            return

        if not messagebox_module.askyesno(
            tr("common.confirm", "Подтверждение"),
            tr(
                "settings.mandatory.import.confirm",
                "Это заменит все существующие обязательные расходы данными из:\n{filepath}\n"
                "\nПродолжить?",
                filepath=filepath,
            ),
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

            messagebox_module.showinfo(
                tr("common.done", "Готово"),
                tr(
                    "settings.mandatory.import.success",
                    "Успешно импортировано {count} обязательных расходов из файла {desc}."
                    "\nВсе существующие обязательные расходы были заменены.",
                    count=result.imported,
                    desc=cfg["desc"],
                )
                + details,
            )
            refresh_mandatory()

        def on_error(exc: BaseException) -> None:
            if isinstance(exc, FileNotFoundError):
                messagebox_module.showerror(
                    tr("common.error", "Ошибка"),
                    tr("common.file_not_found", "Файл не найден: {filepath}", filepath=filepath),
                )
                return
            messagebox_module.showerror(
                tr("common.error", "Ошибка"),
                tr(
                    "settings.mandatory.import.error",
                    "Не удалось импортировать {fmt}: {error}",
                    fmt=fmt,
                    error=exc,
                ),
            )

        context._run_background(
            task,
            on_success=on_success,
            on_error=on_error,
            busy_message=tr(
                "settings.mandatory.import.busy",
                "Импортируем обязательные расходы из {desc}...",
                desc=cfg["desc"],
            ),
        )

    def export_mand() -> None:
        fmt = format_var.get()
        expenses = context.controller.load_mandatory_expenses()
        if not expenses:
            messagebox_module.showinfo(
                tr("settings.mandatory.export.empty_title", "Нет расходов"),
                tr("settings.mandatory.export.empty", "Нет обязательных расходов для экспорта."),
            )
            return

        filepath = filedialog.asksaveasfilename(
            defaultextension=f".{fmt.lower()}",
            title=tr("settings.mandatory.export.save", "Сохранить обязательные расходы"),
        )
        if not filepath:
            return

        def task() -> None:
            from gui.exporters import export_mandatory_expenses

            export_mandatory_expenses(expenses, filepath, fmt.lower())

        def on_success(_: Any) -> None:
            messagebox_module.showinfo(
                tr("common.done", "Готово"),
                tr(
                    "settings.mandatory.export.success",
                    "Обязательные расходы экспортированы в {filepath}",
                    filepath=filepath,
                ),
            )
            open_in_file_manager(os.path.dirname(filepath))

        context._run_background(
            task,
            on_success=on_success,
            busy_message=tr(
                "settings.mandatory.export.busy",
                "Экспортируем обязательные расходы в {fmt}...",
                fmt=fmt,
            ),
        )

    _build_mandatory_actions_row(
        mand_frame,
        format_var=format_var,
        on_create=add_mandatory_inline,
        on_edit=edit_mandatory_inline,
        on_add_to_records=add_to_records_inline,
        on_delete=delete_mandatory,
        on_delete_all=delete_all_mandatory,
        on_refresh=refresh_mandatory,
        on_import=import_mand,
        on_export=export_mand,
        pad_x=pad_x,
        pad_y=pad_y,
    )

    return refresh_mandatory
