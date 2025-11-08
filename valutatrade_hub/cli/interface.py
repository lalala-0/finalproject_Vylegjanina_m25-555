import shlex
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
                    parsed[arg] = get_arg(params, arg, default)

                result = fn(**{k.lstrip('-'): v for k, v in parsed.items()})
                print(result)

            except ValueError as e:
                print(f"Ошибка: {e}")
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
                    return usecase.buy(currency, float(amount))
                cmd_buy(params)
            case "sell":
                @cli_command(required_args=["--currency", "--amount"])
                def cmd_sell(currency, amount):
                    return usecase.sell(currency, float(amount))
                cmd_sell(params)
            case "get-rate":
                @cli_command(required_args=["--from", "--to"])
                def cmd_get_rate(**kwargs):
                    return usecase.get_rate(kwargs["from"], kwargs["to"])
                cmd_get_rate(params)
                
            case _:
                print(f"Неизвестная команда: {cmd}. Введите 'help' для списка доступных.")

