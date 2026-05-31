from __future__ import annotations

import importlib
import sqlite3
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from gui.controllers_pkg.delegates import ControllerDelegateMixin
from services.sync import service as sync_service_module
from services.sync.service import SyncPeer, SyncResult, SyncService, SyncStatus


class _Repo:
    def __init__(self, db_path: str) -> None:
        self.db_path = db_path


class _FakeSyncCore:
    def __init__(self) -> None:
        self.configs: list[dict[str, object]] = []

    def sync_start_daemon(self, config: dict[str, object]) -> dict[str, object]:
        self.configs.append(config)
        return {
            "enabled": True,
            "running": True,
            "bind_host": config["bind_host"],
            "bind_port": 41234,
            "device_id": config["device_id"],
            "device_name": config["device_name"],
            "last_error": None,
        }

    def sync_stop_daemon(self) -> dict[str, object]:
        return {"enabled": True, "running": False, "bind_host": "127.0.0.1", "bind_port": 0}

    def sync_status(self) -> dict[str, object]:
        return {"enabled": True, "running": True, "last_error": None}

    def sync_discover_peers(self, timeout_ms: int, discovery_port: int) -> list[dict[str, object]]:
        assert timeout_ms == 50
        assert discovery_port == 37639
        return [
            {
                "host": "127.0.0.1",
                "port": 41234,
                "device_id": "peer",
                "device_name": "Peer",
            }
        ]

    def sync_push_once(
        self, config: dict[str, object], peer_host: str, peer_port: int
    ) -> dict[str, object]:
        self.configs.append(config)
        assert peer_host == "127.0.0.1"
        assert peer_port == 41234
        return {"inserted": 1, "skipped": 2, "errors": 0}


def _init_sync_db(path: Path) -> None:
    conn = sqlite3.connect(path)
    try:
        conn.executescript(
            """
            PRAGMA foreign_keys = ON;
            CREATE TABLE wallets (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                currency TEXT NOT NULL,
                initial_balance REAL NOT NULL DEFAULT 0,
                initial_balance_minor INTEGER DEFAULT NULL,
                system INTEGER NOT NULL DEFAULT 0,
                allow_negative INTEGER NOT NULL DEFAULT 0,
                is_active INTEGER NOT NULL DEFAULT 1
            );
            CREATE TABLE records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                type TEXT NOT NULL,
                date TEXT NOT NULL,
                wallet_id INTEGER NOT NULL,
                transfer_id INTEGER,
                related_debt_id INTEGER DEFAULT NULL,
                amount_original REAL NOT NULL,
                amount_original_minor INTEGER DEFAULT NULL,
                currency TEXT NOT NULL,
                rate_at_operation REAL NOT NULL,
                rate_at_operation_text TEXT DEFAULT NULL,
                amount_base REAL NOT NULL,
                amount_base_minor INTEGER DEFAULT NULL,
                category TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                period TEXT,
                FOREIGN KEY(wallet_id) REFERENCES wallets(id)
            );
            INSERT INTO wallets (id, name, currency) VALUES (1, 'Main', 'KZT');
            """
        )
        conn.commit()
    finally:
        conn.close()


def _insert_standalone_record(path: Path) -> None:
    conn = sqlite3.connect(path)
    try:
        conn.execute(
            """
            INSERT INTO records (
                type, date, wallet_id, amount_original, amount_original_minor,
                currency, rate_at_operation, rate_at_operation_text,
                amount_base, amount_base_minor, category, description
            )
            VALUES ('income', '2026-03-01', 1, 100.0, 10000, 'KZT', 1.0, '1.000000',
                    100.0, 10000, 'Salary', 'March')
            """
        )
        conn.commit()
    finally:
        conn.close()


def _record_count(path: Path) -> int:
    conn = sqlite3.connect(path)
    try:
        return int(conn.execute("SELECT COUNT(*) FROM records").fetchone()[0])
    finally:
        conn.close()


def test_sync_service_returns_disabled_status_when_core_missing(monkeypatch) -> None:
    monkeypatch.setattr(sync_service_module, "_RUST_SYNC_CORE", None)

    service = SyncService(SimpleNamespace(db_path="ledger.db"))

    assert service.status() == SyncStatus(enabled=False, running=False)
    assert service.start_daemon() == SyncStatus(enabled=False, running=False)
    assert service.stop_daemon() == SyncStatus(enabled=False, running=False)
    assert service.discover_peers() == []
    assert service.push_once("127.0.0.1", 1) == SyncResult(inserted=0, skipped=0, errors=0)


def test_sync_service_maps_rust_payloads(monkeypatch, tmp_path: Path) -> None:
    fake_core = _FakeSyncCore()
    monkeypatch.setattr(sync_service_module, "_RUST_SYNC_CORE", fake_core)
    service = SyncService(_Repo(str(tmp_path / "ledger.db")))

    status = service.start_daemon(
        bind_host="0.0.0.0",
        bind_port=45678,
        discovery_enabled=True,
        discovery_port=45679,
        poll_interval_ms=250,
        device_name="Test Device",
    )
    assert status.running is True
    assert status.bind_port == 41234
    assert fake_core.configs[0]["bind_host"] == "0.0.0.0"
    assert fake_core.configs[0]["bind_port"] == 45678
    assert fake_core.configs[0]["discovery_enabled"] is True
    assert fake_core.configs[0]["discovery_port"] == 45679
    assert fake_core.configs[0]["poll_interval_ms"] == 250
    assert fake_core.configs[0]["device_name"] == "Test Device"

    assert service.status() == SyncStatus(enabled=True, running=True)
    assert service.discover_peers(50) == [
        SyncPeer(host="127.0.0.1", port=41234, device_id="peer", device_name="Peer")
    ]
    assert service.push_once("127.0.0.1", 41234) == SyncResult(inserted=1, skipped=2, errors=0)


def test_controller_forwards_sync_daemon_lan_options() -> None:
    class _Sync:
        def __init__(self) -> None:
            self.kwargs: dict[str, object] = {}

        def start_daemon(self, **kwargs: object) -> SyncStatus:
            self.kwargs = kwargs
            return SyncStatus(enabled=True, running=True, bind_host=str(kwargs["bind_host"]))

    class _Controller(ControllerDelegateMixin):
        def __init__(self) -> None:
            self._sync: Any = _Sync()

    controller = _Controller()

    status = controller.start_sync_daemon(
        bind_host="0.0.0.0",
        bind_port=45678,
        discovery_enabled=True,
        discovery_port=45679,
        poll_interval_ms=250,
        device_name="LAN Device",
    )

    assert status.bind_host == "0.0.0.0"
    assert controller._sync.kwargs == {
        "bind_host": "0.0.0.0",
        "bind_port": 45678,
        "discovery_enabled": True,
        "discovery_port": 45679,
        "poll_interval_ms": 250,
        "device_name": "LAN Device",
    }


def test_sync_push_once_smoke_with_two_sqlite_databases(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("LEDGERA_ENABLE_RUST_CORE", "1")
    monkeypatch.delenv("LEDGERA_FORCE_PYTHON_FALLBACK", raising=False)
    reloaded = importlib.reload(sync_service_module)
    if reloaded._RUST_SYNC_CORE is None:
        pytest.skip("ledgera_core sync extension is not available")

    source_path = tmp_path / "source.db"
    peer_path = tmp_path / "peer.db"
    _init_sync_db(source_path)
    _init_sync_db(peer_path)
    _insert_standalone_record(source_path)

    source = reloaded.SyncService(_Repo(str(source_path)))
    peer = reloaded.SyncService(_Repo(str(peer_path)))
    status = peer.start_daemon(bind_host="127.0.0.1", bind_port=0, device_name="Peer")
    try:
        result = source.push_once("127.0.0.1", status.bind_port, device_name="Source")
        assert (result.inserted, result.skipped, result.errors) == (1, 0, 0)
        assert _record_count(peer_path) == 1

        duplicate = source.push_once("127.0.0.1", status.bind_port, device_name="Source")
        assert duplicate.inserted == 0
        assert duplicate.skipped == 1
        assert _record_count(peer_path) == 1
    finally:
        peer.stop_daemon()
