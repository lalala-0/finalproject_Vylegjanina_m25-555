from datetime import datetime, timezone
from typing import List
from valutatrade_hub.core.exceptions import ApiRequestError
from valutatrade_hub.parser_service.api_clients import BaseApiClient
from valutatrade_hub.parser_service.storage import RatesStorage
from valutatrade_hub.logging_config import logger

class RatesUpdater:
    """
    Координирует процесс обновления курсов валют.
    Получает данные от клиентов, объединяет их и сохраняет в storage.
    """

    def __init__(self, clients: List[BaseApiClient], storage: RatesStorage):
        self.clients = clients
        self.storage = storage

    def run_update(self):
        """Запускает процесс обновления курсов."""
        updated_rates = {}
        now = datetime.now(timezone.utc)
        now_iso = now.isoformat(timespec="seconds")

        for client in self.clients:
            client_name = client.__class__.__name__
            try:
                rates = client.fetch_rates()
                for pair, rate in rates.items():
                    updated_rates[pair] = {
                        "rate": rate,
                        "updated_at": now_iso
                    }
            except ApiRequestError as e:
                logger.error(f"[{client_name}] Ошибка обновления курсов: {e}")
                continue
            except Exception as e:
                logger.exception(f"[{client_name}] Неожиданная ошибка: {e}")
                continue

        if not updated_rates:
            logger.warning("Не удалось получить ни одного курса от всех клиентов.")
            return

        updated_rates["source"] = "ParserService"
        updated_rates["last_refresh"] = now_iso

        self.storage.save_rates(updated_rates)
        logger.info(f"Обновление завершено: {len(self.clients)} клиентов опрошены, "
                    f"{len(updated_rates) - 2} пар курсов сохранено")
