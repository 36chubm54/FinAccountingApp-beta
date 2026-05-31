use crate::{open_sqlite_connection, sqlite_err, StorageResult};
use ledgera_engine_core::{to_money_float, to_rate_float};
use rusqlite::Connection;
use std::collections::{HashMap, HashSet};
use std::time::{SystemTime, UNIX_EPOCH};

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct AuditFindingRow {
    pub check: String,
    pub severity: String,
    pub message: String,
    pub detail: String,
}

#[derive(Debug, Clone)]
struct WalletAuditRow {
    id: i64,
    system: i64,
}

#[derive(Debug, Clone)]
struct TransferAuditRow {
    id: i64,
    from_wallet_id: i64,
    to_wallet_id: i64,
    date: String,
    amount_original: f64,
    currency: String,
    rate_at_operation: f64,
    amount_base: f64,
}

#[derive(Debug, Clone)]
struct RecordAuditRow {
    id: i64,
    record_type: String,
    date: String,
    wallet_id: i64,
    transfer_id: Option<i64>,
    amount_original: f64,
    currency: String,
    rate_at_operation: f64,
    amount_base: f64,
    category: String,
}

#[derive(Debug, Clone)]
struct MandatoryAuditRow {
    id: i64,
    amount_original: f64,
    amount_base: f64,
    date: Option<String>,
    auto_pay: i64,
}

#[derive(Debug, Clone)]
struct TagAuditRow {
    id: i64,
    name: String,
    usage_count: i64,
}

#[derive(Debug, Clone)]
struct RecordTagAuditRow {
    record_id: i64,
    tag_id: i64,
}

#[derive(Debug, Clone)]
struct DebtAuditRow {
    id: i64,
    total_amount_minor: i64,
    remaining_amount_minor: i64,
    status: String,
}

#[derive(Debug, Clone)]
struct DebtPaymentAuditRow {
    id: i64,
    debt_id: i64,
    record_id: Option<i64>,
    operation_type: String,
    principal_paid_minor: i64,
    is_write_off: i64,
}

#[derive(Debug, Clone)]
struct AssetAuditRow {
    id: i64,
    name: String,
    category: String,
    currency: String,
    is_active: i64,
    created_at: String,
}

#[derive(Debug, Clone)]
struct AssetSnapshotAuditRow {
    id: i64,
    asset_id: i64,
    snapshot_date: String,
    value_minor: i64,
    currency: String,
}

#[derive(Debug, Clone)]
struct GoalAuditRow {
    id: i64,
    title: String,
    target_amount_minor: i64,
    currency: String,
    target_date: Option<String>,
    is_completed: i64,
    created_at: String,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
struct DateParts {
    year: i32,
    month: u32,
    day: u32,
}

pub fn audit_run(db_path: &str) -> StorageResult<Vec<AuditFindingRow>> {
    let conn = open_sqlite_connection(db_path)?;
    let wallets = wallet_rows(&conn)?;
    let transfers = transfer_rows(&conn)?;
    let records = record_rows(&conn)?;
    let mandatory_expenses = mandatory_rows(&conn)?;
    let tags = tag_rows(&conn)?;
    let record_tags = record_tag_rows(&conn)?;
    let debts = debt_rows(&conn)?;
    let debt_payments = debt_payment_rows(&conn)?;
    let assets = asset_rows(&conn)?;
    let asset_snapshots = asset_snapshot_rows(&conn)?;
    let goals = goal_rows(&conn)?;

    let (transfer_linked_records, record_findings) = scan_records(&records);
    let mut findings = Vec::new();
    findings.extend(check_system_wallet_sanity(&wallets));
    findings.extend(check_transfer_pair_integrity(
        &transfers,
        &transfer_linked_records,
    ));
    findings.extend(check_transfer_amount_alignment(
        &transfers,
        &transfer_linked_records,
    ));
    findings.extend(check_transfer_record_invariants(
        &transfers,
        &transfer_linked_records,
    ));
    findings.extend(findings_or_ok(
        record_findings.amount_consistency,
        "amount_consistency",
        "All record amounts are consistent.",
    ));
    findings.extend(check_amount_positivity(
        record_findings.amount_positivity,
        &transfers,
        &mandatory_expenses,
    ));
    findings.extend(findings_or_ok(
        record_findings.rate_positivity,
        "rate_positivity",
        "All rates positive.",
    ));
    findings.extend(findings_or_ok(
        record_findings.date_validity,
        "date_validity",
        "All record dates are valid.",
    ));
    findings.extend(check_currency_codes(
        record_findings.currency_codes,
        &transfers,
    ));
    findings.extend(check_tag_integrity(&conn, &tags, &record_tags)?);
    findings.extend(check_mandatory_template_date_and_autopay(
        &mandatory_expenses,
    ));
    findings.extend(check_debt_balance_integrity(&conn, &debts, &debt_payments)?);
    findings.extend(check_asset_integrity(&assets));
    findings.extend(check_asset_snapshot_integrity(&assets, &asset_snapshots));
    findings.extend(check_goal_integrity(&goals));
    Ok(findings)
}

struct RecordFindingGroups {
    amount_consistency: Vec<AuditFindingRow>,
    amount_positivity: Vec<AuditFindingRow>,
    rate_positivity: Vec<AuditFindingRow>,
    date_validity: Vec<AuditFindingRow>,
    currency_codes: Vec<AuditFindingRow>,
}

fn scan_records(
    records: &[RecordAuditRow],
) -> (HashMap<i64, Vec<RecordAuditRow>>, RecordFindingGroups) {
    let mut transfer_linked_records: HashMap<i64, Vec<RecordAuditRow>> = HashMap::new();
    let mut amount_consistency = Vec::new();
    let mut amount_positivity = Vec::new();
    let mut rate_positivity = Vec::new();
    let mut date_validity = Vec::new();
    let mut currency_codes = Vec::new();

    for record in records {
        let amount_original = money_float(record.amount_original);
        let rate_at_operation = rate_float(record.rate_at_operation);
        let amount_base = money_float(record.amount_base);
        let expected = money_float(amount_original) * rate_float(rate_at_operation);
        let delta = money_float(amount_base) - money_float(expected);
        if delta.abs() > 0.01 {
            amount_consistency.push(finding(
                "amount_consistency",
                "warning",
                format!("Record id={} has inconsistent amount_base.", record.id),
                format!("delta {:.2} KZT", delta),
            ));
        }

        if amount_original <= 0.0 {
            amount_positivity.push(finding(
                "amount_positivity",
                "error",
                format!("Record id={} has non-positive amount_original.", record.id),
                format!("amount_original={amount_original}"),
            ));
        }
        if amount_base <= 0.0 {
            amount_positivity.push(finding(
                "amount_positivity",
                "error",
                format!("Record id={} has non-positive amount_base.", record.id),
                format!("amount_base={amount_base}"),
            ));
        }

        if rate_at_operation <= 0.0 {
            rate_positivity.push(finding(
                "rate_positivity",
                "error",
                format!(
                    "Record id={} has non-positive rate_at_operation.",
                    record.id
                ),
                format!("rate_at_operation={rate_at_operation}"),
            ));
        }

        if let Err(error) = parse_ymd_not_future(&record.date) {
            date_validity.push(finding(
                "date_validity",
                "error",
                format!("Record id={} has invalid date.", record.id),
                format!("{}: {error}", record.date),
            ));
        }

        if record.currency.trim().is_empty() {
            currency_codes.push(finding(
                "currency_codes",
                "warning",
                format!("Record id={} has empty currency code.", record.id),
                "",
            ));
        }

        if let Some(transfer_id) = record.transfer_id {
            transfer_linked_records
                .entry(transfer_id)
                .or_default()
                .push(record.clone());
        }
    }

    (
        transfer_linked_records,
        RecordFindingGroups {
            amount_consistency,
            amount_positivity,
            rate_positivity,
            date_validity,
            currency_codes,
        },
    )
}

fn check_system_wallet_sanity(wallets: &[WalletAuditRow]) -> Vec<AuditFindingRow> {
    let mut findings = Vec::new();
    match wallets.iter().find(|wallet| wallet.id == 1) {
        Some(wallet) if wallet.system != 1 => findings.push(finding(
            "system_wallet_sanity",
            "error",
            "System wallet id=1 must have system=1.",
            format!("system={}", wallet.system),
        )),
        None => findings.push(finding(
            "system_wallet_sanity",
            "error",
            "System wallet id=1 is missing.",
            "",
        )),
        _ => {}
    }
    let mut system_wallet_ids = wallets
        .iter()
        .filter(|wallet| wallet.system == 1)
        .map(|wallet| wallet.id)
        .collect::<Vec<_>>();
    system_wallet_ids.sort_unstable();
    if system_wallet_ids.len() > 1 {
        findings.push(finding(
            "system_wallet_sanity",
            "warning",
            "Multiple system wallets detected.",
            format!("ids={system_wallet_ids:?}"),
        ));
    }
    findings_or_ok(findings, "system_wallet_sanity", "System wallet sanity OK.")
}

fn check_transfer_pair_integrity(
    transfers: &[TransferAuditRow],
    linked_by_transfer: &HashMap<i64, Vec<RecordAuditRow>>,
) -> Vec<AuditFindingRow> {
    let transfer_ids = transfers
        .iter()
        .map(|transfer| transfer.id)
        .collect::<HashSet<_>>();
    let mut findings = Vec::new();
    let mut sorted_transfer_ids = transfer_ids.iter().copied().collect::<Vec<_>>();
    sorted_transfer_ids.sort_unstable();
    for transfer_id in sorted_transfer_ids {
        let linked = non_commission_records(linked_by_transfer.get(&transfer_id));
        let expense_count = linked
            .iter()
            .filter(|record| record.record_type.trim() == "expense")
            .count();
        let income_count = linked
            .iter()
            .filter(|record| record.record_type.trim() == "income")
            .count();
        if linked.len() != 2 || expense_count != 1 || income_count != 1 {
            findings.push(finding(
                "transfer_pair_integrity",
                "error",
                format!("Transfer id={transfer_id} has invalid linked record pair."),
                format!(
                    "linked={}, expense={}, income={}",
                    linked.len(),
                    expense_count,
                    income_count
                ),
            ));
        }
    }

    let mut linked_ids = linked_by_transfer.keys().copied().collect::<Vec<_>>();
    linked_ids.sort_unstable();
    for transfer_id in linked_ids {
        if !transfer_ids.contains(&transfer_id) {
            findings.push(finding(
                "transfer_pair_integrity",
                "error",
                format!("Transfer id={transfer_id} is referenced by records but missing."),
                "",
            ));
        }
    }
    findings_or_ok(
        findings,
        "transfer_pair_integrity",
        "All transfer pairs valid.",
    )
}

fn check_transfer_amount_alignment(
    transfers: &[TransferAuditRow],
    linked_by_transfer: &HashMap<i64, Vec<RecordAuditRow>>,
) -> Vec<AuditFindingRow> {
    let mut findings = Vec::new();
    for transfer in transfers {
        let linked = non_commission_records(linked_by_transfer.get(&transfer.id));
        if linked.len() != 2 {
            continue;
        }
        let expense = linked
            .iter()
            .find(|record| record.record_type.as_str() == "expense");
        let income = linked
            .iter()
            .find(|record| record.record_type.as_str() == "income");
        let (Some(expense), Some(income)) = (expense, income) else {
            continue;
        };
        let mut mismatches = Vec::new();
        if money_diff(transfer.amount_original, expense.amount_original).abs() > 0.0
            || money_diff(transfer.amount_original, income.amount_original).abs() > 0.0
        {
            mismatches.push("amount_original mismatch");
        }
        if transfer.currency != expense.currency || transfer.currency != income.currency {
            mismatches.push("currency mismatch");
        }
        if rate_diff(transfer.rate_at_operation, expense.rate_at_operation).abs() > 0.0
            || rate_diff(transfer.rate_at_operation, income.rate_at_operation).abs() > 0.0
        {
            mismatches.push("rate_at_operation mismatch");
        }
        if money_diff(transfer.amount_base, expense.amount_base).abs() > 0.0
            || money_diff(transfer.amount_base, income.amount_base).abs() > 0.0
        {
            mismatches.push("amount_base mismatch");
        }
        if !mismatches.is_empty() {
            findings.push(finding(
                "transfer_amount_alignment",
                "error",
                format!("Transfer id={} does not match linked records.", transfer.id),
                mismatches.join(", "),
            ));
        }
    }
    findings_or_ok(
        findings,
        "transfer_amount_alignment",
        "All transfers match their linked records.",
    )
}

fn check_transfer_record_invariants(
    transfers: &[TransferAuditRow],
    linked_by_transfer: &HashMap<i64, Vec<RecordAuditRow>>,
) -> Vec<AuditFindingRow> {
    let transfer_by_id = transfers
        .iter()
        .map(|transfer| (transfer.id, transfer))
        .collect::<HashMap<_, _>>();
    let mut findings = Vec::new();
    let mut transfer_ids = linked_by_transfer.keys().copied().collect::<Vec<_>>();
    transfer_ids.sort_unstable();
    for transfer_id in transfer_ids {
        let Some(transfer) = transfer_by_id.get(&transfer_id) else {
            continue;
        };
        if let Some(records) = linked_by_transfer.get(&transfer_id) {
            for record in records {
                let category = record.category.trim();
                let category_lc = category.to_lowercase();
                if category_lc == "commission" {
                    continue;
                }
                if category_lc != "transfer" {
                    findings.push(finding(
                        "transfer_record_invariants",
                        "error",
                        format!(
                            "Record id={} is transfer-linked but has non-Transfer category.",
                            record.id
                        ),
                        format!("category={}", py_string_repr(category)),
                    ));
                }
                let expected_wallet_id = match record.record_type.trim().to_lowercase().as_str() {
                    "expense" => transfer.from_wallet_id,
                    "income" => transfer.to_wallet_id,
                    _ => continue,
                };
                if expected_wallet_id > 0 && record.wallet_id != expected_wallet_id {
                    findings.push(finding(
                        "transfer_record_invariants",
                        "error",
                        format!("Record id={} has mismatched transfer wallet.", record.id),
                        format!(
                            "expected_wallet_id={}, wallet_id={}",
                            expected_wallet_id, record.wallet_id
                        ),
                    ));
                }
                if !transfer.date.is_empty()
                    && !record.date.is_empty()
                    && transfer.date != record.date
                {
                    findings.push(finding(
                        "transfer_record_invariants",
                        "error",
                        format!("Record id={} has mismatched transfer date.", record.id),
                        format!(
                            "transfer_date={}, record_date={}",
                            py_string_repr(&transfer.date),
                            py_string_repr(&record.date)
                        ),
                    ));
                }
            }
        }
    }
    findings_or_ok(
        findings,
        "transfer_record_invariants",
        "All transfer-linked record invariants satisfied.",
    )
}

fn check_amount_positivity(
    mut findings: Vec<AuditFindingRow>,
    transfers: &[TransferAuditRow],
    mandatory_expenses: &[MandatoryAuditRow],
) -> Vec<AuditFindingRow> {
    for transfer in transfers {
        if transfer.amount_original <= 0.0 {
            findings.push(finding(
                "amount_positivity",
                "error",
                format!(
                    "Transfer id={} has non-positive amount_original.",
                    transfer.id
                ),
                format!("amount_original={}", transfer.amount_original),
            ));
        }
        if transfer.amount_base <= 0.0 {
            findings.push(finding(
                "amount_positivity",
                "error",
                format!("Transfer id={} has non-positive amount_base.", transfer.id),
                format!("amount_base={}", transfer.amount_base),
            ));
        }
    }

    for expense in mandatory_expenses {
        if expense.amount_original <= 0.0 {
            findings.push(finding(
                "amount_positivity",
                "error",
                format!(
                    "Mandatory expense id={} has non-positive amount_original.",
                    expense.id
                ),
                format!("amount_original={}", expense.amount_original),
            ));
        }
        if expense.amount_base <= 0.0 {
            findings.push(finding(
                "amount_positivity",
                "error",
                format!(
                    "Mandatory expense id={} has non-positive amount_base.",
                    expense.id
                ),
                format!("amount_base={}", expense.amount_base),
            ));
        }
    }
    findings_or_ok(findings, "amount_positivity", "All amounts are positive.")
}

fn check_currency_codes(
    mut findings: Vec<AuditFindingRow>,
    transfers: &[TransferAuditRow],
) -> Vec<AuditFindingRow> {
    for transfer in transfers {
        if transfer.currency.trim().is_empty() {
            findings.push(finding(
                "currency_codes",
                "warning",
                format!("Transfer id={} has empty currency code.", transfer.id),
                "",
            ));
        }
    }
    findings_or_ok(
        findings,
        "currency_codes",
        "All currency codes are present.",
    )
}

fn check_mandatory_template_date_and_autopay(rows: &[MandatoryAuditRow]) -> Vec<AuditFindingRow> {
    let mut findings = Vec::new();
    for expense in rows {
        let normalized_date = expense.date.as_deref().unwrap_or("").trim();
        if let (true, Err(error)) = (!normalized_date.is_empty(), parse_ymd(normalized_date)) {
            findings.push(finding(
                "mandatory_template_date_and_autopay",
                "error",
                format!("Mandatory expense id={} has invalid date.", expense.id),
                format!("{normalized_date}: {error}"),
            ));
        }
        let expected_auto_pay = !normalized_date.is_empty();
        let actual_auto_pay = expense.auto_pay != 0;
        if expected_auto_pay != actual_auto_pay {
            findings.push(finding(
                "mandatory_template_date_and_autopay",
                "error",
                format!(
                    "Mandatory expense id={} has inconsistent auto_pay.",
                    expense.id
                ),
                format!(
                    "date={}, auto_pay={}",
                    py_string_repr(normalized_date),
                    expense.auto_pay
                ),
            ));
        }
    }
    findings_or_ok(
        findings,
        "mandatory_template_date_and_autopay",
        "All mandatory template dates and auto_pay flags consistent.",
    )
}

fn check_tag_integrity(
    conn: &Connection,
    tags: &[TagAuditRow],
    record_tags: &[RecordTagAuditRow],
) -> StorageResult<Vec<AuditFindingRow>> {
    let mut findings = Vec::new();
    let tags_by_id = tags
        .iter()
        .map(|tag| (tag.id, tag))
        .collect::<HashMap<_, _>>();
    let existing_record_ids = existing_record_ids(conn)?;
    let mut normalized_names: HashMap<String, i64> = HashMap::new();
    let mut actual_usage_by_tag_id: HashMap<i64, i64> = HashMap::new();
    let mut seen_pairs = HashSet::new();

    for tag in tags {
        let raw_name = tag.name.clone();
        let normalized_name = raw_name.trim().to_lowercase();
        if normalized_name.is_empty() {
            findings.push(finding(
                "tag_integrity",
                "error",
                format!("Tag id={} has empty name.", tag.id),
                "",
            ));
        } else if let Some(existing_id) = normalized_names.get(&normalized_name) {
            let mut ids = vec![*existing_id, tag.id];
            ids.sort_unstable();
            findings.push(finding(
                "tag_integrity",
                "error",
                "Duplicate tag names detected.",
                format!("tag_ids={ids:?}, name={}", py_string_repr(&raw_name)),
            ));
        } else {
            normalized_names.insert(normalized_name, tag.id);
        }
    }

    for row in record_tags {
        let pair = (row.record_id, row.tag_id);
        if !seen_pairs.insert(pair) {
            findings.push(finding(
                "tag_integrity",
                "error",
                "Duplicate record-tag assignment detected.",
                format!("record_id={}, tag_id={}", row.record_id, row.tag_id),
            ));
        }
        if !existing_record_ids.contains(&row.record_id) {
            findings.push(finding(
                "tag_integrity",
                "error",
                "Record-tag assignment references missing record.",
                format!("record_id={}, tag_id={}", row.record_id, row.tag_id),
            ));
            continue;
        }
        if !tags_by_id.contains_key(&row.tag_id) {
            findings.push(finding(
                "tag_integrity",
                "error",
                "Record-tag assignment references missing tag.",
                format!("record_id={}, tag_id={}", row.record_id, row.tag_id),
            ));
            continue;
        }
        *actual_usage_by_tag_id.entry(row.tag_id).or_insert(0) += 1;
    }

    for tag in tags {
        let actual_usage = *actual_usage_by_tag_id.get(&tag.id).unwrap_or(&0);
        if tag.usage_count != actual_usage {
            findings.push(finding(
                "tag_integrity",
                "warning",
                format!("Tag id={} has inconsistent usage_count.", tag.id),
                format!(
                    "usage_count={}, actual_assignments={actual_usage}",
                    tag.usage_count
                ),
            ));
        }
    }
    Ok(findings_or_ok(
        findings,
        "tag_integrity",
        "All tag rows and record-tag assignments are consistent.",
    ))
}

fn check_debt_balance_integrity(
    conn: &Connection,
    debts: &[DebtAuditRow],
    payments: &[DebtPaymentAuditRow],
) -> StorageResult<Vec<AuditFindingRow>> {
    let debt_by_id = debts
        .iter()
        .map(|debt| (debt.id, debt))
        .collect::<HashMap<_, _>>();
    let record_debt_links = record_debt_links(conn)?;
    let mut payments_by_debt: HashMap<i64, Vec<&DebtPaymentAuditRow>> = HashMap::new();
    let mut findings = Vec::new();

    for payment in payments {
        payments_by_debt
            .entry(payment.debt_id)
            .or_default()
            .push(payment);
        if !debt_by_id.contains_key(&payment.debt_id) {
            findings.push(finding(
                "debt_balance_integrity",
                "error",
                format!("Debt payment id={} references missing debt.", payment.id),
                format!("debt_id={}", payment.debt_id),
            ));
            continue;
        }
        let operation_type = payment.operation_type.trim().to_lowercase();
        let is_write_off = payment.is_write_off != 0;
        if is_write_off != (operation_type == "debt_forgive") {
            findings.push(finding(
                "debt_balance_integrity",
                "error",
                format!(
                    "Debt payment id={} has mismatched write-off flags.",
                    payment.id
                ),
                format!(
                    "operation_type={operation_type}, is_write_off={}",
                    i32::from(is_write_off)
                ),
            ));
        }
        if let Some(record_id) = payment.record_id {
            let linked_debt_id = record_debt_links.get(&record_id).copied();
            if linked_debt_id != Some(payment.debt_id) {
                findings.push(finding(
                    "debt_balance_integrity",
                    "error",
                    format!("Debt payment id={} is linked to wrong record.", payment.id),
                    format!(
                        "record_id={record_id}, record.related_debt_id={}, debt_id={}",
                        option_i64_repr(linked_debt_id),
                        payment.debt_id
                    ),
                ));
            }
        } else if !is_write_off {
            findings.push(finding(
                "debt_balance_integrity",
                "error",
                format!("Debt payment id={} is missing linked record.", payment.id),
                "",
            ));
        }
    }

    let mut sorted_debts = debts.iter().collect::<Vec<_>>();
    sorted_debts.sort_by_key(|debt| debt.id);
    for debt in sorted_debts {
        let paid_minor = payments_by_debt
            .get(&debt.id)
            .map(|rows| {
                rows.iter()
                    .map(|payment| payment.principal_paid_minor)
                    .sum::<i64>()
            })
            .unwrap_or(0);
        if debt.total_amount_minor != debt.remaining_amount_minor + paid_minor {
            findings.push(finding(
                "debt_balance_integrity",
                "error",
                format!(
                    "Debt id={} has inconsistent balance decomposition.",
                    debt.id
                ),
                format!(
                    "total={}, remaining={}, paid={paid_minor}",
                    debt.total_amount_minor, debt.remaining_amount_minor
                ),
            ));
        }
        let status = debt.status.trim().to_lowercase();
        if status == "closed" && debt.remaining_amount_minor != 0 {
            findings.push(finding(
                "debt_balance_integrity",
                "error",
                format!(
                    "Debt id={} is closed with non-zero remaining balance.",
                    debt.id
                ),
                format!("remaining_amount_minor={}", debt.remaining_amount_minor),
            ));
        }
        if status == "open" && debt.remaining_amount_minor == 0 {
            findings.push(finding(
                "debt_balance_integrity",
                "error",
                format!("Debt id={} is open with zero remaining balance.", debt.id),
                "",
            ));
        }
    }
    Ok(findings_or_ok(
        findings,
        "debt_balance_integrity",
        "Debt balances and linked payments are consistent.",
    ))
}

fn check_asset_integrity(assets: &[AssetAuditRow]) -> Vec<AuditFindingRow> {
    let mut findings = Vec::new();
    let valid_categories = HashSet::from(["bank", "crypto", "cash", "other"]);
    for asset in assets {
        if asset.name.trim().is_empty() {
            findings.push(finding(
                "asset_integrity",
                "error",
                format!("Asset id={} has empty name.", asset.id),
                "",
            ));
        }
        let category = asset.category.trim().to_lowercase();
        if !valid_categories.contains(category.as_str()) {
            findings.push(finding(
                "asset_integrity",
                "error",
                format!("Asset id={} has invalid category.", asset.id),
                format!("category={}", py_string_repr(&category)),
            ));
        }
        let currency = asset.currency.trim().to_uppercase();
        if currency.len() != 3 {
            findings.push(finding(
                "asset_integrity",
                "warning",
                format!("Asset id={} has invalid currency code.", asset.id),
                format!("currency={}", py_string_repr(&currency)),
            ));
        }
        if let Err(error) = parse_ymd_not_future(&asset.created_at) {
            findings.push(finding(
                "asset_integrity",
                "error",
                format!("Asset id={} has invalid created_at.", asset.id),
                format!("{}: {error}", asset.created_at),
            ));
        }
        if !matches!(asset.is_active, 0 | 1) {
            findings.push(finding(
                "asset_integrity",
                "error",
                format!("Asset id={} has invalid is_active flag.", asset.id),
                format!("is_active={:?}", asset.is_active),
            ));
        }
    }
    findings_or_ok(
        findings,
        "asset_integrity",
        "All assets passed integrity checks.",
    )
}

fn check_asset_snapshot_integrity(
    assets: &[AssetAuditRow],
    snapshots: &[AssetSnapshotAuditRow],
) -> Vec<AuditFindingRow> {
    let assets_by_id = assets
        .iter()
        .map(|asset| (asset.id, asset))
        .collect::<HashMap<_, _>>();
    let mut findings = Vec::new();
    for snapshot in snapshots {
        let Some(asset) = assets_by_id.get(&snapshot.asset_id) else {
            findings.push(finding(
                "asset_snapshot_integrity",
                "error",
                format!(
                    "Asset snapshot id={} references missing asset.",
                    snapshot.id
                ),
                format!("asset_id={}", snapshot.asset_id),
            ));
            continue;
        };
        if snapshot.value_minor < 0 {
            findings.push(finding(
                "asset_snapshot_integrity",
                "error",
                format!("Asset snapshot id={} has negative value.", snapshot.id),
                format!("value_minor={}", snapshot.value_minor),
            ));
        }
        match parse_ymd_not_future(&snapshot.snapshot_date) {
            Ok(snapshot_date) => match parse_ymd(&asset.created_at) {
                Ok(asset_created_at) if snapshot_date < asset_created_at => {
                    findings.push(finding(
                        "asset_snapshot_integrity",
                        "error",
                        format!(
                            "Asset snapshot id={} is earlier than asset created_at.",
                            snapshot.id
                        ),
                        format!(
                            "snapshot_date={}, asset_created_at={}",
                            snapshot.snapshot_date, asset.created_at
                        ),
                    ));
                }
                Err(error) => findings.push(finding(
                    "asset_snapshot_integrity",
                    "error",
                    format!(
                        "Asset snapshot id={} has invalid snapshot_date.",
                        snapshot.id
                    ),
                    format!("{}: {error}", snapshot.snapshot_date),
                )),
                _ => {}
            },
            Err(error) => findings.push(finding(
                "asset_snapshot_integrity",
                "error",
                format!(
                    "Asset snapshot id={} has invalid snapshot_date.",
                    snapshot.id
                ),
                format!("{}: {error}", snapshot.snapshot_date),
            )),
        }
        let currency = snapshot.currency.trim().to_uppercase();
        if currency.len() != 3 {
            findings.push(finding(
                "asset_snapshot_integrity",
                "warning",
                format!(
                    "Asset snapshot id={} has invalid currency code.",
                    snapshot.id
                ),
                format!("currency={}", py_string_repr(&currency)),
            ));
        } else if currency != asset.currency.trim().to_uppercase() {
            findings.push(finding(
                "asset_snapshot_integrity",
                "warning",
                format!(
                    "Asset snapshot id={} currency mismatches asset.",
                    snapshot.id
                ),
                format!(
                    "snapshot_currency={}, asset_currency={}",
                    py_string_repr(&currency),
                    py_string_repr(&asset.currency.trim().to_uppercase())
                ),
            ));
        }
    }
    findings_or_ok(
        findings,
        "asset_snapshot_integrity",
        "All asset snapshots passed integrity checks.",
    )
}

fn check_goal_integrity(goals: &[GoalAuditRow]) -> Vec<AuditFindingRow> {
    let mut findings = Vec::new();
    for goal in goals {
        if goal.title.trim().is_empty() {
            findings.push(finding(
                "goal_integrity",
                "error",
                format!("Goal id={} has empty title.", goal.id),
                "",
            ));
        }
        if goal.target_amount_minor <= 0 {
            findings.push(finding(
                "goal_integrity",
                "error",
                format!("Goal id={} has non-positive target amount.", goal.id),
                format!("target_amount_minor={}", goal.target_amount_minor),
            ));
        }
        let currency = goal.currency.trim().to_uppercase();
        if currency.len() != 3 {
            findings.push(finding(
                "goal_integrity",
                "warning",
                format!("Goal id={} has invalid currency code.", goal.id),
                format!("currency={}", py_string_repr(&currency)),
            ));
        }
        let created_at = match parse_ymd_not_future(&goal.created_at) {
            Ok(value) => Some(value),
            Err(error) => {
                findings.push(finding(
                    "goal_integrity",
                    "error",
                    format!("Goal id={} has invalid created_at.", goal.id),
                    format!("{}: {error}", goal.created_at),
                ));
                None
            }
        };
        if let Some(target_date_raw) = goal
            .target_date
            .as_deref()
            .map(str::trim)
            .filter(|v| !v.is_empty())
        {
            match parse_ymd(target_date_raw) {
                Ok(target_date)
                    if created_at.is_some_and(|created_at| target_date < created_at) =>
                {
                    findings.push(finding(
                        "goal_integrity",
                        "error",
                        format!(
                            "Goal id={} has target_date earlier than created_at.",
                            goal.id
                        ),
                        format!(
                            "created_at={}, target_date={target_date_raw}",
                            goal.created_at
                        ),
                    ));
                }
                Err(error) => findings.push(finding(
                    "goal_integrity",
                    "error",
                    format!("Goal id={} has invalid target_date.", goal.id),
                    format!("{target_date_raw}: {error}"),
                )),
                _ => {}
            }
        }
        if !matches!(goal.is_completed, 0 | 1) {
            findings.push(finding(
                "goal_integrity",
                "error",
                format!("Goal id={} has invalid is_completed flag.", goal.id),
                format!("is_completed={:?}", goal.is_completed),
            ));
        }
    }
    findings_or_ok(
        findings,
        "goal_integrity",
        "All goals passed integrity checks.",
    )
}

fn non_commission_records(records: Option<&Vec<RecordAuditRow>>) -> Vec<&RecordAuditRow> {
    records
        .into_iter()
        .flat_map(|rows| rows.iter())
        .filter(|record| record.category.trim().to_lowercase() != "commission")
        .collect()
}

fn findings_or_ok(
    findings: Vec<AuditFindingRow>,
    check: &str,
    ok_message: &str,
) -> Vec<AuditFindingRow> {
    if findings.is_empty() {
        vec![finding(check, "ok", ok_message, "")]
    } else {
        findings
    }
}

fn finding(
    check: impl Into<String>,
    severity: impl Into<String>,
    message: impl Into<String>,
    detail: impl Into<String>,
) -> AuditFindingRow {
    AuditFindingRow {
        check: check.into(),
        severity: severity.into(),
        message: message.into(),
        detail: detail.into(),
    }
}

fn money_float(value: f64) -> f64 {
    to_money_float(&value.to_string()).unwrap_or(value)
}

fn rate_float(value: f64) -> f64 {
    to_rate_float(&value.to_string()).unwrap_or(value)
}

fn money_diff(left: f64, right: f64) -> f64 {
    money_float(left) - money_float(right)
}

fn rate_diff(left: f64, right: f64) -> f64 {
    rate_float(left) - rate_float(right)
}

fn option_i64_repr(value: Option<i64>) -> String {
    value.map_or_else(|| "None".to_owned(), |value| value.to_string())
}

fn py_string_repr(value: &str) -> String {
    format!("'{}'", value.replace('\\', "\\\\").replace('\'', "\\'"))
}

fn parse_ymd_not_future(value: &str) -> Result<DateParts, String> {
    let parsed = parse_ymd(value)?;
    let today = today_utc();
    if parsed > today {
        Err("Date cannot be in the future".to_owned())
    } else {
        Ok(parsed)
    }
}

fn parse_ymd(value: &str) -> Result<DateParts, String> {
    if value.is_empty() {
        return Err("Date value is empty".to_owned());
    }
    let bytes = value.as_bytes();
    if bytes.len() != 10
        || !bytes[0..4].iter().all(u8::is_ascii_digit)
        || bytes[4] != b'-'
        || !bytes[5..7].iter().all(u8::is_ascii_digit)
        || bytes[7] != b'-'
        || !bytes[8..10].iter().all(u8::is_ascii_digit)
    {
        return Err("Invalid date format".to_owned());
    }
    let year = value[0..4]
        .parse::<i32>()
        .map_err(|_| "Invalid date format".to_owned())?;
    let month = value[5..7]
        .parse::<u32>()
        .map_err(|_| "Invalid date format".to_owned())?;
    let day = value[8..10]
        .parse::<u32>()
        .map_err(|_| "Invalid date format".to_owned())?;
    if !(1..=12).contains(&month) {
        return Err("Invalid month".to_owned());
    }
    let last_day = days_in_month(year, month);
    if day == 0 || day > last_day {
        return Err("Invalid day".to_owned());
    }
    let parsed = DateParts { year, month, day };
    if parsed
        < (DateParts {
            year: 1970,
            month: 1,
            day: 1,
        })
    {
        return Err("Date cannot be earlier than 1970-01-01".to_owned());
    }
    Ok(parsed)
}

fn days_in_month(year: i32, month: u32) -> u32 {
    match month {
        1 | 3 | 5 | 7 | 8 | 10 | 12 => 31,
        4 | 6 | 9 | 11 => 30,
        2 if is_leap_year(year) => 29,
        2 => 28,
        _ => 0,
    }
}

fn is_leap_year(year: i32) -> bool {
    (year % 4 == 0 && year % 100 != 0) || year % 400 == 0
}

fn today_utc() -> DateParts {
    let days_since_epoch = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|duration| (duration.as_secs() / 86_400) as i64)
        .unwrap_or(0);
    civil_from_days(days_since_epoch)
}

fn civil_from_days(days_since_epoch: i64) -> DateParts {
    let z = days_since_epoch + 719_468;
    let era = if z >= 0 { z } else { z - 146_096 } / 146_097;
    let doe = z - era * 146_097;
    let yoe = (doe - doe / 1460 + doe / 36_524 - doe / 146_096) / 365;
    let y = yoe + era * 400;
    let doy = doe - (365 * yoe + yoe / 4 - yoe / 100);
    let mp = (5 * doy + 2) / 153;
    let day = doy - (153 * mp + 2) / 5 + 1;
    let month = mp + if mp < 10 { 3 } else { -9 };
    let year = y + i64::from(month <= 2);
    DateParts {
        year: year as i32,
        month: month as u32,
        day: day as u32,
    }
}

fn wallet_rows(conn: &Connection) -> StorageResult<Vec<WalletAuditRow>> {
    let mut stmt = conn
        .prepare("SELECT id, system FROM wallets ORDER BY id")
        .map_err(sqlite_err)?;
    stmt.query_map([], |row| {
        Ok(WalletAuditRow {
            id: row.get(0)?,
            system: row.get(1)?,
        })
    })
    .map_err(sqlite_err)?
    .collect::<Result<Vec<_>, _>>()
    .map_err(sqlite_err)
}

fn transfer_rows(conn: &Connection) -> StorageResult<Vec<TransferAuditRow>> {
    let mut stmt = conn
        .prepare(
            "SELECT id, from_wallet_id, to_wallet_id, date, amount_original, currency,
                    rate_at_operation, amount_base
             FROM transfers
             ORDER BY id",
        )
        .map_err(sqlite_err)?;
    stmt.query_map([], |row| {
        Ok(TransferAuditRow {
            id: row.get(0)?,
            from_wallet_id: row.get(1)?,
            to_wallet_id: row.get(2)?,
            date: row.get(3)?,
            amount_original: row.get(4)?,
            currency: row.get(5)?,
            rate_at_operation: row.get(6)?,
            amount_base: row.get(7)?,
        })
    })
    .map_err(sqlite_err)?
    .collect::<Result<Vec<_>, _>>()
    .map_err(sqlite_err)
}

fn record_rows(conn: &Connection) -> StorageResult<Vec<RecordAuditRow>> {
    let mut stmt = conn
        .prepare(
            "SELECT id, type, date, wallet_id, transfer_id,
                    amount_original, currency, rate_at_operation, amount_base, category
             FROM records
             ORDER BY id",
        )
        .map_err(sqlite_err)?;
    stmt.query_map([], |row| {
        Ok(RecordAuditRow {
            id: row.get(0)?,
            record_type: row.get(1)?,
            date: row.get(2)?,
            wallet_id: row.get(3)?,
            transfer_id: row.get(4)?,
            amount_original: row.get(5)?,
            currency: row.get(6)?,
            rate_at_operation: row.get(7)?,
            amount_base: row.get(8)?,
            category: row.get(9)?,
        })
    })
    .map_err(sqlite_err)?
    .collect::<Result<Vec<_>, _>>()
    .map_err(sqlite_err)
}

fn mandatory_rows(conn: &Connection) -> StorageResult<Vec<MandatoryAuditRow>> {
    let mut stmt = conn
        .prepare(
            "SELECT id, amount_original, amount_base, date, auto_pay
             FROM mandatory_expenses
             ORDER BY id",
        )
        .map_err(sqlite_err)?;
    stmt.query_map([], |row| {
        Ok(MandatoryAuditRow {
            id: row.get(0)?,
            amount_original: row.get(1)?,
            amount_base: row.get(2)?,
            date: row.get(3)?,
            auto_pay: row.get(4)?,
        })
    })
    .map_err(sqlite_err)?
    .collect::<Result<Vec<_>, _>>()
    .map_err(sqlite_err)
}

fn tag_rows(conn: &Connection) -> StorageResult<Vec<TagAuditRow>> {
    let mut stmt = conn
        .prepare("SELECT id, name, usage_count FROM tags ORDER BY id")
        .map_err(sqlite_err)?;
    stmt.query_map([], |row| {
        Ok(TagAuditRow {
            id: row.get(0)?,
            name: row.get(1)?,
            usage_count: row.get(2)?,
        })
    })
    .map_err(sqlite_err)?
    .collect::<Result<Vec<_>, _>>()
    .map_err(sqlite_err)
}

fn record_tag_rows(conn: &Connection) -> StorageResult<Vec<RecordTagAuditRow>> {
    let mut stmt = conn
        .prepare("SELECT record_id, tag_id FROM record_tags ORDER BY record_id, tag_id")
        .map_err(sqlite_err)?;
    stmt.query_map([], |row| {
        Ok(RecordTagAuditRow {
            record_id: row.get(0)?,
            tag_id: row.get(1)?,
        })
    })
    .map_err(sqlite_err)?
    .collect::<Result<Vec<_>, _>>()
    .map_err(sqlite_err)
}

fn debt_rows(conn: &Connection) -> StorageResult<Vec<DebtAuditRow>> {
    let mut stmt = conn
        .prepare(
            "SELECT id, total_amount_minor, remaining_amount_minor, status FROM debts ORDER BY id",
        )
        .map_err(sqlite_err)?;
    stmt.query_map([], |row| {
        Ok(DebtAuditRow {
            id: row.get(0)?,
            total_amount_minor: row.get(1)?,
            remaining_amount_minor: row.get(2)?,
            status: row.get(3)?,
        })
    })
    .map_err(sqlite_err)?
    .collect::<Result<Vec<_>, _>>()
    .map_err(sqlite_err)
}

fn debt_payment_rows(conn: &Connection) -> StorageResult<Vec<DebtPaymentAuditRow>> {
    let mut stmt = conn
        .prepare(
            "SELECT id, debt_id, record_id, operation_type, principal_paid_minor, is_write_off
             FROM debt_payments
             ORDER BY id",
        )
        .map_err(sqlite_err)?;
    stmt.query_map([], |row| {
        Ok(DebtPaymentAuditRow {
            id: row.get(0)?,
            debt_id: row.get(1)?,
            record_id: row.get(2)?,
            operation_type: row.get(3)?,
            principal_paid_minor: row.get(4)?,
            is_write_off: row.get(5)?,
        })
    })
    .map_err(sqlite_err)?
    .collect::<Result<Vec<_>, _>>()
    .map_err(sqlite_err)
}

fn asset_rows(conn: &Connection) -> StorageResult<Vec<AssetAuditRow>> {
    let mut stmt = conn
        .prepare(
            "SELECT id, name, category, currency, is_active, created_at FROM assets ORDER BY id",
        )
        .map_err(sqlite_err)?;
    stmt.query_map([], |row| {
        Ok(AssetAuditRow {
            id: row.get(0)?,
            name: row.get(1)?,
            category: row.get(2)?,
            currency: row.get(3)?,
            is_active: row.get(4)?,
            created_at: row.get(5)?,
        })
    })
    .map_err(sqlite_err)?
    .collect::<Result<Vec<_>, _>>()
    .map_err(sqlite_err)
}

fn asset_snapshot_rows(conn: &Connection) -> StorageResult<Vec<AssetSnapshotAuditRow>> {
    let mut stmt = conn
        .prepare("SELECT id, asset_id, snapshot_date, value_minor, currency FROM asset_snapshots ORDER BY id")
        .map_err(sqlite_err)?;
    stmt.query_map([], |row| {
        Ok(AssetSnapshotAuditRow {
            id: row.get(0)?,
            asset_id: row.get(1)?,
            snapshot_date: row.get(2)?,
            value_minor: row.get(3)?,
            currency: row.get(4)?,
        })
    })
    .map_err(sqlite_err)?
    .collect::<Result<Vec<_>, _>>()
    .map_err(sqlite_err)
}

fn goal_rows(conn: &Connection) -> StorageResult<Vec<GoalAuditRow>> {
    let mut stmt = conn
        .prepare(
            "SELECT id, title, target_amount_minor, currency, target_date, is_completed, created_at
             FROM goals
             ORDER BY id",
        )
        .map_err(sqlite_err)?;
    stmt.query_map([], |row| {
        Ok(GoalAuditRow {
            id: row.get(0)?,
            title: row.get(1)?,
            target_amount_minor: row.get(2)?,
            currency: row.get(3)?,
            target_date: row.get(4)?,
            is_completed: row.get(5)?,
            created_at: row.get(6)?,
        })
    })
    .map_err(sqlite_err)?
    .collect::<Result<Vec<_>, _>>()
    .map_err(sqlite_err)
}

fn existing_record_ids(conn: &Connection) -> StorageResult<HashSet<i64>> {
    let mut stmt = conn.prepare("SELECT id FROM records").map_err(sqlite_err)?;
    stmt.query_map([], |row| row.get::<_, i64>(0))
        .map_err(sqlite_err)?
        .collect::<Result<HashSet<_>, _>>()
        .map_err(sqlite_err)
}

fn record_debt_links(conn: &Connection) -> StorageResult<HashMap<i64, i64>> {
    let mut stmt = conn
        .prepare("SELECT id, related_debt_id FROM records WHERE related_debt_id IS NOT NULL")
        .map_err(sqlite_err)?;
    stmt.query_map([], |row| Ok((row.get::<_, i64>(0)?, row.get::<_, i64>(1)?)))
        .map_err(sqlite_err)?
        .collect::<Result<HashMap<_, _>, _>>()
        .map_err(sqlite_err)
}

#[cfg(test)]
mod tests {
    use super::*;
    use rusqlite::Connection;
    use std::fs;
    use std::time::{SystemTime, UNIX_EPOCH};

    fn test_db_path(name: &str) -> String {
        let nanos = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .expect("clock")
            .as_nanos();
        std::env::temp_dir()
            .join(format!("ledgera_audit_{name}_{nanos}.db"))
            .to_string_lossy()
            .into_owned()
    }

    fn init_clean_db(db_path: &str) {
        let conn = Connection::open(db_path).expect("open");
        conn.execute_batch(
            "
            CREATE TABLE wallets (id INTEGER PRIMARY KEY, system INTEGER NOT NULL, is_active INTEGER NOT NULL DEFAULT 1);
            CREATE TABLE transfers (
                id INTEGER PRIMARY KEY, from_wallet_id INTEGER, to_wallet_id INTEGER, date TEXT,
                amount_original REAL, currency TEXT, rate_at_operation REAL, amount_base REAL
            );
            CREATE TABLE records (
                id INTEGER PRIMARY KEY, type TEXT, date TEXT, wallet_id INTEGER, transfer_id INTEGER,
                related_debt_id INTEGER, amount_original REAL, currency TEXT,
                rate_at_operation REAL, amount_base REAL, category TEXT
            );
            CREATE TABLE mandatory_expenses (
                id INTEGER PRIMARY KEY, amount_original REAL, amount_base REAL, date TEXT, auto_pay INTEGER
            );
            CREATE TABLE tags (id INTEGER PRIMARY KEY, name TEXT, usage_count INTEGER);
            CREATE TABLE record_tags (record_id INTEGER, tag_id INTEGER);
            CREATE TABLE debts (
                id INTEGER PRIMARY KEY, total_amount_minor INTEGER, remaining_amount_minor INTEGER, status TEXT
            );
            CREATE TABLE debt_payments (
                id INTEGER PRIMARY KEY, debt_id INTEGER, record_id INTEGER, operation_type TEXT,
                principal_paid_minor INTEGER, is_write_off INTEGER
            );
            CREATE TABLE assets (
                id INTEGER PRIMARY KEY, name TEXT, category TEXT, currency TEXT, is_active INTEGER, created_at TEXT
            );
            CREATE TABLE asset_snapshots (
                id INTEGER PRIMARY KEY, asset_id INTEGER, snapshot_date TEXT, value_minor INTEGER, currency TEXT
            );
            CREATE TABLE goals (
                id INTEGER PRIMARY KEY, title TEXT, target_amount_minor INTEGER, currency TEXT,
                target_date TEXT, is_completed INTEGER, created_at TEXT
            );
            INSERT INTO wallets (id, system) VALUES (1, 1), (2, 0);
            INSERT INTO transfers VALUES (1, 1, 2, '2026-03-04', 100.0, 'KZT', 1.0, 100.0);
            INSERT INTO records VALUES
                (1, 'income', '2026-03-02', 1, NULL, NULL, 200.0, 'KZT', 1.0, 200.0, 'Salary'),
                (2, 'expense', '2026-03-03', 1, NULL, NULL, 50.0, 'KZT', 1.0, 50.0, 'Food'),
                (3, 'expense', '2026-03-04', 1, 1, NULL, 100.0, 'KZT', 1.0, 100.0, 'Transfer'),
                (4, 'income', '2026-03-04', 2, 1, NULL, 100.0, 'KZT', 1.0, 100.0, 'Transfer');
            INSERT INTO mandatory_expenses VALUES (1, 75.0, 75.0, NULL, 0);
            INSERT INTO assets VALUES (1, 'Broker', 'bank', 'KZT', 1, '2026-03-01');
            INSERT INTO asset_snapshots VALUES (1, 1, '2026-03-05', 150000, 'KZT');
            INSERT INTO goals VALUES (1, 'Emergency Fund', 500000, 'KZT', '2026-12-31', 0, '2026-03-02');
            ",
        )
        .expect("schema");
    }

    #[test]
    fn clean_fixture_returns_15_ok_findings() {
        let db_path = test_db_path("clean");
        init_clean_db(&db_path);
        let findings = audit_run(&db_path).expect("audit");
        assert_eq!(findings.len(), 15);
        assert!(findings.iter().all(|finding| finding.severity == "ok"));
        fs::remove_file(db_path).ok();
    }

    #[test]
    fn amount_inconsistency_reports_warning() {
        let db_path = test_db_path("amount");
        init_clean_db(&db_path);
        let conn = Connection::open(&db_path).expect("open");
        conn.execute("UPDATE records SET amount_base = 200.05 WHERE id = 1", [])
            .expect("update");
        let findings = audit_run(&db_path).expect("audit");
        assert!(findings.iter().any(|finding| {
            finding.check == "amount_consistency" && finding.severity == "warning"
        }));
        fs::remove_file(db_path).ok();
    }

    #[test]
    fn transfer_pair_error_is_detected() {
        let db_path = test_db_path("transfer");
        init_clean_db(&db_path);
        let conn = Connection::open(&db_path).expect("open");
        conn.execute("DELETE FROM records WHERE id = 4", [])
            .expect("delete");
        let findings = audit_run(&db_path).expect("audit");
        assert!(findings.iter().any(
            |finding| finding.check == "transfer_pair_integrity" && finding.severity == "error"
        ));
        fs::remove_file(db_path).ok();
    }
}
