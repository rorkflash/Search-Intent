"""One Pipeline per collection, built on first use and rebuilt after any edit.

Edits made outside the sandbox (an editor, an agent, `git checkout`) count
too: a collection is rebuilt whenever its files' mtimes or sizes change.
"""

from __future__ import annotations

import asyncio
from dataclasses import replace
from pathlib import Path

from search_intent.config import load_config, validate_config
from search_intent.core import Pipeline
from search_intent.settings import Settings

from .collections import CollectionStore


def _without_cache(cache_config: dict) -> dict:
    # A cached search object would hide the edit you just made, and the cache
    # key (locale + query) knows nothing about the config that produced it.
    return {**cache_config, "cache": {**cache_config.get("cache", {}), "enabled": False}}


def _signature(folder: Path) -> tuple:
    return tuple(
        (p.name, p.stat().st_mtime_ns, p.stat().st_size) for p in sorted(folder.glob("*.json"))
    )


class PipelineRegistry:
    def __init__(self, store: CollectionStore, settings: Settings) -> None:
        self.store = store
        self.settings = settings
        self._pipelines: dict[str, tuple[tuple, Pipeline]] = {}
        self._lock = asyncio.Lock()

    def _build(self, name: str) -> Pipeline:
        config = load_config(self.store.root / name)
        validate_config(config)
        config = replace(config, cache=_without_cache(config.cache))
        return Pipeline(config, self.settings)

    async def get(self, name: str) -> Pipeline:
        signature = _signature(self.store.root / name)
        async with self._lock:
            entry = self._pipelines.get(name)
            if entry is not None and entry[0] == signature:
                return entry[1]
            if entry is not None:
                await entry[1].close()
            # Loading a GLiNER2 model blocks for seconds; keep the loop free.
            pipeline = await asyncio.to_thread(self._build, name)
            self._pipelines[name] = (signature, pipeline)
            return pipeline

    async def invalidate(self, name: str) -> None:
        async with self._lock:
            entry = self._pipelines.pop(name, None)
        if entry is not None:
            await entry[1].close()

    async def close(self) -> None:
        for name in list(self._pipelines):
            await self.invalidate(name)
