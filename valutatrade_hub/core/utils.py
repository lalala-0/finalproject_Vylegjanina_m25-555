from datetime import datetime, timezone
from venv import logger

from valutatrade_hub.core.exceptions import ApiRequestError, CurrencyNotFoundError, RateNotFoundError
from valutatrade_hub.infra.database import DatabaseManager
from valutatrade_hub.infra.settings import SettingsLoader
from valutatrade_hub.parser_service.api_clients import (
    CoinGeckoClient,
    ExchangeRateApiClient,
)
from valutatrade_hub.parser_service.config import ParserConfig
from valutatrade_hub.parser_service.storage import RatesStorage
from valutatrade_hub.parser_service.updater import RatesUpdater

def load_json(path: str):
    """Загрузка данных из json"""
    try:
        return DatabaseManager().load(path)
    except FileNotFoundError:
        return []


def save_json(path: str, data):
    """Сохранение данных в json"""
    DatabaseManager().save(path, data)


def next_id(records: list) -> int:
    """Вычисление нового id пользователя"""
    if not records:
        return 1
    return max(u["user_id"] for u in records) + 1


def find_rate(rates: dict, a: str, b: str):
    """Пробует найти курс в прямом или обратном направлении."""
    if (key := f"{a}_{b}") in rates:
        return rates[key]["rate"], datetime.fromisoformat(rates[key]["updated_at"])
    if (rev := f"{b}_{a}") in rates:
        return 1 / rates[rev]["rate"], datetime.fromisoformat(rates[rev]["updated_at"])
    raise RateNotFoundError(f"{a}→{b}")

def update_rates(source: str | None = None):
    """Вызывает обновление курсов через RatesUpdater."""
    try:
        config = ParserConfig()
        if source == "coingecko":
            clients = [CoinGeckoClient(config)]
        elif source == "exchangerate":
            clients = [ExchangeRateApiClient(config)]
        else:
            clients = [CoinGeckoClient(config), ExchangeRateApiClient(config)]
        storage = RatesStorage()
        updater = RatesUpdater(clients, storage)
        updated_cnt = updater.run_update()
    except ApiRequestError:
        raise
    except Exception as e:
        raise ApiRequestError(f"Не удалось обновить курсы: {e}")
    if updated_cnt == 0:
        raise ApiRequestError("Не удалось получить ни одного курса от всех клиентов.")

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
        logger.warning("Файл с курсами пуст или повреждён. " \
                        "Выполняется первичное обновление.")
        update_rates()
        rates = storage.load_rates()

    try:
        rate, updated_at = find_rate(rates, from_currency, to_currency)
    except RateNotFoundError:
        logger.info(f"Курс {from_currency}→{to_currency} не найден, обновление данных.")
        update_rates()
        rates = storage.load_rates()
        rate, updated_at = find_rate(rates, from_currency, to_currency)

    ttl = SettingsLoader().get("RATES_TTL_SECONDS", 3600)
    if (datetime.now(timezone.utc) - updated_at).total_seconds() > ttl:
        logger.info("Истёк TTL курсов - выполняется обновление...")
        update_rates()
        rates = storage.load_rates()
        rate, updated_at = find_rate(rates, from_currency, to_currency)
    return rate, updated_at

