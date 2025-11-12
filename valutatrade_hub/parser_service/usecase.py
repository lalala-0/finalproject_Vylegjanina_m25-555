from datetime import datetime, timezone
from prettytable import PrettyTable
from valutatrade_hub.core.currancies import get_currency
from valutatrade_hub.core.exceptions import ApiRequestError, CurrencyNotFoundError
from valutatrade_hub.infra.settings import SettingsLoader
from valutatrade_hub.parser_service.api_clients import CoinGeckoClient, ExchangeRateApiClient
from valutatrade_hub.parser_service.config import ParserConfig
from valutatrade_hub.parser_service.storage import RatesStorage
from valutatrade_hub.parser_service.updater import RatesUpdater
from valutatrade_hub.logging_config import logger



def _update_rates(source: str | None = None):
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
        updater.run_update()
    except Exception as e:
        raise ApiRequestError(f"Не удалось обновить курсы: {e}")

def update_rates(source: str| None = None) -> str:
    """
    Обновляет курсы валют через RatesUpdater, логирует процесс и выводит краткий отчёт.
    source: 'coingecko', 'exchangerate' или None (все источники)
    """
    try:
        print("INFO: Старт обновления курсов...")
        logger.info("Старт обновления курсов...")

        _update_rates(source)

        storage = RatesStorage()
        rates = storage.load_rates()
        last_refresh = rates.get("last_refresh", "unknown")
        total_updated = len([k for k in rates if k not in ("source", "last_refresh")])

        logger.info(f"Обновление курсов успешно. Всего обновлено: {total_updated}. Время последнего обновления: {last_refresh.replace('T', ' ').split('+')[0]}")
        return f"INFO: Обновление курсов успешно. Всего обновлено: {total_updated}. Время последнего обновления: {last_refresh.replace('T', ' ').split('+')[0]}"

    except ApiRequestError as e:
        msg = f"Обновление курсов не удалось: {e}"
        logger.error(msg)
        return f"ERROR: Обновление курсов не удалось: {msg}"

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


def show_rates(currency: str = None, top: int = None) -> str:
    """
    Показать список актуальных курсов из локального кэша, упорядоченный по алфавиту.
    Опционально фильтрует по валюте (--currency),
    показывает N самых дорогих и упорядочивает по стоимости (--top).
    """
    try:
        if currency is not None:
            currency = currency.upper()
            get_currency(currency)
    except CurrencyNotFoundError as e:
        logger.error(e)
        return f"ERROR: {e}"
    if top < 0:
        logger.error("Параметр 'top' должен быть положительным числом")
        return f"ERROR: Параметр 'top' должен быть положительным числом"
    
    base =  ParserConfig().get("BASE_CURRENCY", "USD")
    
    storage = RatesStorage()
    rates = storage.load_rates()
    if not rates or "last_refresh" not in rates:
        msg = "Локальный кеш курсов пуст. Выполните 'update-rates', чтобы загрузить данные."
        logger.warning(msg)
        return f"WARNING: {msg}"

    last_refresh = rates.get("last_refresh")
    filtered = []

    for pair, info in rates.items():
        if pair in ("source", "last_refresh"):
            continue

        from_curr, to_curr = pair.split("_")
        if currency and from_curr != currency:
            continue

        rate = info["rate"]
        if base != to_curr:
            try:
                if (key := f"{to_curr}_{base}") in rates:
                    base_rate = rates[key]["rate"], datetime.fromisoformat(rates[key]["updated_at"])
                if (rev := f"{base}_{to_curr}") in rates:
                    base_rate = 1 / rates[rev]["rate"], datetime.fromisoformat(rates[rev]["updated_at"])
                rate /= base_rate
                to_curr = base
            except Exception:
                continue

        filtered.append((f"{from_curr}_{to_curr}", rate, info["updated_at"]))

    if not filtered:
        msg = f"Курс для '{currency}' не найден в кеше." if currency else "Нет доступных курсов."
        logger.info(msg)
        return f"INFO: {msg}"

    if top:
        filtered.sort(key=lambda x: x[1], reverse=True)
        filtered = filtered[:int(top)]
    else:
        filtered.sort(key=lambda x: x[0])

    table = PrettyTable()
    table.field_names = ["Валютная пара", "Курс", "Обновлено"]
    table.align["Курс"] = "r"

    for pair, rate, updated_at in filtered:
        table.add_row([pair, f"{rate:.6f}", updated_at.replace('T', ' ').split('+')[0]])

    table_str = f"Курсы из кэша (обновлены {last_refresh.replace('T', ' ').split('+')[0]}):\n{table}"
    return table_str

