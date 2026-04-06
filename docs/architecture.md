# Architecture Guide

This document keeps the technical map of the project outside the compact release-oriented `README.md` / `README_EN.md`.

It is intended for contributors who need to understand where logic lives, how the runtime is composed, and which modules usually change together.

## 1. System Overview

The application is a Tkinter desktop app backed by SQLite at runtime.

At a high level:

1. `main.py` starts the GUI
2. `bootstrap.py` validates and prepares runtime storage
3. `gui/tkinter_gui.py` builds the application shell and tabs
4. `gui/controllers.py` exposes app-level operations to the UI
5. `app/use_cases.py` and `services/*` implement business flows
6. `infrastructure/sqlite_repository.py` and `storage/sqlite_storage.py` persist runtime data

Supported business areas include:

- records, transfers, wallets
- budgets
- debts and loans
- monthly distribution
- strategic assets and goals
- analytics, reports, and audit
- import / export / backup / migration

## 2. Layer Map

| Layer | Purpose | Main modules |
| --- | --- | --- |
| `domain` | Immutable entities, enums, validation rules, report DTOs | `records.py`, `wallets.py`, `budget.py`, `debt.py`, `asset.py`, `goal.py`, `reports.py`, `audit.py`, `validation.py` |
| `app` | Use cases and application orchestration | `use_cases.py`, `use_case_support.py`, `finance_service.py`, `record_service.py` |
| `services` | Focused business subsystems and read-only engines | `import_service.py`, `audit_service.py`, `balance_service.py`, `metrics_service.py`, `timeline_service.py`, `budget_service.py`, `debt_service.py`, `distribution_service.py`, `asset_service.py`, `goal_service.py`, `dashboard_service.py` |
| `infrastructure` | Runtime repository implementation | `sqlite_repository.py`, `repositories.py` |
| `storage` | Low-level persistence adapters and schema bootstrap | `sqlite_storage.py`, `json_storage.py`, `base.py` |
| `gui` | Tkinter presentation layer | `tkinter_gui.py`, `controllers.py`, `tabs/*`, `exporters.py`, `importers.py`, `tooltip.py` |
| `utils` | Format-specific helpers and shared technical helpers | `backup_utils.py`, `import_core.py`, `csv_utils.py`, `excel_utils.py`, `pdf_utils.py`, `money.py`, `charting.py`, `debt_report_utils.py`, `tabular_utils.py` |
| `tests` | Regression, contract, and integration-like coverage | `test_*` modules across all subsystems |

## 3. Key Runtime Flows

### 3.1 Startup

- `main.py` launches the app
- `bootstrap.py` prepares runtime SQLite state
- `storage/sqlite_storage.py` initializes schema and compatibility migrations
- `gui/tkinter_gui.py` creates the main window and tabs
- post-startup maintenance may run after the first window paint

Important startup concerns:

- SQLite integrity and schema readiness
- JSON export/backup synchronization
- optional currency refresh
- auto-application of mandatory payments

### 3.2 Creating or Editing Financial Data

Typical path:

`GUI tab -> FinancialController -> use case / service -> SQLiteRecordRepository -> SQLiteStorage`

Examples:

- operations and transfers are initiated from `gui/tabs/operations_tab.py`
- debts/loans are initiated from `gui/tabs/debts_tab.py`
- assets/goals are initiated from `gui/tabs/dashboard_tab.py`

### 3.3 Reports and Analytics

There are three main read-only analytics layers:

- `BalanceService` — balances and net worth
- `MetricsService` — rates, category summaries, month summaries
- `TimelineService` — month-by-month historical aggregates

Report UI uses:

- `gui/tabs/reports_tab.py`
- `gui/tabs/reports_controller.py`
- `services/report_service.py`

Export uses:

- `gui/exporters.py`
- `utils/csv_utils.py`
- `utils/excel_utils.py`
- `utils/pdf_utils.py`

### 3.4 Import / Backup / Migration

Main application import entry:

- `FinancialController.import_records(...)`
- `services.import_service.ImportService.import_file(...)`

Low-level backup helpers:

- `utils.backup_utils.export_full_backup_to_json(...)`
- `utils.backup_utils.import_full_backup_from_json(...)`

Migration entry:

- `migrate_json_to_sqlite.py`

Important details:

- dry-run and real import share the same validation pipeline
- readonly snapshots require `force=True`
- JSON full backups can contain extended runtime entities such as budgets, debts, assets, goals, and distribution payloads
- compatibility logic in `storage/sqlite_storage.py` protects older SQLite databases during schema initialization

## 4. Subsystem Map

### 4.1 Records / Wallets / Transfers

Core modules:

- `domain/records.py`
- `domain/wallets.py`
- `domain/transfers.py`
- `infrastructure/sqlite_repository.py`

These form the base event history used by reports and analytics.

### 4.2 Budgets

Core modules:

- `domain/budget.py`
- `services/budget_service.py`
- `gui/tabs/budget_tab.py`

Budgets are date-ranged category limits with live execution tracking.

### 4.3 Debts and Loans

Core modules:

- `domain/debt.py`
- `services/debt_service.py`
- `gui/tabs/debts_tab.py`
- `utils/debt_report_utils.py`

This subsystem links debt payments to cashflow records and affects net worth and report exports.

### 4.4 Distribution

Core modules:

- `domain/distribution.py`
- `services/distribution_service.py`
- `gui/tabs/distribution_tab.py`

This subsystem calculates monthly net-income allocation and supports frozen snapshot rows.

### 4.5 Assets / Goals / Dashboard

Core modules:

- `domain/asset.py`
- `domain/goal.py`
- `domain/dashboard.py`
- `services/asset_service.py`
- `services/goal_service.py`
- `services/dashboard_service.py`
- `gui/tabs/dashboard_tab.py`

This subsystem adds a strategic wealth-management layer above the transactional ledger.

### 4.6 Audit

Core modules:

- `domain/audit.py`
- `services/audit_service.py`

Audit is intentionally read-only and validates runtime integrity without mutating data.

## 5. Data Model Overview

Main SQLite tables:

- `wallets`
- `records`
- `transfers`
- `mandatory_expenses`
- `budgets`
- `debts`
- `debt_payments`
- `distribution_items`
- `distribution_subitems`
- `distribution_snapshots`
- `assets`
- `asset_snapshots`
- `goals`

Important data-model notes:

- money values often use dual storage: human-readable values plus exact `*_minor`
- records may reference `transfer_id` and `related_debt_id`
- debt, asset, and goal data affect read-only wealth calculations
- schema/bootstrap compatibility must be preserved for older SQLite databases

## 6. Change Patterns

When adding a new domain concept, the usual sequence is:

1. Add immutable domain models and validation
2. Extend SQLite schema and storage/repository mapping
3. Add service and/or use case logic
4. Expose it through `FinancialController`
5. Wire it into a tab or export flow
6. Add tests across domain, service, controller, and integration paths
7. Update `README.md`, `README_EN.md`, and `CHANGELOG.md`

When changing import/export behavior, review together:

- `services/import_service.py`
- `services/import_parser.py`
- `utils/backup_utils.py`
- `gui/exporters.py`
- `migrate_json_to_sqlite.py`
- the related contract tests

## 7. Packaging Notes

Base runtime dependencies live in `requirements.txt`.

Optional PDF support is separated into:

- `requirements-pdf.txt`
- `pyproject.toml` optional dependency group `pdf`

This keeps the default install lighter while preserving PDF export as an add-on.

## 8. Where to Start

If you are new to the codebase:

- start with `README.md`
- open `gui/controllers.py`
- inspect `app/use_cases.py`
- then move into the service or tab that matches your feature area

For data-format issues:

- start with `services/import_service.py`
- then inspect `utils/backup_utils.py` and `migrate_json_to_sqlite.py`

For net-worth/report issues:

- start with `services/balance_service.py`
- then `services/timeline_service.py`, `services/report_service.py`, and report exporters
