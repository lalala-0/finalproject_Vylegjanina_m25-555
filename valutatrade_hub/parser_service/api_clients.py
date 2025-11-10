# valutatrade_hub/parser_service/api_clients.py

import requests
import time
from abc import ABC, abstractmethod
from typing import Dict
from valutatrade_hub.core.exceptions import ApiRequestError
from valutatrade_hub.parser_service.config import ParserConfig


class BaseApiClient(ABC):
    """Абстрактный клиент для получения курсов валют."""

    def __init__(self, config: ParserConfig | None = None):
        self.config = config or ParserConfig()

    @abstractmethod
    def fetch_rates(self) -> Dict[str, float]:
        """Получает словарь курсов валют в формате { 'BTC_USD': 59337.21 }."""
        pass

    @staticmethod
    def handle_http_error(response: requests.Response, source: str):
        status = response.status_code

        if status == 400:
            msg = "Некорректный запрос (ошибка 400)"
        elif status == 401:
            msg = "Ошибка аутентификации — неверный API ключ (401)"
        elif status == 403:
            msg = "Доступ запрещён — проверьте права или тариф API (403)"
        elif status == 404:
            msg = "Ресурс не найден (404)"
        elif status == 429:
            msg = "Превышен лимит запросов API (429)"
        elif status == 500:
            msg = "Внутренняя ошибка сервера API (500)"
        elif status == 503:
            msg = "API временно недоступен (503)"
        else:
            msg = f"Неожиданная ошибка API ({status})"

        raise ApiRequestError(f"{source} ответил ошибкой {status}: {msg}")


class CoinGeckoClient(BaseApiClient):
    """Клиент для получения криптовалютных курсов с CoinGecko."""

    def fetch_rates(self) -> Dict[str, float]:
        crypto_map = self.config.get("CRYPTO_ID_MAP")
        cryptos = self.config.get("CRYPTO_CURRENCIES")
        base = self.config.get("BASE_CURRENCY")
        url = self.config.get("COINGECKO_URL")
        timeout = self.config.get("REQUEST_TIMEOUT", 10)

        ids = ",".join(crypto_map[c] for c in cryptos)
        vs = base.lower()
        url = f"{url}?ids={ids}&vs_currencies={vs}"

        start = time.time()
        try:
            response = requests.get(url, timeout=timeout)
        except requests.exceptions.Timeout:
            raise ApiRequestError("CoinGecko: превышено время ожидания ответа")
        except requests.exceptions.ConnectionError:
            raise ApiRequestError("CoinGecko: ошибка соединения (проверьте интернет или URL)")
        except requests.exceptions.RequestException as e:
            raise ApiRequestError(f"CoinGecko: сбой при запросе: {e}")

        if not response.ok:
            self.handle_http_error(response, "CoinGecko")

        try:
            data = response.json()
        except ValueError:
            raise ApiRequestError("CoinGecko: некорректный JSON-ответ")
        
        rates = {}
        for symbol, coin_id in crypto_map.items():
            try:
                rate = data[coin_id][vs]
                pair_key = f"{symbol}_{base}"
                rates[pair_key] = rate
            except KeyError:
                continue

        elapsed = round((time.time() - start) * 1000, 2)
        print(f"[CoinGecko] Получено {len(rates)} курсов за {elapsed} мс")
        return rates


class ExchangeRateApiClient(BaseApiClient):
    """Клиент для получения фиатных курсов с ExchangeRate-API."""

    def fetch_rates(self) -> Dict[str, float]:
        api_key = self.config.get("EXCHANGERATE_API_KEY")
        if not api_key:
            raise ApiRequestError("Отсутствует ключ EXCHANGERATE_API_KEY")

        base = self.config.get("BASE_CURRENCY")
        fiat_currencies = self.config.get("FIAT_CURRENCIES")
        base_url = self.config.get("EXCHANGERATE_API_URL")
        timeout = self.config.get("REQUEST_TIMEOUT", 10)

        url = f"{base_url}/{api_key}/latest/{base}"

        start = time.time()
        try:
            response = requests.get(url, timeout=timeout)
        except requests.exceptions.Timeout:
            raise ApiRequestError("ExchangeRate-API: превышено время ожидания ответа")
        except requests.exceptions.ConnectionError:
            raise ApiRequestError("ExchangeRate-API: ошибка соединения (проверьте интернет или URL)")
        except requests.exceptions.RequestException as e:
            raise ApiRequestError(f"ExchangeRate-API: сбой при запросе: {e}")

        if not response.ok:
            self.handle_http_error(response, "ExchangeRate-API")

        try:
            data = response.json()
        except requests.exceptions.RequestException as e:
            raise ApiRequestError(f"Ошибка запроса к ExchangeRate-API: {e}")

        if data.get("result") != "success":
            raise ApiRequestError(
                f"ExchangeRate-API вернул ошибку: {data.get('error-type', 'unknown')}"
            )

        rates = {}
        for code in fiat_currencies:
            if code in data.get("rates", {}):
                pair_key = f"{code}_{base}"
                rates[pair_key] = data["rates"][code]

        elapsed = round((time.time() - start) * 1000, 2)
        print(f"[ExchangeRate-API] Получено {len(rates)} курсов за {elapsed} мс")
        return rates
