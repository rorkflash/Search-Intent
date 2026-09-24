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
from ..models import ApiRequest, ParseResponse, SearchObject, UserLocation
from ..resolvers import build_resolvers
from ..settings import Settings
from .geo import GeoPolicy, is_empty_response
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
        self.geo_policy = GeoPolicy(config.geo)

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
        self,
        query: str,
        locale: str,
        limit: int | None,
        offset: int | None,
        user_location: UserLocation | None = None,
    ) -> tuple[SearchObject, bool]:
        normalized = normalize(query)
        cache_parts = {"locale": locale, "query_hash": self.cache.query_hash(normalized)}

        cached = await self.cache.get("search_object", **cache_parts)
        if cached is not None:
            search_object = SearchObject.model_validate(cached)
            return self.geo_policy.apply(search_object, user_location), True

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
        # Cached before the geo fallback is applied: the cache key is only
        # locale + query, so anything position-dependent must stay out of it.
        await self.cache.set("search_object", search_object.model_dump(), **cache_parts)
        return self.geo_policy.apply(search_object, user_location), False

    # --- /v1/generate ----------------------------------------------------
    async def generate(
        self,
        query: str,
        locale: str,
        limit: int | None,
        offset: int | None,
        user_location: UserLocation | None = None,
    ) -> tuple[SearchObject, ApiRequest, bool]:
        search_object, hit = await self.build_search_object(
            query, locale, limit, offset, user_location
        )
        request = self.mapper.build_request(search_object)
        return search_object, request, hit

    # --- /v1/search ------------------------------------------------------
    async def search(
        self,
        query: str,
        locale: str,
        limit: int | None,
        offset: int | None,
        user_location: UserLocation | None = None,
    ) -> tuple[SearchObject, ApiRequest, Any | None, bool]:
        search_object, request, hit = await self.generate(
            query, locale, limit, offset, user_location
        )
        api_response: Any | None = None
        if self.mapper.mode in ("execute", "generate_and_execute"):
            api_response = await self.executor.execute(request)
            search_object, request, api_response = await self._retry_without_geo(
                search_object, request, api_response
            )
        return search_object, request, api_response, hit

    async def _retry_without_geo(
        self, search_object: SearchObject, request: ApiRequest, api_response: Any
    ) -> tuple[SearchObject, ApiRequest, Any]:
        """Widen a geo-scoped search that found nothing back to global.

        The user's position is only a fallback anchor, so it must not be the
        reason a search returns nothing: "Harry Potter places" from someone in
        Yerevan should still find the ones in London. Costs one extra upstream
        call, and only when the scoped search came back empty.
        """
        geo = search_object.geo
        if not geo or not geo.get("applied"):
            return search_object, request, api_response
        if not self.geo_policy.retry_without_geo_when_empty:
            return search_object, request, api_response
        if not is_empty_response(api_response):
            return search_object, request, api_response

        search_object = self.geo_policy.drop(search_object)
        request = self.mapper.build_request(search_object)
        return search_object, request, await self.executor.execute(request)

    async def close(self) -> None:
        await self.cache.close()
