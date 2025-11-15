import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from valutatrade_hub.infra.settings import SettingsLoader


class LoggerSingleton:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        settings = SettingsLoader()

        log_dir = Path(settings.get("LOG_DIR", "logs"))
        log_dir.mkdir(parents=True, exist_ok=True)

        log_file = log_dir / settings.get("LOG_FILE", "actions.log")
        max_bytes = settings.get("LOG_MAX_BYTES", 1_000_000)
        backup_count = settings.get("LOG_BACKUP_COUNT", 3)

        handler = RotatingFileHandler(
            log_file,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8"
        )

        formatter = logging.Formatter(
            fmt="%(levelname)s %(asctime)s %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S"
        )
        handler.setFormatter(formatter)

        level_name = settings.get("LOG_LEVEL", "INFO").upper()
        level = getattr(logging, level_name, logging.INFO)

        self.logger = logging.getLogger("valutatrade.actions")
        self.logger.setLevel(level)
        self.logger.addHandler(handler)
        self.logger.propagate = False

        self._initialized = True

logger = LoggerSingleton().logger
