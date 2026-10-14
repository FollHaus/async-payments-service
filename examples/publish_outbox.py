import asyncio
from faststream.rabbit import RabbitBroker, Channel, RabbitQueue
from app.core.config import settings
from app.db.session import engine
from app.services.outbox import publish_next_event
from aio_pika.exceptions import ChannelInvalidStateError


async def publish_outbox():
    default_channel = Channel(
        publisher_confirms=True, on_return_raises=True
    )
    broker = RabbitBroker(
        settings.rabbitmq_url,
        default_channel=default_channel,
    )

    try:
        await broker.connect()
        await broker.declare_queue(RabbitQueue("payments.new", durable=True))
        while True:
            try:
                is_published = await publish_next_event(broker, "payments.new")
                if is_published:
                    print("Событие опубликовано и отмечено в БД")
                else:
                    print("Нет подходящих событий")
                    await asyncio.sleep(1)
            except (ConnectionError, TimeoutError, ChannelInvalidStateError) as exc:
                print(type(exc).__name__, exc)
                await asyncio.sleep(1)
    except Exception as e:
        print("Произошла ошибка чтения, публикации или сохранения", e)
        raise
    finally:
        try:
            await broker.stop()
        except Exception as e:
            print("Не удалось плавно остановить брокер:", e)
        finally:
            await engine.dispose()


asyncio.run(publish_outbox())
