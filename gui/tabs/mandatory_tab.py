"""Compatibility shim for the mandatory tab."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from gui.tabs.mandatory import MandatoryTabBindings, MandatoryTabContext
from gui.tabs.mandatory.builder import build_mandatory_tab as _build_mandatory_tab
from gui.ui_dialogs import messagebox_compat as messagebox


def build_mandatory_tab(
    parent: tk.Frame | ttk.Frame,
    context: MandatoryTabContext,
    import_formats: dict[str, dict[str, str]],
) -> MandatoryTabBindings:
    return _build_mandatory_tab(
        parent,
        context,
        import_formats,
        messagebox_module=messagebox,
    )
