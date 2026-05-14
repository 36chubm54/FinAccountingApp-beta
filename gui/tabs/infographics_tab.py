"""Compatibility shim for the infographics tab."""

from __future__ import annotations

from .infographics.builder import build_infographics_tab
from .infographics.contracts import InfographicsTabBindings
from .infographics.pie_section import (
    _legend_category_max_width,
    draw_expense_pie,
    update_pie_month_options,
)

__all__ = [
    "InfographicsTabBindings",
    "build_infographics_tab",
    "draw_expense_pie",
    "update_pie_month_options",
    "_legend_category_max_width",
]
