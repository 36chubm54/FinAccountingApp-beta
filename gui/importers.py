import logging

from domain.import_policy import ImportPolicy
from domain.records import Record

logger = logging.getLogger(__name__)


def import_records_from_csv(
    filepath: str,
    policy: ImportPolicy = ImportPolicy.FULL_BACKUP,
    currency_service=None,
    wallet_ids: set[int] | None = None,
    existing_initial_balance: float = 0.0,
) -> tuple[list[Record], float, tuple[int, int, list[str]]]:
    try:
        from utils.csv_utils import import_records_from_csv as _import_records_from_csv

        return _import_records_from_csv(
            filepath,
            policy=policy,
            currency_service=currency_service,
            wallet_ids=wallet_ids,
            existing_initial_balance=existing_initial_balance,
        )
    except Exception:
        logger.exception("Failed to import records from csv: %s", filepath)
        raise


def import_records_from_xlsx(
    filepath: str,
    policy: ImportPolicy = ImportPolicy.FULL_BACKUP,
    currency_service=None,
    wallet_ids: set[int] | None = None,
    existing_initial_balance: float = 0.0,
) -> tuple[list[Record], float, tuple[int, int, list[str]]]:
    try:
        from utils.excel_utils import (
            import_records_from_xlsx as _import_records_from_xlsx,
        )

        return _import_records_from_xlsx(
            filepath,
            policy=policy,
            currency_service=currency_service,
            wallet_ids=wallet_ids,
            existing_initial_balance=existing_initial_balance,
        )
    except Exception:
        logger.exception("Failed to import records from xlsx: %s", filepath)
        raise


def import_mandatory_expenses_from_csv(
    filepath: str,
    policy: ImportPolicy = ImportPolicy.FULL_BACKUP,
    currency_service=None,
) -> tuple[list, tuple[int, int, list[str]]]:
    try:
        from utils.csv_utils import import_mandatory_expenses_from_csv

        return import_mandatory_expenses_from_csv(
            filepath, policy=policy, currency_service=currency_service
        )
    except Exception:
        logger.exception("Failed to import mandatory expenses from csv: %s", filepath)
        raise


def import_mandatory_expenses_from_xlsx(
    filepath: str,
    policy: ImportPolicy = ImportPolicy.FULL_BACKUP,
    currency_service=None,
) -> tuple[list, tuple[int, int, list[str]]]:
    try:
        from utils.excel_utils import import_mandatory_expenses_from_xlsx

        return import_mandatory_expenses_from_xlsx(
            filepath, policy=policy, currency_service=currency_service
        )
    except Exception:
        logger.exception("Failed to import mandatory expenses from xlsx: %s", filepath)
        raise


def import_full_backup(filepath: str, *, force: bool = False):
    """Legacy compatibility wrapper.

    Prefer FinancialController.import_data(...) / ImportService.import_file(...)
    for application-level imports. This helper remains for tests, tools, and
    low-level backup JSON parsing flows.
    """
    try:
        from utils.backup_utils import import_full_backup_from_json

        return import_full_backup_from_json(filepath, force=force)
    except Exception:
        logger.exception("Failed to import full backup from json: %s", filepath)
        raise
