"""DashboardService - unified wealth dashboard payload builder."""

from __future__ import annotations

from domain.dashboard import (
    DashboardAllocationSlice,
    DashboardPayload,
    DashboardSummary,
    DashboardTrendPoint,
)
from infrastructure.sqlite_repository import SQLiteRecordRepository
from services.asset_service import AssetService
from services.goal_service import GoalService
from services.timeline_service import TimelineService


class DashboardService:
    def __init__(
        self,
        repository: SQLiteRecordRepository,
        asset_service: AssetService,
        goal_service: GoalService,
        timeline_service: TimelineService,
        *,
        current_net_worth_kzt: float,
    ) -> None:
        self._repo = repository
        self._assets = asset_service
        self._goals = goal_service
        self._timeline = timeline_service
        self._current_net_worth_kzt = float(current_net_worth_kzt)

    def build_payload(self) -> DashboardPayload:
        trend = [
            DashboardTrendPoint(month=str(point.month), balance=float(point.balance))
            for point in self._timeline.get_net_worth_timeline()
        ]
        allocation = [
            DashboardAllocationSlice(
                category=str(category),
                amount_kzt=float(amount_kzt),
                share_pct=float(share_pct),
            )
            for category, amount_kzt, share_pct in self._assets.get_allocation_by_category()
        ]
        goals = self._goals.get_all_goal_progress()
        goals_total = len(goals)
        goals_completed = sum(1 for goal in goals if bool(goal.is_completed))
        assets_total_kzt = float(self._assets.get_total_assets_kzt())
        return DashboardPayload(
            summary=DashboardSummary(
                net_worth_kzt=float(self._current_net_worth_kzt),
                assets_total_kzt=assets_total_kzt,
                goals_completed=goals_completed,
                goals_total=goals_total,
            ),
            trend=list(trend),
            allocation=allocation,
            goals=goals,
        )
