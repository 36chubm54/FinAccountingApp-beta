import pytest

from domain.asset import Asset, AssetCategory, AssetSnapshot
from domain.goal import Goal


def test_asset_creation_accepts_valid_active_asset() -> None:
    asset = Asset(
        id=1,
        name="Kaspi Deposit",
        category=AssetCategory.BANK,
        currency="KZT",
        is_active=True,
        created_at="2026-04-05",
        description="Emergency reserve",
    )

    assert asset.category is AssetCategory.BANK
    assert asset.is_active is True


def test_asset_snapshot_rejects_negative_value() -> None:
    with pytest.raises(ValueError, match="Asset snapshot value cannot be negative"):
        AssetSnapshot(
            id=1,
            asset_id=1,
            snapshot_date="2026-04-05",
            value_minor=-1,
            currency="KZT",
        )


def test_goal_requires_positive_target_amount() -> None:
    with pytest.raises(ValueError, match="Goal target amount must be positive"):
        Goal(
            id=1,
            title="Build safety cushion",
            target_amount_minor=0,
            currency="KZT",
            created_at="2026-04-05",
        )


def test_goal_accepts_optional_target_date() -> None:
    goal = Goal(
        id=1,
        title="Buy apartment",
        target_amount_minor=25_000_000_00,
        currency="KZT",
        created_at="2026-04-05",
        target_date="2028-12-31",
    )

    assert goal.target_date == "2028-12-31"
    assert goal.is_completed is False
