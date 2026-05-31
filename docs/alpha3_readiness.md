# Ledgera v3.0.0 Alpha.3 Readiness

## Status

`v3.0.0-alpha.3` is closed as the first Rust-backed planning write-path and local sync MVP.

The app still exposes the existing Python service, controller, dataclass, and GUI contracts. Rust remains opt-in through `LEDGERA_ENABLE_RUST_CORE=1`, and `LEDGERA_FORCE_PYTHON_FALLBACK=1` keeps the Python path available for validation and rollback where a fallback exists.

## Completed

- `DistributionService` can delegate item/subitem CRUD, structure replacement, validation helpers, monthly payload reads, frozen-row operations, freeze/unfreeze checks, and history reads to Rust.
- `BudgetService` can delegate budget create/list/delete/update-limit/replace operations and spent/overlap helpers to Rust.
- `DebtService` can delegate debt creation, loan creation, payment/write-off registration, payment deletion, debt deletion, row replacement, history reads, and recalculation helpers to Rust.
- Rust planning mutations use primitive payloads and atomic SQLite transactions while Python keeps public models, validation, and dataclass reconstruction.
- `ledgera-sync` provides the first Desktop LAN sync prototype for standalone income/expense records.
- Sync supports daemon start/stop/status, peer discovery, and one-shot push through the Python bridge and `SyncService`.
- `AuditService` can delegate the full current 15-check AuditEngine v2 contract to a Rust read-only batch path.
- Seam-level logging now covers bridge capability decisions, sync lifecycle/results, audit Rust completion/fallback, controller sync entrypoints, and planning Rust/Python boundaries.
- Root-level smoke and wrapper tests cover the new planning, sync, audit, and logging contracts.

## Runtime Flags

- `LEDGERA_ENABLE_RUST_CORE=1` enables Rust-backed bridge loading.
- `LEDGERA_FORCE_PYTHON_FALLBACK=1` forces Python fallback and skips importing the Rust extension.
- If both variables are set, forced Python fallback wins.

## Compatibility Boundaries

- Python remains the owner of public service signatures, dataclasses, enums, GUI/controller APIs, user-facing validation, and date/scope normalization.
- Rust planning write paths start only after Python validation and use one SQLite transaction per mutation.
- A Rust mutation failure is propagated; Python fallback is not retried after a Rust write has started.
- Rust audit is strictly read-only and does not perform repair actions, migrations, cache writes, or schema changes.
- Sync is additive-only and limited to standalone `records` rows where `transfer_id IS NULL`, `related_debt_id IS NULL`, and type is `income` or `expense`.
- Sync inserts remote rows as new local IDs and detects duplicates by canonical fingerprint, not by preserving remote IDs.
- Sync excludes transfers, debt-linked records, mandatory templates, budgets, distribution snapshots, assets, goals, tags, and all updates/deletes/conflicts.
- Sync discovery startup fails if the UDP discovery port cannot be bound, so the UI does not report a listening daemon with dead discovery.
- Seam logs must stay diagnostic only: no full financial payloads, descriptions, tags, amounts, or full local DB paths.

## Validation Evidence

- `cargo test` in `rust/ledgera_engine`
- `cargo clippy --all-targets -- -D warnings` in `rust/ledgera_engine`
- `maturin build --release`
- Fresh `ledgera_core` wheel installation before Rust-backed Python smoke tests
- Targeted Rust-enabled pytest for planning wrappers, sync service, audit engine, audit wrapper, bridge, and `ledgera_core` package tests
- Forced Python fallback parity tests for migrated planning and analytics paths
- Rust sync daemon lifecycle tests are serialized around the shared daemon singleton to keep parallel test runs deterministic
- `npx -y pyright` on bridge, planning services, sync service, audit service, controller seams, stubs, and touched tests
- Manual local two-Desktop sync acceptance: `SyncResult(inserted=1, skipped=0, errors=0)` with `elapsed=0.049s`

## Deferred

- General record write-path migration outside debt-created cashflow records.
- Sync for transfers, debts, budgets, distribution, tags, assets, goals, mandatory templates, updates, deletes, conflict resolution, and CRDT.
- Pairing/settings UI, authentication, encryption, cloud relay, mobile/Kotlin client, and Android sync.
- Rust-owned schema migrations, WAL bootstrap, and broad repository replacement.
- Audit repair/autofix UI and sync-conflict audit checks.

## Acceptance

Alpha.3 is ready to merge into `v3.0.0-alpha` when PR review feedback is addressed, the Rust/Python targeted gates are green, and the PR documents the remaining sync and Rust ownership boundaries listed above.
