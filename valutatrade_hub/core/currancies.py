# currencies.py
from abc import ABC, abstractmethod
from typing import Dict


class CurrencyNotFoundError(Exception):
    """Выбрасывается, если код валюты не найден в реестре."""
    pass


class Currency(ABC):
    """Абстрактный базовый класс для валют."""
    def __init__(self, name: str, code: str):
        if not name.strip():
            raise ValueError("name не может быть пустым")
        if not code.isupper() or not (2 <= len(code) <= 5) or " " in code:
            raise ValueError("code должен быть в верхнем регистре (2-5 символов, без пробелов)")

        self.name = name
        self.code = code

    @abstractmethod
    def get_display_info(self) -> str:
        """Возвращает строковое представление валюты для UI/логов."""
        pass


class FiatCurrency(Currency):
    """Фиатная валюта (эмитент - государство или валютная зона)."""
    def __init__(self, name: str, code: str, issuing_country: str):
        super().__init__(name, code)
        if not issuing_country.strip():
            raise ValueError("issuing_country не может быть пустым")
        self.issuing_country = issuing_country

    def get_display_info(self) -> str:
        return f"[FIAT] {self.code} — {self.name} (Issuing: {self.issuing_country})"


class CryptoCurrency(Currency):
    """Криптовалюта (доп. сведения: алгоритм и капитализация)."""
    def __init__(self, name: str, code: str, algorithm: str, market_cap: float):
        super().__init__(name, code)
        if not algorithm.strip():
            raise ValueError("algorithm не может быть пустым")
        if market_cap < 0:
            raise ValueError("market_cap должен быть неотрицательным")
        self.algorithm = algorithm
        self.market_cap = market_cap

    def get_display_info(self) -> str:
        return f"[CRYPTO] {self.code} — {self.name} (Algo: {self.algorithm}, MCAP: {self.market_cap:.2e})"



_CURRENCY_REGISTRY: Dict[str, Currency] = {
    "USD": FiatCurrency("US Dollar", "USD", "United States"),
    "EUR": FiatCurrency("Euro", "EUR", "Eurozone"),
    "RUB": FiatCurrency("Russian Ruble", "RUB", "Russia"),
    "BTC": CryptoCurrency("Bitcoin", "BTC", "SHA-256", 1.12e12),
    "ETH": CryptoCurrency("Ethereum", "ETH", "Ethash", 3.9e11),
}


def get_currency(code: str) -> Currency:
    """Возвращает объект Currency по коду, если он известен."""
    code = code.upper()
    if code not in _CURRENCY_REGISTRY:
        raise CurrencyNotFoundError(f"Неизвестная валюта: '{code}'")
    return _CURRENCY_REGISTRY[code]

