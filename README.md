# Async Payments Service

Асинхронный сервис обработки платежей. API принимает платёж и возвращает `202 Accepted`, а отдельный consumer имитирует обработку и отправляет результат на указанный webhook.

Стек: Python 3.12, FastAPI, Pydantic 2, SQLAlchemy Async, asyncpg, PostgreSQL 17, RabbitMQ, FastStream, Alembic, HTTPX, uv и Docker Compose.

## Как работает сервис

1. API сохраняет платёж со статусом `pending` и событие `payment.created` в outbox в одной транзакции PostgreSQL.
2. Outbox worker выбирает неопубликованные события с `FOR UPDATE SKIP LOCKED`, публикует их в `payments.new` и отмечает время публикации после подтверждения брокера.
3. Consumer блокирует строку платежа, имитирует обработку в течение 2–5 секунд и сохраняет результат: `succeeded` с вероятностью 90% или `failed` с вероятностью 10%.
4. После завершения транзакции consumer отправляет HTTP POST на `webhook_url`.
5. Если доставка окончательно не удалась, сообщение направляется через `payments.dlx` в `payments.dlq`.

Повторная обработка события для завершённого платежа сохраняет прежние `status` и `processed_at`, но повторяет отправку webhook. Получатель должен учитывать возможность повторных уведомлений. Публикация в RabbitMQ и отметка в PostgreSQL не являются общей транзакцией: при сбое между ними событие может быть опубликовано повторно.

## Запуск

Для контейнерного запуска нужны Docker и Docker Compose с поддержкой `post_start` (Compose 2.30+). Проект проверялся с Compose 5.5.1 на Windows. Команды выполняются из корня проекта. Python на хосте нужен только для локальных примеров.

### 1. Настройка окружения

Создайте `.env.docker`:

```dotenv
API_KEY=local-test-key
DATABASE_URL=postgresql+asyncpg://payments:POSTGRES_PASSWORD_HERE@postgres:5432/payments
RABBITMQ_URL=amqp://rabbitmq:RABBITMQ_PASSWORD_HERE@rabbitmq:5672/payments
RABBITMQ_MANAGEMENT_URL=http://rabbitmq:15672
```

Замените `POSTGRES_PASSWORD_HERE` и `RABBITMQ_PASSWORD_HERE` значениями `POSTGRES_PASSWORD` и `RABBITMQ_DEFAULT_PASS` из `compose.yaml`. Если меняете пользователей, согласуйте их с Compose. Специальные символы в логине и пароле внутри URL необходимо percent-encode. `API_KEY` задайте самостоятельно и используйте в запросах.

Внутри Docker адреса сервисов — `postgres` и `rabbitmq`. `127.0.0.1` внутри контейнера указывает на сам контейнер. Файл `.env.docker` передаётся сервисам через `env_file`; локальный `.env` используется при запуске Python непосредственно на хосте. Файлы с реальными секретами не следует включать в репозиторий.

### 2. Сборка и запуск

```powershell
docker compose up -d --build
docker compose ps -a
```

При запуске автоматически выполняются миграции и импорт `docker/rabbitmq/definitions.json`. Сервис `rabbitmq-ready` проверяет очереди, binding и политику DLQ через Management API. Он ожидает готовности около 60 секунд; текущие HTTP-запросы могут немного увеличить этот срок. Ошибки подключения и таймауты повторяются; прочие ошибки завершают проверку.

`consumer` и `outbox` запускаются после успешного завершения миграций и проверки топологии.

| Сервис | Ожидаемое состояние |
| --- | --- |
| `postgres`, `rabbitmq` | Up (healthy) |
| `api`, `consumer`, `outbox` | Up |
| `migrate`, `rabbitmq-ready` | Exited (0) |

`Exited (0)` для одноразовых сервисов означает успешное завершение. Проверка готовности без сообщений может иметь пустой лог.

| Ресурс | Адрес на хосте |
| --- | --- |
| Swagger UI | http://127.0.0.1:8000/docs |
| API | http://127.0.0.1:8000/api/v1 |
| RabbitMQ Management | http://127.0.0.1:15672 |
| PostgreSQL | 127.0.0.1:5433 |
| RabbitMQ AMQP | 127.0.0.1:5672 |

Для входа в RabbitMQ Management используйте пользователя и пароль из Compose, vhost — `payments`.

## Локальный получатель webhook

В проекте есть пример `examples/webhook_receiver.py`. Для запуска на хосте установите uv и выполните в отдельном терминале:

```powershell
uv sync --locked
uv run --no-sync uvicorn examples.webhook_receiver:app --host 0.0.0.0 --port 8001
```

На Docker Desktop для Windows указывайте в платеже:

```text
http://host.docker.internal:8001/hooks/payments
```

Этот адрес позволяет consumer из контейнера обратиться к получателю на хосте. Для Linux без Docker Desktop потребуется отдельно настроить доступ к хосту или использовать другой доступный consumer URL. Не используйте `localhost` для обращения из consumer к получателю на хосте.

## API

Все маршруты платежей требуют заголовок `X-API-Key`. В Swagger UI его можно задать через кнопку **Authorize**.

### Создание платежа

`POST /api/v1/payments` требует непустой заголовок `Idempotency-Key`.

Пример для PowerShell, при запущенном локальном получателе webhook:

```powershell
$apiKey = "local-test-key" # значение API_KEY из .env.docker
$idempotencyKey = [guid]::NewGuid().ToString()
$headers = @{
    "X-API-Key" = $apiKey
    "Idempotency-Key" = $idempotencyKey
}
$body = @{
    amount = "150.50"
    currency = "RUB"
    description = "Test payment"
    metadata = @{ order_id = "order-001" }
    webhook_url = "http://host.docker.internal:8001/hooks/payments"
} | ConvertTo-Json -Depth 5

$payment = Invoke-RestMethod -Method Post `
    -Uri "http://127.0.0.1:8000/api/v1/payments" `
    -Headers $headers -ContentType "application/json" -Body $body
$payment
```

Ответ `202 Accepted` для нового платежа:

```json
{
  "payment_id": "6dec54b4-6cbf-417d-9151-e0cf05595363",
  "status": "pending",
  "created_at": "2026-10-09T14:40:07.383957Z"
}
```

`amount` должен быть больше нуля. Допустимые валюты: `RUB`, `USD`, `EUR`. `description` и `webhook_url` обязательны, `metadata` по умолчанию — пустой объект.

Повтор запроса с тем же ключом и теми же данными возвращает существующий платёж с его текущим статусом, без создания нового события. Повтор с тем же ключом и изменёнными данными возвращает `409 Conflict`. Для нового платежа используйте новый ключ.

### Получение платежа

`GET /api/v1/payments/{payment_id}`:

```powershell
Invoke-RestMethod -Method Get `
    -Uri "http://127.0.0.1:8000/api/v1/payments/$($payment.payment_id)" `
    -Headers @{ "X-API-Key" = $apiKey }
```

Ответ включает `payment_id`, `amount`, `currency`, `status`, `description`, `idempotency_key`, `metadata`, `webhook_url`, `created_at` и `processed_at`. До обработки `processed_at` равен `null`.

| Код | Значение |
| --- | --- |
| 200 | Платёж получен |
| 202 | Запрос создания принят или возвращён существующий платёж |
| 401 | API-ключ отсутствует или неверен |
| 404 | Платёж не найден |
| 409 | Idempotency-Key повторно использован с другими данными |
| 422 | Ошибка валидации, включая отсутствующий Idempotency-Key |

## Webhook, повторы и DLQ

Consumer отправляет JSON:

```json
{
  "payment_id": "6dec54b4-6cbf-417d-9151-e0cf05595363",
  "status": "succeeded"
}
```

Успехом доставки считается ответ `2xx`. Ответ с JSON не обязателен. Для HTTP `5xx`, `429`, ошибки подключения и таймаута предусмотрены максимум 3 попытки с паузами 1 и 2 секунды. HTTP-клиент настроен с таймаутом 3 секунды. Остальные HTTP-ошибки не повторяются.

При необработанной ошибке consumer сообщение отклоняется без возврата в исходную очередь и направляется в DLQ по политике RabbitMQ:

```text
payments.new → payments.dlx → payments.dlq
```

Сбой webhook не меняет уже сохранённый результат платежа. Статус `failed` означает результат имитации оплаты, а не ошибку доставки уведомления. Автоматическая повторная обработка DLQ в проекте не реализована.

## Проверка работы

1. Запустите Compose и пример получателя webhook.
2. Создайте платёж и проверьте ответ `202`.
3. Через несколько секунд запросите платёж: ожидаются конечный статус и заполненный `processed_at`.
4. В терминале получателя проверьте webhook с тем же ID и статусом.
5. Повторите POST с прежним ключом и телом: ID должен остаться прежним. Измените сумму с тем же ключом: ожидается `409`.
6. Для проверки недоступного получателя остановите его и создайте новый платёж с новым ключом. В логах consumer ожидаются 3 попытки, после чего в `payments.dlq` должно появиться сообщение. Конечный статус платежа сохраняется.

Это ручные проверки. Они не заменяют автоматизированный набор тестов.

## Диагностика и остановка

```powershell
docker compose logs --tail 100 api consumer outbox
docker compose logs --tail 100 migrate rabbitmq-ready rabbitmq
docker compose exec rabbitmq rabbitmqctl list_queues -p payments name messages_ready messages_unacknowledged
docker compose stop
```

Данные PostgreSQL и RabbitMQ хранятся в именованных томах. `docker compose down` удаляет контейнеры и сеть, сохраняя тома; добавление `-v` удаляет и данные.

Если проверка готовности завершилась с ошибкой, проверьте адрес Management API, учётные данные и логи импорта definitions. При конфликте порта измените опубликованный порт хоста в Compose; внутренние адреса сервисов сохраняют порты `5432`, `5672` и `15672`.

При локальной разработке не обновляйте зависимости в `.venv`, пока их использует запущенный Python-процесс: Windows может блокировать файлы расширений. После изменения кода пересоберите контейнерный образ командой `docker compose up -d --build`.

## Структура проекта

```text
app/
  api/                     # Маршруты и зависимости FastAPI
  core/                    # Настройки окружения
  db/                      # SQLAlchemy engine, сессии и Base
  models/                  # Модели платежей и outbox
  schemas/                 # Pydantic-схемы
  services/                # Публикация outbox, webhook, readiness
  workers/                 # Consumer и outbox worker
migrations/                # Миграции Alembic
docker/rabbitmq/            # definitions.json
examples/                  # Примеры и локальный получатель webhook
Dockerfile                 # Multi-stage сборка
compose.yaml               # Сервисы и порядок запуска
```

Проект имитирует оплату и не обращается к реальному платёжному провайдеру. Webhook не подписывается; его URL задаётся клиентом. Для публичного развёртывания необходимы отдельные меры защиты исходящих запросов и управление секретами. Проверка топологии выполняется при запуске и не является постоянным мониторингом.
