"""Resolver interface: converts extracted values into real system IDs.

e.g. "Nike" -> brand_ids: [42]
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class Resolver(ABC):
    def __init__(self, entity_key: str, spec: dict[str, Any]) -> None:
        self.entity_key = entity_key
        self.spec = spec
        # Filter key the resolved IDs are written into (e.g. "brand_ids").
        self.target: str = spec.get("target", f"{entity_key}_ids")
        self.cache_ttl_seconds: int | None = spec.get("cache_ttl_seconds")

    @abstractmethod
    async def resolve(self, value: str) -> list[Any]:
        """Resolve a single extracted value into zero or more IDs."""
