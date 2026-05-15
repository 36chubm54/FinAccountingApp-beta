"""Debts tab subpackage."""

from .builder import build_debts_tab
from .contracts import DebtsTabBindings, DebtsTabContext, refresh_debts_views
from .render import _draw_debt_progress, _segment_widths

__all__ = [
    "DebtsTabBindings",
    "DebtsTabContext",
    "build_debts_tab",
    "refresh_debts_views",
    "_segment_widths",
    "_draw_debt_progress",
]
