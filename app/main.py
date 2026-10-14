from contextlib import asynccontextmanager

from fastapi import FastAPI
from app.api import payments
from app.db.session import engine

PREFIX_V1 = "/api/v1"

@asynccontextmanager
async def lifespan(app: FastAPI):
    try:

        yield

    finally:
        await engine.dispose()


app = FastAPI(lifespan=lifespan)

app.include_router(payments.router, prefix=PREFIX_V1)
