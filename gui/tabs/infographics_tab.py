"""Infographics tab — expense and income data aggregation and visualization"""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from dataclasses import dataclass
from tkinter import ttk


@dataclass(slots=True)
class InfographicsTabBindings:
    pie_month_var: tk.StringVar
    pie_month_menu: ttk.OptionMenu
    chart_month_var: tk.StringVar
    chart_month_menu: ttk.OptionMenu
    chart_year_var: tk.StringVar
    chart_year_menu: ttk.OptionMenu
    expense_pie_canvas: tk.Canvas
    expense_legend_canvas: tk.Canvas
    expense_legend_frame: tk.Frame
    daily_bar_canvas: tk.Canvas
    monthly_bar_canvas: tk.Canvas


def build_infographics_tab(
    parent: tk.Frame | ttk.Frame,
    *,
    on_chart_filter_change: Callable[..., None],
    on_refresh_charts: Callable[[], None],
    on_legend_mousewheel: Callable[[tk.Event], None],
    bind_all: Callable[[str, Callable[[tk.Event], None]], str],
    after: Callable[[int, Callable[[], None]], str],
    after_cancel: Callable[[str], None],
) -> InfographicsTabBindings:
    pie_frame = ttk.LabelFrame(parent, text="Expenses by category")
    pie_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=10)

    pie_controls = tk.Frame(pie_frame)
    pie_controls.pack(fill=tk.X, padx=10, pady=(8, 0))
    ttk.Label(pie_controls, text="Month:").pack(side=tk.LEFT)

    pie_month_var = tk.StringVar()
    pie_month_menu = ttk.OptionMenu(pie_controls, pie_month_var, "")
    pie_month_menu.pack(side=tk.LEFT, padx=6)
    pie_month_var.trace_add("write", on_chart_filter_change)

    daily_frame = ttk.LabelFrame(parent, text="Income/expense by day of month")
    daily_frame.grid(row=1, column=1, sticky="nsew", padx=10, pady=10)

    monthly_frame = ttk.LabelFrame(parent, text="Income/expense by months of year")
    monthly_frame.grid(row=2, column=0, columnspan=2, sticky="nsew", padx=10, pady=10)

    parent.grid_columnconfigure(0, weight=1)
    parent.grid_columnconfigure(1, weight=1)
    parent.grid_rowconfigure(1, weight=1)
    parent.grid_rowconfigure(2, weight=1)

    expense_pie_canvas = tk.Canvas(pie_frame, height=240, bg="white", highlightthickness=0)
    expense_pie_canvas.pack(fill=tk.BOTH, expand=True, padx=10, pady=(10, 6))

    legend_container = tk.Frame(pie_frame)
    legend_container.pack(fill=tk.BOTH, expand=False, padx=10, pady=(0, 10))
    expense_legend_canvas = tk.Canvas(legend_container, height=110, highlightthickness=0)
    expense_legend_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    legend_scroll = ttk.Scrollbar(
        legend_container,
        orient="vertical",
        command=expense_legend_canvas.yview,
    )
    legend_scroll.pack(side=tk.RIGHT, fill=tk.Y)
    expense_legend_canvas.configure(yscrollcommand=legend_scroll.set)

    expense_legend_frame = tk.Frame(expense_legend_canvas)
    expense_legend_canvas.create_window((0, 0), window=expense_legend_frame, anchor="nw")

    def _update_legend_scroll(_event: object | None = None) -> None:
        expense_legend_canvas.configure(scrollregion=expense_legend_canvas.bbox("all"))

    expense_legend_frame.bind("<Configure>", _update_legend_scroll)
    expense_legend_canvas.bind("<MouseWheel>", on_legend_mousewheel)
    expense_legend_frame.bind("<MouseWheel>", on_legend_mousewheel)

    bind_all("<MouseWheel>", on_legend_mousewheel)

    daily_controls = tk.Frame(daily_frame)
    daily_controls.pack(fill=tk.X, padx=10, pady=(10, 0))
    ttk.Label(daily_controls, text="Month:").pack(side=tk.LEFT)

    chart_month_var = tk.StringVar()
    chart_month_menu = ttk.OptionMenu(daily_controls, chart_month_var, "")
    chart_month_menu.pack(side=tk.LEFT, padx=6)
    chart_month_var.trace_add("write", on_chart_filter_change)

    daily_bar_canvas = tk.Canvas(daily_frame, height=220, bg="white", highlightthickness=0)
    daily_bar_canvas.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    monthly_controls = tk.Frame(monthly_frame)
    monthly_controls.pack(fill=tk.X, padx=10, pady=(10, 0))
    ttk.Label(monthly_controls, text="Year:").pack(side=tk.LEFT)

    chart_year_var = tk.StringVar()
    chart_year_menu = ttk.OptionMenu(monthly_controls, chart_year_var, "")
    chart_year_menu.pack(side=tk.LEFT, padx=6)
    chart_year_var.trace_add("write", on_chart_filter_change)

    monthly_bar_canvas = tk.Canvas(monthly_frame, height=220, bg="white", highlightthickness=0)
    monthly_bar_canvas.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    chart_redraw_job: str | None = None

    def _schedule_redraw(_event: object | None = None) -> None:
        nonlocal chart_redraw_job
        if chart_redraw_job is not None:
            try:
                after_cancel(chart_redraw_job)
            except Exception:
                pass
        chart_redraw_job = after(120, on_refresh_charts)

    expense_pie_canvas.bind("<Configure>", _schedule_redraw)
    daily_bar_canvas.bind("<Configure>", _schedule_redraw)
    monthly_bar_canvas.bind("<Configure>", _schedule_redraw)

    return InfographicsTabBindings(
        pie_month_var=pie_month_var,
        pie_month_menu=pie_month_menu,
        chart_month_var=chart_month_var,
        chart_month_menu=chart_month_menu,
        chart_year_var=chart_year_var,
        chart_year_menu=chart_year_menu,
        expense_pie_canvas=expense_pie_canvas,
        expense_legend_canvas=expense_legend_canvas,
        expense_legend_frame=expense_legend_frame,
        daily_bar_canvas=daily_bar_canvas,
        monthly_bar_canvas=monthly_bar_canvas,
    )
