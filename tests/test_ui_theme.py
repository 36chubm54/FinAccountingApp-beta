from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from gui.ui_theme import bootstrap_ui, get_palette, get_theme, set_theme


def test_set_theme_switches_runtime_palette() -> None:
    set_theme("dark")
    assert get_theme() == "dark"
    assert get_palette().name == "dark"

    set_theme("light")
    assert get_theme() == "light"
    assert get_palette().name == "light"


def test_bootstrap_ui_supports_light_and_dark() -> None:
    root = tk.Tk()
    root.withdraw()
    try:
        bootstrap_ui(root, "light")
        light_style = ttk.Style(root)
        assert light_style.lookup("TFrame", "background")

        bootstrap_ui(root, "dark")
        dark_style = ttk.Style(root)
        assert dark_style.lookup("StatusBar.TFrame", "background")
        assert get_theme() == "dark"
    finally:
        root.destroy()
        set_theme("light")
