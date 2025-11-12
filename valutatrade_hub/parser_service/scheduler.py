import time
from valutatrade_hub.parser_service.updater import RatesUpdater
from valutatrade_hub.parser_service.api_clients import CoinGeckoClient, ExchangeRateApiClient
from valutatrade_hub.parser_service.storage import RatesStorage
from valutatrade_hub.parser_service.config import ParserConfig
from valutatrade_hub.infra.logger import logger 

class UpdateScheduler:
    """Периодический запуск обновления курсов."""

    _instance = None

    def __new__(cls, interval_sec: int = 3600):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, interval_sec: int = 3600):
        if getattr(self, "_initialized", False):
            return
        self.interval = interval_sec
        self.storage = RatesStorage()
        self.config = ParserConfig()
        self.clients = [
            CoinGeckoClient(self.config),
            ExchangeRateApiClient(self.config)
        ]
        self.updater = RatesUpdater(self.clients, self.storage)
        self._initialized = True

    def start(self):
        """Запускает периодическое обновление курсов."""
        logger.info(f"Запуск периодического обновления каждые {self.interval} секунд")
        while True:
            try:
                self.updater.run_update()
            except Exception as e:
                logger.exception(f"Ошибка при периодическом обновлении курсов: {e}")
            time.sleep(self.interval)

