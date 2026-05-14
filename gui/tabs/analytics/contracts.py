from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from dataclasses import dataclass
from tkinter import ttk
from typing import Any, Protocol


class AnalyticsTabContext(Protocol):
    controller: Any

    def after(self, ms: int, func: Callable[[], None]) -> str: ...

    def after_cancel(self, id: str) -> None: ...


@dataclass(slots=True)
class AnalyticsTabBindings:
    period_from_entry: ttk.Entry
    period_to_entry: ttk.Entry
    net_worth_label: ttk.Label
    savings_rate_label: ttk.Label
    burn_rate_label: ttk.Label
    spending_tree: ttk.Treeview
    income_tree: ttk.Treeview
    category_canvas: tk.Canvas
    monthly_tree: ttk.Treeview
    timeline_canvas: tk.Canvas
    refresh: Callable[[], None]
    toggle_tag_mode: Callable[[], None]
