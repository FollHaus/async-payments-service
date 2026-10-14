"""Роутеры для работы с платежами (Payments).

Определяет API-эндпоинты для создания и получения платёжных операций,
включая идемпотентное создание через заголовок ``Idempotency-Key``
и обработку конфликтов дублирующихся запросов.
"""

import json
from uuid import UUID
from http import HTTPStatus
from typing import Annotated

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import APIRouter, Header, Depends, HTTPException

from app.models.payment import Payment
from app.models.outbox import OutboxEvent
from app.api.dependencies import get_session, verify_api_key
from app.schemas.payments import PaymentCreate, PaymentAccepted, PaymentDetails

router = APIRouter(
    prefix="/payments",
    tags=["Payments"],
    dependencies=[Depends(verify_api_key)],
)


def find_payment_mismatches(
    db_payment: Payment,
    payment: PaymentCreate,
) -> list[str]:
    """Найти расхождения между сохранённым и входящим платежами.

    Сравнивает ключевые поля существующей записи ``Payment`` в БД
    с данными из входящего запроса ``PaymentCreate``. Используется
    для определения причин конфликта при повторном запросе с тем же
    ``idempotency_key``.

    Args:
        db_payment: Объект платежа, загруженный из базы данных.
        payment: Схема входящего запроса на создание платежа.

    Returns:
        Список имён полей, значения которых не совпадают между
        записью в БД и входящим запросом. Пустой список означает
        полное совпадение.
    """
    # Сравниваем поля для проверки дубликата
    matches = {
        "amount": db_payment.amount == payment.amount,
        "currency": db_payment.currency == payment.currency,
        "description": db_payment.description == payment.description,
        "metadata": json.dumps(db_payment.metadata_, sort_keys=True) == json.dumps(payment.metadata, sort_keys=True),
        "webhook_url": str(db_payment.webhook_url) == str(payment.webhook_url),
    }

    return [k for k, v in matches.items() if not v]


@router.post("", status_code=HTTPStatus.ACCEPTED, response_model=PaymentAccepted)
async def payments_create(
    payment: PaymentCreate,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=1)],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    """Создать новый платёж с поддержкой идемпотентности.

    Создаёт запись ``Payment`` и соответствующее событие ``OutboxEvent``
    типа ``payment.created``. Если запрос с тем же ``idempotency_key``
    уже был обработан, возвращает результат предыдущего создания без
    повторного выполнения.

    Если повторный запрос содержит иные данные (сумма, валюта, описание
    и т.д.), возвращается ошибка ``409 Conflict`` с перечнем расходящихся
    полей.

    Args:
        payment: Схема данных создаваемого платежа.
        idempotency_key: Уникальный ключ идемпотентности из заголовка
            ``Idempotency-Key``. Гарантирует, что повторный запрос
            с тем же ключом не приведёт к двойному списанию.
        session: Асинхронная сессия SQLAlchemy.

    Returns:
        Схема ``PaymentAccepted`` с идентификатором платежа,
        статусом и датой создания.

    Raises:
        HTTPException: ``409 Conflict``, если повторный запрос
            с тем же ``idempotency_key`` содержит другие данные.
        HTTPException: ``409 Conflict`` (внутренне), если возникает
            ошибка ``IntegrityError`` с SQLSTATE ``23505`` для
            ограничения уникальности ``idempotency_key``.
    """
    try:
        async with session.begin():
            result = await session.execute(
                select(Payment).where(Payment.idempotency_key == idempotency_key))
            db_payment = result.scalar_one_or_none()

            if db_payment is None:
                db_payment = Payment(
                    amount=payment.amount,
                    currency=payment.currency,
                    description=payment.description,
                    metadata_=payment.metadata,
                    webhook_url=str(payment.webhook_url),
                    idempotency_key=idempotency_key,
                )
                session.add(db_payment)
                await session.flush()

                event = OutboxEvent(
                    event_type="payment.created",
                    payload={"payment_id": str(db_payment.id)}
                )

                session.add(event)

    except IntegrityError as exc:
        driver_error = exc.orig.__cause__
        sqlstate = getattr(driver_error, "sqlstate", None)
        constraint = getattr(driver_error, "constraint_name", None)

        if sqlstate == "23505" and constraint == "payments_idempotency_key_key":
            # Обрабатываем ошибку уникальности
            async with session.begin():
                result = await session.execute(
                    select(Payment).where(Payment.idempotency_key == idempotency_key))
                db_payment = result.scalar_one_or_none()

                if db_payment is None:
                    raise
        else:
            raise

    diff = find_payment_mismatches(db_payment, payment)

    if diff:
        raise HTTPException(
            status_code=HTTPStatus.CONFLICT,
            detail=f"Дубликат idempotency key с разными данными.\n"
                   f"Расхождение в: {', '.join(diff)}",
        )

    return PaymentAccepted(
        payment_id=db_payment.id,
        status=db_payment.status,
        created_at=db_payment.created_at,
    )


@router.get("/{payment_id}", response_model=PaymentDetails, status_code=HTTPStatus.OK)
async def get_payment_by_id(
    payment_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
):
    """Получить платёж по его уникальному идентификатору.

    Args:
        payment_id: UUID создаваемого платежа.
        session: Асинхронная сессия SQLAlchemy.

    Returns:
        Схема ``PaymentDetails`` с полной информацией о платеже.

    Raises:
        HTTPException: ``404 Not Found``, если платёж с указанным
            идентификатором не найден в базе данных.
    """
    result = await session.get(Payment, payment_id)
    if result is None:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="Платёж не найден")
    return PaymentDetails.model_validate(result)