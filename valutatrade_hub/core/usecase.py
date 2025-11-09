from valutatrade_hub.core.currancies import get_currency
from valutatrade_hub.core.exceptions import ApiRequestError, CurrencyNotFoundError, InsufficientFundsError
from valutatrade_hub.infra.settings import SettingsLoader
from . import utils as u
from .models import User, Wallet, Portfolio
from datetime import datetime

_current_user: User | None = None
_current_portfolio: Portfolio | None = None

def register(username: str, password: str) -> str:
    """Создаёт нового пользователя и пустой портфель."""
    users_data = u.load_json(SettingsLoader().get("USERS_FILE"))
    if any(u["username"] == username for u in users_data):
        return f"Имя пользователя '{username}' уже занято"
    if len(password) < 4:
        return "Пароль должен быть не короче 4 символов"

    user_id = u.next_id(users_data)
    user = User(user_id=user_id, username=username, password=password)
    users_data.append(user.get_user_info())
    u.save_json(SettingsLoader().get("USERS_FILE"), users_data)

    portfolios = u.load_json(SettingsLoader().get("PORTFOLIOS_FILE"))
    portfolios.append({
        "user_id": user_id,
        "wallets": {"USD": {"balance": 0.0}}
    })
    u.save_json(SettingsLoader().get("PORTFOLIOS_FILE"), portfolios)

    return f"Пользователь '{username}' зарегистрирован (id={user_id}). Войдите: login --username {username} --password ****"


def login(username: str, password: str) -> str:
    """Вход пользователя и загрузка его портфеля."""
    global _current_user, _current_portfolio

    users_data = u.load_json(SettingsLoader().get("USERS_FILE"))
    user_entry = next((u_ for u_ in users_data if u_["username"] == username), None)
    if not user_entry:
        return f"Пользователь '{username}' не найден"

    user = User(
        user_id=user_entry["user_id"],
        username=user_entry["username"],
        password=password,
        salt=user_entry["salt"],
        registration_date=datetime.fromisoformat(user_entry["registration_date"]),
    )

    if not user.verify_password(password):
        if user.hashed_password != user_entry["hashed_password"]:
            return "Неверный пароль"

    _current_user = user

    portfolios_data = u.load_json(SettingsLoader().get("PORTFOLIOS_FILE")) 
    portfolio_entry = next((p for p in portfolios_data if p["user_id"] == user.user_id), None) 
    wallets_raw = portfolio_entry["wallets"] if portfolio_entry else {} 
    wallets = {code: Wallet(code, w["balance"]) for code, w in wallets_raw.items()} 
    _current_portfolio = Portfolio(user.user_id, wallets)

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
        except Exception:
            lines.append(f"- {code}: {wallet.balance:.4f} (нет курса {code}→{base})")
            continue
        converted = wallet.balance * rate
        total_value += converted
        lines.append(f"- {code}: {wallet.balance:.4f}  → {converted:.2f} {base}")

    lines.append("-" * 33)
    lines.append(f"ИТОГО: {total_value:.2f} {base}")
    return "\n".join(lines)


def buy(currency: str, amount: float) -> str:
    """Купить валюту и увеличить баланс кошелька."""
    if _current_user is None or _current_portfolio is None:
        raise ValueError("Сначала выполните login")
    if amount <= 0:
        raise ValueError("'amount' должен быть положительным числом")

    currency = currency.upper()
    try:
        get_currency(currency) 
    except CurrencyNotFoundError:
        raise

    wallets = _current_portfolio._wallets
    if currency not in wallets:
        wallets[currency] = Wallet(currency, 0.0)

    wallet = wallets[currency]
    old_balance = wallet.balance
    wallet.deposit(amount)

    _save_portfolio()

    try:
        rate, _ = u.get_exchange_rate(currency, "USD")
    except Exception as e:
        raise ApiRequestError(str(e))


    value_usd = amount * rate
    return (f"Покупка выполнена: {amount:.4f} {currency} по курсу {rate:.2f} USD/{currency}\n"
            f"Изменения в портфеле:\n- {currency}: было {old_balance:.4f} → стало {wallet.balance:.4f}\n"
            f"Оценочная стоимость покупки: {value_usd:.2f} USD")


def sell(currency: str, amount: float) -> str:
    """Продать валюту: уменьшить баланс и начислить выручку в USD."""
    if _current_user is None or _current_portfolio is None:
        raise ValueError("Сначала выполните login")
    if amount <= 0:
        raise ValueError("'amount' должен быть положительным числом")

    currency = currency.upper()
    wallets = _current_portfolio._wallets
    if currency not in wallets:
        raise CurrencyNotFoundError(currency)

    wallet = wallets[currency]
    old_balance = wallet.balance
    try:
        wallet.withdraw(amount)
    except ValueError:
        raise InsufficientFundsError(wallet.balance, amount, currency)

    if currency == "USD":
        _save_portfolio()
        return (
            f"Продажа выполнена: {amount:.2f} USD\n"
            f"Изменения в портфеле:\n"
            f"- USD: было {old_balance:.2f} → стало {wallet.balance:.2f}\n"
            f"Примечание: продажа базовой валюты (USD) не конвертируется."
        )

    try:
        rate, _ = u.get_exchange_rate(currency, "USD")
    except Exception as e:
        _save_portfolio()
        raise ApiRequestError(str(e))

    revenue_usd = amount * rate
    usd_wallet = _current_portfolio.get_wallet("USD") if "USD" in _current_portfolio._wallets else _current_portfolio.add_wallet("USD", 0.0)
    old_usd_balance = usd_wallet.balance
    usd_wallet.deposit(revenue_usd)
    _save_portfolio()

    return (
        f"Продажа выполнена: {amount:.4f} {currency} по курсу {rate:.2f} USD/{currency}\n"
        f"Изменения в портфеле:\n"
        f"- {currency}: было {old_balance:.4f} → стало {wallet.balance:.4f}\n"
        f"- USD: было {old_usd_balance:.2f} → стало {usd_wallet.balance:.2f}\n"
        f"Оценочная выручка: {revenue_usd:.2f} USD\n"
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

def _save_portfolio():
    """Сохраняет портфель текущего пользователя."""
    portfolios = u.load_json(SettingsLoader().get("PORTFOLIOS_FILE"))
    for p in portfolios:
        if p["user_id"] == _current_portfolio.user_id:
            p["wallets"] = {code: {"balance": w.balance} for code, w in _current_portfolio._wallets.items()}
            break
    else:
        portfolios.append({
            "user_id": _current_portfolio.user_id,
            "wallets": {code: {"balance": w.balance} for code, w in _current_portfolio._wallets.items()}
        })
    u.save_json(SettingsLoader().get("PORTFOLIOS_FILE"), portfolios)