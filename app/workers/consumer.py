import asyncio
from datetime import datetime, UTC
from enum import Enum
from random import randint, random

import httpx
from faststream import FastStream, Context, ContextRepo
from typing import Annotated
from faststream.rabbit import RabbitBroker, RabbitQueue

from app.core.config import settings
from app.db.session import Session, engine
from app.models.payment import Payment
from app.schemas.events import PaymentCreatedEvent
from app.services.webhooks import send_webhook

broker = RabbitBroker(settings.rabbitmq_url)

app = FastStream(broker)


class StatusEnum(str, Enum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    PENDING = "pending"


@broker.subscriber(RabbitQueue("payments.new", durable=True))
async def handle_payment_created(
        event: PaymentCreatedEvent,
        client: Annotated[httpx.AsyncClient, Context("http_client")]
):
    async with Session() as session:
        async with session.begin():
            db_payment = await session.get(Payment, event.payment_id, with_for_update=True)

            if db_payment is None:
                raise ValueError(f"[Ошибка] Платеж ID: {event.payment_id} не найден")

            if db_payment.status == StatusEnum.PENDING:
                delay = randint(2, 5)
                await asyncio.sleep(delay)  # имитация обработки
                db_payment.processed_at = datetime.now(UTC)
                db_payment.status = StatusEnum.SUCCEEDED if random() < 0.9 else StatusEnum.FAILED

        payload = {
            "payment_id": str(db_payment.id),
            "status": db_payment.status
        }
        webhook_url = db_payment.webhook_url

        print(f"\nОбработка завершена: {db_payment.id}")
        print(f"Status: {db_payment.status}")
        print(f"Processed_at: {db_payment.processed_at}\n")

    await send_webhook(client, webhook_url, payload)
    print("Webhook отправлен\n")


@app.on_startup
async def on_startup_hook(context: ContextRepo):
    client = httpx.AsyncClient(timeout=3.0, trust_env=False)
    context.set_global("http_client", client)


@app.after_shutdown
async def after_shutdown_hook(client: Annotated[httpx.AsyncClient, Context("http_client")]):
    try:
        await client.aclose()
    finally:
        await engine.dispose()
