
class InsufficientFundsError(Exception):
    """Выбрасывается, если на кошельке недостаточно средств для операции."""

    def __init__(self, available: float, required: float, code: str):
        self.available = available
        self.required = required
        self.code = code
        message = f"Недостаточно средств: "\
            f"доступно {available} {code}, требуется {required} {code}"
        super().__init__(message)


class CurrencyNotFoundError(Exception):
    """Выбрасывается, если валюта не найдена в реестре валют."""

    def __init__(self, code: str):
        self.code = code
        message = f"Неизвестная валюта '{code}'"
        super().__init__(message)


class ApiRequestError(Exception):
    """Выбрасывается при сбое внешнего API (например, получение курсов валют)."""

    def __init__(self, reason: str):
        self.reason = reason
        message = f"Ошибка при обращении к внешнему API: {reason}"
        super().__init__(message)
