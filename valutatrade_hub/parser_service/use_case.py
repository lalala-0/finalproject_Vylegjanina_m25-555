from datetime import datetime, timezone
from valutatrade_hub.core.exceptions import ApiRequestError, CurrencyNotFoundError
from valutatrade_hub.infra.settings import SettingsLoader
from valutatrade_hub.parser_service.api_clients import CoinGeckoClient, ExchangeRateApiClient
from valutatrade_hub.parser_service.config import ParserConfig
from valutatrade_hub.parser_service.storage import RatesStorage
from valutatrade_hub.parser_service.updater import RatesUpdater
from valutatrade_hub.logging_config import logger


def _update_rates():
    """Вызывает обновление курсов через RatesUpdater."""
    try:
        config = ParserConfig()
        clients = [CoinGeckoClient(config), ExchangeRateApiClient(config)]
        storage = RatesStorage()
        updater = RatesUpdater(clients, storage)
        updater.run_update()
    except Exception as e:
        raise ApiRequestError(f"Не удалось обновить курсы: {e}")

def _find_rate(rates: dict, a: str, b: str):
    """Пробует найти курс в прямом или обратном направлении."""
    if (key := f"{a}_{b}") in rates:
        return rates[key]["rate"], datetime.fromisoformat(rates[key]["updated_at"])
    if (rev := f"{b}_{a}") in rates:
        return 1 / rates[rev]["rate"], datetime.fromisoformat(rates[rev]["updated_at"])
    raise CurrencyNotFoundError(f"Курс {a}→{b} не найден")

def get_exchange_rate(from_currency: str, to_currency: str) -> tuple[float, datetime]:
    """
    Возвращает курс между валютами из rates.json.
    При истечении TTL - обновляет кеш.
    """

    from_currency, to_currency = from_currency.upper(), to_currency.upper()
    if from_currency == to_currency:
        return 1.0, datetime.now()

    storage = RatesStorage()
    rates = storage.load_rates()
    if not rates or "last_refresh" not in rates:
        logger.warning("Файл с курсами пуст или повреждён - выполняется первичное обновление.")
        _update_rates()
        rates = storage.load_rates()

    try:
        rate, updated_at = _find_rate(rates, from_currency, to_currency)
    except CurrencyNotFoundError:
        logger.info(f"Курс {from_currency}→{to_currency} не найден, обновляем данные...")
        _update_rates()
        rates = storage.load_rates()
        rate, updated_at = _find_rate(rates, from_currency, to_currency)

    ttl = SettingsLoader().get("RATES_TTL_SECONDS", 3600)
    if (datetime.now(timezone.utc) - updated_at).total_seconds() > ttl:
        logger.info("Истёк TTL курсов - выполняется обновление...")
        _update_rates()
        rates = storage.load_rates()
        rate, updated_at = _find_rate(rates, from_currency, to_currency)
    return rate, updated_at