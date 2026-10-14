"""Модуль Webhook"""
import asyncio
from http import HTTPStatus
from fastapi import FastAPI
from pydantic import BaseModel, Field


class PaymentNotification(BaseModel):
    payment_id: str = Field(..., min_length=1)
    status: str = Field(..., min_length=1)

app = FastAPI()


@app.post("/hooks/payments", status_code=HTTPStatus.OK)
async def receive_notification(notification: PaymentNotification):
    print("Уведомление об оплате:", notification)
    return {"received": True}