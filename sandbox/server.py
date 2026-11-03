"""Local web app for browsing, editing and testing config collections.

Development only: it writes config files over HTTP and skips inbound auth,
so it binds to localhost and is never part of the service image.
"""

from __future__ import annotations

import asyncio
import os
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Literal

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from search_intent.config import ConfigError
from search_intent.models import GenerateResponse, QueryRequest, SearchResponse
from search_intent.settings import get_settings

from .collections import CollectionError, CollectionStore
from .registry import PipelineRegistry

STATIC_DIR = Path(__file__).parent / "static"
DEFAULT_CONFIG_ROOT = Path(__file__).resolve().parent.parent / "config"


class CreateCollection(BaseModel):
    name: str
    copy_from: str | None = None


class FileBody(BaseModel):
    text: str


class RunRequest(QueryRequest):
    mode: Literal["parse", "generate", "search"] = "generate"


class RunResponse(BaseModel):
    mode: str
    elapsed_ms: float
    stages: dict[str, Any] | None = Field(
        None, description="What /v1/parse sees, shown next to generate/search output."
    )
    output: dict[str, Any]


def create_app(config_root: str | Path = DEFAULT_CONFIG_ROOT) -> FastAPI:
    # Http resolvers and api-map *_from_env lookups read os.environ directly.
    load_dotenv()
    settings = get_settings()
    # Same model cache as the service (see search_intent.main), so the sandbox
    # doesn't download a second copy of each model into ~/.cache.
    os.environ.setdefault("HF_HOME", os.path.abspath(settings.model_cache_dir))
    store = CollectionStore(config_root)
    registry = PipelineRegistry(store, settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        try:
            yield
        finally:
            await registry.close()

    app = FastAPI(title="Search Intent Sandbox", lifespan=lifespan, docs_url=None, redoc_url=None)

    @app.exception_handler(CollectionError)
    async def collection_error(_request: Request, exc: CollectionError) -> JSONResponse:
        return JSONResponse({"detail": str(exc)}, status_code=exc.status_code)

    def details(name: str) -> dict[str, Any]:
        return {**store.summary(name), "validation": store.validate(name)}

    # --- collections -----------------------------------------------------
    @app.get("/api/collections")
    async def list_collections() -> list[dict[str, Any]]:
        return [details(name) for name in store.names()]

    @app.post("/api/collections", status_code=201)
    async def create_collection(body: CreateCollection) -> dict[str, Any]:
        store.create(body.name, body.copy_from)
        return details(body.name)

    @app.get("/api/collections/{name}")
    async def get_collection(name: str) -> dict[str, Any]:
        return details(name)

    @app.delete("/api/collections/{name}", status_code=204)
    async def delete_collection(name: str) -> None:
        store.delete(name)
        await registry.invalidate(name)

    # --- files -----------------------------------------------------------
    @app.get("/api/collections/{name}/files/{stem}")
    async def read_file(name: str, stem: str) -> dict[str, str]:
        return {"stem": stem, "text": store.read_file(name, stem)}

    @app.put("/api/collections/{name}/files/{stem}")
    async def write_file(name: str, stem: str, body: FileBody) -> dict[str, Any]:
        store.write_file(name, stem, body.text)
        await registry.invalidate(name)
        return details(name)

    @app.delete("/api/collections/{name}/files/{stem}")
    async def delete_file(name: str, stem: str) -> dict[str, Any]:
        store.delete_file(name, stem)
        await registry.invalidate(name)
        return details(name)

    # --- run a query -----------------------------------------------------
    @app.post("/api/collections/{name}/run", response_model=RunResponse)
    async def run(name: str, body: RunRequest) -> RunResponse:
        store.summary(name)  # 404 for an unknown collection
        started = time.perf_counter()
        try:
            pipeline = await registry.get(name)
            parsed = await asyncio.to_thread(pipeline.parse, body.query, body.locale)
            stages: dict[str, Any] | None = parsed.model_dump()
            args = (body.query, body.locale, body.limit, body.offset, body.user_location)

            if body.mode == "parse":
                output, stages = stages, None
            elif body.mode == "generate":
                search_object, request, hit = await pipeline.generate(*args)
                output = GenerateResponse(
                    query=search_object.query,
                    locale=search_object.locale,
                    intent=search_object.intent,
                    search_object=search_object,
                    api_request=request,
                    cache={"hit": hit},
                ).model_dump()
            else:
                search_object, request, api_response, hit = await pipeline.search(*args)
                output = SearchResponse(
                    query=search_object.query,
                    locale=search_object.locale,
                    intent=search_object.intent,
                    search_object=search_object,
                    api_request=request,
                    api_response=api_response,
                    cache={"hit": hit},
                ).model_dump()
        except (ConfigError, FileNotFoundError, ValueError) as exc:
            raise HTTPException(422, f"Config problem: {exc}") from exc
        except httpx.HTTPError as exc:
            raise HTTPException(502, f"Target API error: {exc}") from exc
        except Exception as exc:  # surface template/resolver bugs to the tester
            raise HTTPException(500, f"{type(exc).__name__}: {exc}") from exc

        return RunResponse(
            mode=body.mode,
            elapsed_ms=round((time.perf_counter() - started) * 1000, 1),
            stages=stages,
            output=output,
        )

    app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
    return app
