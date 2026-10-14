import asyncio
from decimal import Decimal

from sqlalchemy.exc import IntegrityError

from app.db.session import Session, engine
from app.models.payment import Payment


async def create_payment():
    try:
        async with Session() as session:
            async with session.begin():
                payment = Payment(
                    amount=Decimal("1499.90"),
                    currency='USD',
                    description="Оплата за услуги",
                    webhook_url="https://example.com",
                    idempotency_key="orm-demo-002"
                )

                session.add(payment)
                await session.flush()
            print(
                "Объект успешно сохранён: ",
                "ID", payment.id,
                "Status", payment.status,
                "Date", payment.created_at,
            )
    except IntegrityError as exc:
            print("Нарушено ограничение базы:", exc.orig)
    finally:
        await engine.dispose()



asyncio.run(create_payment())
