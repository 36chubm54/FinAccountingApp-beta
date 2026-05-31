use crate::{
    StorageResult, minor_amount_expr, signed_minor_amount_expr, sqlite_err,
    storage_clear_read_connection_cache, with_cached_read_connection,
};
use ledgera_engine_core::minor_to_money_value;
use rusqlite::{Connection, OptionalExtension, params, params_from_iter};

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
pub struct FrozenDistributionPayload {
    pub month: String,
    pub column_order: Vec<String>,
    pub headings_by_column: Vec<(String, String)>,
    pub values_by_column: Vec<(String, String)>,
    pub is_negative: bool,
    pub auto_fixed: bool,
}

#[derive(Debug, Clone, PartialEq)]
pub struct BudgetPayload {
    pub id: i64,
    pub category: String,
    pub start_date: String,
    pub end_date: String,
    pub limit_base: f64,
    pub limit_base_minor: i64,
    pub include_mandatory: bool,
    pub scope_type: String,
    pub scope_value: String,
}

#[derive(Debug, Clone, PartialEq)]
pub struct BudgetCreatePayload<'a> {
    pub category: &'a str,
    pub scope_type: &'a str,
    pub scope_value: &'a str,
    pub start_date: &'a str,
    pub end_date: &'a str,
    pub limit_base: f64,
    pub limit_base_minor: i64,
    pub include_mandatory: bool,
}

#[derive(Debug, Clone, PartialEq)]
pub struct DebtRecalculatePayload {
    pub remaining_amount_minor: i64,
    pub status: String,
    pub closed_at: Option<String>,
}

#[derive(Debug, Clone, PartialEq)]
pub struct DebtPayload {
    pub id: i64,
    pub contact_name: String,
    pub kind: String,
    pub total_amount_minor: i64,
    pub remaining_amount_minor: i64,
    pub currency: String,
    pub interest_rate: f64,
    pub status: String,
    pub created_at: String,
    pub closed_at: Option<String>,
}

#[derive(Debug, Clone, PartialEq)]
pub struct DebtPaymentPayload {
    pub id: i64,
    pub debt_id: i64,
    pub record_id: Option<i64>,
    pub operation_type: String,
    pub principal_paid_minor: i64,
    pub is_write_off: bool,
    pub payment_date: String,
}

#[derive(Debug, Clone, PartialEq)]
pub struct DebtRecordPayload {
    pub record_type: String,
    pub date: String,
    pub wallet_id: i64,
    pub amount_original: f64,
    pub amount_original_minor: i64,
    pub currency: String,
    pub rate_at_operation: f64,
    pub rate_at_operation_text: String,
    pub amount_base: f64,
    pub amount_base_minor: i64,
    pub category: String,
    pub description: String,
    pub period: Option<String>,
}

fn apply_pct(amount_minor: i64, pct_minor: i64) -> i64 {
    let numerator = i128::from(amount_minor) * i128::from(pct_minor);
    let sign = if numerator < 0 { -1 } else { 1 };
    let rounded_abs =
        (numerator.abs() + i128::from(FULL_PCT_MINOR / 2)) / i128::from(FULL_PCT_MINOR);
    (rounded_abs * i128::from(sign)) as i64
}

fn open_write_connection(db_path: &str) -> StorageResult<Connection> {
    Connection::open(db_path).map_err(sqlite_err)
}

fn map_distribution_integrity_error(
    err: rusqlite::Error,
    name: &str,
    item_id: Option<i64>,
) -> String {
    let message = err.to_string();
    if message.contains("distribution_items.name") {
        return format!("Distribution item '{name}' already exists");
    }
    if message.contains("distribution_subitems.item_id, distribution_subitems.name") {
        if let Some(id) = item_id {
            return format!("Distribution subitem '{name}' already exists for item #{id}");
        }
        return format!("Distribution subitem '{name}' already exists");
    }
    format!("sqlite error: {err}")
}

fn distribution_item_from_conn(
    conn: &Connection,
    item_id: i64,
) -> StorageResult<DistributionItemPayload> {
    conn.query_row(
        "SELECT id, name, group_name, sort_order, pct, pct_minor, is_active
         FROM distribution_items
         WHERE id = ?",
        [item_id],
        |row| {
            Ok(DistributionItemPayload {
                id: row.get(0)?,
                name: row.get(1)?,
                group_name: row.get(2)?,
                sort_order: row.get(3)?,
                pct: row.get(4)?,
                pct_minor: row.get(5)?,
                is_active: row.get(6)?,
                amount_base: 0.0,
                amount_minor: 0,
                subitems: Vec::new(),
            })
        },
    )
    .optional()
    .map_err(sqlite_err)?
    .ok_or_else(|| format!("Distribution item not found: {item_id}"))
}

fn distribution_subitem_from_conn(
    conn: &Connection,
    subitem_id: i64,
) -> StorageResult<DistributionSubitemPayload> {
    conn.query_row(
        "SELECT id, item_id, name, sort_order, pct, pct_minor, is_active
         FROM distribution_subitems
         WHERE id = ?",
        [subitem_id],
        |row| {
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
        },
    )
    .optional()
    .map_err(sqlite_err)?
    .ok_or_else(|| format!("Distribution subitem not found: {subitem_id}"))
}

fn distribution_item_exists(conn: &Connection, item_id: i64) -> StorageResult<bool> {
    conn.query_row(
        "SELECT 1 FROM distribution_items WHERE id = ?",
        [item_id],
        |_| Ok(()),
    )
    .optional()
    .map_err(sqlite_err)
    .map(|row| row.is_some())
}

fn budget_from_conn(conn: &Connection, budget_id: i64) -> StorageResult<BudgetPayload> {
    conn.query_row(
        "SELECT id, category, start_date, end_date,
                limit_base, limit_base_minor, include_mandatory, scope_type, scope_value
         FROM budgets
         WHERE id = ?",
        [budget_id],
        |row| {
            Ok(BudgetPayload {
                id: row.get(0)?,
                category: row.get(1)?,
                start_date: row.get(2)?,
                end_date: row.get(3)?,
                limit_base: row.get(4)?,
                limit_base_minor: row.get(5)?,
                include_mandatory: row.get(6)?,
                scope_type: row.get(7)?,
                scope_value: row.get(8)?,
            })
        },
    )
    .optional()
    .map_err(sqlite_err)?
    .ok_or_else(|| format!("Budget not found: {budget_id}"))
}

fn budget_exists(conn: &Connection, budget_id: i64) -> StorageResult<bool> {
    conn.query_row(
        "SELECT 1 FROM budgets WHERE id = ?",
        [budget_id],
        |_| Ok(()),
    )
    .optional()
    .map_err(sqlite_err)
    .map(|row| row.is_some())
}

fn debt_from_conn(conn: &Connection, debt_id: i64) -> StorageResult<DebtPayload> {
    conn.query_row(
        "SELECT id, contact_name, kind, total_amount_minor, remaining_amount_minor,
                currency, interest_rate, status, created_at, closed_at
         FROM debts
         WHERE id = ?",
        [debt_id],
        |row| {
            Ok(DebtPayload {
                id: row.get(0)?,
                contact_name: row.get(1)?,
                kind: row.get(2)?,
                total_amount_minor: row.get(3)?,
                remaining_amount_minor: row.get(4)?,
                currency: row.get(5)?,
                interest_rate: row.get(6)?,
                status: row.get(7)?,
                created_at: row.get(8)?,
                closed_at: row.get(9)?,
            })
        },
    )
    .optional()
    .map_err(sqlite_err)?
    .ok_or_else(|| format!("Debt not found: {debt_id}"))
}

fn debt_payment_from_conn(
    conn: &Connection,
    payment_id: i64,
) -> StorageResult<DebtPaymentPayload> {
    conn.query_row(
        "SELECT id, debt_id, record_id, operation_type, principal_paid_minor,
                is_write_off, payment_date
         FROM debt_payments
         WHERE id = ?",
        [payment_id],
        |row| {
            Ok(DebtPaymentPayload {
                id: row.get(0)?,
                debt_id: row.get(1)?,
                record_id: row.get(2)?,
                operation_type: row.get(3)?,
                principal_paid_minor: row.get(4)?,
                is_write_off: row.get(5)?,
                payment_date: row.get(6)?,
            })
        },
    )
    .optional()
    .map_err(sqlite_err)?
    .ok_or_else(|| format!("Debt payment not found: {payment_id}"))
}

fn insert_debt_row(conn: &Connection, debt: &DebtPayload, with_id: bool) -> StorageResult<i64> {
    if with_id {
        conn.execute(
            "INSERT INTO debts (
                id, contact_name, kind, total_amount_minor, remaining_amount_minor,
                currency, interest_rate, status, created_at, closed_at
             )
             VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            params![
                debt.id,
                debt.contact_name,
                debt.kind,
                debt.total_amount_minor,
                debt.remaining_amount_minor,
                debt.currency,
                debt.interest_rate,
                debt.status,
                debt.created_at,
                debt.closed_at
            ],
        )
        .map_err(sqlite_err)?;
        Ok(debt.id)
    } else {
        conn.execute(
            "INSERT INTO debts (
                contact_name, kind, total_amount_minor, remaining_amount_minor,
                currency, interest_rate, status, created_at, closed_at
             )
             VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            params![
                debt.contact_name,
                debt.kind,
                debt.total_amount_minor,
                debt.remaining_amount_minor,
                debt.currency,
                debt.interest_rate,
                debt.status,
                debt.created_at,
                debt.closed_at
            ],
        )
        .map_err(sqlite_err)?;
        Ok(conn.last_insert_rowid())
    }
}

fn insert_debt_record_row(
    conn: &Connection,
    record: &DebtRecordPayload,
    related_debt_id: i64,
) -> StorageResult<i64> {
    conn.execute(
        "INSERT INTO records (
            type, date, wallet_id, transfer_id, related_debt_id,
            amount_original, amount_original_minor, currency,
            rate_at_operation, rate_at_operation_text,
            amount_base, amount_base_minor, category, description, period
         )
         VALUES (?, ?, ?, NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        params![
            record.record_type,
            record.date,
            record.wallet_id,
            related_debt_id,
            record.amount_original,
            record.amount_original_minor,
            record.currency,
            record.rate_at_operation,
            record.rate_at_operation_text,
            record.amount_base,
            record.amount_base_minor,
            record.category,
            record.description,
            record.period
        ],
    )
    .map_err(sqlite_err)?;
    Ok(conn.last_insert_rowid())
}

fn insert_debt_payment_row(
    conn: &Connection,
    payment: &DebtPaymentPayload,
    debt_id: i64,
    record_id: Option<i64>,
    with_id: bool,
) -> StorageResult<i64> {
    if with_id {
        conn.execute(
            "INSERT INTO debt_payments (
                id, debt_id, record_id, operation_type,
                principal_paid_minor, is_write_off, payment_date
             )
             VALUES (?, ?, ?, ?, ?, ?, ?)",
            params![
                payment.id,
                debt_id,
                record_id,
                payment.operation_type,
                payment.principal_paid_minor,
                payment.is_write_off,
                payment.payment_date
            ],
        )
        .map_err(sqlite_err)?;
        Ok(payment.id)
    } else {
        conn.execute(
            "INSERT INTO debt_payments (
                debt_id, record_id, operation_type,
                principal_paid_minor, is_write_off, payment_date
             )
             VALUES (?, ?, ?, ?, ?, ?)",
            params![
                debt_id,
                record_id,
                payment.operation_type,
                payment.principal_paid_minor,
                payment.is_write_off,
                payment.payment_date
            ],
        )
        .map_err(sqlite_err)?;
        Ok(conn.last_insert_rowid())
    }
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
            .query_map([], |row| {
                Ok((row.get::<_, i64>(0)?, row.get::<_, String>(1)?))
            })
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

pub fn distribution_item_rows(
    db_path: &str,
    active_only: bool,
) -> StorageResult<Vec<DistributionItemPayload>> {
    with_cached_read_connection(db_path, |conn| {
        let where_clause = if active_only {
            "WHERE is_active = 1"
        } else {
            ""
        };
        let mut stmt = conn
            .prepare(&format!(
                "SELECT id, name, group_name, sort_order, pct, pct_minor, is_active
                 FROM distribution_items
                 {where_clause}
                 ORDER BY sort_order ASC, name COLLATE NOCASE ASC, id ASC"
            ))
            .map_err(sqlite_err)?;
        let rows = stmt
            .query_map([], |row| {
                Ok(DistributionItemPayload {
                    id: row.get(0)?,
                    name: row.get(1)?,
                    group_name: row.get(2)?,
                    sort_order: row.get(3)?,
                    pct: row.get(4)?,
                    pct_minor: row.get(5)?,
                    is_active: row.get(6)?,
                    amount_base: 0.0,
                    amount_minor: 0,
                    subitems: Vec::new(),
                })
            })
            .map_err(sqlite_err)?;
        rows.collect::<Result<Vec<_>, _>>().map_err(sqlite_err)
    })
}

pub fn distribution_subitem_rows(
    db_path: &str,
    item_id: i64,
    active_only: bool,
) -> StorageResult<Vec<DistributionSubitemPayload>> {
    with_cached_read_connection(db_path, |conn| {
        if !distribution_item_exists(conn, item_id)? {
            return Err(format!("Distribution item not found: {item_id}"));
        }
        let active_clause = if active_only { "AND is_active = 1" } else { "" };
        let mut stmt = conn
            .prepare(&format!(
                "SELECT id, item_id, name, sort_order, pct, pct_minor, is_active
                 FROM distribution_subitems
                 WHERE item_id = ? {active_clause}
                 ORDER BY sort_order ASC, name COLLATE NOCASE ASC, id ASC"
            ))
            .map_err(sqlite_err)?;
        let rows = stmt
            .query_map([item_id], |row| {
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
        rows.collect::<Result<Vec<_>, _>>().map_err(sqlite_err)
    })
}

pub fn distribution_create_item(
    db_path: &str,
    name: &str,
    group_name: &str,
    sort_order: i64,
    pct: f64,
    pct_minor: i64,
) -> StorageResult<DistributionItemPayload> {
    let mut conn = open_write_connection(db_path)?;
    let tx = conn.transaction().map_err(sqlite_err)?;
    tx.execute(
        "INSERT INTO distribution_items (name, group_name, sort_order, pct, pct_minor)
         VALUES (?, ?, ?, ?, ?)",
        params![name, group_name, sort_order, pct, pct_minor],
    )
    .map_err(|err| map_distribution_integrity_error(err, name, None))?;
    let item_id = tx.last_insert_rowid();
    tx.commit().map_err(sqlite_err)?;
    storage_clear_read_connection_cache();
    let conn = open_write_connection(db_path)?;
    distribution_item_from_conn(&conn, item_id)
}

pub fn distribution_update_item_pct(
    db_path: &str,
    item_id: i64,
    pct: f64,
    pct_minor: i64,
) -> StorageResult<DistributionItemPayload> {
    let mut conn = open_write_connection(db_path)?;
    if !distribution_item_exists(&conn, item_id)? {
        return Err(format!("Distribution item not found: {item_id}"));
    }
    let tx = conn.transaction().map_err(sqlite_err)?;
    tx.execute(
        "UPDATE distribution_items SET pct = ?, pct_minor = ? WHERE id = ?",
        params![pct, pct_minor, item_id],
    )
    .map_err(sqlite_err)?;
    tx.commit().map_err(sqlite_err)?;
    storage_clear_read_connection_cache();
    let conn = open_write_connection(db_path)?;
    distribution_item_from_conn(&conn, item_id)
}

pub fn distribution_update_item_name(
    db_path: &str,
    item_id: i64,
    name: &str,
) -> StorageResult<DistributionItemPayload> {
    let mut conn = open_write_connection(db_path)?;
    if !distribution_item_exists(&conn, item_id)? {
        return Err(format!("Distribution item not found: {item_id}"));
    }
    let tx = conn.transaction().map_err(sqlite_err)?;
    tx.execute(
        "UPDATE distribution_items SET name = ? WHERE id = ?",
        params![name, item_id],
    )
    .map_err(|err| map_distribution_integrity_error(err, name, None))?;
    tx.commit().map_err(sqlite_err)?;
    storage_clear_read_connection_cache();
    let conn = open_write_connection(db_path)?;
    distribution_item_from_conn(&conn, item_id)
}

pub fn distribution_update_item_order(
    db_path: &str,
    item_id: i64,
    sort_order: i64,
) -> StorageResult<()> {
    let mut conn = open_write_connection(db_path)?;
    if !distribution_item_exists(&conn, item_id)? {
        return Err(format!("Distribution item not found: {item_id}"));
    }
    let tx = conn.transaction().map_err(sqlite_err)?;
    tx.execute(
        "UPDATE distribution_items SET sort_order = ? WHERE id = ?",
        params![sort_order, item_id],
    )
    .map_err(sqlite_err)?;
    tx.commit().map_err(sqlite_err)?;
    storage_clear_read_connection_cache();
    Ok(())
}

pub fn distribution_delete_item(db_path: &str, item_id: i64) -> StorageResult<()> {
    let mut conn = open_write_connection(db_path)?;
    if !distribution_item_exists(&conn, item_id)? {
        return Err(format!("Distribution item not found: {item_id}"));
    }
    let tx = conn.transaction().map_err(sqlite_err)?;
    tx.execute("DELETE FROM distribution_items WHERE id = ?", [item_id])
        .map_err(sqlite_err)?;
    tx.commit().map_err(sqlite_err)?;
    storage_clear_read_connection_cache();
    Ok(())
}

pub fn distribution_create_subitem(
    db_path: &str,
    item_id: i64,
    name: &str,
    sort_order: i64,
    pct: f64,
    pct_minor: i64,
) -> StorageResult<DistributionSubitemPayload> {
    let mut conn = open_write_connection(db_path)?;
    if !distribution_item_exists(&conn, item_id)? {
        return Err(format!("Distribution item not found: {item_id}"));
    }
    let tx = conn.transaction().map_err(sqlite_err)?;
    tx.execute(
        "INSERT INTO distribution_subitems (item_id, name, sort_order, pct, pct_minor)
         VALUES (?, ?, ?, ?, ?)",
        params![item_id, name, sort_order, pct, pct_minor],
    )
    .map_err(|err| map_distribution_integrity_error(err, name, Some(item_id)))?;
    let subitem_id = tx.last_insert_rowid();
    tx.commit().map_err(sqlite_err)?;
    storage_clear_read_connection_cache();
    let conn = open_write_connection(db_path)?;
    distribution_subitem_from_conn(&conn, subitem_id)
}

pub fn distribution_update_subitem_pct(
    db_path: &str,
    subitem_id: i64,
    pct: f64,
    pct_minor: i64,
) -> StorageResult<DistributionSubitemPayload> {
    let mut conn = open_write_connection(db_path)?;
    distribution_subitem_from_conn(&conn, subitem_id)?;
    let tx = conn.transaction().map_err(sqlite_err)?;
    tx.execute(
        "UPDATE distribution_subitems SET pct = ?, pct_minor = ? WHERE id = ?",
        params![pct, pct_minor, subitem_id],
    )
    .map_err(sqlite_err)?;
    tx.commit().map_err(sqlite_err)?;
    storage_clear_read_connection_cache();
    let conn = open_write_connection(db_path)?;
    distribution_subitem_from_conn(&conn, subitem_id)
}

pub fn distribution_update_subitem_name(
    db_path: &str,
    subitem_id: i64,
    name: &str,
) -> StorageResult<DistributionSubitemPayload> {
    let mut conn = open_write_connection(db_path)?;
    let existing = distribution_subitem_from_conn(&conn, subitem_id)?;
    let tx = conn.transaction().map_err(sqlite_err)?;
    tx.execute(
        "UPDATE distribution_subitems SET name = ? WHERE id = ?",
        params![name, subitem_id],
    )
    .map_err(|err| map_distribution_integrity_error(err, name, Some(existing.item_id)))?;
    tx.commit().map_err(sqlite_err)?;
    storage_clear_read_connection_cache();
    let conn = open_write_connection(db_path)?;
    distribution_subitem_from_conn(&conn, subitem_id)
}

pub fn distribution_update_subitem_order(
    db_path: &str,
    subitem_id: i64,
    sort_order: i64,
) -> StorageResult<()> {
    let mut conn = open_write_connection(db_path)?;
    distribution_subitem_from_conn(&conn, subitem_id)?;
    let tx = conn.transaction().map_err(sqlite_err)?;
    tx.execute(
        "UPDATE distribution_subitems SET sort_order = ? WHERE id = ?",
        params![sort_order, subitem_id],
    )
    .map_err(sqlite_err)?;
    tx.commit().map_err(sqlite_err)?;
    storage_clear_read_connection_cache();
    Ok(())
}

pub fn distribution_delete_subitem(db_path: &str, subitem_id: i64) -> StorageResult<()> {
    let mut conn = open_write_connection(db_path)?;
    distribution_subitem_from_conn(&conn, subitem_id)?;
    let tx = conn.transaction().map_err(sqlite_err)?;
    tx.execute(
        "DELETE FROM distribution_subitems WHERE id = ?",
        [subitem_id],
    )
    .map_err(sqlite_err)?;
    tx.commit().map_err(sqlite_err)?;
    storage_clear_read_connection_cache();
    Ok(())
}

pub fn distribution_replace_structure(
    db_path: &str,
    items: &[DistributionItemPayload],
    subitems: &[DistributionSubitemPayload],
) -> StorageResult<()> {
    let mut conn = open_write_connection(db_path)?;
    let tx = conn.transaction().map_err(sqlite_err)?;
    tx.execute("DELETE FROM distribution_subitems", [])
        .map_err(sqlite_err)?;
    tx.execute("DELETE FROM distribution_items", [])
        .map_err(sqlite_err)?;

    let mut sorted_items = items.to_vec();
    sorted_items.sort_by(|left, right| {
        left.sort_order
            .cmp(&right.sort_order)
            .then_with(|| left.name.to_lowercase().cmp(&right.name.to_lowercase()))
            .then_with(|| left.id.cmp(&right.id))
    });
    for item in &sorted_items {
        tx.execute(
            "INSERT INTO distribution_items (
                id, name, group_name, sort_order, pct, pct_minor, is_active
             )
             VALUES (?, ?, ?, ?, ?, ?, ?)",
            params![
                item.id,
                item.name,
                item.group_name,
                item.sort_order,
                item.pct,
                item.pct_minor,
                item.is_active
            ],
        )
        .map_err(|err| map_distribution_integrity_error(err, &item.name, None))?;
    }

    let mut sorted_subitems = subitems.to_vec();
    sorted_subitems.sort_by(|left, right| {
        left.sort_order
            .cmp(&right.sort_order)
            .then_with(|| left.name.to_lowercase().cmp(&right.name.to_lowercase()))
            .then_with(|| left.id.cmp(&right.id))
    });
    for subitem in &sorted_subitems {
        tx.execute(
            "INSERT INTO distribution_subitems (
                id, item_id, name, sort_order, pct, pct_minor, is_active
             )
             VALUES (?, ?, ?, ?, ?, ?, ?)",
            params![
                subitem.id,
                subitem.item_id,
                subitem.name,
                subitem.sort_order,
                subitem.pct,
                subitem.pct_minor,
                subitem.is_active
            ],
        )
        .map_err(|err| {
            map_distribution_integrity_error(err, &subitem.name, Some(subitem.item_id))
        })?;
    }

    tx.execute(
        "DELETE FROM sqlite_sequence WHERE name IN ('distribution_items', 'distribution_subitems')",
        [],
    )
    .map_err(sqlite_err)?;
    if let Some(max_id) = items.iter().map(|item| item.id).max() {
        tx.execute(
            "INSERT INTO sqlite_sequence(name, seq) VALUES('distribution_items', ?)",
            [max_id],
        )
        .map_err(sqlite_err)?;
    }
    if let Some(max_id) = subitems.iter().map(|subitem| subitem.id).max() {
        tx.execute(
            "INSERT INTO sqlite_sequence(name, seq) VALUES('distribution_subitems', ?)",
            [max_id],
        )
        .map_err(sqlite_err)?;
    }
    tx.commit().map_err(sqlite_err)?;
    storage_clear_read_connection_cache();
    Ok(())
}

pub fn distribution_is_month_fixed(db_path: &str, month: &str) -> StorageResult<bool> {
    with_cached_read_connection(db_path, |conn| {
        conn.query_row(
            "SELECT 1 FROM distribution_snapshots WHERE month = ?",
            [month],
            |_| Ok(()),
        )
        .optional()
        .map_err(sqlite_err)
        .map(|row| row.is_some())
    })
}

pub fn distribution_is_month_auto_fixed(db_path: &str, month: &str) -> StorageResult<bool> {
    with_cached_read_connection(db_path, |conn| {
        Ok(conn
            .query_row(
                "SELECT auto_fixed FROM distribution_snapshots WHERE month = ?",
                [month],
                |row| row.get::<_, bool>(0),
            )
            .optional()
            .map_err(sqlite_err)?
            .unwrap_or(false))
    })
}

pub fn distribution_write_frozen_row(
    db_path: &str,
    row: &FrozenDistributionPayload,
) -> StorageResult<()> {
    let mut conn = open_write_connection(db_path)?;
    let tx = conn.transaction().map_err(sqlite_err)?;
    tx.execute(
        "INSERT OR REPLACE INTO distribution_snapshots (month, is_negative, auto_fixed)
         VALUES (?, ?, ?)",
        params![row.month, row.is_negative, row.auto_fixed],
    )
    .map_err(sqlite_err)?;
    tx.execute(
        "DELETE FROM distribution_snapshot_values WHERE snapshot_month = ?",
        [row.month.as_str()],
    )
    .map_err(sqlite_err)?;
    for (index, column_id) in row.column_order.iter().enumerate() {
        let label = row
            .headings_by_column
            .iter()
            .find(|(key, _)| key == column_id)
            .map(|(_, value)| value.as_str())
            .unwrap_or(column_id);
        let value = row
            .values_by_column
            .iter()
            .find(|(key, _)| key == column_id)
            .map(|(_, value)| value.as_str())
            .unwrap_or("-");
        tx.execute(
            "INSERT INTO distribution_snapshot_values (
                snapshot_month, column_key, column_label, column_order, value_text
             )
             VALUES (?, ?, ?, ?, ?)",
            params![row.month, column_id, label, index as i64, value],
        )
        .map_err(sqlite_err)?;
    }
    tx.commit().map_err(sqlite_err)?;
    storage_clear_read_connection_cache();
    Ok(())
}

pub fn distribution_unfreeze_month(db_path: &str, month: &str) -> StorageResult<()> {
    let mut conn = open_write_connection(db_path)?;
    let auto_fixed = conn
        .query_row(
            "SELECT auto_fixed FROM distribution_snapshots WHERE month = ?",
            [month],
            |row| row.get::<_, bool>(0),
        )
        .optional()
        .map_err(sqlite_err)?
        .unwrap_or(false);
    if auto_fixed {
        return Err(format!("Month {month} is auto-fixed and cannot be unfixed"));
    }
    let tx = conn.transaction().map_err(sqlite_err)?;
    tx.execute(
        "DELETE FROM distribution_snapshots WHERE month = ?",
        [month],
    )
    .map_err(sqlite_err)?;
    tx.commit().map_err(sqlite_err)?;
    storage_clear_read_connection_cache();
    Ok(())
}

pub fn distribution_frozen_rows(
    db_path: &str,
    start_month: Option<&str>,
    end_month: Option<&str>,
) -> StorageResult<Vec<FrozenDistributionPayload>> {
    with_cached_read_connection(db_path, |conn| {
        let mut clauses = Vec::new();
        if start_month.is_some() {
            clauses.push("month >= ?");
        }
        if end_month.is_some() {
            clauses.push("month <= ?");
        }
        let where_clause = if clauses.is_empty() {
            String::new()
        } else {
            format!("WHERE {}", clauses.join(" AND "))
        };
        let mut params_vec: Vec<String> = Vec::new();
        if let Some(start) = start_month {
            params_vec.push(start.to_owned());
        }
        if let Some(end) = end_month {
            params_vec.push(end.to_owned());
        }
        let mut stmt = conn
            .prepare(&format!(
                "SELECT month, is_negative, auto_fixed
                 FROM distribution_snapshots
                 {where_clause}
                 ORDER BY month ASC"
            ))
            .map_err(sqlite_err)?;
        let snapshot_rows = stmt
            .query_map(params_from_iter(params_vec.iter()), |row| {
                Ok((
                    row.get::<_, String>(0)?,
                    row.get::<_, bool>(1)?,
                    row.get::<_, bool>(2)?,
                ))
            })
            .map_err(sqlite_err)?
            .collect::<Result<Vec<_>, _>>()
            .map_err(sqlite_err)?;

        let mut rows = Vec::new();
        for (month, is_negative, auto_fixed) in snapshot_rows {
            let mut values_stmt = conn
                .prepare(
                    "SELECT column_key, column_label, value_text
                     FROM distribution_snapshot_values
                     WHERE snapshot_month = ?
                     ORDER BY column_order ASC",
                )
                .map_err(sqlite_err)?;
            let values = values_stmt
                .query_map([month.as_str()], |row| {
                    Ok((
                        row.get::<_, String>(0)?,
                        row.get::<_, String>(1)?,
                        row.get::<_, String>(2)?,
                    ))
                })
                .map_err(sqlite_err)?
                .collect::<Result<Vec<_>, _>>()
                .map_err(sqlite_err)?;
            rows.push(FrozenDistributionPayload {
                month,
                column_order: values.iter().map(|(key, _, _)| key.clone()).collect(),
                headings_by_column: values
                    .iter()
                    .map(|(key, label, _)| (key.clone(), label.clone()))
                    .collect(),
                values_by_column: values
                    .into_iter()
                    .map(|(key, _, value)| (key, value))
                    .collect(),
                is_negative,
                auto_fixed,
            });
        }
        Ok(rows)
    })
}

pub fn distribution_replace_frozen_rows(
    db_path: &str,
    rows: &[FrozenDistributionPayload],
) -> StorageResult<()> {
    let mut conn = open_write_connection(db_path)?;
    let tx = conn.transaction().map_err(sqlite_err)?;
    tx.execute("DELETE FROM distribution_snapshot_values", [])
        .map_err(sqlite_err)?;
    tx.execute("DELETE FROM distribution_snapshots", [])
        .map_err(sqlite_err)?;
    let mut sorted_rows = rows.to_vec();
    sorted_rows.sort_by(|left, right| left.month.cmp(&right.month));
    for row in &sorted_rows {
        tx.execute(
            "INSERT INTO distribution_snapshots (month, is_negative, auto_fixed)
             VALUES (?, ?, ?)",
            params![row.month, row.is_negative, row.auto_fixed],
        )
        .map_err(sqlite_err)?;
        for (index, column_id) in row.column_order.iter().enumerate() {
            let label = row
                .headings_by_column
                .iter()
                .find(|(key, _)| key == column_id)
                .map(|(_, value)| value.as_str())
                .unwrap_or(column_id);
            let value = row
                .values_by_column
                .iter()
                .find(|(key, _)| key == column_id)
                .map(|(_, value)| value.as_str())
                .unwrap_or("-");
            tx.execute(
                "INSERT INTO distribution_snapshot_values (
                    snapshot_month, column_key, column_label, column_order, value_text
                 )
                 VALUES (?, ?, ?, ?, ?)",
                params![row.month, column_id, label, index as i64, value],
            )
            .map_err(sqlite_err)?;
        }
    }
    tx.commit().map_err(sqlite_err)?;
    storage_clear_read_connection_cache();
    Ok(())
}

pub fn budget_rows(db_path: &str) -> StorageResult<Vec<BudgetPayload>> {
    with_cached_read_connection(db_path, |conn| {
        let mut stmt = conn
            .prepare(
                "SELECT id, category, start_date, end_date,
                        limit_base, limit_base_minor, include_mandatory, scope_type, scope_value
                 FROM budgets
                 ORDER BY start_date DESC, category ASC, id DESC",
            )
            .map_err(sqlite_err)?;
        let rows = stmt
            .query_map([], |row| {
                Ok(BudgetPayload {
                    id: row.get(0)?,
                    category: row.get(1)?,
                    start_date: row.get(2)?,
                    end_date: row.get(3)?,
                    limit_base: row.get(4)?,
                    limit_base_minor: row.get(5)?,
                    include_mandatory: row.get(6)?,
                    scope_type: row.get(7)?,
                    scope_value: row.get(8)?,
                })
            })
            .map_err(sqlite_err)?;
        rows.collect::<Result<Vec<_>, _>>().map_err(sqlite_err)
    })
}

pub fn budget_create(
    db_path: &str,
    payload: BudgetCreatePayload<'_>,
) -> StorageResult<BudgetPayload> {
    let mut conn = open_write_connection(db_path)?;
    let tx = conn.transaction().map_err(sqlite_err)?;
    tx.execute(
        "INSERT INTO budgets (
            category, scope_type, scope_value,
            start_date, end_date, limit_base, limit_base_minor, include_mandatory
         )
         VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        params![
            payload.category,
            payload.scope_type,
            payload.scope_value,
            payload.start_date,
            payload.end_date,
            payload.limit_base,
            payload.limit_base_minor,
            payload.include_mandatory
        ],
    )
    .map_err(sqlite_err)?;
    let budget_id = tx.last_insert_rowid();
    tx.commit().map_err(sqlite_err)?;
    storage_clear_read_connection_cache();
    let conn = open_write_connection(db_path)?;
    budget_from_conn(&conn, budget_id)
}

pub fn budget_delete(db_path: &str, budget_id: i64) -> StorageResult<()> {
    let mut conn = open_write_connection(db_path)?;
    if !budget_exists(&conn, budget_id)? {
        return Err(format!("Budget not found: {budget_id}"));
    }
    let tx = conn.transaction().map_err(sqlite_err)?;
    tx.execute("DELETE FROM budgets WHERE id = ?", [budget_id])
        .map_err(sqlite_err)?;
    tx.commit().map_err(sqlite_err)?;
    storage_clear_read_connection_cache();
    Ok(())
}

pub fn budget_update_limit(
    db_path: &str,
    budget_id: i64,
    limit_base: f64,
    limit_base_minor: i64,
) -> StorageResult<BudgetPayload> {
    let mut conn = open_write_connection(db_path)?;
    if !budget_exists(&conn, budget_id)? {
        return Err(format!("Budget not found: {budget_id}"));
    }
    let tx = conn.transaction().map_err(sqlite_err)?;
    tx.execute(
        "UPDATE budgets SET limit_base = ?, limit_base_minor = ? WHERE id = ?",
        params![limit_base, limit_base_minor, budget_id],
    )
    .map_err(sqlite_err)?;
    tx.commit().map_err(sqlite_err)?;
    storage_clear_read_connection_cache();
    let conn = open_write_connection(db_path)?;
    budget_from_conn(&conn, budget_id)
}

pub fn budget_replace_rows(db_path: &str, budgets: &[BudgetPayload]) -> StorageResult<()> {
    let mut conn = open_write_connection(db_path)?;
    let tx = conn.transaction().map_err(sqlite_err)?;
    tx.execute("DELETE FROM budgets", []).map_err(sqlite_err)?;
    let mut sorted = budgets.to_vec();
    sorted.sort_by_key(|budget| budget.id);
    for budget in &sorted {
        tx.execute(
            "INSERT INTO budgets (
                id, category, start_date, end_date,
                limit_base, limit_base_minor, include_mandatory, scope_type, scope_value
             )
             VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            params![
                budget.id,
                budget.category,
                budget.start_date,
                budget.end_date,
                budget.limit_base,
                budget.limit_base_minor,
                budget.include_mandatory,
                budget.scope_type,
                budget.scope_value,
            ],
        )
        .map_err(sqlite_err)?;
    }
    tx.execute("DELETE FROM sqlite_sequence WHERE name = ?", ["budgets"])
        .map_err(sqlite_err)?;
    if let Some(max_id) = budgets.iter().map(|budget| budget.id).max() {
        tx.execute(
            "INSERT INTO sqlite_sequence(name, seq) VALUES('budgets', ?)",
            [max_id],
        )
        .map_err(sqlite_err)?;
    }
    tx.commit().map_err(sqlite_err)?;
    storage_clear_read_connection_cache();
    Ok(())
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
        .map(
            |(id, scope_type, scope_value, start_date, end_date, include_mandatory)| {
                budget_spent_minor(
                    db_path,
                    scope_type,
                    scope_value,
                    start_date,
                    end_date,
                    *include_mandatory,
                )
                .map(|spent| (*id, spent))
            },
        )
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
        let exclude_clause = if exclude_id.is_some() {
            "AND id != ?"
        } else {
            ""
        };
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
            conn.query_row(
                &sql,
                (scope_type, scope_value, end_date, start_date),
                |_| Ok(()),
            )
            .optional()
        }
        .map_err(sqlite_err)?
        .is_some();
        Ok(exists)
    })
}

pub fn debt_rows(db_path: &str) -> StorageResult<Vec<DebtPayload>> {
    with_cached_read_connection(db_path, |conn| {
        let mut stmt = conn
            .prepare(
                "SELECT id, contact_name, kind, total_amount_minor, remaining_amount_minor,
                        currency, interest_rate, status, created_at, closed_at
                 FROM debts
                 ORDER BY id",
            )
            .map_err(sqlite_err)?;
        let rows = stmt
            .query_map([], |row| {
                Ok(DebtPayload {
                    id: row.get(0)?,
                    contact_name: row.get(1)?,
                    kind: row.get(2)?,
                    total_amount_minor: row.get(3)?,
                    remaining_amount_minor: row.get(4)?,
                    currency: row.get(5)?,
                    interest_rate: row.get(6)?,
                    status: row.get(7)?,
                    created_at: row.get(8)?,
                    closed_at: row.get(9)?,
                })
            })
            .map_err(sqlite_err)?;
        rows.collect::<Result<Vec<_>, _>>().map_err(sqlite_err)
    })
}

pub fn debt_payment_rows(
    db_path: &str,
    debt_id: Option<i64>,
) -> StorageResult<Vec<DebtPaymentPayload>> {
    with_cached_read_connection(db_path, |conn| {
        let sql = if debt_id.is_some() {
            "SELECT id, debt_id, record_id, operation_type, principal_paid_minor,
                    is_write_off, payment_date
             FROM debt_payments
             WHERE debt_id = ?
             ORDER BY id"
        } else {
            "SELECT id, debt_id, record_id, operation_type, principal_paid_minor,
                    is_write_off, payment_date
             FROM debt_payments
             ORDER BY id"
        };
        let mut stmt = conn.prepare(sql).map_err(sqlite_err)?;
        let rows = if let Some(id) = debt_id {
            stmt.query_map([id], |row| {
                Ok(DebtPaymentPayload {
                    id: row.get(0)?,
                    debt_id: row.get(1)?,
                    record_id: row.get(2)?,
                    operation_type: row.get(3)?,
                    principal_paid_minor: row.get(4)?,
                    is_write_off: row.get(5)?,
                    payment_date: row.get(6)?,
                })
            })
            .map_err(sqlite_err)?
            .collect::<Result<Vec<_>, _>>()
        } else {
            stmt.query_map([], |row| {
                Ok(DebtPaymentPayload {
                    id: row.get(0)?,
                    debt_id: row.get(1)?,
                    record_id: row.get(2)?,
                    operation_type: row.get(3)?,
                    principal_paid_minor: row.get(4)?,
                    is_write_off: row.get(5)?,
                    payment_date: row.get(6)?,
                })
            })
            .map_err(sqlite_err)?
            .collect::<Result<Vec<_>, _>>()
        };
        rows.map_err(sqlite_err)
    })
}

pub fn debt_create_obligation(
    db_path: &str,
    debt: &DebtPayload,
    open_record: &DebtRecordPayload,
) -> StorageResult<DebtPayload> {
    let mut conn = open_write_connection(db_path)?;
    let tx = conn.transaction().map_err(sqlite_err)?;
    let debt_id = insert_debt_row(&tx, debt, false)?;
    insert_debt_record_row(&tx, open_record, debt_id)?;
    tx.commit().map_err(sqlite_err)?;
    storage_clear_read_connection_cache();
    let conn = open_write_connection(db_path)?;
    debt_from_conn(&conn, debt_id)
}

pub fn debt_delete(db_path: &str, debt_id: i64) -> StorageResult<()> {
    let mut conn = open_write_connection(db_path)?;
    debt_from_conn(&conn, debt_id)?;
    let tx = conn.transaction().map_err(sqlite_err)?;
    tx.execute(
        "UPDATE records SET related_debt_id = NULL WHERE related_debt_id = ?",
        [debt_id],
    )
    .map_err(sqlite_err)?;
    tx.execute("DELETE FROM debt_payments WHERE debt_id = ?", [debt_id])
        .map_err(sqlite_err)?;
    tx.execute("DELETE FROM debts WHERE id = ?", [debt_id])
        .map_err(sqlite_err)?;
    tx.commit().map_err(sqlite_err)?;
    storage_clear_read_connection_cache();
    Ok(())
}

pub fn debt_register_payment(
    db_path: &str,
    debt_id: i64,
    payment: &DebtPaymentPayload,
    payment_record: Option<&DebtRecordPayload>,
) -> StorageResult<DebtPaymentPayload> {
    let mut conn = open_write_connection(db_path)?;
    let debt = debt_from_conn(&conn, debt_id)?;
    let tx = conn.transaction().map_err(sqlite_err)?;
    let record_id = if let Some(record) = payment_record {
        Some(insert_debt_record_row(&tx, record, debt_id)?)
    } else {
        None
    };
    let payment_id = insert_debt_payment_row(&tx, payment, debt_id, record_id, false)?;
    let remaining_amount_minor = (debt.remaining_amount_minor - payment.principal_paid_minor).max(0);
    let is_closed = remaining_amount_minor == 0;
    tx.execute(
        "UPDATE debts
         SET remaining_amount_minor = ?, status = ?, closed_at = ?
         WHERE id = ?",
        params![
            remaining_amount_minor,
            if is_closed { "closed" } else { "open" },
            if is_closed {
                Some(payment.payment_date.as_str())
            } else {
                None
            },
            debt_id
        ],
    )
    .map_err(sqlite_err)?;
    tx.commit().map_err(sqlite_err)?;
    storage_clear_read_connection_cache();
    let conn = open_write_connection(db_path)?;
    debt_payment_from_conn(&conn, payment_id)
}

pub fn debt_delete_payment(
    db_path: &str,
    payment_id: i64,
    delete_linked_record: bool,
) -> StorageResult<DebtPayload> {
    let mut conn = open_write_connection(db_path)?;
    let payment = debt_payment_from_conn(&conn, payment_id)?;
    let debt = debt_from_conn(&conn, payment.debt_id)?;
    let tx = conn.transaction().map_err(sqlite_err)?;
    if delete_linked_record && let Some(record_id) = payment.record_id {
        tx.execute("DELETE FROM records WHERE id = ?", [record_id])
            .map_err(sqlite_err)?;
    }
    tx.execute("DELETE FROM debt_payments WHERE id = ?", [payment_id])
        .map_err(sqlite_err)?;
    let restored_remaining = (debt.remaining_amount_minor + payment.principal_paid_minor)
        .min(debt.total_amount_minor);
    tx.execute(
        "UPDATE debts
         SET remaining_amount_minor = ?, status = ?, closed_at = ?
         WHERE id = ?",
        params![
            restored_remaining,
            if restored_remaining > 0 {
                "open"
            } else {
                debt.status.as_str()
            },
            if restored_remaining > 0 {
                None::<&str>
            } else {
                debt.closed_at.as_deref()
            },
            payment.debt_id
        ],
    )
    .map_err(sqlite_err)?;
    tx.commit().map_err(sqlite_err)?;
    storage_clear_read_connection_cache();
    let conn = open_write_connection(db_path)?;
    debt_from_conn(&conn, payment.debt_id)
}

pub fn debt_replace_rows(
    db_path: &str,
    debts: &[DebtPayload],
    payments: &[DebtPaymentPayload],
) -> StorageResult<()> {
    let mut conn = open_write_connection(db_path)?;
    let tx = conn.transaction().map_err(sqlite_err)?;
    tx.execute("DELETE FROM debt_payments", [])
        .map_err(sqlite_err)?;
    tx.execute("DELETE FROM debts", []).map_err(sqlite_err)?;
    tx.execute("DELETE FROM sqlite_sequence WHERE name IN ('debts', 'debt_payments')", [])
        .map_err(sqlite_err)?;

    let mut sorted_debts = debts.to_vec();
    sorted_debts.sort_by_key(|debt| debt.id);
    for debt in &sorted_debts {
        insert_debt_row(&tx, debt, true)?;
    }

    let mut sorted_payments = payments.to_vec();
    sorted_payments.sort_by_key(|payment| payment.id);
    for payment in &sorted_payments {
        if !sorted_debts.iter().any(|debt| debt.id == payment.debt_id) {
            return Err(format!(
                "Debt payment #{} references missing debt {}",
                payment.id, payment.debt_id
            ));
        }
        if let Some(record_id) = payment.record_id {
            let exists = tx
                .query_row("SELECT 1 FROM records WHERE id = ?", [record_id], |_| Ok(()))
                .optional()
                .map_err(sqlite_err)?
                .is_some();
            if !exists {
                return Err(format!(
                    "Debt payment #{} references missing record {}",
                    payment.id, record_id
                ));
            }
        }
        insert_debt_payment_row(&tx, payment, payment.debt_id, payment.record_id, true)?;
    }

    if let Some(max_id) = debts.iter().map(|debt| debt.id).max() {
        tx.execute(
            "INSERT INTO sqlite_sequence(name, seq) VALUES('debts', ?)",
            [max_id],
        )
        .map_err(sqlite_err)?;
    }
    if let Some(max_id) = payments.iter().map(|payment| payment.id).max() {
        tx.execute(
            "INSERT INTO sqlite_sequence(name, seq) VALUES('debt_payments', ?)",
            [max_id],
        )
        .map_err(sqlite_err)?;
    }
    tx.commit().map_err(sqlite_err)?;
    storage_clear_read_connection_cache();
    Ok(())
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
    use super::*;
    use std::fs;
    use std::time::{SystemTime, UNIX_EPOCH};

    #[test]
    fn apply_pct_rounds_half_up_for_positive_and_negative_values() {
        assert_eq!(apply_pct(101, 5000), 51);
        assert_eq!(apply_pct(-101, 5000), -51);
    }

    fn test_db_path(name: &str) -> String {
        let nanos = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .expect("clock")
            .as_nanos();
        std::env::temp_dir()
            .join(format!("ledgera_{name}_{nanos}.db"))
            .to_string_lossy()
            .into_owned()
    }

    fn init_distribution_schema(db_path: &str) {
        let conn = Connection::open(db_path).expect("open test db");
        conn.execute_batch(
            "
            CREATE TABLE budgets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT NOT NULL,
                scope_type TEXT NOT NULL DEFAULT 'category',
                scope_value TEXT NOT NULL DEFAULT '',
                start_date TEXT NOT NULL,
                end_date TEXT NOT NULL,
                limit_base REAL NOT NULL,
                limit_base_minor INTEGER NOT NULL DEFAULT 0,
                include_mandatory INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                type TEXT NOT NULL,
                date TEXT NOT NULL,
                wallet_id INTEGER NOT NULL,
                transfer_id INTEGER,
                related_debt_id INTEGER,
                amount_original REAL NOT NULL,
                amount_original_minor INTEGER,
                currency TEXT NOT NULL,
                rate_at_operation REAL NOT NULL,
                rate_at_operation_text TEXT NOT NULL,
                amount_base REAL NOT NULL,
                amount_base_minor INTEGER,
                category TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                period TEXT
            );
            CREATE TABLE debts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                contact_name TEXT NOT NULL,
                kind TEXT NOT NULL,
                total_amount_minor INTEGER NOT NULL,
                remaining_amount_minor INTEGER NOT NULL,
                currency TEXT NOT NULL,
                interest_rate REAL NOT NULL DEFAULT 0,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                closed_at TEXT
            );
            CREATE TABLE debt_payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                debt_id INTEGER NOT NULL,
                record_id INTEGER,
                operation_type TEXT NOT NULL,
                principal_paid_minor INTEGER NOT NULL,
                is_write_off INTEGER NOT NULL DEFAULT 0,
                payment_date TEXT NOT NULL
            );
            CREATE TABLE distribution_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                group_name TEXT NOT NULL DEFAULT '',
                sort_order INTEGER NOT NULL DEFAULT 0,
                pct REAL NOT NULL DEFAULT 0.0,
                pct_minor INTEGER NOT NULL DEFAULT 0,
                is_active INTEGER NOT NULL DEFAULT 1
            );
            CREATE TABLE distribution_subitems (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                item_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                sort_order INTEGER NOT NULL DEFAULT 0,
                pct REAL NOT NULL DEFAULT 0.0,
                pct_minor INTEGER NOT NULL DEFAULT 0,
                is_active INTEGER NOT NULL DEFAULT 1,
                FOREIGN KEY(item_id) REFERENCES distribution_items(id) ON DELETE CASCADE,
                UNIQUE(item_id, name)
            );
            CREATE TABLE distribution_snapshots (
                month TEXT PRIMARY KEY,
                is_negative INTEGER NOT NULL DEFAULT 0,
                auto_fixed INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE distribution_snapshot_values (
                snapshot_month TEXT NOT NULL,
                column_key TEXT NOT NULL,
                column_label TEXT NOT NULL,
                column_order INTEGER NOT NULL,
                value_text TEXT NOT NULL,
                PRIMARY KEY(snapshot_month, column_key),
                FOREIGN KEY(snapshot_month) REFERENCES distribution_snapshots(month) ON DELETE CASCADE
            );
            ",
        )
        .expect("schema");
    }

    fn test_debt(contact_name: &str, amount_minor: i64) -> DebtPayload {
        DebtPayload {
            id: 1,
            contact_name: contact_name.to_owned(),
            kind: "debt".to_owned(),
            total_amount_minor: amount_minor,
            remaining_amount_minor: amount_minor,
            currency: "KZT".to_owned(),
            interest_rate: 0.0,
            status: "open".to_owned(),
            created_at: "2026-03-01".to_owned(),
            closed_at: None,
        }
    }

    fn test_debt_record(record_type: &str, amount_minor: i64) -> DebtRecordPayload {
        DebtRecordPayload {
            record_type: record_type.to_owned(),
            date: "2026-03-01".to_owned(),
            wallet_id: 1,
            amount_original: minor_to_money_value(amount_minor),
            amount_original_minor: amount_minor,
            currency: "KZT".to_owned(),
            rate_at_operation: 1.0,
            rate_at_operation_text: "1.000000".to_owned(),
            amount_base: minor_to_money_value(amount_minor),
            amount_base_minor: amount_minor,
            category: "Debt".to_owned(),
            description: "Alice".to_owned(),
            period: None,
        }
    }

    fn test_payment(debt_id: i64, amount_minor: i64, write_off: bool) -> DebtPaymentPayload {
        DebtPaymentPayload {
            id: 1,
            debt_id,
            record_id: None,
            operation_type: if write_off {
                "debt_forgive"
            } else {
                "debt_repay"
            }
            .to_owned(),
            principal_paid_minor: amount_minor,
            is_write_off: write_off,
            payment_date: "2026-03-05".to_owned(),
        }
    }

    #[test]
    fn distribution_crud_and_replace_structure_preserve_sequences() {
        let db_path = test_db_path("distribution_crud");
        init_distribution_schema(&db_path);
        let item =
            distribution_create_item(&db_path, "Needs", "", 0, 100.0, 10000).expect("create item");
        assert_eq!(item.id, 1);
        let subitem = distribution_create_subitem(&db_path, item.id, "Rent", 0, 100.0, 10000)
            .expect("create subitem");
        assert_eq!(subitem.id, 1);
        assert!(
            distribution_create_item(&db_path, "Needs", "", 1, 0.0, 0)
                .expect_err("duplicate")
                .contains("already exists")
        );
        let updated = distribution_update_item_name(&db_path, item.id, "Core").expect("rename");
        assert_eq!(updated.name, "Core");
        distribution_delete_subitem(&db_path, subitem.id).expect("delete subitem");
        assert!(
            distribution_subitem_rows(&db_path, item.id, false)
                .expect("subitems")
                .is_empty()
        );

        let replacement_item = DistributionItemPayload {
            id: 7,
            name: "Replacement".to_owned(),
            group_name: "".to_owned(),
            sort_order: 0,
            pct: 100.0,
            pct_minor: 10000,
            is_active: true,
            amount_base: 0.0,
            amount_minor: 0,
            subitems: Vec::new(),
        };
        let replacement_subitem = DistributionSubitemPayload {
            id: 9,
            item_id: 7,
            name: "Child".to_owned(),
            sort_order: 0,
            pct: 100.0,
            pct_minor: 10000,
            is_active: true,
            amount_base: 0.0,
            amount_minor: 0,
        };
        distribution_replace_structure(&db_path, &[replacement_item], &[replacement_subitem])
            .expect("replace");
        let created = distribution_create_item(&db_path, "Next", "", 1, 0.0, 0)
            .expect("create after replace");
        assert_eq!(created.id, 8);
        fs::remove_file(db_path).ok();
    }

    #[test]
    fn distribution_frozen_rows_round_trip_and_auto_unfreeze_guard() {
        let db_path = test_db_path("distribution_snapshots");
        init_distribution_schema(&db_path);
        let row = FrozenDistributionPayload {
            month: "2026-03".to_owned(),
            column_order: vec!["month".to_owned(), "net_income".to_owned()],
            headings_by_column: vec![
                ("month".to_owned(), "Month".to_owned()),
                ("net_income".to_owned(), "Net income".to_owned()),
            ],
            values_by_column: vec![
                ("month".to_owned(), "2026-03".to_owned()),
                ("net_income".to_owned(), "1,000".to_owned()),
            ],
            is_negative: false,
            auto_fixed: true,
        };
        distribution_write_frozen_row(&db_path, &row).expect("write frozen");
        assert!(distribution_is_month_fixed(&db_path, "2026-03").expect("fixed"));
        assert!(distribution_is_month_auto_fixed(&db_path, "2026-03").expect("auto"));
        assert!(
            distribution_unfreeze_month(&db_path, "2026-03")
                .expect_err("auto-fixed")
                .contains("auto-fixed")
        );
        let rows = distribution_frozen_rows(&db_path, None, None).expect("frozen rows");
        assert_eq!(rows, vec![row]);
        fs::remove_file(db_path).ok();
    }

    #[test]
    fn budget_crud_and_replace_rows_preserve_sequences() {
        let db_path = test_db_path("budget_crud");
        init_distribution_schema(&db_path);
        let budget = budget_create(
            &db_path,
            BudgetCreatePayload {
                category: "Food",
                scope_type: "category",
                scope_value: "Food",
                start_date: "2026-03-01",
                end_date: "2026-03-31",
                limit_base: 1000.0,
                limit_base_minor: 100000,
                include_mandatory: true,
            },
        )
        .expect("create budget");
        assert_eq!(budget.id, 1);
        assert_eq!(budget.limit_base_minor, 100000);
        let updated =
            budget_update_limit(&db_path, budget.id, 1250.0, 125000).expect("update limit");
        assert_eq!(updated.limit_base, 1250.0);
        assert_eq!(updated.limit_base_minor, 125000);
        assert!(
            budget_update_limit(&db_path, 999, 1.0, 100)
                .expect_err("missing update")
                .contains("Budget not found: 999")
        );
        budget_delete(&db_path, budget.id).expect("delete");
        assert!(budget_rows(&db_path).expect("rows").is_empty());
        assert!(
            budget_delete(&db_path, budget.id)
                .expect_err("missing delete")
                .contains("Budget not found: 1")
        );

        let replacement = BudgetPayload {
            id: 7,
            category: "Travel".to_owned(),
            start_date: "2026-04-01".to_owned(),
            end_date: "2026-04-30".to_owned(),
            limit_base: 500.0,
            limit_base_minor: 50000,
            include_mandatory: false,
            scope_type: "category".to_owned(),
            scope_value: "Travel".to_owned(),
        };
        budget_replace_rows(&db_path, &[replacement]).expect("replace");
        let created = budget_create(
            &db_path,
            BudgetCreatePayload {
                category: "Next",
                scope_type: "category",
                scope_value: "Next",
                start_date: "2026-05-01",
                end_date: "2026-05-31",
                limit_base: 100.0,
                limit_base_minor: 10000,
                include_mandatory: false,
            },
        )
        .expect("create after replace");
        assert_eq!(created.id, 8);
        fs::remove_file(db_path).ok();
    }

    #[test]
    fn budget_overlap_helper_matches_period_contract() {
        let db_path = test_db_path("budget_overlap");
        init_distribution_schema(&db_path);
        budget_create(
            &db_path,
            BudgetCreatePayload {
                category: "Food",
                scope_type: "category",
                scope_value: "Food",
                start_date: "2026-03-01",
                end_date: "2026-03-31",
                limit_base: 1000.0,
                limit_base_minor: 100000,
                include_mandatory: false,
            },
        )
        .expect("create budget");
        assert!(
            budget_overlap_exists(
                &db_path,
                "category",
                "Food",
                "2026-03-15",
                "2026-04-15",
                None,
            )
            .expect("overlap")
        );
        assert!(
            !budget_overlap_exists(
                &db_path,
                "category",
                "Food",
                "2026-04-01",
                "2026-04-30",
                None,
            )
            .expect("adjacent")
        );
        fs::remove_file(db_path).ok();
    }

    #[test]
    fn debt_create_payment_delete_and_replace_preserve_contracts() {
        let db_path = test_db_path("debt_write");
        init_distribution_schema(&db_path);
        let debt = debt_create_obligation(
            &db_path,
            &test_debt("Alice", 50_000),
            &test_debt_record("income", 50_000),
        )
        .expect("create debt");
        assert_eq!(debt.id, 1);
        assert_eq!(debt.remaining_amount_minor, 50_000);

        let payment = debt_register_payment(
            &db_path,
            debt.id,
            &test_payment(debt.id, 20_000, false),
            Some(&test_debt_record("expense", 20_000)),
        )
        .expect("register payment");
        assert_eq!(payment.id, 1);
        assert!(payment.record_id.is_some());
        let conn = Connection::open(&db_path).expect("open");
        assert_eq!(
            debt_from_conn(&conn, debt.id)
                .expect("debt")
                .remaining_amount_minor,
            30_000
        );

        let reopened = debt_delete_payment(&db_path, payment.id, true).expect("delete payment");
        assert_eq!(reopened.remaining_amount_minor, 50_000);
        assert!(
            debt_payment_rows(&db_path, Some(debt.id))
                .expect("payments")
                .is_empty()
        );

        let write_off =
            debt_register_payment(&db_path, debt.id, &test_payment(debt.id, 50_000, true), None)
                .expect("write off");
        assert!(write_off.record_id.is_none());
        let conn = Connection::open(&db_path).expect("open");
        assert_eq!(
            debt_from_conn(&conn, debt.id).expect("debt").status,
            "closed"
        );

        let replacement_debt = DebtPayload {
            id: 7,
            contact_name: "Bob".to_owned(),
            kind: "loan".to_owned(),
            total_amount_minor: 10_000,
            remaining_amount_minor: 10_000,
            currency: "KZT".to_owned(),
            interest_rate: 0.0,
            status: "open".to_owned(),
            created_at: "2026-04-01".to_owned(),
            closed_at: None,
        };
        debt_replace_rows(&db_path, std::slice::from_ref(&replacement_debt), &[])
            .expect("replace debts");
        let next = debt_create_obligation(
            &db_path,
            &test_debt("Next", 10_000),
            &test_debt_record("income", 10_000),
        )
        .expect("create after replace");
        assert_eq!(next.id, 8);
        assert!(
            debt_delete(&db_path, 999)
                .expect_err("missing delete")
                .contains("Debt not found: 999")
        );
        fs::remove_file(db_path).ok();
    }
}
