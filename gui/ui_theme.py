from __future__ import annotations

import tkinter as tk
from tkinter import ttk

FONT_FAMILY = "Segoe UI"
FONT_SIZE = 10
HEADING_FONT = (FONT_FAMILY, 11, "bold")
SECTION_FONT = (FONT_FAMILY, 10, "bold")
METRIC_FONT = (FONT_FAMILY, 14, "bold")

BACKGROUND = "#eef4fb"
SURFACE = "#f9fbff"
SURFACE_ELEVATED = "#ffffff"
SURFACE_ALT = "#f2f7ff"
BORDER_SOFT = "#d8e3f2"
TEXT_PRIMARY = "#213247"
TEXT_MUTED = "#6b7f99"
ACCENT_BLUE = "#2f6fed"
ACCENT_BLUE_HOVER = "#5a8df2"
ACCENT_BLUE_ACTIVE = "#2459c9"
ROW_ALT = "#f5f9ff"

SUBTLE_TEXT = TEXT_MUTED
PRIMARY = ACCENT_BLUE
SUCCESS = "#2d7d6c"
WARNING = "#b6842f"
DANGER = "#b96a73"


def bootstrap_ui(root: tk.Misc) -> ttk.Style:
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass

    root["background"] = BACKGROUND
    root.option_add("*Font", (FONT_FAMILY, FONT_SIZE))
    root.option_add("*TCombobox*Listbox.font", (FONT_FAMILY, FONT_SIZE))
    root.option_add("*Menu.background", SURFACE_ELEVATED)
    root.option_add("*Menu.foreground", TEXT_PRIMARY)
    root.option_add("*Menu.activeBackground", "#dce9ff")
    root.option_add("*Menu.activeForeground", TEXT_PRIMARY)
    root.option_add("*Menu.borderWidth", 0)

    style.configure(".", font=(FONT_FAMILY, FONT_SIZE))
    style.configure("TFrame", background=BACKGROUND)
    style.configure(
        "TLabelframe",
        background=SURFACE,
        borderwidth=1,
        relief="solid",
        bordercolor=BORDER_SOFT,
        lightcolor=SURFACE,
        darkcolor=SURFACE,
    )
    style.configure(
        "TLabelframe.Label",
        font=SECTION_FONT,
        foreground=TEXT_PRIMARY,
        background=BACKGROUND,
    )
    style.configure("TLabel", background=BACKGROUND, foreground=TEXT_PRIMARY)
    style.configure(
        "Section.TLabel", font=HEADING_FONT, foreground=TEXT_PRIMARY, background=BACKGROUND
    )
    style.configure("Subtle.TLabel", foreground=SUBTLE_TEXT, background=BACKGROUND)
    style.configure(
        "Metric.TLabel", font=METRIC_FONT, foreground=TEXT_PRIMARY, background=BACKGROUND
    )
    style.configure("StatusMuted.TLabel", foreground=SUBTLE_TEXT, background=BACKGROUND)
    style.configure("StatusSuccess.TLabel", foreground=SUCCESS, background=BACKGROUND)
    style.configure("StatusWarning.TLabel", foreground=WARNING, background=BACKGROUND)
    style.configure("StatusDanger.TLabel", foreground=DANGER, background=BACKGROUND)

    style.configure(
        "TButton",
        padding=(8, 5),
        background=SURFACE_ELEVATED,
        foreground=TEXT_PRIMARY,
        borderwidth=1,
        relief="flat",
        focusthickness=0,
    )
    style.map(
        "TButton",
        background=[("active", SURFACE_ALT), ("pressed", SURFACE_ALT)],
        bordercolor=[("!disabled", BORDER_SOFT)],
    )
    style.configure("Primary.TButton", padding=(12, 7), background=PRIMARY, foreground="#ffffff")
    style.map(
        "Primary.TButton",
        background=[
            ("active", ACCENT_BLUE_HOVER),
            ("pressed", ACCENT_BLUE_ACTIVE),
            ("!disabled", PRIMARY),
        ],
        foreground=[("!disabled", "#ffffff")],
    )
    style.configure(
        "TMenubutton",
        padding=(8, 5),
        background=SURFACE_ELEVATED,
        foreground=TEXT_PRIMARY,
        borderwidth=1,
        relief="flat",
        arrowcolor=TEXT_MUTED,
    )
    style.map(
        "TMenubutton",
        background=[("active", SURFACE_ALT), ("pressed", SURFACE_ALT)],
        bordercolor=[("!disabled", BORDER_SOFT)],
    )

    style.configure(
        "TEntry",
        padding=(6, 5),
        fieldbackground=SURFACE_ELEVATED,
        foreground=TEXT_PRIMARY,
        bordercolor=BORDER_SOFT,
        lightcolor=BORDER_SOFT,
        darkcolor=BORDER_SOFT,
    )
    style.map("TEntry", bordercolor=[("focus", ACCENT_BLUE)], lightcolor=[("focus", ACCENT_BLUE)])
    style.configure(
        "TCombobox",
        padding=(4, 4),
        fieldbackground=SURFACE_ELEVATED,
        background=SURFACE_ELEVATED,
        foreground=TEXT_PRIMARY,
        bordercolor=BORDER_SOFT,
        arrowsize=14,
    )
    style.map(
        "TCombobox",
        fieldbackground=[("readonly", SURFACE_ELEVATED)],
        bordercolor=[("focus", ACCENT_BLUE)],
        lightcolor=[("focus", ACCENT_BLUE)],
    )
    style.configure(
        "TCheckbutton",
        background=BACKGROUND,
        foreground=TEXT_PRIMARY,
        indicatorbackground=SURFACE_ELEVATED,
        indicatorforeground=ACCENT_BLUE,
        indicatormargin=4,
        focuscolor=BACKGROUND,
    )
    style.map(
        "TCheckbutton",
        background=[("active", BACKGROUND), ("pressed", BACKGROUND)],
        foreground=[("active", TEXT_PRIMARY), ("pressed", TEXT_PRIMARY)],
        indicatorbackground=[
            ("selected", ACCENT_BLUE),
            ("active", SURFACE_ALT),
            ("pressed", SURFACE_ALT),
        ],
        indicatorforeground=[("selected", "#ffffff")],
    )
    style.configure(
        "TRadiobutton",
        background=BACKGROUND,
        foreground=TEXT_PRIMARY,
        indicatorbackground=SURFACE_ELEVATED,
        indicatorforeground=ACCENT_BLUE,
        indicatormargin=4,
        focuscolor=BACKGROUND,
    )
    style.map(
        "TRadiobutton",
        background=[("active", BACKGROUND), ("pressed", BACKGROUND)],
        foreground=[("active", TEXT_PRIMARY), ("pressed", TEXT_PRIMARY)],
        indicatorbackground=[
            ("selected", ACCENT_BLUE),
            ("active", SURFACE_ALT),
            ("pressed", SURFACE_ALT),
        ],
        indicatorforeground=[("selected", "#ffffff")],
    )
    style.configure(
        "Vertical.TScrollbar",
        troughcolor=SURFACE_ALT,
        background="#d7e5fb",
        arrowcolor=TEXT_MUTED,
        bordercolor=BORDER_SOFT,
        lightcolor=SURFACE_ALT,
        darkcolor=SURFACE_ALT,
        gripcount=0,
        arrowsize=12,
    )
    style.configure(
        "Horizontal.TScrollbar",
        troughcolor=SURFACE_ALT,
        background="#d7e5fb",
        arrowcolor=TEXT_MUTED,
        bordercolor=BORDER_SOFT,
        lightcolor=SURFACE_ALT,
        darkcolor=SURFACE_ALT,
        gripcount=0,
        arrowsize=12,
    )
    style.map(
        "Vertical.TScrollbar",
        background=[("active", "#c6daf8"), ("pressed", "#b5cff6")],
    )
    style.map(
        "Horizontal.TScrollbar",
        background=[("active", "#c6daf8"), ("pressed", "#b5cff6")],
    )

    style.configure(
        "Treeview",
        rowheight=26,
        font=(FONT_FAMILY, FONT_SIZE),
        fieldbackground=SURFACE_ELEVATED,
        background=SURFACE_ELEVATED,
        foreground=TEXT_PRIMARY,
        borderwidth=0,
    )
    style.map(
        "Treeview",
        background=[("selected", "#dce9ff")],
        foreground=[("selected", TEXT_PRIMARY)],
    )
    style.configure(
        "Treeview.Heading",
        font=(FONT_FAMILY, FONT_SIZE, "bold"),
        padding=(8, 6),
        background=SURFACE_ALT,
        foreground=TEXT_PRIMARY,
        borderwidth=1,
        relief="flat",
    )
    style.map(
        "Treeview.Heading",
        background=[("active", "#e8f1ff"), ("pressed", "#dce9ff")],
        foreground=[("active", TEXT_PRIMARY), ("pressed", TEXT_PRIMARY)],
        bordercolor=[("active", BORDER_SOFT), ("pressed", ACCENT_BLUE)],
        lightcolor=[("active", "#e8f1ff"), ("pressed", "#dce9ff")],
        darkcolor=[("active", "#e8f1ff"), ("pressed", "#dce9ff")],
    )

    style.configure("TNotebook", background=BACKGROUND, borderwidth=0, tabmargins=(8, 6, 8, 0))
    style.configure(
        "TNotebook.Tab",
        padding=(10, 5),
        font=(FONT_FAMILY, FONT_SIZE),
        background=SURFACE_ALT,
        foreground=TEXT_MUTED,
        borderwidth=0,
    )
    style.map(
        "TNotebook.Tab",
        background=[("selected", SURFACE_ELEVATED), ("active", "#e8f1ff")],
        foreground=[("selected", TEXT_PRIMARY), ("active", TEXT_PRIMARY)],
    )

    style.configure(
        "TPanedwindow",
        background=BACKGROUND,
        borderwidth=0,
        sashthickness=10,
        relief="flat",
        sashrelief="flat",
        gripcount=0,
        handlesize=0,
    )
    style.configure(
        "Reports.TPanedwindow",
        background=BACKGROUND,
        borderwidth=0,
        sashthickness=10,
        relief="flat",
        sashrelief="flat",
        gripcount=0,
        handlesize=0,
    )

    style.configure(
        "StatusBar.TFrame",
        background=SURFACE_ELEVATED,
        borderwidth=1,
        relief="flat",
        bordercolor=BORDER_SOFT,
        lightcolor=SURFACE_ELEVATED,
        darkcolor=SURFACE_ELEVATED,
    )
    style.configure("StatusBar.TLabel", background=SURFACE_ELEVATED, foreground=TEXT_PRIMARY)
    style.configure(
        "StatusBarMuted.TLabel",
        background=SURFACE_ELEVATED,
        foreground=TEXT_MUTED,
    )
    style.configure("StatusBar.TSeparator", background=BORDER_SOFT)

    style.configure(
        "StatusBar.TCheckbutton",
        background=SURFACE_ELEVATED,
        foreground=TEXT_PRIMARY,
        indicatorbackground=SURFACE_ELEVATED,
        indicatorforeground=ACCENT_BLUE,
        focuscolor=SURFACE_ELEVATED,
    )
    style.map(
        "StatusBar.TCheckbutton",
        background=[("active", SURFACE_ELEVATED), ("pressed", SURFACE_ELEVATED)],
        foreground=[("active", TEXT_PRIMARY), ("pressed", TEXT_PRIMARY)],
        indicatorbackground=[
            ("selected", ACCENT_BLUE),
            ("active", SURFACE_ALT),
            ("pressed", SURFACE_ALT),
        ],
        indicatorforeground=[("selected", "#ffffff")],
    )
    style.configure(
        "InlinePanel.TFrame",
        background=BACKGROUND,
        borderwidth=1,
        relief="flat",
        bordercolor=BORDER_SOFT,
        lightcolor=BACKGROUND,
        darkcolor=BACKGROUND,
    )
    style.configure("TProgressbar", troughcolor=SURFACE_ALT, background=ACCENT_BLUE, borderwidth=0)
    return style
