"""Debts tab - debt and loan management."""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from tkinter import ttk
from typing import Any, Protocol

from domain.debt import Debt, DebtKind, DebtOperationType, DebtPayment
from gui.i18n import tr
from gui.ui_dialogs import messagebox_compat as messagebox
from gui.ui_helpers import attach_treeview_scrollbars
from gui.ui_theme import get_palette


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
    palette = get_palette()
    canvas.delete("all")
    width = max(canvas.winfo_width(), 420)
    height = max(canvas.winfo_height(), 70)
    canvas.configure(
        height=height,
        bg=palette.surface_elevated,
        highlightbackground=palette.border_soft,
    )
    if debt is None or debt.total_amount_minor <= 0:
        canvas.create_text(
            width // 2,
            height // 2,
            text=tr("debts.progress.empty", "Выберите долг, чтобы увидеть прогресс"),
            fill=palette.text_muted,
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
    debt_color = palette.warning if debt.kind is DebtKind.DEBT else palette.accent_blue
    forgive_color = palette.text_muted
    track_color = palette.surface_alt
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
        (open_w, open_amount, palette.surface_elevated, True),
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

    canvas.create_rectangle(x0, y0, x0 + bar_w, y0 + bar_h, outline=palette.border_soft, width=1)
    canvas.create_text(
        x0,
        y0 + bar_h + 14,
        anchor="w",
        text=tr(
            "debts.progress.summary",
            "Погашено: {paid}   Списано: {forgiven}   Осталось: {remaining}",
            paid=f"{paid / 100:.2f}",
            forgiven=f"{forgiven / 100:.2f}",
            remaining=f"{remaining / 100:.2f}",
        ),
        fill=palette.chart_text,
        font=("Segoe UI", 9),
    )


def build_debts_tab(
    parent: tk.Frame | ttk.Frame,
    *,
    context: DebtsTabContext,
) -> DebtsTabBindings:
    palette = get_palette()
    parent.grid_columnconfigure(0, weight=2, uniform="debts")
    parent.grid_columnconfigure(1, weight=5, uniform="debts")
    parent.grid_rowconfigure(0, weight=1)

    left = ttk.Frame(parent)
    left.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
    left.grid_columnconfigure(0, weight=1)
    right = ttk.Frame(parent)
    right.grid(row=0, column=1, sticky="nsew", padx=(0, 10), pady=10)
    right.grid_columnconfigure(0, weight=1)
    right.grid_rowconfigure(0, weight=1)
    right.grid_rowconfigure(1, weight=0)
    right.grid_rowconfigure(2, weight=0)
    right.grid_rowconfigure(3, weight=1)

    create_frame = ttk.LabelFrame(left, text=tr("debts.create.title", "Новый долг / заем"))
    create_frame.grid(row=0, column=0, sticky="ew")
    create_frame.grid_columnconfigure(1, weight=1)

    ttk.Label(create_frame, text=tr("common.type", "Тип:")).grid(
        row=0, column=0, sticky="w", padx=6, pady=4
    )
    debt_label = tr("debts.kind.debt", "Долг")
    loan_label = tr("debts.kind.loan", "Заем")
    kind_var = tk.StringVar(value=debt_label)
    ttk.OptionMenu(create_frame, kind_var, debt_label, debt_label, loan_label).grid(
        row=0, column=1, sticky="ew", padx=6, pady=4
    )

    ttk.Label(create_frame, text=tr("debts.contact", "Контакт:")).grid(
        row=1, column=0, sticky="w", padx=6, pady=4
    )
    contact_entry = ttk.Entry(create_frame)
    contact_entry.grid(row=1, column=1, sticky="ew", padx=6, pady=4)

    ttk.Label(create_frame, text=tr("debts.amount", "Сумма (KZT):")).grid(
        row=2, column=0, sticky="w", padx=6, pady=4
    )
    amount_entry = ttk.Entry(create_frame)
    amount_entry.grid(row=2, column=1, sticky="ew", padx=6, pady=4)

    ttk.Label(create_frame, text=tr("common.date", "Дата:")).grid(
        row=3, column=0, sticky="w", padx=6, pady=4
    )
    date_entry = ttk.Entry(create_frame)
    date_entry.grid(row=3, column=1, sticky="ew", padx=6, pady=4)
    date_entry.insert(0, date.today().isoformat())

    ttk.Label(create_frame, text=tr("common.wallet", "Кошелек:")).grid(
        row=4, column=0, sticky="w", padx=6, pady=4
    )
    wallet_var = tk.StringVar(value="")
    wallet_menu = ttk.OptionMenu(create_frame, wallet_var, "")
    wallet_menu.grid(row=4, column=1, sticky="ew", padx=6, pady=4)
    wallet_map: dict[str, int] = {}

    ttk.Label(create_frame, text=tr("common.description", "Описание:")).grid(
        row=5, column=0, sticky="w", padx=6, pady=4
    )
    description_entry = ttk.Entry(create_frame)
    description_entry.grid(row=5, column=1, sticky="ew", padx=6, pady=4)

    actions_frame = ttk.LabelFrame(
        left, text=tr("debts.actions.title", "Действия по выбранному долгу")
    )
    actions_frame.grid(row=1, column=0, sticky="ew", pady=(10, 0))
    actions_frame.grid_columnconfigure(1, weight=1)

    ttk.Label(actions_frame, text=tr("debts.amount", "Сумма (KZT):")).grid(
        row=0, column=0, sticky="w", padx=6, pady=4
    )
    action_amount_entry = ttk.Entry(actions_frame)
    action_amount_entry.grid(row=0, column=1, sticky="ew", padx=6, pady=4)

    ttk.Label(actions_frame, text=tr("common.date", "Дата:")).grid(
        row=1, column=0, sticky="w", padx=6, pady=4
    )
    action_date_entry = ttk.Entry(actions_frame)
    action_date_entry.grid(row=1, column=1, sticky="ew", padx=6, pady=4)
    action_date_entry.insert(0, date.today().isoformat())

    ttk.Label(actions_frame, text=tr("common.wallet", "Кошелек:")).grid(
        row=2, column=0, sticky="w", padx=6, pady=4
    )
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
        ("contact", tr("debts.contact_short", "Контакт"), 140, "w"),
        ("kind", tr("common.type_short", "Тип"), 80, "center"),
        ("total", tr("debts.total", "Сумма"), 95, "e"),
        ("remaining", tr("debts.remaining", "Остаток"), 110, "e"),
        ("status", tr("common.status", "Статус"), 85, "center"),
        ("created", tr("debts.created", "Создан"), 95, "center"),
    ):
        debt_tree.heading(col, text=label)
        debt_tree.column(col, width=width, minwidth=width, anchor=anchor, stretch=col == "contact")  # type: ignore[arg-type]
    debt_tree.grid(row=0, column=0, sticky="nsew")
    attach_treeview_scrollbars(right, debt_tree, row=0, column=0, horizontal=True)

    progress_canvas = tk.Canvas(
        right,
        height=72,
        bg=palette.surface_elevated,
        highlightthickness=0,
        highlightbackground=palette.border_soft,
    )
    progress_canvas.grid(row=2, column=0, sticky="ew", pady=(8, 8))

    current_debt: Debt | None = None
    current_payments: list[DebtPayment] = []

    def _redraw_progress_on_resize(event=None):
        """Перерисовать прогрессбар при изменении размера canvas."""
        if current_debt is not None:
            _draw_debt_progress(progress_canvas, current_debt, current_payments)
        else:
            _draw_debt_progress(progress_canvas, None, [])

    progress_canvas.bind("<Configure>", _redraw_progress_on_resize)

    history_frame = ttk.LabelFrame(right, text=tr("common.history", "История"))
    history_frame.grid(row=3, column=0, columnspan=2, sticky="nsew")
    history_frame.grid_columnconfigure(0, weight=1)
    history_frame.grid_rowconfigure(0, weight=1)

    history_tree = ttk.Treeview(
        history_frame,
        show="headings",
        columns=("date", "operation", "amount", "write_off", "record"),
        height=8,
    )
    for col, label, width, anchor in (
        ("date", tr("common.date", "Дата"), 95, "center"),
        ("operation", tr("common.operation", "Операция"), 100, "w"),
        ("amount", tr("common.amount", "Сумма"), 90, "e"),
        ("write_off", tr("debts.write_off_short", "Списание"), 100, "center"),
        ("record", tr("debts.record_id", "ID записи"), 100, "center"),
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
    attach_treeview_scrollbars(history_frame, history_tree, row=0, column=0, horizontal=True)
    history_tree.tag_configure("writeoff", foreground=palette.text_muted)

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
        nonlocal current_debt, current_payments
        history_tree.delete(*history_tree.get_children())
        debt = _selected_debt()
        if debt is None:
            current_debt = None
            current_payments = []
            _draw_debt_progress(progress_canvas, None, [])
            return
        history = context.controller.get_debt_history(debt.id)
        current_debt = debt
        current_payments = history
        for payment in history:
            tag = ("writeoff",) if payment.is_write_off else ()
            history_tree.insert(
                "",
                "end",
                values=(
                    payment.payment_date,
                    payment.operation_type.value,
                    f"{payment.principal_paid_minor / 100:.2f}",
                    tr("common.yes", "Да") if payment.is_write_off else tr("common.no", "Нет"),
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

        def _display_kind(kind: DebtKind) -> str:
            return {
                DebtKind.DEBT: tr("debts.kind.debt", "Долг"),
                DebtKind.LOAN: tr("debts.kind.loan", "Заем"),
            }.get(kind, str(kind.value))

        def _display_status(status: Any) -> str:
            raw = str(getattr(status, "value", status))
            return {
                "open": tr("debts.status.open", "Открыт"),
                "closed": tr("debts.status.closed", "Закрыт"),
            }.get(raw, raw)

        for debt in debts:
            debt_tree.insert(
                "",
                "end",
                iid=str(debt.id),
                values=(
                    debt.id,
                    debt.contact_name,
                    _display_kind(debt.kind),
                    f"{debt.total_amount_minor / 100:.2f}",
                    f"{debt.remaining_amount_minor / 100:.2f}",
                    _display_status(debt.status),
                    debt.created_at,
                ),
            )
        if current_selection and debt_tree.exists(current_selection[0]):
            debt_tree.selection_set(current_selection[0])
        elif debts:
            debt_tree.selection_set(str(debts[0].id))
        status_label.config(
            text=tr(
                "debts.status.summary",
                "{open_count} открыто / {total_count} всего",
                open_count=len(context.controller.get_open_debts()),
                total_count=len(debts),
            )
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
            messagebox.showerror(
                tr("common.error", "Ошибка"),
                tr("debts.error.amount_number", "Сумма должна быть числом."),
            )
            return
        if wallet_id is None:
            messagebox.showerror(
                tr("common.error", "Ошибка"),
                tr("debts.error.wallet_required", "Кошелек обязателен."),
            )
            return
        try:
            if kind_var.get() == debt_label:
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
            messagebox.showerror(tr("debts.error.create_title", "Ошибка долга"), str(error))

    def _run_on_selected(
        self_name: str,
        action: Callable[[Debt, float, str, int | None], None],
        *,
        wallet_optional: bool = False,
    ) -> None:
        debt = _selected_debt()
        if debt is None:
            messagebox.showerror(
                tr("common.error", "Ошибка"),
                tr("debts.error.select_first", "Сначала выберите долг."),
            )
            return
        date_text = action_date_entry.get().strip()
        try:
            amount_kzt = float(action_amount_entry.get().strip().replace(",", "."))
        except ValueError:
            messagebox.showerror(
                tr("common.error", "Ошибка"),
                tr("debts.error.amount_number", "Сумма должна быть числом."),
            )
            return
        wallet_id = wallet_map.get(action_wallet_var.get())
        if not wallet_optional and wallet_id is None:
            messagebox.showerror(
                tr("common.error", "Ошибка"),
                tr("debts.error.wallet_required", "Кошелек обязателен."),
            )
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
            tr("debts.error.payment_title", "Ошибка погашения"),
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
            tr("debts.error.writeoff_title", "Ошибка списания"),
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
            messagebox.showerror(
                tr("common.error", "Ошибка"),
                tr("debts.error.select_first", "Сначала выберите долг."),
            )
            return
        wallet_id = wallet_map.get(action_wallet_var.get())
        if wallet_id is None and debt.kind is DebtKind.DEBT:
            messagebox.showerror(
                tr("common.error", "Ошибка"),
                tr("debts.error.wallet_required", "Кошелек обязателен."),
            )
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
            messagebox.showerror(tr("debts.error.close_title", "Ошибка закрытия"), str(error))

    def _delete() -> None:
        debt = _selected_debt()
        if debt is None:
            messagebox.showerror(
                tr("common.error", "Ошибка"),
                tr("debts.error.select_first", "Сначала выберите долг."),
            )
            return
        if not messagebox.askyesno(
            tr("common.confirm", "Подтверждение"),
            tr(
                "debts.confirm.delete",
                "Удалить долг для '{contact}'?\n"
                "\nЭто удалит только карточку долга и историю платежей."
                "\nСвязанные записи доходов/расходов и балансы кошельков останутся без изменений.",
                contact=debt.contact_name,
            ),
        ):
            return
        try:
            context.controller.delete_debt(debt.id)
            _refresh()
        except Exception as error:
            messagebox.showerror(tr("debts.error.delete_title", "Ошибка удаления"), str(error))

    ttk.Button(
        create_frame,
        text=tr("debts.save", "Сохранить"),
        style="Primary.TButton",
        command=_create,
    ).grid(row=6, column=0, columnspan=2, sticky="ew", padx=6, pady=8)
    ttk.Button(actions_frame, text=tr("debts.pay", "Погасить"), command=_pay).grid(
        row=3, column=0, sticky="ew", padx=6, pady=6
    )
    ttk.Button(actions_frame, text=tr("debts.write_off", "Списать"), command=_write_off).grid(
        row=3, column=1, sticky="ew", padx=6, pady=6
    )
    ttk.Button(actions_frame, text=tr("debts.close", "Закрыть"), command=_close).grid(
        row=4, column=0, sticky="ew", padx=6, pady=(0, 6)
    )
    ttk.Button(actions_frame, text=tr("debts.delete", "Удалить"), command=_delete).grid(
        row=4, column=1, sticky="ew", padx=6, pady=(0, 6)
    )
    ttk.Button(actions_frame, text=tr("common.refresh", "Обновить"), command=_refresh).grid(
        row=5, column=0, columnspan=2, sticky="ew", padx=6, pady=(0, 6)
    )

    debt_tree.bind("<<TreeviewSelect>>", lambda _event: _refresh_history(), add="+")
    _refresh()
    return DebtsTabBindings(debt_tree=debt_tree, history_tree=history_tree, refresh=_refresh)
