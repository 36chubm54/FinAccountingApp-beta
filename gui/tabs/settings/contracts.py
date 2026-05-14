"""Public contracts for the settings tab."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol

from gui.i18n import tr


class SettingsTabContext(Protocol):
    controller: Any
    repository: Any
    refresh_operation_wallet_menu: Callable[[], None] | None
    refresh_transfer_wallet_menus: Callable[[], None] | None
    refresh_wallets: Callable[[], None] | None
    refresh_mandatory: Callable[[], None] | None

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
