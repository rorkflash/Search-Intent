"""One Pipeline per collection, built on first use and dropped on every edit."""

from __future__ import annotations

import asyncio
from dataclasses import replace

from search_intent.config import load_config, validate_config
from search_intent.core import Pipeline
from search_intent.settings import Settings

from .collections import CollectionStore


def _without_cache(cache_config: dict) -> dict:
    # A cached search object would hide the edit you just made, and the cache
    # key (locale + query) knows nothing about the config that produced it.
    return {**cache_config, "cache": {**cache_config.get("cache", {}), "enabled": False}}


class PipelineRegistry:
    def __init__(self, store: CollectionStore, settings: Settings) -> None:
        self.store = store
        self.settings = settings
        self._pipelines: dict[str, Pipeline] = {}
        self._lock = asyncio.Lock()

    def _build(self, name: str) -> Pipeline:
        config = load_config(self.store.root / name)
        validate_config(config)
        config = replace(config, cache=_without_cache(config.cache))
        return Pipeline(config, self.settings)

    async def get(self, name: str) -> Pipeline:
        async with self._lock:
            pipeline = self._pipelines.get(name)
            if pipeline is None:
                # Loading a GLiNER2 model blocks for seconds; keep the loop free.
                pipeline = await asyncio.to_thread(self._build, name)
                self._pipelines[name] = pipeline
            return pipeline

    async def invalidate(self, name: str) -> None:
        async with self._lock:
            pipeline = self._pipelines.pop(name, None)
        if pipeline is not None:
            await pipeline.close()

    async def close(self) -> None:
        for name in list(self._pipelines):
            await self.invalidate(name)
