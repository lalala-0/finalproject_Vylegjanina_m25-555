from . import utils as u
from .constants import USERS_FILE, PORTFOLIOS_FILE, EXCHANGE_RATES
from .models import User, Wallet, Portfolio
from datetime import datetime

_current_user: User | None = None
_current_portfolio: Portfolio | None = None

def register(username: str, password: str) -> str:
    """Создаёт нового пользователя и пустой портфель."""
    users_data = u.load_json(USERS_FILE)
    if any(u["username"] == username for u in users_data):
        return f"Имя пользователя '{username}' уже занято"
    if len(password) < 4:
        return "Пароль должен быть не короче 4 символов"

    user_id = u.next_id(users_data)
    user = User(user_id=user_id, username=username, password=password)
    users_data.append(user.get_user_info())
    u.save_json(USERS_FILE, users_data)

    portfolios = u.load_json(PORTFOLIOS_FILE)
    portfolios.append({
        "user_id": user_id,
        "wallets": {"USD": {"balance": 0.0}}
    })
    u.save_json(PORTFOLIOS_FILE, portfolios)

    return f"Пользователь '{username}' зарегистрирован (id={user_id}). Войдите: login --username {username} --password ****"


def login(username: str, password: str) -> str:
    """Вход пользователя и загрузка его портфеля."""
    global _current_user, _current_portfolio

    users_data = u.load_json(USERS_FILE)
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

    portfolios_data = u.load_json(PORTFOLIOS_FILE) 
    portfolio_entry = next((p for p in portfolios_data if p["user_id"] == user.user_id), None) 
    wallets_raw = portfolio_entry["wallets"] if portfolio_entry else {} 
    wallets = {code: Wallet(code, w["balance"]) for code, w in wallets_raw.items()} 
    _current_portfolio = Portfolio(user.user_id, wallets)

    return f"Вы вошли как '{username}'"


def show_portfolio(base: str = "USD") -> str:
    """Показывает все кошельки и общую стоимость в базовой валюте."""
    if _current_user is None or _current_portfolio is None:
        return "Сначала выполните login"

    base = base.upper()
    if base not in EXCHANGE_RATES:
        return f"Неизвестная базовая валюта '{base}'"

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
        return "Сначала выполните login"
    if amount <= 0:
        return "'amount' должен быть положительным числом"

    currency = currency.upper()
    wallets = _current_portfolio._wallets

    if currency not in wallets:
        wallets[currency] = Wallet(currency, 0.0)

    wallet = wallets[currency]
    old_balance = wallet.balance
    wallet.deposit(amount)

    _save_portfolio()

    try:
        rate, _ = u.get_exchange_rate(currency, "USD")
    except Exception:
        return f"Не удалось получить курс для {currency}→USD"


    value_usd = amount * rate
    return (f"Покупка выполнена: {amount:.4f} {currency} по курсу {rate:.2f} USD/{currency}\n"
            f"Изменения в портфеле:\n- {currency}: было {old_balance:.4f} → стало {wallet.balance:.4f}\n"
            f"Оценочная стоимость покупки: {value_usd:.2f} USD")


def sell(currency: str, amount: float) -> str:
    """Продать валюту и уменьшить баланс кошелька."""
    if _current_user is None or _current_portfolio is None:
        return "Сначала выполните login"
    if amount <= 0:
        return "'amount' должен быть положительным числом"

    currency = currency.upper()
    try:
        wallet = _current_portfolio.get_wallet(currency)
    except KeyError:
        return f"У вас нет кошелька '{currency}'. Добавьте валюту: она создаётся автоматически при первой покупке."

    try:
        old_balance = wallet.balance
        wallet.withdraw(amount)
    except ValueError as e:
        return str(e)

    _save_portfolio()

    try:
        rate, _ = u.get_exchange_rate(currency, "USD")
    except Exception:
        return f"Не удалось получить курс для {currency}→USD"

    revenue_usd = amount * rate
    return (f"Продажа выполнена: {amount:.4f} {currency} по курсу {rate:.2f} USD/{currency}\n"
            f"Изменения в портфеле:\n- {currency}: было {old_balance:.4f} → стало {wallet.balance:.4f}\n"
            f"Оценочная выручка: {revenue_usd:.2f} USD")


def get_rate(frm: str, to: str) -> str:
    """Возвращает текущий курс валют и обратный курс."""
    frm, to = frm.upper(), to.upper()

    try:
        rate, updated = u.get_exchange_rate(frm, to)
        inv = 1 / rate
    except Exception:
        return f"Курс {frm}→{to} недоступен. Повторите попытку позже."

    return (
        f"Курс {frm} → {to}: {rate:.6f} (обновлено: {updated.strftime('%Y-%m-%d %H:%M:%S')})\n"
        f"Обратный курс {to} → {frm}: {inv:.6f}"
    )

def _save_portfolio():
    """Сохраняет портфель текущего пользователя."""
    portfolios = u.load_json(PORTFOLIOS_FILE)
    for p in portfolios:
        if p["user_id"] == _current_portfolio.user_id:
            p["wallets"] = {code: {"balance": w.balance} for code, w in _current_portfolio._wallets.items()}
            break
    else:
        portfolios.append({
            "user_id": _current_portfolio.user_id,
            "wallets": {code: {"balance": w.balance} for code, w in _current_portfolio._wallets.items()}
        })
    u.save_json(PORTFOLIOS_FILE, portfolios)