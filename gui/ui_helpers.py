from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from gui.i18n import tr
from gui.ui_dialogs import ask_confirm as _ask_confirm_dialog
from gui.ui_dialogs import ask_text as _ask_text_dialog
from gui.ui_dialogs import show_error as _show_error_dialog
from gui.ui_dialogs import show_info as _show_info_dialog
from gui.ui_dialogs import show_warning as _show_warning_dialog
from gui.ui_theme import get_palette


def show_error(
    message: str,
    *,
    title: str | None = None,
    parent: tk.Misc | None = None,
) -> None:
    resolved_title = title or tr("common.error", "Ошибка")
    _show_error_dialog(message, title=resolved_title, parent=parent)


def show_info(
    message: str,
    *,
    title: str | None = None,
    parent: tk.Misc | None = None,
) -> None:
    resolved_title = title or tr("common.done", "Готово")
    _show_info_dialog(message, title=resolved_title, parent=parent)


def show_warning(
    message: str,
    *,
    title: str | None = None,
    parent: tk.Misc | None = None,
) -> None:
    resolved_title = title or tr("common.warning", "Внимание")
    _show_warning_dialog(message, title=resolved_title, parent=parent)


def ask_confirm(
    message: str,
    *,
    title: str | None = None,
    parent: tk.Misc | None = None,
) -> bool:
    resolved_title = title or tr("common.confirm", "Подтверждение")
    return bool(_ask_confirm_dialog(message, title=resolved_title, parent=parent))


def ask_text(
    title: str,
    prompt: str,
    *,
    parent: tk.Misc | None = None,
    initialvalue: str = "",
    validator=None,
    normalize=None,
    ok_text: str | None = None,
    cancel_text: str | None = None,
) -> str | None:
    return _ask_text_dialog(
        title,
        prompt,
        parent=parent,
        initialvalue=initialvalue,
        validator=validator,
        normalize=normalize,
        ok_text=ok_text,
        cancel_text=cancel_text,
    )


def center_dialog(
    dialog: tk.Toplevel, parent: tk.Misc, *, min_width: int = 0, min_height: int = 0
) -> None:
    dialog.update_idletasks()
    parent_window = parent.winfo_toplevel()
    parent_x = parent_window.winfo_rootx()
    parent_y = parent_window.winfo_rooty()
    parent_w = parent_window.winfo_width()
    parent_h = parent_window.winfo_height()
    screen_w = dialog.winfo_screenwidth()
    screen_h = dialog.winfo_screenheight()
    width = min(max(dialog.winfo_reqwidth(), min_width), int(screen_w * 0.92))
    height = min(max(dialog.winfo_reqheight(), min_height), int(screen_h * 0.9))
    pos_x = parent_x + max((parent_w - width) // 2, 0)
    pos_y = parent_y + max((parent_h - height) // 2, 0)
    if min_width or min_height:
        dialog.minsize(min_width or dialog.winfo_reqwidth(), min_height or dialog.winfo_reqheight())
    dialog.resizable(True, True)
    if min_width or min_height:
        dialog.geometry(f"{width}x{height}+{pos_x}+{pos_y}")
    else:
        dialog.geometry(f"{width}x{height}+{pos_x}+{pos_y}")


def set_status(label: ttk.Label, text: str, *, tone: str = "muted") -> None:
    style_map = {
        "muted": "StatusMuted.TLabel",
        "success": "StatusSuccess.TLabel",
        "warning": "StatusWarning.TLabel",
        "danger": "StatusDanger.TLabel",
    }
    label.configure(text=text, style=style_map.get(tone, "StatusMuted.TLabel"))


def create_toolbar(parent: tk.Misc, *, padding: tuple[int, int] = (0, 0)) -> ttk.Frame:
    frame = ttk.Frame(parent, padding=padding)
    frame.grid_columnconfigure(99, weight=1)
    return frame


def create_actions_row(parent: tk.Misc, *, padding: tuple[int, int] = (0, 0)) -> ttk.Frame:
    return ttk.Frame(parent, padding=padding)


def create_canvas_empty_state(canvas: tk.Canvas, text: str) -> None:
    canvas.delete("all")
    width = max(canvas.winfo_width(), 240)
    height = max(canvas.winfo_height(), 140)
    palette = get_palette()
    canvas.create_text(
        width // 2,
        height // 2,
        text=text,
        fill=palette.text_muted,
        font=("Segoe UI", 11),
    )


def attach_treeview_scrollbars(
    parent: tk.Misc,
    tree: ttk.Treeview,
    *,
    row: int,
    column: int,
    horizontal: bool = True,
    padx: int = 0,
    pady: int = 0,
) -> tuple[ttk.Scrollbar, ttk.Scrollbar | None]:
    y_scroll = ttk.Scrollbar(parent, orient="vertical", command=tree.yview)
    y_scroll.grid(row=row, column=column + 1, sticky="ns", padx=(6, padx), pady=pady)
    tree.configure(yscrollcommand=y_scroll.set)
    x_scroll: ttk.Scrollbar | None = None
    if horizontal:
        x_scroll = ttk.Scrollbar(parent, orient="horizontal", command=tree.xview)
        x_scroll.grid(row=row + 1, column=column, sticky="ew", padx=padx, pady=(6, pady))
        tree.configure(xscrollcommand=x_scroll.set)
    return y_scroll, x_scroll


def bind_label_wrap(
    label: ttk.Label | tk.Label,
    container: tk.Misc | None = None,
    *,
    padding: int = 32,
    min_width: int = 140,
    max_width: int = 560,
) -> None:
    target = container or label.master
    if target is None:
        return

    def _sync_wrap(_event: tk.Event | None = None) -> None:
        try:
            width = max(min_width, min(max_width, target.winfo_width() - padding))
            label.configure(wraplength=width)
        except Exception:
            pass

    target.bind("<Configure>", _sync_wrap, add="+")
    label.after_idle(_sync_wrap)
