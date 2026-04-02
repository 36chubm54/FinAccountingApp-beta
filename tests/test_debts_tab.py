from __future__ import annotations

import sqlite3
import tkinter as tk
from pathlib import Path
from tkinter import ttk
from typing import cast
from unittest.mock import patch

from app.services import CurrencyService
from gui.controllers import FinancialController
from gui.tabs.debts_tab import DebtsTabContext, _segment_widths, build_debts_tab
from infrastructure.sqlite_repository import SQLiteRecordRepository


def _schema_path() -> str:
    return str(Path(__file__).resolve().parents[1] / "db" / "schema.sql")


def _build_repo(tmp_path: Path, name: str = "debts_tab.db") -> SQLiteRecordRepository:
    db_path = tmp_path / name
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(Path(_schema_path()).read_text(encoding="utf-8"))
        conn.execute(
            """
            INSERT INTO wallets (
                id,
                name,
                currency,
                initial_balance,
                initial_balance_minor,
                system,
                allow_negative,
                is_active
            )
            VALUES
                (1, 'Main', 'KZT', 0, 0, 1, 0, 1),
                (2, 'Cash', 'KZT', 1000, 100000, 0, 0, 1)
            """
        )
        conn.commit()
    finally:
        conn.close()
    return SQLiteRecordRepository(str(db_path), schema_path=_schema_path())


def _find_button(parent: tk.Misc, text: str) -> tk.Button | ttk.Button | None:
    for child in parent.winfo_children():
        if isinstance(child, (tk.Button, ttk.Button)):
            try:
                if child.cget("text") == text:
                    return child
            except Exception:
                pass
        nested = _find_button(child, text)
        if nested is not None:
            return nested
    return None


def _find_entry_by_order(parent: tk.Misc, index: int) -> tk.Entry:
    entries: list[tk.Entry] = []

    def _collect(node: tk.Misc) -> None:
        for child in node.winfo_children():
            if isinstance(child, tk.Entry):
                entries.append(child)
            _collect(child)

    _collect(parent)
    return entries[index]


def test_debts_tab_create_and_pay_flow(tmp_path: Path) -> None:
    repo = _build_repo(tmp_path)
    controller = FinancialController(repo, CurrencyService())
    root = tk.Tk()
    root.withdraw()
    try:
        parent = tk.Frame(root)
        parent.pack()
        bindings = build_debts_tab(
            parent, context=cast(DebtsTabContext, type("Ctx", (), {"controller": controller})())
        )
        root.update_idletasks()

        contact_entry = _find_entry_by_order(parent, 0)
        amount_entry = _find_entry_by_order(parent, 1)
        date_entry = _find_entry_by_order(parent, 2)
        action_amount_entry = _find_entry_by_order(parent, 4)
        action_date_entry = _find_entry_by_order(parent, 5)

        contact_entry.insert(0, "Alice")
        amount_entry.insert(0, "300")
        date_entry.delete(0, tk.END)
        date_entry.insert(0, "2026-03-01")

        with (
            patch("gui.tabs.debts_tab.messagebox.showerror"),
            patch("gui.tabs.debts_tab.messagebox.askyesno", return_value=True),
        ):
            save_button = _find_button(parent, "Save")
            assert save_button is not None
            save_button.invoke()
            root.update_idletasks()

            rows = bindings.debt_tree.get_children()
            assert len(rows) == 1
            bindings.debt_tree.selection_set(rows[0])
            bindings.refresh()
            root.update_idletasks()

            action_amount_entry.delete(0, tk.END)
            action_amount_entry.insert(0, "100")
            action_date_entry.delete(0, tk.END)
            action_date_entry.insert(0, "2026-03-02")
            pay_button = _find_button(parent, "Pay")
            assert pay_button is not None
            pay_button.invoke()
            root.update_idletasks()

            history_rows = bindings.history_tree.get_children()
            assert len(history_rows) == 1
            debts = controller.get_debts()
            assert len(debts) == 1
            assert debts[0].remaining_amount_minor == 20000
    finally:
        repo.close()
        root.destroy()


def test_debts_tab_delete_confirmation_explains_records_are_kept(tmp_path: Path) -> None:
    repo = _build_repo(tmp_path, "debts_tab_delete.db")
    controller = FinancialController(repo, CurrencyService())
    root = tk.Tk()
    root.withdraw()
    try:
        debt = controller.create_debt(
            contact_name="Alice",
            wallet_id=2,
            amount_kzt=300.0,
            created_at="2026-03-01",
        )
        parent = tk.Frame(root)
        parent.pack()
        bindings = build_debts_tab(
            parent, context=cast(DebtsTabContext, type("Ctx", (), {"controller": controller})())
        )
        root.update_idletasks()
        bindings.debt_tree.selection_set(str(debt.id))

        with (
            patch("gui.tabs.debts_tab.messagebox.showerror"),
            patch("gui.tabs.debts_tab.messagebox.askyesno", return_value=False) as askyesno,
        ):
            delete_button = _find_button(parent, "Delete")
            assert delete_button is not None
            delete_button.invoke()
            root.update_idletasks()

        askyesno.assert_called_once()
        _, prompt = askyesno.call_args.args
        assert "payment history only" in prompt
        assert "Linked income/expense records and wallet balances will stay unchanged." in prompt
        assert len(controller.get_debts()) == 1
    finally:
        repo.close()
        root.destroy()


def test_debt_progress_segment_widths_keep_tiny_payment_visible() -> None:
    paid_w, forgiven_w, open_w = _segment_widths(
        total=1_000_000,
        bar_w=200,
        paid=1,
        forgiven=0,
    )

    assert paid_w == 1
    assert forgiven_w == 0
    assert open_w == 199


def test_debt_progress_segment_widths_keep_tiny_writeoff_visible() -> None:
    paid_w, forgiven_w, open_w = _segment_widths(
        total=1_000_000,
        bar_w=200,
        paid=0,
        forgiven=1,
    )

    assert paid_w == 0
    assert forgiven_w == 1
    assert open_w == 199


def test_debt_progress_segment_widths_split_evenly_for_half_paid_case() -> None:
    paid_w, forgiven_w, open_w = _segment_widths(
        total=1_000,
        bar_w=200,
        paid=500,
        forgiven=0,
    )

    assert paid_w == 100
    assert forgiven_w == 0
    assert open_w == 100
