"""Модуль Webhook.

Пример простого webhook-эндпоинта для приёма уведомлений о статусах платежей.
"""

from http import HTTPStatus
from fastapi import FastAPI
from pydantic import BaseModel, Field


class PaymentNotification(BaseModel):
    """Схема уведомления о статусе платежа.

    Attributes:
        payment_id: Идентификатор платежа (обязательное поле, минимальная длина 1).
        status: Новый статус платежа (обязательное поле, минимальная длина 1).
    """
    payment_id: str = Field(..., min_length=1)
    status: str = Field(..., min_length=1)

app = FastAPI()


@app.post("/hooks/payments", status_code=HTTPStatus.OK)
async def receive_notification(notification: PaymentNotification):
    """Принять уведомление о статусе платежа.

    Эндпоинт для получения webhook-уведомлений от внешних платёжных систем.

    Args:
        notification: Тело запроса в формате ``PaymentNotification``.

    Returns:
        Подтверждение получения уведомления.
    """
    print("Уведомление об оплате:", notification)
    return {"received": True}