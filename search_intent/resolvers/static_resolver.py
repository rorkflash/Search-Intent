"""Static resolver: looks values up in an in-config mapping.

Useful for small, fixed vocabularies and for local development without a
backend resolver service. Example spec:

    {
      "type": "static",
      "target": "brand_ids",
      "map": {"nike": 42, "apple": 7}
    }
"""

from __future__ import annotations

from typing import Any

from .base import Resolver


class StaticResolver(Resolver):
    def __init__(self, entity_key: str, spec: dict[str, Any]) -> None:
        super().__init__(entity_key, spec)
        # Normalize keys to lowercase for case-insensitive lookup.
        self._map = {str(k).lower(): v for k, v in spec.get("map", {}).items()}

    async def resolve(self, value: str) -> list[Any]:
        result = self._map.get(value.strip().lower())
        if result is None:
            return []
        return result if isinstance(result, list) else [result]
