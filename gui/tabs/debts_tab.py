"""Compatibility shim for the debts tab."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from gui.tabs.debts.builder import build_debts_tab as _build_debts_tab
from gui.tabs.debts.contracts import DebtsTabBindings, DebtsTabContext, refresh_debts_views
from gui.tabs.debts.render import _draw_debt_progress, _segment_widths
from gui.ui_dialogs import messagebox_compat as messagebox


def build_debts_tab(
    parent: tk.Frame | ttk.Frame,
    *,
    context: DebtsTabContext,
) -> DebtsTabBindings:
    return _build_debts_tab(parent, context=context, messagebox_module=messagebox)


__all__ = [
    "DebtsTabBindings",
    "DebtsTabContext",
    "build_debts_tab",
    "refresh_debts_views",
    "_segment_widths",
    "_draw_debt_progress",
    "messagebox",
]
