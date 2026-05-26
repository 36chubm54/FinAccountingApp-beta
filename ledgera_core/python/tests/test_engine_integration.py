from ledgera_core import calculate_daily_burn


def test_rust_core_integration():
    # Тест: передаем данные из Python, считаем в Rust
    total = 50000.0
    days = 10

    expected = 5000.0
    actual = calculate_daily_burn(total, days)

    assert actual == expected, f"Rust вернул {actual}, ожидалось {expected}"


def test_rust_edge_cases():
    # Проверка на аномальные данные
    assert calculate_daily_burn(1000.0, -1) == 1000.0
