"""Cache backend interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class CacheBackend(ABC):
    """Async key/value cache with TTL support."""

    @abstractmethod
    async def get(self, key: str) -> Any | None: ...

    @abstractmethod
    async def set(self, key: str, value: Any, ttl_seconds: int | None = None) -> None: ...

    @abstractmethod
    async def delete(self, key: str) -> None: ...

    async def close(self) -> None:  # pragma: no cover - optional override
        return None
