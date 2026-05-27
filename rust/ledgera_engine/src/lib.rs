use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use pyo3::types::PyDict;
use rusqlite::{Connection, OptionalExtension};
use std::collections::HashMap;

const MONEY_SCALE: u32 = 2;
const RATE_SCALE: u32 = 6;
fn pow10(power: u32) -> PyResult<i128> {
    10_i128
        .checked_pow(power)
        .ok_or_else(|| PyValueError::new_err("numeric scale overflow"))
}

fn py_value_to_text(value: &Bound<'_, PyAny>, default: &str) -> PyResult<String> {
    if value.is_none() {
        return Ok(default.to_owned());
    }
    Ok(value.str()?.to_str()?.trim().to_owned())
}

fn parse_scaled_decimal(text: &str, scale: u32) -> PyResult<i128> {
    let trimmed = text.trim();
    let normalized = if trimmed.is_empty() { "0" } else { trimmed };

    let (sign, unsigned) = if let Some(rest) = normalized.strip_prefix('-') {
        (-1_i128, rest)
    } else if let Some(rest) = normalized.strip_prefix('+') {
        (1_i128, rest)
    } else {
        (1_i128, normalized)
    };

    let mut parts = unsigned.split('.');
    let int_part = parts.next().unwrap_or_default();
    let frac_part = parts.next().unwrap_or_default();

    if parts.next().is_some() {
        return Err(PyValueError::new_err("invalid decimal value"));
    }

    if !int_part.chars().all(|ch| ch.is_ascii_digit())
        || !frac_part.chars().all(|ch| ch.is_ascii_digit())
    {
        return Err(PyValueError::new_err("invalid decimal value"));
    }

    let int_value = if int_part.is_empty() {
        0_i128
    } else {
        int_part
            .parse::<i128>()
            .map_err(|_| PyValueError::new_err("invalid decimal value"))?
    };
    let frac_value = if frac_part.is_empty() {
        0_i128
    } else {
        frac_part
            .parse::<i128>()
            .map_err(|_| PyValueError::new_err("invalid decimal value"))?
    };

    let frac_len = frac_part.len() as u32;
    let base = int_value
        .checked_mul(pow10(frac_len)?)
        .and_then(|value| value.checked_add(frac_value))
        .ok_or_else(|| PyValueError::new_err("decimal value too large"))?;

    let quantized_abs = if frac_len <= scale {
        base.checked_mul(pow10(scale - frac_len)?)
            .ok_or_else(|| PyValueError::new_err("decimal value too large"))?
    } else {
        let divisor = pow10(frac_len - scale)?;
        let quotient = base / divisor;
        let remainder = base % divisor;
        let should_round_up = remainder.checked_mul(2).unwrap_or(i128::MAX) >= divisor;
        if should_round_up {
            quotient
                .checked_add(1)
                .ok_or_else(|| PyValueError::new_err("decimal value too large"))?
        } else {
            quotient
        }
    };

    quantized_abs
        .checked_mul(sign)
        .ok_or_else(|| PyValueError::new_err("decimal value too large"))
}

fn scaled_to_float(value: i128, scale: u32) -> PyResult<f64> {
    let divisor = pow10(scale)? as f64;
    Ok(value as f64 / divisor)
}

fn scaled_to_text(value: i128, scale: u32) -> PyResult<String> {
    let sign = if value < 0 { "-" } else { "" };
    let abs_value = value.abs();
    let divisor = pow10(scale)?;
    let integer = abs_value / divisor;
    if scale == 0 {
        return Ok(format!("{sign}{integer}"));
    }
    let fraction = abs_value % divisor;
    Ok(format!(
        "{sign}{integer}.{fraction:0width$}",
        width = scale as usize
    ))
}

fn minor_to_money_value(value: i64) -> f64 {
    value as f64 / 100.0
}

fn round_div_half_up(numerator: i128, denominator: i128) -> PyResult<i128> {
    if denominator == 0 {
        return Err(PyValueError::new_err("division by zero"));
    }

    let sign = if (numerator < 0) ^ (denominator < 0) {
        -1_i128
    } else {
        1_i128
    };
    let abs_numerator = numerator.abs();
    let abs_denominator = denominator.abs();
    let quotient = abs_numerator / abs_denominator;
    let remainder = abs_numerator % abs_denominator;
    let rounded = if remainder.checked_mul(2).unwrap_or(i128::MAX) >= abs_denominator {
        quotient
            .checked_add(1)
            .ok_or_else(|| PyValueError::new_err("numeric value too large"))?
    } else {
        quotient
    };

    rounded
        .checked_mul(sign)
        .ok_or_else(|| PyValueError::new_err("numeric value too large"))
}

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

#[pyfunction]
fn to_money_float(value: &Bound<'_, PyAny>) -> PyResult<f64> {
    scaled_to_float(quantize_scaled_decimal(value, MONEY_SCALE)?, MONEY_SCALE)
}

#[pyfunction]
fn to_rate_float(value: &Bound<'_, PyAny>) -> PyResult<f64> {
    scaled_to_float(quantize_scaled_decimal(value, RATE_SCALE)?, RATE_SCALE)
}

#[pyfunction]
fn to_minor_units(value: &Bound<'_, PyAny>) -> PyResult<i64> {
    let scaled = quantize_scaled_decimal(value, MONEY_SCALE)?;
    i64::try_from(scaled).map_err(|_| PyValueError::new_err("minor units overflow"))
}

#[pyfunction]
fn minor_to_money(value: &Bound<'_, PyAny>) -> PyResult<f64> {
    let units = parse_scaled_decimal(&py_value_to_text(value, "0")?, 0)?;
    scaled_to_float(units, MONEY_SCALE)
}

#[pyfunction]
fn build_rate(
    amount_original: &Bound<'_, PyAny>,
    amount_base: &Bound<'_, PyAny>,
    currency: &str,
) -> PyResult<f64> {
    if currency.trim().eq_ignore_ascii_case("KZT") {
        return Ok(1.0);
    }

    let amount_original_scaled =
        parse_scaled_decimal(&py_value_to_text(amount_original, "0")?, MONEY_SCALE)?;
    if amount_original_scaled == 0 {
        return Ok(1.0);
    }

    let amount_base_scaled =
        parse_scaled_decimal(&py_value_to_text(amount_base, "0")?, MONEY_SCALE)?;
    let numerator = amount_base_scaled
        .checked_mul(pow10(RATE_SCALE)?)
        .ok_or_else(|| PyValueError::new_err("rate overflow"))?;
    let rate_scaled = round_div_half_up(numerator, amount_original_scaled)?;
    scaled_to_float(rate_scaled, RATE_SCALE)
}

#[pyfunction]
fn money_abs(value: &Bound<'_, PyAny>) -> PyResult<f64> {
    let scaled = quantize_scaled_decimal(value, MONEY_SCALE)?;
    scaled_to_float(scaled.abs(), MONEY_SCALE)
}

fn quantize_scaled_decimal(value: &Bound<'_, PyAny>, scale: u32) -> PyResult<i128> {
    parse_scaled_decimal(&py_value_to_text(value, "0")?, scale)
}

#[pyfunction]
fn quantize_money_text(value: &Bound<'_, PyAny>) -> PyResult<String> {
    scaled_to_text(quantize_scaled_decimal(value, MONEY_SCALE)?, MONEY_SCALE)
}

#[pyfunction]
fn quantize_rate_text(value: &Bound<'_, PyAny>) -> PyResult<String> {
    scaled_to_text(quantize_scaled_decimal(value, RATE_SCALE)?, RATE_SCALE)
}

#[pyfunction]
fn rate_to_text(value: &Bound<'_, PyAny>) -> PyResult<String> {
    quantize_rate_text(value)
}

#[pyfunction]
fn money_diff_text(left: &Bound<'_, PyAny>, right: &Bound<'_, PyAny>) -> PyResult<String> {
    let left_scaled = parse_scaled_decimal(&py_value_to_text(left, "0")?, MONEY_SCALE)?;
    let right_scaled = parse_scaled_decimal(&py_value_to_text(right, "0")?, MONEY_SCALE)?;
    scaled_to_text(
        left_scaled
            .checked_sub(right_scaled)
            .ok_or_else(|| PyValueError::new_err("money difference overflow"))?,
        MONEY_SCALE,
    )
}

#[pyfunction]
fn rate_diff_text(left: &Bound<'_, PyAny>, right: &Bound<'_, PyAny>) -> PyResult<String> {
    let left_scaled = parse_scaled_decimal(&py_value_to_text(left, "0")?, RATE_SCALE)?;
    let right_scaled = parse_scaled_decimal(&py_value_to_text(right, "0")?, RATE_SCALE)?;
    scaled_to_text(
        left_scaled
            .checked_sub(right_scaled)
            .ok_or_else(|| PyValueError::new_err("rate difference overflow"))?,
        RATE_SCALE,
    )
}

fn minor_amount_expr(column: &str) -> String {
    format!(
        "CASE \
         WHEN {column}_minor IS NOT NULL \
         AND ({column}_minor != 0 OR ROUND({column}, 2) = 0) \
         THEN {column}_minor \
         ELSE CAST(ROUND({column} * 100.0) AS INTEGER) \
         END"
    )
}

fn signed_minor_amount_expr(column: &str, type_column: &str) -> String {
    let amount_expr = minor_amount_expr(column);
    format!("CASE WHEN {type_column} = 'income' THEN {amount_expr} ELSE -{amount_expr} END")
}

fn sqlite_err(err: rusqlite::Error) -> PyErr {
    PyValueError::new_err(format!("sqlite error: {err}"))
}

fn open_sqlite_connection(db_path: &str) -> PyResult<Connection> {
    Connection::open(db_path).map_err(sqlite_err)
}

#[pyfunction]
fn wallet_balance_parts(
    db_path: &str,
    wallet_id: i64,
    up_to_date: Option<&str>,
) -> PyResult<Option<(f64, String, f64)>> {
    let conn = open_sqlite_connection(db_path)?;
    let wallet_row = conn
        .query_row(
            "SELECT \
                COALESCE(initial_balance_minor, CAST(ROUND(initial_balance * 100.0) AS INTEGER), 0), \
                currency \
             FROM wallets \
             WHERE id = ?1 AND is_active = 1",
            [wallet_id],
            |row| Ok((row.get::<_, i64>(0)?, row.get::<_, String>(1)?)),
        )
        .optional()
        .map_err(sqlite_err)?;
    let Some((initial_minor, currency)) = wallet_row else {
        return Ok(None);
    };

    let signed_expr = signed_minor_amount_expr("amount_base", "type");
    let delta_minor = if let Some(date) = up_to_date {
        let sql = format!(
            "SELECT COALESCE(SUM({signed_expr}), 0) \
             FROM records WHERE wallet_id = ?1 AND date <= ?2"
        );
        conn.query_row(&sql, (&wallet_id, &date), |row| row.get::<_, i64>(0))
            .map_err(sqlite_err)?
    } else {
        let sql =
            format!("SELECT COALESCE(SUM({signed_expr}), 0) FROM records WHERE wallet_id = ?1");
        conn.query_row(&sql, [wallet_id], |row| row.get::<_, i64>(0))
            .map_err(sqlite_err)?
    };

    Ok(Some((
        minor_to_money_value(initial_minor),
        currency,
        minor_to_money_value(delta_minor),
    )))
}

#[pyfunction]
fn wallet_balance_rows(
    db_path: &str,
    up_to_date: Option<&str>,
) -> PyResult<Vec<(i64, String, String, f64, f64)>> {
    let conn = open_sqlite_connection(db_path)?;
    let signed_expr = signed_minor_amount_expr("r.amount_base", "r.type");
    let mut sql = format!(
        "SELECT \
            w.id, \
            w.name, \
            w.currency, \
            COALESCE(w.initial_balance_minor, CAST(ROUND(w.initial_balance * 100.0) AS INTEGER), 0) AS initial_minor, \
            COALESCE(SUM({signed_expr}), 0) AS delta_minor \
         FROM wallets AS w \
         LEFT JOIN records AS r ON r.wallet_id = w.id"
    );
    if up_to_date.is_some() {
        sql.push_str(" AND r.date <= ?1");
    }
    sql.push_str(
        " WHERE w.is_active = 1 GROUP BY w.id, w.name, w.currency, initial_minor ORDER BY w.id",
    );

    let mut stmt = conn.prepare(&sql).map_err(sqlite_err)?;
    let mapper = |row: &rusqlite::Row<'_>| -> rusqlite::Result<(i64, String, String, f64, f64)> {
        let initial_minor: i64 = row.get(3)?;
        let delta_minor: i64 = row.get(4)?;
        Ok((
            row.get(0)?,
            row.get(1)?,
            row.get(2)?,
            minor_to_money_value(initial_minor),
            minor_to_money_value(delta_minor),
        ))
    };
    let mapped = if let Some(date) = up_to_date {
        stmt.query_map([date], mapper).map_err(sqlite_err)?
    } else {
        stmt.query_map([], mapper).map_err(sqlite_err)?
    };

    let mut rows = Vec::new();
    for row in mapped {
        rows.push(row.map_err(sqlite_err)?);
    }
    Ok(rows)
}

#[pyfunction]
fn cashflow_sum(
    db_path: &str,
    record_type: &str,
    start_date: &str,
    end_date: &str,
) -> PyResult<f64> {
    let conn = open_sqlite_connection(db_path)?;
    let amount_expr = minor_amount_expr("amount_base");
    let minor_total = if record_type == "expense" {
        let sql = format!(
            "SELECT COALESCE(SUM({amount_expr}), 0) \
             FROM records \
             WHERE type IN ('expense', 'mandatory_expense') \
               AND transfer_id IS NULL \
               AND date >= ?1 AND date <= ?2"
        );
        conn.query_row(&sql, (start_date, end_date), |row| row.get::<_, i64>(0))
            .map_err(sqlite_err)?
    } else {
        let sql = format!(
            "SELECT COALESCE(SUM({amount_expr}), 0) \
             FROM records \
             WHERE type = ?1 \
               AND transfer_id IS NULL \
               AND date >= ?2 AND date <= ?3"
        );
        conn.query_row(&sql, (record_type, start_date, end_date), |row| {
            row.get::<_, i64>(0)
        })
        .map_err(sqlite_err)?
    };
    Ok(minor_to_money_value(minor_total))
}

fn money_value_from_sql_row(
    row: &rusqlite::Row<'_>,
    real_index: usize,
    minor_index: usize,
) -> rusqlite::Result<f64> {
    let minor_value: Option<i64> = row.get(minor_index)?;
    if let Some(minor) = minor_value {
        Ok(minor_to_money_value(minor))
    } else {
        row.get::<_, f64>(real_index)
    }
}

fn rate_value_from_sql_row(
    row: &rusqlite::Row<'_>,
    real_index: usize,
    text_index: usize,
) -> rusqlite::Result<f64> {
    let rate_text = row.get::<_, Option<String>>(text_index)?;
    if let Some(text) = rate_text {
        if text.trim().is_empty() {
            row.get::<_, f64>(real_index)
        } else {
            let scaled = parse_scaled_decimal(text.trim(), RATE_SCALE).map_err(|err| {
                rusqlite::Error::FromSqlConversionFailure(
                    text_index,
                    rusqlite::types::Type::Text,
                    Box::new(std::io::Error::other(err.to_string())),
                )
            })?;
            scaled_to_float(scaled, RATE_SCALE).map_err(|err| {
                rusqlite::Error::FromSqlConversionFailure(
                    text_index,
                    rusqlite::types::Type::Text,
                    Box::new(std::io::Error::other(err.to_string())),
                )
            })
        }
    } else {
        row.get::<_, f64>(real_index)
    }
}

#[pyfunction]
fn wallet_list_rows(py: Python<'_>, db_path: &str) -> PyResult<Vec<Py<PyAny>>> {
    let conn = open_sqlite_connection(db_path)?;
    let mut stmt = conn
        .prepare(
            "SELECT
                id,
                name,
                currency,
                initial_balance,
                initial_balance_minor,
                system,
                allow_negative,
                is_active
             FROM wallets
             ORDER BY id",
        )
        .map_err(sqlite_err)?;
    let rows = stmt
        .query_map([], |row| {
            Ok((
                row.get::<_, i64>(0)?,
                row.get::<_, String>(1)?,
                row.get::<_, String>(2)?,
                money_value_from_sql_row(row, 3, 4)?,
                row.get::<_, i64>(5)? != 0,
                row.get::<_, i64>(6)? != 0,
                row.get::<_, i64>(7)? != 0,
            ))
        })
        .map_err(sqlite_err)?;

    let mut result = Vec::new();
    for row in rows {
        let (wallet_id, name, currency, initial_balance, system, allow_negative, is_active) =
            row.map_err(sqlite_err)?;
        let payload = PyDict::new(py);
        payload.set_item("id", wallet_id)?;
        payload.set_item("name", name)?;
        payload.set_item("currency", currency)?;
        payload.set_item("initial_balance", initial_balance)?;
        payload.set_item("system", system)?;
        payload.set_item("allow_negative", allow_negative)?;
        payload.set_item("is_active", is_active)?;
        result.push(payload.into_any().unbind());
    }
    Ok(result)
}

#[pyfunction]
fn transfer_list_rows(py: Python<'_>, db_path: &str) -> PyResult<Vec<Py<PyAny>>> {
    let conn = open_sqlite_connection(db_path)?;
    let mut stmt = conn
        .prepare(
            "SELECT
                id,
                from_wallet_id,
                to_wallet_id,
                date,
                amount_original,
                amount_original_minor,
                currency,
                rate_at_operation,
                rate_at_operation_text,
                amount_base,
                amount_base_minor,
                description
             FROM transfers
             ORDER BY id",
        )
        .map_err(sqlite_err)?;
    let rows = stmt
        .query_map([], |row| {
            Ok((
                row.get::<_, i64>(0)?,
                row.get::<_, i64>(1)?,
                row.get::<_, i64>(2)?,
                row.get::<_, String>(3)?,
                money_value_from_sql_row(row, 4, 5)?,
                row.get::<_, String>(6)?,
                rate_value_from_sql_row(row, 7, 8)?,
                money_value_from_sql_row(row, 9, 10)?,
                row.get::<_, String>(11)?,
            ))
        })
        .map_err(sqlite_err)?;

    let mut result = Vec::new();
    for row in rows {
        let (
            transfer_id,
            from_wallet_id,
            to_wallet_id,
            date,
            amount_original,
            currency,
            rate_at_operation,
            amount_base,
            description,
        ) = row.map_err(sqlite_err)?;
        let payload = PyDict::new(py);
        payload.set_item("id", transfer_id)?;
        payload.set_item("from_wallet_id", from_wallet_id)?;
        payload.set_item("to_wallet_id", to_wallet_id)?;
        payload.set_item("date", date)?;
        payload.set_item("amount_original", amount_original)?;
        payload.set_item("currency", currency)?;
        payload.set_item("rate_at_operation", rate_at_operation)?;
        payload.set_item("amount_base", amount_base)?;
        payload.set_item("description", description)?;
        result.push(payload.into_any().unbind());
    }
    Ok(result)
}

#[pyfunction]
fn transfer_id_by_record_index(db_path: &str, index: i64) -> PyResult<Option<i64>> {
    if index < 0 {
        return Ok(None);
    }
    let conn = open_sqlite_connection(db_path)?;
    conn.query_row(
        "SELECT transfer_id
         FROM records
         ORDER BY id
         LIMIT 1 OFFSET ?1",
        [index],
        |row| row.get::<_, Option<i64>>(0),
    )
    .optional()
    .map_err(sqlite_err)
    .map(|value| value.flatten())
}

fn mandatory_expense_select_sql(conn: &Connection, filter_by_id: bool) -> PyResult<String> {
    let mut stmt = conn
        .prepare("PRAGMA table_info(mandatory_expenses)")
        .map_err(sqlite_err)?;
    let rows = stmt
        .query_map([], |row| row.get::<_, String>(1))
        .map_err(sqlite_err)?;
    let mut has_date = false;
    let mut has_auto_pay = false;
    for row in rows {
        let name = row.map_err(sqlite_err)?;
        if name == "date" {
            has_date = true;
        } else if name == "auto_pay" {
            has_auto_pay = true;
        }
    }

    let mut sql = String::from(
        "SELECT
            id,
            wallet_id,
            amount_original,
            amount_original_minor,
            currency,
            rate_at_operation,
            rate_at_operation_text,
            amount_base,
            amount_base_minor,
            category,
            description,
            period",
    );
    if has_date {
        sql.push_str(",\n            date");
    } else {
        sql.push_str(",\n            NULL AS date");
    }
    if has_auto_pay {
        sql.push_str(",\n            auto_pay");
    } else {
        sql.push_str(",\n            0 AS auto_pay");
    }
    sql.push_str("\n         FROM mandatory_expenses");
    if filter_by_id {
        sql.push_str("\n         WHERE id = ?1");
    }
    sql.push_str("\n         ORDER BY id");
    Ok(sql)
}

fn mandatory_expense_row_dicts(
    py: Python<'_>,
    conn: &Connection,
    sql: &str,
    params: &[&dyn rusqlite::ToSql],
) -> PyResult<Vec<Py<PyAny>>> {
    let mut stmt = conn.prepare(sql).map_err(sqlite_err)?;
    let rows = stmt
        .query_map(params, |row| {
            Ok((
                row.get::<_, i64>(0)?,
                row.get::<_, i64>(1)?,
                money_value_from_sql_row(row, 2, 3)?,
                row.get::<_, String>(4)?,
                rate_value_from_sql_row(row, 5, 6)?,
                money_value_from_sql_row(row, 7, 8)?,
                row.get::<_, String>(9)?,
                row.get::<_, String>(10)?,
                row.get::<_, String>(11)?,
                row.get::<_, Option<String>>(12)?,
                row.get::<_, i64>(13)? != 0,
            ))
        })
        .map_err(sqlite_err)?;

    let mut result = Vec::new();
    for row in rows {
        let (
            expense_id,
            wallet_id,
            amount_original,
            currency,
            rate_at_operation,
            amount_base,
            category,
            description,
            period,
            date,
            auto_pay,
        ) = row.map_err(sqlite_err)?;
        let payload = PyDict::new(py);
        payload.set_item("id", expense_id)?;
        payload.set_item("wallet_id", wallet_id)?;
        payload.set_item("amount_original", amount_original)?;
        payload.set_item("currency", currency)?;
        payload.set_item("rate_at_operation", rate_at_operation)?;
        payload.set_item("amount_base", amount_base)?;
        payload.set_item("category", category)?;
        payload.set_item("description", description)?;
        payload.set_item("period", period)?;
        payload.set_item("date", date.unwrap_or_default())?;
        payload.set_item("auto_pay", auto_pay)?;
        result.push(payload.into_any().unbind());
    }
    Ok(result)
}

#[pyfunction]
fn mandatory_expense_rows(py: Python<'_>, db_path: &str) -> PyResult<Vec<Py<PyAny>>> {
    let conn = open_sqlite_connection(db_path)?;
    let sql = mandatory_expense_select_sql(&conn, false)?;
    mandatory_expense_row_dicts(py, &conn, &sql, &[])
}

#[pyfunction]
fn mandatory_expense_row(
    py: Python<'_>,
    db_path: &str,
    expense_id: i64,
) -> PyResult<Option<Py<PyAny>>> {
    let conn = open_sqlite_connection(db_path)?;
    let sql = mandatory_expense_select_sql(&conn, true)?;
    let mut rows = mandatory_expense_row_dicts(py, &conn, &sql, &[&expense_id])?;
    Ok(rows.pop())
}

fn record_row_dicts(
    py: Python<'_>,
    conn: &Connection,
    sql: &str,
    params: &[&dyn rusqlite::ToSql],
) -> PyResult<Vec<Py<PyAny>>> {
    let mut tags_by_record: HashMap<i64, Vec<String>> = HashMap::new();
    let mut tag_stmt = conn
        .prepare(
            "SELECT rt.record_id, t.name
             FROM record_tags AS rt
             JOIN tags AS t ON t.id = rt.tag_id
             ORDER BY rt.record_id, t.name COLLATE NOCASE, t.name",
        )
        .map_err(sqlite_err)?;
    let tag_rows = tag_stmt
        .query_map([], |row| {
            Ok((row.get::<_, i64>(0)?, row.get::<_, String>(1)?))
        })
        .map_err(sqlite_err)?;
    for row in tag_rows {
        let (record_id, tag_name) = row.map_err(sqlite_err)?;
        tags_by_record.entry(record_id).or_default().push(tag_name);
    }

    let mut stmt = conn.prepare(sql).map_err(sqlite_err)?;
    let rows = stmt
        .query_map(params, |row| {
            let record_id: i64 = row.get(0)?;
            let amount_original = money_value_from_sql_row(row, 6, 7)?;
            let amount_base = money_value_from_sql_row(row, 11, 12)?;
            let rate_at_operation = rate_value_from_sql_row(row, 9, 10)?;
            Ok((
                record_id,
                row.get::<_, String>(1)?,
                row.get::<_, String>(2)?,
                row.get::<_, i64>(3)?,
                row.get::<_, Option<i64>>(4)?,
                row.get::<_, Option<i64>>(5)?,
                amount_original,
                row.get::<_, String>(8)?,
                rate_at_operation,
                amount_base,
                row.get::<_, String>(13)?,
                row.get::<_, String>(14)?,
                row.get::<_, Option<String>>(15)?,
            ))
        })
        .map_err(sqlite_err)?;

    let mut result: Vec<Py<PyAny>> = Vec::new();
    for row in rows {
        let (
            record_id,
            record_type,
            date,
            wallet_id,
            transfer_id,
            related_debt_id,
            amount_original,
            currency,
            rate_at_operation,
            amount_base,
            category,
            description,
            period,
        ) = row.map_err(sqlite_err)?;
        let tags = tags_by_record.remove(&record_id).unwrap_or_default();
        let payload = PyDict::new(py);
        payload.set_item("id", record_id)?;
        payload.set_item("type", record_type)?;
        payload.set_item("date", date)?;
        payload.set_item("wallet_id", wallet_id)?;
        payload.set_item("transfer_id", transfer_id)?;
        payload.set_item("related_debt_id", related_debt_id)?;
        payload.set_item("amount_original", amount_original)?;
        payload.set_item("currency", currency)?;
        payload.set_item("rate_at_operation", rate_at_operation)?;
        payload.set_item("amount_base", amount_base)?;
        payload.set_item("category", category)?;
        payload.set_item("description", description)?;
        payload.set_item("period", period)?;
        payload.set_item("tags", tags)?;
        result.push(payload.into_any().unbind());
    }
    Ok(result)
}

#[pyfunction]
fn record_list_rows(py: Python<'_>, db_path: &str) -> PyResult<Vec<Py<PyAny>>> {
    let conn = open_sqlite_connection(db_path)?;
    record_row_dicts(
        py,
        &conn,
        "SELECT
            id,
            type,
            date,
            wallet_id,
            transfer_id,
            related_debt_id,
            amount_original,
            amount_original_minor,
            currency,
            rate_at_operation,
            rate_at_operation_text,
            amount_base,
            amount_base_minor,
            category,
            description,
            period
         FROM records
         ORDER BY id",
        &[],
    )
}

#[pyfunction]
fn record_get_row(py: Python<'_>, db_path: &str, record_id: i64) -> PyResult<Option<Py<PyAny>>> {
    let conn = open_sqlite_connection(db_path)?;
    let mut rows = record_row_dicts(
        py,
        &conn,
        "SELECT
            id,
            type,
            date,
            wallet_id,
            transfer_id,
            related_debt_id,
            amount_original,
            amount_original_minor,
            currency,
            rate_at_operation,
            rate_at_operation_text,
            amount_base,
            amount_base_minor,
            category,
            description,
            period
         FROM records
         WHERE id = ?1",
        &[&record_id],
    )?;
    Ok(rows.pop())
}

#[pyfunction]
fn record_rows_by_tag(py: Python<'_>, db_path: &str, tag_name: &str) -> PyResult<Vec<Py<PyAny>>> {
    let conn = open_sqlite_connection(db_path)?;
    record_row_dicts(
        py,
        &conn,
        "SELECT
            id,
            type,
            date,
            wallet_id,
            transfer_id,
            related_debt_id,
            amount_original,
            amount_original_minor,
            currency,
            rate_at_operation,
            rate_at_operation_text,
            amount_base,
            amount_base_minor,
            category,
            description,
            period
         FROM records
         WHERE EXISTS (
            SELECT 1
            FROM record_tags AS rt
            JOIN tags AS t ON t.id = rt.tag_id
            WHERE rt.record_id = records.id
              AND lower(t.name) = lower(?1)
         )
         ORDER BY id",
        &[&tag_name],
    )
}

#[pymodule]
fn ledgera_core(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(convert_amount, m)?)?;
    m.add_function(wrap_pyfunction!(calculate_daily_burn, m)?)?;
    m.add_function(wrap_pyfunction!(to_money_float, m)?)?;
    m.add_function(wrap_pyfunction!(to_rate_float, m)?)?;
    m.add_function(wrap_pyfunction!(to_minor_units, m)?)?;
    m.add_function(wrap_pyfunction!(minor_to_money, m)?)?;
    m.add_function(wrap_pyfunction!(build_rate, m)?)?;
    m.add_function(wrap_pyfunction!(money_abs, m)?)?;
    m.add_function(wrap_pyfunction!(quantize_money_text, m)?)?;
    m.add_function(wrap_pyfunction!(quantize_rate_text, m)?)?;
    m.add_function(wrap_pyfunction!(rate_to_text, m)?)?;
    m.add_function(wrap_pyfunction!(money_diff_text, m)?)?;
    m.add_function(wrap_pyfunction!(rate_diff_text, m)?)?;
    m.add_function(wrap_pyfunction!(wallet_balance_parts, m)?)?;
    m.add_function(wrap_pyfunction!(wallet_balance_rows, m)?)?;
    m.add_function(wrap_pyfunction!(cashflow_sum, m)?)?;
    m.add_function(wrap_pyfunction!(wallet_list_rows, m)?)?;
    m.add_function(wrap_pyfunction!(transfer_list_rows, m)?)?;
    m.add_function(wrap_pyfunction!(transfer_id_by_record_index, m)?)?;
    m.add_function(wrap_pyfunction!(mandatory_expense_rows, m)?)?;
    m.add_function(wrap_pyfunction!(mandatory_expense_row, m)?)?;
    m.add_function(wrap_pyfunction!(record_list_rows, m)?)?;
    m.add_function(wrap_pyfunction!(record_get_row, m)?)?;
    m.add_function(wrap_pyfunction!(record_rows_by_tag, m)?)?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use pyo3::Python;
    use pyo3::types::PyString;
    use rusqlite::Connection;
    use std::fs;
    use std::path::PathBuf;
    use std::time::{SystemTime, UNIX_EPOCH};

    fn create_balance_test_db() -> String {
        let unique = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap()
            .as_nanos();
        let path = std::env::temp_dir().join(format!("ledgera_balance_test_{unique}.db"));
        let conn = Connection::open(&path).unwrap();
        conn.execute_batch(
            "
            CREATE TABLE wallets (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                currency TEXT NOT NULL,
                initial_balance REAL NOT NULL DEFAULT 0,
                initial_balance_minor INTEGER DEFAULT NULL,
                system INTEGER NOT NULL DEFAULT 0,
                allow_negative INTEGER NOT NULL DEFAULT 0,
                is_active INTEGER NOT NULL DEFAULT 1
            );
            CREATE TABLE transfers (
                id INTEGER PRIMARY KEY,
                from_wallet_id INTEGER NOT NULL,
                to_wallet_id INTEGER NOT NULL,
                date TEXT NOT NULL,
                amount_original REAL NOT NULL,
                amount_original_minor INTEGER DEFAULT NULL,
                currency TEXT NOT NULL,
                rate_at_operation REAL NOT NULL,
                rate_at_operation_text TEXT DEFAULT NULL,
                amount_base REAL NOT NULL,
                amount_base_minor INTEGER DEFAULT NULL,
                description TEXT NOT NULL DEFAULT ''
            );
            CREATE TABLE mandatory_expenses (
                id INTEGER PRIMARY KEY,
                wallet_id INTEGER NOT NULL,
                amount_original REAL NOT NULL,
                amount_original_minor INTEGER DEFAULT NULL,
                currency TEXT NOT NULL,
                rate_at_operation REAL NOT NULL,
                rate_at_operation_text TEXT DEFAULT NULL,
                amount_base REAL NOT NULL,
                amount_base_minor INTEGER DEFAULT NULL,
                category TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                period TEXT DEFAULT NULL,
                date TEXT DEFAULT NULL,
                auto_pay INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE records (
                id INTEGER PRIMARY KEY,
                type TEXT NOT NULL,
                date TEXT NOT NULL,
                wallet_id INTEGER NOT NULL,
                transfer_id INTEGER DEFAULT NULL,
                amount_base REAL NOT NULL,
                amount_base_minor INTEGER DEFAULT NULL
            );
            ",
        )
        .unwrap();
        conn.execute(
            "INSERT INTO wallets (
                id, name, currency, initial_balance, initial_balance_minor, system, allow_negative, is_active
             ) VALUES (1, 'Cash', 'KZT', 1000.0, 100000, 1, 0, 1)",
            [],
        )
        .unwrap();
        conn.execute(
            "INSERT INTO wallets (
                id, name, currency, initial_balance, initial_balance_minor, system, allow_negative, is_active
             ) VALUES (2, 'Card', 'KZT', 500.0, 50000, 0, 1, 1)",
            [],
        )
        .unwrap();
        conn.execute(
            "INSERT INTO wallets (
                id, name, currency, initial_balance, initial_balance_minor, system, allow_negative, is_active
             ) VALUES (3, 'Inactive', 'KZT', 999.0, 99900, 0, 0, 0)",
            [],
        )
        .unwrap();
        conn.execute(
            "INSERT INTO transfers (
                id, from_wallet_id, to_wallet_id, date, amount_original, amount_original_minor,
                currency, rate_at_operation, rate_at_operation_text, amount_base, amount_base_minor, description
             ) VALUES (
                1, 1, 2, '2026-01-04', 300.0, 30000,
                'KZT', 1.0, '1.000000', 300.0, 30000, 'Move to card'
             )",
            [],
        )
        .unwrap();
        conn.execute(
            "INSERT INTO mandatory_expenses (
                id, wallet_id, amount_original, amount_original_minor, currency,
                rate_at_operation, rate_at_operation_text, amount_base, amount_base_minor,
                category, description, period, date, auto_pay
             ) VALUES (
                1, 1, 40.0, 4000, 'KZT',
                1.0, '1.000000', 40.0, 4000,
                'Rent', 'Monthly rent', 'monthly', '2026-01-15', 1
             )",
            [],
        )
        .unwrap();
        conn.execute(
            "INSERT INTO records (id, type, date, wallet_id, transfer_id, amount_base, amount_base_minor)
             VALUES (1, 'income', '2026-01-01', 1, NULL, 200.0, 20000)",
            [],
        )
        .unwrap();
        conn.execute(
            "INSERT INTO records (id, type, date, wallet_id, transfer_id, amount_base, amount_base_minor)
             VALUES (2, 'expense', '2026-01-02', 1, NULL, 50.0, 5000)",
            [],
        )
        .unwrap();
        conn.execute(
            "INSERT INTO records (id, type, date, wallet_id, transfer_id, amount_base, amount_base_minor)
             VALUES (3, 'mandatory_expense', '2026-01-03', 2, NULL, 25.0, 2500)",
            [],
        )
        .unwrap();
        conn.execute(
            "INSERT INTO records (id, type, date, wallet_id, transfer_id, amount_base, amount_base_minor)
             VALUES (4, 'expense', '2026-01-04', 1, 1, 300.0, 30000)",
            [],
        )
        .unwrap();
        conn.execute(
            "INSERT INTO records (id, type, date, wallet_id, transfer_id, amount_base, amount_base_minor)
             VALUES (5, 'income', '2026-01-04', 2, 1, 300.0, 30000)",
            [],
        )
        .unwrap();
        path.to_string_lossy().into_owned()
    }

    fn remove_test_db(path: &str) {
        let _ = fs::remove_file(PathBuf::from(path));
    }

    #[test]
    fn test_convert_amount() {
        assert_eq!(convert_amount(100.0, 2.0).unwrap(), 200.0);
    }

    #[test]
    fn test_calculate_daily_burn() {
        assert_eq!(calculate_daily_burn(100.0, 4).unwrap(), 25.0);
        assert_eq!(calculate_daily_burn(100.0, 0).unwrap(), 100.0);
    }

    #[test]
    fn test_money_rounding_half_up() {
        Python::initialize();
        Python::attach(|py| {
            let value = PyString::new(py, "1.005");
            assert_eq!(to_money_float(&value.into_any()).unwrap(), 1.01);
            let negative = PyString::new(py, "-1.005");
            assert_eq!(to_money_float(&negative.into_any()).unwrap(), -1.01);
        });
    }

    #[test]
    fn test_rate_rounding_half_up() {
        Python::initialize();
        Python::attach(|py| {
            let value = PyString::new(py, "1.2345675");
            assert_eq!(to_rate_float(&value.into_any()).unwrap(), 1.234568);
        });
    }

    #[test]
    fn test_minor_units_round_trip() {
        Python::initialize();
        Python::attach(|py| {
            let value = PyString::new(py, "123.455");
            assert_eq!(to_minor_units(&value.into_any()).unwrap(), 12346);
            let units = PyString::new(py, "12346");
            assert_eq!(minor_to_money(&units.into_any()).unwrap(), 123.46);
        });
    }

    #[test]
    fn test_build_rate_preserves_special_cases() {
        Python::initialize();
        Python::attach(|py| {
            let amount_original = PyString::new(py, "10.00");
            let amount_base = PyString::new(py, "5000.00");
            assert_eq!(
                build_rate(
                    &amount_original.clone().into_any(),
                    &amount_base.clone().into_any(),
                    "USD",
                )
                .unwrap(),
                500.0
            );

            let zero_original = PyString::new(py, "0");
            assert_eq!(
                build_rate(
                    &zero_original.into_any(),
                    &amount_base.clone().into_any(),
                    "USD"
                )
                .unwrap(),
                1.0
            );

            assert_eq!(
                build_rate(&amount_original.into_any(), &amount_base.into_any(), "KZT").unwrap(),
                1.0
            );
        });
    }

    #[test]
    fn test_money_abs_quantizes_before_abs() {
        Python::initialize();
        Python::attach(|py| {
            let value = PyString::new(py, "-10.004");
            assert_eq!(money_abs(&value.into_any()).unwrap(), 10.0);
        });
    }

    #[test]
    fn test_quantize_money_text_half_up() {
        Python::initialize();
        Python::attach(|py| {
            let value = PyString::new(py, "1.005");
            assert_eq!(quantize_money_text(&value.into_any()).unwrap(), "1.01");
            let negative = PyString::new(py, "-1.005");
            assert_eq!(quantize_money_text(&negative.into_any()).unwrap(), "-1.01");
        });
    }

    #[test]
    fn test_quantize_rate_text_half_up() {
        Python::initialize();
        Python::attach(|py| {
            let value = PyString::new(py, "1.2345675");
            assert_eq!(quantize_rate_text(&value.into_any()).unwrap(), "1.234568");
        });
    }

    #[test]
    fn test_rate_to_text_preserves_canonical_scale() {
        Python::initialize();
        Python::attach(|py| {
            let value = PyString::new(py, "1.2");
            assert_eq!(rate_to_text(&value.into_any()).unwrap(), "1.200000");
        });
    }

    #[test]
    fn test_money_diff_text_preserves_sign_and_rounding() {
        Python::initialize();
        Python::attach(|py| {
            let left = PyString::new(py, "10.005");
            let right = PyString::new(py, "1.00");
            assert_eq!(
                money_diff_text(&left.into_any(), &right.into_any()).unwrap(),
                "9.01"
            );
        });
    }

    #[test]
    fn test_rate_diff_text_preserves_sign_and_scale() {
        Python::initialize();
        Python::attach(|py| {
            let left = PyString::new(py, "1.2345675");
            let right = PyString::new(py, "0.2345674");
            assert_eq!(
                rate_diff_text(&left.into_any(), &right.into_any()).unwrap(),
                "1.000001"
            );
        });
    }

    #[test]
    fn test_wallet_balance_parts_reads_sqlite_balance_state() {
        let db_path = create_balance_test_db();
        let result = wallet_balance_parts(&db_path, 1, None).unwrap().unwrap();
        assert_eq!(result.0, 1000.0);
        assert_eq!(result.1, "KZT");
        assert_eq!(result.2, -150.0);
        remove_test_db(&db_path);
    }

    #[test]
    fn test_wallet_balance_rows_returns_active_wallets_only() {
        let db_path = create_balance_test_db();
        let rows = wallet_balance_rows(&db_path, Some("2026-01-03")).unwrap();
        assert_eq!(rows.len(), 2);
        assert_eq!(
            rows[0],
            (1, "Cash".to_owned(), "KZT".to_owned(), 1000.0, 150.0)
        );
        assert_eq!(
            rows[1],
            (2, "Card".to_owned(), "KZT".to_owned(), 500.0, -25.0)
        );
        remove_test_db(&db_path);
    }

    #[test]
    fn test_cashflow_sum_excludes_transfer_linked_records() {
        let db_path = create_balance_test_db();
        assert_eq!(
            cashflow_sum(&db_path, "income", "2026-01-01", "2026-01-31").unwrap(),
            200.0
        );
        assert_eq!(
            cashflow_sum(&db_path, "expense", "2026-01-01", "2026-01-31").unwrap(),
            75.0
        );
        remove_test_db(&db_path);
    }

    #[test]
    fn test_wallet_list_rows_preserves_wallet_flags_and_minor_balance() {
        Python::initialize();
        let db_path = create_balance_test_db();
        Python::attach(|py| {
            let rows = wallet_list_rows(py, &db_path).unwrap();
            let first = rows[0].bind(py);
            assert_eq!(first.get_item("id").unwrap().extract::<i64>().unwrap(), 1);
            assert!(first.get_item("system").unwrap().extract::<bool>().unwrap());
            assert_eq!(
                first
                    .get_item("initial_balance")
                    .unwrap()
                    .extract::<f64>()
                    .unwrap(),
                1000.0
            );
            let second = rows[1].bind(py);
            assert!(
                second
                    .get_item("allow_negative")
                    .unwrap()
                    .extract::<bool>()
                    .unwrap()
            );
        });
        remove_test_db(&db_path);
    }

    #[test]
    fn test_transfer_list_rows_reads_money_and_rate_columns() {
        Python::initialize();
        let db_path = create_balance_test_db();
        Python::attach(|py| {
            let rows = transfer_list_rows(py, &db_path).unwrap();
            assert_eq!(rows.len(), 1);
            let row = rows[0].bind(py);
            assert_eq!(
                row.get_item("from_wallet_id")
                    .unwrap()
                    .extract::<i64>()
                    .unwrap(),
                1
            );
            assert_eq!(
                row.get_item("to_wallet_id")
                    .unwrap()
                    .extract::<i64>()
                    .unwrap(),
                2
            );
            assert_eq!(
                row.get_item("amount_original")
                    .unwrap()
                    .extract::<f64>()
                    .unwrap(),
                300.0
            );
            assert_eq!(
                row.get_item("rate_at_operation")
                    .unwrap()
                    .extract::<f64>()
                    .unwrap(),
                1.0
            );
        });
        remove_test_db(&db_path);
    }

    #[test]
    fn test_transfer_id_by_record_index_reads_nullable_lookup() {
        let db_path = create_balance_test_db();
        assert_eq!(transfer_id_by_record_index(&db_path, 0).unwrap(), None);
        assert_eq!(transfer_id_by_record_index(&db_path, 3).unwrap(), Some(1));
        assert_eq!(transfer_id_by_record_index(&db_path, -1).unwrap(), None);
        remove_test_db(&db_path);
    }

    #[test]
    fn test_mandatory_expense_rows_and_row_preserve_read_contract() {
        Python::initialize();
        let db_path = create_balance_test_db();
        Python::attach(|py| {
            let rows = mandatory_expense_rows(py, &db_path).unwrap();
            assert_eq!(rows.len(), 1);
            let row = rows[0].bind(py);
            assert_eq!(
                row.get_item("category")
                    .unwrap()
                    .extract::<String>()
                    .unwrap(),
                "Rent"
            );
            assert!(row.get_item("auto_pay").unwrap().extract::<bool>().unwrap());
            let single = mandatory_expense_row(py, &db_path, 1).unwrap().unwrap();
            assert_eq!(
                single
                    .bind(py)
                    .get_item("date")
                    .unwrap()
                    .extract::<String>()
                    .unwrap(),
                "2026-01-15"
            );
            assert!(mandatory_expense_row(py, &db_path, 99).unwrap().is_none());
        });
        remove_test_db(&db_path);
    }
}
