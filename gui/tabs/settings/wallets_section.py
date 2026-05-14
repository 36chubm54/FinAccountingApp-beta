from __future__ import annotations

import logging
import tkinter as tk
from collections.abc import Callable
from dataclasses import dataclass
from tkinter import ttk
from typing import Any, Protocol

from domain.errors import DomainError
from gui.i18n import tr
from gui.logging_utils import log_ui_error
from gui.ui_dialogs import messagebox_compat as messagebox
from gui.ui_helpers import attach_treeview_scrollbars, enable_treeview_column_autosize
from gui.ui_theme import PAD_LG, PAD_SM, PAD_XS, create_card_section, enable_treeview_zebra

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class WalletsSectionBindings:
    refresh_wallets: Callable[[], None]


@dataclass(slots=True)
class WalletFormFields:
    name_entry: ttk.Entry
    currency_entry: ttk.Entry
    initial_entry: ttk.Entry
    allow_negative_var: tk.BooleanVar


class MessageBoxLike(Protocol):
    def showerror(self, title: str, message: str) -> Any: ...

    def showinfo(self, title: str, message: str) -> Any: ...

    def askyesno(self, title: str, message: str) -> bool: ...


def refresh_wallet_related_ui(context: Any) -> None:
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


def _create_wallet_form(
    parent: tk.Misc,
    *,
    base_currency_code: str,
    pad_x: int,
    pad_y: int,
    label_style: str = "TLabel",
    checkbutton_style: str = "TCheckbutton",
) -> WalletFormFields:
    form = ttk.Frame(parent)
    form.grid(row=0, column=0, sticky="ew", padx=pad_x, pady=pad_y)
    form.grid_columnconfigure(1, weight=1)

    ttk.Label(
        form,
        text=tr("settings.wallets.name", "Название:"),
        style=label_style,
    ).grid(row=0, column=0, sticky="w")
    wallet_name_entry = ttk.Entry(form)
    wallet_name_entry.grid(row=0, column=1, sticky="ew", pady=2)

    ttk.Label(
        form,
        text=tr("settings.wallets.currency", "Валюта:"),
        style=label_style,
    ).grid(row=1, column=0, sticky="w")
    wallet_currency_entry = ttk.Entry(form, width=8)
    wallet_currency_entry.insert(0, base_currency_code)
    wallet_currency_entry.grid(row=1, column=1, sticky="ew", pady=2)

    ttk.Label(
        form,
        text=tr("settings.wallets.initial_balance", "Начальный баланс:"),
        style=label_style,
    ).grid(row=2, column=0, sticky="w")
    wallet_initial_entry = ttk.Entry(form)
    wallet_initial_entry.insert(0, "0")
    wallet_initial_entry.grid(row=2, column=1, sticky="ew", pady=2)

    wallet_allow_negative_var = tk.BooleanVar(value=False)
    ttk.Checkbutton(
        form,
        text=tr("settings.wallets.allow_negative", "Разрешить отрицательный баланс"),
        variable=wallet_allow_negative_var,
        style=checkbutton_style,
    ).grid(
        row=3,
        column=0,
        columnspan=2,
        sticky="w",
        pady=2,
    )
    return WalletFormFields(
        name_entry=wallet_name_entry,
        currency_entry=wallet_currency_entry,
        initial_entry=wallet_initial_entry,
        allow_negative_var=wallet_allow_negative_var,
    )


def _build_wallet_tree(
    parent: tk.Misc,
    *,
    pad_x: int,
) -> tuple[ttk.Treeview, ttk.Scrollbar | None, ttk.Scrollbar | None]:
    list_frame = ttk.Frame(parent)
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
    enable_treeview_zebra(wallet_tree)
    for col, text, width, minwidth, stretch, anchor in (
        ("id", "ID", 40, 40, False, "e"),
        ("name", tr("settings.wallets.name_short", "Название"), 100, 100, True, "w"),
        ("currency", tr("settings.wallets.currency_short", "Вал."), 60, 60, False, "center"),
        (
            "initial_balance",
            tr("settings.wallets.initial_balance_short", "Старт"),
            110,
            90,
            False,
            "e",
        ),
        ("balance", tr("settings.wallets.balance", "Баланс"), 110, 90, False, "e"),
        (
            "allow_negative",
            tr("settings.wallets.allow_negative_short", "Минус"),
            92,
            92,
            False,
            "center",
        ),
        ("active", tr("settings.wallets.active", "Активен"), 90, 90, False, "center"),
    ):
        wallet_tree.heading(col, text=text)
        wallet_tree.column(col, width=width, minwidth=minwidth, stretch=stretch, anchor=anchor)  # type: ignore[arg-type]
    enable_treeview_column_autosize(wallet_tree, columns=("name",), max_width=320)
    wallet_tree.grid(row=0, column=0, sticky="nsew")
    wallet_scroll, wallet_xscroll = attach_treeview_scrollbars(
        list_frame, wallet_tree, row=0, column=0, horizontal=True
    )
    return wallet_tree, wallet_scroll, wallet_xscroll


def _bind_wallet_scrolling(
    wallet_tree: ttk.Treeview,
    wallet_scroll: ttk.Scrollbar | None,
    wallet_xscroll: ttk.Scrollbar | None,
) -> None:
    def _wallet_scroll_units(delta: int, *, multiplier: int = 12) -> int:
        if delta == 0:
            return 0
        base_units = max(1, abs(int(delta)) // 120)
        return base_units * multiplier

    def _scroll_wallet_vertically(direction: int, units: int) -> str:
        wallet_tree.yview_scroll(direction * units, "units")
        return "break"

    def _scroll_wallet_horizontally(direction: int, units: int) -> str:
        wallet_tree.xview_scroll(direction * units, "units")
        return "break"

    def _on_wallet_mousewheel(event: tk.Event) -> str:
        delta = int(getattr(event, "delta", 0))
        units = _wallet_scroll_units(delta, multiplier=8)
        if units <= 0:
            return "break"
        direction = -1 if delta > 0 else 1
        return _scroll_wallet_vertically(direction, units)

    def _on_wallet_shift_mousewheel(event: tk.Event) -> str:
        delta = int(getattr(event, "delta", 0))
        units = _wallet_scroll_units(delta, multiplier=12)
        if units <= 0:
            return "break"
        direction = -1 if delta > 0 else 1
        return _scroll_wallet_horizontally(direction, units)

    def _on_wallet_button4(_event: tk.Event) -> str:
        return _scroll_wallet_vertically(-1, 3)

    def _on_wallet_button5(_event: tk.Event) -> str:
        return _scroll_wallet_vertically(1, 3)

    def _on_wallet_shift_button4(_event: tk.Event) -> str:
        return _scroll_wallet_horizontally(-1, 3)

    def _on_wallet_shift_button5(_event: tk.Event) -> str:
        return _scroll_wallet_horizontally(1, 3)

    for widget in (wallet_tree, wallet_scroll, wallet_xscroll):
        if widget is not None:
            widget.bind("<MouseWheel>", _on_wallet_mousewheel, add="+")
            widget.bind("<Shift-MouseWheel>", _on_wallet_shift_mousewheel, add="+")
            widget.bind("<Button-4>", _on_wallet_button4, add="+")
            widget.bind("<Button-5>", _on_wallet_button5, add="+")
            widget.bind("<Shift-Button-4>", _on_wallet_shift_button4, add="+")
            widget.bind("<Shift-Button-5>", _on_wallet_shift_button5, add="+")


def _build_wallet_actions(
    parent: tk.Misc,
    *,
    pad_x: int,
    pad_y: int,
    on_delete: Callable[[], None],
    on_refresh: Callable[[], None],
    on_close: Callable[[], None] | None,
) -> None:
    wallet_actions = ttk.Frame(parent)
    wallet_actions.grid(row=2, column=0, sticky="ew", padx=pad_x, pady=pad_y)
    wallet_actions.grid_columnconfigure(0, weight=1)
    wallet_actions.grid_columnconfigure(1, weight=1)
    if on_close is not None:
        wallet_actions.grid_columnconfigure(2, weight=1)

    ttk.Button(
        wallet_actions,
        text=tr("settings.wallets.delete", "Удалить кошелек"),
        command=on_delete,
    ).grid(row=0, column=0, sticky="ew", padx=(0, 4))
    ttk.Button(
        wallet_actions,
        text=tr("common.refresh", "Обновить"),
        command=on_refresh,
    ).grid(row=0, column=1, sticky="ew", padx=(4, 0))
    if on_close is not None:
        ttk.Button(
            wallet_actions,
            text=tr("common.close", "Закрыть"),
            command=on_close,
        ).grid(row=0, column=2, sticky="ew", padx=(8, 0))


def build_wallets_section(
    parent_panel: tk.Frame | ttk.Frame,
    *,
    context: Any,
    base_currency_code: str,
    messagebox_module: MessageBoxLike = messagebox,
    use_card: bool = True,
    row_index: int = 0,
    on_close: Callable[[], None] | None = None,
) -> WalletsSectionBindings:
    pad_x = PAD_SM
    pad_y = PAD_XS

    if use_card:
        wallets_card = create_card_section(parent_panel, tr("settings.wallets", "Кошельки"))
        wallets_card.grid(row=row_index, column=0, sticky="nsew", pady=(0, PAD_LG))
        wallets_frame = wallets_card.winfo_children()[-1]
    else:
        wallets_frame = ttk.Frame(parent_panel)
        wallets_frame.grid(row=row_index, column=0, sticky="nsew")
    wallets_frame.grid_columnconfigure(0, weight=1)
    wallets_frame.grid_rowconfigure(1, weight=1)
    form_fields = _create_wallet_form(
        wallets_frame,
        base_currency_code=base_currency_code,
        pad_x=pad_x,
        pad_y=pad_y,
        label_style="FormField.TLabel" if use_card else "TLabel",
        checkbutton_style="FormField.TCheckbutton" if use_card else "TCheckbutton",
    )
    wallet_tree, wallet_scroll, wallet_xscroll = _build_wallet_tree(wallets_frame, pad_x=pad_x)
    _bind_wallet_scrolling(wallet_tree, wallet_scroll, wallet_xscroll)

    def refresh_wallets() -> None:
        for iid in wallet_tree.get_children():
            wallet_tree.delete(iid)
        active_balances = {
            int(balance.wallet_id): float(balance.balance)
            for balance in context.controller.get_wallet_balances()
        }
        for wallet in context.controller.load_wallets():
            balance = active_balances.get(int(wallet.id))
            if balance is None:
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
                    tr("common.yes", "Да") if wallet.allow_negative else tr("common.no", "Нет"),
                    tr("common.yes", "Да") if wallet.is_active else tr("common.no", "Нет"),
                ),
            )
        refresh_wallet_related_ui(context)

    context.refresh_wallets = refresh_wallets

    def create_wallet() -> None:
        try:
            initial_balance = float(form_fields.initial_entry.get().strip() or "0")
        except ValueError:
            messagebox_module.showerror(
                tr("common.error", "Ошибка"),
                tr(
                    "settings.wallets.error.initial_balance",
                    "Некорректный начальный баланс кошелька.",
                ),
            )
            return

        name = ""
        try:
            name = form_fields.name_entry.get().strip()
            wallet = context.controller.create_wallet(
                name=name,
                currency=(form_fields.currency_entry.get() or base_currency_code).strip(),
                initial_balance=initial_balance,
                allow_negative=form_fields.allow_negative_var.get(),
            )
            messagebox_module.showinfo(
                tr("common.done", "Готово"),
                tr(
                    "settings.wallets.created",
                    "Кошелек создан: [{wallet_id}] {wallet_name}",
                    wallet_id=wallet.id,
                    wallet_name=wallet.name,
                ),
            )
            form_fields.name_entry.delete(0, tk.END)
            form_fields.initial_entry.delete(0, tk.END)
            form_fields.initial_entry.insert(0, "0")
            refresh_wallets()
        except (DomainError, ValueError, TypeError, RuntimeError) as error:
            log_ui_error(logger, "UI_SETTINGS_CREATE_WALLET_FAILED", error, name=name)
            messagebox_module.showerror(
                tr("common.error", "Ошибка"),
                tr(
                    "settings.wallets.error.create",
                    "Не удалось создать кошелек: {error}",
                    error=str(error),
                ),
            )

    ttk.Button(
        form_fields.name_entry.master,
        text=tr("settings.wallets.create", "Создать кошелек"),
        style="Primary.TButton",
        command=create_wallet,
    ).grid(row=4, column=0, columnspan=2, sticky="ew", pady=(6, 0))

    def delete_wallet() -> None:
        selection = wallet_tree.selection()
        if not selection:
            messagebox_module.showerror(
                tr("common.error", "Ошибка"),
                tr("settings.wallets.error.select_delete", "Выберите кошелек для удаления."),
            )
            return
        try:
            values = wallet_tree.item(selection[0], "values")
            wallet_id = int(values[0])
        except (TypeError, ValueError, IndexError):
            messagebox_module.showerror(
                tr("common.error", "Ошибка"),
                tr(
                    "settings.wallets.error.parse_id",
                    "Не удалось определить идентификатор выбранного кошелька.",
                ),
            )
            return

        try:
            context.controller.soft_delete_wallet(wallet_id)
            messagebox_module.showinfo(
                tr("common.done", "Готово"),
                tr("settings.wallets.deleted", "Кошелек деактивирован."),
            )
            refresh_wallets()
        except (DomainError, ValueError, TypeError, RuntimeError) as error:
            log_ui_error(logger, "UI_SETTINGS_DELETE_WALLET_FAILED", error, wallet_id=wallet_id)
            messagebox_module.showerror(tr("common.error", "Ошибка"), str(error))

    _build_wallet_actions(
        wallets_frame,
        pad_x=pad_x,
        pad_y=pad_y,
        on_delete=delete_wallet,
        on_refresh=refresh_wallets,
        on_close=on_close,
    )

    return WalletsSectionBindings(refresh_wallets=refresh_wallets)
