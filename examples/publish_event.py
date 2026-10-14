import asyncio

from faststream.rabbit import RabbitBroker, RabbitQueue
from app.core.config import settings


async def test_publish_event():
    broker = RabbitBroker(settings.rabbitmq_url)
    try:
        await broker.connect()
        await broker.declare_queue(RabbitQueue("payments.new", durable=True))
        await broker.publish(
            message={"payment_id": "31aacd98-2004-4efb-b521-aa784b4a7cdc"},
            queue=RabbitQueue("payments.new", durable=True),
            persist=True,
        )
        print("Сообщение отправлено")
    finally:
        await broker.stop()


asyncio.run(test_publish_event())
