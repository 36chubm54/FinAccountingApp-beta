"""Asset domain models."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .validation import parse_ymd


class AssetCategory(Enum):
    BANK = "bank"
    CRYPTO = "crypto"
    CASH = "cash"
    OTHER = "other"


@dataclass(frozen=True)
class Asset:
    id: int
    name: str
    category: AssetCategory
    currency: str
    is_active: bool
    created_at: str
    description: str = ""

    def __post_init__(self) -> None:
        if int(self.id) <= 0:
            raise ValueError("Asset id must be positive")
        if not str(self.name or "").strip():
            raise ValueError("Asset name is required")
        currency = str(self.currency or "").strip().upper()
        if len(currency) != 3:
            raise ValueError("Asset currency must be a 3-letter code")
        parse_ymd(self.created_at)


@dataclass(frozen=True)
class AssetSnapshot:
    id: int
    asset_id: int
    snapshot_date: str
    value_minor: int
    currency: str
    note: str = ""

    def __post_init__(self) -> None:
        if int(self.id) <= 0:
            raise ValueError("Asset snapshot id must be positive")
        if int(self.asset_id) <= 0:
            raise ValueError("Asset snapshot asset_id must be positive")
        if int(self.value_minor) < 0:
            raise ValueError("Asset snapshot value cannot be negative")
        currency = str(self.currency or "").strip().upper()
        if len(currency) != 3:
            raise ValueError("Asset snapshot currency must be a 3-letter code")
        parse_ymd(self.snapshot_date)
