"""Compatibility shim for the distribution tab."""

from __future__ import annotations

from gui.tabs.distribution.builder import build_distribution_tab
from gui.tabs.distribution.contracts import DistributionTabBindings, DistributionTabContext
from gui.tabs.distribution.formatting import (
    _default_end,
    _default_start,
    _fmt_amount,
    _parse_snapshot_amount,
    _snapshot_values_to_display,
)

__all__ = [
    "DistributionTabBindings",
    "DistributionTabContext",
    "build_distribution_tab",
    "_snapshot_values_to_display",
    "_parse_snapshot_amount",
    "_fmt_amount",
    "_default_start",
    "_default_end",
]
