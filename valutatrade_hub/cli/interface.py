import shlex
from functools import wraps
from json import JSONDecodeError

import prompt

from valutatrade_hub.core.currancies import getRegistryCurrencys
from valutatrade_hub.core.exceptions import (
    ApiRequestError,
    CurrencyNotFoundError,
    InsufficientFundsError,
    RateNotFoundError,
)

from ..core import usecase


def print_help():
    commands = [
        ("register --username <имя> --password <пароль>", "регистрация"),
        ("login --username <имя> --password <пароль>", "вход"),
        ("show-portfolio [--base USD]", "показать портфель"),
        ("buy --currency <код> --amount <число>", "купить валюту"),
        ("sell --currency <код> --amount <число>", "продать валюту"),
        ("get-rate --from <код> --to <код>", "получить курс"),
        ("update-rates [--source coingecko|exchangerate]",
         "обновить кэш курсов валют (по умолчанию все источники)"),
        ("show-rates [--currency <код>] [--top <число>]",
         "показать актуальные курсы из кэша"),
        ("help", "показать список доступных команд"),
        ("exit", "выход"),
    ]

    print("\nДоступные команды:\n")
    for cmd, desc in commands:
        print(f"  {cmd:<50} — {desc}")
    print()


def get_arg(params, name, default=None):
    """Вспомогательная функция для парсинга аргументов"""
    if name in params:
        index = params.index(name)
        try:
            value = params[index + 1]
            if value.startswith("--"):
                raise ValueError(f"Для параметра {name} нужно указать значение")
            return value
        except IndexError:
            raise ValueError(f"Для параметра {name} нужно указать значение")
    if default is not None:
        return default
    raise ValueError(f"Отсутствует обязательный параметр {name}")


def cli_command(required_args=None, optional_args=None):
    """
    Декоратор для CLI-команд.
    required_args: список обязательных аргументов (например ["--username", "--amount"])
    optional_args: словарь с параметрами по умолчанию, например {"--base": "USD"}
    """
    required_args = required_args or []
    optional_args = optional_args or {}

    def decorator(fn):
        @wraps(fn)
        def wrapper(params):
            try:
                parsed = {arg: get_arg(params, arg) for arg in required_args}

                for arg, default in optional_args.items():
                    if arg in params:
                        parsed[arg] = get_arg(params, arg, default)
                    elif default is not None:
                        parsed[arg] = default

                result = fn(**{k.lstrip('-'): \
                               v for k, v in parsed.items() if v is not None})
                print(result)

            except JSONDecodeError as e:
                print(f"Некорректный JSON-файл ({e.filename}).")
                print(f"Проверьте синтаксис (строка {e.lineno}): {e.msg}")
            except ValueError as e:
                print(e)
            except InsufficientFundsError as e:
                print(f"Недостаточно средств: доступно {e.available} {e.code}, "\
                                            f"требуется {e.required} {e.code}")
            except RateNotFoundError as e:
                print(f"Курс {e.code} не найден.")
                print("Используйте show-rates для просмотра списка курсов.")
            except CurrencyNotFoundError as e:
                print(f"Неизвестная валюта '{e.code}'. Доступные валюты: \n")
                print(getRegistryCurrencys())
            except ApiRequestError as e:
                print(f"{e} Попробуйте позже или проверьте сеть.")
            except FileNotFoundError as e:
                print(f"Файл данных не найден: {e.filename}")
            except Exception as e:
                print(f"Неожиданная ошибка: {e}")

        return wrapper
    return decorator


def cli():
    print_help()

    while True:
        try:
            user_input = prompt.string("\n>>>Введите команду: ")
        except (KeyboardInterrupt, EOFError):
            print("\nЗавершение работы.")
            break

        try:
            args = shlex.split(user_input, posix=False)
            cmd, *params = args
        except Exception as e:
            print(f"Некорректные параметры: {e}")
            continue

        match cmd:
            case "exit":
                print("Выход из программы.")
                break
            case "help":
                print_help()

            case "register":
                @cli_command(required_args=["--username", "--password"])
                def cmd_register(username, password):
                    return usecase.register(username, password)
                cmd_register(params)
            case "login":
                @cli_command(required_args=["--username", "--password"])
                def cmd_login(username, password):
                    return usecase.login(username, password)
                cmd_login(params)
            case "show-portfolio":
                @cli_command(optional_args={"--base": "USD"})
                def cmd_show_portfolio(base):
                    return usecase.show_portfolio(base)
                cmd_show_portfolio(params)
            case "buy":
                @cli_command(required_args=["--currency", "--amount"])
                def cmd_buy(currency, amount):
                    try:
                        amount = float(amount) if amount is not None else None
                    except ValueError:
                        return "ERROR: Параметр --amount должен быть числом."
                    return usecase.buy(currency, amount)
                cmd_buy(params)
            case "sell":
                @cli_command(required_args=["--currency", "--amount"])
                def cmd_sell(currency, amount):
                    try:
                        amount = float(amount) if amount is not None else None
                    except ValueError:
                        return "ERROR: Параметр --amount должен быть числом."
                    return usecase.sell(currency, amount)
                cmd_sell(params)
            case "get-rate":
                @cli_command(required_args=["--from", "--to"])
                def cmd_get_rate(**kwargs):
                    return usecase.get_rate(kwargs["from"], kwargs["to"])
                cmd_get_rate(params)

            case "update-rates":
                @cli_command(optional_args={"--source": None})
                def cmd_update_rates(source=None):
                    return usecase.update_rates(source)
                cmd_update_rates(params)
            case "show-rates":
                @cli_command(optional_args={"--currency": None, "--top": None})
                def cmd_show_rates(currency=None, top=None):
                    try:
                        top_value = int(top) if top is not None else None
                    except ValueError:
                        return "ERROR: Параметр --top должен быть числом."
                    return usecase.show_rates(currency, top_value)
                cmd_show_rates(params)


            case _:
                print(f"Неизвестная команда: {cmd}. "\
                      f"Введите 'help' для списка доступных.")

