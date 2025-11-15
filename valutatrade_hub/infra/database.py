import os
import json
from threading import Lock


class DatabaseManager:
    """Простой Singleton над JSON-файлами."""

    _instance = None
    _lock = Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
        return cls._instance

    def load(self, path: str):
        """Загрузка данных из json."""
        if not os.path.exists(path):
            raise FileNotFoundError
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def save(self, path: str, data):
        """Сохранение данных в json."""
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
