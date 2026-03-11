from __future__ import annotations

import re
from pathlib import Path

from domain.validation import VALID_PERIODS


def _schema_sql() -> str:
    return (Path(__file__).resolve().parents[1] / "db" / "schema.sql").read_text(encoding="utf-8")


def test_schema_period_constraints_match_domain_contract() -> None:
    """
    Contract test: the DB schema should accept the same `period` values as the domain.

    We keep domain validation even with DB CHECK constraints:
    - domain: early, user-friendly errors (imports/GUI), no DB dependency
    - DB: last line of defense for integrity (manual edits, legacy code paths)
    """

    periods_sql = ", ".join(f"'{p}'" for p in VALID_PERIODS)
    schema = _schema_sql()

    records_period_check = re.search(
        rf"period\s+TEXT\s+CHECK\s*\(\s*period\s+IN\s*\(\s*{re.escape(periods_sql)}\s*\)\s*OR\s*period\s+IS\s+NULL\s*\)",
        schema,
        flags=re.IGNORECASE,
    )
    assert records_period_check is not None

    mandatory_period_check = re.search(
        rf"mandatory_expenses\s*\(.*?period\s+TEXT\s+NOT\s+NULL\s+CHECK\s*\(\s*period\s+IN\s*\(\s*{re.escape(periods_sql)}\s*\)\s*\)",
        schema,
        flags=re.IGNORECASE | re.DOTALL,
    )
    assert mandatory_period_check is not None
