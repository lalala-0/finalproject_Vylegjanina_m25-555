import json
import os
from datetime import datetime
from valutatrade_hub.core.exceptions import ApiRequestError, CurrencyNotFoundError
from valutatrade_hub.infra.settings import SettingsLoader


def load_json(path: str):
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def save_json(path: str, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def next_id(records: list) -> int:
    if not records:
        return 1
    return max(u["user_id"] for u in records) + 1


def update_rates():
    pass

def get_exchange_rate(from_currency: str, to_currency: str) -> tuple[float, datetime]:
    """Возвращает курс между валютами из rates.json.
    При истечении TTL — обновляет кеш, иначе выбрасывает ApiRequestError."""

    from_currency, to_currency = from_currency.upper(), to_currency.upper()
    if from_currency == to_currency:
        return 1.0, datetime.now()

    def _find_rate(rates: dict, a: str, b: str):
        """Пробует найти курс в прямом или обратном направлении."""
        if (key := f"{a}_{b}") in rates:
            return rates[key]["rate"], datetime.fromisoformat(rates[key]["updated_at"])
        if (rev := f"{b}_{a}") in rates:
            return 1 / rates[rev]["rate"], datetime.fromisoformat(rates[rev]["updated_at"])
        raise CurrencyNotFoundError(f"Курс {a}→{b} не найден")

    rates_path = SettingsLoader().get("RATES_FILE")
    ttl = SettingsLoader().get("RATES_TTL_SECONDS", 3600)

    rates = load_json(rates_path)
    if not rates:
        raise ApiRequestError("Файл с курсами пуст или не найден")

    try:
        rate, updated_at = _find_rate(rates, from_currency, to_currency)
    except CurrencyNotFoundError:
        raise

    if (datetime.now() - updated_at).total_seconds() <= ttl:
        return rate, updated_at

    try:
        update_rates()
        rates = load_json(rates_path)
        rate, updated_at = _find_rate(rates, from_currency, to_currency)
    except Exception as e:
        raise ApiRequestError(f"Не удалось обновить курсы: {e}")

    return rate, updated_at