"""Debts tab - debt and loan management."""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from tkinter import messagebox, ttk
from typing import Any, Protocol

from domain.debt import Debt, DebtKind, DebtOperationType, DebtPayment


class DebtsTabContext(Protocol):
    controller: Any

    def _refresh_list(self) -> None: ...

    def _refresh_charts(self) -> None: ...

    def _refresh_wallets(self) -> None: ...

    def _refresh_all(self) -> None: ...


def refresh_debts_views(context: DebtsTabContext) -> None:
    context._refresh_list()
    context._refresh_charts()
    context._refresh_wallets()
    context._refresh_all()


@dataclass(slots=True)
class DebtsTabBindings:
    debt_tree: ttk.Treeview
    history_tree: ttk.Treeview
    refresh: Callable[[], None]


def _segment_widths(*, total: int, bar_w: int, paid: int, forgiven: int) -> tuple[int, int, int]:
    total = max(int(total), 1)
    bar_w = max(int(bar_w), 1)
    paid = max(0, int(paid))
    forgiven = max(0, int(forgiven))

    paid_w = int(bar_w * paid / total) if paid > 0 else 0
    forgiven_w = int(bar_w * forgiven / total) if forgiven > 0 else 0

    if paid > 0 and paid_w == 0:
        paid_w = 1
    if forgiven > 0 and forgiven_w == 0:
        forgiven_w = 1

    overflow = max(0, paid_w + forgiven_w - bar_w)
    while overflow > 0 and (paid_w > 1 or forgiven_w > 1):
        if paid_w >= forgiven_w and paid_w > 1:
            paid_w -= 1
        elif forgiven_w > 1:
            forgiven_w -= 1
        overflow -= 1

    open_w = max(0, bar_w - paid_w - forgiven_w)
    return paid_w, forgiven_w, open_w


def _draw_debt_progress(canvas: tk.Canvas, debt: Debt | None, payments: list[DebtPayment]) -> None:
    canvas.delete("all")
    width = max(canvas.winfo_width(), 420)
    height = max(canvas.winfo_height(), 70)
    canvas.configure(height=height)
    if debt is None or debt.total_amount_minor <= 0:
        canvas.create_text(
            width // 2,
            height // 2,
            text="Select a debt to view progress",
            fill="#6b7280",
            font=("Segoe UI", 10),
        )
        return

    total = max(1, int(debt.total_amount_minor))
    remaining = int(debt.remaining_amount_minor)
    forgiven = sum(
        int(payment.principal_paid_minor)
        for payment in payments
        if payment.operation_type is DebtOperationType.DEBT_FORGIVE
    )
    paid = max(0, total - remaining - forgiven)
    paid = max(0, min(total, paid))
    forgiven = max(0, min(total - paid, forgiven))
    open_amount = max(0, total - paid - forgiven)

    x0 = 20
    y0 = 18
    bar_w = max(120, width - 40)
    bar_h = 22
    debt_color = "#FF9800" if debt.kind is DebtKind.DEBT else "#2196F3"
    forgive_color = "#9ca3af"
    track_color = "#e5e7eb"
    paid_w, forgiven_w, open_w = _segment_widths(
        total=total,
        bar_w=bar_w,
        paid=paid,
        forgiven=forgiven,
    )

    canvas.create_rectangle(x0, y0, x0 + bar_w, y0 + bar_h, fill=track_color, outline="")
    current_x = x0
    for seg_w, amount, color, is_open_segment in (
        (paid_w, paid, debt_color, False),
        (forgiven_w, forgiven, forgive_color, False),
        (open_w, open_amount, "#ffffff", True),
    ):
        if amount <= 0 or seg_w <= 0:
            continue
        if is_open_segment:
            canvas.create_rectangle(
                current_x,
                y0,
                x0 + bar_w,
                y0 + bar_h,
                fill=color,
                outline="",
            )
        else:
            canvas.create_rectangle(
                current_x,
                y0,
                current_x + seg_w,
                y0 + bar_h,
                fill=color,
                outline="",
            )
            current_x += seg_w

    canvas.create_rectangle(x0, y0, x0 + bar_w, y0 + bar_h, outline="#cbd5e1", width=1)
    canvas.create_text(
        x0,
        y0 + bar_h + 14,
        anchor="w",
        text=f"Paid: {paid / 100:.2f}   Written off: {forgiven / 100:.2f}   Remaining: {remaining / 100:.2f}",  # noqa: E501
        fill="#374151",
        font=("Segoe UI", 9),
    )


def build_debts_tab(
    parent: tk.Frame | ttk.Frame,
    *,
    context: DebtsTabContext,
) -> DebtsTabBindings:
    parent.grid_columnconfigure(0, weight=0)
    parent.grid_columnconfigure(1, weight=1)
    parent.grid_rowconfigure(0, weight=1)

    left = ttk.Frame(parent)
    left.grid(row=0, column=0, sticky="nsw", padx=10, pady=10)
    right = ttk.Frame(parent)
    right.grid(row=0, column=1, sticky="nsew", padx=(0, 10), pady=10)
    right.grid_columnconfigure(0, weight=1)
    right.grid_rowconfigure(0, weight=1)
    right.grid_rowconfigure(1, weight=0)
    right.grid_rowconfigure(2, weight=1)

    create_frame = ttk.LabelFrame(left, text="New Debt / Loan")
    create_frame.grid(row=0, column=0, sticky="ew")
    create_frame.grid_columnconfigure(1, weight=1)

    ttk.Label(create_frame, text="Kind:").grid(row=0, column=0, sticky="w", padx=6, pady=4)
    kind_var = tk.StringVar(value="Debt")
    ttk.OptionMenu(create_frame, kind_var, "Debt", "Debt", "Loan").grid(
        row=0, column=1, sticky="ew", padx=6, pady=4
    )

    ttk.Label(create_frame, text="Contact:").grid(row=1, column=0, sticky="w", padx=6, pady=4)
    contact_entry = ttk.Entry(create_frame)
    contact_entry.grid(row=1, column=1, sticky="ew", padx=6, pady=4)

    ttk.Label(create_frame, text="Amount (KZT):").grid(row=2, column=0, sticky="w", padx=6, pady=4)
    amount_entry = ttk.Entry(create_frame)
    amount_entry.grid(row=2, column=1, sticky="ew", padx=6, pady=4)

    ttk.Label(create_frame, text="Date:").grid(row=3, column=0, sticky="w", padx=6, pady=4)
    date_entry = ttk.Entry(create_frame)
    date_entry.grid(row=3, column=1, sticky="ew", padx=6, pady=4)
    date_entry.insert(0, date.today().isoformat())

    ttk.Label(create_frame, text="Wallet:").grid(row=4, column=0, sticky="w", padx=6, pady=4)
    wallet_var = tk.StringVar(value="")
    wallet_menu = ttk.OptionMenu(create_frame, wallet_var, "")
    wallet_menu.grid(row=4, column=1, sticky="ew", padx=6, pady=4)
    wallet_map: dict[str, int] = {}

    ttk.Label(create_frame, text="Description:").grid(row=5, column=0, sticky="w", padx=6, pady=4)
    description_entry = ttk.Entry(create_frame)
    description_entry.grid(row=5, column=1, sticky="ew", padx=6, pady=4)

    actions_frame = ttk.LabelFrame(left, text="Selected Debt Actions")
    actions_frame.grid(row=1, column=0, sticky="ew", pady=(10, 0))
    actions_frame.grid_columnconfigure(1, weight=1)

    ttk.Label(actions_frame, text="Amount (KZT):").grid(row=0, column=0, sticky="w", padx=6, pady=4)
    action_amount_entry = ttk.Entry(actions_frame)
    action_amount_entry.grid(row=0, column=1, sticky="ew", padx=6, pady=4)

    ttk.Label(actions_frame, text="Date:").grid(row=1, column=0, sticky="w", padx=6, pady=4)
    action_date_entry = ttk.Entry(actions_frame)
    action_date_entry.grid(row=1, column=1, sticky="ew", padx=6, pady=4)
    action_date_entry.insert(0, date.today().isoformat())

    ttk.Label(actions_frame, text="Wallet:").grid(row=2, column=0, sticky="w", padx=6, pady=4)
    action_wallet_var = tk.StringVar(value="")
    action_wallet_menu = ttk.OptionMenu(actions_frame, action_wallet_var, "")
    action_wallet_menu.grid(row=2, column=1, sticky="ew", padx=6, pady=4)

    debt_tree = ttk.Treeview(
        right,
        show="headings",
        columns=("id", "contact", "kind", "total", "remaining", "status", "created"),
        height=10,
    )
    for col, label, width, anchor in (
        ("id", "#", 45, "e"),
        ("contact", "Contact", 160, "w"),
        ("kind", "Kind", 80, "center"),
        ("total", "Total", 95, "e"),
        ("remaining", "Remaining", 95, "e"),
        ("status", "Status", 85, "center"),
        ("created", "Created", 95, "center"),
    ):
        debt_tree.heading(col, text=label)
        debt_tree.column(col, width=width, minwidth=width, anchor=anchor, stretch=col == "contact")  # type: ignore[arg-type]
    debt_tree.grid(row=0, column=0, sticky="nsew")
    debt_scroll = ttk.Scrollbar(right, orient="vertical", command=debt_tree.yview)
    debt_scroll.grid(row=0, column=1, sticky="ns")
    debt_tree.configure(yscrollcommand=debt_scroll.set)

    progress_canvas = tk.Canvas(right, height=72, bg="white", highlightthickness=0)
    progress_canvas.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(8, 8))

    history_frame = ttk.LabelFrame(right, text="History")
    history_frame.grid(row=2, column=0, columnspan=2, sticky="nsew")
    history_frame.grid_columnconfigure(0, weight=1)
    history_frame.grid_rowconfigure(0, weight=1)

    history_tree = ttk.Treeview(
        history_frame,
        show="headings",
        columns=("date", "operation", "amount", "write_off", "record"),
        height=8,
    )
    for col, label, width, anchor in (
        ("date", "Date", 95, "center"),
        ("operation", "Operation", 120, "w"),
        ("amount", "Amount", 90, "e"),
        ("write_off", "Write-off", 80, "center"),
        ("record", "Record ID", 80, "center"),
    ):
        history_tree.heading(col, text=label)
        history_tree.column(
            col,
            width=width,
            minwidth=width,
            anchor=anchor,  # type: ignore[arg-type]
            stretch=col == "operation",
        )
    history_tree.grid(row=0, column=0, sticky="nsew")
    history_scroll = ttk.Scrollbar(history_frame, orient="vertical", command=history_tree.yview)
    history_scroll.grid(row=0, column=1, sticky="ns")
    history_tree.configure(yscrollcommand=history_scroll.set)
    history_tree.tag_configure("writeoff", foreground="#6b7280")

    status_label = ttk.Label(left, text="")
    status_label.grid(row=2, column=0, sticky="w", pady=(8, 0))

    def _refresh_wallets() -> None:
        nonlocal wallet_map
        wallets = context.controller.load_active_wallets()
        wallet_map = {
            f"[{wallet.id}] {wallet.name} ({wallet.currency})": wallet.id for wallet in wallets
        }
        labels = list(wallet_map.keys()) or [""]
        for menu_widget, var in (
            (wallet_menu, wallet_var),
            (action_wallet_menu, action_wallet_var),
        ):
            menu = menu_widget["menu"]
            menu.delete(0, "end")
            for label in labels:
                menu.add_command(
                    label=label, command=lambda value=label, target=var: target.set(value)
                )
            if var.get() not in wallet_map:
                var.set(labels[0])

    def _selected_debt() -> Debt | None:
        selection = debt_tree.selection()
        if not selection:
            return None
        debt_id = int(selection[0])
        return next(
            (item for item in context.controller.get_debts() if int(item.id) == debt_id), None
        )

    def _refresh_history() -> None:
        history_tree.delete(*history_tree.get_children())
        debt = _selected_debt()
        if debt is None:
            _draw_debt_progress(progress_canvas, None, [])
            return
        history = context.controller.get_debt_history(debt.id)
        for payment in history:
            tag = ("writeoff",) if payment.is_write_off else ()
            history_tree.insert(
                "",
                "end",
                values=(
                    payment.payment_date,
                    payment.operation_type.value,
                    f"{payment.principal_paid_minor / 100:.2f}",
                    "Yes" if payment.is_write_off else "No",
                    "" if payment.record_id is None else str(payment.record_id),
                ),
                tags=tag,
            )
        progress_canvas.after(20, lambda: _draw_debt_progress(progress_canvas, debt, history))

    def _refresh() -> None:
        _refresh_wallets()
        debts = context.controller.get_debts()
        current_selection = debt_tree.selection()
        debt_tree.delete(*debt_tree.get_children())
        for debt in debts:
            debt_tree.insert(
                "",
                "end",
                iid=str(debt.id),
                values=(
                    debt.id,
                    debt.contact_name,
                    debt.kind.value,
                    f"{debt.total_amount_minor / 100:.2f}",
                    f"{debt.remaining_amount_minor / 100:.2f}",
                    debt.status.value,
                    debt.created_at,
                ),
            )
        if current_selection and debt_tree.exists(current_selection[0]):
            debt_tree.selection_set(current_selection[0])
        elif debts:
            debt_tree.selection_set(str(debts[0].id))
        status_label.config(
            text=f"{len(context.controller.get_open_debts())} open / {len(debts)} total"
        )
        _refresh_history()

    def _create() -> None:
        contact = contact_entry.get().strip()
        date_text = date_entry.get().strip()
        description = description_entry.get().strip()
        wallet_id = wallet_map.get(wallet_var.get())
        try:
            amount_kzt = float(amount_entry.get().strip().replace(",", "."))
        except ValueError:
            messagebox.showerror("Error", "Amount must be a number.")
            return
        if wallet_id is None:
            messagebox.showerror("Error", "Wallet is required.")
            return
        try:
            if kind_var.get() == "Debt":
                context.controller.create_debt(
                    contact_name=contact,
                    wallet_id=wallet_id,
                    amount_kzt=amount_kzt,
                    created_at=date_text,
                    description=description,
                )
            else:
                context.controller.create_loan(
                    contact_name=contact,
                    wallet_id=wallet_id,
                    amount_kzt=amount_kzt,
                    created_at=date_text,
                    description=description,
                )
            contact_entry.delete(0, tk.END)
            amount_entry.delete(0, tk.END)
            description_entry.delete(0, tk.END)
            _refresh()
            refresh_debts_views(context)
        except Exception as error:
            messagebox.showerror("Debt Error", str(error))

    def _run_on_selected(
        self_name: str,
        action: Callable[[Debt, float, str, int | None], None],
        *,
        wallet_optional: bool = False,
    ) -> None:
        debt = _selected_debt()
        if debt is None:
            messagebox.showerror("Error", "Select a debt first.")
            return
        date_text = action_date_entry.get().strip()
        try:
            amount_kzt = float(action_amount_entry.get().strip().replace(",", "."))
        except ValueError:
            messagebox.showerror("Error", "Amount must be a number.")
            return
        wallet_id = wallet_map.get(action_wallet_var.get())
        if not wallet_optional and wallet_id is None:
            messagebox.showerror("Error", "Wallet is required.")
            return
        wallet_id_arg: int | None = wallet_id
        if not wallet_optional and wallet_id_arg is not None:
            wallet_id_arg = int(wallet_id_arg)
        try:
            action(debt, amount_kzt, date_text, wallet_id_arg)
            _refresh()
        except Exception as error:
            messagebox.showerror(self_name, str(error))

    def _pay() -> None:
        _run_on_selected(
            "Payment Error",
            lambda debt, amount, date_text, wallet_id: context.controller.register_debt_payment(
                debt_id=debt.id,
                wallet_id=int(wallet_id),  # type: ignore[arg-type]
                amount_kzt=amount,
                payment_date=date_text,
            ),
        )
        refresh_debts_views(context)

    def _write_off() -> None:
        _run_on_selected(
            "Write-off Error",
            lambda debt, amount, date_text, _wallet_id: context.controller.register_debt_write_off(
                debt_id=debt.id,
                amount_kzt=amount,
                payment_date=date_text,
            ),
            wallet_optional=True,
        )

    def _close() -> None:
        debt = _selected_debt()
        if debt is None:
            messagebox.showerror("Error", "Select a debt first.")
            return
        wallet_id = wallet_map.get(action_wallet_var.get())
        if wallet_id is None and debt.kind is DebtKind.DEBT:
            messagebox.showerror("Error", "Wallet is required.")
            return
        try:
            context.controller.close_debt(
                debt_id=debt.id,
                payment_date=action_date_entry.get().strip(),
                wallet_id=wallet_id,
                write_off=False,
            )
            _refresh()
            refresh_debts_views(context)
        except Exception as error:
            messagebox.showerror("Close Error", str(error))

    def _delete() -> None:
        debt = _selected_debt()
        if debt is None:
            messagebox.showerror("Error", "Select a debt first.")
            return
        if not messagebox.askyesno(
            "Confirm Delete",
            (
                f"Delete debt for '{debt.contact_name}'?\n\n"
                "This removes the debt card and payment history only.\n"
                "Linked income/expense records and wallet balances will stay unchanged."
            ),
        ):
            return
        try:
            context.controller.delete_debt(debt.id)
            _refresh()
        except Exception as error:
            messagebox.showerror("Delete Error", str(error))

    ttk.Button(create_frame, text="Save", command=_create).grid(
        row=6, column=0, columnspan=2, sticky="ew", padx=6, pady=8
    )
    ttk.Button(actions_frame, text="Pay", command=_pay).grid(
        row=3, column=0, sticky="ew", padx=6, pady=6
    )
    ttk.Button(actions_frame, text="Write off", command=_write_off).grid(
        row=3, column=1, sticky="ew", padx=6, pady=6
    )
    ttk.Button(actions_frame, text="Close", command=_close).grid(
        row=4, column=0, sticky="ew", padx=6, pady=(0, 6)
    )
    ttk.Button(actions_frame, text="Delete", command=_delete).grid(
        row=4, column=1, sticky="ew", padx=6, pady=(0, 6)
    )
    ttk.Button(actions_frame, text="Refresh", command=_refresh).grid(
        row=5, column=0, columnspan=2, sticky="ew", padx=6, pady=(0, 6)
    )

    debt_tree.bind("<<TreeviewSelect>>", lambda _event: _refresh_history(), add="+")
    _refresh()
    return DebtsTabBindings(debt_tree=debt_tree, history_tree=history_tree, refresh=_refresh)
