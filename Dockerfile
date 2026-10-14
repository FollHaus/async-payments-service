FROM python:3.12-slim-trixie AS builder

COPY --from=ghcr.io/astral-sh/uv:0.13.0 /uv /bin/uv

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-install-project


FROM python:3.12-slim-trixie AS runtime

COPY --from=builder /app/.venv /app/.venv

WORKDIR /app

COPY app ./app
COPY migrations  /app/migrations
COPY alembic.ini  /app/alembic.ini
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

ENV PATH="/app/.venv/bin:$PATH"
