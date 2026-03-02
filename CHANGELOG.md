# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Storage Abstraction and SQLite Migration Foundation (Day 1):
  - Added `storage/base.py` with `Storage` contract for wallets, records, transfers, and mandatory expenses.
  - Added `storage/json_storage.py` (`JsonStorage`) as a wrapper over current JSON persistence.
  - Added `storage/sqlite_storage.py` (`SQLiteStorage`) on standard `sqlite3` with:
    - `PRAGMA foreign_keys = ON`,
    - `PRAGMA journal_mode = WAL`,
    - domain-object mapping for read/write operations.
  - Added `db/schema.sql` with tables `wallets`, `records`, `transfers`, `mandatory_expenses`, including PK/FK/CHECK constraints and date/wallet indexes.
  - Preserved existing domain models and service-layer business logic without changes.
- JSON -> SQLite Migration Script:
  - Added `migrate_json_to_sqlite.py` with `parse_args()`, `main()`, `run_dry_run()`, `run_migration()`, and `validate_migration()`.
  - Added dry-run mode with source integrity checks and migration statistics output without inserts.
  - Added transactional migration flow with strict insert order: wallets, transfers, records, mandatory expenses.
  - Added id-preservation and fallback id-mapping (`old_id -> new_id`) with reference remapping for `wallet_id` and `transfer_id`.
  - Added post-migration consistency checks: counts, wallet balances, and net worth; rollback on mismatch/error.
  - Added tests in `tests/test_migrate_json_to_sqlite.py` for dry-run and successful migration with id preservation.
- SQLite Primary Storage Bootstrap (Day 3):
  - Added `config.py` with `USE_SQLITE`, `SQLITE_PATH`, `JSON_PATH`.
  - Added `infrastructure/sqlite_repository.py` as `RecordRepository` implementation backed by SQLite.
  - Added `bootstrap.py` for storage selection and startup flow:
    - SQLite/JSON switch via config flag,
    - protection from repeated migration if SQLite already has data,
    - one-time migration from JSON when SQLite is empty,
    - startup integrity validation (counts + net worth) with emergency mode on mismatch.
  - Added `backup.py` with:
    - `create_backup()` for timestamped JSON backup at startup,
    - `export_to_json()` for SQLite -> JSON export without recalculations.
  - Updated GUI initialization to use bootstrap-selected repository while keeping service layer unchanged.
  - Added tests `tests/test_bootstrap_backup.py`.
- Migration script/test hardening:
  - Fixed `schema.sql` path resolution in `migrate_json_to_sqlite.py` for non-project working directories.
  - Updated migration tests to use absolute path to `db/schema.sql`.
  - Clarified test commands in docs to run via `python -m pytest` in active virtual environment.
- Migration reliability fixes:
  - Fixed fallback auto-ID insertion branches in `migrate_json_to_sqlite.py` to avoid forcing source ids.
  - Improved rerun behavior: migration now checks existing SQLite dataset and skips safely when data is equivalent.
  - Added test coverage for safe migration rerun on non-empty SQLite.
- Storage path fixes:
  - Fixed `config.py` storage paths to be anchored to the `project` directory.
  - Fixed migration script defaults to use `<project>/data.json`, `<project>/finance.db`, and `<project>/db/schema.sql`.
  - Ensured backup/database files are created inside `project` regardless of current working directory.
- Immutable Domain Model and SQL-ready Repository Layer (Phase 3.3):
  - Added immutable `Record.id` for stable identity of domain records.
  - Added `Record.with_updated_amount_kzt()` that returns a new instance via copy/replace.
  - Added repository contract methods `list_all()`, `get_by_id()` and `replace()`.
  - Added `RecordService.update_amount_kzt()` to centralize edit logic and block transfer-linked edits.
  - Added inline `Edit Amount KZT` action in `Operations` tab using service-layer update flow.
  - Added tests for immutable record behavior, service guardrails and repository replace flow.
- Transfer Aggregate Integrity and Cascade Delete (Phase 3.1):
  - Added `DomainError` for domain invariant violations.
  - Added `DeleteTransfer` use-case and controller method with atomic cascade delete.
  - Added protection from partial deletion: deleting transfer-linked record now deletes whole transfer.
  - Added repository-level transfer integrity validation on load/save:
    - each transfer must have exactly two linked records (`expense` + `income`),
    - dangling transfer-linked records are rejected.
  - Added migration for legacy commission transfer links to non-linked commission records.
  - Added logging for transfer creation/deletion and wallet creation/soft-delete.
  - Added unit tests for transfer integrity, cascade delete, and corruption detection.
- Wallet Operations Binding and Safe Delete (Phase 3):
  - Added mandatory `wallet_id` flow for income/expense creation.
  - Added `is_active` for wallets and safe soft delete for zero-balance wallets.
  - Added active-wallet filtering in GUI operation/transfer selectors.
  - Added domain/use-case checks for `allow_negative` during expense creation.
  - Added idempotent migration coverage for missing `wallet_id`.
  - Added phase-3 tests for wallet-bound operations, migration, soft delete and net worth.
- Wallets, Transfers and Commissions (Phase 2):
  - Added `Transfer` aggregate model and repository persistence.
  - Added `transfer_id` linkage in records and transfer double-entry creation.
  - Added transfer commission handling as a separate `Commission` expense.
  - Added wallet management enhancements including `allow_negative`.
  - Added dynamic net worth calculation (fixed and current).
  - Added transfer/wallet UI controls in desktop GUI (wallets + transfer form).
  - Added phase-2 unit tests for transfer invariants, commission effect, opening balance and date typing.
- Wallet Support (Phase 1):
  - Added `Wallet` domain model and system wallet (`id=1`, `Main wallet`).
  - Added `wallet_id` to records and automatic assignment to system wallet for new entries.
  - Added repository migration from legacy `initial_balance` to `wallet.initial_balance` with `initial_balance=0` in root JSON.
  - Added wallet-focused tests for migration invariants, record creation, report totals, opening balance, and date typing.
- Add initial balance feature to financial tracker
- Add mandatory expenses management feature
- Add CSV import and delete all records features
- Add web directory with frontend files (HTML, CSS, JS) for financial accounting interface
- Add delete all records functionality and improve currency service
- Add CSV export functionality for reports
- Add financial accounting project structure
- Add CSV import/export functionality for mandatory expenses with dedicated UI buttons and error handling
- Add utils module for mandatory expense CSV operations with validation and data integrity checks
- Add Excel import/export support: import records from `.xlsx` and export reports to `.xlsx`
- Add Excel import/export for mandatory expenses (sheet `Mandatory` with columns `Amount (KZT),Category,Description,Period`)
- Add PDF export support for reports and mandatory expenses
- UI: replace separate import/export buttons with format dropdowns and single Import/Export buttons (supports CSV, XLSX, PDF)
- Add monthly income/expense summary for past and current months in report output
- Add yearly report export as a separate XLSX sheet and as a second PDF table after the statement
- Limit XLSX report import to the first worksheet only
- Add infographic block to the main window: expense pie chart plus daily/monthly income-expense histograms
- Group minor expense categories into an "Other" slice in the pie chart
- Add time filter for the pie chart and make the category list scrollable
- Unit tests: add tests for `gui.exporters` and `gui.importers`.
- Add export of grouped category tables to Excel/PDF report after the main statement.
- Add multicurrency records with FX revaluation and unified data import/export
- Add import policies, validated row-level import, and full JSON backup support
- SQLite migration verification and startup integrity tests:
  - Added `tests/test_bootstrap_migration_verification.py` for `migration_verified` flow and SQLite-only startup validation.
  - Added `tests/test_transfer_order_sqlite.py` to verify transfer records are appended to the end of `records`.

### Removed

- Remove outdated web directory with frontend files (HTML, CSS, JS) for financial accounting interface

### Changed

- SQLite import/ID normalization and startup performance:
  - Restored deterministic ID normalization (`1..N`) for `wallets`, `records`, `transfers`, `mandatory_expenses` during full replacement flows.
  - Added wallet-id remapping in JSON backup import (`wallet.id`, `wallet_id`, `from_wallet_id`, `to_wallet_id`) to keep references consistent after normalization.
  - Reworked `replace_records_and_transfers()` to rebuild transfer/record sets with stable remapping and no manual ID collisions.
  - Added repository bootstrap check to normalize already-drifted IDs in existing SQLite datasets.
  - Added AUTOINCREMENT reset on table wipes (`sqlite_sequence`) so recreated entities start from `1`.
  - Hardened mandatory expense import/save path against missing wallet links (prevents FK failures on inconsistent payloads).
  - Removed hot-path `sync_sequences()` calls from frequent startup flow to fix long app startup delays.
- SQLite bootstrap integrity flow:
  - Added persistent migration marker `schema_meta.migration_verified`.
  - Switched startup behavior to one-time JSON vs SQLite verification only before migration confirmation.
  - Changed regular startup validation (with `USE_SQLITE=True`) to SQLite-only integrity checks.
  - Added stricter transfer integrity check in bootstrap validation: each transfer must be exactly `income + expense`.
- Transfer creation ordering:
  - Updated `CreateTransfer` to assign deterministic tail IDs for linked transfer records so transfer entries are persisted at the end of `records`.

- Updated transfer commission linkage:
  - transfer aggregate now keeps exactly two linked records via `transfer_id`,
  - commission remains a separate expense and is associated for cascade delete via description marker.
- Updated global report arithmetic to exclude transfer-linked records from net profit while keeping commission as expense.
- Updated controller record-list rendering to display transfer-linked records as one logical operation.
- Updated report/domain logic to use normalized `datetime.date` in records and opening-balance computations.
- Updated GUI flow so operation/report creation goes through `FinancialController` instead of direct use-case calls.
- Refactor online currency rates fetching (online mode remains opt-in)
- Replace CLI with Tkinter GUI for financial accounting
- Refactor: move export/import UI logic into `gui/exporters.py` and `gui/importers.py` and add `gui/helpers.py`.

- Improve PDF font registration to support Cyrillic on Windows/Linux, with multiple fallbacks.
- Improve GUI error handling: export/import handlers now log exceptions for diagnostics.
- Redesign GUI (tabs, error handling, and visual feedback).
- Fix filtered report totals to use period opening balance instead of global initial balance.
- Update report export rows (`CSV/XLSX/PDF`) to show opening balance label for filtered periods.
- Update GUI report summary label to show `Opening balance` for filtered reports and `Initial balance` otherwise.
- Expand `Report` tests to cover year/month/day filters, opening-balance invariant, and edge cases.
- Add strict report period validation for `YYYY`, `YYYY-MM`, `YYYY-MM-DD` and reject future filter dates.
- Add report period end filter and validate both start/end values including `end >= start`.
- Add period-range title to report generation and exports (`PDF/CSV/XLSX`), with default end date = today when end is omitted in GUI.
- Standardize filtered balance row label to `Opening balance`.

### Documentation

- Updated `README.md` and `README_EN.md` with storage abstraction, JSON/SQLite adapters, and `db/schema.sql` details.
- Updated `README.md` and `README_EN.md` with:
  - SQLite as source of truth,
  - `migration_verified` startup flow,
  - SQLite-only integrity checks after migration verification,
  - new tests for migration verification and transfer order.
- Updated `README.md` with SQLite ID normalization/reindex rules and JSON backup wallet-id remapping behavior.
- Documented `migrate_json_to_sqlite.py` usage and migration guarantees in `README.md` and `README_EN.md`.
- Fixed link to the "Web application" title in the README_EN.md table of contents
- Improve README formatting and add test setup note
- Add web application section to README.md with features, setup, and structure details
- Document main window infographics in README.md and README_EN.md
- Update READMEs and CHANGELOG to reflect GUI refactor, improved logging and font handling
- Add section `Opening Balance in Filtered Reports` to `README.md` and `README_EN.md`.

### Initial

- Initial commit: Financial accounting - backend with domain, application and infrastructure layers
