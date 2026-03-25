from gui.tooltip import _calculate_tooltip_position


def test_calculate_tooltip_position_prefers_bottom_when_it_fits() -> None:
    x, y = _calculate_tooltip_position(
        preferred_x=120,
        preferred_y_bottom=240,
        widget_top_y=200,
        tooltip_width=80,
        tooltip_height=40,
        boundary_left=100,
        boundary_right=400,
        boundary_top=100,
        boundary_bottom=500,
    )
    assert (x, y) == (120, 240)


def test_calculate_tooltip_position_respects_negative_window_origin() -> None:
    x, y = _calculate_tooltip_position(
        preferred_x=-260,
        preferred_y_bottom=40,
        widget_top_y=10,
        tooltip_width=120,
        tooltip_height=50,
        boundary_left=-300,
        boundary_right=200,
        boundary_top=-100,
        boundary_bottom=300,
    )
    assert x < 0
    assert y == 40
