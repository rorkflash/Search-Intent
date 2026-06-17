"""Cache manager: builds the backend from cache.json and computes cache keys."""

from __future__ import annotations

import hashlib
from typing import Any

from .base import CacheBackend
from .memory_cache import MemoryCache


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


class CacheManager:
    """Wraps a CacheBackend and resolves config-driven key patterns."""

    def __init__(self, cache_config: dict[str, Any], redis_url: str | None = None) -> None:
        cfg = cache_config.get("cache", {})
        self.enabled: bool = bool(cfg.get("enabled", False))
        self.namespace: str = cfg.get("namespace", "search-intent")
        self.project_version: str = cfg.get("project_version", {}).get("value", "v1")
        self._keys: dict[str, Any] = cfg.get("keys", {})

        backend = cfg.get("backend", "memory")
        if self.enabled and backend == "redis" and redis_url:
            from .redis_cache import RedisCache

            self.backend: CacheBackend = RedisCache(redis_url)
        else:
            # Fall back to memory if redis was requested but unavailable.
            self.backend = MemoryCache()

    def key(self, kind: str, **parts: str) -> str | None:
        """Render the key pattern for ``kind`` from cache.json, or None."""
        spec = self._keys.get(kind)
        if not spec:
            return None
        pattern = spec["pattern"]
        values = {
            "namespace": self.namespace,
            "project_version": self.project_version,
            **parts,
        }
        return pattern.format(**values)

    def ttl(self, kind: str) -> int | None:
        spec = self._keys.get(kind)
        return spec.get("ttl_seconds") if spec else None

    @staticmethod
    def query_hash(query: str) -> str:
        return _hash(query.strip().lower())

    @staticmethod
    def value_hash(value: str) -> str:
        return _hash(value.strip().lower())

    async def get(self, kind: str, **parts: str) -> Any | None:
        if not self.enabled:
            return None
        key = self.key(kind, **parts)
        if key is None:
            return None
        return await self.backend.get(key)

    async def set(self, kind: str, value: Any, **parts: str) -> None:
        if not self.enabled:
            return
        key = self.key(kind, **parts)
        if key is None:
            return
        await self.backend.set(key, value, self.ttl(kind))

    async def close(self) -> None:
        await self.backend.close()
