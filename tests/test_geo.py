"""Tests for the user-location fallback (core/geo.py + its pipeline wiring).

These build a Pipeline directly from in-memory config with the regex
extractor, so nothing here loads an ML model or touches the network.
"""

from __future__ import annotations

import math
from typing import Any

import pytest

from search_intent.config.loader import ProjectConfig
from search_intent.core import Pipeline, bounding_box, is_empty_response
from search_intent.core.geo import GeoPolicy
from search_intent.mappers import request_builder, template_engine
from search_intent.models import SearchObject, UserLocation
from search_intent.settings import Settings

YEREVAN = UserLocation(lat=40.1792, lng=44.4991)

GEO_CONFIG: dict[str, Any] = {
    "geo": {
        "enabled": True,
        "radius_km": 50,
        "cue_radius_km": 25,
        "blocking_filters": ["city_ids", "country_ids"],
        "blocking_entities": ["city", "country"],
        "headers": {
            "lat": ["x-user-lat", "cf-iplatitude"],
            "lng": ["x-user-lng", "cf-iplongitude"],
        },
    }
}


def search_object(**overrides: Any) -> SearchObject:
    base: dict[str, Any] = {
        "query": "cafe places",
        "locale": "en",
        "intent": "search_places",
        "objects": ["places"],
        "entities": {"location_type": ["cafe"]},
        "filters": {"place_type_ids": [3]},
    }
    base.update(overrides)
    return SearchObject(**base)


# --- bounding box ---------------------------------------------------------
def test_bounding_box_is_centered_and_roughly_the_right_size():
    box = bounding_box(40.18, 44.50, 50)
    assert box["min_lat"] < 40.18 < box["max_lat"]
    assert box["min_lng"] < 44.50 < box["max_lng"]
    # ~0.45 degrees of latitude for 50 km.
    assert math.isclose(box["max_lat"] - box["min_lat"], 2 * 50 / 110.574, rel_tol=1e-6)


def test_bounding_box_widens_longitude_away_from_the_equator():
    equator = bounding_box(0.0, 0.0, 50)
    northern = bounding_box(60.0, 0.0, 50)
    equator_span = equator["max_lng"] - equator["min_lng"]
    northern_span = northern["max_lng"] - northern["min_lng"]
    # At 60°N a degree of longitude is half as wide, so the box spans twice as many.
    assert math.isclose(northern_span, 2 * equator_span, rel_tol=0.01)


def test_bounding_box_clamps_to_the_globe():
    box = bounding_box(89.9, 179.9, 500)
    assert box["max_lat"] == 90.0
    assert box["max_lng"] == 180.0
    assert -90.0 <= box["min_lat"] <= 90.0


# --- empty-response detection ---------------------------------------------
@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"places": {"data": [], "pagination": {"total": 0}}},
        {"places": {"data": []}, "scenes": {"data": []}},
        [],
        None,
    ],
)
def test_is_empty_response_true(payload):
    assert is_empty_response(payload) is True


@pytest.mark.parametrize(
    "payload",
    [
        {"places": {"data": [{"id": 1}], "pagination": {"total": 1}}},
        {"places": {"data": []}, "scenes": {"data": [{"id": 9}]}},
        [{"id": 1}],
    ],
)
def test_is_empty_response_false(payload):
    assert is_empty_response(payload) is False


# --- policy decisions -----------------------------------------------------
def test_applies_when_the_query_names_no_place():
    geo = GeoPolicy(GEO_CONFIG).apply(search_object(), YEREVAN).geo
    assert geo["applied"] is True
    assert geo["trigger"] == "no_location_entity"
    assert geo["radius_km"] == 50
    assert geo["bbox"]["min_lat"] < geo["lat"] < geo["bbox"]["max_lat"]


def test_skips_when_the_query_named_a_city():
    so = search_object(
        query="places in Paris",
        entities={"city": ["Paris"]},
        filters={"city_ids": [359]},
    )
    assert GeoPolicy(GEO_CONFIG).apply(so, YEREVAN).geo is None


def test_skips_when_the_query_named_a_country():
    so = search_object(
        query="movies filmed in France",
        entities={"country": ["France"]},
        filters={"country_ids": [86]},
    )
    assert GeoPolicy(GEO_CONFIG).apply(so, YEREVAN).geo is None


def test_a_named_city_wins_over_an_explicit_cue():
    # "near me in Paris" is contradictory; the place the user actually typed wins.
    so = search_object(
        query="cafe places near me in Paris",
        entities={"city": ["Paris"]},
        filters={"city_ids": [359]},
    )
    assert GeoPolicy(GEO_CONFIG).apply(so, YEREVAN).geo is None


def test_explicit_cue_uses_the_tighter_radius():
    geo = GeoPolicy(GEO_CONFIG).apply(search_object(query="cafe places near me"), YEREVAN).geo
    assert geo["trigger"] == "explicit_cue"
    assert geo["radius_km"] == 25


def test_caller_radius_overrides_the_configured_default():
    location = UserLocation(lat=40.1792, lng=44.4991, radius_km=10, source="browser")
    geo = GeoPolicy(GEO_CONFIG).apply(search_object(), location).geo
    assert geo["radius_km"] == 10
    assert geo["source"] == "browser"


def test_position_is_snapped_before_it_reaches_the_request():
    location = UserLocation(lat=40.179246, lng=44.499103)
    geo = GeoPolicy(GEO_CONFIG).apply(search_object(), location).geo
    assert (geo["lat"], geo["lng"]) == (40.18, 44.5)


def test_no_location_means_no_geo():
    assert GeoPolicy(GEO_CONFIG).apply(search_object(), None).geo is None


def test_disabled_policy_is_a_no_op():
    policy = GeoPolicy({"geo": {"enabled": False}})
    assert policy.apply(search_object(), YEREVAN).geo is None
    assert policy.location_from_headers({"x-user-lat": "40.1", "x-user-lng": "44.5"}) is None


def test_missing_geo_config_disables_the_policy():
    assert GeoPolicy({}).enabled is False
    assert GeoPolicy(None).apply(search_object(), YEREVAN).geo is None


def test_drop_widens_the_search_and_says_so():
    policy = GeoPolicy(GEO_CONFIG)
    so = policy.drop(policy.apply(search_object(), YEREVAN))
    assert so.geo["applied"] is False
    assert so.geo["fallback"] == "global"
    assert "bbox" not in so.geo


# --- header fallback ------------------------------------------------------
def test_location_from_cloudflare_headers():
    location = GeoPolicy(GEO_CONFIG).location_from_headers(
        {"cf-iplatitude": "51.5074", "cf-iplongitude": "-0.1278"}
    )
    assert (location.lat, location.lng, location.source) == (51.5074, -0.1278, "header")


def test_explicit_headers_win_over_the_ip_lookup():
    location = GeoPolicy(GEO_CONFIG).location_from_headers(
        {
            "x-user-lat": "40.1792",
            "x-user-lng": "44.4991",
            "cf-iplatitude": "51.5074",
            "cf-iplongitude": "-0.1278",
        }
    )
    assert location.lat == 40.1792


@pytest.mark.parametrize(
    "headers",
    [
        {},
        {"x-user-lat": "40.1"},  # half a position is no position
        {"x-user-lat": "not-a-number", "x-user-lng": "44.5"},
        {"x-user-lat": "200", "x-user-lng": "44.5"},  # out of range
    ],
)
def test_unusable_headers_yield_no_location(headers):
    assert GeoPolicy(GEO_CONFIG).location_from_headers(headers) is None


# --- api-map rendering ----------------------------------------------------
BODY_TEMPLATE = {
    "q": "{{ search_object.filters.q }}",
    "filters": {
        "city_id": "{{ search_object.filters.city_ids.first }}",
        "minLat": "{{ search_object.geo.bbox.min_lat }}",
        "minLng": "{{ search_object.geo.bbox.min_lng }}",
        "maxLat": "{{ search_object.geo.bbox.max_lat }}",
        "maxLng": "{{ search_object.geo.bbox.max_lng }}",
    },
}


def render_body(so: SearchObject) -> dict[str, Any]:
    body = template_engine.render(BODY_TEMPLATE, {"search_object": so.model_dump()})
    return request_builder.prune(
        body, drop_null=True, drop_empty_arrays=True, drop_empty_objects=True
    )


def test_bbox_renders_into_the_target_request():
    so = GeoPolicy(GEO_CONFIG).apply(search_object(), YEREVAN)
    body = render_body(so)
    assert set(body["filters"]) == {"minLat", "minLng", "maxLat", "maxLng"}
    assert body["filters"]["minLat"] == so.geo["bbox"]["min_lat"]


def test_request_carries_no_geo_fields_without_a_position():
    assert "filters" not in render_body(search_object())


# --- pipeline wiring ------------------------------------------------------
def build_pipeline(*, cache: bool = False, geo: dict[str, Any] | None = None) -> Pipeline:
    config = ProjectConfig(
        project={"name": "geo-test", "default_locale": "en"},
        extractor={
            "extractor": {"provider": "regex"},
            "entities": {
                "city": {"examples": ["Paris", "London"]},
                "location_type": {"examples": ["cafe", "museum"]},
            },
        },
        intent_map={
            "intents": {
                "search_places": {"keywords": ["places", "place"], "default_objects": ["places"]}
            }
        },
        search_map={"objects": {"places": {"aliases": ["place", "places"]}}},
        api_map={
            "api": {"base_url": "https://api.example.com", "mode": "generate_and_execute"},
            "endpoints": {
                "search": {
                    "method": "POST",
                    "path": "/v1/search",
                    "body": BODY_TEMPLATE,
                    "options": {
                        "remove_null_values": True,
                        "remove_empty_arrays": True,
                        "remove_empty_objects": True,
                    },
                }
            },
            "intent_endpoint_map": {"search_places": "search"},
        },
        resolver_map={
            "resolvers": {
                "city": {"type": "static", "target": "city_ids", "map": {"paris": 359}}
            }
        },
        cache=(
            {
                "cache": {
                    "enabled": True,
                    "backend": "memory",
                    "keys": {
                        "search_object": {
                            "pattern": "{namespace}:{locale}:{query_hash}:search_object",
                            "ttl_seconds": 60,
                        }
                    },
                }
            }
            if cache
            else {}
        ),
        geo=geo if geo is not None else GEO_CONFIG,
    )
    return Pipeline(config, Settings())


async def test_generate_scopes_a_placeless_query_to_the_user():
    _, request, _ = await (build_pipeline()).generate("cafe places", "en", None, None, YEREVAN)
    assert set(request.body["filters"]) == {"minLat", "minLng", "maxLat", "maxLng"}


async def test_generate_leaves_a_city_query_alone():
    _, request, _ = await (build_pipeline()).generate("places in Paris", "en", None, None, YEREVAN)
    assert request.body["filters"] == {"city_id": 359}


async def test_cached_search_object_never_carries_another_users_position():
    pipeline = build_pipeline(cache=True)
    await pipeline.generate("cafe places", "en", None, None, YEREVAN)

    # Same query, second caller with no position: must hit the cache and come
    # back with no geo scoping at all.
    search_object, request, hit = await pipeline.generate("cafe places", "en", None, None, None)
    assert hit is True
    assert search_object.geo is None
    assert "filters" not in request.body

    # ...and a third caller elsewhere gets their own box, not the first one's.
    london = UserLocation(lat=51.5074, lng=-0.1278)
    search_object, _, hit = await pipeline.generate("cafe places", "en", None, None, london)
    assert hit is True
    assert search_object.geo["lat"] == 51.51


async def test_empty_geo_scoped_search_retries_globally(monkeypatch: pytest.MonkeyPatch):
    pipeline = build_pipeline()
    calls: list[dict[str, Any]] = []

    async def fake_execute(request):
        calls.append(request.body)
        # Empty inside the box, results once the box is gone.
        if "filters" in request.body:
            return {"places": {"data": []}}
        return {"places": {"data": [{"id": 1}]}}

    monkeypatch.setattr(pipeline.executor, "execute", fake_execute)
    search_object, _, api_response, _ = await pipeline.search(
        "cafe places", "en", None, None, YEREVAN
    )

    assert len(calls) == 2
    assert "minLat" in calls[0]["filters"]
    assert "filters" not in calls[1]
    assert api_response["places"]["data"] == [{"id": 1}]
    assert search_object.geo["applied"] is False
    assert search_object.geo["fallback"] == "global"


async def test_non_empty_geo_scoped_search_is_not_retried(monkeypatch: pytest.MonkeyPatch):
    pipeline = build_pipeline()
    calls: list[Any] = []

    async def fake_execute(request):
        calls.append(request.body)
        return {"places": {"data": [{"id": 1}]}}

    monkeypatch.setattr(pipeline.executor, "execute", fake_execute)
    search_object, _, _, _ = await pipeline.search("cafe places", "en", None, None, YEREVAN)

    assert len(calls) == 1
    assert search_object.geo["applied"] is True


async def test_retry_can_be_turned_off(monkeypatch: pytest.MonkeyPatch):
    pipeline = build_pipeline(
        geo={"geo": {**GEO_CONFIG["geo"], "retry_without_geo_when_empty": False}}
    )
    calls: list[Any] = []

    async def fake_execute(request):
        calls.append(request.body)
        return {"places": {"data": []}}

    monkeypatch.setattr(pipeline.executor, "execute", fake_execute)
    search_object, _, _, _ = await pipeline.search("cafe places", "en", None, None, YEREVAN)

    assert len(calls) == 1
    assert search_object.geo["applied"] is True
