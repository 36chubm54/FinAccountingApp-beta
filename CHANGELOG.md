# Changelog

All notable changes to this project will be documented in this file.

The format is based on Keep a Changelog.
This project adheres to Semantic Versioning.

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
- Import preview dialog in `Operations` tab: displays record count, skipped rows, and errors before the user confirms the operation
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
