from dataclasses import replace

from infrastructure.repositories import RecordRepository


class RecordService:
    def __init__(self, repository: RecordRepository) -> None:
        self._repository = repository

    def update_amount_kzt(self, record_id: int, new_amount_kzt: float) -> None:
        record = self._repository.get_by_id(int(record_id))
        if (
            record.transfer_id is not None
            or str(record.category or "").strip().lower() == "transfer"
        ):
            raise ValueError("Transfer-linked records cannot be edited")
        updated = record.with_updated_amount_kzt(float(new_amount_kzt))
        self._repository.replace(updated)

    def update_record_inline(
        self,
        record_id: int,
        *,
        new_amount_kzt: float,
        new_category: str,
        new_description: str = "",
    ) -> None:
        record = self._repository.get_by_id(int(record_id))
        if (
            record.transfer_id is not None
            or str(record.category or "").strip().lower() == "transfer"
        ):
            raise ValueError("Transfer-linked records cannot be edited")

        category = str(new_category or "").strip()
        if not category:
            raise ValueError("Category is required")

        updated = record.with_updated_amount_kzt(float(new_amount_kzt))
        updated = replace(
            updated,
            category=category,
            description=str(new_description or "").strip(),
        )
        self._repository.replace(updated)

    def update_mandatory_amount_kzt(self, expense_id: int, new_amount_kzt: float) -> None:
        try:
            new_amount_kzt = float(new_amount_kzt)
            if new_amount_kzt <= 0:
                raise ValueError("Сумма должна быть положительной")
        except (TypeError, ValueError) as error:
            raise ValueError(f"Некорректная сумма: {error}") from error

        expense = self._repository.get_mandatory_expense_by_id(int(expense_id))
        updated = expense.with_updated_amount_kzt(new_amount_kzt)
        self._repository.update_mandatory_expense(updated)

    def update_mandatory_date(self, expense_id: int, new_date: str) -> None:
        normalized_date = (new_date or "").strip()
        if normalized_date:
            from domain.validation import parse_ymd

            parse_ymd(normalized_date)

        expense = self._repository.get_mandatory_expense_by_id(int(expense_id))
        updated = expense.with_updated_date(normalized_date)
        self._repository.update_mandatory_expense(updated)
