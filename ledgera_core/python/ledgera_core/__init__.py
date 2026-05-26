from . import ledgera_core as _ledgera_core
from .ledgera_core import build_rate, calculate_daily_burn, convert_amount
from .ledgera_core import minor_to_money, money_abs, to_minor_units, to_money_float, to_rate_float

rate_to_text = getattr(_ledgera_core, "rate_to_text", None)
money_diff_text = getattr(_ledgera_core, "money_diff_text", None)
rate_diff_text = getattr(_ledgera_core, "rate_diff_text", None)

__all__ = [
    "build_rate",
    "calculate_daily_burn",
    "convert_amount",
    "minor_to_money",
    "money_abs",
    "to_minor_units",
    "to_money_float",
    "to_rate_float",
]
if rate_to_text is not None:
    __all__.append("rate_to_text")
if money_diff_text is not None:
    __all__.append("money_diff_text")
if rate_diff_text is not None:
    __all__.append("rate_diff_text")
__doc__ = _ledgera_core.__doc__
