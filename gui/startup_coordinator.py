from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any, Protocol, TypeAlias

from bootstrap import run_post_startup_maintenance
from gui.logging_utils import log_ui_error


class StartupController(Protocol):
    def apply_mandatory_auto_payments(self) -> list[Any]: ...


class StartupRepository(Protocol):
    def load_all(self) -> list[Any]: ...


class BackgroundRunner(Protocol):
    def __call__(
        self,
        task: Callable[[], Any],
        *,
        on_success: Callable[[Any], None],
        on_error: Callable[[BaseException], None] | None = None,
        busy_message: str = "",
        block_ui: bool = True,
    ) -> None: ...


class IdleScheduler(Protocol):
    def __call__(self, key: str, callback: Callable[[], None]) -> str: ...


class DelayedScheduler(Protocol):
    def __call__(self, key: str, delay_ms: int, callback: Callable[[], None]) -> str: ...


RecordsRefreshCallback: TypeAlias = Callable[..., None]
AutoPaymentsMessageCallback: TypeAlias = Callable[[list[Any]], None]


class DeferredStartupCoordinator:
    _STEP_DELAY_MS = 24

    def __init__(
        self,
        *,
        controller: StartupController,
        repository: StartupRepository,
        run_background: BackgroundRunner,
        schedule_after_idle: IdleScheduler,
        schedule_after: DelayedScheduler,
        refresh_list: RecordsRefreshCallback,
        refresh_charts: RecordsRefreshCallback,
        refresh_budgets: Callable[[], None],
        refresh_all: Callable[[], None],
        apply_saved_online_mode: Callable[[], None],
        show_auto_payment_message: AutoPaymentsMessageCallback,
        restore_keyboard_focus: Callable[[], None],
        set_busy: Callable[[bool, str], None],
        logger: logging.Logger,
    ) -> None:
        self._controller = controller
        self._repository = repository
        self._run_background = run_background
        self._schedule_after_idle = schedule_after_idle
        self._schedule_after = schedule_after
        self._refresh_list = refresh_list
        self._refresh_charts = refresh_charts
        self._refresh_budgets = refresh_budgets
        self._refresh_all = refresh_all
        self._apply_saved_online_mode = apply_saved_online_mode
        self._show_auto_payment_message = show_auto_payment_message
        self._restore_keyboard_focus = restore_keyboard_focus
        self._set_busy = set_busy
        self._logger = logger
        self._running = False

    @property
    def running(self) -> bool:
        return self._running

    def start(self) -> None:
        if self._running:
            return
        self._running = True

        def task() -> tuple[list[Any], list[Any]]:
            created_auto_payments = self._controller.apply_mandatory_auto_payments()
            run_post_startup_maintenance()
            records = self._repository.load_all()
            return created_auto_payments, records

        def on_success(result: tuple[list[Any], list[Any]]) -> None:
            self._running = False
            self._set_busy(False, "")
            self._restore_keyboard_focus()
            created_auto_payments, records = result

            def _schedule_next_step(key: str, callback: Callable[[], None]) -> None:
                self._schedule_after(key, self._STEP_DELAY_MS, callback)

            def _refresh_list_step() -> None:
                self._refresh_list(records=records)
                _schedule_next_step("startup:refresh_charts", _refresh_charts_step)

            def _refresh_charts_step() -> None:
                self._refresh_charts(records=records)
                _schedule_next_step("startup:refresh_budgets", _refresh_budgets_step)

            def _refresh_budgets_step() -> None:
                self._refresh_budgets()
                _schedule_next_step("startup:refresh_all", _refresh_all_step)

            def _refresh_all_step() -> None:
                self._refresh_all()
                _schedule_next_step("startup:apply_online_mode", _apply_online_mode_step)

            def _apply_online_mode_step() -> None:
                self._apply_saved_online_mode()
                _schedule_next_step("startup:show_autopayments", _show_autopayments_step)

            def _show_autopayments_step() -> None:
                self._show_auto_payment_message(created_auto_payments)

            self._schedule_after_idle("startup:refresh_list", _refresh_list_step)

        def on_error(exc: BaseException) -> None:
            self._running = False
            self._set_busy(False, "")
            self._restore_keyboard_focus()
            self._logger.exception("Deferred startup sync failed", exc_info=exc)
            try:
                records = self._repository.load_all()
            except (RuntimeError, ValueError, TypeError, OSError) as load_error:
                log_ui_error(self._logger, "UI_APP_STARTUP_LOAD_FAILED", load_error)
                records = None
            if records is not None:
                self._refresh_list(records=records)
                self._refresh_charts(records=records)
            self._apply_saved_online_mode()

        self._run_background(
            task,
            on_success=on_success,
            on_error=on_error,
            busy_message="",
            block_ui=False,
        )
