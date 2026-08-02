"""Builds the normalized SearchObject from intent + extracted entities.

Responsibilities:
  - turn entities into filters
  - run resolvers (entity value -> system IDs) and merge results
  - apply sort/pagination defaults from search-object-schema.json
"""

from __future__ import annotations

import re
from typing import Any

from ..cache import CacheManager
from ..models import SearchObject
from ..resolvers import Resolver
from .intent_detector import IntentResult

_NUM_RE = re.compile(r"\d+(?:[.,]\d+)?")
_MIN_WORDS = ("over", "above", "more than", "min", "from", "starting")
_MAX_WORDS = ("under", "below", "less than", "max", "up to", "cheaper")


def parse_price(expressions: list[str]) -> dict[str, float]:
    """Turn price phrases like 'under $100' into {'max': 100.0}."""
    result: dict[str, float] = {}
    for expr in expressions:
        nums = [float(n.replace(",", "")) for n in _NUM_RE.findall(expr)]
        if not nums:
            continue
        lowered = expr.lower()
        if len(nums) >= 2:
            result["min"], result["max"] = min(nums[:2]), max(nums[:2])
        elif any(w in lowered for w in _MIN_WORDS):
            result["min"] = nums[0]
        elif any(w in lowered for w in _MAX_WORDS):
            result["max"] = nums[0]
        else:
            result["max"] = nums[0]
    return result


class SearchObjectBuilder:
    def __init__(
        self,
        search_map: dict[str, Any],
        schema: dict[str, Any],
        resolvers: dict[str, Resolver],
        cache: CacheManager | None = None,
    ) -> None:
        self._search_map = search_map
        self._defaults = schema.get("defaults", {})
        self._resolvers = resolvers
        self._cache = cache

    async def build(
        self,
        *,
        query: str,
        locale: str,
        intent: IntentResult,
        entities: dict[str, list[str]],
        limit: int | None = None,
        offset: int | None = None,
    ) -> SearchObject:
        filters: dict[str, Any] = {}
        resolved: dict[str, Any] = {}

        for label, values in entities.items():
            if label == "price":
                price = parse_price(values)
                if price:
                    filters["price"] = price
                continue

            resolver = self._resolvers.get(label)
            if resolver is not None:
                ids = await self._resolve_all(resolver, values)
                if ids:
                    resolved[resolver.target] = ids
                    filters[resolver.target] = ids
            else:
                filters[label] = values

        return SearchObject(
            query=query,
            locale=locale,
            intent=intent.intent,
            objects=intent.objects,
            entities=entities,
            resolved=resolved,
            filters=filters,
            sort=dict(self._defaults.get("sort", {})),
            pagination=self._build_pagination(limit, offset),
        )

    def _build_pagination(self, limit: int | None, offset: int | None) -> dict[str, Any]:
        pagination = dict(self._defaults.get("pagination", {"limit": 20, "offset": 0}))
        if limit is not None:
            pagination["limit"] = limit
        if offset is not None:
            pagination["offset"] = offset
        return pagination

    async def _resolve_all(self, resolver: Resolver, values: list[str]) -> list[Any]:
        collected: list[Any] = []
        for value in values:
            ids = await self._resolve_cached(resolver, value)
            for i in ids:
                if i not in collected:
                    collected.append(i)
        return collected

    async def _resolve_cached(self, resolver: Resolver, value: str) -> list[Any]:
        if self._cache is None or not self._cache.enabled:
            return await resolver.resolve(value)

        parts = {
            "entity_key": resolver.entity_key,
            "value_hash": self._cache.value_hash(value),
        }
        cached = await self._cache.get("resolved_entity", **parts)
        if cached is not None:
            return cached
        ids = await resolver.resolve(value)
        await self._cache.set("resolved_entity", ids, **parts)
        return ids
