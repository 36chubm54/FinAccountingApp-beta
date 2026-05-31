from __future__ import annotations

import hashlib
import socket
from dataclasses import dataclass
from typing import Any

from bridge.ledgera_bridge import get_sync_core

_RUST_SYNC_CORE = get_sync_core()
DEFAULT_DISCOVERY_PORT = 37639


@dataclass(frozen=True, slots=True)
class SyncStatus:
    enabled: bool
    running: bool
    bind_host: str = ""
    bind_port: int = 0
    device_id: str = ""
    device_name: str = ""
    last_error: str | None = None


@dataclass(frozen=True, slots=True)
class SyncPeer:
    host: str
    port: int
    device_id: str
    device_name: str


@dataclass(frozen=True, slots=True)
class SyncResult:
    inserted: int
    skipped: int
    errors: int


class SyncService:
    def __init__(self, repository: Any) -> None:
        self._repo = repository

    def start_daemon(
        self,
        *,
        bind_host: str = "127.0.0.1",
        bind_port: int = 0,
        discovery_enabled: bool = False,
        discovery_port: int = DEFAULT_DISCOVERY_PORT,
        poll_interval_ms: int = 1000,
        device_name: str | None = None,
    ) -> SyncStatus:
        core = _RUST_SYNC_CORE
        if core is None or not self._db_path():
            return self._disabled_status()
        return self._status_from_payload(
            core.sync_start_daemon(
                self._config(
                    bind_host=bind_host,
                    bind_port=bind_port,
                    discovery_enabled=discovery_enabled,
                    discovery_port=discovery_port,
                    poll_interval_ms=poll_interval_ms,
                    device_name=device_name,
                )
            )
        )

    def stop_daemon(self) -> SyncStatus:
        core = _RUST_SYNC_CORE
        if core is None:
            return self._disabled_status()
        return self._status_from_payload(core.sync_stop_daemon())

    def status(self) -> SyncStatus:
        core = _RUST_SYNC_CORE
        if core is None:
            return self._disabled_status()
        return self._status_from_payload(core.sync_status())

    def discover_peers(
        self,
        timeout_ms: int = 1000,
        *,
        discovery_port: int = DEFAULT_DISCOVERY_PORT,
    ) -> list[SyncPeer]:
        core = _RUST_SYNC_CORE
        if core is None:
            return []
        return [
            self._peer_from_payload(row)
            for row in core.sync_discover_peers(int(timeout_ms), int(discovery_port))
        ]

    def push_once(
        self,
        peer_host: str,
        peer_port: int,
        *,
        bind_host: str = "127.0.0.1",
        discovery_port: int = DEFAULT_DISCOVERY_PORT,
        device_name: str | None = None,
    ) -> SyncResult:
        core = _RUST_SYNC_CORE
        if core is None or not self._db_path():
            return SyncResult(inserted=0, skipped=0, errors=0)
        payload = core.sync_push_once(
            self._config(
                bind_host=bind_host,
                bind_port=0,
                discovery_enabled=False,
                discovery_port=discovery_port,
                poll_interval_ms=1000,
                device_name=device_name,
            ),
            peer_host,
            int(peer_port),
        )
        return self._result_from_payload(payload)

    def _config(
        self,
        *,
        bind_host: str,
        bind_port: int,
        discovery_enabled: bool,
        discovery_port: int,
        poll_interval_ms: int,
        device_name: str | None,
    ) -> dict[str, object]:
        db_path = self._db_path() or ""
        return {
            "db_path": db_path,
            "device_id": self._device_id(db_path),
            "device_name": device_name or socket.gethostname() or "Ledgera Desktop",
            "bind_host": bind_host,
            "bind_port": int(bind_port),
            "discovery_enabled": bool(discovery_enabled),
            "discovery_port": int(discovery_port),
            "poll_interval_ms": int(poll_interval_ms),
        }

    def _db_path(self) -> str | None:
        db_path = getattr(self._repo, "db_path", None)
        return db_path if isinstance(db_path, str) and db_path else None

    @staticmethod
    def _device_id(db_path: str) -> str:
        return hashlib.sha256(db_path.encode("utf-8")).hexdigest()[:16]

    @staticmethod
    def _disabled_status() -> SyncStatus:
        return SyncStatus(enabled=False, running=False)

    @staticmethod
    def _status_from_payload(payload: dict[str, object]) -> SyncStatus:
        return SyncStatus(
            enabled=bool(payload.get("enabled", False)),
            running=bool(payload.get("running", False)),
            bind_host=str(payload.get("bind_host") or ""),
            bind_port=_int_payload(payload.get("bind_port")),
            device_id=str(payload.get("device_id") or ""),
            device_name=str(payload.get("device_name") or ""),
            last_error=(
                str(payload["last_error"]) if payload.get("last_error") is not None else None
            ),
        )

    @staticmethod
    def _peer_from_payload(payload: dict[str, object]) -> SyncPeer:
        return SyncPeer(
            host=str(payload.get("host") or ""),
            port=_int_payload(payload.get("port")),
            device_id=str(payload.get("device_id") or ""),
            device_name=str(payload.get("device_name") or ""),
        )

    @staticmethod
    def _result_from_payload(payload: dict[str, object]) -> SyncResult:
        return SyncResult(
            inserted=_int_payload(payload.get("inserted")),
            skipped=_int_payload(payload.get("skipped")),
            errors=_int_payload(payload.get("errors")),
        )


def _int_payload(value: object) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int | float | str):
        return int(value)
    return 0
