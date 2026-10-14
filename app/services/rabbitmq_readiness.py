import asyncio
import json
import subprocess
from typing import Any
from urllib.parse import urlsplit, unquote

import httpx

from app.core.config import settings


def queues_ready(queues: list[dict[str, str]]) -> bool:
    """Проверяет, что очереди RabbitMQ созданы и настроены корректно.

    Проверяет наличие очереди ``payments.new`` с политикой ``payments-dlq``
    и наличие очереди ``payments.dlq``.

    Args:
        queues: Список словарей с ключами ``name`` и ``policy`` для каждой очереди.

    Returns:
        ``True``, если обе очереди существуют и ``payments.new`` привязана
        к политике ``payments-dlq``, иначе ``False``.
    """
    policies_by_name = {queue["name"]: queue.get("policy") for queue in queues}

    return policies_by_name.get("payments.new") == "payments-dlq" and "payments.dlq" in policies_by_name


def bindings_ready(bindings: list[dict[str, str]]) -> bool:
    """Проверяет, что биндинг между обменом и очередью создан.

    Ожидается биндинг:
        источник: ``payments.dlx`` → назначение: ``payments.dlq``
        с routing key ``payments.dlq``.

    Args:
        bindings: Список словарей с ключами ``source_name``,
                  ``destination_name``, ``routing_key``.

    Returns:
        ``True``, если требуемый биндинг найден, иначе ``False``.
    """
    expected = {
        "source": "payments.dlx",
        "destination": "payments.dlq",
        "routing_key": "payments.dlq",
    }

    return any(expected.items() <= binding.items() for binding in bindings)


def policies_ready(policies: list[dict[str, object]]) -> bool:
    """Проверяет, что политика Dead-Letter создана и настроена верно.

    Ищет политику с именем ``payments-dlq`` для vhost ``payments``
    и проверяет, что в её ``definition`` указаны:
        - ``dead-letter-exchange``: ``payments.dlx``
        - ``dead-letter-routing-key``: ``payments.dlq``

    Args:
        policies: Список словарей политик RabbitMQ, включая поля
                  ``name``, ``vhost`` и ``definition`` (JSON-строка или словарь).

    Returns:
        ``True``, если политика найдена и содержит корректные параметры,
        иначе ``False``.
    """
    expected_policies = {
        "dead-letter-exchange": "payments.dlx",
        "dead-letter-routing-key": "payments.dlq"
    }

    for policy in policies:
        if policy["name"] == "payments-dlq" and policy["vhost"] == "payments":
            definition = policy["definition"]

            if isinstance(definition, str):
                definition = json.loads(definition)

            if not isinstance(definition, dict):
                return False

            return expected_policies.items() <= definition.items()

    return False


def topology_ready(
        queues: list[dict[str, str]],
        bindings: list[dict[str, str]],
        policies: list[dict[str, str]],
) -> bool:
    """Проверяет полную топологию RabbitMQ.

    Выполняет проверку очередей, биндингов и политик одновременно.

    Args:
        queues: Список очередей.
        bindings: Список биндингов.
        policies: Список политик.

    Returns:
        ``True``, если все три подпроверки прошли успешно, иначе ``False``.
    """
    return queues_ready(queues) and bindings_ready(bindings) and policies_ready(policies)


async def load_queues(
        client: httpx.AsyncClient,
) -> list[dict[str, Any]]:
    response = await client.get("/api/queues/payments")
    response.raise_for_status()
    return response.json()


async def load_bindings(
        client: httpx.AsyncClient,
) -> list[dict[str, Any]]:
    response = await client.get("/api/bindings/payments")
    response.raise_for_status()
    return response.json()


async def load_policies(
        client: httpx.AsyncClient,
) -> list[dict[str, Any]]:
    response = await client.get("/api/policies/payments")
    response.raise_for_status()
    return response.json()


async def wait_for_topology(
        client: httpx.AsyncClient,
        timeout: float = 60.0,
) -> bool:
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout

    while loop.time() < deadline:
        try:
            queues = await load_queues(client)
            bindings = await load_bindings(client)
            policies = await load_policies(client)
            if topology_ready(queues, bindings, policies):
                return True
        except (httpx.ConnectError, httpx.TimeoutException):
            print("Ожидание подключения")

        await asyncio.sleep(1)

    return False


async def main() -> int:
    broker_url = urlsplit(settings.rabbitmq_url)

    if broker_url.username is None or broker_url.password is None:
        raise ValueError("В RABBITMQ_URL должны быть указаны логин и пароль")

    auth = (unquote(broker_url.username), unquote(broker_url.password))
    base_url = settings.rabbitmq_management_url

    async with httpx.AsyncClient(timeout=3, trust_env=False, base_url=base_url, auth=auth) as client:
        is_ready = await wait_for_topology(client)

        if is_ready:
            return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
