"""Compatibility shim for the dashboard tab."""

from __future__ import annotations

from gui.tabs.dashboard.actions import (
    _asset_actions_state,
    _asset_form_error,
    _bulk_snapshot_form_error,
    _goal_form_error,
    _parse_positive_amount,
    _prepare_asset_payload,
    _prepare_bulk_snapshot_entries,
    _prepare_goal_payload,
)
from gui.tabs.dashboard.builder import build_dashboard_tab
from gui.tabs.dashboard.contracts import DashboardTabBindings, DashboardTabContext

__all__ = [
    "DashboardTabBindings",
    "DashboardTabContext",
    "build_dashboard_tab",
    "_parse_positive_amount",
    "_goal_form_error",
    "_asset_form_error",
    "_bulk_snapshot_form_error",
    "_asset_actions_state",
    "_prepare_goal_payload",
    "_prepare_asset_payload",
    "_prepare_bulk_snapshot_entries",
]
