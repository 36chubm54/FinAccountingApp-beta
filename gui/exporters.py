import logging
import os
from collections.abc import Iterable

logger = logging.getLogger(__name__)


def _raise_missing_pdf_dependency(exc: ModuleNotFoundError) -> None:
    if exc.name and exc.name.startswith("reportlab"):
        raise RuntimeError(
            "PDF export requires the optional 'pdf' dependency. "
            "Install it with `pip install .[pdf]` or add `reportlab==4.0.0` manually."
        ) from exc
    raise exc


def export_report(report, filepath: str, fmt: str, *, debts=None) -> None:
    fmt = (fmt or "csv").lower()
    os.makedirs(os.path.dirname(filepath), exist_ok=True) if os.path.dirname(filepath) else None
    try:
        if fmt == "csv":
            from utils.csv_utils import report_to_csv

            report_to_csv(report, filepath)
        elif fmt in ("xlsx", "xls"):
            from utils.excel_utils import report_to_xlsx

            report_to_xlsx(report, filepath, debts=list(debts or []))
        elif fmt == "pdf":
            report_to_pdf = None
            try:
                from utils.pdf_utils import report_to_pdf as pdf_func

                report_to_pdf = pdf_func
            except ModuleNotFoundError as exc:
                _raise_missing_pdf_dependency(exc)

            assert report_to_pdf is not None
            report_to_pdf(report, filepath, debts=list(debts or []))
        else:
            raise ValueError(f"Unsupported export format: {fmt}")
    except Exception:
        logger.exception("Failed to export report to %s (%s)", filepath, fmt)
        raise


def export_grouped_report(
    statement_title: str,
    grouped_rows: list[tuple[str, int, float]],
    filepath: str,
    fmt: str,
) -> None:
    fmt = (fmt or "csv").lower()
    os.makedirs(os.path.dirname(filepath), exist_ok=True) if os.path.dirname(filepath) else None
    try:
        if fmt == "csv":
            from utils.csv_utils import grouped_report_to_csv

            grouped_report_to_csv(statement_title, grouped_rows, filepath)
        elif fmt in ("xlsx", "xls"):
            from utils.excel_utils import grouped_report_to_xlsx

            grouped_report_to_xlsx(statement_title, grouped_rows, filepath)
        elif fmt == "pdf":
            grouped_report_to_pdf = None
            try:
                from utils.pdf_utils import grouped_report_to_pdf as pdf_func

                grouped_report_to_pdf = pdf_func
            except ModuleNotFoundError as exc:
                _raise_missing_pdf_dependency(exc)

            assert grouped_report_to_pdf is not None
            grouped_report_to_pdf(statement_title, grouped_rows, filepath)
        else:
            raise ValueError(f"Unsupported export format: {fmt}")
    except Exception:
        logger.exception("Failed to export grouped report to %s (%s)", filepath, fmt)
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
    budgets=(),
    debts=(),
    debt_payments=(),
    assets=(),
    asset_snapshots=(),
    goals=(),
    distribution_items=(),
    distribution_subitems=(),
    distribution_snapshots=(),
    transfers=None,
    initial_balance: float = 0.0,
    readonly: bool = True,
    storage_mode: str = "unknown",
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
            budgets=list(budgets or []),
            debts=list(debts or []),
            debt_payments=list(debt_payments or []),
            assets=list(assets or []),
            asset_snapshots=list(asset_snapshots or []),
            goals=list(goals or []),
            distribution_items=list(distribution_items or []),
            distribution_subitems=list(distribution_subitems or []),
            distribution_snapshots=list(distribution_snapshots or []),
            transfers=list(transfers or []),
            readonly=readonly,
            storage_mode=storage_mode,
        )
    except Exception:
        logger.exception("Failed to export full backup to %s", filepath)
        raise
