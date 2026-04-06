"""Dashboard tab - strategic overview for assets, goals and wealth trend."""

from __future__ import annotations

import logging
import tkinter as tk
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from tkinter import messagebox, ttk
from typing import Any, Protocol

from domain.asset import Asset
from domain.dashboard import DashboardAllocationSlice, DashboardPayload, DashboardTrendPoint
from domain.goal import GoalProgress
from domain.validation import ensure_not_future, parse_ymd

logger = logging.getLogger(__name__)

_PALETTE = [
    "#1d4ed8",
    "#059669",
    "#d97706",
    "#dc2626",
    "#7c3aed",
    "#0891b2",
    "#65a30d",
    "#ea580c",
]


class DashboardTabContext(Protocol):
    controller: Any

    def after(self, ms: int, func: Callable[[], None]) -> str: ...

    def after_cancel(self, id: str) -> None: ...


@dataclass(slots=True)
class DashboardTabBindings:
    net_worth_label: ttk.Label
    assets_total_label: ttk.Label
    goals_status_label: ttk.Label
    assets_status_label: ttk.Label
    trend_canvas: tk.Canvas
    allocation_canvas: tk.Canvas
    goals_canvas: tk.Canvas
    create_asset_button: ttk.Button
    manage_assets_button: ttk.Button
    create_goal_button: ttk.Button
    bulk_update_button: ttk.Button
    refresh: Callable[[], None]


def _format_money(value: float) -> str:
    return f"{float(value):,.0f} KZT"


def _minor_to_money_text(value_minor: int) -> str:
    return f"{float(value_minor) / 100.0:,.2f}"


def _set_button_enabled(button: ttk.Button, enabled: bool) -> None:
    button.state(["!disabled"] if enabled else ["disabled"])


def _parse_positive_amount(raw_value: str, *, field_name: str) -> float:
    text = str(raw_value or "").strip()
    if not text:
        raise ValueError(f"{field_name} is required")
    try:
        value = float(text.replace(",", ""))
    except ValueError as exc:
        raise ValueError(f"{field_name} must be a number") from exc
    if value <= 0:
        raise ValueError(f"{field_name} must be positive")
    return value


def _goal_form_error(
    *,
    title: str,
    target_amount: str,
    currency: str,
    created_at: str,
    target_date: str,
    description: str,
) -> str | None:
    try:
        _prepare_goal_payload(
            title=title,
            target_amount=target_amount,
            currency=currency,
            created_at=created_at,
            target_date=target_date,
            description=description,
        )
    except ValueError as error:
        return str(error)
    return None


def _asset_form_error(
    *,
    name: str,
    category: str,
    currency: str,
    created_at: str,
    description: str,
) -> str | None:
    try:
        _prepare_asset_payload(
            name=name,
            category=category,
            currency=currency,
            created_at=created_at,
            description=description,
        )
    except ValueError as error:
        return str(error)
    return None


def _bulk_snapshot_form_error(
    *,
    assets: list[Asset],
    snapshot_date: str,
    value_by_asset_id: dict[int, str],
    note_by_asset_id: dict[int, str],
) -> str | None:
    try:
        entries = _prepare_bulk_snapshot_entries(
            assets=assets,
            snapshot_date=snapshot_date,
            value_by_asset_id=value_by_asset_id,
            note_by_asset_id=note_by_asset_id,
        )
    except ValueError as error:
        return str(error)
    if not entries:
        return "Fill at least one value to save snapshots"
    return None


def _asset_actions_state(selected_asset: Asset | None) -> tuple[bool, bool]:
    if selected_asset is None:
        return False, False
    return True, bool(selected_asset.is_active)


def _prepare_goal_payload(
    *,
    title: str,
    target_amount: str,
    currency: str,
    created_at: str,
    target_date: str,
    description: str,
) -> dict:
    title_text = str(title or "").strip()
    if not title_text:
        raise ValueError("Goal title is required")
    currency_text = str(currency or "").strip().upper()
    if len(currency_text) != 3:
        raise ValueError("Goal currency must be a 3-letter code")
    created_at_text = str(created_at or "").strip()
    if not created_at_text:
        raise ValueError("Created at date is required")
    created_at_date = parse_ymd(created_at_text)
    ensure_not_future(created_at_date)
    target_date_text = str(target_date or "").strip()
    if target_date_text:
        target_date_value = parse_ymd(target_date_text)
        if target_date_value < created_at_date:
            raise ValueError("Target date cannot be earlier than created at")
    return {
        "title": title_text,
        "target_amount": _parse_positive_amount(target_amount, field_name="Target amount"),
        "currency": currency_text,
        "created_at": created_at_text,
        "target_date": target_date_text or None,
        "description": str(description or "").strip(),
    }


def _prepare_asset_payload(
    *,
    name: str,
    category: str,
    currency: str,
    created_at: str,
    description: str,
) -> dict:
    name_text = str(name or "").strip()
    if not name_text:
        raise ValueError("Asset name is required")
    category_text = str(category or "").strip().lower()
    if category_text not in {"bank", "crypto", "cash", "other"}:
        raise ValueError("Asset category must be one of: bank, crypto, cash, other")
    currency_text = str(currency or "").strip().upper()
    if len(currency_text) != 3:
        raise ValueError("Asset currency must be a 3-letter code")
    created_at_text = str(created_at or "").strip()
    if not created_at_text:
        raise ValueError("Created at date is required")
    created_at_date = parse_ymd(created_at_text)
    ensure_not_future(created_at_date)
    return {
        "name": name_text,
        "category": category_text,
        "currency": currency_text,
        "created_at": created_at_text,
        "description": str(description or "").strip(),
    }


def _prepare_bulk_snapshot_entries(
    *,
    assets: list[Asset],
    snapshot_date: str,
    value_by_asset_id: dict[int, str],
    note_by_asset_id: dict[int, str],
) -> list[dict]:
    entries: list[dict] = []
    date_text = str(snapshot_date or "").strip()
    if not date_text:
        raise ValueError("Snapshot date is required")
    snapshot_day = parse_ymd(date_text)
    ensure_not_future(snapshot_day)

    for asset in assets:
        raw_value = str(value_by_asset_id.get(int(asset.id), "") or "").strip()
        if not raw_value:
            continue
        normalized_value = raw_value.replace(",", "")
        try:
            value = float(normalized_value)
        except ValueError as exc:
            raise ValueError(f"Invalid value for asset '{asset.name}'") from exc
        if value < 0:
            raise ValueError(f"Value for asset '{asset.name}' cannot be negative")
        entries.append(
            {
                "asset_id": int(asset.id),
                "snapshot_date": date_text,
                "value": value,
                "currency": str(asset.currency),
                "note": str(note_by_asset_id.get(int(asset.id), "") or "").strip(),
            }
        )
    return entries


def _draw_trend(canvas: tk.Canvas, data: list[DashboardTrendPoint]) -> None:
    canvas.delete("all")
    width = max(canvas.winfo_width(), 320)
    height = max(canvas.winfo_height(), 200)
    pad = {"left": 54, "right": 18, "top": 20, "bottom": 34}

    if not data:
        canvas.create_text(
            width // 2,
            height // 2,
            text="No trend data yet",
            fill="#6b7280",
            font=("Segoe UI", 11),
        )
        return

    values = [float(point.balance) for point in data]
    min_value = min(values)
    max_value = max(values)
    span = (max_value - min_value) or 1.0

    def to_xy(index: int, value: float) -> tuple[float, float]:
        x = pad["left"] + (width - pad["left"] - pad["right"]) * index / max(1, len(data) - 1)
        y = pad["top"] + (height - pad["top"] - pad["bottom"]) * (1 - (value - min_value) / span)
        return x, y

    canvas.create_rectangle(
        pad["left"],
        pad["top"],
        width - pad["right"],
        height - pad["bottom"],
        outline="#e5e7eb",
        width=1,
    )

    if min_value < 0 < max_value:
        _, zero_y = to_xy(0, 0.0)
        canvas.create_line(
            pad["left"],
            zero_y,
            width - pad["right"],
            zero_y,
            fill="#d1d5db",
            dash=(4, 4),
        )

    for index in range(len(values) - 1):
        x1, y1 = to_xy(index, values[index])
        x2, y2 = to_xy(index + 1, values[index + 1])
        canvas.create_line(x1, y1, x2, y2, fill="#1d4ed8", width=3, smooth=True)

    for index, point in enumerate(data):
        x, y = to_xy(index, float(point.balance))
        canvas.create_oval(x - 3, y - 3, x + 3, y + 3, fill="#1d4ed8", outline="white", width=1)

    step = max(1, len(data) // 5)
    for index, point in enumerate(data):
        if index % step == 0 or index == len(data) - 1:
            x, _ = to_xy(index, float(point.balance))
            canvas.create_text(
                x,
                height - pad["bottom"] + 12,
                text=str(point.month),
                fill="#6b7280",
                font=("Segoe UI", 8),
            )

    canvas.create_text(
        pad["left"] - 6,
        pad["top"],
        text=f"{max_value:,.0f}",
        fill="#6b7280",
        font=("Segoe UI", 8),
        anchor="e",
    )
    canvas.create_text(
        pad["left"] - 6,
        height - pad["bottom"],
        text=f"{min_value:,.0f}",
        fill="#6b7280",
        font=("Segoe UI", 8),
        anchor="e",
    )


def _draw_allocation(canvas: tk.Canvas, data: list[DashboardAllocationSlice]) -> None:
    canvas.delete("all")
    width = max(canvas.winfo_width(), 280)
    height = max(canvas.winfo_height(), 220)
    center_x = width * 0.35
    center_y = height * 0.48
    radius = min(width * 0.23, height * 0.34)
    inner_radius = radius * 0.58

    if not data:
        canvas.create_text(
            width // 2,
            height // 2,
            text="No assets yet",
            fill="#6b7280",
            font=("Segoe UI", 11),
        )
        return

    total = sum(float(item.amount_kzt) for item in data)
    if total <= 0:
        canvas.create_text(
            width // 2,
            height // 2,
            text="No allocation data",
            fill="#6b7280",
            font=("Segoe UI", 11),
        )
        return

    start_angle = 90.0
    for index, item in enumerate(data):
        amount = float(item.amount_kzt)
        sweep = amount / total * 360.0
        color = _PALETTE[index % len(_PALETTE)]
        canvas.create_arc(
            center_x - radius,
            center_y - radius,
            center_x + radius,
            center_y + radius,
            start=start_angle,
            extent=-sweep,
            fill=color,
            outline="white",
            width=2,
        )
        start_angle -= sweep

    canvas.create_oval(
        center_x - inner_radius,
        center_y - inner_radius,
        center_x + inner_radius,
        center_y + inner_radius,
        fill="white",
        outline="white",
    )
    canvas.create_text(
        center_x,
        center_y - 8,
        text="Assets",
        fill="#6b7280",
        font=("Segoe UI", 9),
    )
    canvas.create_text(
        center_x,
        center_y + 12,
        text=_format_money(total),
        fill="#111827",
        font=("Segoe UI", 10, "bold"),
    )

    legend_x = width * 0.62
    legend_y = 30
    for index, item in enumerate(data[:6]):
        y = legend_y + index * 28
        color = _PALETTE[index % len(_PALETTE)]
        canvas.create_rectangle(legend_x, y, legend_x + 12, y + 12, fill=color, outline="")
        canvas.create_text(
            legend_x + 18,
            y + 1,
            anchor="nw",
            text=str(item.category).title(),
            fill="#111827",
            font=("Segoe UI", 9, "bold"),
        )
        canvas.create_text(
            legend_x + 18,
            y + 14,
            anchor="nw",
            text=f"{item.share_pct:.1f}% • {_format_money(item.amount_kzt)}",
            fill="#6b7280",
            font=("Segoe UI", 8),
        )


def _render_goals(container: ttk.Frame, goals: list[GoalProgress]) -> None:
    _render_goals_with_actions(container, goals, on_toggle_completed=None)


def _render_goals_with_actions(
    container: ttk.Frame,
    goals: list[GoalProgress],
    *,
    on_toggle_completed: Callable[[GoalProgress], None] | None,
    on_delete_goal: Callable[[GoalProgress], None] | None = None,
) -> None:
    for child in container.winfo_children():
        child.destroy()

    if not goals:
        empty = ttk.Label(container, text="No goals yet", foreground="#6b7280")
        empty.grid(row=0, column=0, sticky="w", padx=6, pady=6)
        return

    container.grid_columnconfigure(0, weight=1)
    for index, item in enumerate(goals):
        card = ttk.Frame(container, padding=(10, 10))
        card.grid(row=index, column=0, sticky="ew", padx=4, pady=4)
        card.grid_columnconfigure(0, weight=1)

        title = str(item.goal.title)
        status = "Completed" if item.is_completed else f"{item.progress_pct:.1f}%"
        ttk.Label(card, text=title, font=("Segoe UI", 10, "bold")).grid(
            row=0,
            column=0,
            sticky="w",
        )
        ttk.Label(card, text=status, foreground="#059669" if item.is_completed else "#2563eb").grid(
            row=0,
            column=1,
            sticky="e",
            padx=(12, 0),
        )

        details = f"{item.current_amount:,.2f} / {item.target_amount:,.2f} {item.goal.currency}"
        ttk.Label(card, text=details, foreground="#6b7280").grid(
            row=1,
            column=0,
            columnspan=2,
            sticky="w",
            pady=(4, 6),
        )

        progress = ttk.Progressbar(card, mode="determinate", maximum=100.0)
        progress.grid(row=2, column=0, columnspan=2, sticky="ew")
        progress["value"] = max(0.0, min(100.0, float(item.progress_pct)))

        if on_toggle_completed is not None:
            action_text = "Reopen" if item.is_completed else "Complete"
            ttk.Button(
                card,
                text=action_text,
                command=lambda goal_progress=item: on_toggle_completed(goal_progress),
            ).grid(row=0, column=2, sticky="e", padx=(12, 0))
        if on_delete_goal is not None:
            ttk.Button(
                card,
                text="Delete",
                command=lambda goal_progress=item: on_delete_goal(goal_progress),
            ).grid(row=0, column=3, sticky="e", padx=(8, 0))

        if item.goal.target_date:
            ttk.Label(
                card,
                text=f"Target date: {item.goal.target_date}",
                foreground="#6b7280",
            ).grid(row=3, column=0, columnspan=3, sticky="w", pady=(6, 0))


def show_bulk_asset_snapshot_dialog(
    parent: tk.Misc,
    *,
    context: DashboardTabContext,
    on_saved: Callable[[], None],
) -> None:
    assets = list(context.controller.get_assets(active_only=True))
    if not assets:
        messagebox.showinfo("Bulk update", "There are no active assets to update.", parent=parent)
        return

    latest_map = {
        int(snapshot.asset_id): snapshot
        for snapshot in context.controller.get_latest_asset_snapshots(active_only=True)
    }

    dialog = tk.Toplevel(parent)
    dialog.title("Bulk Asset Snapshot Update")
    dialog.transient(parent.winfo_toplevel())
    dialog.minsize(900, 500)
    dialog.resizable(True, True)
    dialog.grid_columnconfigure(0, weight=1)
    dialog.grid_rowconfigure(0, weight=1)

    content = ttk.Frame(dialog, padding=12)
    content.grid(row=0, column=0, sticky="nsew")
    content.grid_columnconfigure(0, weight=1)
    content.grid_rowconfigure(3, weight=1)

    ttk.Label(content, text="Bulk Asset Snapshot Update", font=("Segoe UI", 11, "bold")).grid(
        row=0,
        column=0,
        sticky="w",
    )
    ttk.Label(
        content,
        text="Fill only the assets you want to update. Empty rows will be skipped.",
        foreground="#6b7280",
    ).grid(row=1, column=0, sticky="w", pady=(4, 10))

    header = ttk.Frame(content)
    header.grid(row=2, column=0, sticky="ew")
    header.grid_columnconfigure(3, weight=1)

    ttk.Label(header, text="Snapshot date:").grid(row=0, column=0, sticky="w")
    snapshot_date_var = tk.StringVar(value=date.today().isoformat())
    snapshot_date_entry = ttk.Entry(header, width=14, textvariable=snapshot_date_var)
    snapshot_date_entry.grid(row=0, column=1, sticky="w", padx=(6, 16))

    ttk.Label(header, text="Date applies to all filled rows.", foreground="#6b7280").grid(
        row=0,
        column=2,
        sticky="w",
    )

    table_frame = ttk.Frame(content)
    table_frame.grid(row=3, column=0, sticky="nsew", pady=(10, 0))
    table_frame.grid_columnconfigure(0, weight=1)
    table_frame.grid_rowconfigure(0, weight=1)

    canvas = tk.Canvas(table_frame, highlightthickness=0, bg="white")
    canvas.grid(row=0, column=0, sticky="nsew")
    scroll = ttk.Scrollbar(table_frame, orient="vertical", command=canvas.yview)
    scroll.grid(row=0, column=1, sticky="ns")
    canvas.configure(yscrollcommand=scroll.set)

    rows = ttk.Frame(canvas, padding=(10, 10))
    window_id = canvas.create_window((0, 0), window=rows, anchor="nw")
    rows.grid_columnconfigure(0, minsize=190)
    rows.grid_columnconfigure(1, minsize=170)
    rows.grid_columnconfigure(2, minsize=90)
    rows.grid_columnconfigure(3, minsize=140)
    rows.grid_columnconfigure(4, weight=1, minsize=260)

    titles = [
        ("Asset", 0),
        ("Current", 1),
        ("Currency", 2),
        ("New value", 3),
        ("Note", 4),
    ]
    for title, column in titles:
        ttk.Label(rows, text=title, font=("Segoe UI", 9, "bold")).grid(
            row=0,
            column=column,
            sticky="w",
            padx=(0, 12),
            pady=(0, 10),
        )

    value_vars: dict[int, tk.StringVar] = {}
    note_vars: dict[int, tk.StringVar] = {}

    for row_index, asset in enumerate(assets, start=1):
        visual_row = row_index * 2 - 1
        latest = latest_map.get(int(asset.id))
        current_text = "No snapshot"
        initial_value = ""
        if latest is not None:
            current_text = f"{_minor_to_money_text(int(latest.value_minor))} {latest.currency}"
            initial_value = _minor_to_money_text(int(latest.value_minor))

        ttk.Label(rows, text=str(asset.name)).grid(
            row=visual_row,
            column=0,
            sticky="w",
            padx=(0, 12),
            pady=6,
        )
        ttk.Label(rows, text=current_text, foreground="#6b7280").grid(
            row=visual_row,
            column=1,
            sticky="w",
            padx=(0, 12),
            pady=6,
        )
        ttk.Label(rows, text=str(asset.currency)).grid(
            row=visual_row,
            column=2,
            sticky="w",
            padx=(0, 12),
            pady=6,
        )

        value_var = tk.StringVar(value=initial_value)
        note_var = tk.StringVar(value="")
        value_vars[int(asset.id)] = value_var
        note_vars[int(asset.id)] = note_var

        ttk.Entry(rows, width=16, textvariable=value_var).grid(
            row=visual_row,
            column=3,
            sticky="ew",
            padx=(0, 12),
            pady=6,
        )
        ttk.Entry(rows, textvariable=note_var).grid(
            row=visual_row,
            column=4,
            sticky="ew",
            pady=6,
        )

        ttk.Separator(rows, orient="horizontal").grid(
            row=visual_row + 1,
            column=0,
            columnspan=5,
            sticky="ew",
            pady=(0, 2),
        )

    def _sync_scrollregion(_event: tk.Event | None = None) -> None:
        canvas.configure(scrollregion=canvas.bbox("all"))

    def _resize_window(_event: tk.Event) -> None:
        canvas.itemconfigure(window_id, width=max(_event.width, 920))

    rows.bind("<Configure>", _sync_scrollregion)
    canvas.bind("<Configure>", _resize_window)

    ttk.Label(
        content,
        text="Tip: empty rows are ignored, so you can update only the assets you touched.",
        foreground="#6b7280",
    ).grid(row=4, column=0, sticky="w", pady=(14, 0))

    buttons = ttk.Frame(content)
    buttons.grid(row=5, column=0, sticky="e", pady=(12, 0))
    form_status = ttk.Label(content, foreground="#b45309")
    form_status.grid(row=5, column=0, sticky="w")

    def _close() -> None:
        dialog.destroy()

    def _validate_form(*_args) -> None:
        error = _bulk_snapshot_form_error(
            assets=assets,
            snapshot_date=snapshot_date_var.get(),
            value_by_asset_id={asset_id: var.get() for asset_id, var in value_vars.items()},
            note_by_asset_id={asset_id: var.get() for asset_id, var in note_vars.items()},
        )
        form_status.config(text=error or "")
        _set_button_enabled(save_button, error is None)

    def _save() -> None:
        try:
            entries = _prepare_bulk_snapshot_entries(
                assets=assets,
                snapshot_date=snapshot_date_var.get(),
                value_by_asset_id={asset_id: var.get() for asset_id, var in value_vars.items()},
                note_by_asset_id={asset_id: var.get() for asset_id, var in note_vars.items()},
            )
            if not entries:
                raise ValueError("Fill at least one value to save snapshots")
            saved = context.controller.bulk_upsert_asset_snapshots(entries)
        except Exception as error:
            logger.warning("Bulk asset snapshot save error: %s", error)
            messagebox.showerror("Bulk update error", str(error), parent=dialog)
            return

        messagebox.showinfo(
            "Bulk update",
            f"Saved {len(saved)} snapshot(s).",
            parent=dialog,
        )
        dialog.destroy()
        on_saved()

    ttk.Button(buttons, text="Cancel", command=_close).pack(side=tk.LEFT, padx=(0, 8))
    save_button = ttk.Button(buttons, text="Save snapshots", command=_save)
    save_button.pack(side=tk.LEFT)

    snapshot_date_var.trace_add("write", _validate_form)
    for var in value_vars.values():
        var.trace_add("write", _validate_form)
    for var in note_vars.values():
        var.trace_add("write", _validate_form)
    _validate_form()

    dialog.protocol("WM_DELETE_WINDOW", _close)
    dialog.update_idletasks()

    parent_window = parent.winfo_toplevel()
    parent_x = parent_window.winfo_rootx()
    parent_y = parent_window.winfo_rooty()
    parent_w = parent_window.winfo_width()
    parent_h = parent_window.winfo_height()
    width = max(dialog.winfo_width(), 760)
    height = max(dialog.winfo_height(), 420)
    pos_x = parent_x + max((parent_w - width) // 2, 0)
    pos_y = parent_y + max((parent_h - height) // 2, 0)
    dialog.geometry(f"{width}x{height}+{pos_x}+{pos_y}")
    dialog.grab_set()
    snapshot_date_entry.focus_set()
    parent.wait_window(dialog)


def show_create_goal_dialog(
    parent: tk.Misc,
    *,
    context: DashboardTabContext,
    on_saved: Callable[[], None],
) -> None:
    dialog = tk.Toplevel(parent)
    dialog.title("Create Goal")
    dialog.transient(parent.winfo_toplevel())
    dialog.resizable(False, False)

    content = ttk.Frame(dialog, padding=12)
    content.grid(row=0, column=0, sticky="nsew")
    for column in (1, 3):
        content.grid_columnconfigure(column, weight=1)

    ttk.Label(content, text="Create Goal", font=("Segoe UI", 11, "bold")).grid(
        row=0, column=0, columnspan=4, sticky="w"
    )

    title_var = tk.StringVar()
    amount_var = tk.StringVar()
    currency_var = tk.StringVar(value="KZT")
    created_at_var = tk.StringVar(value=date.today().isoformat())
    target_date_var = tk.StringVar()
    description_var = tk.StringVar()

    ttk.Label(content, text="Title").grid(row=1, column=0, sticky="w", pady=(10, 0))
    title_entry = ttk.Entry(content, textvariable=title_var, width=28)
    title_entry.grid(row=2, column=0, columnspan=2, sticky="ew", padx=(0, 10))

    ttk.Label(content, text="Target amount").grid(row=1, column=2, sticky="w", pady=(10, 0))
    amount_entry = ttk.Entry(content, textvariable=amount_var, width=16)
    amount_entry.grid(row=2, column=2, sticky="ew", padx=(0, 10))

    ttk.Label(content, text="Currency").grid(row=1, column=3, sticky="w", pady=(10, 0))
    currency_entry = ttk.Entry(content, textvariable=currency_var, width=8)
    currency_entry.grid(row=2, column=3, sticky="ew")

    ttk.Label(content, text="Created at").grid(row=3, column=0, sticky="w", pady=(10, 0))
    created_at_entry = ttk.Entry(content, textvariable=created_at_var, width=16)
    created_at_entry.grid(row=4, column=0, sticky="ew", padx=(0, 10))

    ttk.Label(content, text="Target date").grid(row=3, column=1, sticky="w", pady=(10, 0))
    target_date_entry = ttk.Entry(content, textvariable=target_date_var, width=16)
    target_date_entry.grid(row=4, column=1, sticky="ew", padx=(0, 10))

    ttk.Label(content, text="Description").grid(
        row=3, column=2, columnspan=2, sticky="w", pady=(10, 0)
    )
    description_entry = ttk.Entry(content, textvariable=description_var)
    description_entry.grid(row=4, column=2, columnspan=2, sticky="ew")

    ttk.Label(
        content,
        text="Dates use YYYY-MM-DD. Target date may be empty.",
        foreground="#6b7280",
    ).grid(row=5, column=0, columnspan=4, sticky="w", pady=(8, 0))
    form_status = ttk.Label(content, foreground="#b45309")
    form_status.grid(row=6, column=0, columnspan=4, sticky="w", pady=(8, 0))

    buttons = ttk.Frame(content)
    buttons.grid(row=7, column=0, columnspan=4, sticky="e", pady=(12, 0))

    def _close() -> None:
        dialog.destroy()

    def _validate_form(*_args) -> None:
        error = _goal_form_error(
            title=title_var.get(),
            target_amount=amount_var.get(),
            currency=currency_var.get(),
            created_at=created_at_var.get(),
            target_date=target_date_var.get(),
            description=description_var.get(),
        )
        form_status.config(text=error or "")
        _set_button_enabled(save_button, error is None)

    def _save() -> None:
        try:
            payload = _prepare_goal_payload(
                title=title_var.get(),
                target_amount=amount_var.get(),
                currency=currency_var.get(),
                created_at=created_at_var.get(),
                target_date=target_date_var.get(),
                description=description_var.get(),
            )
            context.controller.create_goal(**payload)
        except Exception as error:
            logger.warning("Goal create error: %s", error)
            messagebox.showerror("Goal create error", str(error), parent=dialog)
            return
        dialog.destroy()
        on_saved()

    ttk.Button(buttons, text="Cancel", command=_close).pack(side=tk.LEFT, padx=(0, 8))
    save_button = ttk.Button(buttons, text="Create goal", command=_save)
    save_button.pack(side=tk.LEFT)

    for var in (
        title_var,
        amount_var,
        currency_var,
        created_at_var,
        target_date_var,
        description_var,
    ):
        var.trace_add("write", _validate_form)
    _validate_form()

    dialog.protocol("WM_DELETE_WINDOW", _close)
    dialog.update_idletasks()

    parent_window = parent.winfo_toplevel()
    parent_x = parent_window.winfo_rootx()
    parent_y = parent_window.winfo_rooty()
    parent_w = parent_window.winfo_width()
    parent_h = parent_window.winfo_height()
    width = max(dialog.winfo_width(), 560)
    height = max(dialog.winfo_height(), 220)
    pos_x = parent_x + max((parent_w - width) // 2, 0)
    pos_y = parent_y + max((parent_h - height) // 2, 0)
    dialog.geometry(f"{width}x{height}+{pos_x}+{pos_y}")
    dialog.grab_set()
    title_entry.focus_set()
    parent.wait_window(dialog)


def show_asset_editor_dialog(
    parent: tk.Misc,
    *,
    context: DashboardTabContext,
    initial_asset: Asset | None,
    on_saved: Callable[[], None],
) -> None:
    dialog = tk.Toplevel(parent)
    dialog.title("Edit Asset" if initial_asset is not None else "Create Asset")
    dialog.transient(parent.winfo_toplevel())
    dialog.resizable(False, False)

    content = ttk.Frame(dialog, padding=12)
    content.grid(row=0, column=0, sticky="nsew")
    for column in (1, 3):
        content.grid_columnconfigure(column, weight=1)

    categories = ["bank", "crypto", "cash", "other"]
    name_var = tk.StringVar(value="" if initial_asset is None else str(initial_asset.name))
    category_var = tk.StringVar(
        value="bank" if initial_asset is None else str(initial_asset.category.value)
    )
    currency_var = tk.StringVar(
        value="KZT" if initial_asset is None else str(initial_asset.currency)
    )
    created_at_var = tk.StringVar(
        value=date.today().isoformat() if initial_asset is None else str(initial_asset.created_at)
    )
    description_var = tk.StringVar(
        value="" if initial_asset is None else str(initial_asset.description or "")
    )
    currency_warning_var = tk.StringVar(value="")

    ttk.Label(
        content,
        text="Edit Asset" if initial_asset is not None else "Create Asset",
        font=("Segoe UI", 11, "bold"),
    ).grid(row=0, column=0, columnspan=4, sticky="w")

    ttk.Label(content, text="Name").grid(row=1, column=0, sticky="w", pady=(10, 0))
    name_entry = ttk.Entry(content, textvariable=name_var, width=28)
    name_entry.grid(row=2, column=0, columnspan=2, sticky="ew", padx=(0, 10))

    ttk.Label(content, text="Category").grid(row=1, column=2, sticky="w", pady=(10, 0))
    category_combo = ttk.Combobox(
        content,
        textvariable=category_var,
        values=categories,
        state="readonly",
        width=12,
    )
    category_combo.grid(row=2, column=2, sticky="ew", padx=(0, 10))

    ttk.Label(content, text="Currency").grid(row=1, column=3, sticky="w", pady=(10, 0))
    currency_entry = ttk.Entry(content, textvariable=currency_var, width=8)
    currency_entry.grid(row=2, column=3, sticky="ew")

    ttk.Label(content, text="Created at").grid(row=3, column=0, sticky="w", pady=(10, 0))
    created_at_entry = ttk.Entry(content, textvariable=created_at_var, width=16)
    created_at_entry.grid(row=4, column=0, sticky="ew", padx=(0, 10))
    if initial_asset is not None:
        created_at_entry.state(["readonly"])

    ttk.Label(content, text="Description").grid(
        row=3, column=1, columnspan=3, sticky="w", pady=(10, 0)
    )
    description_entry = ttk.Entry(content, textvariable=description_var)
    description_entry.grid(row=4, column=1, columnspan=3, sticky="ew")

    ttk.Label(
        content,
        text=(
            "Created at uses YYYY-MM-DD."
            if initial_asset is None
            else "Created at is locked for existing assets."
        ),
        foreground="#6b7280",
    ).grid(row=5, column=0, columnspan=4, sticky="w", pady=(8, 0))
    currency_warning = ttk.Label(content, textvariable=currency_warning_var, foreground="#b45309")
    currency_warning.grid(row=6, column=0, columnspan=4, sticky="w", pady=(8, 0))
    form_status = ttk.Label(content, foreground="#b45309")
    form_status.grid(row=7, column=0, columnspan=4, sticky="w", pady=(4, 0))

    buttons = ttk.Frame(content)
    buttons.grid(row=8, column=0, columnspan=4, sticky="e", pady=(12, 0))

    def _close() -> None:
        dialog.destroy()

    def _validate_form(*_args) -> None:
        created_at_value = (
            str(initial_asset.created_at) if initial_asset is not None else created_at_var.get()
        )
        error = _asset_form_error(
            name=name_var.get(),
            category=category_var.get(),
            currency=currency_var.get(),
            created_at=created_at_value,
            description=description_var.get(),
        )
        form_status.config(text=error or "")
        if (
            initial_asset is not None
            and str(currency_var.get()).strip().upper()
            != str(initial_asset.currency).strip().upper()
        ):
            currency_warning_var.set(
                "Changing asset currency requires saving a new snapshot in the new currency."
            )
        else:
            currency_warning_var.set("")
        _set_button_enabled(save_button, error is None)

    def _save() -> None:
        try:
            payload = _prepare_asset_payload(
                name=name_var.get(),
                category=category_var.get(),
                currency=currency_var.get(),
                created_at=(
                    str(initial_asset.created_at)
                    if initial_asset is not None
                    else created_at_var.get()
                ),
                description=description_var.get(),
            )
            if initial_asset is None:
                context.controller.create_asset(**payload)
            else:
                context.controller.update_asset(initial_asset.id, **payload)
        except Exception as error:
            logger.warning("Asset save error: %s", error)
            messagebox.showerror("Asset save error", str(error), parent=dialog)
            return
        dialog.destroy()
        on_saved()

    ttk.Button(buttons, text="Cancel", command=_close).pack(side=tk.LEFT, padx=(0, 8))
    save_button = ttk.Button(buttons, text="Save asset", command=_save)
    save_button.pack(side=tk.LEFT)

    tracked_vars = [name_var, category_var, currency_var, description_var]
    if initial_asset is None:
        tracked_vars.append(created_at_var)
    for var in tracked_vars:
        var.trace_add("write", _validate_form)
    _validate_form()

    dialog.protocol("WM_DELETE_WINDOW", _close)
    dialog.update_idletasks()

    parent_window = parent.winfo_toplevel()
    parent_x = parent_window.winfo_rootx()
    parent_y = parent_window.winfo_rooty()
    parent_w = parent_window.winfo_width()
    parent_h = parent_window.winfo_height()
    width = max(dialog.winfo_width(), 560)
    height = max(dialog.winfo_height(), 220)
    pos_x = parent_x + max((parent_w - width) // 2, 0)
    pos_y = parent_y + max((parent_h - height) // 2, 0)
    dialog.geometry(f"{width}x{height}+{pos_x}+{pos_y}")
    dialog.grab_set()
    name_entry.focus_set()
    parent.wait_window(dialog)


def show_manage_assets_dialog(
    parent: tk.Misc,
    *,
    context: DashboardTabContext,
    on_saved: Callable[[], None],
) -> None:
    dialog = tk.Toplevel(parent)
    dialog.title("Manage Assets")
    dialog.transient(parent.winfo_toplevel())
    dialog.minsize(760, 360)

    content = ttk.Frame(dialog, padding=12)
    content.grid(row=0, column=0, sticky="nsew")
    content.grid_columnconfigure(0, weight=1)
    content.grid_rowconfigure(1, weight=1)

    ttk.Label(content, text="Manage Assets", font=("Segoe UI", 11, "bold")).grid(
        row=0, column=0, sticky="w"
    )

    tree = ttk.Treeview(
        content,
        columns=("name", "category", "currency", "created_at", "status"),
        show="headings",
        height=10,
    )
    tree.grid(row=1, column=0, sticky="nsew", pady=(10, 0))
    tree.heading("name", text="Name")
    tree.heading("category", text="Category")
    tree.heading("currency", text="Currency")
    tree.heading("created_at", text="Created")
    tree.heading("status", text="Status")
    tree.column("name", width=220)
    tree.column("category", width=100)
    tree.column("currency", width=80, anchor="center")
    tree.column("created_at", width=110, anchor="center")
    tree.column("status", width=90, anchor="center")

    actions = ttk.Frame(content)
    actions.grid(row=2, column=0, sticky="ew", pady=(12, 0))

    assets_by_id: dict[str, Asset] = {}
    edit_button = ttk.Button(actions, text="Edit", command=lambda: _edit_asset())
    deactivate_button = ttk.Button(actions, text="Deactivate", command=lambda: _deactivate_asset())

    def _selected_asset() -> Asset | None:
        selected = tree.selection()
        if not selected:
            return None
        return assets_by_id.get(str(selected[0]))

    def _refresh_action_state(*_args) -> None:
        can_edit, can_deactivate = _asset_actions_state(_selected_asset())
        _set_button_enabled(edit_button, can_edit)
        _set_button_enabled(deactivate_button, can_deactivate)

    def _refresh_assets() -> None:
        nonlocal assets_by_id
        tree.delete(*tree.get_children())
        assets = list(context.controller.get_assets(active_only=False))
        assets_by_id = {str(asset.id): asset for asset in assets}
        for asset in assets:
            tree.insert(
                "",
                "end",
                iid=str(asset.id),
                values=(
                    str(asset.name),
                    str(asset.category.value),
                    str(asset.currency),
                    str(asset.created_at),
                    "Active" if bool(asset.is_active) else "Inactive",
                ),
            )
        _refresh_action_state()

    def _create_asset() -> None:
        show_asset_editor_dialog(
            dialog, context=context, initial_asset=None, on_saved=_after_change
        )

    def _edit_asset() -> None:
        asset = _selected_asset()
        if asset is None:
            messagebox.showinfo("Manage Assets", "Select an asset to edit.", parent=dialog)
            return
        show_asset_editor_dialog(
            dialog, context=context, initial_asset=asset, on_saved=_after_change
        )

    def _deactivate_asset() -> None:
        asset = _selected_asset()
        if asset is None:
            messagebox.showinfo("Manage Assets", "Select an asset to deactivate.", parent=dialog)
            return
        if not bool(asset.is_active):
            messagebox.showinfo(
                "Manage Assets", "Selected asset is already inactive.", parent=dialog
            )
            return
        confirmed = messagebox.askyesno(
            "Deactivate Asset",
            f"Deactivate asset '{asset.name}'?",
            parent=dialog,
        )
        if not confirmed:
            return
        try:
            context.controller.deactivate_asset(asset.id)
        except Exception as error:
            logger.warning("Asset deactivate error: %s", error)
            messagebox.showerror("Asset deactivate error", str(error), parent=dialog)
            return
        _after_change()

    def _after_change() -> None:
        _refresh_assets()
        on_saved()

    ttk.Button(actions, text="Create", command=_create_asset).pack(side=tk.LEFT)
    edit_button.pack(side=tk.LEFT, padx=(8, 0))
    deactivate_button.pack(side=tk.LEFT, padx=(8, 0))
    ttk.Button(actions, text="Close", command=dialog.destroy).pack(side=tk.RIGHT)

    tree.bind("<<TreeviewSelect>>", _refresh_action_state)
    _refresh_assets()
    dialog.update_idletasks()

    parent_window = parent.winfo_toplevel()
    parent_x = parent_window.winfo_rootx()
    parent_y = parent_window.winfo_rooty()
    parent_w = parent_window.winfo_width()
    parent_h = parent_window.winfo_height()
    width = max(dialog.winfo_width(), 760)
    height = max(dialog.winfo_height(), 360)
    pos_x = parent_x + max((parent_w - width) // 2, 0)
    pos_y = parent_y + max((parent_h - height) // 2, 0)
    dialog.geometry(f"{width}x{height}+{pos_x}+{pos_y}")
    dialog.grab_set()
    parent.wait_window(dialog)


def build_dashboard_tab(
    parent: tk.Frame | ttk.Frame,
    *,
    context: DashboardTabContext,
) -> DashboardTabBindings:
    parent.grid_columnconfigure(0, weight=1)
    parent.grid_rowconfigure(1, weight=1)
    parent.grid_rowconfigure(2, weight=1)

    toolbar = ttk.Frame(parent)
    toolbar.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 6))
    toolbar.grid_columnconfigure(5, weight=1)

    ttk.Label(toolbar, text="Strategic Dashboard", font=("Segoe UI", 12, "bold")).grid(
        row=0, column=0, sticky="w"
    )
    ttk.Label(
        toolbar,
        text="Quick actions:",
        foreground="#6b7280",
    ).grid(row=0, column=1, sticky="e", padx=(16, 8))
    create_asset_button = ttk.Button(toolbar, text="Create Asset")
    create_asset_button.grid(row=0, column=2, sticky="e", padx=(0, 8))
    manage_assets_button = ttk.Button(toolbar, text="Manage Assets")
    manage_assets_button.grid(row=0, column=3, sticky="e", padx=(0, 8))
    create_goal_button = ttk.Button(toolbar, text="Create Goal")
    create_goal_button.grid(row=0, column=4, sticky="e", padx=(0, 8))
    bulk_update_button = ttk.Button(toolbar, text="Bulk Update Assets")
    bulk_update_button.grid(row=0, column=5, sticky="e", padx=(0, 8))
    refresh_button = ttk.Button(toolbar, text="Refresh")
    refresh_button.grid(row=0, column=6, sticky="e")

    summary_frame = ttk.LabelFrame(parent, text="Overview")
    summary_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 8))
    for column in range(3):
        summary_frame.grid_columnconfigure(column, weight=1)

    net_worth_label = ttk.Label(
        summary_frame,
        text="Net worth: -",
        font=("Segoe UI", 14, "bold"),
    )
    net_worth_label.grid(row=0, column=0, sticky="w", padx=12, pady=(12, 4))

    assets_total_label = ttk.Label(
        summary_frame,
        text="Assets total: -",
        font=("Segoe UI", 14, "bold"),
    )
    assets_total_label.grid(row=0, column=1, sticky="w", padx=12, pady=(12, 4))

    goals_status_label = ttk.Label(
        summary_frame,
        text="Goals: -",
        font=("Segoe UI", 14, "bold"),
    )
    goals_status_label.grid(row=0, column=2, sticky="w", padx=12, pady=(12, 4))

    assets_status_label = ttk.Label(
        summary_frame,
        text="Assets: -",
        foreground="#6b7280",
    )
    assets_status_label.grid(row=1, column=0, sticky="w", padx=12, pady=(0, 4))

    trend_label = ttk.Label(summary_frame, text="Net Worth Trend", font=("Segoe UI", 10, "bold"))
    trend_label.grid(row=2, column=0, columnspan=2, sticky="w", padx=12, pady=(8, 0))
    ttk.Label(
        summary_frame,
        text="Compact monthly path for fast capital check.",
        foreground="#6b7280",
    ).grid(row=3, column=0, columnspan=2, sticky="w", padx=12)

    allocation_label = ttk.Label(
        summary_frame, text="Asset Allocation", font=("Segoe UI", 10, "bold")
    )
    allocation_label.grid(row=2, column=2, sticky="w", padx=12, pady=(8, 0))
    ttk.Label(
        summary_frame,
        text="Active assets grouped by category.",
        foreground="#6b7280",
    ).grid(row=3, column=2, sticky="w", padx=12)

    trend_canvas = tk.Canvas(summary_frame, height=220, bg="white", highlightthickness=0)
    trend_canvas.grid(row=4, column=0, columnspan=2, sticky="nsew", padx=(12, 6), pady=(6, 12))

    allocation_canvas = tk.Canvas(summary_frame, height=220, bg="white", highlightthickness=0)
    allocation_canvas.grid(row=4, column=2, sticky="nsew", padx=(6, 12), pady=(6, 12))

    goals_frame = ttk.LabelFrame(parent, text="Goals")
    goals_frame.grid(row=2, column=0, sticky="nsew", padx=10, pady=(0, 10))
    goals_frame.grid_columnconfigure(0, weight=1)
    goals_frame.grid_rowconfigure(1, weight=1)

    goals_header = ttk.Frame(goals_frame)
    goals_header.grid(row=0, column=0, columnspan=2, sticky="ew", padx=10, pady=(10, 0))
    goals_header.grid_columnconfigure(0, weight=1)
    ttk.Label(
        goals_header,
        text="Track progress and complete goals directly from this view.",
        foreground="#6b7280",
    ).grid(row=0, column=0, sticky="w")

    goals_canvas = tk.Canvas(goals_frame, bg="white", highlightthickness=0)
    goals_canvas.grid(row=1, column=0, sticky="nsew", padx=(10, 0), pady=10)

    goals_scroll = ttk.Scrollbar(goals_frame, orient="vertical", command=goals_canvas.yview)
    goals_scroll.grid(row=1, column=1, sticky="ns", padx=(6, 10), pady=10)
    goals_canvas.configure(yscrollcommand=goals_scroll.set)

    goals_inner = ttk.Frame(goals_canvas)
    goals_window = goals_canvas.create_window((0, 0), window=goals_inner, anchor="nw")

    last_payload: DashboardPayload | None = None
    redraw_job: str | None = None

    def _sync_goals_scrollregion(_event: tk.Event | None = None) -> None:
        goals_canvas.configure(scrollregion=goals_canvas.bbox("all"))

    def _resize_goals_window(_event: tk.Event) -> None:
        goals_canvas.itemconfigure(goals_window, width=_event.width)

    def _schedule_redraw() -> None:
        nonlocal redraw_job
        if redraw_job is not None:
            try:
                context.after_cancel(redraw_job)
            except Exception:
                pass
        redraw_job = context.after(120, _redraw)

    def _redraw() -> None:
        nonlocal redraw_job
        redraw_job = None
        if last_payload is None:
            _draw_trend(trend_canvas, [])
            _draw_allocation(allocation_canvas, [])
            return
        _draw_trend(trend_canvas, list(last_payload.trend))
        _draw_allocation(allocation_canvas, list(last_payload.allocation))

    def _refresh() -> None:
        nonlocal last_payload
        try:
            payload = context.controller.get_dashboard_payload()
            last_payload = payload
            all_assets = list(context.controller.get_assets(active_only=False))
            active_assets = [asset for asset in all_assets if bool(asset.is_active)]
            net_worth_label.config(
                text=f"Net worth: {_format_money(payload.summary.net_worth_kzt)}"
            )
            assets_total_label.config(
                text=f"Assets total: {_format_money(payload.summary.assets_total_kzt)}"
            )
            goals_status_label.config(
                text=(
                    f"Goals: {payload.summary.goals_completed} / "
                    f"{payload.summary.goals_total} completed"
                )
            )
            assets_status_label.config(
                text=f"Assets: {len(active_assets)} active / {len(all_assets)} total"
            )
            _render_goals_with_actions(
                goals_inner,
                list(payload.goals),
                on_toggle_completed=_toggle_goal_completed,
                on_delete_goal=_delete_goal,
            )
            _sync_goals_scrollregion()
            _redraw()
        except Exception as error:
            logger.warning("Dashboard refresh error: %s", error)
            messagebox.showerror("Dashboard error", str(error))

    def _toggle_goal_completed(goal_progress: GoalProgress) -> None:
        goal = goal_progress.goal
        completed = not bool(goal_progress.is_completed)
        try:
            context.controller.set_goal_completed(goal.id, completed)
        except Exception as error:
            logger.warning("Goal completion toggle error: %s", error)
            messagebox.showerror("Goal update error", str(error), parent=parent)
            return
        _refresh()

    def _delete_goal(goal_progress: GoalProgress) -> None:
        goal = goal_progress.goal
        confirmed = messagebox.askyesno(
            "Delete Goal",
            f"Delete goal '{goal.title}'?",
            parent=parent,
        )
        if not confirmed:
            return
        try:
            context.controller.delete_goal(goal.id)
        except Exception as error:
            logger.warning("Goal delete error: %s", error)
            messagebox.showerror("Goal delete error", str(error), parent=parent)
            return
        _refresh()

    def _open_bulk_update_dialog() -> None:
        show_bulk_asset_snapshot_dialog(parent, context=context, on_saved=_refresh)

    def _open_create_goal_dialog() -> None:
        show_create_goal_dialog(parent, context=context, on_saved=_refresh)

    def _open_create_asset_dialog() -> None:
        show_asset_editor_dialog(parent, context=context, initial_asset=None, on_saved=_refresh)

    def _open_manage_assets_dialog() -> None:
        show_manage_assets_dialog(parent, context=context, on_saved=_refresh)

    create_asset_button.configure(command=_open_create_asset_dialog)
    manage_assets_button.configure(command=_open_manage_assets_dialog)
    create_goal_button.configure(command=_open_create_goal_dialog)
    bulk_update_button.configure(command=_open_bulk_update_dialog)
    refresh_button.configure(command=_refresh)
    trend_canvas.bind("<Configure>", lambda _event: _schedule_redraw())
    allocation_canvas.bind("<Configure>", lambda _event: _schedule_redraw())
    goals_canvas.bind("<Configure>", _resize_goals_window)
    goals_inner.bind("<Configure>", _sync_goals_scrollregion)

    parent.after(100, _refresh)

    return DashboardTabBindings(
        net_worth_label=net_worth_label,
        assets_total_label=assets_total_label,
        goals_status_label=goals_status_label,
        assets_status_label=assets_status_label,
        trend_canvas=trend_canvas,
        allocation_canvas=allocation_canvas,
        goals_canvas=goals_canvas,
        create_asset_button=create_asset_button,
        manage_assets_button=manage_assets_button,
        create_goal_button=create_goal_button,
        bulk_update_button=bulk_update_button,
        refresh=_refresh,
    )
