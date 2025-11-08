import hashlib
from datetime import datetime
from copy import deepcopy
from .utils import get_exchange_rate

class User:
    def __init__(self, user_id: int, username: str, password: str, salt: str = None, registration_date: datetime = None):
        if len(password) < 4:
            raise ValueError("Пароль должен быть не короче 4 символов")

        self._user_id = user_id
        self._username = username
        self._salt = salt or self._generate_salt()
        self._hashed_password = self._hash_password(password)
        self._registration_date = registration_date or datetime.now()

    @property
    def user_id(self):
        return self._user_id

    @property
    def username(self):
        return self._username

    @username.setter
    def username(self, new_name: str):
        if not new_name:
            raise ValueError("Имя пользователя не может быть пустым")
        self._username = new_name

    @property
    def registration_date(self):
        return self._registration_date

    @property
    def hashed_password(self):
        return self._hashed_password

    @property
    def salt(self):
        return self._salt
    
    def _generate_salt(self) -> str:
        return hashlib.sha256(str(datetime.now().timestamp()).encode()).hexdigest()[:8]

    def _hash_password(self, password: str) -> str:
        return hashlib.sha256((password + self._salt).encode()).hexdigest()

    def get_user_info(self) -> dict:
        """Возвращает информацию о пользователе."""
        return {
            "user_id": self._user_id,
            "username": self._username,
            "registration_date": self._registration_date.isoformat(),
            "salt": self._salt,
            "hashed_password": self._hashed_password,
        }

    def verify_password(self, password: str) -> bool:
        """Проверяет правильность введённого пароля."""
        return self._hashed_password == self._hash_password(password)

    def change_password(self, new_password: str):
        """Изменяет пароль и пересчитывает хеш."""
        if len(new_password) < 4:
            raise ValueError("Пароль должен быть не короче 4 символов")
        self._salt = self._generate_salt()
        self._hashed_password = self._hash_password(new_password)


class Wallet:
    def __init__(self, currency_code: str, balance: float = 0.0):
        if not isinstance(currency_code, str) or not currency_code:
            raise ValueError("Код валюты должен быть непустой строкой")
        if not isinstance(balance, (int, float)) or balance < 0:
            raise ValueError("Баланс должен быть числом не меньше 0")

        self.currency_code = currency_code.upper()
        self._balance = float(balance)

    @property
    def balance(self) -> float:
        return self._balance

    @balance.setter
    def balance(self, value: float):
        if not isinstance(value, (int, float)):
            raise TypeError("Баланс должен быть числом")
        if value < 0:
            raise ValueError("Баланс не может быть отрицательным")
        self._balance = float(value)

    def deposit(self, amount: float):
        """Пополняет баланс на указанную сумму."""
        if not isinstance(amount, (int, float)):
            raise TypeError("Сумма пополнения должна быть числом")
        if amount <= 0:
            raise ValueError("Сумма пополнения должна быть положительной")
        self._balance += float(amount)

    def withdraw(self, amount: float):
        """Снимает средства с баланса, если хватает средств."""
        if not isinstance(amount, (int, float)):
            raise TypeError("Сумма снятия должна быть числом")
        if amount <= 0:
            raise ValueError("Сумма снятия должна быть положительной")
        if amount > self._balance:
            raise ValueError("Недостаточно средств на балансе")
        self._balance -= float(amount)


class Portfolio:
    def __init__(self, user_id: int, wallets: dict[str, Wallet]):
        if not isinstance(user_id, int) or user_id <= 0:
            raise ValueError("user_id должен быть положительным числом")

        self._user_id = user_id
        self._wallets = wallets or {}

    @property
    def user_id(self) -> int:
        #TODO: должен возвращать "объект пользователя (без возможности перезаписи)."
        return self._user_id

    @property
    def wallets(self) -> dict[str, Wallet]:
        """Возвращает копию словаря кошельков."""
        return deepcopy(self._wallets)

    def add_currency(self, currency_code: str):
        """Добавляет новый кошелёк, если его ещё нет."""
        code = currency_code.upper()
        if code in self._wallets:
            raise ValueError(f"Кошелёк для валюты {code} уже существует")

        self._wallets[code] = Wallet(currency_code=code)
        return self._wallets[code]

    def get_wallet(self, currency_code: str) -> Wallet:
        """Возвращает объект Wallet по коду валюты."""
        code = currency_code.upper()
        wallet = self._wallets.get(code)
        if wallet is None:
            raise KeyError(f"Кошелёк для валюты {code} не найден")
        return wallet

    def get_total_value(self, base_currency: str = "USD") -> float:
        """Возвращает общую стоимость портфеля в выбранной базовой валюте."""
        base_currency = base_currency.upper()

        total_value_base = 0.0
        for code, wallet in self._wallets.items():
            if code == base_currency:
                total_value_base += wallet.balance
            continue

        try:
            rate, _ = get_exchange_rate(code, base_currency)
        except ValueError:
            raise ValueError(f"Нет курса для валют {code}→{base_currency}")

        total_value_base += wallet.balance * rate

        return round(total_value_base, 2)


