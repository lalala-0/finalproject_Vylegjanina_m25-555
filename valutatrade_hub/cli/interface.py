import shlex

from valutatrade_hub.core.exceptions import ApiRequestError, CurrencyNotFoundError, InsufficientFundsError
from valutatrade_hub.parser_service.usecase import show_rates, update_rates
from ..core import usecase
import prompt
from functools import wraps


def print_help():
    print(
        "Доступные команды:\n"
        "  register --username <имя> --password <пароль>   — регистрация\n"
        "  login --username <имя> --password <пароль>      — вход\n"
        "  show-portfolio [--base USD]                     — показать портфель\n"
        "  buy --currency <код> --amount <число>           — купить валюту\n"
        "  sell --currency <код> --amount <число>          — продать валюту\n"
        "  get-rate --from <код> --to <код>                — получить курс\n"
        "  update-rates [--source coingecko|exchangerate]  — обновить кеш курсов валют (по умолчанию все источники)\n"
        "  show-rates [--currency <код>] [--top <число>]   — показать актуальные курсы из кеша отсортирвоанные по алфавиту,\n"
        "                                                    можно фильтровать по валюте, количеству самых дорогих валют (сортировка по стоимости)\n"
        "  help                                                — показать список доступных команд\n"
        "  exit                                            — выход\n"
    )

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
    required_args: список обязательных аргументов (например ["--username", "--password"])
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

                result = fn(**{k.lstrip('-'): v for k, v in parsed.items() if v is not None})
                print(result)

            except ValueError as e:
                print(e)
            except InsufficientFundsError as e:
                print(f"Недостаточно средств: доступно {e.available} {e.code}, требуется {e.required} {e.code}")
            except CurrencyNotFoundError as e:
                print(f"Неизвестная валюта '{e.code}'. Используйте help get-rate или проверьте поддерживаемые валюты.")
            except ApiRequestError as e:
                print(f"Ошибка при обращении к внешнему API: {e.reason}. Попробуйте позже или проверьте сеть.")
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
                    return update_rates(source)
                cmd_update_rates(params)
            case "show-rates":
                @cli_command(optional_args={"--currency": None, "--top": None})
                def cmd_show_rates(currency=None, top=None):
                    try:
                        top_value = int(top) if top is not None else None
                    except ValueError:
                        return "ERROR: Параметр --top должен быть числом."
                    return show_rates(currency, top_value)
                cmd_show_rates(params)


            case _:
                print(f"Неизвестная команда: {cmd}. Введите 'help' для списка доступных.")

