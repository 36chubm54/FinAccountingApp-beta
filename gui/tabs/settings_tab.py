"""
Settings tab — management of wallets and mandatory expenses (CRUD, import/export), backup, audit.
"""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from dataclasses import dataclass
from tkinter import ttk
from typing import Any, Protocol

from gui.i18n import tr
from gui.tabs.settings_mandatory_section import build_mandatory_section
from gui.tabs.settings_sections import (
    build_audit_section,
    build_backup_section,
    build_currency_section,
    build_wallets_section,
)
from gui.ui_dialogs import messagebox_compat as messagebox
from gui.ui_theme import PAD_LG, PAD_SM, PAD_XL


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
        busy_message: str = tr("app.busy.default", "Выполняется операция..."),
    ) -> None: ...


@dataclass(slots=True)
class SettingsTabBindings:
    refresh: Callable[[], None]


def build_settings_tab(
    parent: tk.Frame | ttk.Frame,
    context: SettingsTabContext,
    import_formats: dict[str, dict[str, str]],
) -> SettingsTabBindings:
    def _base_currency_code() -> str:
        getter = getattr(context.controller, "get_base_currency_code", None)
        if callable(getter):
            return str(getter() or "").strip().upper() or "KZT"
        return "KZT"

    parent.grid_columnconfigure(0, weight=3, uniform="settings")
    parent.grid_columnconfigure(1, weight=5, uniform="settings")
    parent.grid_rowconfigure(0, weight=1)

    left_panel = ttk.Frame(parent)
    left_panel.grid(row=0, column=0, sticky="nsew", padx=(PAD_XL, PAD_SM), pady=PAD_LG)
    left_panel.grid_columnconfigure(0, weight=1)

    right_panel = ttk.Frame(parent)
    right_panel.grid(row=0, column=1, sticky="nsew", padx=(PAD_SM, PAD_XL), pady=PAD_LG)
    right_panel.grid_rowconfigure(0, weight=0)
    right_panel.grid_rowconfigure(1, weight=1)
    right_panel.grid_columnconfigure(0, weight=1)

    base_currency_code = _base_currency_code()

    wallets = build_wallets_section(
        left_panel,
        context=context,
        base_currency_code=base_currency_code,
        messagebox_module=messagebox,
    )
    build_currency_section(right_panel, context=context, messagebox_module=messagebox)
    refresh_mandatory = build_mandatory_section(
        right_panel,
        context=context,
        import_formats=import_formats,
        refresh_wallets=wallets.refresh_wallets,
        base_currency_code=base_currency_code,
        messagebox_module=messagebox,
    )
    build_backup_section(
        left_panel,
        parent=parent,
        context=context,
        refresh_wallets=wallets.refresh_wallets,
        refresh_mandatory=refresh_mandatory,
        messagebox_module=messagebox,
    )
    build_audit_section(left_panel, parent=parent, context=context, messagebox_module=messagebox)

    wallets.refresh_wallets()
    refresh_mandatory()
    return SettingsTabBindings(refresh=refresh_mandatory)
