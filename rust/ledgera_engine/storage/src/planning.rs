use crate::{
    StorageResult, minor_amount_expr, signed_minor_amount_expr, sqlite_err,
    with_cached_read_connection,
};
use ledgera_engine_core::minor_to_money_value;
use rusqlite::OptionalExtension;

const FULL_PCT_MINOR: i64 = 10_000;

#[derive(Debug, Clone, PartialEq)]
pub struct DistributionValidationRow {
    pub level: String,
    pub message: String,
}

#[derive(Debug, Clone, PartialEq)]
pub struct DistributionItemPayload {
    pub id: i64,
    pub name: String,
    pub group_name: String,
    pub sort_order: i64,
    pub pct: f64,
    pub pct_minor: i64,
    pub is_active: bool,
    pub amount_base: f64,
    pub amount_minor: i64,
    pub subitems: Vec<DistributionSubitemPayload>,
}

#[derive(Debug, Clone, PartialEq)]
pub struct DistributionSubitemPayload {
    pub id: i64,
    pub item_id: i64,
    pub name: String,
    pub sort_order: i64,
    pub pct: f64,
    pub pct_minor: i64,
    pub is_active: bool,
    pub amount_base: f64,
    pub amount_minor: i64,
}

#[derive(Debug, Clone, PartialEq)]
pub struct DistributionMonthlyPayload {
    pub month: String,
    pub net_income_base: f64,
    pub net_income_minor: i64,
    pub is_negative: bool,
    pub items: Vec<DistributionItemPayload>,
}

#[derive(Debug, Clone, PartialEq)]
pub struct DebtRecalculatePayload {
    pub remaining_amount_minor: i64,
    pub status: String,
    pub closed_at: Option<String>,
}

fn apply_pct(amount_minor: i64, pct_minor: i64) -> i64 {
    let numerator = i128::from(amount_minor) * i128::from(pct_minor);
    let sign = if numerator < 0 { -1 } else { 1 };
    let rounded_abs = (numerator.abs() + i128::from(FULL_PCT_MINOR / 2)) / i128::from(FULL_PCT_MINOR);
    (rounded_abs * i128::from(sign)) as i64
}

pub fn distribution_net_income_for_period(
    db_path: &str,
    start_date: &str,
    end_date: &str,
) -> StorageResult<(f64, i64)> {
    with_cached_read_connection(db_path, |conn| {
        let expr = signed_minor_amount_expr("amount_base", "type");
        let net_minor = conn
            .query_row(
                &format!(
                    "SELECT COALESCE(SUM({expr}), 0)
                     FROM records
                     WHERE transfer_id IS NULL
                       AND date >= ?
                       AND date <= ?"
                ),
                (start_date, end_date),
                |row| row.get::<_, i64>(0),
            )
            .map_err(sqlite_err)?;
        Ok((minor_to_money_value(net_minor), net_minor))
    })
}

pub fn distribution_available_months(db_path: &str) -> StorageResult<Vec<String>> {
    with_cached_read_connection(db_path, |conn| {
        let mut stmt = conn
            .prepare(
                "SELECT DISTINCT substr(date, 1, 7) AS month
                 FROM records
                 WHERE transfer_id IS NULL
                 ORDER BY month ASC",
            )
            .map_err(sqlite_err)?;
        let rows = stmt
            .query_map([], |row| row.get::<_, String>(0))
            .map_err(sqlite_err)?;
        rows.collect::<Result<Vec<_>, _>>().map_err(sqlite_err)
    })
}

pub fn distribution_history_months(
    db_path: &str,
    start_month: &str,
    end_month: &str,
) -> StorageResult<Vec<String>> {
    with_cached_read_connection(db_path, |conn| {
        let mut stmt = conn
            .prepare(
                "SELECT DISTINCT substr(date, 1, 7) AS month
                 FROM records
                 WHERE transfer_id IS NULL
                   AND substr(date, 1, 7) >= ?
                   AND substr(date, 1, 7) <= ?
                 ORDER BY month ASC",
            )
            .map_err(sqlite_err)?;
        let rows = stmt
            .query_map((start_month, end_month), |row| row.get::<_, String>(0))
            .map_err(sqlite_err)?;
        rows.collect::<Result<Vec<_>, _>>().map_err(sqlite_err)
    })
}

pub fn distribution_validate_structure(
    db_path: &str,
) -> StorageResult<Vec<DistributionValidationRow>> {
    with_cached_read_connection(db_path, |conn| {
        let mut errors = Vec::new();
        let total_pct_minor = conn
            .query_row(
                "SELECT COALESCE(SUM(pct_minor), 0)
                 FROM distribution_items
                 WHERE is_active = 1",
                [],
                |row| row.get::<_, i64>(0),
            )
            .map_err(sqlite_err)?;
        if total_pct_minor != FULL_PCT_MINOR {
            errors.push(DistributionValidationRow {
                level: "error".to_owned(),
                message: format!(
                    "Sum of top-level item percentages is {:.2}% (must be 100.00%)",
                    minor_to_money_value(total_pct_minor)
                ),
            });
        }

        let mut stmt = conn
            .prepare(
                "SELECT id, name
                 FROM distribution_items
                 WHERE is_active = 1
                 ORDER BY sort_order ASC, name COLLATE NOCASE ASC, id ASC",
            )
            .map_err(sqlite_err)?;
        let items = stmt
            .query_map([], |row| Ok((row.get::<_, i64>(0)?, row.get::<_, String>(1)?)))
            .map_err(sqlite_err)?;
        for item in items {
            let (item_id, item_name) = item.map_err(sqlite_err)?;
            let (sub_total_minor, sub_count) = conn
                .query_row(
                    "SELECT COALESCE(SUM(pct_minor), 0), COUNT(*)
                     FROM distribution_subitems
                     WHERE item_id = ? AND is_active = 1",
                    [item_id],
                    |row| Ok((row.get::<_, i64>(0)?, row.get::<_, i64>(1)?)),
                )
                .map_err(sqlite_err)?;
            if sub_count > 0 && sub_total_minor != FULL_PCT_MINOR {
                errors.push(DistributionValidationRow {
                    level: "error".to_owned(),
                    message: format!(
                        "Sum of subitem percentages for '{}' is {:.2}% (must be 100.00%)",
                        item_name,
                        minor_to_money_value(sub_total_minor)
                    ),
                });
            }
        }
        Ok(errors)
    })
}

pub fn distribution_monthly_payload(
    db_path: &str,
    month: &str,
    start_date: &str,
    end_date: &str,
) -> StorageResult<DistributionMonthlyPayload> {
    let (net_income_base, net_income_minor) =
        distribution_net_income_for_period(db_path, start_date, end_date)?;
    with_cached_read_connection(db_path, |conn| {
        let mut item_stmt = conn
            .prepare(
                "SELECT id, name, group_name, sort_order, pct, pct_minor, is_active
                 FROM distribution_items
                 WHERE is_active = 1
                 ORDER BY sort_order ASC, name COLLATE NOCASE ASC, id ASC",
            )
            .map_err(sqlite_err)?;
        let item_rows = item_stmt
            .query_map([], |row| {
                Ok((
                    row.get::<_, i64>(0)?,
                    row.get::<_, String>(1)?,
                    row.get::<_, String>(2)?,
                    row.get::<_, i64>(3)?,
                    row.get::<_, f64>(4)?,
                    row.get::<_, i64>(5)?,
                    row.get::<_, bool>(6)?,
                ))
            })
            .map_err(sqlite_err)?;
        let mut items = Vec::new();
        for item_row in item_rows {
            let (id, name, group_name, sort_order, pct, pct_minor, is_active) =
                item_row.map_err(sqlite_err)?;
            let item_minor = apply_pct(net_income_minor, pct_minor);
            let mut sub_stmt = conn
                .prepare(
                    "SELECT id, item_id, name, sort_order, pct, pct_minor, is_active
                     FROM distribution_subitems
                     WHERE item_id = ? AND is_active = 1
                     ORDER BY sort_order ASC, name COLLATE NOCASE ASC, id ASC",
                )
                .map_err(sqlite_err)?;
            let sub_rows = sub_stmt
                .query_map([id], |row| {
                    Ok(DistributionSubitemPayload {
                        id: row.get(0)?,
                        item_id: row.get(1)?,
                        name: row.get(2)?,
                        sort_order: row.get(3)?,
                        pct: row.get(4)?,
                        pct_minor: row.get(5)?,
                        is_active: row.get(6)?,
                        amount_base: 0.0,
                        amount_minor: 0,
                    })
                })
                .map_err(sqlite_err)?;
            let mut subitems = Vec::new();
            for sub_row in sub_rows {
                let mut subitem = sub_row.map_err(sqlite_err)?;
                subitem.amount_minor = apply_pct(item_minor, subitem.pct_minor);
                subitem.amount_base = minor_to_money_value(subitem.amount_minor);
                subitems.push(subitem);
            }
            items.push(DistributionItemPayload {
                id,
                name,
                group_name,
                sort_order,
                pct,
                pct_minor,
                is_active,
                amount_base: minor_to_money_value(item_minor),
                amount_minor: item_minor,
                subitems,
            });
        }
        Ok(DistributionMonthlyPayload {
            month: month.to_owned(),
            net_income_base,
            net_income_minor,
            is_negative: net_income_minor < 0,
            items,
        })
    })
}

pub fn budget_spent_minor(
    db_path: &str,
    scope_type: &str,
    scope_value: &str,
    start_date: &str,
    end_date: &str,
    include_mandatory: bool,
) -> StorageResult<i64> {
    with_cached_read_connection(db_path, |conn| {
        let minor_expr = minor_amount_expr("amount_base");
        let type_filter = if include_mandatory {
            "type IN ('expense', 'mandatory_expense')"
        } else {
            "type = 'expense'"
        };
        let sql = if scope_type == "tag" {
            format!(
                "SELECT COALESCE(SUM({minor_expr}), 0)
                 FROM records
                 WHERE {type_filter}
                   AND transfer_id IS NULL
                   AND date >= ?
                   AND date <= ?
                   AND EXISTS (
                        SELECT 1
                        FROM record_tags AS rt
                        JOIN tags AS t ON t.id = rt.tag_id
                        WHERE rt.record_id = records.id
                          AND lower(t.name) = lower(?)
                   )"
            )
        } else {
            format!(
                "SELECT COALESCE(SUM({minor_expr}), 0)
                 FROM records
                 WHERE {type_filter}
                   AND category = ?
                   AND transfer_id IS NULL
                   AND date >= ?
                   AND date <= ?"
            )
        };
        let params: [&dyn rusqlite::ToSql; 3] = if scope_type == "tag" {
            [&start_date, &end_date, &scope_value]
        } else {
            [&scope_value, &start_date, &end_date]
        };
        conn.query_row(&sql, params, |row| row.get::<_, i64>(0))
            .map_err(sqlite_err)
    })
}

pub fn budget_batch_spent_minor(
    db_path: &str,
    budgets: &[(i64, String, String, String, String, bool)],
) -> StorageResult<Vec<(i64, i64)>> {
    budgets
        .iter()
        .map(|(id, scope_type, scope_value, start_date, end_date, include_mandatory)| {
            budget_spent_minor(
                db_path,
                scope_type,
                scope_value,
                start_date,
                end_date,
                *include_mandatory,
            )
            .map(|spent| (*id, spent))
        })
        .collect()
}

pub fn budget_overlap_exists(
    db_path: &str,
    scope_type: &str,
    scope_value: &str,
    start_date: &str,
    end_date: &str,
    exclude_id: Option<i64>,
) -> StorageResult<bool> {
    with_cached_read_connection(db_path, |conn| {
        let exclude_clause = if exclude_id.is_some() { "AND id != ?" } else { "" };
        let sql = format!(
            "SELECT 1
             FROM budgets
             WHERE scope_type = ?
               AND scope_value = ?
               AND start_date <= ?
               AND end_date >= ?
               {exclude_clause}
             LIMIT 1"
        );
        let exists = if let Some(id) = exclude_id {
            conn.query_row(
                &sql,
                (scope_type, scope_value, end_date, start_date, id),
                |_| Ok(()),
            )
            .optional()
        } else {
            conn.query_row(&sql, (scope_type, scope_value, end_date, start_date), |_| Ok(()))
                .optional()
        }
        .map_err(sqlite_err)?
        .is_some();
        Ok(exists)
    })
}

pub fn debt_payment_total_minor(db_path: &str, debt_id: i64) -> StorageResult<i64> {
    with_cached_read_connection(db_path, |conn| {
        conn.query_row(
            "SELECT COALESCE(SUM(principal_paid_minor), 0)
             FROM debt_payments
             WHERE debt_id = ?",
            [debt_id],
            |row| row.get::<_, i64>(0),
        )
        .map_err(sqlite_err)
    })
}

pub fn debt_recalculate_payload(
    db_path: &str,
    debt_id: i64,
) -> StorageResult<DebtRecalculatePayload> {
    with_cached_read_connection(db_path, |conn| {
        let total_amount_minor = conn
            .query_row(
                "SELECT total_amount_minor FROM debts WHERE id = ?",
                [debt_id],
                |row| row.get::<_, i64>(0),
            )
            .map_err(sqlite_err)?;
        let (paid_minor, latest_payment_date) = conn
            .query_row(
                "SELECT COALESCE(SUM(principal_paid_minor), 0), MAX(payment_date)
                 FROM debt_payments
                 WHERE debt_id = ?",
                [debt_id],
                |row| Ok((row.get::<_, i64>(0)?, row.get::<_, Option<String>>(1)?)),
            )
            .map_err(sqlite_err)?;
        let remaining_amount_minor = (total_amount_minor - paid_minor).max(0);
        let is_closed = remaining_amount_minor == 0;
        Ok(DebtRecalculatePayload {
            remaining_amount_minor,
            status: if is_closed { "closed" } else { "open" }.to_owned(),
            closed_at: if is_closed { latest_payment_date } else { None },
        })
    })
}

pub fn debt_validate_payment_amount(
    remaining_amount_minor: i64,
    payment_amount_minor: i64,
) -> StorageResult<i64> {
    if payment_amount_minor <= 0 {
        return Err("Payment amount must be positive".to_owned());
    }
    if payment_amount_minor > remaining_amount_minor {
        return Err("Payment amount exceeds remaining debt".to_owned());
    }
    Ok(payment_amount_minor)
}

#[cfg(test)]
mod tests {
    use super::apply_pct;

    #[test]
    fn apply_pct_rounds_half_up_for_positive_and_negative_values() {
        assert_eq!(apply_pct(101, 5000), 51);
        assert_eq!(apply_pct(-101, 5000), -51);
    }
}
