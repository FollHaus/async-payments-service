"""Pydantic схемы платежей"""

from datetime import datetime
from typing import Literal, Any
from uuid import UUID

from pydantic import BaseModel, Field, HttpUrl
from decimal import Decimal


class PaymentCreate(BaseModel):
    """Схема создания платежа"""
    amount: Decimal = Field(gt=0)

    currency: Literal["EUR", "USD", "RUB"]

    description: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    webhook_url: HttpUrl


class PaymentAccepted(BaseModel):
    """Схема ответа сервера"""
    payment_id: UUID
    status: str = "pending"
    created_at: datetime


class PaymentDetails(BaseModel):
    """Полная информация о платеже"""
    payment_id: UUID = Field(validation_alias="id")
    amount: Decimal
    currency: Literal["RUB", "USD", "EUR"]
    status: Literal["pending", "succeeded", "failed"]
    description: str
    idempotency_key: str
    metadata: dict[str, Any] = Field(validation_alias="metadata_", default_factory=dict)
    webhook_url: HttpUrl
    created_at: datetime
    processed_at: datetime | None = None

    model_config = {"from_attributes": True}
