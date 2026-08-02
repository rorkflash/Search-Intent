"""Redis-backed cache. Values are JSON-encoded."""

from __future__ import annotations

import json
from typing import Any

import redis.asyncio as redis

from .base import CacheBackend


class RedisCache(CacheBackend):
    def __init__(self, url: str) -> None:
        self._client = redis.from_url(url, decode_responses=True)

    async def get(self, key: str) -> Any | None:
        raw = await self._client.get(key)
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except (TypeError, ValueError):
            return raw

    async def set(self, key: str, value: Any, ttl_seconds: int | None = None) -> None:
        raw = json.dumps(value)
        if ttl_seconds:
            await self._client.set(key, raw, ex=ttl_seconds)
        else:
            await self._client.set(key, raw)

    async def delete(self, key: str) -> None:
        await self._client.delete(key)

    async def close(self) -> None:
        await self._client.aclose()
