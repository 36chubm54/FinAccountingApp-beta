import tkinter as tk


def _calculate_tooltip_position(
    *,
    preferred_x: int,
    preferred_y_bottom: int,
    widget_top_y: int,
    tooltip_width: int,
    tooltip_height: int,
    boundary_left: int,
    boundary_right: int,
    boundary_top: int,
    boundary_bottom: int,
) -> tuple[int, int]:
    x = preferred_x
    if x + tooltip_width > boundary_right:
        x = boundary_right - tooltip_width
    if x < boundary_left:
        x = boundary_left

    y_top = widget_top_y - tooltip_height - 5
    y_bottom_fits = (
        preferred_y_bottom + tooltip_height <= boundary_bottom
        and preferred_y_bottom >= boundary_top
    )
    y_top_fits = y_top + tooltip_height <= boundary_bottom and y_top >= boundary_top

    if y_bottom_fits:
        y = preferred_y_bottom
    elif y_top_fits:
        y = y_top
    else:
        y = max(boundary_top, min(preferred_y_bottom, boundary_bottom - tooltip_height))

    if y + tooltip_height > boundary_bottom:
        y = boundary_bottom - tooltip_height
    if y < boundary_top:
        y = boundary_top
    return x, y


class Tooltip:
    """Простой Tooltip для tkinter/ttk виджетов."""

    def __init__(self, widget: tk.Widget, text: str):
        self.widget = widget
        self.text = text
        self.tipwindow = None
        self.id = None
        self.x = self.y = 0
        self.widget.bind("<Enter>", self.enter)
        self.widget.bind("<Leave>", self.leave)

    def enter(self, event=None):
        self.schedule()

    def leave(self, event=None):
        self.unschedule()
        self.hidetip()

    def schedule(self):
        self.unschedule()
        self.id = self.widget.after(500, self.showtip)

    def unschedule(self):
        if self.id:
            self.widget.after_cancel(self.id)
            self.id = None

    def showtip(self):
        if self.tipwindow:
            return
        # Исходная позиция подсказки (ниже и справа от виджета)
        x = self.widget.winfo_rootx() + 20
        y_bottom = self.widget.winfo_rooty() + self.widget.winfo_height() + 5
        self.tipwindow = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        # Создаём label, чтобы вычислить размеры подсказки
        label = tk.Label(
            tw,
            text=self.text,
            justify=tk.LEFT,
            background="#ffffff",
            relief=tk.SOLID,
            borderwidth=1,
            font=("Segoe UI", 10),
        )
        label.pack(ipadx=1)
        tw.update_idletasks()  # Обновляем геометрию для получения размеров
        tw_width = tw.winfo_width()
        tw_height = tw.winfo_height()

        # Получаем границы корневого окна
        root = self.widget.winfo_toplevel()
        root_x = root.winfo_rootx()
        root_y = root.winfo_rooty()
        root_width = root.winfo_width()
        root_height = root.winfo_height()

        # Границы экрана
        screen_width = self.widget.winfo_screenwidth()
        screen_height = self.widget.winfo_screenheight()

        # Вычисляем допустимые границы (окно приложения, без жёсткого clamp к primary screen)
        left_boundary = root_x
        right_boundary = min(root_x + root_width, screen_width)
        top_boundary = root_y
        bottom_boundary = min(root_y + root_height, screen_height)

        x, y = _calculate_tooltip_position(
            preferred_x=x,
            preferred_y_bottom=y_bottom,
            widget_top_y=self.widget.winfo_rooty(),
            tooltip_width=tw_width,
            tooltip_height=tw_height,
            boundary_left=left_boundary,
            boundary_right=right_boundary,
            boundary_top=top_boundary,
            boundary_bottom=bottom_boundary,
        )

        tw.wm_geometry(f"+{x}+{y}")

    def hidetip(self):
        if self.tipwindow:
            self.tipwindow.destroy()
            self.tipwindow = None
