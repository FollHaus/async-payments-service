from datetime import datetime, UTC
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import Numeric, String, Uuid, Text, DateTime, CheckConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Payment(Base):
    """Модель платежа для базы"""
    __tablename__ = "payments"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    amount: Mapped[Decimal] = mapped_column(Numeric(), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="pending", nullable=False)
    description: Mapped[str] = mapped_column(Text(), nullable=False)
    metadata_: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB(), nullable=False, default=dict)
    webhook_url: Mapped[str] = mapped_column(Text(), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(), nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False,
                                                 default=lambda: datetime.now(UTC))
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, default=None)

    __table_args__ = (
        # Ограничения на уровне БД
        CheckConstraint("amount > 0", name="ck_payments_amount_positive"),
        CheckConstraint("currency IN ('RUB', 'USD', 'EUR')", name="ck_payments_currency"),
        CheckConstraint("status IN ('pending', 'succeeded', 'failed')", name="ck_payments_status"),
    )
