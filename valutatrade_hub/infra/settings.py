import json
from pathlib import Path
from typing import Any

from valutatrade_hub.infra.database import DatabaseManager


class SettingsLoader:
    _instance = None
    # Реализовано через __new__ — проще и читаемее, чем метакласс.
    # в проекте только один Singleton без наследников, поэтому метакласс избыточен.

    def __new__(cls, config_path: str = "config.json"):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, config_path: str = "config.json"):
        if self._initialized:
            return
        self._config_path = Path(config_path)
        self._data = {}
        self.reload()
        self._initialized = True

    def get(self, key: str, default: Any = None) -> Any:
        """
        Возвращает значение конфигурации по ключу.
        Если ключ не найден, возвращает default.
        Пример: settings.get("RATES_FILE") -> 'data/rates.json'
        """
        return self._data.get(key, default)

    def reload(self):
        """Перезагрузка конфигурации с диска."""
        if not self._config_path.exists():
            raise FileNotFoundError(f"Файл конфигурации {self._config_path} не найден")
        self._data = DatabaseManager().load(self._config_path)
