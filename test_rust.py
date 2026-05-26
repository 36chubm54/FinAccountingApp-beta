import sys
from pathlib import Path
from typing import Protocol, cast

sys.path.insert(0, str(Path(__file__).resolve().parent / "ledgera_core" / "python"))

import ledgera_core as _ledgera_core


class _LedgeraCoreModule(Protocol):
    def convert_amount(self, amount: float, rate: float) -> float: ...


ledgera_core = cast(_LedgeraCoreModule, _ledgera_core)


if __name__ == "__main__":
    result = ledgera_core.convert_amount(100.0, 5.25)
    print(f"convert_amount(100.0, 5.25) = {result}")
