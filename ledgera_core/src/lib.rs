use pyo3::prelude::*;

/// Функция конвертации валюты, написанная на Rust
#[pyfunction]
fn convert_amount(amount: f64, rate: f64) -> PyResult<f64> {
    Ok(amount * rate)
}

#[pyfunction]
fn calculate_daily_burn(total_spent: f64, days_passed: i32) -> PyResult<f64> {
    if days_passed <= 0 {
        return Ok(total_spent);
    }
    Ok(total_spent / days_passed as f64)
}

/// Наш Python-модуль, который склеивает функции вместе
#[pymodule]
fn ledgera_core(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(convert_amount, m)?)?;
    m.add_function(wrap_pyfunction!(calculate_daily_burn, m)?)?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_convert_amount() {
        assert_eq!(convert_amount(100.0, 2.0).unwrap(), 200.0);
    }
    
    #[test]
    fn test_calculate_daily_burn() {
        // Проверка нормального случая
        assert_eq!(calculate_daily_burn(100.0, 4).unwrap(), 25.0);
        // Проверка деления на ноль (защита)
        assert_eq!(calculate_daily_burn(100.0, 0).unwrap(), 100.0);
    }
}