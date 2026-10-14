import asyncio
from uuid import UUID

import httpx

from app.db.session import Session, engine
from app.models.payment import Payment
from app.services.webhooks import send_webhook
from app.workers.consumer import StatusEnum


async def main():
    payment_id: UUID = UUID("13b34aac-5a5e-4268-89b5-ab8f483ad0e9")
    try:
        async with Session() as session:
            db_payment = await session.get(Payment, payment_id)

            if db_payment and (db_payment.status != StatusEnum.PENDING):
                payload = {
                    "payment_id": str(db_payment.id),
                    "status": db_payment.status,
                }
                webhook_url = db_payment.webhook_url
            else:
                return

        async with httpx.AsyncClient(timeout=3.0, trust_env=False) as client:
            await send_webhook(client=client, payload=payload, url=webhook_url)
            print(f"Webhook доставлен")

    finally:
        await engine.dispose()


asyncio.run(main())
