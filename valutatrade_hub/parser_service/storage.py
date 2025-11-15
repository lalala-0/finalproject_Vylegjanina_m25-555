from datetime import datetime, timezone
from pathlib import Path
from typing import Dict

from valutatrade_hub.infra.database import DatabaseManager
from valutatrade_hub.infra.settings import SettingsLoader

settings = SettingsLoader()

class RatesStorage:
    """Хранилище для курсов валют."""

    def __init__(self):
        self.rates_file = Path(settings.get("RATES_FILE",
                                            "data/rates.json"))
        self.history_file = Path(settings.get("HISTORY_FILE",
                                              "data/exchange_rates.json"))
        self.rates_file.parent.mkdir(parents=True, exist_ok=True)

    def load_rates(self) -> Dict:
        """Загрузить актуальные курсы (rates.json)."""
        if not self.rates_file.exists():
            return {}
        return DatabaseManager().load(self.rates_file)

    def save_rates(self, rates: Dict):
        """
        Сохранить актуальные курсы (rates.json)
        и добавить в историю (exchange_rates.json).
        """
        DatabaseManager().save(self.rates_file, rates)

        try:
            history = DatabaseManager().load(self.history_file)
        except FileNotFoundError:
            history = []

        now_iso = datetime.now(timezone.utc).isoformat()
        for pair, data in rates.items():
            if pair in ("source", "last_refresh"):
                continue
            entry = {
                "id": f"{pair}_{now_iso}",
                "from_currency": pair.split("_")[0],
                "to_currency": pair.split("_")[1],
                "rate": data["rate"],
                "timestamp": data["updated_at"],
                "source": rates.get("source", "ParserService"),
            }
            history.append(entry)

        DatabaseManager().save(self.history_file, history)
