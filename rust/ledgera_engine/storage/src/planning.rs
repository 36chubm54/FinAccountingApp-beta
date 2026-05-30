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
pub struct DebtRecalculatePayload {
    pub remaining_amount_minor: i64,
    pub status: String,
    pub closed_at: Option<String>,
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
}
