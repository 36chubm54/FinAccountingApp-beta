# FinAccountingApp

Graphical application for personal financial accounting with multicurrency, categories and reports.

## 📋 Contents

- [Quick start](#-quick-start)
- [Using the application](#️-using-the-application)
- [Project architecture](#️-project-architecture)
- [Software API](#-software-api)
- [File structure](#-file-structure)
- [Tests](#-tests)
- [Supported currencies](#-supported-currencies)

---

## 🚀 Quick start

### System requirements

- Python 3.10+
- pip

### Installation

```bash
# Go to the project directory
cd "Проект ФУ/project"

# Create a virtual environment
python -m venv .venv

# Activation (Windows PowerShell)
.\.venv\Scripts\Activate.ps1

# Activation (Windows CMD)
.venv\Scripts\activate.bat

# Activation (Linux/macOS)
source .venv/bin/activate

# Install runtime dependencies
pip install -r requirements.txt

# Install dev dependencies (tests, coverage)
pip install -r requirements-dev.txt
```

### First launch

```bash
python main.py
```

After launch, the graphical window of the Financial Accounting application will open.

---

## 🖥️ Using the application

### Main window

After running `python main.py` from the `project` directory, a window will open with control tabs and an infographic block.
The bottom of the window now includes a persistent status bar with the app version, currency-rate status, and an `Online` toggle that can be switched at runtime without restarting.

Tabs and actions:

- `Infographics` — displays infographics (pie charts, histograms) with the ability to filter by month/year.
- `Operations` — management of records and transfers (adding, editing, deleting, importing/exporting).
- `Reports` — report generation, export.
- `Analytics` — financial analytics for an arbitrary period (dashboard, categories, monthly report).
- `Budget` — category budgets with arbitrary date ranges, pace tracking, and live progress.
- `Distribution` — monthly net-income distribution structure with fixed rows and snapshot history.
- `Settings` — management of mandatory expenses and wallets.

Infographics:

- Pie chart of expenses by category with month filter.
- Histogram of income/expenses by day of the month.
- Histogram of income/expenses by month of the year.

Income is displayed in green, expenses in red. For a pie chart, small categories are aggregated into "Other". The list of categories in the legend scrolls. Records with the "Transfer" category have been excluded to improve analysis accuracy and consistency.

### Analytics tab

Financial analytics for an arbitrary period.

- **Dashboard** — key metrics: net worth, savings rate, burn rate, avg monthly income, avg monthly expenses, year income, year expense, and cost per day/hour/minute.
- **Net Worth Timeline** — line chart of net worth by month.
- **Category Breakdown** — expenses and income by category (tables + expenses pie chart).
- **Monthly Report** — table with income, expenses, cashflow and savings rate by month.

The period filter uses `YYYY-MM-DD` in the `From` / `To` fields. Transfers are excluded from calculations.
The Dashboard now includes an `ⓘ` tooltip that explains the metric formulas.
`Year expense` is calculated as calendar-year expenses up to the selected end date, and `Cost per day/hour/minute` now derives from that year-to-date expense instead of an annualized burn rate.

> **Note:** After launching the application, mandatory payments are automatically applied with a detailed GUI message displayed.
> If online mode was saved previously, the application restores it on startup and refreshes currency rates in the background.

### Budget tab

Planning and tracking category budgets across arbitrary date ranges.

- `New Budget` form: `Category`, `From`, `To`, `Limit (KZT)`, and `Include mandatory expenses`.
- Budget Treeview columns: `Category`, `Period`, `Limit`, `Spent`, `Remaining`, `Usage %`, `Pace`, `Status`, `Include mandatory`.
- Pace states: `on_track`, `overpace`, `overspent`.
- Period states: `future`, `active`, `expired`.
- The progress canvas is displayed below the table:
  colored bar = share of budget spent, blue vertical = share of time elapsed.
- Multiple budgets per category are allowed as long as their date ranges do not overlap.

### Distribution tab

Monthly net-income allocation structure and month-by-month history view.

- The left `Distribution Structure` panel manages top-level items/subitems with percentages and optional groups.
- The right `Distribution Table` shows `Month`, `Fixed`, `Net income`, and calculated item/subitem allocation columns.
- `Fix Row` freezes or unfreezes a month row; auto-fixed closed months are protected from manual unfix.
- When frozen rows are requested, the service auto-freezes closed past months.
- Validation requires top-level items to total `100%`, and subitems within an item to total `100%` when present.

### Adding income/expense

1. Open the `Operations` tab.
2. In the `Add operation` block, select the type of operation (`Income` or `Expense`).
3. Enter the date in the format `YYYY-MM-DD` (the date cannot be in the future).
4. Enter the amount.
5. Specify the currency (default is `KZT`).
6. Specify a category (default is `General`).
   The category field is an editable `Combobox`: for `Income` it suggests known income categories, for `Expense` it suggests expense categories; manual input is still allowed.
7. Optionally fill in `Description`.
8. Click `Save`.

The amount is converted into the base currency `KZT` at the current rates of the currency service. Once an entry is added, the list is automatically updated.

### Adding a transfer

1. Open the `Operations` tab.
2. In the `Transfer` block, select `From wallet` and `To wallet`.
3. Enter the date in the format `YYYY-MM-DD` (the date cannot be in the future and cannot be earlier than UNIX time).
4. Enter the amount.
5. Specify the currency (default is `KZT`).
6. Optionally enter `Commission` and its currency.
7. Optionally fill in `Description`.
8. Click `Save`.

### Deleting an entry

1. Open the `Operations` tab.
2. Select an entry from the list.
3. Click `Delete Selected`. A deletion message appears with the index of the entry or ID of the transfer.

### Delete all entries

1. Open the `Operations` tab.
2. In the `List of operations` block, select an entry from the list.
3. Click `Delete All Records` and confirm the deletion. The entries will be permanently deleted and the list of entries will be updated.

### Inline record editing

1. Open the `Operations` tab.
2. Select a record in the list.
3. Click `Edit`.
4. Change `Date`, `Wallet`, `Amount KZT`, `Category`, and optionally `Description`.
5. Click `Save`.

The update is applied through the immutable domain model: a new record instance is created, `rate_at_operation` is recalculated automatically, and `description` remains optional. The date is validated (`YYYY-MM-DD`, not in the future and not earlier than UNIX time) and the wallet must be active. Transfer-linked records and records with category `"Transfer"` cannot be edited.

### Report generation

1. Open the `Reports` tab.
2. Enter filters (optional):
    - `Period` — period start (`YYYY`, `YYYY-MM`, `YYYY-MM-DD`).
    - `Period end` — period end (`YYYY`, `YYYY-MM`, `YYYY-MM-DD`).
    - `Category` — filter by category.
3. Choose one wallet for generating the report on it or all wallets.
4. Optionally enable `Group by category` — grouped view (double-click a category to open its details; use `Back` to return to the summary).
5. Choose `Totals mode`:
    - `On fixed rate` — totals based on fixed `amount_kzt` (operation-time rate).
    - `On current rate` — totals on current FX rates (`CurrencyService`).
6. Click `Generate`.

On the right, the “Monthly summary” block shows month-level income/expense aggregates.

Export report:

- Formats: `CSV`, `XLSX`, `PDF`.
- Report title includes the selected range:
  `Transaction statement (<start_date> - <end_date>)`.
- If `Period end` is not provided, current date is used as the period end.
- In addition to the main records, a `Yearly Report` sheet with a monthly summary is added to `XLSX`. The `By Category` sheet is created only when grouping adds a distinct summary rather than duplicating an already filtered report.
- `XLSX` now ships as a more readable export: styled header/total rows, `freeze panes`, `auto filter`, auto-sized columns, and numeric amount cells instead of stringified totals.
- In `PDF` the monthly summary remains, and after the main statement, category tables are added; if the report is already filtered to a single category, the duplicate grouped section is skipped.
- When `Group by category` is enabled, exporting the summary view uses grouped report export in `CSV` / `XLSX` / `PDF`.

### Opening Balance in Filtered Reports

- `Initial balance` is the starting balance of the whole history and does not depend on filters.
- `Opening balance` is the balance at the beginning of the selected period and is calculated dynamically.
- For `YYYY`, period start is `YYYY-01-01`.
- For `YYYY-MM`, period start is `YYYY-MM-01`.
- For `YYYY-MM-DD`, period start is the provided date.
- The period filter cannot point to a future date (for all supported formats).

### Managing mandatory expenses

In the `Settings` tab, in the `Mandatory Expenses` block, the following operations are available:

- `Add` — add a mandatory expense.
- `Edit` — inline edit the selected template.
- `Delete` — delete the selected one.
- `Delete All` — delete everything.
- `Add to Records` — add the selected expense to records with the specified date.
- File format selector for import/export.
- `Import` — import of mandatory expenses.
- `Export` — export of mandatory expenses.

Mandatory expense fields:

- `Wallet`, `Amount`, `Currency`, `Category` (default `Mandatory`), `Description` (required), `Period` (`daily`, `weekly`, `monthly`, `yearly`).

#### Mandatory expense template fields

- `Date` (optional, `YYYY-MM-DD`) — if provided, the `auto_pay` flag is set automatically
- `auto_pay` — derived from `date`: non-empty → `True`, empty → `False`

`auto_pay` behavior:

- Applies to all templates with a non-empty `date` (i.e. `auto_pay=True`).
- Auto-pay does not start before the template `date` (anchor date).
- Frequency is defined by `period`:
  `daily` — 1 record per day;
  `weekly` — 1 record per week on the same weekday as `date`;
  `monthly` — 1 record per month with the same `DD` (clamped to month end);
  `yearly` — 1 record per year with the same `MM-DD` (clamped for missing days, e.g. Feb 29).

#### Inline template editing

1. Select a template in the list.
2. Click `Edit`.
3. Change `Amount KZT`, `Date`, `Period` and/or `Wallet`.
4. Click `Save`.

`amount_kzt` is validated numerically; `date` is validated against the `YYYY-MM-DD` format.
`auto_pay` is recalculated automatically when the date changes.

Import/export of mandatory expenses:

- Import: `CSV`, `XLSX`.
- Export: `CSV`, `XLSX`.
- Runtime templates in SQLite can now store `date` and derived `auto_pay`.
- The `date` field for `mandatory_expenses` is now preserved in `CSV`/`XLSX` import-export.

### Finance Audit

In the `Settings` tab, the `Finance Audit` block provides a `Run Audit` button.

Clicking it runs a read-only diagnostic of the SQLite database.
The audit checks:

- System wallet sanity (`id=1` exists and has `system=1`)
- Transfer pair integrity (exactly 2 linked records: income + expense per transfer)
- Alignment of `transfers` aggregates with linked `expense`/`income` records
- Transfer-linked record invariants (consistency of wallet IDs, amounts, currency, and categories)
- Amount consistency (amount_kzt equals amount_original × rate_at_operation)
- Positivity of amount_original and amount_kzt in records / transfers / mandatory_expenses
- Rate positivity (rate_at_operation > 0 for all records)
- Date validity (YYYY-MM-DD format, not in the future)
- Currency code presence (currency not empty)
- Mandatory template date/auto_pay consistency (`auto_pay` matches whether `date` is provided)

Results are shown in a modal dialog grouped into three sections:
`Errors`, `Warnings`, `Passed`. The database is never modified.

### Balance Engine

`BalanceService` is a read-only analytical service that derives financial state from the record history.
Balance is never stored in the database — it is always computed dynamically.

Available methods:

- `get_wallet_balance(wallet_id, date=None)` — wallet balance (optionally at a given date)
- `get_wallet_balances(date=None)` — balances of all active wallets
- `get_total_balance(date=None)` — total system net worth
- `get_cashflow(start_date, end_date)` — income, expenses, and net cashflow for a period
- `get_income(start_date, end_date)` — income for a period
- `get_expenses(start_date, end_date)` — expenses for a period

The service is strictly read-only and never modifies the database.
Transfer records (`category='Transfer'`) are excluded from cashflow calculations to prevent double-counting.

### Timeline Engine

Analytical service that builds historical financial dynamics.

| Method                                       | Description                                    |
| -------------------------------------------- | ---------------------------------------------- |
| `get_net_worth_timeline()`                   | Net worth (KZT) at the end of each month       |
| `get_monthly_cashflow(start_date, end_date)` | Monthly income, expenses, and cashflow         |
| `get_cumulative_income_expense()`            | Running totals of income and expenses by month |

All methods are read-only. Transfers (`transfer_id IS NOT NULL`) are excluded from cashflow calculations
to prevent double-counting; they are included in net worth (expense + income = 0, neutral).
Initial balances (`wallets.initial_balance`) are included in every timeline point.

### Metrics Engine

Analytical service for calculating financial metrics on the fly.

| Method                                          | Description                                   |
| ----------------------------------------------- | --------------------------------------------- |
| `get_savings_rate(start, end)`                  | Savings rate (%) for a custom period          |
| `get_burn_rate(start, end)`                     | Average daily expense (KZT)                   |
| `get_spending_by_category(start, end)`          | Expenses by category, sorted descending       |
| `get_income_by_category(start, end)`            | Income by category, sorted descending         |
| `get_top_expense_categories(start, end, top_n)` | Top N expense categories                      |
| `get_monthly_summary(start, end)`               | Monthly income/expenses/cashflow/savings rate |

All methods are read-only. Transfers are excluded from all calculations (`transfer_id IS NULL`).
Metrics are computed via SQL aggregates with no intermediate storage.

### Importing financial records

Import is performed via `Import` in the `Operations` tab.

Import architecture:

- `ImportService -> FinancialController (FinanceService) -> RecordRepository/Storage`.
- Import does not create records directly through `JsonStorage/SQLiteStorage`.
- Transfers are created only via `create_transfer(...)` (the `1 transfer = 2 record` invariant is preserved).
- Before any write, the application performs a dry-run: full parse and validation without touching SQLite.
- In the `Operations` tab, the dry-run result is shown in a modal preview dialog; the user either confirms or cancels the real import.
- The real import runs inside the service transaction and returns a structured `ImportResult`.
- `Full Backup` preserves source `amount_kzt` and `rate_at_operation` values.
- `Current Rate` recalculates values using `CurrencyService.get_rate(...)`.
- Parser-level guardrails are enabled (file size, row limit, CSV field size).
- Invalid rows are not written to the database and are returned in `ImportResult.errors`; valid rows may still be imported.
- If the dry-run finds no valid rows (`imported == 0`), the preview dialog does not allow the user to continue.
- `initial_balance` is allowed only once per import file. Duplicate rows are reported in the preview/result.
- `wallet_id` in import data must be a positive integer (no fractional part).
- Non-numeric and non-finite values (`NaN`, `inf`) in numeric import fields are rejected.

Formats:

- Through the `Operations` tab UI: `CSV`, `XLSX`.
- At the controller/service level, `JSON` is also supported.
- Import pipeline: `parser -> dry-run validation -> user confirmation -> SQLite transaction`.
- For `CSV/XLSX`, the real import replaces runtime data with valid rows from the file; invalid rows remain only in the import report.
- For readonly `JSON` snapshots, `force=True` is required; readonly/checksum validation happens before the commit stage.
- `JSON` full backup can now include `distribution_items`, `distribution_subitems`, and `distribution_snapshots`; on import they are restored into SQLite when the repository supports the Distribution System.
- For `JSON` full backup, distribution structure is validated strictly: malformed item/subitem payloads now fail the import instead of being skipped silently.

Data format:

- **CSV/XLSX data (import/export):**  
  `date,type,wallet_id,category,amount_original,currency,rate_at_operation,amount_kzt,description,period,transfer_id,from_wallet_id,to_wallet_id`.
- `wallet_id` — identifier of the wallet in which the operation was made.
- `transfer_id` — identifier of the transfer between wallets.
- `from_wallet_id` — identifier of the source wallet in a transfer.
- `to_wallet_id` — identifier of the target wallet in a transfer.
- Legacy import is supported (old files with the `amount` field or the `Amount (KZT)` column).
- All existing entries are replaced with data from the file.

Important:

- `CSV/XLSX report` and `CSV/XLSX data` are different formats.
- Report `CSV/XLSX` is read-only by the user and **should not** be used as a data source for import.

### ImportPolicy

There are 3 modes available for importing records:

- `Full Backup` (`ImportPolicy.FULL_BACKUP`)  
  Used for full import with a fixed transaction rate. Expected string format:
  `date,type,wallet_id,category,amount_original,currency,rate_at_operation,amount_kzt,description,period,transfer_id,from_wallet_id,to_wallet_id`.
- `Current Rate` (`ImportPolicy.CURRENT_RATE`)  
  For each imported line, the rate is taken at the time of import through `CurrencyService.get_rate(currency)`, and `rate_at_operation` and `amount_kzt` are recalculated and fixed again.
- `Legacy Import` (`ImportPolicy.LEGACY`)
  The old `date,type,category,amount` format is automatically migrated to the new one:
  `currency="KZT"`, `rate_at_operation=1.0`, `amount_kzt=amount`.

All modes perform line-by-line validation and return `ImportResult`
(`imported`, `skipped`, `errors`, `dry_run`).

### Dry-run Mode

- Before writing to the database, the application performs a full dry-run: the file is parsed and validated without modifying any records.
- A preview dialog shows the number of records to import, skipped rows, and any errors.
- The user explicitly confirms or cancels before data is changed.

### Backup

Full backup is implemented in `JSON` format in two modes:

- `Snapshot backup` (default):
  - root object: `meta` + `data`;
  - `meta.readonly=true`, `meta.checksum` (SHA256 of `data`);
  - checksum is computed deterministically via `json.dumps(data, sort_keys=True, ensure_ascii=False, separators=(",", ":"))`.
- `Technical backup` (`readonly=False`):
  - legacy-compatible JSON without `meta` and checksum;
  - used by the standard import pipeline without readonly protection.
- Snapshot metadata:
  - `meta.app_version` is taken from `version.py`;
  - `meta.storage` is provided by the caller and is no longer hardcoded to `sqlite`.
  - GUI full-backup export from `Settings` marks the source as `meta.storage="sqlite"`.
- The `Settings` tab contains the following buttons:
  - `Export Full Backup`
  - `Import Full Backup`
- Importing a readonly snapshot requires `force=True` (or force confirmation in UI).

Backup restores:

- wallets with fields `id/name/currency/balance`;
- all records with fields `type/date/wallet_id/transfer_id/category/amount_original/currency/rate_at_operation/amount_kzt/category/description`;
- all mandatory expenses with `date/description/period`;
- distribution structure: `distribution_items` and `distribution_subitems`;
- frozen `distribution_snapshots` with visible column layout and values;
- all transfers between wallets.

Additionally:

- JSON export now writes atomically via a temporary file + `os.replace`, preventing partially written backup files;
- startup SQLite → JSON export uses already frozen distribution months and can skip auto-freeze inside the background export thread.

### FX Revaluation

`Report` supports:

- `net_worth_fixed()` — net asset value at the time of recording;
- `net_worth_current()` — net asset value at the current rate;
- `total_fixed()` — accounting total at the exchange rate on the transaction date;
- `total_current(currency_service)` — total at the current rate;
- `fx_difference(currency_service)` — revaluation (`current - fixed`);
- `total()` — alias for `total_fixed()` (backward compatibility).

### Migration

Rules for migrating old formats:

- legacy `amount` -> `amount_original`;
- missing currency -> `KZT`;
- missing course -> `1.0`;
- missing `amount_kzt` -> calculated according to the import policy;
- invalid lines are skipped and included in the error list.

### Data storage

SQLite (`finance.db`) is the only runtime storage.
JSON (`data.json`) is no longer used as an application backend and remains only for:

- JSON import;
- JSON export;
- backups.

During startup, after SQLite integrity validation, the current runtime state is exported to `data.json`.
This export now preserves `mandatory_expenses.date`, the Distribution System structure, and frozen `distribution_snapshots`.

A dedicated `storage/` layer is used for data access:

- `storage/base.py` — `Storage` contract (data-access operations only).
- `storage/json_storage.py` — JSON adapter for import/export/backup only.
- `storage/sqlite_storage.py` — `SQLiteStorage` based on standard `sqlite3`.
- `db/schema.sql` — SQL schema for `wallets`, `records`, `transfers`, `mandatory_expenses`, `budgets`, and `distribution_*`.

### JSON -> SQLite migration

Use `migrate_json_to_sqlite.py` for safe data migration.

Run examples:

```bash
# Validation only, no write
python migrate_json_to_sqlite.py --dry-run

# Full migration
python migrate_json_to_sqlite.py --json-path data.json --sqlite-path finance.db
```

What the script does:

- loads source data via `JsonStorage`;
- writes to SQLite in one explicit transaction with strict order:
  `wallets -> distribution_items -> distribution_subitems -> transfers -> records -> mandatory_expenses -> distribution_snapshots`;
- preserves existing `id` values (or builds `old_id -> new_id` mapping when ids are auto-generated);
- populates precision fields `*_minor` and `rate_at_operation_text` while writing;
- for full backup, strictly validates `distribution_items` / `distribution_subitems` and aborts migration on malformed payloads;
- validates integrity and compares balances/`net worth`;
- performs `rollback` on any error or mismatch.
- is safe to rerun: if SQLite already has an equivalent dataset, migration is skipped without failure.

### Runtime storage configuration

`config.py` defines the paths:

- `SQLITE_PATH = "finance.db"`
- `JSON_PATH = "data.json"`
- `JSON_BACKUP_KEEP_LAST = 30` — how many timestamped JSON backups to keep in `project/backups/` (older ones are pruned on startup after creating a new backup).
- `LAZY_EXPORT_SIZE_THRESHOLD = 50 * 1024 * 1024` — SQLite size threshold (in bytes) above which SQLite → JSON export may run in the background.

Paths are resolved relative to the `project` directory, so `finance.db` and `data.json` are created inside `project` even when launched from another folder.

Initialization is handled by `bootstrap.py`:

- the application always uses SQLite as runtime storage;
- if `finance.db` is missing, the database and schema are created on startup;
- the bootstrap ensures that a system wallet exists;
- SQLite internal integrity is validated on startup:
  `PRAGMA foreign_key_check`, transfer linkage (`exactly 2 linked records: income+expense`),
  no orphan records, and no CHECK-like violations;
- after a successful integrity check, a lazy SQLite → `data.json` export is performed:
  export runs only if `data.json` is missing or older than `finance.db`;
  for large databases, export may run in a background thread (non-blocking UI);
- JSON bootstrap and direct runtime work against `data.json` have been removed.

SQLite behavior by identifiers:

- For work operations, `INSERT` is performed without manual transmission of `id`; `id` is generated by SQLite.
- For scenarios of complete data replacement (`replace_all_data`, backup import, normalization after import), entities are reindexed into the range `1..N`.
- With this reindexing, links (`wallet_id`, `transfer_id`, `from_wallet_id`, `to_wallet_id`) are remapped atomically to maintain the integrity of the links.
- After clearing tables, `sqlite_sequence` is reset so that new records start at `1` again.
- Data equality checks before/after import should be performed on business fields and invariants, not on specific `id` values.

SQLite behavior for money fields:

- Monetary values are stored in both `REAL` columns and exact integer minor-units (`*_minor`).
- FX rates additionally store canonical text in `rate_at_operation_text`.
- `SQLiteStorage` auto-adds and backfills these precision columns for existing databases.

---

## 🏗️ Project architecture

The project follows a layered architecture:

- `domain/` — business models and rules (records, budgets, reports, data audit, date/period validation, currencies, wallets, transfers).
- `app/` — use cases, including audit execution, and the currency service adapter.
- `infrastructure/` — JSON and SQLite `RecordRepository` implementations.
- `storage/` — storage abstraction and JSON/SQLite adapters.
- `db/` — SQLite SQL schema.
- `bootstrap.py` — SQLite initialization and startup validation.
- `backup.py` — JSON backup and SQLite -> JSON export.
- `config.py` — runtime SQLite and JSON import/export paths.
- `services/` — service layer for import orchestration, read-only SQLite audit, budgets, and analytics.
- `utils/` — import/export and preparation of data for graphs.
- `gui/` — GUI layer (Tkinter).

Data flow for GUI:

- UI (Tkinter) → `gui/controllers.py` → `app/use_cases.py` → `infrastructure/sqlite_repository.py` → `finance.db`.

Domain relationships:

- `Record` belongs to `Wallet` through `record.wallet_id`.
- `Transfer` links two records (`expense`/`income`) through `transfer_id`.
- Transfer commission is stored as a separate `Expense` (`Commission` category) and is not part of the linked transfer record pair.

### Immutable Domain Model

- `Record` is immutable (`@dataclass(frozen=True)`), including the `id` field.
- Any record update creates a new object instead of mutating the existing one.
- Amount edits use `with_updated_amount_kzt(new_amount_kzt)`.
- This protects financial data integrity and prepares the architecture for SQLite migration.

---

## 📝 Software API

Below are the key classes and functions synchronized with the actual code.

### Domain

`domain/currency.py`

- `CurrencyService` — conversion of currencies to base (`KZT`).

`domain/audit.py`

- `AuditSeverity` — severity enum for audit results (`ok`, `warning`, `error`).
- `AuditFinding(check, severity, message, detail="")` — a single audit observation.
- `AuditReport(findings, db_path)` — full audit result with grouped `errors`, `warnings`, and `passed`.
- `summary()` — compact human-readable audit summary.

`domain/errors.py`

- `DomainError` — domain error (thrown when domain invariants are violated).

`domain/import_policy.py`

- `ImportPolicy` — import policy (enum).

`domain/import_result.py`

- `ImportResult(imported, skipped, errors, dry_run=False)` — immutable result of a dry-run or real import (`errors` is stored as a `tuple[str, ...]`).
- `summary()` — compact result string; adds the `[DRY-RUN]` prefix for previews.

`domain/records.py`

- `Record` — base record (abstract class). It includes mandatory `wallet_id` and optional `transfer_id`.
- `Record.id` — mandatory record identifier.
- Money fields and `rate_at_operation` are normalized via `utils.money` on construction.
- `Record.with_updated_amount_kzt(new_amount_kzt)` — returns a new record instance with recalculated `rate_at_operation` and money quantization.
- `IncomeRecord` — income.
- `ExpenseRecord` — expense.
- `MandatoryExpenseRecord` — mandatory expense with `description` and `period`.

`domain/budget.py`

- `Budget` — immutable category budget model with date range and spending limit.
- `BudgetResult` — live tracking result: spent, remaining, usage/time percentage, pace/status.
- `BudgetStatus` — `future` / `active` / `expired`.
- `PaceStatus` — `on_track` / `overpace` / `overspent`.
- `compute_pace_status(...)` — derives the pace state from spent/limit/time inputs.

`domain/reports.py`

- `Report(records, initial_balance=0.0)` — report.
- `total_fixed()` — total at the transaction rate (accounting mode).
- `total_current(currency_service)` — total at the current exchange rate.
- `fx_difference(currency_service)` — exchange rate difference.
- `total()` — alias `total_fixed()` for backwards compatibility.
- `opening_balance(start_date)` — computes period start balance: `initial_balance + all records with date < start_date`.
- `filter_by_period(prefix)` — filtering by date prefix.
- `filter_by_period_range(start_prefix, end_prefix)` — filtering by date range.
- `filter_by_category(category)` — filtering by category.
- `grouped_by_category()` — grouping by categories while preserving report context (`balance_label`, period range).
- `display_records()` / `sorted_display_records()` — records intended for UI display (transfer legs excluded from the report view).
- `sorted_by_date()` — sorting by date.
- `net_profit_fixed()` — net profit at fixed exchange rates.
- `monthly_income_expense_rows(year=None, up_to_month=None)` — monthly aggregates.
- `to_csv(filepath)` and `from_csv(filepath)` — report export and backward-compatible import.

`domain/wallets.py`

- `Wallet` — wallet (`allow_negative`, `is_active`).

`domain/transfers.py`

- `Transfer` — wallet-to-wallet transfer aggregate.
- Money fields and FX rate are normalized to the configured money/rate scale.

`domain/validation.py`

- `parse_ymd(value)` — parsing and validating the date `YYYY-MM-DD`.
- `ensure_not_before_unix(date)` — prohibition of dates earlier than UNIX time.
- `ensure_not_future(date)` — prohibition of future dates.
- `ensure_valid_period(period)` — period validation.
- `parse_report_period_start(value)` — validates report period filter (`YYYY`/`YYYY-MM`/`YYYY-MM-DD`) and returns period start date while rejecting future dates.
- `parse_report_period_end(value)` — validates report period end (`YYYY`/`YYYY-MM`/`YYYY-MM-DD`) and returns period end date while rejecting future dates.

### Application

`app/services.py`

- `CurrencyService(rates=None, base="KZT", use_online=False)` - adapter for domain service.
- When `use_online=True`, it attempts to load National Bank of Kazakhstan rates on startup and caches them in `currency_rates.json`.
- Supports runtime switching via `set_online(enabled)`, the `is_online` flag, the `last_fetched_at` timestamp, and manual refresh through `refresh_rates()`.
- In the GUI, online mode is controlled by the global bottom status-bar toggle and persisted between sessions via `schema_meta`.

`app/use_cases.py`

- `CreateIncome.execute(date, wallet_id, amount, currency, category="General", description="", amount_kzt=None, rate_at_operation=None)`.
- `CreateExpense.execute(date, wallet_id, amount, currency, category="General", description="", amount_kzt=None, rate_at_operation=None)`.
- `GenerateReport.execute(wallet_id=None)` → `Report` taking into account the initial balance.
- `CreateWallet.execute(name, currency, initial_balance, allow_negative=False)` — creating a new wallet.
- `GetWallets.execute()` — all wallets.
- `GetActiveWallets.execute()` — active wallets only.
- `SoftDeleteWallet.execute(wallet_id)` — safe wallet soft delete.
- `CalculateWalletBalance.execute(wallet_id)` — calculating wallet balance.
- `CalculateNetWorth.execute_fixed()` — calculating net worth at fixed exchange rates.
- `CalculateNetWorth.execute_current()` — calculating net worth at current exchange rates.
- `CreateTransfer.execute(from_wallet_id, to_wallet_id, transfer_date, amount_original, currency, description="", commission_amount=0.0, commission_currency=None, amount_kzt=None, rate_at_operation=None)` — creating a transfer between wallets.
- `DeleteTransfer.execute(transfer_id)` — atomic cascade deletion of a transfer aggregate.
- `DeleteRecord.execute(index)`.
- `DeleteAllRecords.execute()`.
- `ImportFromCSV.execute(filepath)` — import and complete replacement of records (CSV, `ImportPolicy.FULL_BACKUP`).
- `CreateMandatoryExpense.execute(wallet_id=1, amount, currency, category, description, period, date="", amount_kzt=None, rate_at_operation=None)`.
- `ApplyMandatoryAutoPayments.execute(today=None)` — creates due mandatory records for templates with `auto_pay=True` for all periods (`daily/weekly/monthly/yearly`).
- `GetMandatoryExpenses.execute()`.
- `DeleteMandatoryExpense.execute(index)`.
- `DeleteAllMandatoryExpenses.execute()`.
- `AddMandatoryExpenseToReport.execute(index, date)`.
- `RunAudit.execute()` — runs the read-only data audit and returns an `AuditReport`.
- `CreateBudget.execute(category, start_date, end_date, limit_kzt, include_mandatory=False)` — creates a budget.
- `DeleteBudget.execute(budget_id)` — deletes a budget.
- `UpdateBudgetLimit.execute(budget_id, new_limit_kzt)` — updates a budget limit.
- `GetBudgets.execute()` — returns the list of budgets.
- `GetBudgetResults.execute()` — returns live budget tracking results.

`app/use_case_support.py`

- Shared helper functions for use cases without separate domain logic.

`app/finance_service.py`

- `FinanceService` protocol used by the import orchestrator (`ImportService`).
- Defines import-facing methods, rollback wrapper, and ID normalization.

`app/record_service.py`

- `RecordService.update_amount_kzt(record_id, new_amount_kzt)` — safe amount update via immutable domain objects and repository replace.
- `RecordService.update_record_inline(record_id, *, new_amount_kzt, new_category, new_description="", new_date=None, new_wallet_id=None)` — inline edit for `Amount KZT` + `Category` (+ `Description`) + (`Date`/`Wallet`).
- `RecordService.update_mandatory_amount_kzt(expense_id, new_amount_kzt)` — updates `amount_kzt` and recalculates `rate_at_operation`.
- `RecordService.update_mandatory_date(expense_id, new_date)` — updates `date` and derives `auto_pay`.
- `RecordService.update_mandatory_wallet_id(expense_id, new_wallet_id)` — changes the template wallet.
- `RecordService.update_mandatory_period(expense_id, new_period)` — changes the template period.

### Infrastructure

`infrastructure/repositories.py`

- `RecordRepository` — repository interface.
- `JsonFileRecordRepository(file_path="data.json")` — JSON repository for backup/import/export scenarios.

`infrastructure/sqlite_repository.py`

- `SQLiteRecordRepository(db_path="finance.db")` — SQLite `RecordRepository` implementation used by service layer.
- `db_path` — path to the active SQLite database, exposed for audit reporting.
- `query_all(...)` / `query_one(...)` — public read-only query APIs used by bootstrap and audit flows.
- `execute(...)` / `commit()` — low-level operations used by budget and audit services.
- Persists money in dual form: `REAL` + `*_minor`; FX rates in `REAL` + `rate_at_operation_text`.

`storage/base.py`

- `Storage` — minimal storage contract (`get/save` for wallets/records/transfers and `get` for mandatory expenses).

`storage/json_storage.py`

- `JsonStorage(file_path="data.json")` — JSON wrapper used only for import/export/backup scenarios.

`storage/sqlite_storage.py`

- `SQLiteStorage(db_path="records.db")` — SQLite adapter based on `sqlite3`, including:
  - `PRAGMA foreign_keys = ON`;
  - `PRAGMA journal_mode = WAL`;
  - auto-migration for existing DBs: adds `*_minor` and `rate_at_operation_text`, then backfills them;
  - domain object read/write mapping without business-logic duplication.

`db/schema.sql`

- Database schema with tables `wallets`, `records`, `transfers`, `mandatory_expenses`, `budgets`, constraints, and indexes.
- Monetary columns have exact integer `*_minor` companions; FX rates have `rate_at_operation_text`.
- Budgets include `limit_kzt_minor`, `include_mandatory`, and indexes for category/date lookups.

### GUI

`gui/tkinter_gui.py`

- `FinancialApp` is the main application class with Tkinter.

`gui/tabs/infographics_tab.py`

- `InfographicsTabBindings` — class for binding events to interface elements of the `Infographics` tab.
- `build_infographics_tab(parent, on_chart_filter_change, on_refresh_charts, on_legend_mousewheel, bind_all, after, after_cancel)` — method for building the interface of the `Infographics` tab. This tab displays charts and summaries of financial data.

`gui/tabs/operations_tab.py`

- `OperationsTabContext` — the context of the operations tab.
- `OperationsTabBindings` — class for binding events to interface elements of the `Operations` tab.
- `show_import_preview_dialog(parent, filepath, policy_label, preview, force=False)` — modal dry-run preview dialog for imports.
- `build_operations_tab(parent, context, import_formats)` — builds the `Operations` tab. The tab supports adding/deleting records, editing currency values, creating transfers, category `Combobox` suggestions, shared list/charts/wallets/budgets refresh, and the two-step import flow `dry-run -> preview -> commit`.

`gui/tabs/budget_tab.py`

- `BudgetTabBindings` — widget bindings for the `Budget` tab.
- `build_budget_tab(parent, context)` — builds the `Budget` tab with the creation form, budget table, progress canvas, and a `refresh` callback.

`gui/tabs/distribution_tab.py`

- `DistributionTabBindings` — widget bindings for the `Distribution` tab.
- `build_distribution_tab(parent, context)` — builds the `Distribution` tab with the structure editor, period range, and frozen/live distribution table.

`gui/tabs/reports_tab.py`

- `ReportsTabContext` — report tab context.
- `build_reports_tab(parent, context)` — builds the `Reports` tab:
  - filters `Period` / `Period end` / `Category` / `Wallet`;
  - `Group by category` with drill-down (double-click) and `Back`;
  - `Totals mode`: `On fixed rate` / `On current rate` (refreshes `Summary`);
  - export via `Export` menu (`CSV`/`XLSX`/`PDF`).

`gui/tabs/reports_controller.py`

- `ReportsController` — adapter between `FinancialController` and the reports UI (filter validation and result assembly).
- For wallet-filtered views, the summary uses the selected wallet balance instead of global net worth.

`gui/record_colors.py`

- `KIND_TO_FOREGROUND` / `foreground_for_kind(kind)` — colors for record kinds (`income`/`expense`/`mandatory`/`transfer`).

`gui/tooltip.py`

- `Tooltip(widget, text)` — simple tooltip for `tkinter`/`ttk` widgets.
- Tooltip positioning respects application-window bounds and now behaves correctly on multi-monitor layouts.

`gui/controller_import_support.py`

- Helpers for GUI controller import transactions: `run_import_transaction(...)`, `normalize_operation_ids_for_import(...)`.

`gui/tabs/operations_support.py`

- Shared `Operations` tab helpers: import preview dialog, safe destroy, and unified operations/charts/wallets/budgets refresh.

`gui/tabs/settings_support.py`

- Shared `Settings` tab helpers: audit dialog and safe teardown of transient windows.

`gui/tabs/analytics_tab.py`

- `AnalyticsTabBindings` — widget bindings for the `Analytics` tab.
- `build_analytics_tab(parent, context)` — builds the `Analytics` tab (Dashboard, Category Breakdown, Monthly Report, Net Worth Timeline).
- The Dashboard includes a metrics tooltip and shows `Year expense` instead of annualized expense.

`gui/tabs/settings_tab.py`

- `SettingsTabContext` — context of the settings tab.
- `build_settings_tab(parent, context, import_formats)` — method for building the interface of the `Settings` tab. This tab allows you to manage wallets, mandatory expenses, backups, and launch the audit.
- `show_audit_report_dialog(report, parent)` — modal audit dialog with `Errors`, `Warnings`, and `Passed` sections.
- Wallet and mandatory-expense changes also refresh the Budget tab in sync.

`gui/controllers.py`

- `FinancialController` — class for managing the business logic of the application.
- `get_income_categories()` — returns known income categories for editable `Combobox` widgets.
- `get_expense_categories()` — returns known expense categories for editable `Combobox` widgets.
- `get_mandatory_expense_categories()` — returns known mandatory expense categories for editable `Combobox` widgets.
- `import_records(fmt, filepath, policy, force=False, dry_run=False)` — single entry point for dry-run and real record imports.
- `import_mandatory(fmt, filepath)` — imports mandatory templates and returns `ImportResult`.
- `run_audit()` — runs the Data Audit Engine through a use case and returns `AuditReport`.
- `get_net_worth_timeline()` — net worth (KZT) at the end of each month (Timeline Engine, SQLite-only).
- `get_monthly_cashflow(start_date=None, end_date=None)` — monthly income/expense/cashflow (excluding transfers).
- `get_cumulative_income_expense()` — cumulative income/expense by month (excluding transfers).
- `get_savings_rate(start_date, end_date)` — savings rate (%) for a period (Metrics Engine, SQLite-only).
- `get_burn_rate(start_date, end_date)` — average daily expense (KZT) (Metrics Engine, SQLite-only).
- `get_year_income(year, up_to_date=None)` — calendar-year income, optionally year-to-date.
- `get_year_expense(year, up_to_date=None)` — calendar-year expenses, optionally year-to-date.
- `get_spending_by_category(start_date, end_date, limit=None)` — expenses by category (Metrics Engine, SQLite-only).
- `get_income_by_category(start_date, end_date, limit=None)` — income by category (Metrics Engine, SQLite-only).
- `get_top_expense_categories(start_date, end_date, top_n=5)` — top expense categories (Metrics Engine, SQLite-only).
- `get_monthly_summary(start_date=None, end_date=None)` — monthly aggregates (Metrics Engine, SQLite-only).
- `get_average_monthly_income(start_date, end_date)` — average monthly income over a range.
- `get_average_monthly_expenses(start_date, end_date)` — average monthly expenses over a range.
- `create_budget(...)`, `get_budgets()`, `get_budget_results()`, `delete_budget(...)`, `update_budget_limit(...)` — Budget System API surface.
- `create_distribution_item(...)`, `create_distribution_subitem(...)`, `update_distribution_item_pct(...)`, `update_distribution_subitem_pct(...)`, `delete_distribution_item(...)`, `delete_distribution_subitem(...)` — Distribution System CRUD API.
- `validate_distribution()`, `get_distribution_history(start_month, end_month)`, `get_frozen_distribution_rows(...)`, `toggle_distribution_month_fixed(month)` — frozen-row lifecycle and monthly distribution calculations.

`gui/exporters.py`

- `export_report(report, filepath, fmt)`.
- `export_grouped_report(statement_title, grouped_rows, filepath, fmt)` — exports grouped report summaries.
- `export_mandatory_expenses(expenses, filepath, fmt)`.
- `export_records(records, filepath, fmt, initial_balance=0.0, transfers=None)`.
- `export_full_backup(filepath, wallets, records, mandatory_expenses, distribution_items=(), distribution_subitems=(), distribution_snapshots=(), transfers=None, initial_balance=0.0, readonly=True, storage_mode="unknown")`.

`gui/importers.py`

- Legacy wrappers over `utils/*` kept for backward compatibility and tests.

`gui/helpers.py`

- `open_in_file_manager(path)`.

`gui/controller_support.py`

- Support structures and helpers for the GUI controller (`RecordListItem`, list building, import normalization).

### Services

`services/import_parser.py`

- `parse_import_file(path, force=False)` -> `ParsedImportData` (DTO/dict parsing layer, no storage writes).
- Enforces safety limits: file size, row count, CSV field size.
- For `JSON`, it also reads `distribution_items`, `distribution_subitems`, and `distribution_snapshots`.
- `parse_transfer_row(...)` handles legacy transfer rows as well as current-rate/full-backup parsing.

`services/import_service.py`

- `ImportService.import_file(path, force=False, dry_run=False)` — dry-run or real operation import; returns `ImportResult`.
- `ImportService.import_mandatory_file(path)` — imports mandatory templates and returns `ImportResult`.
- Dry-run uses the same parse/validation pipeline but performs no SQLite writes.
- `Full Backup` keeps fixed `amount_kzt/rate_at_operation`; `Current Rate` recalculates values.
- For `JSON` full backup, it can also restore distribution structure and frozen snapshots through `replace_distribution_structure(...)` / `replace_distribution_snapshots(...)`.
- Malformed distribution structure in a `JSON` full backup is now treated as an import error instead of being skipped silently.

`services/audit_service.py`

- `AuditService(repository)` — read-only diagnostic service for SQLite data.
- `run()` — scans SQLite data and executes 10 integrity/consistency checks.
- Each check returns `AuditFinding` entries and emits one `OK` finding when no violations are found.

`services/report_service.py`

- DTOs and helpers for the reports UI: `ReportFilters`, `ReportSummary`, `ReportsResult`,
  `build_operations_rows(report)`, `build_monthly_rows(report)`, `extract_categories(rows)`.

`services/balance_service.py`

- `WalletBalance(wallet_id, name, currency, balance)` — immutable wallet balance snapshot.
- `CashflowResult(income, expenses, cashflow)` — immutable period aggregate.
- `BalanceService(repository, currency_service=None)` — read-only analytics over `wallets` + `records`.
- When `currency_service` is provided, wallet initial balances are normalized to KZT before aggregation.
- SQL aggregates use `*_minor` when available to avoid accumulated float drift.
- `get_wallet_balance(wallet_id, date=None)` — wallet balance at a date or over full history.
- `get_wallet_balances(date=None)` — balances of all active wallets.
- `get_total_balance(date=None)` — total system balance.
- `get_cashflow(start_date, end_date)` — income, expenses, and net cashflow without transfer double-counting.
- `get_income(start_date, end_date)` — income for a period without transfers.
- `get_expenses(start_date, end_date)` — expenses for a period, including `mandatory_expense`.

`services/timeline_service.py`

- `MonthlyNetWorth(month, balance)` — immutable net worth snapshot at month end.
- `MonthlyCashflow(month, income, expenses, cashflow)` — immutable monthly cashflow aggregate.
- `MonthlyCumulative(month, cumulative_income, cumulative_expenses)` — immutable running totals by month.
- `TimelineService(repository, currency_service=None)` — read-only timeline analytics from `wallets` + `records`.
- When `currency_service` is provided, the timeline correctly includes multi-currency `wallet.initial_balance`.
- Uses SQL helper expressions over `*_minor` for money totals.
- `get_net_worth_timeline()` — net worth (KZT) at the end of each month (includes transfer pairs, they net to zero).
- `get_monthly_cashflow(start_date=None, end_date=None)` — monthly income/expense/cashflow (excludes `transfer_id IS NOT NULL`).
- `get_cumulative_income_expense()` — cumulative income and expenses by month (excludes `transfer_id IS NOT NULL`).

`services/metrics_service.py`

- `CategorySpend(category, total_kzt, record_count)` — immutable per-category aggregate.
- `MonthlySummary(month, income, expenses, cashflow, savings_rate)` — immutable monthly aggregate.
- `MetricsService(repository)` — read-only metrics analytics over `records`.
- Uses quantized money and minor-unit SQL for sums and comparisons.
- `get_savings_rate(start_date, end_date)` — (income - expenses) / income * 100, safe division by zero.
- `get_burn_rate(start_date, end_date)` — average daily expense (KZT) for date range.
- `get_spending_by_category(start_date, end_date, limit=None)` — expenses by category, sorted descending.
- `get_income_by_category(start_date, end_date, limit=None)` — income by category, sorted descending.
- `get_distinct_income_categories()` — unique income categories.
- `get_distinct_expense_categories()` — unique expense categories.
- `get_distinct_mandatory_expense_categories()` — unique mandatory expense categories.
- `get_top_expense_categories(start_date, end_date, top_n=5)` — wrapper over `get_spending_by_category`.
- `get_monthly_summary(start_date=None, end_date=None)` — per-month aggregates (income/expenses/cashflow/savings_rate).

`services/budget_service.py`

- `BudgetService(repository)` — budget management and live spend-tracking service.
- `create_budget(category, start_date, end_date, limit_kzt, include_mandatory)` — creating a new budget.
- `get_budgets()` — list of all budgets.
- `delete_budget(budget_id)` — deleting a budget.
- `update_budget_limit(budget_id, new_limit_kzt)` — updating the budget limit.
- `get_budget_result(budget, today)` — budget results for the specified date.
- `get_all_results(today)` — batch calculation of all budget results for the specified date.

`services/distribution_service.py`

- `DistributionService(repository)` — Distribution System CRUD and monthly allocation service for SQLite.
- `create_item(...)`, `create_subitem(...)`, `update_*_pct(...)`, `update_*_name(...)`, `delete_*(...)` — item/subitem structure management.
- `validate()` — verifies that top-level and subitem percentages total `100%`.
- `get_monthly_distribution(month)` / `get_distribution_history(start_month, end_month)` — monthly allocation based on net income excluding transfers.
- `freeze_month(month, auto_fixed=False)`, `freeze_closed_months()`, `toggle_month_fixed(month)`, `get_frozen_rows(...)`, `replace_frozen_rows(rows)` — frozen snapshot lifecycle.

`services/currency_support.py`

- `convert_money_to_kzt(amount, currency, currency_service=None)` — helper for normalizing amounts to KZT inside read-only services and use cases.

`services/sqlite_money_sql.py`

- SQL helper expressions for minor-unit sums: `minor_amount_expr`, `money_expr`, `signed_minor_amount_expr`.

### Utils

`utils/backup_utils.py`

- `compute_checksum(data)` — SHA256 checksum for `data`.
- `export_full_backup_to_json(filepath, wallets, records, mandatory_expenses, distribution_items=(), distribution_subitems=(), distribution_snapshots=(), transfers=(), initial_balance=0.0, readonly=True, storage_mode="unknown")`.
- `import_full_backup_from_json(filepath, force=False)`.
- Backup/import normalizes money values and FX rates via `utils.money`.
- JSON export writes atomically via a temporary file + `os.replace`.

`utils/money.py`

- Shared precise money helpers: `quantize_money`, `quantize_rate`, `to_minor_units`, `minor_to_money`, `build_rate`, and diff helpers.

`utils/csv_utils.py`

- `report_to_csv(report, filepath)`.
- `report_from_csv(filepath)`.
- `export_records_to_csv(records, filepath, initial_balance=0.0, transfers=None)`.
- `import_records_from_csv(filepath, policy, currency_service, wallet_ids=None)`.
- `export_mandatory_expenses_to_csv(expenses, filepath)`.
- `import_mandatory_expenses_from_csv(filepath, policy, currency_service)`.
- CSV import/export validates and quantizes amounts/rates without float drift; transfer integrity checks use quantized comparisons.

`utils/excel_utils.py`

- `report_to_xlsx(report, filepath)`.
- `report_from_xlsx(filepath)`.
- `export_records_to_xlsx(records, filepath, initial_balance=0.0, transfers=None)`.
- `import_records_from_xlsx(filepath, policy, currency_service, wallet_ids=None)`.
- `export_mandatory_expenses_to_xlsx(expenses, filepath)`.
- `import_mandatory_expenses_from_xlsx(filepath, policy, currency_service)`.
- `existing_initial_balance` is quantized to money scale during import.
- XLSX export adds styled headers/sections/totals, `freeze_panes`, `auto_filter`, auto-width columns, and keeps money amounts as numeric cells.

`utils/tabular_utils.py`

- Shared helpers for CSV/XLSX row building, type labels, and rate resolver logic.

`utils/pdf_utils.py`

- `report_to_pdf(report, filepath)`.

`utils/charting.py`

- `aggregate_expenses_by_category(records)`.
- `aggregate_daily_cashflow(records, year, month)`.
- `aggregate_monthly_cashflow(records, year)`.
- `extract_years(records)`.

`utils/import_core.py`

- Base import-row parser with Decimal-based money parsing, quantization, and payload validation.
- `extract_months(records)`.

`utils/import_core.py`

- `norm_key(value)`.
- `as_float(value, default=None)`.
- `safe_type(value)`.
- `record_type_name(record)`.
- `parse_import_row(row, row_label, policy, get_rate, mandatory_only)`.

---

## 📁 File structure

```text
project/
│
├── main.py                           # Application entry point
├── config.py                         # Runtime SQLite and JSON import/export paths
├── bootstrap.py                      # SQLite initialization + startup validation
├── backup.py                         # JSON backup and SQLite -> JSON export
├── migrate_json_to_sqlite.py         # Data migration from JSON to SQLite
├── version.py                        # Application version for snapshot metadata
├── data.json                         # Optional JSON import/export/backup file
├── currency_rates.json               # Currency rate cache for online mode
├── requirements.txt                  # Runtime dependencies
├── requirements-dev.txt              # Dev dependencies (tests, coverage)
├── pytest.ini                        # pytest settings
├── pyproject.toml                    # Project configuration
├── README.md                         # This documentation
├── README_EN.md                      # Documentation in English
├── CHANGELOG.md                      # History of changes
├── LICENSE                           # License
│
├── app/                              # Application layer
│   ├── __init__.py
│   ├── finance_service.py            # FinanceService protocol for import orchestration
│   ├── record_service.py             # Service for records
│   ├── services.py                   # CurrencyService adapter
│   ├── use_case_support.py           # Shared helpers for use cases
│   └── use_cases.py                  # Use cases
│
├── domain/                           # Domain layer
│   ├── __init__.py
│   ├── audit.py                      # Audit models and logic
│   ├── budget.py                     # Budgets, pace/status, and live tracking DTOs
│   ├── distribution.py               # DTOs and frozen snapshot models for the Distribution System
│   ├── records.py                    # Records
│   ├── reports.py                    # Reports
│   ├── currency.py                   # Domain CurrencyService
│   ├── wallets.py                    # Wallets
│   ├── transfers.py                  # Transfers
│   ├── validation.py                 # Validation of dates and periods
│   ├── errors.py                     # Application errors 
│   ├── import_policy.py              # Import policies
│   └── import_result.py              # Import results
│
├── infrastructure/                   # Infrastructure layer
│   ├── repositories.py               # JSON repository
│   └── sqlite_repository.py          # SQLite repository
│
├── storage/                          # Storage abstraction and JSON/SQLite adapters
│   ├── __init__.py
│   ├── base.py                       # Base storage class
│   ├── json_storage.py               # JSON storage adapter
│   └── sqlite_storage.py             # SQLite storage adapter
│
├── db/                               # SQL schema for SQLite
│   └── schema.sql
│
├── services/                         # Service layer
│   ├── __init__.py
│   ├── audit_service.py              # Audit service
│   ├── balance_service.py            # Read-only balance and cashflow service
│   ├── budget_service.py             # Budget CRUD and live spend tracking
│   ├── currency_support.py           # Converting money amounts to KZT for services
│   ├── distribution_service.py       # Distribution structure CRUD and frozen month snapshots
│   ├── import_parser.py              # CSV/XLSX/JSON parser -> DTO
│   ├── import_service.py             # Import orchestration via FinanceService
│   ├── metrics_service.py            # Read-only financial metrics service
│   ├── report_service.py             # DTOs and helpers for reports UI
│   ├── sqlite_money_sql.py           # SQL helper expressions for minor-unit sums
│   └── timeline_service.py           # Read-only timeline service
│
├── utils/                            # Import/export and graphs
│   ├── __init__.py
│   ├── backup_utils.py               # Backup of data
│   ├── import_core.py                # Import validator
│   ├── charting.py                   # Graphs and Aggregations
│   ├── csv_utils.py
│   ├── excel_utils.py
│   ├── money.py                      # Precise money arithmetic and quantization helpers
│   ├── pdf_utils.py
│   └── tabular_utils.py              # Shared CSV/XLSX helpers
│
├── gui/                              # GUI layer (Tkinter)
│   ├── tabs/
│   │   ├── infographics_tab.py       # Tab with infographics
│   │   ├── operations_tab.py         # Tab with operations and transfers
│   │   ├── operations_support.py     # Shared helpers for the Operations tab
│   │   ├── reports_tab.py            # Tab with reports
│   │   ├── reports_controller.py     # Reports tab controller (UI adapter)
│   │   ├── analytics_tab.py          # Analytics tab (dashboard, categories, report)
│   │   ├── budget_tab.py             # Budget tab and progress canvas
│   │   ├── distribution_tab.py       # Net-income distribution tab by month
│   │   ├── settings_support.py       # Shared helpers for the Settings tab
│   │   └── settings_tab.py           # Tab with wallets and mandatory expenses
│   │
│   ├── __init__.py
│   ├── tkinter_gui.py                # Main GUI application
│   ├── record_colors.py              # Row colors by record kind
│   ├── tooltip.py                    # Tooltip for tkinter/ttk
│   ├── controller_import_support.py  # Import-flow helpers for the GUI controller
│   ├── controller_support.py         # GUI support helpers
│   ├── helpers.py                    # Helpers for GUI
│   ├── controllers.py                # GUI controllers
│   ├── importers.py                  # Legacy import wrappers (compatibility/tests)
│   └── exporters.py                  # Export reports, mandatory expenses and backup
│
└── tests/                            # Tests
    ├── __init__.py
    ├── conftest.py                   # Local tmp fixture for stable test execution
    ├── test_analytics_tab.py
    ├── test_audit_engine.py
    ├── test_balance_service.py
    ├── test_bootstrap_backup.py
    ├── test_bootstrap_migration_verification.py
    ├── test_budget_service.py
    ├── test_charting.py
    ├── test_csv.py
    ├── test_currency.py
    ├── test_distribution_service.py
    ├── test_excel.py
    ├── test_gui_exporters_importers.py
    ├── test_import_balance_contract.py
    ├── test_import_core.py
    ├── test_import_dry_run.py
    ├── test_import_parser.py
    ├── test_import_policy_and_backup.py
    ├── test_import_security.py
    ├── test_import_service.py
    ├── test_mandatory_ux.py
    ├── test_metrics_service.py
    ├── test_migrate_json_to_sqlite.py
    ├── test_online_mode.py
    ├── test_pdf.py
    ├── test_records.py
    ├── test_reports.py
    ├── test_repositories.py
    ├── test_schema_contracts.py
    ├── test_services.py
    ├── test_sqlite_runtime_storage.py
    ├── test_tooltip.py
    ├── test_timeline_service.py
    ├── test_transfer_integrity.py
    ├── test_transfer_order_sqlite.py
    ├── test_use_cases.py
    ├── test_validation.py
    ├── test_wallet_phase1.py
    ├── test_wallet_phase2.py
    ├── test_wallet_phase3.py
    ├── test_phase33_immutable_repo_service.py
    └── test_phase4_import_export.py
```

---

## 🧪 Tests

### Launch

```bash
# Go to project directory
cd "FU Project/project"

# Install dev dependencies (if not installed yet)
pip install -r requirements-dev.txt

# Run all tests (inside activated venv)
python -m pytest

# With verbose output
python -m pytest -v

# Specific file
python -m pytest tests/test_records.py -v

# Specific test
python -m pytest tests/test_reports.py::test_report_total -v
```

### Coverage

```bash
pip install -r requirements-dev.txt
python -m pytest --cov=. --cov-report=term-missing
python -m pytest --cov=. --cov-report=html
```

> **Note:** The tests expect the `CurrencyService` to use local courses by default (parameter `use_online=False`).

---

## 💱 Supported currencies

Default application rates:

| Currency          | Code | Default rate | Description     |
| ----------------- | ---- | ------------ | --------------- |
| Kazakhstani tenge | KZT  | 1.0          | Base currency   |
| US dollar         | USD  | 500.0        | 1 USD = 500 KZT |
| Euro              | EUR  | 590.0        | 1 EUR = 590 KZT |
| Russian ruble     | RUB  | 6.5          | 1 RUB = 6.5 KZT |

By default, the application uses local exchange rates. Online mode can be enabled either at construction time with `CurrencyService(use_online=True)` or later via `CurrencyService.set_online(True)` or the `Online` toggle in the bottom status bar. After a successful fetch, National Bank of Kazakhstan rates are saved to `currency_rates.json`, and the status bar shows the latest update time.

---

## 📄 License

MIT License — free to use, modify and distribute.
