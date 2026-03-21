import json
import logging
import threading
from datetime import datetime
from pathlib import Path

from domain.currency import CurrencyService as DomainCurrencyService

logger = logging.getLogger(__name__)


class CurrencyService:
    """Адаптер сервиса валют для приложения.

    По умолчанию использует локальные дефолтные курсы (совместимо с тестами).
    Если требуется — можно разрешить попытку получить актуальные курсы с
    https://www.nationalbank.kz/rss/rates_all.xml
    установив `use_online=True` при создании. В этом случае курсы кэшируются
    в `project/currency_rates.json` и будут использованы при отсутствии сети.
    """

    CACHE_FILE = Path(__file__).resolve().parents[1] / "currency_rates.json"

    def __init__(
        self,
        rates: dict[str, float] | None = None,
        base: str = "KZT",
        use_online: bool = False,  # connect to online source if no rates provided
    ):
        self._use_online = bool(use_online)
        self._online_lock = threading.Lock()
        self._last_fetched_at: datetime | None = None

        # If explicit rates provided, use them.
        if rates is not None:
            self._service = DomainCurrencyService(rates=rates, base=base)
            return

        # If online fetching requested, try to fetch and cache; else fall back to defaults.
        if use_online:
            parsed = self._fetch_online_rates()
            if parsed:
                self._service = DomainCurrencyService(rates=parsed, base=base)
                self._last_fetched_at = datetime.now()
                return
            logger.info("Falling back to default currency rates after online fetch")

        # Default static rates (keeps existing test expectations)
        defaults = {"USD": 500.0, "EUR": 590.0, "RUB": 6.5}
        self._service = DomainCurrencyService(rates=defaults, base=base)

    def convert(self, amount: float, currency: str) -> float:
        try:
            return self._service.convert(amount, currency)
        except KeyError as err:
            raise ValueError(f"Unsupported currency: {currency}") from err

    def get_rate(self, currency: str) -> float:
        code = (currency or "").upper()
        if not code:
            raise ValueError("Currency is required")
        try:
            return float(self._service.get_rate(code))
        except KeyError as err:
            raise ValueError(f"Unsupported currency: {currency}") from err

    @property
    def base_currency(self) -> str:
        return self._service.base_currency

    def get_all_rates(self) -> dict[str, float]:
        return self._service.get_all_rates()

    @property
    def is_online(self) -> bool:
        """Current online mode state."""
        return bool(self._use_online)

    @property
    def last_fetched_at(self) -> datetime | None:
        """Datetime of the last successful rate fetch, or None."""
        return self._last_fetched_at

    def set_online(self, enabled: bool) -> bool:
        """
        Switch online mode at runtime without restarting the application.

        Returns True if the mode was actually changed.
        """
        enabled = bool(enabled)
        with self._online_lock:
            if enabled == bool(self._use_online):
                return False

            self._use_online = enabled
            if enabled:
                try:
                    if self._fetch_online_rates():
                        self._last_fetched_at = datetime.now()
                except Exception:
                    logger.warning(
                        "CurrencyService: failed to fetch rates on mode switch",
                        exc_info=True,
                    )
            else:
                self._load_offline_rates()
        return True

    def refresh_rates(self) -> bool:
        """Manually refresh rates if online mode is active."""
        if not self._use_online:
            return False
        with self._online_lock:
            try:
                if not self._fetch_online_rates():
                    return False
                self._last_fetched_at = datetime.now()
                return True
            except Exception:
                logger.warning("CurrencyService: manual rate refresh failed", exc_info=True)
                return False

    def _load_offline_rates(self) -> None:
        cached = self._load_cached()
        if cached:
            self._service = DomainCurrencyService(rates=cached, base=self.base_currency)
            return
        defaults = {"USD": 500.0, "EUR": 590.0, "RUB": 6.5}
        self._service = DomainCurrencyService(rates=defaults, base=self.base_currency)

    def _fetch_online_rates(self) -> dict[str, float] | None:
        """Попытаться получить курсы с RSS-фида НБРК и сохранить в кеш.

        Возвращает словарь rates или None при ошибке.
        """
        url = "https://www.nationalbank.kz/rss/rates_all.xml"
        try:
            import xml.etree.ElementTree as ET

            import requests
        except ImportError as e:
            logger.warning("Missing dependencies for online fetching: %s", e)
            return self._load_cached()

        try:
            resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
            resp.raise_for_status()
            root = ET.fromstring(resp.text)
        except requests.RequestException as e:
            logger.warning("Network error fetching rates: %s", e)
            logger.info("Falling back to cached currency rates")
            return self._load_cached()
        except ET.ParseError as e:
            logger.warning("XML parsing error: %s", e)
            logger.info("Falling back to cached currency rates")
            return self._load_cached()
        except Exception as e:
            logger.exception("Unexpected error fetching rates: %s", e)
            logger.info("Falling back to cached currency rates")
            return self._load_cached()

        rates: dict[str, float] = {}

        # Parse RSS items
        for item in root.findall(".//item"):
            title = item.find("title")
            description = item.find("description")
            if title is not None and description is not None and title.text and description.text:
                code = title.text.strip()
                rate_text = description.text.strip()
                try:
                    rate = float(rate_text.replace(",", "."))
                    rates[code] = rate
                except ValueError as e:
                    logger.warning("Invalid rate value for %s: %s (%s)", code, rate_text, e)
                    continue

        if rates:
            try:
                self._save_cache(rates)
            except Exception as e:
                logger.warning("Failed to save cache: %s", e)
            self._service = DomainCurrencyService(rates=rates, base=self.base_currency)
            return rates
        else:
            logger.warning("No valid rates found in XML")
            logger.info("Falling back to cached currency rates")
            cached = self._load_cached()
            if cached:
                self._service = DomainCurrencyService(rates=cached, base=self.base_currency)
            return cached

    def _load_cached(self) -> dict[str, float] | None:
        try:
            if self.CACHE_FILE.exists():
                with open(self.CACHE_FILE, encoding="utf-8") as f:
                    data = json.load(f)
                    # Expect mapping code->rate
                    return {k: float(v) for k, v in data.items()}
        except Exception as e:
            logger.exception("Failed to load cached currency rates: %s", e)
            return None
        logger.info("Currency rate cache not found, fallback to defaults")
        return None

    def _save_cache(self, rates: dict[str, float]) -> None:
        try:
            with open(self.CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(rates, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.exception("Failed to save currency cache: %s", e)
