import json
import os
from pathlib import Path
from typing import Any



class ParserConfig:
    _instance = None

    # Значения по умолчанию
    DEFAULTS = {
        "EXCHANGERATE_API_KEY": "",
        "COINGECKO_URL": "https://api.coingecko.com/api/v3/simple/price",
        "EXCHANGERATE_API_URL": "https://v6.exchangerate-api.com/v6",
        "BASE_CURRENCY": "USD",
        "FIAT_CURRENCIES": ["EUR", "GBP", "RUB"],
        "CRYPTO_CURRENCIES": ["BTC", "ETH", "SOL"],
        "CRYPTO_ID_MAP": {
            "BTC": "bitcoin",
            "ETH": "ethereum",
            "SOL": "solana",
        },
        "RATES_FILE_PATH": "data/rates.json",
        "HISTORY_FILE_PATH": "data/exchange_rates.json",
        "REQUEST_TIMEOUT": 10,
    }

    def __new__(cls, config_path: str = "parser_config.json"):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, config_path: str = "parser_config.json"):
        if self._initialized:
            return
        self._config_path = Path(config_path)
        self._data = {}
        self.reload()
        self._initialized = True

    def get(self, key: str, default: Any = None) -> Any:
        """
        Возвращает значение конфигурации по ключу.
        Если ключ не найден, возвращает default или значение по умолчанию.
        Для EXCHANGERATE_API_KEY - берётся из переменной окружения, если есть.
        """
        if key == "EXCHANGERATE_API_KEY":
            env_value = os.getenv("EXCHANGERATE_API_KEY")
            if env_value is not None:
                return env_value
        return self._data.get(key, self.DEFAULTS.get(key, default))

    def reload(self):
        """Перезагрузка конфигурации с диска. Если файла нет — создаём с дефолтами."""
        if not self._config_path.exists():
            print(f"Конфиг {self._config_path} не найден, создаю с настройками парсера по умолчанию.")
            self._data = self.DEFAULTS.copy()
            self._config_path.parent.mkdir(parents=True, exist_ok=True)
            with self._config_path.open("w", encoding="utf-8") as f:
                json.dump(self._data, f, indent=2, ensure_ascii=False)
            return

        with self._config_path.open("r", encoding="utf-8") as f:
            try:
                self._data = json.load(f)
            except json.JSONDecodeError:
                print(f"Ошибка чтения {self._config_path}, восстановлены значения по умолчанию.")
                self._data = self.DEFAULTS.copy()

        # Если в конфиге чего-то нет — дополним из DEFAULTS
        updated = False
        for key, value in self.DEFAULTS.items():
            if key not in self._data:
                self._data[key] = value
                updated = True

        if updated:
            # Автоматически дописываем недостающие поля в файл
            with self._config_path.open("w", encoding="utf-8") as f:
                json.dump(self._data, f, indent=2, ensure_ascii=False)

    def as_dict(self) -> dict:
        """Возвращает полную конфигурацию в виде словаря."""
        return self._data.copy()
