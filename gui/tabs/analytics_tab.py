"""Compatibility shim for the analytics tab."""

from __future__ import annotations

from gui.tabs.analytics.builder import build_analytics_tab
from gui.tabs.analytics.contracts import AnalyticsTabBindings, AnalyticsTabContext
from gui.tabs.analytics.render import _draw_breakdown_pie, _draw_net_worth_line

__all__ = [
    "AnalyticsTabBindings",
    "AnalyticsTabContext",
    "build_analytics_tab",
    "_draw_breakdown_pie",
    "_draw_net_worth_line",
]
