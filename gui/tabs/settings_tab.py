"""Compatibility shim for the settings tab."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from gui.tabs.settings import SettingsTabBindings, SettingsTabContext
from gui.tabs.settings.builder import build_settings_tab as _build_settings_tab
from gui.tabs.wallet_manager import show_wallet_manager_dialog
from gui.ui_dialogs import messagebox_compat as messagebox


def build_settings_tab(
    parent: tk.Frame | ttk.Frame,
    context: SettingsTabContext,
) -> SettingsTabBindings:
    return _build_settings_tab(
        parent,
        context,
        messagebox_module=messagebox,
        wallet_manager_dialog=show_wallet_manager_dialog,
    )
