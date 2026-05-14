from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from tkinter import ttk
from typing import Any, Protocol


class DebtsTabContext(Protocol):
    controller: Any

    def _refresh_list(self) -> None: ...

    def _refresh_charts(self) -> None: ...

    def _refresh_wallets(self) -> None: ...

    def _refresh_all(self) -> None: ...


def refresh_debts_views(context: DebtsTabContext) -> None:
    for method_name in ("_refresh_list", "_refresh_charts", "_refresh_wallets", "_refresh_all"):
        method = getattr(context, method_name, None)
        if callable(method):
            method()


@dataclass(slots=True)
class DebtsTabBindings:
    debt_tree: ttk.Treeview
    history_tree: ttk.Treeview
    refresh: Callable[[], None]
    add_debt: Callable[[], None]
    pay_debt: Callable[[], None]
    write_off_debt: Callable[[], None]
    delete_debt: Callable[[], None]
