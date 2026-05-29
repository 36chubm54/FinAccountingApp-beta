from __future__ import annotations

import argparse
import os
import sqlite3
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from infrastructure.sqlite_repository import SQLiteRecordRepository  # noqa: E402
from services.analytics import metrics as metrics_module  # noqa: E402
from services.analytics import timeline as timeline_module  # noqa: E402
from services.analytics.metrics import MetricsService  # noqa: E402
from services.analytics.timeline import TimelineService  # noqa: E402

SCHEMA_PATH = ROOT / "db" / "schema.sql"
TMP_ROOT = ROOT / "tests" / "_tmp"


def _remove_if_unlocked(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except PermissionError:
        print(f"warning: benchmark database is still locked and was not removed: {path}")


def _seed_db(db_path: Path, rows: int) -> None:
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        conn.execute(
            "INSERT INTO wallets (id, name, currency, initial_balance, is_active) "
            "VALUES (1, 'Bench', 'KZT', 0, 1)"
        )
        for index in range(rows):
            record_type = "income" if index % 5 == 0 else "expense"
            category = "Salary" if record_type == "income" else f"Category {index % 12}"
            amount = 1000.0 if record_type == "income" else float(10 + index % 200)
            month = (index % 12) + 1
            day = (index % 28) + 1
            conn.execute(
                "INSERT INTO records "
                "(type, date, wallet_id, amount_original, currency, rate_at_operation, amount_base, category) "  # noqa: E501
                "VALUES (?, ?, 1, ?, 'KZT', 1.0, ?, ?)",
                (record_type, f"2026-{month:02d}-{day:02d}", amount, amount, category),
            )
        conn.commit()
    finally:
        conn.close()


def _time_call(label: str, iterations: int, callback) -> float:
    started = time.perf_counter()
    for _ in range(iterations):
        callback()
    elapsed = time.perf_counter() - started
    print(f"{label}: {elapsed:.4f}s total, {elapsed / iterations:.6f}s/op")
    return elapsed


def _backend_label() -> str:
    metrics_backend = "rust" if metrics_module._RUST_METRICS_CORE is not None else "python"
    timeline_backend = "rust" if timeline_module._RUST_TIMELINE_CORE is not None else "python"
    return f"metrics={metrics_backend}, timeline={timeline_backend}"


def main() -> None:
    parser = argparse.ArgumentParser(description="Alpha.2 analytics bridge benchmark")
    parser.add_argument("--rows", type=int, default=10_000)
    parser.add_argument("--iterations", type=int, default=25)
    args = parser.parse_args()

    os.environ.setdefault("LEDGERA_ENABLE_RUST_CORE", "1")
    TMP_ROOT.mkdir(exist_ok=True)
    db_path = TMP_ROOT / f"alpha2_bench_{os.getpid()}.db"
    try:
        _remove_if_unlocked(db_path)
        _seed_db(db_path, args.rows)
        repo = SQLiteRecordRepository(str(db_path), schema_path=str(SCHEMA_PATH))
        try:
            if metrics_module._RUST_METRICS_CORE is None:
                raise RuntimeError(
                    "Rust metrics core is unavailable; build/install ledgera_core before benchmarking"  # noqa: E501
                )
            print(f"backend: {_backend_label()}")
            print(f"fixture: rows={args.rows}, iterations={args.iterations}")
            metrics = MetricsService(repo)
            timeline = TimelineService(repo)
            rust_elapsed = _time_call(
                "rust-or-current metrics",
                args.iterations,
                lambda: (
                    metrics.get_savings_rate("2026-01-01", "2026-12-31"),
                    metrics.get_spending_by_category("2026-01-01", "2026-12-31", limit=10),
                    metrics.get_monthly_summary(),
                    timeline.get_monthly_cashflow(),
                ),
            )

            rust_core = metrics_module._RUST_METRICS_CORE
            rust_timeline_core = timeline_module._RUST_TIMELINE_CORE
            metrics_module._RUST_METRICS_CORE = None
            timeline_module._RUST_TIMELINE_CORE = None
            try:
                print(f"fallback backend: {_backend_label()}")
                fallback_metrics = MetricsService(repo)
                fallback_timeline = TimelineService(repo)
                fallback_elapsed = _time_call(
                    "python-fallback metrics",
                    args.iterations,
                    lambda: (
                        fallback_metrics.get_savings_rate("2026-01-01", "2026-12-31"),
                        fallback_metrics.get_spending_by_category(
                            "2026-01-01", "2026-12-31", limit=10
                        ),
                        fallback_metrics.get_monthly_summary(),
                        fallback_timeline.get_monthly_cashflow(),
                    ),
                )
            finally:
                metrics_module._RUST_METRICS_CORE = rust_core
                timeline_module._RUST_TIMELINE_CORE = rust_timeline_core
            if rust_elapsed > 0:
                print(f"speedup_vs_python: {fallback_elapsed / rust_elapsed:.2f}x")
        finally:
            repo.close()
    finally:
        _remove_if_unlocked(db_path)


if __name__ == "__main__":
    main()
