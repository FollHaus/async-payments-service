"""Модуль зависимостей FastAPI.

Определяет зависимости для аутентификации через API-ключ
и управления сессиями базы данных SQLAlchemy.
"""

from collections.abc import AsyncIterator
from http import HTTPStatus
from typing import Annotated
from fastapi import HTTPException, Depends
from fastapi.security import APIKeyHeader
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import Session

# Зависимость FastAPI для извлечения API-ключа из заголовка HTTP-запроса.
# Ожидается заголовок «X-API-Key». Auto_error=False позволяет вручную
# обрабатывать отсутствие заголовка в точке проверки.
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def verify_api_key(
    api_key: Annotated[str | None, Depends(api_key_header)]
) -> None:
    """Валидирует переданный API-ключ.

    Извлекает значение заголовка ``X-API-Key`` из текущего HTTP-запроса
    и сравнивает его со значением, настроенным в ``settings.api_key``.

    Args:
        api_key: Значение заголовка ``X-API-Key``. Может быть ``None``,
            если заголовок отсутствует в запросе.

    Raises:
        HTTPException: Статус ``401 Unauthorized``, если заголовок
            отсутствует или его значение не совпадает с конфигурационным
            API-ключом.
    """
    if api_key is None or api_key != settings.api_key:
        raise HTTPException(
            status_code=HTTPStatus.UNAUTHORIZED,
            detail="Не верный API key",
        )


async def get_session() -> AsyncIterator[AsyncSession]:
    """Создать и предоставить асинхронную сессию SQLAlchemy.

    Является генератором-асинхронной зависимостью FastAPI. Создаёт новую
    сессию ``AsyncSession`` при входе в блок зависимостии корректно
    завершает её (коммитит/откатывает и закрывает) при выходе.

    Yields:
        Готовую к использованию асинхронную сессию базы данных
        ``AsyncSession``.
    """
    async with Session() as session:
        yield session