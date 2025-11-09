import json
import os
from datetime import datetime
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

def get_exchange_rate(from_currency: str, to_currency: str) -> tuple[float, datetime]:
    """
    Возвращает курс конверсии между двумя валютами из rates.json.
    Если курса нет — вызывает исключение.
    Возвращает (rate, updated_at).
    """
    if from_currency == to_currency:
        return 1.0, datetime.now()
    rates_data = load_json(SettingsLoader().get("RATES_FILE"))
    if not rates_data:
        raise ValueError("Файл с курсами пуст или не найден")

    from_currency = from_currency.upper()
    to_currency = to_currency.upper()

    key = f"{from_currency}_{to_currency}"
    reverse_key = f"{to_currency}_{from_currency}"

    if key in rates_data:
        entry = rates_data[key]
        return entry["rate"], datetime.fromisoformat(entry["updated_at"])

    if reverse_key in rates_data:
        entry = rates_data[reverse_key]
        reverse_rate = 1 / entry["rate"]
        return reverse_rate, datetime.fromisoformat(entry["updated_at"])

    raise ValueError(f"Курс {from_currency}→{to_currency} не найден")

