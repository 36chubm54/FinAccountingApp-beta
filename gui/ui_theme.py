from __future__ import annotations

import tkinter as tk
from dataclasses import dataclass
from tkinter import ttk

FONT_FAMILY = "Segoe UI"
FONT_SIZE = 10
HEADING_FONT = (FONT_FAMILY, 11, "bold")
SECTION_FONT = (FONT_FAMILY, 10, "bold")
METRIC_FONT = (FONT_FAMILY, 14, "bold")
DEFAULT_THEME = "light"


@dataclass(frozen=True)
class ThemePalette:
    name: str
    background: str
    surface: str
    surface_elevated: str
    surface_alt: str
    border_soft: str
    text_primary: str
    text_muted: str
    accent_blue: str
    accent_blue_hover: str
    accent_blue_active: str
    row_alt: str
    success: str
    warning: str
    danger: str
    success_tint: str
    warning_tint: str
    danger_tint: str
    chart_grid: str
    chart_axis: str
    chart_empty: str
    chart_text: str
    chart_income: str
    chart_expense: str
    chart_outline: str
    chart_series: tuple[str, ...]


THEMES: dict[str, ThemePalette] = {
    "light": ThemePalette(
        name="light",
        background="#eef4fb",
        surface="#f9fbff",
        surface_elevated="#ffffff",
        surface_alt="#f2f7ff",
        border_soft="#d8e3f2",
        text_primary="#213247",
        text_muted="#6b7f99",
        accent_blue="#2f6fed",
        accent_blue_hover="#5a8df2",
        accent_blue_active="#2459c9",
        row_alt="#f5f9ff",
        success="#2d7d6c",
        warning="#b6842f",
        danger="#b96a73",
        success_tint="#e8f6f1",
        warning_tint="#fcf5e6",
        danger_tint="#f9e9ec",
        chart_grid="#d1d5db",
        chart_axis="#d1d5db",
        chart_empty="#6b7280",
        chart_text="#1f2937",
        chart_income="#10b981",
        chart_expense="#ef4444",
        chart_outline="#ffffff",
        chart_series=(
            "#4f46e5",
            "#06b6d4",
            "#f59e0b",
            "#10b981",
            "#ec4899",
            "#8b5cf6",
            "#14b8a6",
            "#ef4444",
            "#f97316",
            "#22c55e",
            "#0ea5e9",
            "#a855f7",
        ),
    ),
    "dark": ThemePalette(
        name="dark",
        background="#0f1727",
        surface="#162033",
        surface_elevated="#1b2740",
        surface_alt="#22304d",
        border_soft="#31415f",
        text_primary="#edf4ff",
        text_muted="#9db0cc",
        accent_blue="#67a2ff",
        accent_blue_hover="#7eb1ff",
        accent_blue_active="#4f8df0",
        row_alt="#182338",
        success="#43b99d",
        warning="#d8ab4a",
        danger="#d98896",
        success_tint="#15352f",
        warning_tint="#3a301c",
        danger_tint="#40242d",
        chart_grid="#31415f",
        chart_axis="#40516f",
        chart_empty="#9db0cc",
        chart_text="#edf4ff",
        chart_income="#37d0a0",
        chart_expense="#ff7a88",
        chart_outline="#162033",
        chart_series=(
            "#76a7ff",
            "#36c4e0",
            "#f7b955",
            "#46d39a",
            "#ff86c4",
            "#a68bff",
            "#31d1c4",
            "#ff7a88",
            "#ff9f57",
            "#71d765",
            "#42bbff",
            "#cb7dff",
        ),
    ),
}

_current_theme = DEFAULT_THEME

BACKGROUND = THEMES[DEFAULT_THEME].background
SURFACE = THEMES[DEFAULT_THEME].surface
SURFACE_ELEVATED = THEMES[DEFAULT_THEME].surface_elevated
SURFACE_ALT = THEMES[DEFAULT_THEME].surface_alt
BORDER_SOFT = THEMES[DEFAULT_THEME].border_soft
TEXT_PRIMARY = THEMES[DEFAULT_THEME].text_primary
TEXT_MUTED = THEMES[DEFAULT_THEME].text_muted
ACCENT_BLUE = THEMES[DEFAULT_THEME].accent_blue
ACCENT_BLUE_HOVER = THEMES[DEFAULT_THEME].accent_blue_hover
ACCENT_BLUE_ACTIVE = THEMES[DEFAULT_THEME].accent_blue_active
ROW_ALT = THEMES[DEFAULT_THEME].row_alt
SUBTLE_TEXT = THEMES[DEFAULT_THEME].text_muted
PRIMARY = THEMES[DEFAULT_THEME].accent_blue
SUCCESS = THEMES[DEFAULT_THEME].success
WARNING = THEMES[DEFAULT_THEME].warning
DANGER = THEMES[DEFAULT_THEME].danger


def get_theme() -> str:
    return _current_theme


def get_palette(theme_name: str | None = None) -> ThemePalette:
    normalized = str(theme_name or _current_theme or DEFAULT_THEME).strip().lower() or DEFAULT_THEME
    return THEMES.get(normalized, THEMES[DEFAULT_THEME])


def _sync_compat_globals(palette: ThemePalette) -> None:
    global BACKGROUND
    global SURFACE
    global SURFACE_ELEVATED
    global SURFACE_ALT
    global BORDER_SOFT
    global TEXT_PRIMARY
    global TEXT_MUTED
    global ACCENT_BLUE
    global ACCENT_BLUE_HOVER
    global ACCENT_BLUE_ACTIVE
    global ROW_ALT
    global SUBTLE_TEXT
    global PRIMARY
    global SUCCESS
    global WARNING
    global DANGER

    BACKGROUND = palette.background
    SURFACE = palette.surface
    SURFACE_ELEVATED = palette.surface_elevated
    SURFACE_ALT = palette.surface_alt
    BORDER_SOFT = palette.border_soft
    TEXT_PRIMARY = palette.text_primary
    TEXT_MUTED = palette.text_muted
    ACCENT_BLUE = palette.accent_blue
    ACCENT_BLUE_HOVER = palette.accent_blue_hover
    ACCENT_BLUE_ACTIVE = palette.accent_blue_active
    ROW_ALT = palette.row_alt
    SUBTLE_TEXT = palette.text_muted
    PRIMARY = palette.accent_blue
    SUCCESS = palette.success
    WARNING = palette.warning
    DANGER = palette.danger


def set_theme(name: str) -> str:
    global _current_theme
    normalized = str(name or "").strip().lower() or DEFAULT_THEME
    if normalized not in THEMES:
        normalized = DEFAULT_THEME
    _current_theme = normalized
    _sync_compat_globals(THEMES[_current_theme])
    return _current_theme


def bootstrap_ui(root: tk.Misc, theme_name: str | None = None) -> ttk.Style:
    theme = set_theme(theme_name or _current_theme)
    palette = get_palette(theme)
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass

    root["background"] = palette.background
    root.option_add("*Font", (FONT_FAMILY, FONT_SIZE))
    root.option_add("*TCombobox*Listbox.font", (FONT_FAMILY, FONT_SIZE))
    root.option_add("*TCombobox*Listbox.background", palette.surface_elevated)
    root.option_add("*TCombobox*Listbox.foreground", palette.text_primary)
    root.option_add("*TCombobox*Listbox.selectBackground", palette.accent_blue)
    root.option_add("*TCombobox*Listbox.selectForeground", palette.surface_elevated)
    root.option_add("*Menu.background", palette.surface_elevated)
    root.option_add("*Menu.foreground", palette.text_primary)
    root.option_add("*Menu.activeBackground", palette.surface_alt)
    root.option_add("*Menu.activeForeground", palette.text_primary)
    root.option_add("*Menu.borderWidth", 0)

    style.configure(".", font=(FONT_FAMILY, FONT_SIZE))
    style.configure("TFrame", background=palette.background)
    style.configure(
        "TLabelframe",
        background=palette.surface,
        borderwidth=1,
        relief="solid",
        bordercolor=palette.border_soft,
        lightcolor=palette.surface,
        darkcolor=palette.surface,
    )
    style.configure(
        "TLabelframe.Label",
        font=SECTION_FONT,
        foreground=palette.text_primary,
        background=palette.background,
    )
    style.configure("TLabel", background=palette.background, foreground=palette.text_primary)
    style.configure(
        "Section.TLabel",
        font=HEADING_FONT,
        foreground=palette.text_primary,
        background=palette.background,
    )
    style.configure("Subtle.TLabel", foreground=palette.text_muted, background=palette.background)
    style.configure(
        "Metric.TLabel",
        font=METRIC_FONT,
        foreground=palette.text_primary,
        background=palette.background,
    )
    style.configure(
        "StatusMuted.TLabel", foreground=palette.text_muted, background=palette.background
    )
    style.configure(
        "StatusSuccess.TLabel", foreground=palette.success, background=palette.background
    )
    style.configure(
        "StatusWarning.TLabel", foreground=palette.warning, background=palette.background
    )
    style.configure("StatusDanger.TLabel", foreground=palette.danger, background=palette.background)

    style.configure(
        "TButton",
        padding=(8, 5),
        background=palette.surface_elevated,
        foreground=palette.text_primary,
        borderwidth=1,
        relief="flat",
        focusthickness=0,
    )
    style.map(
        "TButton",
        background=[("active", palette.surface_alt), ("pressed", palette.surface_alt)],
        bordercolor=[("!disabled", palette.border_soft)],
        foreground=[("disabled", palette.text_muted)],
    )
    style.configure(
        "Primary.TButton",
        padding=(12, 7),
        background=palette.accent_blue,
        foreground=palette.surface_elevated,
    )
    style.map(
        "Primary.TButton",
        background=[
            ("active", palette.accent_blue_hover),
            ("pressed", palette.accent_blue_active),
            ("!disabled", palette.accent_blue),
        ],
        foreground=[("!disabled", palette.surface_elevated)],
    )
    style.configure(
        "TMenubutton",
        padding=(8, 5),
        background=palette.surface_elevated,
        foreground=palette.text_primary,
        borderwidth=1,
        relief="flat",
        arrowcolor=palette.text_muted,
    )
    style.map(
        "TMenubutton",
        background=[("active", palette.surface_alt), ("pressed", palette.surface_alt)],
        bordercolor=[("!disabled", palette.border_soft)],
    )

    style.configure(
        "TEntry",
        padding=(6, 5),
        fieldbackground=palette.surface_elevated,
        foreground=palette.text_primary,
        insertcolor=palette.text_primary,
        bordercolor=palette.border_soft,
        lightcolor=palette.border_soft,
        darkcolor=palette.border_soft,
    )
    style.map(
        "TEntry",
        bordercolor=[("focus", palette.accent_blue)],
        lightcolor=[("focus", palette.accent_blue)],
    )
    style.configure(
        "TCombobox",
        padding=(4, 4),
        fieldbackground=palette.surface_elevated,
        background=palette.surface_elevated,
        foreground=palette.text_primary,
        arrowcolor=palette.text_muted,
        bordercolor=palette.border_soft,
        arrowsize=14,
    )
    style.map(
        "TCombobox",
        fieldbackground=[("readonly", palette.surface_elevated)],
        selectbackground=[("readonly", palette.surface_elevated)],
        selectforeground=[("readonly", palette.text_primary)],
        bordercolor=[("focus", palette.accent_blue)],
        lightcolor=[("focus", palette.accent_blue)],
    )
    style.configure(
        "StatusBar.TCombobox",
        padding=(3, 2),
        fieldbackground=palette.surface_elevated,
        background=palette.surface_elevated,
        foreground=palette.text_primary,
        arrowcolor=palette.text_muted,
        bordercolor=palette.border_soft,
        arrowsize=12,
    )
    style.map(
        "StatusBar.TCombobox",
        fieldbackground=[("readonly", palette.surface_elevated)],
        selectbackground=[("readonly", palette.surface_elevated)],
        selectforeground=[("readonly", palette.text_primary)],
        bordercolor=[("focus", palette.accent_blue)],
        lightcolor=[("focus", palette.accent_blue)],
    )

    style.configure(
        "TCheckbutton",
        background=palette.background,
        foreground=palette.text_primary,
        indicatorbackground=palette.surface_elevated,
        indicatorforeground=palette.accent_blue,
        indicatormargin=4,
        focuscolor=palette.background,
    )
    style.map(
        "TCheckbutton",
        background=[("active", palette.background), ("pressed", palette.background)],
        foreground=[("active", palette.text_primary), ("pressed", palette.text_primary)],
        indicatorbackground=[
            ("selected", palette.accent_blue),
            ("active", palette.surface_alt),
            ("pressed", palette.surface_alt),
        ],
        indicatorforeground=[("selected", palette.surface_elevated)],
    )
    style.configure(
        "TRadiobutton",
        background=palette.background,
        foreground=palette.text_primary,
        indicatorbackground=palette.surface_elevated,
        indicatorforeground=palette.accent_blue,
        indicatormargin=4,
        focuscolor=palette.background,
    )
    style.map(
        "TRadiobutton",
        background=[("active", palette.background), ("pressed", palette.background)],
        foreground=[("active", palette.text_primary), ("pressed", palette.text_primary)],
        indicatorbackground=[
            ("selected", palette.accent_blue),
            ("active", palette.surface_alt),
            ("pressed", palette.surface_alt),
        ],
        indicatorforeground=[("selected", palette.surface_elevated)],
    )

    for scrollbar_style in ("Vertical.TScrollbar", "Horizontal.TScrollbar"):
        style.configure(
            scrollbar_style,
            troughcolor=palette.surface_alt,
            background=palette.surface,
            arrowcolor=palette.text_muted,
            bordercolor=palette.border_soft,
            lightcolor=palette.surface_alt,
            darkcolor=palette.surface_alt,
            gripcount=0,
            arrowsize=12,
        )
        style.map(
            scrollbar_style,
            background=[("active", palette.surface_elevated), ("pressed", palette.surface)],
        )

    style.configure(
        "Treeview",
        rowheight=26,
        font=(FONT_FAMILY, FONT_SIZE),
        fieldbackground=palette.surface_elevated,
        background=palette.surface_elevated,
        foreground=palette.text_primary,
        borderwidth=0,
    )
    style.map(
        "Treeview",
        background=[("selected", palette.surface_alt)],
        foreground=[("selected", palette.text_primary)],
    )
    style.configure(
        "Treeview.Heading",
        font=(FONT_FAMILY, FONT_SIZE, "bold"),
        padding=(8, 6),
        background=palette.surface_alt,
        foreground=palette.text_primary,
        borderwidth=1,
        relief="flat",
    )
    style.map(
        "Treeview.Heading",
        background=[("active", palette.surface), ("pressed", palette.surface_alt)],
        foreground=[("active", palette.text_primary), ("pressed", palette.text_primary)],
        bordercolor=[("active", palette.border_soft), ("pressed", palette.accent_blue)],
        lightcolor=[("active", palette.surface), ("pressed", palette.surface_alt)],
        darkcolor=[("active", palette.surface), ("pressed", palette.surface_alt)],
    )

    style.configure(
        "TNotebook",
        background=palette.background,
        borderwidth=0,
        tabmargins=(8, 6, 8, 0),
    )
    style.configure(
        "TNotebook.Tab",
        padding=(10, 5),
        font=(FONT_FAMILY, FONT_SIZE),
        background=palette.surface_alt,
        foreground=palette.text_muted,
        borderwidth=0,
    )
    style.map(
        "TNotebook.Tab",
        background=[("selected", palette.surface_elevated), ("active", palette.surface)],
        foreground=[("selected", palette.text_primary), ("active", palette.text_primary)],
    )

    for paned_style in ("TPanedwindow", "Reports.TPanedwindow"):
        style.configure(
            paned_style,
            background=palette.background,
            borderwidth=0,
            sashthickness=10,
            relief="flat",
            sashrelief="flat",
            gripcount=0,
            handlesize=0,
        )

    style.configure(
        "StatusBar.TFrame",
        background=palette.surface_elevated,
        borderwidth=1,
        relief="flat",
        bordercolor=palette.border_soft,
        lightcolor=palette.surface_elevated,
        darkcolor=palette.surface_elevated,
    )
    style.configure(
        "StatusBar.TLabel",
        background=palette.surface_elevated,
        foreground=palette.text_primary,
    )
    style.configure(
        "StatusBarMuted.TLabel",
        background=palette.surface_elevated,
        foreground=palette.text_muted,
    )
    style.configure("StatusBar.TSeparator", background=palette.border_soft)
    style.configure(
        "StatusBar.TCheckbutton",
        background=palette.surface_elevated,
        foreground=palette.text_primary,
        indicatorbackground=palette.surface_elevated,
        indicatorforeground=palette.accent_blue,
        focuscolor=palette.surface_elevated,
    )
    style.map(
        "StatusBar.TCheckbutton",
        background=[("active", palette.surface_elevated), ("pressed", palette.surface_elevated)],
        foreground=[("active", palette.text_primary), ("pressed", palette.text_primary)],
        indicatorbackground=[
            ("selected", palette.accent_blue),
            ("active", palette.surface_alt),
            ("pressed", palette.surface_alt),
        ],
        indicatorforeground=[("selected", palette.surface_elevated)],
    )
    style.configure(
        "InlinePanel.TFrame",
        background=palette.background,
        borderwidth=1,
        relief="flat",
        bordercolor=palette.border_soft,
        lightcolor=palette.background,
        darkcolor=palette.background,
    )
    style.configure(
        "TProgressbar",
        troughcolor=palette.surface_alt,
        background=palette.accent_blue,
        borderwidth=0,
    )
    return style
