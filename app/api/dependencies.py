"""Модуль зависимостей"""
from collections.abc import AsyncIterator
from http import HTTPStatus
from typing import Annotated
from fastapi import HTTPException, Depends
from fastapi.security import APIKeyHeader
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import  Session

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def verify_api_key(api_key: Annotated[str | None, Depends(api_key_header)]):
    """ Проверяем API ключ """
    if api_key is None or api_key != settings.api_key:
        raise HTTPException(status_code=HTTPStatus.UNAUTHORIZED, detail="Не верный API key")


async def get_session() -> AsyncIterator[AsyncSession]:
    """ Получаем сессию """
    async with Session() as session:
        yield session