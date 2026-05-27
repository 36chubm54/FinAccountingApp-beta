from . import ledgera_core as _ledgera_core
from .ledgera_core import (
    build_rate,
    calculate_daily_burn,
    convert_amount,
    minor_to_money,
    money_abs,
    to_minor_units,
    to_money_float,
    to_rate_float,
)

cashflow_sum = getattr(_ledgera_core, "cashflow_sum", None)
record_list_rows = getattr(_ledgera_core, "record_list_rows", None)
wallet_balance_parts = getattr(_ledgera_core, "wallet_balance_parts", None)
wallet_balance_rows = getattr(_ledgera_core, "wallet_balance_rows", None)
rate_to_text = getattr(_ledgera_core, "rate_to_text", None)
money_diff_text = getattr(_ledgera_core, "money_diff_text", None)
rate_diff_text = getattr(_ledgera_core, "rate_diff_text", None)
quantize_money_text = getattr(_ledgera_core, "quantize_money_text", None)
quantize_rate_text = getattr(_ledgera_core, "quantize_rate_text", None)

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
if cashflow_sum is not None:
    __all__.append("cashflow_sum")
if record_list_rows is not None:
    __all__.append("record_list_rows")
if wallet_balance_parts is not None:
    __all__.append("wallet_balance_parts")
if wallet_balance_rows is not None:
    __all__.append("wallet_balance_rows")
if rate_to_text is not None:
    __all__.append("rate_to_text")
if money_diff_text is not None:
    __all__.append("money_diff_text")
if rate_diff_text is not None:
    __all__.append("rate_diff_text")
if quantize_money_text is not None:
    __all__.append("quantize_money_text")
if quantize_rate_text is not None:
    __all__.append("quantize_rate_text")
__doc__ = _ledgera_core.__doc__
