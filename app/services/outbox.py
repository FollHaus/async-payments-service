from datetime import datetime, UTC

from sqlalchemy import select

from app.db.session import Session
from app.models.outbox import OutboxEvent
from faststream.rabbit import RabbitBroker


async def publish_next_event(broker: RabbitBroker, queue: str) -> bool:
    """Опубликовать следующее неопубликованное событие из Outbox в RabbitMQ.

    Атомарно выбирает первое неподтверждённое событие (``published_at IS NULL``)
    из таблицы ``OutboxEvent``, сортируя по времени создания, и публикует его
    в указанную очередь RabbitMQ. После успешной публикации отмечает событие
    как опубликованное, устанавливая ``published_at``.

    Использует ``FOR UPDATE SKIP LOCKED`` для безопасной конкурентной
    обработки несколькими воркерами без блокировок.

    Args:
        broker: Экземпляр ``RabbitBroker`` для публикации сообщений.
        queue: Имя очереди RabbitMQ, в которую будет отправлено событие.

    Returns:
        ``True``, если событие было успешно выбрано, опубликовано
        и помечено как опубликованное. ``False``, если неподтверждённых
        событий в Outbox не осталось.
    """
    async with Session() as session:
        async with session.begin():
            outbox_event = await session.execute(
                select(OutboxEvent).with_for_update(skip_locked=True)
                .where(OutboxEvent.published_at.is_(None))
                .order_by(OutboxEvent.created_at)
                .limit(1)
            )
            event = outbox_event.scalar_one_or_none()

            if event is None:
                return False

            await broker.publish(
                message=event.payload,
                queue=queue,
                persist=True,
                message_id=str(event.id),
                timeout=5.0,
            )
            event.published_at = datetime.now(UTC)
    return True