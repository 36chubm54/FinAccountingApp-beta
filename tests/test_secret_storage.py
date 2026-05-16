from __future__ import annotations

import app.secret_storage as secret_storage
from app.secret_storage import get_secret_storage_status


def test_secret_storage_status_marks_fail_backend_unavailable(monkeypatch) -> None:
    class FailKeyring:
        __module__ = "keyring.backends.fail"

    monkeypatch.setattr(secret_storage, "_keyring_backend", lambda: FailKeyring())

    status = get_secret_storage_status()

    assert status.available is False
    assert status.backend_name == "FailKeyring"


def test_secret_storage_status_marks_nonpositive_priority_backend_unavailable(
    monkeypatch,
) -> None:
    class HeadlessBackend:
        __module__ = "custom.backend"
        priority = 0

    monkeypatch.setattr(secret_storage, "_keyring_backend", lambda: HeadlessBackend())

    status = get_secret_storage_status()

    assert status.available is False
    assert status.backend_name == "HeadlessBackend"
