# syntax=docker/dockerfile:1
FROM python:3.12-slim

# Install uv (fast, reproducible installs from uv.lock).
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Install dependencies first for better layer caching.
COPY pyproject.toml uv.lock ./
COPY search_intent ./search_intent
COPY README.md ./
RUN uv sync --frozen --no-dev

COPY config ./config
COPY plugins ./plugins

ENV PATH="/app/.venv/bin:$PATH" \
    SEARCH_INTENT_HOST=0.0.0.0 \
    SEARCH_INTENT_PORT=8080

EXPOSE 8080

CMD ["uvicorn", "search_intent.main:app", "--host", "0.0.0.0", "--port", "8080"]
