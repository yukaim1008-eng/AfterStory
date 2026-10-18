FROM python:3.13-slim

COPY --from=ghcr.io/astral-sh/uv:0.11.20 /uv /uvx /usr/local/bin/

ENV UV_PYTHON_DOWNLOADS=never \
    UV_LINK_MODE=copy \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:${PATH}"

WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-install-project --no-cache

COPY afterstory/ ./afterstory/
COPY migrations/ ./migrations/
COPY alembic.ini ./
COPY fixtures/ ./fixtures/

USER 10001:10001
EXPOSE 8000
CMD ["uvicorn", "afterstory.api:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]