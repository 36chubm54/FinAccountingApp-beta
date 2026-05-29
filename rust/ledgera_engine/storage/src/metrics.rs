use ledgera_engine_core::minor_to_money_value;
use rusqlite::Connection;

use crate::{
    CategoryMetricRow, MonthlySummaryRow, StorageResult, TagCoverageRow, TagMetricRow,
    limit_clause, minor_amount_expr, round_money, sqlite_err, table_has_column,
    with_cached_read_connection,
};

fn sum_income_minor(conn: &Connection, start_date: &str, end_date: &str) -> StorageResult<i64> {
    let amount_expr = minor_amount_expr("amount_base");
    let sql = format!(
        "SELECT COALESCE(SUM({amount_expr}), 0) \
         FROM records \
         WHERE type = 'income' \
           AND transfer_id IS NULL \
           AND date >= ?1 AND date <= ?2"
    );
    conn.query_row(&sql, (start_date, end_date), |row| row.get::<_, i64>(0))
        .map_err(sqlite_err)
}

fn sum_expense_minor(conn: &Connection, start_date: &str, end_date: &str) -> StorageResult<i64> {
    let amount_expr = minor_amount_expr("amount_base");
    let sql = format!(
        "SELECT COALESCE(SUM({amount_expr}), 0) \
         FROM records \
         WHERE type IN ('expense', 'mandatory_expense') \
           AND transfer_id IS NULL \
           AND date >= ?1 AND date <= ?2"
    );
    conn.query_row(&sql, (start_date, end_date), |row| row.get::<_, i64>(0))
        .map_err(sqlite_err)
}

pub fn metrics_savings_rate(db_path: &str, start_date: &str, end_date: &str) -> StorageResult<f64> {
    with_cached_read_connection(db_path, |conn| {
        let income = minor_to_money_value(sum_income_minor(conn, start_date, end_date)?);
        let expenses = minor_to_money_value(sum_expense_minor(conn, start_date, end_date)?);
        if income <= 0.0 {
            return Ok(0.0);
        }
        Ok(round_money((income - expenses) / income * 100.0))
    })
}

pub fn metrics_burn_rate(
    db_path: &str,
    start_date: &str,
    end_date: &str,
    days: i64,
) -> StorageResult<f64> {
    if days <= 0 {
        return Ok(0.0);
    }
    with_cached_read_connection(db_path, |conn| {
        let expenses = minor_to_money_value(sum_expense_minor(conn, start_date, end_date)?);
        Ok(round_money(expenses / days as f64))
    })
}

fn category_metric_rows(
    db_path: &str,
    record_type_filter: &str,
    start_date: &str,
    end_date: &str,
    limit: Option<i64>,
) -> StorageResult<Vec<CategoryMetricRow>> {
    with_cached_read_connection(db_path, |conn| {
        let amount_expr = minor_amount_expr("amount_base");
        let sql = format!(
            "SELECT \
                category, \
                COALESCE(SUM({amount_expr}), 0) AS total_base, \
                COUNT(*) AS record_count \
             FROM records \
             WHERE {record_type_filter} \
               AND transfer_id IS NULL \
               AND date >= ?1 AND date <= ?2 \
             GROUP BY category \
             ORDER BY total_base DESC{}",
            limit_clause(limit)
        );
        let mut stmt = conn.prepare(&sql).map_err(sqlite_err)?;
        let rows = stmt
            .query_map((start_date, end_date), |row| {
                let total_minor: i64 = row.get(1)?;
                Ok(CategoryMetricRow {
                    category: row.get(0)?,
                    total_base: minor_to_money_value(total_minor),
                    record_count: row.get(2)?,
                })
            })
            .map_err(sqlite_err)?;

        let mut result = Vec::new();
        for row in rows {
            result.push(row.map_err(sqlite_err)?);
        }
        Ok(result)
    })
}

pub fn metrics_spending_by_category(
    db_path: &str,
    start_date: &str,
    end_date: &str,
    limit: Option<i64>,
) -> StorageResult<Vec<CategoryMetricRow>> {
    category_metric_rows(
        db_path,
        "type IN ('expense', 'mandatory_expense')",
        start_date,
        end_date,
        limit,
    )
}

pub fn metrics_income_by_category(
    db_path: &str,
    start_date: &str,
    end_date: &str,
    limit: Option<i64>,
) -> StorageResult<Vec<CategoryMetricRow>> {
    category_metric_rows(db_path, "type = 'income'", start_date, end_date, limit)
}

pub fn metrics_spending_by_tag(
    db_path: &str,
    start_date: &str,
    end_date: &str,
    limit: Option<i64>,
) -> StorageResult<Vec<TagMetricRow>> {
    with_cached_read_connection(db_path, |conn| {
        let amount_expr = minor_amount_expr("r.amount_base");
        let color_select = if table_has_column(conn, "tags", "color")? {
            "COALESCE(t.color, '')"
        } else {
            "''"
        };
        let color_group = if table_has_column(conn, "tags", "color")? {
            ", t.color"
        } else {
            ""
        };
        let sql = format!(
            "SELECT \
                t.name AS tag_name, \
                {color_select} AS color, \
                COALESCE(SUM({amount_expr}), 0) AS total_base, \
                COUNT(DISTINCT r.id) AS record_count \
             FROM records AS r \
             JOIN record_tags AS rt ON rt.record_id = r.id \
             JOIN tags AS t ON t.id = rt.tag_id \
             WHERE r.type IN ('expense', 'mandatory_expense') \
               AND r.transfer_id IS NULL \
               AND r.date >= ?1 AND r.date <= ?2 \
             GROUP BY t.id, t.name{color_group} \
             ORDER BY total_base DESC, t.name COLLATE NOCASE, t.name{}",
            limit_clause(limit)
        );
        let mut stmt = conn.prepare(&sql).map_err(sqlite_err)?;
        let rows = stmt
            .query_map((start_date, end_date), |row| {
                let total_minor: i64 = row.get(2)?;
                Ok(TagMetricRow {
                    tag: row.get(0)?,
                    color: row.get(1)?,
                    total_base: minor_to_money_value(total_minor),
                    record_count: row.get(3)?,
                })
            })
            .map_err(sqlite_err)?;

        let mut result = Vec::new();
        for row in rows {
            result.push(row.map_err(sqlite_err)?);
        }
        Ok(result)
    })
}

pub fn metrics_tag_coverage(
    db_path: &str,
    start_date: &str,
    end_date: &str,
) -> StorageResult<TagCoverageRow> {
    with_cached_read_connection(db_path, |conn| {
        let total_count = conn
            .query_row(
                "SELECT COUNT(*) \
                 FROM records \
                 WHERE type IN ('expense', 'mandatory_expense') \
                   AND transfer_id IS NULL \
                   AND date >= ?1 AND date <= ?2",
                (start_date, end_date),
                |row| row.get::<_, i64>(0),
            )
            .map_err(sqlite_err)?;
        let tagged_count = conn
            .query_row(
                "SELECT COUNT(DISTINCT r.id) \
                 FROM records AS r \
                 JOIN record_tags AS rt ON rt.record_id = r.id \
                 WHERE r.type IN ('expense', 'mandatory_expense') \
                   AND r.transfer_id IS NULL \
                   AND r.date >= ?1 AND r.date <= ?2",
                (start_date, end_date),
                |row| row.get::<_, i64>(0),
            )
            .map_err(sqlite_err)?;
        let coverage_pct = if total_count > 0 {
            round_money(tagged_count as f64 / total_count as f64 * 100.0)
        } else {
            0.0
        };
        Ok(TagCoverageRow {
            tagged_count,
            total_count,
            coverage_pct,
        })
    })
}

pub fn metrics_monthly_summary(
    db_path: &str,
    start_date: Option<&str>,
    end_date: Option<&str>,
) -> StorageResult<Vec<MonthlySummaryRow>> {
    with_cached_read_connection(db_path, |conn| {
        let amount_expr = minor_amount_expr("amount_base");
        let mut sql = format!(
            "SELECT \
                strftime('%Y-%m', date) AS month, \
                COALESCE(SUM(CASE type WHEN 'income' THEN {amount_expr} ELSE 0 END), 0) AS income, \
                COALESCE(SUM(CASE WHEN type IN ('expense', 'mandatory_expense') THEN {amount_expr} ELSE 0 END), 0) AS expenses \
             FROM records \
             WHERE transfer_id IS NULL"
        );
        if start_date.is_some() {
            sql.push_str(" AND date >= ?1");
        }
        if end_date.is_some() {
            sql.push_str(if start_date.is_some() {
                " AND date <= ?2"
            } else {
                " AND date <= ?1"
            });
        }
        sql.push_str(" GROUP BY strftime('%Y-%m', date) ORDER BY month");

        let mut stmt = conn.prepare(&sql).map_err(sqlite_err)?;
        let mapper = |row: &rusqlite::Row<'_>| -> rusqlite::Result<MonthlySummaryRow> {
            let income = minor_to_money_value(row.get::<_, i64>(1)?);
            let expenses = minor_to_money_value(row.get::<_, i64>(2)?);
            let cashflow = round_money(income - expenses);
            let savings_rate = if income > 0.0 {
                round_money(cashflow / income * 100.0)
            } else {
                0.0
            };
            Ok(MonthlySummaryRow {
                month: row.get(0)?,
                income,
                expenses,
                cashflow,
                savings_rate,
            })
        };
        let mut result = Vec::new();
        match (start_date, end_date) {
            (Some(start), Some(end)) => {
                for row in stmt.query_map((start, end), mapper).map_err(sqlite_err)? {
                    result.push(row.map_err(sqlite_err)?);
                }
            }
            (Some(start), None) => {
                for row in stmt.query_map([start], mapper).map_err(sqlite_err)? {
                    result.push(row.map_err(sqlite_err)?);
                }
            }
            (None, Some(end)) => {
                for row in stmt.query_map([end], mapper).map_err(sqlite_err)? {
                    result.push(row.map_err(sqlite_err)?);
                }
            }
            (None, None) => {
                for row in stmt.query_map([], mapper).map_err(sqlite_err)? {
                    result.push(row.map_err(sqlite_err)?);
                }
            }
        }
        Ok(result)
    })
}
