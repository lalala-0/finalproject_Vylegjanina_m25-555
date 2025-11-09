import json
from pathlib import Path
from typing import Any

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
        return self._data.get(key, default)

    def reload(self):
        """Перезагрузка конфигурации с диска."""
        if not self._config_path.exists():
            raise FileNotFoundError(f"Файл конфигурации {self._config_path} не найден")
        with self._config_path.open("r", encoding="utf-8") as f:
            self._data = json.load(f)
