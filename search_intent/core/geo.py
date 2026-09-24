"""User-location fallback for queries that name no place.

A query like "cafe places" or "walking tours" has no geographic anchor at all,
so the target API would search the whole planet. When the caller knows where
the searcher is, that position is a better anchor than nothing: it becomes a
bounding box on the SearchObject (``search_object.geo.bbox``), which
api-map.json maps onto whatever geo fields the target API exposes.

Explicit cues ("near me", "nearby", "around me") say the same thing out loud.
They never name a place either, so they take the same branch — only with the
tighter ``cue_radius_km``, since someone asking for "cafes near me" means
walking distance, not the surrounding region.

A place named in the query always wins: "places in Paris" is never re-anchored
on the user, even from a caller that sent a position, and even if the query
also says "near me".

Everything here is config-driven through ``geo.json``. With no ``geo.json`` in
the project config the policy is disabled and the pipeline behaves exactly as
before.
"""

from __future__ import annotations

import math
import re
from typing import Any, Iterable, Mapping

from ..models import SearchObject, UserLocation

# Radius defaults mirror mt-backend-data's /popular "near" support
# (DEFAULT_NEAR_RADIUS_KM = 50, capped at 500) so both paths agree on what
# "near you" means.
DEFAULT_RADIUS_KM = 50.0
DEFAULT_CUE_RADIUS_KM = 25.0
MAX_RADIUS_KM = 500.0

# Coordinates are snapped before use: it keeps the exact position out of the
# generated request and out of logs, and repeated searches from one
# neighbourhood produce one identical bounding box. 2 decimals ≈ 1.1 km.
DEFAULT_PRECISION = 2

# Filters that mean "the query named a place". These are the resolver targets
# of the city/country entities; projects override them in geo.json.
DEFAULT_BLOCKING_FILTERS = ("city_ids", "country_ids")
DEFAULT_BLOCKING_ENTITIES = ("city", "country", "location", "address", "region")

DEFAULT_CUES = (
    "near me",
    "nearby",
    "near by",
    "around me",
    "around here",
    "close to me",
    "close by",
    "next to me",
    "in my area",
    "near my location",
    "my location",
    "where i am",
    "walking distance",
)

DEFAULT_LAT_HEADERS = ("x-user-lat", "cf-iplatitude")
DEFAULT_LNG_HEADERS = ("x-user-lng", "cf-iplongitude")

# Degrees per km. Latitude is near enough constant; longitude shrinks with the
# cosine of the latitude.
_KM_PER_DEG_LAT = 110.574
_KM_PER_DEG_LNG_AT_EQUATOR = 111.320
# Keeps the longitude span finite at the poles (cos -> 0).
_MIN_COS_LAT = 0.01


def bounding_box(lat: float, lng: float, radius_km: float) -> dict[str, float]:
    """Axis-aligned box of ``radius_km`` around a point, clamped to the globe.

    Deliberately a box and not a circle: the target API filters on
    min/max lat/lng, so the corners are slightly further away than the radius.
    Near the antimeridian the box is clamped rather than wrapped — a single
    min/max pair cannot express a wrapped range, and the affected strip has no
    content worth splitting the request for.
    """
    d_lat = radius_km / _KM_PER_DEG_LAT
    cos_lat = max(math.cos(math.radians(lat)), _MIN_COS_LAT)
    d_lng = radius_km / (_KM_PER_DEG_LNG_AT_EQUATOR * cos_lat)

    return {
        "min_lat": round(max(lat - d_lat, -90.0), 6),
        "min_lng": round(max(lng - d_lng, -180.0), 6),
        "max_lat": round(min(lat + d_lat, 90.0), 6),
        "max_lng": round(min(lng + d_lng, 180.0), 6),
    }


def is_empty_response(payload: Any) -> bool:
    """True when a target API response carries no results anywhere in it.

    Shape-agnostic on purpose: the response is whatever the configured target
    API returns. Any non-empty list at any depth counts as a result, which
    holds for the ``{entity: {data: [...], pagination: {...}}}`` shape
    mt-backend-data returns as well as for a bare list.
    """
    if isinstance(payload, list):
        return not payload
    if isinstance(payload, dict):
        return all(is_empty_response(v) for v in payload.values())
    # Scalars (including None) carry no results of their own.
    return True


def _cue_pattern(cues: Iterable[str]) -> re.Pattern[str] | None:
    terms = sorted({c.strip().lower() for c in cues if c and c.strip()}, key=len, reverse=True)
    if not terms:
        return None
    return re.compile(r"\b(?:" + "|".join(re.escape(t) for t in terms) + r")\b", re.IGNORECASE)


class GeoPolicy:
    """Decides whether a search should be anchored on the user's position."""

    def __init__(self, geo_config: dict[str, Any] | None = None) -> None:
        geo: dict[str, Any] = (geo_config or {}).get("geo", {})

        self.enabled: bool = bool(geo.get("enabled", False))
        self.retry_without_geo_when_empty: bool = bool(
            geo.get("retry_without_geo_when_empty", True)
        )

        self._max_radius_km = float(geo.get("max_radius_km", MAX_RADIUS_KM))
        self._radius_km = self._clamp_radius(geo.get("radius_km", DEFAULT_RADIUS_KM))
        self._cue_radius_km = self._clamp_radius(
            geo.get("cue_radius_km", min(DEFAULT_CUE_RADIUS_KM, self._radius_km))
        )
        self._precision = int(geo.get("precision", DEFAULT_PRECISION))

        self._blocking_filters = set(geo.get("blocking_filters", DEFAULT_BLOCKING_FILTERS))
        self._blocking_entities = {
            str(e).lower() for e in geo.get("blocking_entities", DEFAULT_BLOCKING_ENTITIES)
        }
        self._cue_re = _cue_pattern(geo.get("cues", DEFAULT_CUES))

        headers = geo.get("headers", {})
        self._lat_headers = [h.lower() for h in headers.get("lat", DEFAULT_LAT_HEADERS)]
        self._lng_headers = [h.lower() for h in headers.get("lng", DEFAULT_LNG_HEADERS)]
        self._header_fallback = bool(geo.get("header_fallback", True))

    # --- inputs ----------------------------------------------------------
    def location_from_headers(self, headers: Mapping[str, str]) -> UserLocation | None:
        """Position from proxy headers, for callers that send no user_location.

        Covers Cloudflare's visitor-location headers (the same source
        mt-front-nextjs falls back to) and an explicit X-User-Lat/X-User-Lng
        pair set by the gateway. Unparsable values are treated as absent.
        """
        if not self.enabled or not self._header_fallback:
            return None

        lat = _first_float(headers, self._lat_headers)
        lng = _first_float(headers, self._lng_headers)
        if lat is None or lng is None:
            return None
        if not (-90.0 <= lat <= 90.0) or not (-180.0 <= lng <= 180.0):
            return None
        return UserLocation(lat=lat, lng=lng, source="header")

    # --- decision --------------------------------------------------------
    def has_cue(self, query: str) -> bool:
        """True when the query itself asks for "near me" / "nearby" / ..."""
        return bool(self._cue_re and self._cue_re.search(query))

    def names_a_place(self, search_object: SearchObject) -> bool:
        """True when the query named a city/country/location of its own."""
        if any(search_object.filters.get(f) for f in self._blocking_filters):
            return True
        return any(
            values
            for label, values in search_object.entities.items()
            if label.lower() in self._blocking_entities
        )

    # --- application -----------------------------------------------------
    def apply(
        self, search_object: SearchObject, location: UserLocation | None
    ) -> SearchObject:
        """Anchor the search on ``location`` when the query named no place.

        Mutates and returns ``search_object``. Always called *after* the
        search object has been cached, so the cache stays location-free and
        one user's position never reaches another user's cached result.
        """
        if not self.enabled or location is None:
            return search_object
        if self.names_a_place(search_object):
            return search_object

        cue = self.has_cue(search_object.query)
        radius_km = self._resolve_radius(location.radius_km, cue)
        lat = round(location.lat, self._precision)
        lng = round(location.lng, self._precision)

        search_object.geo = {
            "applied": True,
            "trigger": "explicit_cue" if cue else "no_location_entity",
            "source": location.source or "user_location",
            "lat": lat,
            "lng": lng,
            "radius_km": radius_km,
            "bbox": bounding_box(lat, lng, radius_km),
        }
        return search_object

    def drop(self, search_object: SearchObject) -> SearchObject:
        """Undo :meth:`apply`, keeping a record of why.

        Used when a geo-scoped search came back empty: the request is rebuilt
        without the bounding box (no ``bbox`` key means the api-map templates
        resolve to null and get pruned) and the response says the search
        widened to global.
        """
        geo = search_object.geo
        if not geo or not geo.get("applied"):
            return search_object

        search_object.geo = {
            **{k: v for k, v in geo.items() if k != "bbox"},
            "applied": False,
            "fallback": "global",
        }
        return search_object

    # --- internals -------------------------------------------------------
    def _resolve_radius(self, requested_km: float | None, cue: bool) -> float:
        if requested_km is not None:
            return self._clamp_radius(requested_km)
        return self._cue_radius_km if cue else self._radius_km

    def _clamp_radius(self, value: Any) -> float:
        try:
            radius = float(value)
        except (TypeError, ValueError):
            return DEFAULT_RADIUS_KM
        if radius <= 0:
            return DEFAULT_RADIUS_KM
        return min(radius, self._max_radius_km)


def _first_float(headers: Mapping[str, str], names: Iterable[str]) -> float | None:
    for name in names:
        raw = headers.get(name)
        if raw is None:
            continue
        try:
            value = float(raw)
        except (TypeError, ValueError):
            continue
        if math.isfinite(value):
            return value
    return None
