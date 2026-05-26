import sys
from pathlib import Path
from typing import Protocol, cast

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import ledgera_core as _ledgera_core


class _LedgeraCoreModule(Protocol):
    def convert_amount(self, amount: float, rate: float) -> float: ...

    def calculate_daily_burn(self, total_spent: float, days_passed: int) -> float: ...


ledgera_core = cast(_LedgeraCoreModule, _ledgera_core)


def test_convert_amount():
    assert ledgera_core.convert_amount(100.0, 5.25) == pytest.approx(525.0)


def test_calculate_daily_burn():
    assert ledgera_core.calculate_daily_burn(100.0, 10) == pytest.approx(10.0)
