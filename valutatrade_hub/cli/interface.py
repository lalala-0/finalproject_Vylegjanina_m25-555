import shlex
from prompt import prompt
from core import usecases

def print_help():
    print (
        "Доступные команды:\n"
        "  register --username <имя> --password <пароль>   — регистрация\n"
        "  login --username <имя> --password <пароль>      — вход\n"
        "  show-portfolio [--base USD]                     — показать портфель\n"
        "  buy --currency <код> --amount <число>           — купить валюту\n"
        "  sell --currency <код> --amount <число>          — продать валюту\n"
        "  get-rate --from <код> --to <код>                — получить курс\n"
        "  exit                                            — выход\n"
    )


def cli():
    print_help()

    while True:
        try:
            user_input = prompt("Введите команду: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nЗавершение работы.")
            break

        try:
            args = shlex.split(user_input, posix=False) # pyright: ignore[reportArgumentType]
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
                username = get_arg(params, "--username")
                password = get_arg(params, "--password")
                usecases.register(username, password)

            case "login":
                username = get_arg(params, "--username")
                password = get_arg(params, "--password")
                usecases.login(username, password)

            case "show-portfolio":
                base = get_arg(params, "--base", default="USD")
                usecases.show_portfolio(base)

            case "buy":
                currency = get_arg(params, "--currency")
                amount = float(get_arg(params, "--amount"))
                usecases.buy(currency, amount)

            case "sell":
                currency = get_arg(params, "--currency")
                amount = float(get_arg(params, "--amount"))
                usecases.sell(currency, amount)

            case "get-rate":
                from_currency = get_arg(params, "--from")
                to_currency = get_arg(params, "--to")
                usecases.get_rate(from_currency, to_currency)

            case _:
                print(f"Неизвестная команда: {cmd}. Введите 'help' для списка доступных.")


def get_arg(params, name, default=None):
    """Вспомогательная функция для парсинга аргументов"""
    if name in params:
        index = params.index(name)
        try:
            return params[index + 1]
        except IndexError:
            raise ValueError(f"Для параметра {name} нужно указать значение")
    if default is not None:
        return default
    raise ValueError(f"Отсутствует обязательный параметр {name}")


if __name__ == "__main__":
    cli()
