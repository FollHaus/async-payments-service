import asyncio
from uuid import UUID
from app.db.session import Session, engine
from app.models.payment import Payment


async def read_payment(payment_id: UUID):
    try:
        async with Session() as session:
            async with session.begin():
                payment = await session.get(Payment, payment_id)
                if payment:
                    print(vars(payment))
                else:
                    print("Payment not found")
    finally:
        await engine.dispose()

save = UUID("1139cb8e-89e7-414f-80b5-37bc9951d2ff")
asyncio.run(read_payment(save))
