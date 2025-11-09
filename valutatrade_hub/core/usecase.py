from valutatrade_hub.core.currancies import get_currency
from valutatrade_hub.core.exceptions import ApiRequestError, CurrencyNotFoundError, InsufficientFundsError
from valutatrade_hub.decorators import log_action
from valutatrade_hub.infra.settings import SettingsLoader
from . import utils as u
from .models import User, Wallet, Portfolio
from datetime import datetime

_current_user: User | None = None
_current_portfolio: Portfolio | None = None

@log_action("REGISTER")
def register(username: str, password: str) -> str:
    """Создаёт нового пользователя и пустой портфель."""
    users_file = SettingsLoader().get("USERS_FILE")
    users_data = u.load_json(users_file)

    if any(u["username"] == username for u in users_data):
        raise ValueError(f"Имя пользователя '{username}' уже занято")

    if len(password) < 4:
        raise ValueError("Пароль должен быть не короче 4 символов")

    user_id = u.next_id(users_data)
    user = User(user_id=user_id, username=username, password=password)
    users_data.append(user.get_user_info())
    u.save_json(users_file, users_data)

    portfolios_file = SettingsLoader().get("PORTFOLIOS_FILE")
    portfolios = u.load_json(portfolios_file)
    portfolios.append({
        "user_id": user_id,
        "wallets": {f"{SettingsLoader().get('BASE_CURRENCY')}": {"balance": 0.0}},
    })
    u.save_json(portfolios_file, portfolios)

    return f"Пользователь '{username}' зарегистрирован (id={user_id}). Войдите: login --username {username} --password ****"


@log_action("LOGIN")
def login(username: str, password: str) -> str:
    """Вход пользователя и загрузка его портфеля."""
    global _current_user, _current_portfolio

    users_data = u.load_json(SettingsLoader().get("USERS_FILE"))
    user_entry = next((u_ for u_ in users_data if u_["username"] == username), None)
    if not user_entry:
        raise ValueError(f"Пользователь '{username}' не найден")

    user = User(
        user_id=user_entry["user_id"],
        username=user_entry["username"],
        password=password,
        salt=user_entry["salt"],
        registration_date=datetime.fromisoformat(user_entry["registration_date"]),
    )

    if not user.verify_password(password):
        if user.hashed_password != user_entry["hashed_password"]:
            raise ValueError("Неверный пароль")

    _current_user = user
    _current_portfolio = Portfolio.load_portfolio(user.user_id)

    return f"Вы вошли как '{username}'"


def show_portfolio(base: str = "USD") -> str:
    """Показывает все кошельки и общую стоимость в базовой валюте."""
    if _current_user is None or _current_portfolio is None:
        raise ValueError("Сначала выполните login")

    base = base.upper()
    rates = u.load_json(SettingsLoader().get("RATES_FILE"))
    base_found = any(base in key.split("_") for key in rates.keys() if "_" in key)
    if not base_found:
        raise CurrencyNotFoundError(base)

    wallets = _current_portfolio.wallets
    if not wallets:
        return f"Портфель пользователя '{_current_user.username}' пуст."

    lines = [f"Портфель пользователя '{_current_user.username}' (база: {base}):"]
    total_value = 0.0

    for code, wallet in wallets.items():
        try:
            rate, _ = u.get_exchange_rate(code, base)
        except CurrencyNotFoundError:
            lines.append(f"- {code}: {wallet.balance:.4f} (нет курса {code}→{base})")
            continue
        except ApiRequestError as e:
            lines.append(f"- {code}: {wallet.balance:.4f} (ошибка API: {e})")
            continue
        converted = wallet.balance * rate
        total_value += converted
        lines.append(f"- {code}: {wallet.balance:.4f}  → {converted:.2f} {base}")

    lines.append("-" * 33)
    lines.append(f"ИТОГО: {total_value:.2f} {base}")
    return "\n".join(lines)


@log_action("BUY", verbose=True)
def buy(currency: str, amount: float) -> str:
    """Купить валюту и увеличить баланс кошелька."""
    if _current_portfolio is None or _current_user is None:
        raise ValueError("Сначала выполните login")
    if amount <= 0:
        raise ValueError("'amount' должен быть положительным числом")

    currency = currency.upper()
    try:
        get_currency(currency) 
    except CurrencyNotFoundError:
        raise

    try:
        wallet = _current_portfolio.get_wallet(currency)
    except CurrencyNotFoundError:
        wallet = _current_portfolio.add_currency(currency)

    old_balance = wallet.balance
    wallet.deposit(amount)
    _current_portfolio.save_portfolio()

    try:
        rate, _ = u.get_exchange_rate(currency, SettingsLoader().get("BASE_CURRENCY"))
    except CurrencyNotFoundError or ApiRequestError:
        raise

    value_usd = amount * rate
    return (f"Покупка выполнена: {amount:.4f} {currency} по курсу {rate:.2f} {SettingsLoader().get("BASE_CURRENCY")}/{currency}\n"
            f"Изменения в портфеле:\n- {currency}: было {old_balance:.4f} → стало {wallet.balance:.4f}\n"
            f"Оценочная стоимость покупки: {value_usd:.2f} {SettingsLoader().get("BASE_CURRENCY")}")


@log_action("SELL", verbose=True)
def sell(currency: str, amount: float) -> str:
    """Продать валюту: уменьшить баланс и начислить выручку в базовой валюте (USD)."""
    if _current_user is None or _current_portfolio is None:
        raise ValueError("Сначала выполните login")
    if amount <= 0:
        raise ValueError("'amount' должен быть положительным числом")

    try:
        wallet = _current_portfolio.get_wallet(currency.upper())
    except CurrencyNotFoundError:
        raise InsufficientFundsError(0.0, amount, currency)

    old_balance = wallet.balance
    try:
        wallet.withdraw(amount)
    except ValueError:
        raise InsufficientFundsError(wallet.balance, amount, currency)

    base_currency = SettingsLoader().get("BASE_CURRENCY")
    if currency == base_currency:
        _current_portfolio.save_portfolio()
        return (
            f"Продажа выполнена: {amount:.2f} {base_currency}\n"
            f"Изменения в портфеле:\n"
            f"- {base_currency}: было {old_balance:.2f} → стало {wallet.balance:.2f}\n"
            f"Примечание: продажа базовой валюты ({base_currency}) не конвертируется."
        )

    try:
        rate, _ = u.get_exchange_rate(currency, base_currency)
    except (CurrencyNotFoundError, ApiRequestError) as e:
        _current_portfolio.save_portfolio()
        return (
            f"Продажа частично выполнена: {amount:.4f} {currency} списано.\n"
            f"Ошибка конверсии в {base_currency}: {e.__class__.__name__} ({e})\n"
            f"Средства в {base_currency} не начислены, повторите позже."
        )
    
    revenue_usd = amount * rate
    try:
        usd_wallet = _current_portfolio.get_wallet(base_currency)
    except CurrencyNotFoundError:
        usd_wallet = _current_portfolio.add_currency(base_currency)
    old_usd_balance = usd_wallet.balance
    usd_wallet.deposit(revenue_usd)
    _current_portfolio.save_portfolio()

    return (
        f"Продажа выполнена: {amount:.4f} {currency} по курсу {rate:.2f} {base_currency}/{currency}\n"
        f"Изменения в портфеле:\n"
        f"- {currency}: было {old_balance:.4f} → стало {wallet.balance:.4f}\n"
        f"- {base_currency}: было {old_usd_balance:.2f} → стало {usd_wallet.balance:.2f}\n"
        f"Оценочная выручка: {revenue_usd:.2f} {base_currency}\n"
    )


def get_rate(frm: str, to: str) -> str:
    """Возвращает текущий курс валют и обратный курс."""
    frm, to = frm.upper(), to.upper()

    try:
        get_currency(frm)
        get_currency(to)
    except CurrencyNotFoundError:
        raise

    try:
        rate, updated = u.get_exchange_rate(frm, to)
        inv = 1 / rate
    except Exception as e:
        raise ApiRequestError(str(e))
    
    return (
        f"Курс {frm} → {to}: {rate:.6f} (обновлено: {updated.strftime('%Y-%m-%d %H:%M:%S')})\n"
        f"Обратный курс {to} → {frm}: {inv:.6f}"
    )
