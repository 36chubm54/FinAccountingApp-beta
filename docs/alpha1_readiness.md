# Ledgera v3.0.0 Alpha.1 Readiness

## Status

`v3.0.0-alpha.1` is closed as a Rust/Python bridge MVP with Python-first runtime semantics.

The Rust engine is available through `bridge.ledgera_bridge`, but app runtime does not use it unless `LEDGERA_ENABLE_RUST_CORE=1` is set. This keeps the alpha.1 contract conservative: Python remains the default production path, while CI and local smoke tests can explicitly exercise Rust parity.

## Completed

- `rust/ledgera_engine` is a Cargo workspace with `core`, `storage`, and `ffi` crates.
- `rust/ledgera_engine/core` owns pure deterministic money/math helpers without Python dependencies.
- `rust/ledgera_engine/storage` owns read-only SQLite helpers and typed row extraction.
- `rust/ledgera_engine/ffi` owns the PyO3 `ledgera_core` extension boundary.
- `bridge.ledgera_bridge` is the only app-level loader for the Rust extension.
- Money helpers have Rust/Python parity coverage.
- Balance read paths have Rust/Python parity coverage.
- SQLite read paths for records, wallets, transfers, and mandatory expenses have Rust/Python parity coverage.
- Root CI covers Ubuntu and Windows with `cargo check`, `cargo test`, `cargo clippy --all-targets -- -D warnings`, `maturin build` + wheel install, targeted `pytest`, and `pyright`.
- App packaging workflows build the Rust extension before PyInstaller.

## Runtime Flags

- `LEDGERA_ENABLE_RUST_CORE=1` enables Rust-backed bridge loading.
- `LEDGERA_FORCE_PYTHON_FALLBACK=1` forces Python fallback and skips importing the Rust extension.
- If both variables are set, forced Python fallback wins.

## Read Path Constraints

- Rust repository readers are read-only in alpha.1.
- Python remains the owner of SQLite mutations, ID normalization, tag updates, debt-payment remapping, and transaction-local visibility.
- Repository Rust reads are skipped when the current Python SQLite connection is inside a transaction or has performed writes after repository startup.
- `get_transfer_id_by_record_index(...)` intentionally remains on the Python SQLite connection because it depends on Python-side normalized transfer IDs.
- These constraints are compatibility boundaries, not final v3 architecture. They should be revisited when `storage` owns write paths and normalization.

## Validation Evidence

- `cargo check --workspace`
- `cargo test --workspace`
- `cargo clippy --workspace --all-targets -- -D warnings`
- `maturin build --out dist/wheels`
- Rust-enabled seam pytest: bridge, money, balance, record wrapper, and `ledgera_core` package tests
- Forced Python fallback pytest for the Rust-backed wrapper slice
- Full pytest with `LEDGERA_ENABLE_RUST_CORE=1`: `848 passed, 185 skipped`
- `npx -y pyright`: `0 errors, 0 warnings`

## Deferred

- Move mutation/write paths such as `RecordEngine::add` into Rust.
- Add the future `sync` crate when alpha.3 local synchronization work starts.
- Add SQLite WAL bootstrap and Rust-owned migrations when write paths move into `storage`.
- Add Kotlin/Native FFI, mobile UI, and sync work.

## Acceptance

Alpha.1 is ready to merge into `v3.0.0-alpha` when the root Rust Alpha1 workflow is green and the branch contains no code changes outside the documented bridge/read-only MVP scope.
