import asyncio

from faststream.rabbit import RabbitBroker,RabbitQueue

from app.core.config import settings


async def test_broker():
    broker = RabbitBroker(settings.rabbitmq_url)
    try:
        await broker.connect()
        await broker.declare_queue(RabbitQueue("payments.new", durable=True))
        print("Очередь объявлена")
    finally:
        await broker.stop()

asyncio.run(test_broker())