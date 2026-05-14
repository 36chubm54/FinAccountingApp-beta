from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from dataclasses import dataclass
from tkinter import ttk
from typing import Any, Protocol


class DistributionTabContext(Protocol):
    controller: Any


@dataclass(slots=True)
class DistributionTabBindings:
    structure_tree: ttk.Treeview
    validation_label: ttk.Label
    period_from_var: tk.StringVar
    period_to_var: tk.StringVar
    results_tree: ttk.Treeview
    status_label: ttk.Label
    refresh: Callable[[], None]
