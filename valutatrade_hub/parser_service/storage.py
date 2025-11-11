import json
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict
from valutatrade_hub.infra.settings import SettingsLoader

settings = SettingsLoader()

class RatesStorage:
    """Хранилище для курсов валют."""

    def __init__(self):
        self.rates_file = Path(settings.get("RATES_FILE", "data/rates.json"))
        self.history_file = Path(settings.get("HISTORY_FILE", "data/exchange_rates.json"))
        self.rates_file.parent.mkdir(parents=True, exist_ok=True)

    def load_rates(self) -> Dict:
        """Загрузить актуальные курсы (rates.json)."""
        if not self.rates_file.exists():
            return {}
        with self.rates_file.open("r", encoding="utf-8") as f:
            return json.load(f)

    def save_rates(self, rates: Dict):
        """Сохранить актуальные курсы (rates.json) и добавить в историю (exchange_rates.json)."""
        with self.rates_file.open("w", encoding="utf-8") as f:
            json.dump(rates, f, ensure_ascii=False, indent=2)

        history = []
        if self.history_file.exists():
            with self.history_file.open("r", encoding="utf-8") as f:
                try:
                    history = json.load(f)
                except json.JSONDecodeError:
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

        with self.history_file.open("w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
