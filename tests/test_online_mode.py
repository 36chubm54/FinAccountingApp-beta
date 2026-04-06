import json
from pathlib import Path
from datetime import datetime

import app.services as app_services
from app.services import CurrencyService


def test_default_is_offline():
    svc = CurrencyService()
    assert svc.is_online is False
    assert svc.last_fetched_at is None


def test_init_with_online_true_sets_online_state(monkeypatch):
    monkeypatch.setattr(CurrencyService, "_fetch_online_rates", lambda self: {"USD": 505.0})
    svc = CurrencyService(use_online=True)
    assert svc.is_online is True
    assert isinstance(svc.last_fetched_at, datetime)


def test_set_online_returns_false_when_unchanged():
    svc = CurrencyService()
    changed = svc.set_online(False)
    assert changed is False


def test_set_online_switches_mode(monkeypatch):
    svc = CurrencyService()
    monkeypatch.setattr(svc, "_fetch_online_rates", lambda: {"USD": 505.0})
    changed = svc.set_online(True)
    assert changed is True
    assert svc.is_online is True


def test_set_online_can_switch_back_offline(monkeypatch):
    svc = CurrencyService()
    monkeypatch.setattr(svc, "_fetch_online_rates", lambda: {"USD": 505.0})
    svc.set_online(True)
    changed = svc.set_online(False)
    assert changed is True
    assert svc.is_online is False


def test_last_fetched_at_updated_after_successful_fetch(monkeypatch):
    svc = CurrencyService()
    monkeypatch.setattr(svc, "_fetch_online_rates", lambda: {"USD": 505.0})
    svc.set_online(True)
    assert isinstance(svc.last_fetched_at, datetime)


def test_last_fetched_at_is_none_when_offline():
    svc = CurrencyService()
    assert svc.last_fetched_at is None


def test_set_online_fetch_error_keeps_online_without_timestamp(monkeypatch):
    svc = CurrencyService()

    def bad_fetch():
        raise RuntimeError("no network")

    monkeypatch.setattr(svc, "_fetch_online_rates", bad_fetch)
    old_fetched = svc.last_fetched_at
    svc.set_online(True)
    assert svc.is_online is True
    assert svc.last_fetched_at == old_fetched


def test_refresh_rates_returns_false_when_offline():
    svc = CurrencyService()
    assert svc.refresh_rates() is False


def test_refresh_rates_updates_timestamp_when_online(monkeypatch):
    svc = CurrencyService()
    monkeypatch.setattr(svc, "_fetch_online_rates", lambda: {"USD": 505.0})
    svc.set_online(True)
    old_fetched = svc.last_fetched_at
    assert old_fetched is not None
    monkeypatch.setattr(svc, "_fetch_online_rates", lambda: {"USD": 506.0})
    assert svc.refresh_rates() is True
    assert isinstance(svc.last_fetched_at, datetime)
    assert svc.last_fetched_at >= old_fetched


def test_save_cache_is_atomic_when_replace_fails(tmp_path, monkeypatch):
    cache_path = tmp_path / "currency_rates.json"
    cache_path.write_text(json.dumps({"USD": 500.0}), encoding="utf-8")
    monkeypatch.setattr(CurrencyService, "CACHE_FILE", cache_path)

    original_replace = app_services.os.replace

    def failing_replace(src, dst):
        raise OSError("replace failed")

    monkeypatch.setattr(app_services.os, "replace", failing_replace)

    svc = CurrencyService()
    svc._save_cache({"USD": 600.0})

    assert json.loads(cache_path.read_text(encoding="utf-8")) == {"USD": 500.0}
    temp_files = list(Path(tmp_path).glob(".currency_rates_*.json"))
    assert temp_files == []
    monkeypatch.setattr(app_services.os, "replace", original_replace)
