from __future__ import annotations

import logging
import re
import shutil
from datetime import datetime
from pathlib import Path

from infrastructure.sqlite_repository import SQLiteRecordRepository
from services.distribution_service import DistributionService
from utils.backup_utils import export_full_backup_to_json

logger = logging.getLogger(__name__)


_BACKUP_RE = re.compile(r"^(?P<stem>.+)_backup_(?P<stamp>\d{8}_\d{6})$")


def _prune_backups(
    backup_dir: Path, *, source_stem: str, source_suffix: str, keep_last: int
) -> None:
    candidates: list[tuple[str, Path]] = []
    for path in backup_dir.glob(f"{source_stem}_backup_*{source_suffix}"):
        match = _BACKUP_RE.match(path.stem)
        if not match:
            continue
        if match.group("stem") != source_stem:
            continue
        candidates.append((match.group("stamp"), path))

    candidates.sort(key=lambda item: item[0], reverse=True)
    retained = max(int(keep_last), 0)
    for _stamp, old_path in candidates[retained:]:
        try:
            old_path.unlink()
            logger.info("Pruned old JSON backup: %s", old_path)
        except Exception:
            logger.exception("Failed to prune backup: %s", old_path)


def create_backup(json_path: str, *, keep_last: int | None = None) -> str | None:
    source = Path(json_path)
    if not source.exists():
        return None
    if keep_last is not None and int(keep_last) <= 0:
        logger.info("JSON backup skipped because keep_last=%s", keep_last)
        return None
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = source.parent / "backups"
    backup_dir.mkdir(exist_ok=True)
    backup_path = backup_dir / f"{source.stem}_backup_{stamp}{source.suffix}"
    shutil.copy2(source, backup_path)
    if keep_last is not None:
        _prune_backups(
            backup_dir,
            source_stem=source.stem,
            source_suffix=source.suffix,
            keep_last=int(keep_last),
        )
    logger.info("JSON backup created: %s", backup_path)
    return str(backup_path)


def export_to_json(
    sqlite_path: str,
    json_path: str,
    schema_path: str | None = None,
    *,
    autofreeze_closed_months: bool = True,
) -> None:
    sqlite_repo = SQLiteRecordRepository(sqlite_path, schema_path=schema_path)
    try:
        distribution_service = DistributionService(sqlite_repo)
        if autofreeze_closed_months:
            distribution_service.freeze_closed_months()
        distribution_items, distribution_subitems_by_item = distribution_service.export_structure()
        wallets = sqlite_repo.load_wallets()
        records = sqlite_repo.load_all()
        transfers = sqlite_repo.load_transfers()
        mandatory_expenses = sqlite_repo.load_mandatory_expenses()
        export_full_backup_to_json(
            json_path,
            wallets=wallets,
            records=records,
            mandatory_expenses=mandatory_expenses,
            distribution_items=distribution_items,
            distribution_subitems=[
                subitem
                for item_id in sorted(distribution_subitems_by_item)
                for subitem in distribution_subitems_by_item[item_id]
            ],
            distribution_snapshots=distribution_service.get_frozen_rows(),
            transfers=transfers,
            readonly=False,
            storage_mode="sqlite",
        )
        logger.info("SQLite exported to JSON: %s", json_path)
    finally:
        sqlite_repo.close()
