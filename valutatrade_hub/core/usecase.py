from datetime import datetime

from prettytable import PrettyTable

from valutatrade_hub.decorators import log_action
from valutatrade_hub.infra.settings import SettingsLoader
from valutatrade_hub.logging_config import logger
from valutatrade_hub.parser_service.config import ParserConfig
from valutatrade_hub.parser_service.storage import RatesStorage

from . import utils as u
from .currancies import get_currency
from .exceptions import (
    ApiRequestError,
    CurrencyNotFoundError,
    InsufficientFundsError,
    RateNotFoundError,
)
from .models import Portfolio, User

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

    return f"Пользователь '{username}' зарегистрирован (id={user_id}). "\
        f"Войдите: login --username {username} --password ****"


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
        raise RateNotFoundError(base)

    wallets = _current_portfolio.wallets
    if not wallets:
        return f"Портфель пользователя '{_current_user.username}' пуст."

    lines = [f"Портфель пользователя '{_current_user.username}' (база: {base}):"]
    total_value = 0.0

    for code, wallet in wallets.items():
        try:
            rate, _ = u.get_exchange_rate(code, base)
        except RateNotFoundError:
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

    base_currency = SettingsLoader().get("BASE_CURRENCY")
    currency = currency.upper()
    if currency == base_currency:
        raise ValueError(f"Нельзя покупать базовую валюту {base_currency}.")
    get_currency(currency)
    try:
        rate, _ = u.get_exchange_rate(currency, base_currency)
    except (CurrencyNotFoundError, ApiRequestError) as e:
        raise ApiRequestError(\
            f"Не удалось получить курс для {currency}/{base_currency}: {e}")

    cost_in_base = amount * rate
    try:
        base_wallet = _current_portfolio.get_wallet(base_currency)
    except CurrencyNotFoundError:
        raise InsufficientFundsError(0.0, cost_in_base, base_currency)

    if base_wallet.balance < cost_in_base:
        raise InsufficientFundsError(base_wallet.balance, cost_in_base, base_currency)
    old_base_balance = base_wallet.balance
    base_wallet.withdraw(cost_in_base)

    try:
        wallet = _current_portfolio.get_wallet(currency)
    except CurrencyNotFoundError:
        wallet = _current_portfolio.add_currency(currency)

    old_balance = wallet.balance
    wallet.deposit(amount)
    _current_portfolio.save_portfolio()

    return (
        f"Покупка выполнена: {amount:.4f} {currency} "\
            f"по курсу {rate:.2f} {base_currency}/{currency}\n"
        f"Изменения в портфеле:\n"
        f"- {currency}: было {old_balance:.4f} → стало {wallet.balance:.4f}\n"
        f"- {base_currency}: "\
            f"было {old_base_balance:.2f} → стало {base_wallet.balance:.2f}\n"
        f"Стоимость покупки: {cost_in_base:.2f} {base_currency}\n"

    )

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
        raise ValueError(f"Нельзя продавать базовую валюту {base_currency}")

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
        f"Продажа выполнена: {amount:.4f} {currency} "\
            f"по курсу {rate:.2f} {base_currency}/{currency}\n"
        f"Изменения в портфеле:\n"
        f"- {currency}: было {old_balance:.4f} → стало {wallet.balance:.4f}\n"
        f"- {base_currency}: "\
            f"было {old_usd_balance:.2f} → стало {usd_wallet.balance:.2f}\n"
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
        f"Курс {frm} → {to}: {rate:.6f} "\
            f"(обновлено: {updated.strftime('%Y-%m-%d %H:%M:%S')})\n"
        f"Обратный курс {to} → {frm}: {inv:.6f}"
    )

def update_rates(source: str| None = None) -> str:
    """
    Обновляет курсы валют через RatesUpdater, логирует процесс и выводит краткий отчёт.
    source: 'coingecko', 'exchangerate' или None (все источники)
    """
    try:
        print("INFO: Старт обновления курсов...")
        logger.info("Старт обновления курсов...")

        u.update_rates(source)

        storage = RatesStorage()
        rates = storage.load_rates()
        last_refr = rates.get("last_refresh", "unknown").replace('T', ' ').split('+')[0]
        total_updated = len([k for k in rates if k not in ("source", "last_refresh")])

        logger.info(f"Обновление курсов успешно. Всего обновлено: {total_updated}. "\
            f"Время последнего обновления: {last_refr}")
        return f"INFO: Обновление курсов успешно. Всего обновлено: {total_updated}. "\
            f"Время последнего обновления: {last_refr}"

    except ApiRequestError as e:
        logger.error(e)
        return f"ERROR: {e}"

def show_rates(currency: str = None, top: int = None) -> str:
    """
    Показать список актуальных курсов из локального кэша, упорядоченный по алфавиту.
    Опционально фильтрует по валюте (--currency),
    показывает N самых дорогих и упорядочивает по стоимости (--top).
    """
    try:
        if currency is not None:
            currency = currency.upper()
            get_currency(currency)
    except CurrencyNotFoundError as e:
        logger.error(e)
        return f"ERROR: {e}"
    if top is not None and top < 0:
        logger.error("Параметр 'top' должен быть положительным числом")
        return "ERROR: Параметр 'top' должен быть положительным числом"

    base =  ParserConfig().get("BASE_CURRENCY", "USD")

    storage = RatesStorage()
    rates = storage.load_rates()
    if not rates or "last_refresh" not in rates:
        msg = "Локальный кеш курсов пуст. " \
        "Выполните 'update-rates', чтобы загрузить данные."
        logger.warning(msg)
        return f"WARNING: {msg}"

    last_refresh = rates.get("last_refresh")
    filtered = []

    for pair, info in rates.items():
        if pair in ("source", "last_refresh"):
            continue

        from_curr, to_curr = pair.split("_")
        if currency and from_curr != currency:
            continue

        rate = info["rate"]
        if base != to_curr:
            try:
                if (key := f"{to_curr}_{base}") in rates:
                    base_rate = rates[key]["rate"], \
                        datetime.fromisoformat(rates[key]["updated_at"])
                if (rev := f"{base}_{to_curr}") in rates:
                    base_rate = 1 / rates[rev]["rate"], \
                        datetime.fromisoformat(rates[rev]["updated_at"])
                rate /= base_rate
                to_curr = base
            except Exception:
                continue

        filtered.append((f"{from_curr}_{to_curr}", rate, info["updated_at"]))

    if not filtered:
        msg = f"Курс для '{currency}' не найден в кеше." \
            if currency else "Нет доступных курсов."
        logger.info(msg)
        return f"INFO: {msg}"

    if top:
        filtered.sort(key=lambda x: x[1], reverse=True)
        filtered = filtered[:int(top)]
    else:
        filtered.sort(key=lambda x: x[0])

    table = PrettyTable()
    table.field_names = ["Валютная пара", "Курс", "Обновлено"]
    table.align["Курс"] = "r"

    for pair, rate, updated_at in filtered:
        table.add_row([pair, f"{rate:.6f}", updated_at.replace('T', ' ').split('+')[0]])

    table_str = f"Курсы из кэша "\
        f"(обновлены {last_refresh.replace('T', ' ').split('+')[0]}):\n{table}"
    return table_str

