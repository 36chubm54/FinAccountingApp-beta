# Changelog

All notable changes to this project will be documented in this file.

The format is based on Keep a Changelog.
This project adheres to Semantic Versioning.

---

## [1.8.1] - 2026-03-24

### Fixed

- Restored legacy transfer-row parsing in `services/import_parser.py` for `ImportPolicy.LEGACY`
- Restored export of orphan/unlinked transfer aggregates in tabular CSV/XLSX data export
- Preserved source record order during post-import ID normalization while keeping deterministic transfer ID remapping
- GUI full-backup export now writes correct snapshot metadata with `meta.storage="sqlite"`

### Changed

- Full-backup import and JSON -> SQLite migration now reject malformed `distribution_items` / `distribution_subitems` instead of silently skipping broken structure payloads
- Tooltip positioning logic was extracted and hardened for multi-monitor layouts with negative window origins
- Backup/export/import docs were updated to reflect distribution structure restore, strict backup validation, and GUI backup metadata

### Tests

- Added regression coverage for legacy transfer parsing, orphan transfer export, tooltip geometry, strict distribution-structure validation, GUI backup metadata, and deterministic import ID normalization

No breaking changes.

---

## [1.8.0] - 2026-03-24

### Added

- Added the Distribution System with persisted `distribution_items` and `distribution_subitems`
- Added `domain/distribution.py` models and `services/distribution_service.py` for CRUD, validation, and monthly cashflow allocation
- Added a new `Distribution` tab between `Budget` and `Settings` for structure editing and period-based distribution review
- Added frozen `distribution_snapshots` with `auto_fixed` support for fixed month rows in JSON backup/import
- Added `tests/test_distribution_service.py` and schema/runtime coverage for the new tables and snapshot flows

### Changed

- Main notebook order is now `Infographics | Operations | Reports | Analytics | Budget | Distribution | Settings`
- Distribution calculations reuse existing minor-unit SQL helpers so the new major feature stays compatible with `v1.7.2`-`v1.7.4` money precision fixes
- Startup now auto-freezes closed distribution months before export, while background JSON export skips repeated auto-freeze
- Full JSON backup export now writes atomically via temp file + replace and can restore distribution snapshots on import

### Tests

- Added service-level coverage for distribution CRUD, validation, monthly net-income calculation, history ranges, snapshot restore, and auto-fixed month protection

### Docs

- Updated `README.md` and `README_EN.md` for the Distribution tab, snapshot-aware backup/import, and atomic JSON export behavior

No breaking changes.

---

## [1.7.4] - 2026-03-23

### Added

- Added shared GUI support modules for import flow, Operations refresh logic, and Settings audit dialogs
- Added grouped report export for summary-by-category view in `CSV`, `XLSX`, and `PDF`
- Added `services/currency_support.py` to normalize wallet balances and timeline initial balances to KZT

### Changed

- Reports summary now shows wallet-specific balances when a wallet filter is selected
- `BalanceService`, `TimelineService`, `GenerateReport`, `CalculateWalletBalance`, and `SoftDeleteWallet` now support multi-currency wallet initial balances via `CurrencyService`
- Budget tab now exposes `Include mandatory` directly in the table and refreshes after related operations/settings changes
- SQLite repository now resolves records and mandatory expenses directly by row/id and supports indexed transfer lookup
- JSON backup pruning now honors `keep_last=0` by skipping backup creation and removing matching retained files
- Batch budget result calculation now uses a single SQL aggregation query for current spend
- `PDF`/`XLSX` grouped category sections are skipped when they would only duplicate a single-category filtered report

### Tests

- Added coverage for multi-currency wallet initial balances in balance, timeline, report, and wallet use cases
- Added coverage for batch budget calculations, mandatory-expense budget inclusion, grouped export behavior, and backup pruning with `keep_last=0`

### Docs

- Updated `README.md` and `README_EN.md` for grouped report export, budget refresh behavior, multi-currency balance analytics, and the new helper modules

No breaking changes.

---

## [1.7.3] - 2026-03-23

### Added

- Excel exports now apply readability styling: colored headers, highlighted totals, `freeze_panes`, `auto_filter`, auto-width columns, and numeric amount cells
- Analytics Dashboard now includes an `ⓘ` tooltip explaining the displayed metrics

### Changed

- `Analytics` replaces annualized expenses with `Year expense` in the Dashboard
- `Cost per day/hour/minute` is now derived from year-to-date expenses instead of annualized burn rate
- `FinancialController` adds `get_year_expense(...)` and removes `get_average_annual_expenses(...)`
- Wallets refresh after editing a selected record in `gui/tabs/operations_tab.py`

### Tests

- Updated `tests/test_analytics_tab.py` for year-to-date expense and time-cost calculations
- Extended `tests/test_excel.py` to cover styled XLSX exports and numeric cell values

### Docs

- Updated `README.md` and `README_EN.md` to document the Analytics metric changes and improved XLSX export formatting

No breaking changes.

---

## [1.7.2] - 2026-03-22

### Added

- Expanded support for date validation in `validation.py` (dates are now rejected if they are earlier than UNIX time)
- After deleting an entry, wallets are updated

### Changed

- `gui/tabs/settings_tab.py` restores the `Refresh` button in the wallet frame

### Tests

- 2 scenarios in `tests/test_validation.py` covering date validation before UNIX time

### Docs

- Updated `README.md` and `README_EN.md` to describe the new date validation rules

---

## [1.7.1] - 2026-03-21

### Added

- Global status bar at the bottom of the main window with an `Online` toggle and runtime currency status
- `CurrencyService.set_online(bool)`, `CurrencyService.is_online`, `CurrencyService.last_fetched_at`, and `CurrencyService.refresh_rates()`
- `FinancialController` online-mode helpers with persistent `schema_meta["online_mode"]`
- `tests/test_online_mode.py` covering runtime online/offline switching scenarios

### Changed

- Saved online mode is restored on application startup without requiring a restart
- Currency status text refreshes periodically so the last update timestamp stays current
- Online-mode switching no longer blocks the GUI while exchange rates are being fetched in the background

### Docs

- Updated `README.md` and `README_EN.md` to describe the new status bar and online toggle

No breaking changes.

---

## [1.7.0] - 2026-03-21

### Added

- Budget System with persistent `budgets` table, overlap-safe date ranges, `limit_kzt_minor`, and `include_mandatory`
- `domain/budget.py` with `Budget`, `BudgetResult`, `BudgetStatus`, `PaceStatus`, and pace computation helpers
- `services/budget_service.py` for budget CRUD, spend aggregation, overlap checks, and category suggestions
- New Budget tab between Analytics and Settings with creation form, Treeview summary, and pace-aware progress canvas
- Budget use cases and controller delegation methods for create/list/delete/update/result flows
- Distinct income / expense / mandatory-expense category helpers in `services/metrics_service.py`
- `tests/test_budget_service.py` plus schema contract coverage for the new table/indexes

### Changed

- `gui/tabs/operations_tab.py` category inputs now use editable `ttk.Combobox` widgets with suggestions that switch by operation type
- Inline category editing in `Operations` now uses category-specific `Combobox` suggestions for income / expense / mandatory records
- `gui/tabs/settings_tab.py` restores the `Refresh` button in the mandatory expenses action bar
- `Add to Records` now validates empty selection early and shows a clearer error dialog instead of proceeding without a selected template
- SQLite schema initialization now creates the `budgets` table automatically for existing and new databases

### Tests

- 19 scenarios in `tests/test_budget_service.py` covering CRUD, overlap detection, pace states, include_mandatory flag, transfer exclusion, category queries, and precision with minor units.

### Docs

- Updated `README.md` and `README_EN.md` to document the budget system and its features

No breaking changes.

---

## [1.6.0] - 2026-03-19

### Added

- Precise money helpers in `utils/money.py` for quantization, minor units, and canonical FX-rate formatting
- SQL helper expressions in `services/sqlite_money_sql.py` for minor-unit based sums and signed money calculations
- Precision columns in SQLite schema: `*_minor` for money and `rate_at_operation_text` for exchange rates

### Changed

- SQLite storage/repository now persist and read money values through dual representation: `REAL` + exact minor units
- Existing SQLite databases are auto-migrated/backfilled with precision columns on startup
- Migration, import, backup, and analytics flows now use quantized money/rate helpers instead of raw float arithmetic
- Balance, metrics, and timeline analytics now aggregate through minor-unit SQL expressions to reduce rounding drift

### Tests

- Extended `tests/test_migrate_json_to_sqlite.py` to verify `*_minor` and `rate_at_operation_text` migration payload
- Added Excel import coverage for quantized `existing_initial_balance` in `tests/test_excel.py`

### Docs

- Updated `README.md` and `README_EN.md` to document the precision model and new helper modules

No breaking changes.

---

## [1.5.1] - 2026-03-18

### Added

- Reports UI refactor: a dedicated `ReportsController` + `services/report_service.py` DTO helpers
- Tooltips and shared record kind colors for Treeviews (`gui/tooltip.py`, `gui/record_colors.py`)
- Lazy SQLite → JSON export on startup (skips when `data.json` is up-to-date; may run in background for large DB)

### Changed

- Reports tab now supports grouped drill-down via double-click and a `Back` button
- Summary totals can be switched between fixed-rate and current-rate mode (`Totals mode`)
- Operations list migrated from Listbox to Treeview with sortable columns and kind-based coloring
- Remove `prettytable` dependency and deprecated Report table helpers (`as_table`, `monthly_income_expense_table`)

### Tests

- Add/extend export contract coverage for CSV/XLSX reports and mandatory templates (`tests/test_csv.py`, `tests/test_excel.py`)
- Add bootstrap/backup coverage for SQLite → JSON export and backup pruning (`tests/test_bootstrap_backup.py`)

### Docs

- Update `README.md` and `README_EN.md` to match the new Reports/Operations UI and lazy export behavior

No breaking changes.

---

## [1.5.0] - 2026-03-15

### Added

- `Analytics` tab in the main Notebook (between Reports and Settings)
- Dashboard section: net worth (KZT), savings rate (%), burn rate (KZT/day)
- Net worth timeline chart (line chart on `tk.Canvas`, monthly granularity)
- Category Breakdown: spending and income Treeviews + expenses pie chart on `tk.Canvas`
- Monthly Report: Treeview with income, expenses, cashflow, savings rate per month
- Period filter (`From` / `To`, `YYYY-MM-DD`) with `Refresh` button
- Positive/negative cashflow rows colored green/red in Monthly Report

### Fixed

- Wallet lists/menus now refresh after operations that change wallets/data (GUI)

### Tests

- Added `tests/test_analytics_tab.py` with 8 headless scenarios (service-level)

### Docs

- Updated `README.md` and `README_EN.md` to document the Analytics tab

No breaking changes.

---

## [1.4.3] - 2026-03-15

- `MetricsService` in `services/metrics_service.py` — read-only financial metrics service (live SQL aggregates; no intermediate storage)
- `CategorySpend` and `MonthlySummary` frozen dataclasses as result types
- Metrics methods:
  `get_savings_rate`, `get_burn_rate`, `get_spending_by_category`, `get_income_by_category`,
  `get_top_expense_categories`, `get_monthly_summary`
- `RunMetrics` use case in `app/use_cases.py`
- Metrics delegation methods in `FinancialController`:
  `get_savings_rate`, `get_burn_rate`, `get_spending_by_category`, `get_income_by_category`,
  `get_top_expense_categories`, `get_monthly_summary`

### Tests

- Added `tests/test_metrics_service.py` with scenarios covering empty DB, transfer exclusion,
  limits, division-by-zero safety, and read-only guarantee.

### Docs

- Updated `README.md` and `README_EN.md` to mention Metrics Engine and the enhanced startup notification.

No breaking changes.

---

## [1.4.2] - 2026-03-14

### Added

- Mandatory auto‑pay now displays a detailed informational GUI message on startup when payments are applied.
- The message includes a list of created mandatory expenses with category, amount (KZT) and date for improved transparency.

### Changed

- `ApplyMandatoryAutoPayments` use case now returns a list of created `MandatoryExpenseRecord` objects instead of a simple count.
- `FinancialController.apply_mandatory_auto_payments()` adapted to return the list.
- GUI startup logic in `tkinter_gui.py` builds a user‑friendly summary from the returned records.

### Tests

- Existing auto‑pay scenarios in `tests/test_mandatory_ux.py` updated.
- All modified modules (`use_cases.py`, `controllers.py`, `tkinter_gui.py`) compile without syntax errors.
- No regression introduced; test suite passes.

### Docs

- Updated `README.md` and `README_EN.md` to mention the enhanced startup notification.

No breaking changes.

---

## [1.4.1] - 2026-03-14

### Added

- Mandatory auto-pay now supports all periods: `daily`, `weekly`, `monthly`, `yearly` (anchored by template `date`)
- Mandatory templates: wallet dropdown on create, plus inline editing of `wallet` and `period` after creation
- Operations tab inline edit: update `date` and `wallet` in addition to `amount_kzt`, `category`, and optional `description`

### Changed

- Transfers are protected from inline edits when the selected record has category `"Transfer"` (in addition to `transfer_id` linkage)

### Tests

- Extended `tests/test_mandatory_ux.py` with auto-pay scenarios for all periods
- Added record inline edit coverage for wallet/date updates

### Docs

- Updated `README.md` and `README_EN.md`

No breaking changes.

---

## [1.4.0] - 2026-03-13

### Added

- Timeline Engine: read-only analytical service for historical net worth and cashflow
- `TimelineService` in `services/timeline_service.py` with 3 methods:
  `get_net_worth_timeline` — net worth per month via SQL window function
  `get_monthly_cashflow` — income/expenses/cashflow per month with optional date range
  `get_cumulative_income_expense` — running totals for income and expenses
- `MonthlyNetWorth`, `MonthlyCashflow`, `MonthlyCumulative` frozen dataclasses as result types
- `RunTimeline` use case in `app/use_cases.py`
- Timeline delegation methods in `FinancialController`:
  `get_net_worth_timeline`, `get_monthly_cashflow`, `get_cumulative_income_expense`

### Changed

- "Transfer" category excluded from charts (expenses by category, daily/monthly cashflow)

### Removed

- Remove obsolete log messages about the selected repository

### Tests

- Added `tests/test_timeline_service.py` with 12 scenarios covering empty DB behavior,
  initial balance baseline, transfer neutrality for net worth, transfer exclusion in cashflow,
  date filters, and read-only guarantee
- Extended `tests/test_charting.py` with scenarios for covering aggregated data with the excluded "Transfer" category

### Docs

- Updated `README.md` and `README_EN.md` with Timeline Engine description

No breaking changes.

---

## [1.3.3] - 2026-03-11

### Added

- `date` field (optional, YYYY-MM-DD) and `auto_pay` flag in mandatory expense templates
- Inline editing of `amount_kzt` and `date` templates directly in the settings list
- `Description` field in the `Add operation` form (Operations tab)
- `Description` field in the `Transfer` form (Operations tab)
- `date` support for `mandatory_expenses` in CSV/XLSX import-export and JSON backup/export flows
- Coloring of text in the list of operations by type income/expense/mandatory/transfer

### Changed

- The `Edit Amount KZT` button has been renamed to `Edit` (Operations tab)
- `auto_pay` is calculated automatically from `date`: non-empty date → `auto_pay=True`
- The form for adding a mandatory expense has been expanded with the `Date (optional)` field
- `data.json` startup export now keeps `mandatory_expenses.date` instead of dropping it
- Startup JSON backups are now pruned via `JSON_BACKUP_KEEP_LAST`

### Removed

- `mandatory_expense_no_date` check removed from Data Audit Engine (date field is now valid)

### Tests

- Added `tests/test_mandatory_ux.py` covering template dates, inline edits, and auto-pay behavior
- Added `tests/test_schema_contracts.py` to enforce schema/domain period constraints
- Updated `tests/test_audit_engine.py`: removed outdated assertions, check count = 10
- Added round-trip coverage for `mandatory_expenses.date` in CSV/XLSX, backup JSON, startup export, and JSON -> SQLite migration

### Docs

- Updated `README.md` and `README_EN.md`

No breaking changes.

---

## [1.3.2] - 2026-03-09

### Added

- Balance Engine: read-only analytical service for derived financial state
- `BalanceService` in `services/balance_service.py` with 6 methods:
  `get_wallet_balance`, `get_wallet_balances`, `get_total_balance`,
  `get_cashflow`, `get_income`, `get_expenses`
- `WalletBalance` and `CashflowResult` frozen dataclasses as result types
- Balance delegation methods in `FinancialController`:
  `get_wallet_balance`, `get_wallet_balances`, `get_total_balance`,
  `get_cashflow`, `get_income`, `get_expenses`
- Index `idx_records_wallet_date` on `records(wallet_id, date)` in `db/schema.sql`

### Tests

- Add `tests/test_balance_service.py` with 13 scenarios covering wallet balance,
  historical balance, transfer neutrality, cashflow, and read-only guarantee

### Docs

- Update `README.md` and `README_EN.md` with Balance Engine description

No breaking changes.

---

## [1.3.1] - 2026-03-09

### Changed

- Removed pure schema-level duplicate checks from the Data Audit Engine
- Narrowed audit scope from 9 checks to 8 business-level checks
- Kept the audit strictly read-only

### Added

- Transfer amount alignment check between `transfers` rows and linked `expense` / `income` records
- Amount positivity check for records, transfers, and mandatory expense templates

### Tests

- Updated `tests/test_audit_engine.py`
- Audit coverage now includes 16 scenarios
- Kept commission exclusion logic and read-only guarantee coverage

### Docs

- Updated `README.md` and `README_EN.md` to reflect the refined audit scope
- Updated `CHANGELOG.md` for `v1.3.1`

No breaking changes.

---

## [1.3.0] - 2026-03-09

### Added

- Data Audit Engine: on-demand, read-only diagnostic of the SQLite database
- `AuditReport`, `AuditFinding`, `AuditSeverity` dataclasses in `domain/audit.py`
- `AuditService` in `services/audit_service.py` with 9 integrity and consistency checks:
  transfer pair integrity, orphan records, amount consistency, rate positivity,
  date validity, wallet references, currency codes, record types,
  mandatory expense date absence
- `RunAudit` use case in `app/use_cases.py`
- `run_audit()` method in `FinancialController`
- `Finance Audit` block in `Settings` tab with `Run Audit` button
- Modal audit report dialog with color-coded Errors, Warnings, and Passed sections

### Tests

- Add `tests/test_audit_engine.py` with 17 scenarios covering all checks,
  commission exclusion logic, and read-only guarantee

### Docs

- Update `README.md` and `README_EN.md` with Data Audit Engine description
  under the Settings tab section

No breaking changes.

---

## [1.2.3] - 2026-03-08

### Added

- Import Dry-run Mode: full parse and validation cycle without writing to SQLite
- `ImportResult` dataclass (`domain/import_result.py`) with fields `imported`, `skipped`, `errors`, `dry_run`; replaces bare tuple returns from `ImportService`
- Import preview dialog in `Operations` tab: displays record count, skipped rows,
  and errors before the user confirms the operation
- `dry_run: bool = False` parameter in `ImportService.import_file(...)` and `FinanceService` protocol

### Changed

- `ImportService.import_file(...)` now returns `ImportResult` instead of a plain tuple
- `Operations` tab import now executes a two-step flow: dry-run preview, user confirmation, then real import
- All callers of `import_file` updated to use `ImportResult` field access

### Tests

- Add dry-run coverage to import service and SQLite import pipeline tests
- Update import controller and runtime storage tests to use `ImportResult` field access

### Docs

- Update `README.md` and `README_EN.md` with dry-run mode description under the import section

No breaking changes.

---

## [1.2.2] - 2026-03-07

### Fixed

- Enforce strict integer validation for `wallet_id` and `transfer_id` across JSON/CSV/XLSX import paths
- Stop silent coercion of malformed IDs in import, repository loading, and legacy JSON migration flows
- Fix SQLite schema path resolution during bootstrap
- Remove direct internal storage access from bootstrap, backup, and migration code
- Preserve report metadata in `grouped_by_category()` subreports while keeping zero initial balance

### Refactor

- Add public admin/query APIs for SQLite storage and repository bootstrap operations
- Extract shared helpers from `use_cases.py` and `controllers.py` to reduce responsibility overlap
- Refactor `migrate_json_to_sqlite.py` to use public storage APIs and explicit transactions
- Extract shared CSV/XLSX tabular export helpers
- Remove redundant `sys.path` bootstrapping from entry and GUI modules

### Changed

- Strengthen SQLite constraints for currency codes and date-shaped fields
- Make snapshot metadata use `version.py` and caller-provided storage mode
- Treat `MandatoryExpenseRecord.type` consistently as `mandatory_expense`
- Align CSV/XLSX export labeling and row-building through shared helpers

### Tests

- Stabilize pytest temp-path handling for the current Windows/OneDrive workspace
- Add regression coverage for strict import ID contracts and malformed payload handling
- Add coverage for bootstrap/runtime SQLite integrity flows
- Add regression coverage for grouped report metadata preservation
- Add contract coverage for snapshot metadata and mandatory record type

### Docs

- Update `README.md` and `README_EN.md` for import validation, launch mode, report grouping, and snapshot metadata

No breaking changes.

---

## [1.2.1] - 2026-03-07

### Refactor

- Finalize SQLite as the only runtime storage backend
- Remove `USE_SQLITE` feature flag and runtime branching
- Simplify bootstrap to always initialize and validate `finance.db`
- Remove JSON runtime bootstrap and startup export flow
- Keep JSON only for import, export, backup, and migration workflows

### Changed

- Repositories now use SQLite runtime storage by default
- Import pipeline now commits application data through SQLite transactions only
- Transfer-linked records now cascade on SQLite transfer deletion

### Tests

- Add SQLite runtime coverage for bootstrap initialization
- Add integration coverage for JSON/CSV/XLSX import into SQLite
- Add rollback regression coverage to ensure failed imports do not mutate the database
- Add cascade-delete verification for transfers and linked records

### Docs

- Update `README.md` and `README_EN.md` to describe SQLite as primary runtime storage
- Add release draft for tag `Finalize SQLite storage backend`

This release removes the legacy dual-backend runtime model.

---

## [1.2.0] - 2026-03-05

### Added

- Immutable snapshot backup format
- SHA256 integrity validation
- Readonly import protection
- Force override mode

### Security

- Prevent import of modified backups
- Guarantee transactional rollback on integrity failure

### Docs

- Update `README.md` and `README_EN.md` with new backup format details
- Document the force override mode and integrity validation process

---

## [1.1.3] - 2026-03-04

### Fixed

- Reject duplicate `initial_balance` rows during import (transaction aborts)
- Enforce strict positive integer `wallet_id` parsing for import rows
- Normalize imported `mandatory_expenses` template IDs to `1..N` in bulk replace path
- Reject non-finite numeric payloads (`NaN`, `inf`) in import amounts and IDs
- Remove `date` from `mandatory_expenses` schema/export payloads (CSV/XLSX/backup)
- Align JSON/SQLite repositories and migration flow to persist mandatory templates without `date`
- Restore compatibility wrappers `report_from_csv` / `report_from_xlsx` for report adapters

### Tests

- Add regression coverage for duplicate `initial_balance` handling
- Add contract test for strict `wallet_id` validation (no fractional values)
- Add coverage for mandatory template ID normalization in bulk import
- Add regression tests for overflow/non-finite numeric values in import rows

### Docs

- Update `README.md` and `README_EN.md` with new import validation rules
- Document that `mandatory_expenses` templates no longer store/export `date`

No breaking changes.

---

## [1.1.2] - 2026-03-04

### Performance

- Implement bulk import replace flow via `replace_all_for_import`
- Build records/transfers in memory and persist once for faster JSON imports
- Decouple SQLite startup cost when `USE_SQLITE=False`
- Lazy-load SQLite modules in bootstrap
- Optimize Windows file lock retry logic (`WinError 5/32`)

### Refactor

- Remove `report_from_csv` wrapper
- Simplify import pipeline integration

No breaking changes.

---

## [1.1.1] - 2026-03-02

### Removed

- Remove deprecated web frontend directory

---

## [1.1.0] - 2026-03-02

### Fixed

- Harden SQLite bootstrap integrity checks
- Restore deterministic ID normalization
- Fix transfer append ordering issues

### Stability

- Strengthen SQLite data consistency guarantees

---

## [1.0.1] - 2026-03-01

### Refactor

- Overhaul SQLite import pipeline with service architecture
- Add safety guardrails for migration consistency

---

## [1.0.0] - 2026-03-01

### Added

- SQLite as primary storage
- Storage abstraction layer
- Robust bootstrap process
- JSON-to-SQLite migration support

### Changed

- Application storage backend migrated from JSON to SQLite

This marks the beginning of the SQL era.

---

## [0.6.0] - 2026-02-28

### Added

- Storage abstraction layer
- JSON-to-SQLite migration foundation

### Stability

- Final stable JSON-based release

This is the last stable release before SQLite migration.

---

## [0.5.0] - 2026-02-19

### Added

- Wallet transfers with commissions
- Net worth calculation
- Wallet domain model

---

## [0.2.0] - 2026-01-20

### Changed

- Replace CLI with multi-window Tkinter GUI

---

## [0.1.0] - 2026-01-20

### Added

- Initial CLI-based financial accounting prototype
- Layered backend structure (domain, application, infrastructure)
