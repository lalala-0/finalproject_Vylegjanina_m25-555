import functools
from datetime import datetime
import inspect
import time as time
from valutatrade_hub.logging_config import logger

def log_action(action: str, verbose: bool = False):
    """
    Декоратор для логирования бизнес-операций (BUY, SELL, REGISTER, LOGIN).
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            from valutatrade_hub.core import usecase 
            bound = inspect.signature(func).bind(*args, **kwargs)
            bound.apply_defaults()
            params = bound.arguments
        
            timestamp = datetime.now().isoformat(timespec="seconds")
            username = params.get("username") or getattr(params.get("user", None), "username", None) or getattr(usecase._current_user, "username", None)
            currency = params.get("currency") or params.get("currency_code")
            amount = params.get("amount")
            base = params.get("base", "USD")

            try:
                result = func(*args, **kwargs)

                log_msg = (
                    f"{action} user='{username}' currency='{currency}' amount={amount} base='{base}' result=OK"
                )

                if verbose and hasattr(result, "balance_before") and hasattr(result, "balance_after"):
                    log_msg += f" | balance: {result.balance_before} → {result.balance_after}"

                logger.info(f"{timestamp} {log_msg}")
                return result

            except Exception as e:
                log_msg = (
                    f"{action} user='{username}' currency='{currency}' amount={amount} "
                    f"result=ERROR type={type(e).__name__} message='{e}'"
                )
                logger.error(f"{timestamp} {log_msg}")
                raise

        return wrapper
    return decorator


def log_api_call(source_name: str):
    """
    Декоратор для логирования вызова API.
    Логирует старт, успех, ошибки и время выполнения.
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            logger.info(f"[{source_name}] Запрос курсов: старт")
            print(f"[{source_name}] Запрос курсов: старт")
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                elapsed = round((time.time() - start_time) * 1000, 2)
                logger.info(f"[{source_name}] Успех: получено {len(result)} курсов за {elapsed} мс")
                print(f"[{source_name}] Получено {len(result)} курсов за {elapsed} мс")
                return result
            except Exception as e:
                elapsed = round((time.time() - start_time) * 1000, 2)
                logger.error(f"[{source_name}] Ошибка после {elapsed} мс: {e}", exc_info=True)
                print(f"[{source_name}] Ошибка после {elapsed} мс: {e}")
                raise
        return wrapper
    return decorator
