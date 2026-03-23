import os
import tempfile

from domain.records import ExpenseRecord, IncomeRecord
from domain.reports import Report
from utils.pdf_utils import _should_add_by_category_section, report_to_pdf


def test_report_pdf_roundtrip():
    records = [
        IncomeRecord(date="2025-01-01", _amount_init=100.0, category="Salary"),
        ExpenseRecord(date="2025-01-02", _amount_init=30.0, category="Food"),
    ]
    report = Report(records, initial_balance=25.0)

    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        path = tmp.name
    try:
        report_to_pdf(report, path)
        assert os.path.getsize(path) > 0
    finally:
        os.unlink(path)


def test_pdf_filtered_single_category_skips_duplicate_group_section():
    records = [
        IncomeRecord(date="2025-01-01", _amount_init=100.0, category="Salary"),
        ExpenseRecord(date="2025-01-02", _amount_init=30.0, category="Food"),
        IncomeRecord(date="2025-01-03", _amount_init=50.0, category="Salary"),
    ]
    filtered = Report(records, initial_balance=200.0).filter_by_category("Salary")
    groups = filtered.grouped_by_category()

    assert _should_add_by_category_section(filtered, groups) is False
