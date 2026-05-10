import json
from datetime import datetime
from pathlib import Path

import pytest
import requests

import app.services as app_services
from app.services import CurrencyService
from infrastructure.currency_aggregator import CurrencyAggregator
from infrastructure.currency_providers import (
    BaseRateProvider,
    CBRProvider,
    NBKProvider,
    OpenExchangeProvider,
    ProviderFetchError,
    StaticProvider,
)


class StubAggregator:
    def __init__(self, rates=None, error: Exception | None = None, provider_name: str = "nbk"):
        self._rates = dict(rates or {})
        self._error = error
        self.last_provider_name = provider_name

    def fetch_rates(self) -> dict[str, float]:
        if self._error is not None:
            raise self._error
        return dict(self._rates)


class DummyProvider(BaseRateProvider):
    def __init__(self, name: str, rates=None, error: Exception | None = None, calls=None):
        self._name = name
        self._rates = dict(rates or {})
        self._error = error
        self._calls = calls

    @property
    def name(self) -> str:
        return self._name

    def fetch(self) -> dict[str, float]:
        if self._calls is not None:
            self._calls.append(self._name)
        if self._error is not None:
            raise self._error
        return dict(self._rates)


class FakeResponse:
    def __init__(self, text: str = "", payload=None, status_code: int = 200):
        self.text = text
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")

    def json(self):
        if self._payload is None:
            raise ValueError("No JSON payload")
        return self._payload


@pytest.fixture
def nbk_xml() -> str:
    return """
    <rss>
      <channel>
        <item><title>USD</title><description>500.0</description></item>
        <item><title>EUR</title><description>590.5</description></item>
      </channel>
    </rss>
    """


@pytest.fixture
def rambler_currencies_html() -> str:
    return """
    <html>
      <body>
        <table>
          <tr><th>Код</th><th>Номинал</th><th>Валюта</th><th>Курс ЦБ</th><th>Изменения</th><th>%</th></tr>
          <tr><td>USD</td><td>1</td><td>Доллар США</td><td>74.2963</td><td>-0.3246</td><td>-0.44 %</td></tr>
          <tr><td>EUR</td><td>1</td><td>Евро</td><td>88.5490</td><td>+0.6593</td><td>+0.75 %</td></tr>
          <tr><td>KZT</td><td>100</td><td>Казахский тенге</td><td>16.0325</td><td>-0.0701</td><td>-0.44 %</td></tr>
        </table>
      </body>
    </html>
    """  # noqa: E501


def test_default_is_offline():
    svc = CurrencyService()
    assert svc.is_online is False
    assert svc.last_fetched_at is None


def test_init_with_online_true_sets_online_state():
    svc = CurrencyService(
        use_online=True,
        aggregator=StubAggregator(rates={"USD": 505.0}, provider_name="nbk"),
    )
    assert svc.is_online is True
    assert isinstance(svc.last_fetched_at, datetime)


def test_set_online_returns_false_when_unchanged():
    svc = CurrencyService()
    changed = svc.set_online(False)
    assert changed is False


def test_set_online_switches_mode():
    svc = CurrencyService(aggregator=StubAggregator(rates={"USD": 505.0}, provider_name="nbk"))
    changed = svc.set_online(True)
    assert changed is True
    assert svc.is_online is True


def test_set_online_can_switch_back_offline():
    svc = CurrencyService(aggregator=StubAggregator(rates={"USD": 505.0}, provider_name="nbk"))
    svc.set_online(True)
    changed = svc.set_online(False)
    assert changed is True
    assert svc.is_online is False


def test_last_fetched_at_updated_after_successful_fetch():
    svc = CurrencyService(aggregator=StubAggregator(rates={"USD": 505.0}, provider_name="nbk"))
    svc.set_online(True)
    assert isinstance(svc.last_fetched_at, datetime)


def test_last_fetched_at_is_none_when_offline():
    svc = CurrencyService()
    assert svc.last_fetched_at is None


def test_set_online_fetch_error_keeps_online_without_timestamp(tmp_path, monkeypatch):
    monkeypatch.setattr(CurrencyService, "CACHE_FILE", tmp_path / "currency_rates.json")
    svc = CurrencyService(aggregator=StubAggregator(error=RuntimeError("no network")))
    old_fetched = svc.last_fetched_at
    svc.set_online(True)
    assert svc.is_online is True
    assert svc.last_fetched_at == old_fetched


def test_refresh_rates_returns_false_when_offline():
    svc = CurrencyService()
    assert svc.refresh_rates() is False


def test_refresh_rates_updates_timestamp_when_online():
    svc = CurrencyService(aggregator=StubAggregator(rates={"USD": 505.0}, provider_name="nbk"))
    svc.set_online(True)
    old_fetched = svc.last_fetched_at
    assert old_fetched is not None
    svc._aggregator = StubAggregator(rates={"USD": 506.0}, provider_name="open_exchange")
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


def test_nbk_provider_parses_xml_correctly(monkeypatch, nbk_xml):
    monkeypatch.setattr(
        requests,
        "get",
        lambda *args, **kwargs: FakeResponse(text=nbk_xml),
    )

    provider = NBKProvider()
    assert provider.fetch() == {"USD": 500.0, "EUR": 590.5}


def test_cbr_provider_parses_rambler_html_correctly(monkeypatch, rambler_currencies_html):
    monkeypatch.setattr(
        requests,
        "get",
        lambda *args, **kwargs: FakeResponse(text=rambler_currencies_html),
    )

    provider = CBRProvider()
    assert provider.fetch() == {"USD": 74.2963, "EUR": 88.5490, "KZT": 0.160325}


def test_aggregator_falls_back_on_provider_error():
    aggregator = CurrencyAggregator(
        [
            DummyProvider("nbk", error=ProviderFetchError("nbk down")),
            StaticProvider(),
        ]
    )

    assert aggregator.fetch_rates() == {"USD": 500.0, "EUR": 590.0, "RUB": 6.5}
    assert aggregator.last_provider_name == "static"


def test_aggregator_uses_first_successful_provider():
    calls: list[str] = []
    aggregator = CurrencyAggregator(
        [
            DummyProvider("nbk", rates={"USD": 501.0}, calls=calls),
            DummyProvider("static", rates={"USD": 500.0}, calls=calls),
        ]
    )

    assert aggregator.fetch_rates() == {"USD": 501.0}
    assert calls == ["nbk"]
    assert aggregator.last_provider_name == "nbk"


def test_open_exchange_provider_raises_without_api_key():
    provider = OpenExchangeProvider(api_key="")
    with pytest.raises(ProviderFetchError, match="No API key configured"):
        provider.fetch()


def test_currency_service_accepts_injected_aggregator():
    svc = CurrencyService(
        use_online=True,
        aggregator=StubAggregator(rates={"USD": 507.0}, provider_name="nbk"),
    )
    assert svc.get_rate("USD") == 507.0
