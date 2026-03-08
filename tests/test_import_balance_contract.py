from unittest.mock import Mock, patch

from app.services import CurrencyService
from domain.import_policy import ImportPolicy
from domain.import_result import ImportResult
from domain.wallets import Wallet
from gui.controllers import FinancialController
from infrastructure.repositories import RecordRepository


def _build_controller() -> tuple[FinancialController, Mock, Mock]:
    repository = Mock(spec=RecordRepository)
    repository.load_wallets.return_value = [
        Wallet(id=1, name="Main", currency="KZT", initial_balance=0.0, system=True)
    ]
    repository.load_initial_balance.return_value = 77.0
    currency = Mock(spec=CurrencyService)
    return FinancialController(repository, currency), repository, currency


def test_import_records_csv_uses_import_service_with_selected_policy() -> None:
    controller, _, _ = _build_controller()
    with patch("services.import_service.ImportService.import_file") as import_file:
        import_file.return_value = ImportResult(imported=2, skipped=0, errors=[])
        summary = controller.import_records("CSV", "dummy.csv", policy=ImportPolicy.FULL_BACKUP)
    import_file.assert_called_once_with("dummy.csv", force=False, dry_run=False)
    assert summary == ImportResult(imported=2, skipped=0, errors=[])


def test_import_records_xlsx_uses_import_service_with_selected_policy() -> None:
    controller, _, _ = _build_controller()
    with patch("services.import_service.ImportService.import_file") as import_file:
        import_file.return_value = ImportResult(imported=1, skipped=0, errors=[])
        summary = controller.import_records("XLSX", "dummy.xlsx", policy=ImportPolicy.CURRENT_RATE)
    import_file.assert_called_once_with("dummy.xlsx", force=False, dry_run=False)
    assert summary == ImportResult(imported=1, skipped=0, errors=[])


def test_import_records_json_uses_import_service() -> None:
    controller, _, _ = _build_controller()
    with patch("services.import_service.ImportService.import_file") as import_file:
        import_file.return_value = ImportResult(imported=10, skipped=0, errors=[])
        summary = controller.import_records("JSON", "dummy.json", policy=ImportPolicy.FULL_BACKUP)
    import_file.assert_called_once_with("dummy.json", force=False, dry_run=False)
    assert summary == ImportResult(imported=10, skipped=0, errors=[])
