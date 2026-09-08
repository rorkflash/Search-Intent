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
    SEARCH_INTENT_PORT=8080 \
    MODEL_CACHE_DIR=/app/models \
    HF_HOME=/app/models

# Bake the GLiNER2 weights into the image (see scripts/prefetch_models.py for
# why a runtime download is not an option here).
COPY scripts/prefetch_models.py ./scripts/
RUN python scripts/prefetch_models.py

# Weights are on disk now; never let a startup path reach out to the Hub.
ENV HF_HUB_OFFLINE=1

EXPOSE 8080

CMD ["uvicorn", "search_intent.main:app", "--host", "0.0.0.0", "--port", "8080"]
