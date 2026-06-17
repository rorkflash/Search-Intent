"""FastAPI application entrypoint.

Loads the active project config at startup, builds the pipeline, and wires up
inbound auth. Run with:  uvicorn search_intent.main:app
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from .api import routes_generate, routes_health, routes_parse, routes_search
from .api.docs import configure_dark_mode_docs
from .auth import AuthGuard, build_authenticator
from .config import load_config, validate_config
from .core import Pipeline
from .settings import get_settings

logger = logging.getLogger("search_intent")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    config = load_config(settings.config_dir)

    warnings = validate_config(config)
    for warning in warnings:
        logger.warning("config: %s", warning)

    authenticator = build_authenticator(config, settings)

    app.state.settings = settings
    app.state.config = config
    app.state.project_name = config.name
    app.state.pipeline = Pipeline(config, settings)
    app.state.auth_guard = AuthGuard(authenticator, config)

    logger.info(
        "Search Intent ready: project=%s extractor=%s api_mode=%s auth=%s",
        config.name,
        config.extractor.get("extractor", {}).get("provider"),
        app.state.pipeline.mapper.mode,
        "on" if authenticator else "off",
    )
    try:
        yield
    finally:
        await app.state.pipeline.close()


def create_app() -> FastAPI:
    app = FastAPI(
        title="Search Intent",
        description="Convert natural-language search queries into structured API requests.",
        version="0.1.0",
        lifespan=lifespan,
        docs_url=None,  # replaced by the system-theme-aware docs below
    )
    configure_dark_mode_docs(app)
    app.include_router(routes_health.router)
    app.include_router(routes_parse.router)
    app.include_router(routes_generate.router)
    app.include_router(routes_search.router)
    return app


app = create_app()
