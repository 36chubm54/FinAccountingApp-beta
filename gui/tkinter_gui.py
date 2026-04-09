import logging
import tkinter as tk
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from datetime import date, datetime
from pathlib import Path
from tkinter import ttk
from typing import Any

from app.services import CurrencyService
from bootstrap import bootstrap_repository, run_post_startup_maintenance
from domain.import_policy import ImportPolicy
from gui.controllers import FinancialController
from gui.i18n import tr
from gui.record_colors import KIND_TO_FOREGROUND, foreground_for_kind
from gui.ui_helpers import show_error, show_info
from gui.ui_text import app_title, get_import_formats, get_tab_titles
from gui.ui_theme import bootstrap_ui
from utils.charting import (
    aggregate_daily_cashflow,
    aggregate_expenses_by_category,
    aggregate_monthly_cashflow,
    extract_months,
    extract_years,
)
from version import __version__

logger = logging.getLogger(__name__)


class FinancialApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        bootstrap_ui(self)

        icons_dir = Path(__file__).resolve().parent / "assets" / "icons"
        ico_path = icons_dir / "app.ico"
        png_path = icons_dir / "app.png"

        try:
            # Windows native icon
            if ico_path.exists():
                self.iconbitmap(default=str(ico_path))
        except Exception:
            pass

        try:
            # Tk fallback (and for other OS)
            if png_path.exists():
                app_icon = tk.PhotoImage(file=str(png_path))
                self.iconphoto(True, app_icon)
                self._app_icon_ref = app_icon  # so that GC does not gather
        except Exception:
            pass

        self._import_formats = get_import_formats()
        self.title(app_title())
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        min_width = min(1440, int(screen_w * 0.8))
        min_height = min(880, int(screen_h * 0.82))
        self.geometry(f"{min_width}x{min_height}")
        self.minsize(min_width, min_height)
        # Make shutdown explicit: ensures background executor and repository are closed
        # when user closes the window via the window manager.
        self.protocol("WM_DELETE_WINDOW", self.destroy)

        self.repository = bootstrap_repository(run_maintenance=False)
        self.currency = CurrencyService()
        self.controller = FinancialController(self.repository, self.currency)

        self._executor = ThreadPoolExecutor(max_workers=2)
        self._busy = False
        self._startup_sync_running = False
        self._record_id_to_repo_index: dict[str, int] = {}
        self._record_id_to_domain_id: dict[str, int] = {}
        self._chart_refresh_suspended = False
        self._built_tabs: set[str] = set()
        self._analytics_bindings: Any | None = None
        self._dashboard_bindings: Any | None = None
        self._budget_bindings: Any | None = None
        self._debt_bindings: Any | None = None
        self._distribution_bindings: Any | None = None

        self.records_tree: ttk.Treeview | None = None
        self.refresh_operation_wallet_menu: Callable[[], None] | None = None
        self.refresh_transfer_wallet_menus: Callable[[], None] | None = None
        self.refresh_wallets: Callable[[], None] | None = None
        self.refresh_budgets: Callable[[], None] | None = None
        self.refresh_all: Callable[[], None] | None = None
        self._status_refresh_job: str | None = None
        self._online_var: tk.BooleanVar | None = None
        self._currency_status_label: ttk.Label | None = None
        self._price_status_label: ttk.Label | None = None
        self._online_toggle_running = False

        self.pie_month_var: tk.StringVar | None = None
        self.pie_month_menu: ttk.OptionMenu | None = None
        self.chart_month_var: tk.StringVar | None = None
        self.chart_month_menu: ttk.OptionMenu | None = None
        self.chart_year_var: tk.StringVar | None = None
        self.chart_year_menu: ttk.OptionMenu | None = None
        self.expense_pie_canvas: tk.Canvas | None = None
        self.expense_legend_canvas: tk.Canvas | None = None
        self.expense_legend_frame: tk.Widget | None = None
        self.daily_bar_canvas: tk.Canvas | None = None
        self.monthly_bar_canvas: tk.Canvas | None = None

        self._status_bar = self._build_status_bar()
        self._status_bar.pack(side=tk.BOTTOM, fill=tk.X)

        notebook = ttk.Notebook(self)
        notebook.pack(fill=tk.BOTH, expand=True)
        self._notebook = notebook

        self.tab_infographics = ttk.Frame(notebook)
        self.tab_operations = ttk.Frame(notebook)
        self.tab_reports = ttk.Frame(notebook)
        self.tab_analytics = ttk.Frame(notebook)
        self.tab_dashboard = ttk.Frame(notebook)
        self.tab_budget = ttk.Frame(notebook)
        self.tab_debts = ttk.Frame(notebook)
        self.tab_distribution = ttk.Frame(notebook)
        self.tab_settings = ttk.Frame(notebook)

        tab_titles = get_tab_titles()
        notebook.add(self.tab_infographics, text=tab_titles["infographics"])
        notebook.add(self.tab_operations, text=tab_titles["operations"])
        notebook.add(self.tab_reports, text=tab_titles["reports"])
        notebook.add(self.tab_analytics, text=tab_titles["analytics"])
        notebook.add(self.tab_dashboard, text=tab_titles["dashboard"])
        notebook.add(self.tab_budget, text=tab_titles["budget"])
        notebook.add(self.tab_debts, text=tab_titles["debts"])
        notebook.add(self.tab_distribution, text=tab_titles["distribution"])
        notebook.add(self.tab_settings, text=tab_titles["settings"])
        self._tab_keys_by_widget = {
            str(self.tab_infographics): "infographics",
            str(self.tab_operations): "operations",
            str(self.tab_reports): "reports",
            str(self.tab_analytics): "analytics",
            str(self.tab_dashboard): "dashboard",
            str(self.tab_budget): "budget",
            str(self.tab_debts): "debts",
            str(self.tab_distribution): "distribution",
            str(self.tab_settings): "settings",
        }
        notebook.bind("<<NotebookTabChanged>>", self._on_tab_changed, add="+")

        self._ensure_tab_built("infographics")
        self._ensure_tab_built("operations")

        self.progress = ttk.Progressbar(self, mode="indeterminate")
        self.progress.pack(fill=tk.X, padx=8, pady=(0, 8))
        self.progress.pack_forget()

        self.after_idle(self._start_deferred_startup)

    def destroy(self) -> None:
        if self._status_refresh_job is not None:
            try:
                self.after_cancel(self._status_refresh_job)
            except Exception:
                pass
        self._executor.shutdown(wait=False, cancel_futures=True)
        close_method = getattr(self.repository, "close", None)
        if callable(close_method):
            close_method()
        super().destroy()

    def reload_strings(self) -> None:
        self._import_formats = get_import_formats()
        self.title(app_title())
        if hasattr(self, "_notebook"):
            tab_titles = get_tab_titles()
            for tab_widget, key in (
                (self.tab_infographics, "infographics"),
                (self.tab_operations, "operations"),
                (self.tab_reports, "reports"),
                (self.tab_analytics, "analytics"),
                (self.tab_dashboard, "dashboard"),
                (self.tab_budget, "budget"),
                (self.tab_debts, "debts"),
                (self.tab_distribution, "distribution"),
                (self.tab_settings, "settings"),
            ):
                self._notebook.tab(tab_widget, text=tab_titles[key])
        if self._currency_status_label is not None and not self._online_toggle_running:
            self._currency_status_label.config(
                text=tr("app.status.currency_offline", "Курсы: офлайн")
            )
        if self._price_status_label is not None:
            self._price_status_label.config(
                text=tr("app.status.prices_local", "Цены активов: локально")
            )

    def _set_busy(self, busy: bool, message: str = "") -> None:
        self._busy = busy
        try:
            self.attributes("-disabled", busy)
        except Exception:
            pass
        if busy:
            self.progress.pack(fill=tk.X, padx=8, pady=(0, 8))
            self.progress.start(12)
            base_title = app_title()
            self.title(f"{base_title} - {message}" if message else base_title)
            self.config(cursor="watch")
        else:
            self.progress.stop()
            self.progress.pack_forget()
            self.title(app_title())
            self.config(cursor="")

    def _run_background(
        self,
        task: Callable[[], Any],
        *,
        on_success: Callable[[Any], None],
        on_error: Callable[[BaseException], None] | None = None,
        busy_message: str = tr("app.busy.default", "Выполняется операция..."),
        block_ui: bool = True,
    ) -> None:
        if block_ui and self._busy:
            show_info(
                tr("app.wait_running", "Дождитесь завершения текущей операции."),
                title=tr("app.wait", "Подождите"),
            )
            return
        if block_ui:
            self._set_busy(True, busy_message)
        future: Future[Any] = self._executor.submit(task)

        def _poll() -> None:
            if not future.done():
                self.after(100, _poll)
                return
            if block_ui:
                self._set_busy(False)
            error = future.exception()
            if error is not None:
                if on_error is not None:
                    on_error(error)
                else:
                    logger.exception("Background operation failed", exc_info=error)
                    show_error(str(error))
                return
            on_success(future.result())

        self.after(100, _poll)

    def _build_status_bar(self) -> ttk.Frame:
        bar = ttk.Frame(self, style="StatusBar.TFrame", padding=(0, 1))
        bar.grid_columnconfigure(4, weight=1)
        self._online_var = tk.BooleanVar(value=False)
        online_check = ttk.Checkbutton(
            bar,
            text=tr("app.status.online", "Онлайн"),
            variable=self._online_var,
            command=self._on_online_toggle,
            style="StatusBar.TCheckbutton",
        )
        online_check.grid(row=0, column=0, sticky="w", padx=(8, 6), pady=4)
        ttk.Separator(bar, orient=tk.VERTICAL, style="StatusBar.TSeparator").grid(
            row=0, column=1, sticky="ns", pady=5, padx=(0, 8)
        )
        self._currency_status_label = ttk.Label(
            bar,
            text=tr("app.status.currency_offline", "Курсы: офлайн"),
            anchor="w",
            style="StatusBar.TLabel",
        )
        self._currency_status_label.grid(row=0, column=2, sticky="w", padx=(0, 8), pady=4)
        ttk.Separator(bar, orient=tk.VERTICAL, style="StatusBar.TSeparator").grid(
            row=0, column=3, sticky="ns", pady=5, padx=(0, 8)
        )
        self._price_status_label = ttk.Label(
            bar,
            text=tr("app.status.prices_local", "Цены активов: локально"),
            anchor="w",
            style="StatusBar.TLabel",
        )
        self._price_status_label.grid(row=0, column=4, sticky="w", padx=(0, 8), pady=4)
        ttk.Separator(bar, orient=tk.VERTICAL, style="StatusBar.TSeparator").grid(
            row=0, column=5, sticky="ns", pady=5, padx=(0, 8)
        )
        ttk.Label(
            bar,
            text=tr("app.status.version", "v{version}", version=__version__),
            style="StatusBarMuted.TLabel",
        ).grid(row=0, column=6, sticky="e", padx=(0, 10), pady=4)
        return bar

    def _on_online_toggle(self) -> None:
        """Called when the Online/Offline toggle is clicked."""
        if self._online_var is None or self._currency_status_label is None:
            return
        if self._online_toggle_running:
            return

        enabled = self._online_var.get()
        self._online_toggle_running = True
        self._currency_status_label.config(
            text=(
                tr("app.status.currency_fetching", "Обновляем курсы...")
                if enabled
                else tr("app.status.currency_offline", "Курсы: офлайн")
            )
        )

        def task() -> None:
            self.controller.set_online_mode(enabled)

        def on_success(_result: Any) -> None:
            self._online_toggle_running = False
            self._refresh_status_bar()

        def on_error(exc: BaseException) -> None:
            self._online_toggle_running = False
            logger.warning("Online mode toggle error: %s", exc)
            self._refresh_status_bar()

        self._run_background(
            task,
            on_success=on_success,
            on_error=on_error,
            busy_message="",
            block_ui=False,
        )

    def _refresh_status_bar(self) -> None:
        """Update status bar labels from controller state."""
        if self._online_var is None or self._currency_status_label is None:
            return
        try:
            status = self.controller.get_online_status()
        except Exception:
            return
        self._online_var.set(self.controller.get_online_mode())
        self._currency_status_label.config(text=status["currency"])
        if self._price_status_label is not None and not self._price_status_label.cget("text"):
            self._price_status_label.config(
                text=tr("app.status.prices_local", "Цены активов: локально")
            )

    def _start_status_refresh_timer(self) -> None:
        """Refresh status bar every 60 seconds to update timestamps."""
        self._refresh_status_bar()
        self._status_refresh_job = self.after(60_000, self._start_status_refresh_timer)

    def _apply_saved_online_mode(self) -> None:
        """Load and apply the saved online mode preference."""
        if self._online_var is None or self._currency_status_label is None:
            return
        saved = self.controller.load_online_mode_preference()
        if saved:
            self._online_var.set(True)
            self._currency_status_label.config(
                text=tr("app.status.currency_fetching", "Обновляем курсы...")
            )
            self._online_toggle_running = True

            def task() -> None:
                self.controller.set_online_mode(True)

            def on_success(_result: Any) -> None:
                self._online_toggle_running = False
                self._refresh_status_bar()

            def on_error(exc: BaseException) -> None:
                self._online_toggle_running = False
                logger.warning("Saved online mode apply error: %s", exc)
                self._refresh_status_bar()

            self._run_background(
                task,
                on_success=on_success,
                on_error=on_error,
                busy_message="",
                block_ui=False,
            )
        else:
            self._online_var.set(False)
            self._refresh_status_bar()
        self._start_status_refresh_timer()

    def _import_policy_from_ui(self, mode_label: str) -> ImportPolicy:
        if mode_label == "Полная замена":
            return ImportPolicy.FULL_BACKUP
        if mode_label == "Наследуемый импорт":
            return ImportPolicy.LEGACY
        return ImportPolicy.CURRENT_RATE

    def _refresh_list(self, records: list[Any] | None = None) -> None:
        if self.records_tree is None:
            return
        for iid in self.records_tree.get_children():
            self.records_tree.delete(iid)
        self._record_id_to_repo_index = {}
        self._record_id_to_domain_id = {}
        for kind, color in KIND_TO_FOREGROUND.items():
            try:
                self.records_tree.tag_configure(kind, foreground=color)
            except Exception:
                pass

        list_items = (
            self.controller.build_record_list_items(records)
            if records is not None
            else self.controller.build_record_list_items()
        )

        def _display_type_label(raw_label: str, kind: str) -> str:
            normalized = str(raw_label or "").strip().lower()
            mapping = {
                "income": tr("operations.type.income", "Доход"),
                "expense": tr("operations.type.expense", "Расход"),
                "mandatory expense": tr("operations.type.mandatory", "Обязательный расход"),
                "transfer": tr("operations.type.transfer", "Перевод"),
            }
            return mapping.get(normalized, mapping.get(kind, str(raw_label)))

        def _display_category_label(raw_category: str, kind: str) -> str:
            category = str(raw_category or "")
            if kind == "transfer" and category.lower().startswith("transfer #"):
                suffix = category.split("#", 1)[1].strip() if "#" in category else ""
                return tr("operations.transfer.category", "Перевод #{id}", id=suffix or "?")
            return category

        for item in list_items:
            self._record_id_to_repo_index[item.record_id] = item.repository_index
            if item.domain_record_id is not None:
                self._record_id_to_domain_id[item.record_id] = item.domain_record_id
            kind = str(getattr(item, "kind", "") or "").strip().lower()
            tags = (kind,) if foreground_for_kind(kind) else ()
            values = (
                str(item.invariant_id),
                str(item.date),
                _display_type_label(str(item.type_label), kind),
                _display_category_label(str(item.category), kind),
                f"{float(item.amount_original):.2f}",
                str(item.currency),
                f"{float(item.amount_kzt):.2f}",
                str(item.wallet_label),
                str(item.extra),
            )
            try:
                self.records_tree.insert("", "end", iid=item.record_id, values=values, tags=tags)
            except Exception:
                self.records_tree.insert("", "end", values=values, tags=tags)

    def _refresh_charts(self, records: list[Any] | None = None) -> None:
        if (
            self.chart_month_menu is None
            or self.chart_month_var is None
            or self.pie_month_menu is None
            or self.pie_month_var is None
            or self.chart_year_menu is None
            or self.chart_year_var is None
        ):
            return

        if records is None:
            records = self.repository.load_all()

        self._chart_refresh_suspended = True
        self._update_month_options(records)
        self._update_pie_month_options(records)
        self._update_year_options(records)
        self._chart_refresh_suspended = False

        self._draw_expense_pie(records)
        self._draw_daily_bars(records)
        self._draw_monthly_bars(records)

    def _ensure_tab_built(self, tab_key: str) -> None:
        if tab_key in self._built_tabs:
            return

        if tab_key == "infographics":
            from gui.tabs.infographics_tab import build_infographics_tab

            infographics = build_infographics_tab(
                self.tab_infographics,
                on_chart_filter_change=self._on_chart_filter_change,
                on_refresh_charts=self._refresh_charts,
                on_legend_mousewheel=self._on_legend_mousewheel,
                bind_all=self.bind_all,
                after=self.after,
                after_cancel=self.after_cancel,
            )
            self.pie_month_var = infographics.pie_month_var
            self.pie_month_menu = infographics.pie_month_menu
            self.chart_month_var = infographics.chart_month_var
            self.chart_month_menu = infographics.chart_month_menu
            self.chart_year_var = infographics.chart_year_var
            self.chart_year_menu = infographics.chart_year_menu
            self.expense_pie_canvas = infographics.expense_pie_canvas
            self.expense_legend_canvas = infographics.expense_legend_canvas
            self.expense_legend_frame = infographics.expense_legend_frame
            self.daily_bar_canvas = infographics.daily_bar_canvas
            self.monthly_bar_canvas = infographics.monthly_bar_canvas
        elif tab_key == "operations":
            from gui.tabs.operations_tab import build_operations_tab

            operations = build_operations_tab(self.tab_operations, self, self._import_formats)
            self.records_tree = operations.records_tree
            self.refresh_operation_wallet_menu = operations.refresh_operation_wallet_menu
            self.refresh_transfer_wallet_menus = operations.refresh_transfer_wallet_menus
        elif tab_key == "reports":
            from gui.tabs.reports_tab import build_reports_tab

            build_reports_tab(self.tab_reports, self)
        elif tab_key == "analytics":
            from gui.tabs.analytics_tab import build_analytics_tab

            self._analytics_bindings = build_analytics_tab(self.tab_analytics, context=self)
        elif tab_key == "dashboard":
            from gui.tabs.dashboard_tab import build_dashboard_tab

            self._dashboard_bindings = build_dashboard_tab(self.tab_dashboard, context=self)
        elif tab_key == "budget":
            from gui.tabs.budget_tab import build_budget_tab

            self._budget_bindings = build_budget_tab(self.tab_budget, context=self)
            self.refresh_budgets = self._budget_bindings.refresh
        elif tab_key == "debts":
            from gui.tabs.debts_tab import build_debts_tab

            self._debt_bindings = build_debts_tab(self.tab_debts, context=self)
        elif tab_key == "distribution":
            from gui.tabs.distribution_tab import build_distribution_tab

            self._distribution_bindings = build_distribution_tab(
                self.tab_distribution, context=self
            )
            self.refresh_all = self._distribution_bindings.refresh
        elif tab_key == "settings":
            from gui.tabs.settings_tab import build_settings_tab

            build_settings_tab(self.tab_settings, self, self._import_formats)
        else:
            return

        self._built_tabs.add(tab_key)

    def _on_tab_changed(self, _event: tk.Event) -> None:
        if not hasattr(self, "_notebook"):
            return
        selected = self._notebook.select()
        tab_key = self._tab_keys_by_widget.get(str(selected))
        if tab_key is not None:
            self._ensure_tab_built(tab_key)

    def _start_deferred_startup(self) -> None:
        if self._startup_sync_running:
            return
        self._startup_sync_running = True

        def task() -> tuple[list[Any], list[Any]]:
            created_auto_payments = self.controller.apply_mandatory_auto_payments()
            run_post_startup_maintenance()
            records = self.repository.load_all()
            return created_auto_payments, records

        def on_success(result: tuple[list[Any], list[Any]]) -> None:
            self._startup_sync_running = False
            created_auto_payments, records = result
            self._refresh_list(records=records)
            self._refresh_charts(records=records)
            self._refresh_budgets()
            self._refresh_all()
            self._apply_saved_online_mode()
            self._show_startup_auto_payment_message(created_auto_payments)

        def on_error(exc: BaseException) -> None:
            self._startup_sync_running = False
            logger.exception("Deferred startup sync failed", exc_info=exc)
            try:
                records = self.repository.load_all()
            except Exception:
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

    def _show_startup_auto_payment_message(self, created_auto_payments: list[Any]) -> None:
        if not created_auto_payments:
            return
        logger.info("Auto-applied mandatory payments on startup: %s", len(created_auto_payments))
        details = []
        for record in created_auto_payments:
            details.append(f"- {record.category}: {record.amount_kzt:.2f} KZT ({record.date})")
        max_details = 5
        if len(details) > max_details:
            displayed = details[:max_details]
            remaining = len(details) - max_details
            displayed.append(f"+ {remaining} more")
            details_text = "\n".join(displayed)
        else:
            details_text = "\n".join(details)
        message_text = (
            tr(
                "app.autopay.summary",
                "Создано автоплатежей: {count}",
                count=len(created_auto_payments),
            )
            + "\n"
            + details_text
        )
        show_info(message_text, title=tr("app.autopay.title", "Автоплатежи применены"))

    def _refresh_wallets(self) -> None:
        """Refresh wallet list in settings tab and wallet menus in operations tab."""
        if self.refresh_wallets is not None:
            try:
                self.refresh_wallets()
            except Exception:
                pass
        if self.refresh_operation_wallet_menu is not None:
            try:
                self.refresh_operation_wallet_menu()
            except Exception:
                pass
        if self.refresh_transfer_wallet_menus is not None:
            try:
                self.refresh_transfer_wallet_menus()
            except Exception:
                pass

    def _refresh_budgets(self) -> None:
        if self.refresh_budgets is not None:
            try:
                self.refresh_budgets()
            except Exception:
                pass

    def _refresh_all(self) -> None:
        if self.refresh_all is not None:
            try:
                self.refresh_all()
            except Exception:
                pass

    def _on_chart_filter_change(self, *_args: Any) -> None:
        if self._chart_refresh_suspended:
            return
        self._refresh_charts()

    def _update_month_options(self, records: Any) -> None:
        if self.chart_month_menu is None or self.chart_month_var is None:
            return
        chart_month_var = self.chart_month_var
        months = extract_months(records)
        current_month = datetime.now().strftime("%Y-%m")
        if current_month not in months:
            months.append(current_month)
        months = sorted(set(months))

        menu = self.chart_month_menu["menu"]
        menu.delete(0, "end")
        for month in months:
            menu.add_command(label=month, command=lambda value=month: chart_month_var.set(value))
        if not chart_month_var.get() or chart_month_var.get() not in months:
            chart_month_var.set(months[-1])

    def _update_pie_month_options(self, records: Any) -> None:
        if self.pie_month_menu is None or self.pie_month_var is None:
            return
        pie_month_var = self.pie_month_var
        months = extract_months(records)
        current_month = datetime.now().strftime("%Y-%m")
        if current_month not in months:
            months.append(current_month)
        months = sorted(set(months))

        menu = self.pie_month_menu["menu"]
        menu.delete(0, "end")
        menu.add_command(
            label=tr("infographics.all_time", "Все время"),
            command=lambda value="all": pie_month_var.set(value),
        )
        for month in months:
            menu.add_command(label=month, command=lambda value=month: pie_month_var.set(value))

        current_value = pie_month_var.get()
        if not current_value:
            pie_month_var.set("all")
            return
        if current_value != "all" and current_value not in months:
            pie_month_var.set(months[-1] if months else "all")

    def _update_year_options(self, records: Any) -> None:
        if self.chart_year_menu is None or self.chart_year_var is None:
            return
        chart_year_var = self.chart_year_var
        years = extract_years(records)
        current_year = datetime.now().year
        if current_year not in years:
            years.append(current_year)
        years = sorted(set(years))

        menu = self.chart_year_menu["menu"]
        menu.delete(0, "end")
        for year in years:
            menu.add_command(
                label=str(year),
                command=lambda value=year: chart_year_var.set(str(value)),
            )
        if not chart_year_var.get() or int(chart_year_var.get()) not in years:
            chart_year_var.set(str(years[-1]))

    def _draw_expense_pie(self, records: Any) -> None:
        if (
            self.pie_month_var is None
            or self.expense_pie_canvas is None
            or self.expense_legend_frame is None
            or self.expense_legend_canvas is None
        ):
            return

        month_value = self.pie_month_var.get()
        filtered = records
        if month_value and month_value != "all":
            filtered = self._filter_records_by_month(records, month_value)
        totals = aggregate_expenses_by_category(filtered)
        data = [(key, value) for key, value in totals.items() if value > 0]
        data.sort(key=lambda item: item[1], reverse=True)
        data = self._group_minor_categories(data, max_slices=10)

        self.expense_pie_canvas.delete("all")
        for child in self.expense_legend_frame.winfo_children():
            child.destroy()

        if not data:
            self.expense_pie_canvas.create_text(
                10,
                10,
                anchor="nw",
                text=tr("common.empty", "Нет данных для отображения"),
                fill="#6b7280",
                font=("Segoe UI", 11),
            )
            return

        width = max(self.expense_pie_canvas.winfo_width(), 220)
        height = max(self.expense_pie_canvas.winfo_height(), 220)
        usable_w = max(width - 32, 120)
        usable_h = max(height - 32, 120)
        radius = max(52, min(usable_w * 0.42, usable_h * 0.48))
        center_x = max(radius + 16, min(width * 0.42, width - radius - 16))
        center_y = height / 2
        x0 = center_x - radius
        y0 = center_y - radius
        x1 = center_x + radius
        y1 = center_y + radius

        colors = self._generate_colors(len(data))

        total = sum(value for _, value in data)
        start = 0
        for index, (category, value) in enumerate(data):
            extent = (value / total) * 360
            color = colors[index % len(colors)]
            self.expense_pie_canvas.create_arc(
                x0,
                y0,
                x1,
                y1,
                start=start,
                extent=extent,
                fill=color,
                outline="white",
            )
            start += extent

            legend_row = tk.Frame(self.expense_legend_frame, bg="white")
            legend_row.pack(fill="x", anchor="w", pady=1, padx=6)
            legend_row.grid_columnconfigure(1, weight=1)
            color_box = tk.Canvas(
                legend_row,
                width=10,
                height=10,
                highlightthickness=0,
                bg="white",
            )
            color_box.create_rectangle(0, 0, 10, 10, fill=color, outline=color)
            color_box.grid(row=0, column=0, sticky="nw", padx=(0, 6), pady=2)
            tk.Label(
                legend_row,
                text=f"{category}: {value:.2f} KZT",
                font=("Segoe UI", 8),
                wraplength=max(96, self.expense_legend_canvas.winfo_width() - 42),
                justify="left",
                anchor="w",
                bg="white",
                fg="#1f2937",
            ).grid(row=0, column=1, sticky="w")

    def _group_minor_categories(
        self, data: list[tuple[str, float]], max_slices: int
    ) -> list[tuple[str, float]]:
        if len(data) <= max_slices:
            return data

        major = data[: max_slices - 1]
        other_total = sum(value for _, value in data[max_slices - 1 :])
        major.append((tr("common.other", "Other"), other_total))
        return major

    def _filter_records_by_month(self, records: Any, month_value: str) -> list[Any]:
        try:
            year, month = map(int, month_value.split("-"))
        except Exception:
            return records

        filtered: list[Any] = []
        for record in records:
            try:
                if isinstance(record.date, date):
                    dt = datetime.combine(record.date, datetime.min.time())
                else:
                    dt = datetime.strptime(record.date, "%Y-%m-%d")
            except Exception:
                continue
            if dt.year == year and dt.month == month:
                filtered.append(record)
        return filtered

    def _generate_colors(self, count: int) -> list[str]:
        if count <= 0:
            return []

        base_palette = [
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
        ]

        if count <= len(base_palette):
            return base_palette[:count]

        colors = list(base_palette)
        remaining = count - len(colors)
        for idx in range(remaining):
            hue = (idx * 360 / max(1, remaining)) % 360
            saturation = 70
            lightness = 50
            colors.append(f"#{self._hsl_to_hex(hue, saturation, lightness)}")
        return colors

    def _hsl_to_hex(self, hue: float, saturation: float, lightness: float) -> str:
        saturation /= 100
        lightness /= 100

        c = (1 - abs(2 * lightness - 1)) * saturation
        x = c * (1 - abs((hue / 60) % 2 - 1))
        m = lightness - c / 2

        if 0 <= hue < 60:
            r, g, b = c, x, 0
        elif 60 <= hue < 120:
            r, g, b = x, c, 0
        elif 120 <= hue < 180:
            r, g, b = 0, c, x
        elif 180 <= hue < 240:
            r, g, b = 0, x, c
        elif 240 <= hue < 300:
            r, g, b = x, 0, c
        else:
            r, g, b = c, 0, x

        r = int((r + m) * 255)
        g = int((g + m) * 255)
        b = int((b + m) * 255)
        return f"{r:02x}{g:02x}{b:02x}"

    def _draw_daily_bars(self, records: Any) -> None:
        if self.chart_month_var is None or self.daily_bar_canvas is None:
            return
        month_value = self.chart_month_var.get()
        if not month_value:
            return
        year, month = map(int, month_value.split("-"))
        income, expense = aggregate_daily_cashflow(records, year, month)
        labels = [str(idx + 1) for idx in range(len(income))]
        self._draw_bar_chart(self.daily_bar_canvas, labels, income, expense, max_labels=8)

    def _draw_monthly_bars(self, records: Any) -> None:
        if self.chart_year_var is None or self.monthly_bar_canvas is None:
            return
        year_value = self.chart_year_var.get()
        if not year_value:
            return
        year = int(year_value)
        income, expense = aggregate_monthly_cashflow(records, year)
        labels = [
            "Jan",
            "Feb",
            "Mar",
            "Apr",
            "May",
            "Jun",
            "Jul",
            "Aug",
            "Sep",
            "Oct",
            "Nov",
            "Dec",
        ]
        self._draw_bar_chart(self.monthly_bar_canvas, labels, income, expense, 12)

    def _on_legend_mousewheel(self, event: tk.Event) -> None:
        if self.expense_legend_canvas is None:
            return

        widget = self.winfo_containing(event.x_root, event.y_root)
        while widget is not None:
            if widget == self.expense_legend_canvas:
                delta = -1 if event.delta > 0 else 1
                self.expense_legend_canvas.yview_scroll(delta, "units")
                return
            widget = widget.master

    def _draw_bar_chart(
        self,
        canvas: tk.Canvas,
        labels: list[str],
        income_values: list[float],
        expense_values: list[float],
        max_labels: int,
    ) -> None:
        canvas.delete("all")
        width = max(canvas.winfo_width(), 300)
        height = max(canvas.winfo_height(), 220)

        max_income = max(income_values) if income_values else 0
        max_expense = max(expense_values) if expense_values else 0
        max_value = max(max_income, max_expense)

        if max_value <= 0:
            canvas.create_text(
                10,
                10,
                anchor="nw",
                text=tr("common.empty", "Нет данных для отображения"),
                fill="#6b7280",
                font=("Segoe UI", 11),
            )
            return

        padding = {
            "left": 34 if width < 420 else 40,
            "right": 16 if width < 420 else 20,
            "top": 20,
            "bottom": 34 if height < 240 else 30,
        }
        chart_w = width - padding["left"] - padding["right"]
        chart_h = height - padding["top"] - padding["bottom"]
        zero_y = padding["top"] + chart_h / 2
        scale = (chart_h / 2 - 10) / max_value

        canvas.create_line(
            padding["left"], zero_y, padding["left"] + chart_w, zero_y, fill="#d1d5db"
        )

        group_width = chart_w / max(1, len(labels))
        bar_gap = 1 if group_width < 18 else 2
        bar_width = max(3, min(16, group_width * 0.34))

        for idx, label in enumerate(labels):
            x_center = padding["left"] + group_width * idx + group_width / 2
            income_h = income_values[idx] * scale
            expense_h = expense_values[idx] * scale

            canvas.create_rectangle(
                x_center - bar_width - bar_gap,
                zero_y - income_h,
                x_center - bar_gap,
                zero_y,
                fill="#10b981",
                outline="",
            )
            canvas.create_rectangle(
                x_center + bar_gap,
                zero_y,
                x_center + bar_width + bar_gap,
                zero_y + expense_h,
                fill="#ef4444",
                outline="",
            )

            label_capacity = max(
                3,
                min(max_labels, int(chart_w // 44) if chart_w > 0 else max_labels),
            )
            label_step = max(1, len(labels) // label_capacity)
            if idx % label_step == 0 or len(labels) <= label_capacity:
                canvas.create_text(
                    x_center,
                    padding["top"] + chart_h + 10,
                    text=label,
                    fill="#6b7280",
                    font=("Segoe UI", 9),
                )

        canvas.create_text(
            padding["left"],
            padding["top"] - 6,
            text="Доходы",
            fill="#10b981",
            anchor="sw",
            font=("Segoe UI", 9),
        )
        canvas.create_text(
            padding["left"] + 60,
            padding["top"] - 6,
            text="Расходы",
            fill="#ef4444",
            anchor="sw",
            font=("Segoe UI", 9),
        )


def main() -> None:
    try:
        app = FinancialApp()
        app.mainloop()
    except KeyboardInterrupt:
        show_info(
            tr("app.closed_by_user", "Приложение закрыто пользователем."),
            title=tr("app.info", "Информация"),
        )
