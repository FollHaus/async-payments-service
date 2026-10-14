import json
import subprocess


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
    policies_by_name = {queue["name"]: queue["policy"] for queue in queues}

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
    expected = {"source_name": "payments.dlx", "destination_name": "payments.dlq", "routing_key": "payments.dlq"}

    return any(expected.items() <= binding.items() for binding in bindings)


def policies_ready(policies: list[dict[str, object]]) -> bool:
    """Проверяет, что политика Dead-Letter создана и настроена верно.

    Ищет политику с именем ``payments-dlq`` для vhost ``payments``
    и проверяет, что в её ``definition`` указаны:
        - ``dead-letter-exchange``: ``payments.dlx``
        - ``dead-letter-routing-key``: ``payments.dlq``

    Args:
        policies: Список словарей политик RabbitMQ, включая поля
                  ``name``, ``vhost`` и ``definition`` (JSON-строка).

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
            definition = json.loads(policy["definition"])
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


def load_queues() -> list[dict[str, str]]:
    """Загружает список очередей из RabbitMQ через ``rabbitmqctl``.

    Выполняет ``docker compose exec`` для контейнера ``rabbitmq``
    и парсит JSON-вывод ``list_queues`` для vhost ``payments``.

    Returns:
        Список словарей с полями ``name`` и ``policy`` каждой очереди.

    Raises:
        subprocess.CalledProcessError: Если команда завершилась с ошибкой.
        json.JSONDecodeError: Если вывод не является валидным JSON.
    """
    cmd = ['docker', 'compose', 'exec', '-T', 'rabbitmq', "rabbitmqctl", "-q", "list_queues", "-p", "payments", "name",
           "policy", "--formatter", "json"]
    result = subprocess.run(cmd, capture_output=True, check=True, text=True, encoding="utf-8").stdout.strip()
    json_res = json.loads(result)

    return json_res


def load_bindings() -> list[dict[str, str]]:
    """Загружает список биндингов из RabbitMQ через ``rabbitmqctl``.

    Выполняет ``docker compose exec`` для контейнера ``rabbitmq``
    и парсит JSON-вывод ``list_bindings`` для vhost ``payments``.

    Returns:
        Список словарей с полями ``source_name``, ``destination_name``,
        ``routing_key`` для каждого биндинга.

    Raises:
        subprocess.CalledProcessError: Если команда завершилась с ошибкой.
        json.JSONDecodeError: Если вывод не является валидным JSON.
    """
    cmd = ['docker', 'compose', 'exec', '-T', 'rabbitmq', 'rabbitmqctl', '-q', 'list_bindings', '-p', 'payments',
           'source_name', 'destination_name', 'routing_key', '--formatter', 'json'
           ]
    result = subprocess.run(cmd, capture_output=True, check=True, text=True, encoding="utf-8").stdout.strip()
    json_res = json.loads(result)

    return json_res


def load_policies() -> list[dict[str, str]]:
    """Загружает список политик из RabbitMQ через ``rabbitmqctl``.

    Выполняет ``docker compose exec`` для контейнера ``rabbitmq``
    и парсит JSON-вывод ``list_policies`` для vhost ``payments``.

    Returns:
        Список словарей с полями политик, включая ``name``, ``vhost``,
        ``definition`` и другие.

    Raises:
        subprocess.CalledProcessError: Если команда завершилась с ошибкой.
        json.JSONDecodeError: Если вывод не является валидным JSON.
    """
    cmd = ['docker', 'compose', 'exec', '-T', 'rabbitmq', 'rabbitmqctl', '-q', 'list_policies', '-p', 'payments',
           '--formatter', 'json'
           ]
    result = subprocess.run(cmd, capture_output=True, check=True, text=True, encoding="utf-8").stdout.strip()
    json_res = json.loads(result)

    return json_res


def main() -> int:
    """Точка входа для проверки топологии RabbitMQ.

    Загружает очереди, биндинги и политики, затем проверяет
    их корректность через ``topology_ready``.

    Returns:
        0 — если топология корректна, 1 — в случае ошибки или
        некорректной топологии.+
    """
    try:
        queues = load_queues()
        bindings = load_bindings()
        policies = load_policies()

        if topology_ready(queues, bindings, policies):
            return 0

        return 1
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, json.JSONDecodeError) as exc:
        print(exc)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())