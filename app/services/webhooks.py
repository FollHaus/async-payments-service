"""Модуль для отправки вебхуков с повторными попытками.

Предоставляет асинхронную функцию отправки HTTP POST-запросов
с экспоненциальной задержкой между повторными попытками.
"""

import asyncio
import httpx


async def send_webhook(
    client: httpx.AsyncClient,
    url: str,
    payload: dict[str, str],
) -> httpx.Response | None:
    """Отправить вебхук с механизмом повторных попыток.

    Выполняет POST-запрос на указанный URL с заданным JSON-телом.
    При ошибках сервера (5xx, 429) и сетевых ошибках (ConnectError,
    TimeoutException) повторяет запрос до ``max_attempts`` раз
    с экспоненциальной задержкой (2^(attempt-1) секунд).

    Ошибки клиента (4xx, кроме 429) и необрабатываемые ошибки
    ``RequestError`` вызывают немедленное повторное поднятие исключения.

    Args:
        client: Асинхронный HTTP-клиент ``httpx.AsyncClient``.
        url: URL-адрес webhook-эндпоинта для отправки запроса.
        payload: Словарь данных, сериализуемых в JSON-тело запроса.

    Returns:
        Объект ``httpx.Response`` при успешном ответе (статус 2xx).
        ``None``, если все попытки исчерпаны без успеха.

    Raises:
        httpx.HTTPStatusError: Если ответ содержит код ошибки
            (4xx, кроме 429, или 5xx после исчерпания попыток).
        httpx.ConnectError / httpx.TimeoutException: При сетевых
            ошибках после исчерпания попыток.
        httpx.RequestError: При необрабатываемых ошибках запроса.
    """
    attempts = 1
    max_attempts = 3

    while attempts <= max_attempts:
        print(f"Попытка №: {attempts}")

        delay_attempt = 2 ** (attempts - 1)

        try:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            return response

        except httpx.HTTPStatusError as he:
            retryable = 500 <= he.response.status_code < 600 or he.response.status_code == 429

            if not retryable:
                raise
            if attempts == max_attempts:
                raise

            print(f"Повтор запроса, задержка {delay_attempt} сек.")
            await asyncio.sleep(delay_attempt)

        except (httpx.ConnectError, httpx.TimeoutException) as exc:

            if attempts == max_attempts:
                raise

            print(f"[{type(exc).__name__}] Повтор запроса, задержка {delay_attempt} сек.")
            await asyncio.sleep(delay_attempt)

        except httpx.RequestError as exc:
            # ошибка выполнения запроса
            print(f"Type: {type(exc).__name__}\n"
                  f"Message: {exc}")
            raise

        attempts += 1

    print("Невозможно выполнить доставку")
    return None