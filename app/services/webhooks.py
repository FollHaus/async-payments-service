import asyncio
import httpx


async def send_webhook(client: httpx.AsyncClient, url: str, payload: dict[str, str]) -> httpx.Response | None:
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
