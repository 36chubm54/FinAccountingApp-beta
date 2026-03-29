"""Analytics tab — Dashboard, Category Breakdown, Monthly Report."""

from __future__ import annotations

import logging
import tkinter as tk
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from tkinter import messagebox, ttk
from typing import Any, Protocol

from gui.tooltip import Tooltip

logger = logging.getLogger(__name__)

PALETTE = [
    "#3b82f6",
    "#10b981",
    "#f59e0b",
    "#ef4444",
    "#8b5cf6",
    "#ec4899",
    "#06b6d4",
    "#84cc16",
    "#f97316",
    "#6366f1",
]


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


def _draw_net_worth_line(canvas: tk.Canvas, data: list) -> None:
    canvas.delete("all")
    if not data:
        canvas.create_text(
            10,
            10,
            anchor="nw",
            text="No data",
            fill="#6b7280",
            font=("Segoe UI", 11),
        )
        return

    w = max(canvas.winfo_width(), 300)
    h = max(canvas.winfo_height(), 160)
    pad = {"left": 60, "right": 20, "top": 16, "bottom": 28}

    values = [float(getattr(item, "balance", 0.0)) for item in data]
    min_v, max_v = min(values), max(values)
    span = (max_v - min_v) or 1.0

    def to_xy(i: int, v: float) -> tuple[float, float]:
        x = pad["left"] + (w - pad["left"] - pad["right"]) * i / max(1, len(data) - 1)
        y = pad["top"] + (h - pad["top"] - pad["bottom"]) * (1 - (v - min_v) / span)
        return x, y

    if min_v < 0 < max_v:
        _, y0 = to_xy(0, 0.0)
        canvas.create_line(
            pad["left"],
            y0,
            w - pad["right"],
            y0,
            fill="#d1d5db",
            dash=(4, 4),
        )

    for i in range(len(values) - 1):
        x1, y1 = to_xy(i, values[i])
        x2, y2 = to_xy(i + 1, values[i + 1])
        canvas.create_line(x1, y1, x2, y2, fill="#3b82f6", width=2)

    for i, item in enumerate(data):
        x, y = to_xy(i, float(getattr(item, "balance", 0.0)))
        canvas.create_oval(
            x - 3,
            y - 3,
            x + 3,
            y + 3,
            fill="#3b82f6",
            outline="white",
            width=1,
        )

    step = max(1, len(data) // 6)
    for i, item in enumerate(data):
        if i % step == 0 or i == len(data) - 1:
            x, _ = to_xy(i, values[i])
            canvas.create_text(
                x,
                h - pad["bottom"] + 10,
                text=str(getattr(item, "month", "")),
                fill="#6b7280",
                font=("Segoe UI", 8),
            )

    canvas.create_text(
        pad["left"] - 4,
        pad["top"],
        text=f"{max_v:,.0f}",
        fill="#6b7280",
        font=("Segoe UI", 8),
        anchor="e",
    )
    canvas.create_text(
        pad["left"] - 4,
        h - pad["bottom"],
        text=f"{min_v:,.0f}",
        fill="#6b7280",
        font=("Segoe UI", 8),
        anchor="e",
    )


def _draw_category_pie(canvas: tk.Canvas, data: list) -> None:
    """Draw a pie chart of category spending."""
    canvas.delete("all")
    if not data:
        return
    total = sum(float(getattr(item, "total_kzt", 0.0)) for item in data)
    if total <= 0:
        return

    w = max(canvas.winfo_width(), 200)
    h = max(canvas.winfo_height(), 200)
    margin = 10
    cx, cy = w // 2, h // 2
    r = min(cx, cy) - margin

    angle = 90.0
    for i, item in enumerate(data[:10]):
        value = float(getattr(item, "total_kzt", 0.0))
        sweep = value / total * 360.0
        color = PALETTE[i % len(PALETTE)]
        canvas.create_arc(
            cx - r,
            cy - r,
            cx + r,
            cy + r,
            start=angle,
            extent=-sweep,
            fill=color,
            outline="white",
            width=1,
        )
        angle -= sweep


def build_analytics_tab(
    parent: tk.Frame | ttk.Frame,
    context: AnalyticsTabContext,
) -> AnalyticsTabBindings:
    parent.grid_columnconfigure(0, weight=1)
    parent.grid_columnconfigure(1, weight=1)
    parent.grid_rowconfigure(1, weight=1)
    parent.grid_rowconfigure(2, weight=2)

    top = ttk.Frame(parent)
    top.grid(row=0, column=0, columnspan=2, sticky="ew", padx=10, pady=(10, 6))
    top.grid_columnconfigure(5, weight=1)

    ttk.Label(top, text="From:").grid(row=0, column=0, sticky="w")
    period_from_entry = ttk.Entry(top, width=12)
    period_from_entry.grid(row=0, column=1, sticky="w", padx=(6, 14))

    ttk.Label(top, text="To:").grid(row=0, column=2, sticky="w")
    period_to_entry = ttk.Entry(top, width=12)
    period_to_entry.grid(row=0, column=3, sticky="w", padx=(6, 14))

    refresh_button = ttk.Button(top, text="Refresh")
    refresh_button.grid(row=0, column=4, sticky="w")

    default_start = datetime.now().strftime("%Y-01-01")
    default_end = datetime.now().strftime("%Y-%m-%d")
    period_from_entry.insert(0, default_start)
    period_to_entry.insert(0, default_end)

    dashboard_frame = ttk.LabelFrame(parent, text="Dashboard")
    dashboard_frame.grid(row=1, column=0, sticky="nsew", padx=(10, 6), pady=(6, 10))
    dashboard_frame.grid_columnconfigure(0, weight=1)

    dashboard_row = ttk.Frame(dashboard_frame, padding=(10, 10))
    dashboard_row.grid(row=0, column=0, sticky="ew")
    dashboard_row.grid_columnconfigure(0, weight=1)
    dashboard_row.grid_columnconfigure(1, weight=1)
    dashboard_row.grid_columnconfigure(2, weight=1)

    dashboard_left = ttk.Frame(dashboard_row)
    dashboard_left.grid(row=0, column=0, sticky="nsew")
    for i in range(4):
        dashboard_left.grid_rowconfigure(i, weight=0)
    dashboard_left.grid_rowconfigure(3, weight=1)
    dashboard_left.grid_columnconfigure(3, weight=1)
    dashboard_right = ttk.Frame(dashboard_row)
    dashboard_right.grid(row=0, column=1, sticky="nw", padx=(24, 0))

    font = ("Segoe UI", 12, "bold")
    net_worth_label = ttk.Label(dashboard_left, text="Net worth: —", font=font)
    net_worth_label.grid(row=0, column=0, sticky="w")

    savings_rate_label = ttk.Label(dashboard_left, text="Savings rate: —", font=font)
    savings_rate_label.grid(row=1, column=0, sticky="w")

    burn_rate_label = ttk.Label(dashboard_left, text="Burn rate: —", font=font)
    burn_rate_label.grid(row=2, column=0, sticky="w")

    tooltip_label = ttk.Label(dashboard_left, text="ⓘ", font=("Segoe UI", 10))
    tooltip_label.config(foreground="gray")
    tooltip_label.grid(row=3, column=0, sticky="sw")

    Tooltip(
        tooltip_label,
        "Savings rate = cashflow / income * 100%."
        "\nBurn rate = total expenses / number of days in range."
        "\nAvg monthly income is the average of all monthly incomes."
        "\nYear income is the sum of all incomes in a year."
        "\nYear income (USD) is the year income in USD."
        "\nAvg monthly expenses is the average of all monthly expenses."
        "\nYear expense is the sum of all expenses in a year."
        "\nCost per day is the cost of a day."
        "\nCost per hour is the cost of an hour."
        "\nCost per minute is the cost of a minute.",
    )

    avg_monthly_income_label = ttk.Label(dashboard_right, text="Avg monthly income: —", font=font)
    avg_monthly_income_label.grid(row=0, column=0, sticky="w")

    avg_monthly_expenses_label = ttk.Label(
        dashboard_right, text="Avg monthly expenses: —", font=font
    )
    avg_monthly_expenses_label.grid(row=1, column=0, sticky="w")

    year_income_label = ttk.Label(dashboard_right, text="Year income: —", font=font)
    year_income_label.grid(row=2, column=0, sticky="w", pady=(10, 0))

    year_income_usd_label = ttk.Label(dashboard_right, text="Year income (USD): —", font=font)
    year_income_usd_label.grid(row=3, column=0, sticky="w")

    year_expense_label = ttk.Label(dashboard_right, text="Year expense: —", font=font)
    year_expense_label.grid(row=4, column=0, sticky="w")

    day_cost_label = ttk.Label(dashboard_right, text="Cost per day: —", font=font)
    day_cost_label.grid(row=5, column=0, sticky="w", pady=(10, 0))

    hour_cost_label = ttk.Label(dashboard_right, text="Cost per hour: —", font=font)
    hour_cost_label.grid(row=6, column=0, sticky="w")

    minute_cost_label = ttk.Label(dashboard_right, text="Cost per minute: —", font=font)
    minute_cost_label.grid(row=7, column=0, sticky="w")

    timeline_frame = ttk.LabelFrame(parent, text="Net Worth Timeline")
    timeline_frame.grid(row=1, column=1, sticky="nsew", padx=(6, 10), pady=(6, 10))
    timeline_frame.grid_columnconfigure(0, weight=1)
    timeline_frame.grid_rowconfigure(0, weight=1)
    timeline_canvas = tk.Canvas(timeline_frame, height=180, bg="white", highlightthickness=0)
    timeline_canvas.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)

    breakdown_frame = ttk.LabelFrame(parent, text="Category Breakdown")
    breakdown_frame.grid(row=2, column=0, sticky="nsew", padx=(10, 6), pady=(0, 10))
    breakdown_frame.grid_columnconfigure(0, weight=3)
    breakdown_frame.grid_columnconfigure(1, weight=2)
    breakdown_frame.grid_rowconfigure(0, weight=1)

    breakdown_left = ttk.Frame(breakdown_frame, padding=(10, 10))
    breakdown_left.grid(row=0, column=0, sticky="nsew")
    breakdown_left.grid_columnconfigure(0, weight=1)

    ttk.Label(breakdown_left, text="Expenses", font=("Segoe UI", 10, "bold")).grid(
        row=0, column=0, sticky="w"
    )
    spending_tree = ttk.Treeview(
        breakdown_left,
        columns=("category", "total", "count"),
        show="headings",
        height=7,
    )
    spending_tree.grid(row=1, column=0, sticky="nsew", pady=(6, 14))
    spending_tree.heading("category", text="Category")
    spending_tree.heading("total", text="Total KZT")
    spending_tree.heading("count", text="#")
    spending_tree.column("category", width=140)
    spending_tree.column("total", width=100, anchor="e")
    spending_tree.column("count", width=40, anchor="center")

    ttk.Label(breakdown_left, text="Income", font=("Segoe UI", 10, "bold")).grid(
        row=2, column=0, sticky="w"
    )
    income_tree = ttk.Treeview(
        breakdown_left,
        columns=("category", "total", "count"),
        show="headings",
        height=7,
    )
    income_tree.grid(row=3, column=0, sticky="nsew", pady=(6, 0))
    income_tree.heading("category", text="Category")
    income_tree.heading("total", text="Total KZT")
    income_tree.heading("count", text="#")
    income_tree.column("category", width=140)
    income_tree.column("total", width=100, anchor="e")
    income_tree.column("count", width=40, anchor="center")

    breakdown_right = ttk.Frame(breakdown_frame, padding=(0, 10, 10, 10))
    breakdown_right.grid(row=0, column=1, sticky="nsew")
    breakdown_right.grid_columnconfigure(0, weight=1)
    breakdown_right.grid_rowconfigure(0, weight=1)
    category_canvas = tk.Canvas(
        breakdown_right, width=200, height=200, bg="white", highlightthickness=0
    )
    category_canvas.grid(row=0, column=0, sticky="nsew")

    monthly_frame = ttk.LabelFrame(parent, text="Monthly Report")
    monthly_frame.grid(row=2, column=1, sticky="nsew", padx=(6, 10), pady=(0, 10))
    monthly_frame.grid_columnconfigure(0, weight=1)
    monthly_frame.grid_rowconfigure(0, weight=1)

    monthly_container = ttk.Frame(monthly_frame, padding=(10, 10))
    monthly_container.grid(row=0, column=0, sticky="nsew")
    monthly_container.grid_columnconfigure(0, weight=1)
    monthly_container.grid_rowconfigure(0, weight=1)

    monthly_tree = ttk.Treeview(
        monthly_container,
        columns=("month", "income", "expenses", "cashflow", "savings"),
        show="headings",
        height=10,
    )
    monthly_tree.grid(row=0, column=0, sticky="nsew")
    monthly_tree.heading("month", text="Month")
    monthly_tree.heading("income", text="Income")
    monthly_tree.heading("expenses", text="Expenses")
    monthly_tree.heading("cashflow", text="Cashflow")
    monthly_tree.heading("savings", text="Savings %")
    monthly_tree.column("month", width=80)
    monthly_tree.column("income", width=100, anchor="e")
    monthly_tree.column("expenses", width=100, anchor="e")
    monthly_tree.column("cashflow", width=100, anchor="e")
    monthly_tree.column("savings", width=70, anchor="e")

    monthly_tree.tag_configure("positive", foreground="#10b981")
    monthly_tree.tag_configure("negative", foreground="#ef4444")

    monthly_scroll = ttk.Scrollbar(monthly_container, orient="vertical", command=monthly_tree.yview)
    monthly_scroll.grid(row=0, column=1, sticky="ns", padx=(6, 0))
    monthly_tree.configure(yscrollcommand=monthly_scroll.set)

    last_timeline_data: list = []
    last_spending_data: list = []
    redraw_job: str | None = None

    def _schedule_redraw() -> None:
        nonlocal redraw_job
        if redraw_job is not None:
            try:
                context.after_cancel(redraw_job)
            except Exception:
                pass
        redraw_job = context.after(120, _redraw_canvases)

    def _redraw_canvases() -> None:
        nonlocal redraw_job
        redraw_job = None
        if last_timeline_data:
            _draw_net_worth_line(timeline_canvas, last_timeline_data)
        if last_spending_data:
            _draw_category_pie(category_canvas, last_spending_data)

    def _refresh_analytics() -> None:
        nonlocal last_timeline_data, last_spending_data
        start = period_from_entry.get().strip() or default_start
        end = period_to_entry.get().strip() or default_end

        try:
            from domain.validation import ensure_not_future, parse_ymd

            parsed_start = parse_ymd(start)
            parsed_end = parse_ymd(end)
            ensure_not_future(parsed_start)
            ensure_not_future(parsed_end)
            if parsed_start > parsed_end:
                raise ValueError("Start date must be <= end date")

            start = parsed_start.isoformat()
            end = parsed_end.isoformat()

            net_worth = float(context.controller.get_total_balance(date=end))
            savings_rate = float(context.controller.get_savings_rate(start, end))
            burn_rate = float(context.controller.get_burn_rate(start, end))
            year = int(parsed_end.year)
            avg_monthly_income = float(
                context.controller.get_average_monthly_income(year, up_to_date=end)
            )
            year_income = float(context.controller.get_year_income(year, up_to_date=end))
            year_income_usd = float(context.controller.convert_kzt_to_usd(year_income))
            year_expense = float(context.controller.get_year_expense(year, up_to_date=end))
            avg_monthly_expenses = float(
                context.controller.get_average_monthly_expenses(start, end)
            )
            day_cost, hour_cost, minute_cost = context.controller.get_time_costs(start, end)

            net_worth_label.config(text=f"Net worth:  {net_worth:,.0f} KZT")
            savings_rate_label.config(
                text=f"Savings rate:  {savings_rate:.1f}%",
                foreground="#10b981" if savings_rate >= 0 else "#ef4444",
            )
            burn_rate_label.config(text=f"Burn rate:  {burn_rate:,.0f} KZT/day")
            avg_monthly_income_label.config(
                text=f"Avg monthly income ({year}):  {avg_monthly_income:,.0f} KZT"
            )
            year_income_label.config(text=f"Year income ({year}):  {year_income:,.0f} KZT")
            year_income_usd_label.config(text=f"Year income (USD):  {year_income_usd:,.2f}")
            avg_monthly_expenses_label.config(
                text=f"Avg monthly expenses:  {avg_monthly_expenses:,.0f} KZT"
            )
            year_expense_label.config(text=f"Year expense ({year}):  {year_expense:,.0f} KZT")
            day_cost_label.config(text=f"Cost per day:  {float(day_cost):,.0f} KZT")
            hour_cost_label.config(text=f"Cost per hour:  {float(hour_cost):,.2f} KZT")
            minute_cost_label.config(text=f"Cost per minute:  {float(minute_cost):,.2f} KZT")

            timeline_data = context.controller.get_net_worth_timeline()
            last_timeline_data = list(timeline_data) if timeline_data else []
            timeline_canvas.after(
                50, lambda: _draw_net_worth_line(timeline_canvas, last_timeline_data)
            )

            spending_data = context.controller.get_spending_by_category(start, end)
            last_spending_data = list(spending_data) if spending_data else []
            spending_tree.delete(*spending_tree.get_children())
            for item in spending_data:
                spending_tree.insert(
                    "",
                    "end",
                    values=(
                        getattr(item, "category", ""),
                        f"{float(getattr(item, 'total_kzt', 0.0)):,.0f}",
                        int(getattr(item, "record_count", 0)),
                    ),
                )

            income_data = context.controller.get_income_by_category(start, end)
            income_tree.delete(*income_tree.get_children())
            for item in income_data:
                income_tree.insert(
                    "",
                    "end",
                    values=(
                        getattr(item, "category", ""),
                        f"{float(getattr(item, 'total_kzt', 0.0)):,.0f}",
                        int(getattr(item, "record_count", 0)),
                    ),
                )

            category_canvas.after(
                50, lambda: _draw_category_pie(category_canvas, last_spending_data)
            )

            monthly_data = context.controller.get_monthly_summary(start_date=start, end_date=end)
            monthly_tree.delete(*monthly_tree.get_children())
            for item in monthly_data:
                cashflow = float(getattr(item, "cashflow", 0.0))
                tag = "positive" if cashflow >= 0 else "negative"
                monthly_tree.insert(
                    "",
                    "end",
                    values=(
                        getattr(item, "month", ""),
                        f"{float(getattr(item, 'income', 0.0)):,.0f}",
                        f"{float(getattr(item, 'expenses', 0.0)):,.0f}",
                        f"{cashflow:,.0f}",
                        f"{float(getattr(item, 'savings_rate', 0.0)):.1f}%",
                    ),
                    tags=(tag,),
                )
        except Exception as error:
            logger.warning("Analytics refresh error: %s", error)
            if isinstance(error, ValueError):
                messagebox.showerror(
                    "Invalid period",
                    f"{error}\n\nUse YYYY-MM-DD and ensure dates are not in the future.",
                )

    refresh_button.configure(command=_refresh_analytics)

    def _bind_enter_refresh(entry: ttk.Entry) -> None:
        entry.bind("<Return>", lambda _event: _refresh_analytics())

    _bind_enter_refresh(period_from_entry)
    _bind_enter_refresh(period_to_entry)

    timeline_canvas.bind("<Configure>", lambda _event: _schedule_redraw())
    category_canvas.bind("<Configure>", lambda _event: _schedule_redraw())

    parent.after(100, _refresh_analytics)

    return AnalyticsTabBindings(
        period_from_entry=period_from_entry,
        period_to_entry=period_to_entry,
        net_worth_label=net_worth_label,
        savings_rate_label=savings_rate_label,
        burn_rate_label=burn_rate_label,
        spending_tree=spending_tree,
        income_tree=income_tree,
        category_canvas=category_canvas,
        monthly_tree=monthly_tree,
        timeline_canvas=timeline_canvas,
    )
