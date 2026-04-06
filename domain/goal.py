"""Strategic goal domain model."""

from __future__ import annotations

from dataclasses import dataclass

from .validation import parse_ymd


@dataclass(frozen=True)
class Goal:
    id: int
    title: str
    target_amount_minor: int
    currency: str
    created_at: str
    is_completed: bool = False
    target_date: str | None = None
    description: str = ""

    def __post_init__(self) -> None:
        if int(self.id) <= 0:
            raise ValueError("Goal id must be positive")
        if not str(self.title or "").strip():
            raise ValueError("Goal title is required")
        if int(self.target_amount_minor) <= 0:
            raise ValueError("Goal target amount must be positive")
        currency = str(self.currency or "").strip().upper()
        if len(currency) != 3:
            raise ValueError("Goal currency must be a 3-letter code")
        parse_ymd(self.created_at)
        if self.target_date:
            parse_ymd(self.target_date)


@dataclass(frozen=True)
class GoalProgress:
    goal: Goal
    current_amount: float
    target_amount: float
    progress_pct: float
    is_completed: bool
