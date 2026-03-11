import logging
import tkinter as tk
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from datetime import date, datetime
from tkinter import Listbox, messagebox, ttk
from typing import Any

from app.services import CurrencyService
from bootstrap import bootstrap_repository
from domain.import_policy import ImportPolicy
from gui.controllers import FinancialController
from gui.tabs import (
    build_infographics_tab,
    build_operations_tab,
    build_reports_tab,
    build_settings_tab,
)
from utils.charting import (
    aggregate_daily_cashflow,
    aggregate_expenses_by_category,
    aggregate_monthly_cashflow,
    extract_months,
    extract_years,
)

logger = logging.getLogger(__name__)

IMPORT_FORMATS = {
    "CSV": {"ext": ".csv", "desc": "CSV"},
    "XLSX": {"ext": ".xlsx", "desc": "Excel"},
    "JSON": {"ext": ".json", "desc": "JSON"},
}


class FinancialApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Financial Accounting")
        self.geometry("1100x800")
        self.minsize(900, 600)
        # Make shutdown explicit: ensures background executor and repository are closed
        # when user closes the window via the window manager.
        self.protocol("WM_DELETE_WINDOW", self.destroy)

        self.repository = bootstrap_repository()
        self.currency = CurrencyService()
        self.controller = FinancialController(self.repository, self.currency)
        try:
            created_auto_payments = self.controller.apply_mandatory_auto_payments()
            if created_auto_payments:
                logger.info("Auto-applied mandatory payments on startup: %s", created_auto_payments)
        except Exception:
            logger.exception("Failed to apply mandatory auto payments on startup")

        self._executor = ThreadPoolExecutor(max_workers=2)
        self._busy = False
        self._list_index_to_record_id: dict[int, str] = {}
        self._record_id_to_repo_index: dict[str, int] = {}
        self._record_id_to_domain_id: dict[str, int] = {}
        self._chart_refresh_suspended = False

        self.records_listbox: Listbox | None = None
        self.refresh_operation_wallet_menu: Callable[[], None] | None = None
        self.refresh_transfer_wallet_menus: Callable[[], None] | None = None

        self.pie_month_var: tk.StringVar | None = None
        self.pie_month_menu: ttk.OptionMenu | None = None
        self.chart_month_var: tk.StringVar | None = None
        self.chart_month_menu: ttk.OptionMenu | None = None
        self.chart_year_var: tk.StringVar | None = None
        self.chart_year_menu: ttk.OptionMenu | None = None
        self.expense_pie_canvas: tk.Canvas | None = None
        self.expense_legend_canvas: tk.Canvas | None = None
        self.expense_legend_frame: tk.Frame | None = None
        self.daily_bar_canvas: tk.Canvas | None = None
        self.monthly_bar_canvas: tk.Canvas | None = None

        notebook = ttk.Notebook(self)
        notebook.pack(fill=tk.BOTH, expand=True)

        self.tab_infographics = ttk.Frame(notebook)
        self.tab_operations = ttk.Frame(notebook)
        self.tab_reports = ttk.Frame(notebook)
        self.tab_settings = ttk.Frame(notebook)

        notebook.add(self.tab_infographics, text="Infographics")
        notebook.add(self.tab_operations, text="Operations")
        notebook.add(self.tab_reports, text="Reports")
        notebook.add(self.tab_settings, text="Settings")

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

        operations = build_operations_tab(self.tab_operations, self, IMPORT_FORMATS)
        self.records_listbox = operations.records_listbox
        self.refresh_operation_wallet_menu = operations.refresh_operation_wallet_menu
        self.refresh_transfer_wallet_menus = operations.refresh_transfer_wallet_menus

        build_reports_tab(self.tab_reports, self)
        build_settings_tab(self.tab_settings, self, IMPORT_FORMATS)

        self.progress = ttk.Progressbar(self, mode="indeterminate")
        self.progress.pack(fill=tk.X, padx=8, pady=(0, 8))
        self.progress.pack_forget()

        self._refresh_list()
        self._refresh_charts()

    def destroy(self) -> None:
        self._executor.shutdown(wait=False, cancel_futures=True)
        close_method = getattr(self.repository, "close", None)
        if callable(close_method):
            close_method()
        super().destroy()

    def _set_busy(self, busy: bool, message: str = "") -> None:
        self._busy = busy
        try:
            self.attributes("-disabled", busy)
        except Exception:
            pass
        if busy:
            self.progress.pack(fill=tk.X, padx=8, pady=(0, 8))
            self.progress.start(12)
            self.title(f"Financial Accounting - {message}" if message else "Financial Accounting")
            self.config(cursor="watch")
        else:
            self.progress.stop()
            self.progress.pack_forget()
            self.title("Financial Accounting")
            self.config(cursor="")

    def _run_background(
        self,
        task: Callable[[], Any],
        *,
        on_success: Callable[[Any], None],
        on_error: Callable[[BaseException], None] | None = None,
        busy_message: str = "Processing...",
    ) -> None:
        if self._busy:
            messagebox.showinfo("Please wait", "Operation is already running.")
            return
        self._set_busy(True, busy_message)
        future: Future[Any] = self._executor.submit(task)

        def _poll() -> None:
            if not future.done():
                self.after(100, _poll)
                return
            self._set_busy(False)
            error = future.exception()
            if error is not None:
                if on_error is not None:
                    on_error(error)
                else:
                    logger.exception("Background operation failed", exc_info=error)
                    messagebox.showerror("Error", str(error))
                return
            on_success(future.result())

        self.after(100, _poll)

    def _import_policy_from_ui(self, mode_label: str) -> ImportPolicy:
        if mode_label == "Full Backup":
            return ImportPolicy.FULL_BACKUP
        if mode_label == "Legacy Import":
            return ImportPolicy.LEGACY
        return ImportPolicy.CURRENT_RATE

    def _refresh_list(self) -> None:
        if self.records_listbox is None:
            return
        self.records_listbox.delete(0, tk.END)
        self._list_index_to_record_id = {}
        self._record_id_to_repo_index = {}
        self._record_id_to_domain_id = {}
        kind_to_color = {
            "income": "#166534",
            "expense": "#b91c1c",
            "mandatory": "#b6ad13",
            "transfer": "#1d4ed8",
        }
        for list_index, item in enumerate(self.controller.build_record_list_items()):
            self._list_index_to_record_id[list_index] = item.record_id
            self._record_id_to_repo_index[item.record_id] = item.repository_index
            if item.domain_record_id is not None:
                self._record_id_to_domain_id[item.record_id] = item.domain_record_id
            self.records_listbox.insert(tk.END, item.label)
            color = kind_to_color.get(getattr(item, "kind", ""))
            if color:
                try:
                    self.records_listbox.itemconfigure(list_index, foreground=color)
                except Exception:
                    pass

    def _refresh_charts(self) -> None:
        if (
            self.chart_month_menu is None
            or self.chart_month_var is None
            or self.pie_month_menu is None
            or self.pie_month_var is None
            or self.chart_year_menu is None
            or self.chart_year_var is None
        ):
            return

        records = self.repository.load_all()

        self._chart_refresh_suspended = True
        self._update_month_options(records)
        self._update_pie_month_options(records)
        self._update_year_options(records)
        self._chart_refresh_suspended = False

        self._draw_expense_pie(records)
        self._draw_daily_bars(records)
        self._draw_monthly_bars(records)

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
        menu.add_command(label="Все время", command=lambda value="all": pie_month_var.set(value))
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
                text="No data to display",
                fill="#6b7280",
                font=("Segoe UI", 11),
            )
            return

        width = max(self.expense_pie_canvas.winfo_width(), 240)
        height = max(self.expense_pie_canvas.winfo_height(), 240)
        size = min(width, height) - 30
        x0 = (width - size) / 2
        y0 = (height - size) / 2
        x1 = x0 + size
        y1 = y0 + size

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

            legend_row = tk.Frame(self.expense_legend_frame)
            legend_row.pack(anchor="w", pady=2)
            color_box = tk.Canvas(legend_row, width=12, height=12, highlightthickness=0)
            color_box.create_rectangle(0, 0, 12, 12, fill=color, outline=color)
            color_box.pack(side=tk.LEFT)
            ttk.Label(
                legend_row,
                text=f"{category}: {value:.2f} KZT",
                font=("Segoe UI", 9),
            ).pack(side=tk.LEFT, padx=6)

    def _group_minor_categories(
        self, data: list[tuple[str, float]], max_slices: int
    ) -> list[tuple[str, float]]:
        if len(data) <= max_slices:
            return data

        major = data[: max_slices - 1]
        other_total = sum(value for _, value in data[max_slices - 1 :])
        major.append(("Other", other_total))
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
                text="No data to display",
                fill="#6b7280",
                font=("Segoe UI", 11),
            )
            return

        padding = {"left": 40, "right": 20, "top": 20, "bottom": 30}
        chart_w = width - padding["left"] - padding["right"]
        chart_h = height - padding["top"] - padding["bottom"]
        zero_y = padding["top"] + chart_h / 2
        scale = (chart_h / 2 - 10) / max_value

        canvas.create_line(
            padding["left"], zero_y, padding["left"] + chart_w, zero_y, fill="#d1d5db"
        )

        group_width = chart_w / max(1, len(labels))
        bar_width = max(6, min(18, group_width * 0.35))

        for idx, label in enumerate(labels):
            x_center = padding["left"] + group_width * idx + group_width / 2
            income_h = income_values[idx] * scale
            expense_h = expense_values[idx] * scale

            canvas.create_rectangle(
                x_center - bar_width - 2,
                zero_y - income_h,
                x_center - 2,
                zero_y,
                fill="#10b981",
                outline="",
            )
            canvas.create_rectangle(
                x_center + 2,
                zero_y,
                x_center + bar_width + 2,
                zero_y + expense_h,
                fill="#ef4444",
                outline="",
            )

            label_step = max(1, len(labels) // max_labels)
            if idx % label_step == 0 or len(labels) <= max_labels:
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
            text="Incomes",
            fill="#10b981",
            anchor="sw",
            font=("Segoe UI", 9),
        )
        canvas.create_text(
            padding["left"] + 60,
            padding["top"] - 6,
            text="Expenses",
            fill="#ef4444",
            anchor="sw",
            font=("Segoe UI", 9),
        )


def main() -> None:
    try:
        app = FinancialApp()
        app.mainloop()
    except KeyboardInterrupt:
        messagebox.showinfo("Info", "Application closed by user.")
