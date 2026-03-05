import logging
import os
from collections.abc import Iterable

logger = logging.getLogger(__name__)


def export_report(report, filepath: str, fmt: str) -> None:
    fmt = (fmt or "csv").lower()
    os.makedirs(os.path.dirname(filepath), exist_ok=True) if os.path.dirname(filepath) else None
    try:
        if fmt == "csv":
            from utils.csv_utils import report_to_csv

            report_to_csv(report, filepath)
        elif fmt in ("xlsx", "xls"):
            from utils.excel_utils import report_to_xlsx

            report_to_xlsx(report, filepath)
        elif fmt == "pdf":
            from utils.pdf_utils import report_to_pdf

            report_to_pdf(report, filepath)
        else:
            raise ValueError(f"Unsupported export format: {fmt}")
    except Exception:
        logger.exception("Failed to export report to %s (%s)", filepath, fmt)
        raise


def export_mandatory_expenses(expenses: Iterable, filepath: str, fmt: str) -> None:
    fmt = (fmt or "csv").lower()
    os.makedirs(os.path.dirname(filepath), exist_ok=True) if os.path.dirname(filepath) else None
    try:
        if fmt == "csv":
            from utils.csv_utils import export_mandatory_expenses_to_csv

            export_mandatory_expenses_to_csv(list(expenses), filepath)
        elif fmt in ("xlsx", "xls"):
            from utils.excel_utils import export_mandatory_expenses_to_xlsx

            export_mandatory_expenses_to_xlsx(list(expenses), filepath)
        else:
            raise ValueError(f"Unsupported export format: {fmt}")
    except Exception:
        logger.exception("Failed to export mandatory expenses to %s (%s)", filepath, fmt)
        raise


def export_records(
    records: Iterable,
    filepath: str,
    fmt: str,
    initial_balance: float = 0.0,
    *,
    transfers: Iterable | None = None,
) -> None:
    del initial_balance  # legacy argument
    fmt = (fmt or "csv").lower()
    os.makedirs(os.path.dirname(filepath), exist_ok=True) if os.path.dirname(filepath) else None
    try:
        if fmt == "csv":
            from utils.csv_utils import export_records_to_csv

            export_records_to_csv(list(records), filepath, transfers=list(transfers or []))
        elif fmt in ("xlsx", "xls"):
            from utils.excel_utils import export_records_to_xlsx

            export_records_to_xlsx(list(records), filepath, transfers=list(transfers or []))
        else:
            raise ValueError(f"Unsupported export format: {fmt}")
    except Exception:
        logger.exception("Failed to export records to %s (%s)", filepath, fmt)
        raise


def export_full_backup(
    filepath: str,
    *,
    wallets=None,
    records,
    mandatory_expenses,
    transfers=None,
    initial_balance: float = 0.0,
    readonly: bool = True,
) -> None:
    del initial_balance  # legacy argument
    os.makedirs(os.path.dirname(filepath), exist_ok=True) if os.path.dirname(filepath) else None
    try:
        from utils.backup_utils import export_full_backup_to_json

        export_full_backup_to_json(
            filepath,
            wallets=list(wallets or []),
            records=list(records),
            mandatory_expenses=list(mandatory_expenses),
            transfers=list(transfers or []),
            readonly=readonly,
        )
    except Exception:
        logger.exception("Failed to export full backup to %s", filepath)
        raise
