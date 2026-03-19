from dataclasses import dataclass
from datetime import date as dt_date

from utils.money import to_money_float, to_rate_float

from .validation import parse_ymd


@dataclass(frozen=True)
class Transfer:
    id: int
    from_wallet_id: int
    to_wallet_id: int
    date: dt_date | str
    amount_original: float
    currency: str
    rate_at_operation: float
    amount_kzt: float
    description: str = ""

    def __post_init__(self) -> None:
        if isinstance(self.date, dt_date):
            parsed = self.date
        else:
            parsed = parse_ymd((self.date or "").strip())
        object.__setattr__(self, "date", parsed)

        if int(self.id) <= 0:
            raise ValueError("Transfer id must be positive")
        if int(self.from_wallet_id) <= 0 or int(self.to_wallet_id) <= 0:
            raise ValueError("Transfer wallet ids must be positive")
        if int(self.from_wallet_id) == int(self.to_wallet_id):
            raise ValueError("Transfer source and destination wallets must be different")
        object.__setattr__(self, "amount_original", to_money_float(self.amount_original))
        object.__setattr__(self, "amount_kzt", to_money_float(self.amount_kzt))
        object.__setattr__(self, "rate_at_operation", to_rate_float(self.rate_at_operation))
        if float(self.amount_original) <= 0:
            raise ValueError("Transfer amount must be positive")
        if float(self.amount_kzt) <= 0:
            raise ValueError("Transfer amount_kzt must be positive")
