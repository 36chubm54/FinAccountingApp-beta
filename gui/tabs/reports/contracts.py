"""Public contracts for the reports tab."""

from __future__ import annotations

from typing import Any, Protocol


class ReportsTabContext(Protocol):
    controller: Any
    currency: Any
