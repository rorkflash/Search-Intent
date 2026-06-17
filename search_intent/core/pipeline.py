"""The end-to-end pipeline wiring config -> extractor -> builder -> mapper.

A single Pipeline instance is built once at startup from the active project
config and reused across requests.
"""

from __future__ import annotations

from typing import Any

from ..cache import CacheManager
from ..config import ProjectConfig
from ..extractors import build_extractor
from ..mappers import ApiExecutor, ApiMapper
from ..models import ApiRequest, ParseResponse, SearchObject
from ..resolvers import build_resolvers
from ..settings import Settings
from .intent_detector import IntentDetector
from .normalizer import normalize
from .search_object_builder import SearchObjectBuilder


class Pipeline:
    def __init__(self, config: ProjectConfig, settings: Settings) -> None:
        self.config = config
        self.settings = settings

        self.cache = CacheManager(config.cache, redis_url=settings.redis_url)
        self.extractor = build_extractor(config.extractor)
        self.intent_detector = IntentDetector(config.intent_map)
        self.resolvers = build_resolvers(config.resolver_map)
        self.builder = SearchObjectBuilder(
            search_map=config.search_map,
            schema=config.search_object_schema,
            resolvers=self.resolvers,
            cache=self.cache,
        )
        self.mapper = ApiMapper(config.api_map)
        self.executor = ApiExecutor()

    # --- /v1/parse -------------------------------------------------------
    def parse(self, query: str, locale: str) -> ParseResponse:
        normalized = normalize(query)
        intent = self.intent_detector.detect(normalized)
        extraction = self.extractor.extract(normalized, locale)
        return ParseResponse(
            query=normalized,
            locale=locale,
            intent=intent.intent,
            objects=intent.objects,
            entities=extraction.entities,
            confidence={
                "intent": intent.confidence,
                "entities": round(extraction.confidence, 2),
            },
        )

    # --- shared: build the SearchObject ----------------------------------
    async def build_search_object(
        self, query: str, locale: str, limit: int | None, offset: int | None
    ) -> tuple[SearchObject, bool]:
        normalized = normalize(query)
        cache_parts = {"locale": locale, "query_hash": self.cache.query_hash(normalized)}

        cached = await self.cache.get("search_object", **cache_parts)
        if cached is not None:
            return SearchObject.model_validate(cached), True

        intent = self.intent_detector.detect(normalized)
        extraction = self.extractor.extract(normalized, locale)
        search_object = await self.builder.build(
            query=normalized,
            locale=locale,
            intent=intent,
            entities=extraction.entities,
            limit=limit,
            offset=offset,
        )
        await self.cache.set("search_object", search_object.model_dump(), **cache_parts)
        return search_object, False

    # --- /v1/generate ----------------------------------------------------
    async def generate(
        self, query: str, locale: str, limit: int | None, offset: int | None
    ) -> tuple[SearchObject, ApiRequest, bool]:
        search_object, hit = await self.build_search_object(query, locale, limit, offset)
        request = self.mapper.build_request(search_object)
        return search_object, request, hit

    # --- /v1/search ------------------------------------------------------
    async def search(
        self, query: str, locale: str, limit: int | None, offset: int | None
    ) -> tuple[SearchObject, ApiRequest, Any | None, bool]:
        search_object, request, hit = await self.generate(query, locale, limit, offset)
        api_response: Any | None = None
        if self.mapper.mode in ("execute", "generate_and_execute"):
            api_response = await self.executor.execute(request)
        return search_object, request, api_response, hit

    async def close(self) -> None:
        await self.cache.close()
