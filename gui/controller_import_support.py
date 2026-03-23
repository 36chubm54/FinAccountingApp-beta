from __future__ import annotations

import logging
from dataclasses import replace

from domain.records import Record
from domain.transfers import Transfer
from infrastructure.repositories import RecordRepository


def run_import_transaction(repository: RecordRepository, operation, logger: logging.Logger):
    wallets_snapshot = repository.load_wallets()
    records_snapshot = repository.load_all()
    mandatory_snapshot = repository.load_mandatory_expenses()
    transfers_snapshot = repository.load_transfers()
    try:
        return operation()
    except Exception as import_error:
        logger.exception("Import failed, rolling back repository state")
        try:
            repository.replace_all_data(
                wallets=wallets_snapshot,
                records=records_snapshot,
                mandatory_expenses=mandatory_snapshot,
                transfers=transfers_snapshot,
            )
        except Exception:
            logger.exception("Rollback failed after import error")
        raise import_error


def normalize_operation_ids_for_import(repository: RecordRepository) -> None:
    def record_sort_key(record: Record) -> tuple[str, int]:
        return (str(record.date), int(record.id))

    records = sorted(repository.load_all(), key=record_sort_key)
    transfers = sorted(repository.load_transfers(), key=lambda item: (str(item.date), int(item.id)))
    transfer_id_map = {int(item.id): index for index, item in enumerate(transfers, start=1)}
    normalized_transfers: list[Transfer] = [
        replace(transfer, id=transfer_id_map[int(transfer.id)]) for transfer in transfers
    ]
    normalized_records: list[Record] = []
    for index, record in enumerate(records, start=1):
        mapped_transfer_id = None
        if record.transfer_id is not None:
            mapped_transfer_id = transfer_id_map.get(int(record.transfer_id))
        normalized_records.append(replace(record, id=index, transfer_id=mapped_transfer_id))
    repository.replace_records_and_transfers(normalized_records, normalized_transfers)
