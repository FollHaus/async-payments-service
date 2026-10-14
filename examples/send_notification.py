import httpx
import asyncio

data = {
    "payment_id": "1",
    "status": "succeeded",
}

payment = {
    "amount": 2563.545,
    "currency": "USD",
    "description": "Gift card",
    "metadata": {
        "additionalProp1": {}
    },
    "webhook_url": "https://example.com/"
}

headers = {"Idempotency-Key": "order-995", "X-API-Key": "local-test-key"}


async def send_notifications():
    async with httpx.AsyncClient(timeout=3.0, trust_env=False) as client:
        attempts = 1
        max_attempts = 3

        while attempts <= max_attempts:
            print(f"Попытка №: {attempts}")
            try:
                response = await client.post("http://127.0.0.1:8000/api/v1/payments",
                                             headers=headers, json=payment)
                response.raise_for_status()
                response_json = response.json()

                print(response.status_code, response_json)
                return response_json
            except httpx.HTTPStatusError as he:
                # не успешный статус
                print(f"Status: {he.response.status_code}\n"
                      f"Description: {he.response.text}")
                return None

            except httpx.ConnectError:

                if attempts == max_attempts:
                    break

                delay_attempt = 2 ** (attempts - 1)
                attempts += 1

                print(f"[ConnectError] Повтор запроса, задержка {delay_attempt} сек.")
                await asyncio.sleep(delay_attempt)
            except httpx.RequestError as exc:
                # ошибка выполнения запроса
                print(f"Type: {type(exc).__name__}\n"
                      f"Message: {exc}")
                return None

        print("Невозможно выполнить доставку")
        return None


async def parallel_queries():
    async with httpx.AsyncClient(timeout=3.0, trust_env=False) as client:
        queries = [
            client.post("http://127.0.0.1:8000/api/v1/payments",
                              headers=headers, json=payment),
            client.post("http://127.0.0.1:8000/api/v1/payments",
                              headers=headers, json=payment),
            client.post("http://127.0.0.1:8000/api/v1/payments",
                              headers=headers, json=payment),
            client.post("http://127.0.0.1:8000/api/v1/payments",
                              headers=headers, json=payment),
            client.post("http://127.0.0.1:8000/api/v1/payments",
                              headers=headers, json=payment)
        ]
        results = await asyncio.gather(
            *queries
        )

        for result in results:
            print(result.status_code)
            print(result.text)


asyncio.run(parallel_queries())
