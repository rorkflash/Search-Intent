"""Pydantic models for API I/O and the internal SearchObject."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class UserLocation(BaseModel):
    """Where the searcher is, when the caller knows it.

    Used only as a fallback anchor: a query that names its own city or country
    is never re-anchored on the user (see core/geo.py).
    """

    lat: float = Field(..., ge=-90, le=90)
    lng: float = Field(..., ge=-180, le=180)
    radius_km: float | None = Field(
        None, gt=0, le=500, description="Search radius; falls back to the configured default"
    )
    source: str | None = Field(
        None, description="Where the position came from, e.g. 'browser', 'ip', 'header'"
    )


class QueryRequest(BaseModel):
    """Inbound request body shared by /parse, /generate and /search."""

    query: str = Field(..., min_length=1, description="Natural-language search query")
    locale: str = Field("en", description="BCP-47 locale of the query")
    limit: int | None = Field(None, ge=1, le=200)
    offset: int | None = Field(None, ge=0)
    user_location: UserLocation | None = Field(
        None,
        description=(
            "Searcher's position. Used only when the query names no city or country; "
            "omitted callers can send X-User-Lat / X-User-Lng headers instead."
        ),
    )


class ParseResponse(BaseModel):
    query: str
    locale: str
    intent: str
    objects: list[str]
    entities: dict[str, list[str]]
    confidence: dict[str, float]


class SearchObject(BaseModel):
    """Normalized internal representation of a parsed query."""

    query: str
    locale: str
    intent: str
    objects: list[str] = Field(default_factory=list)
    entities: dict[str, list[str]] = Field(default_factory=dict)
    resolved: dict[str, Any] = Field(default_factory=dict)
    filters: dict[str, Any] = Field(default_factory=dict)
    sort: dict[str, Any] = Field(default_factory=dict)
    pagination: dict[str, Any] = Field(default_factory=dict)
    geo: dict[str, Any] | None = Field(
        None,
        description=(
            "Set when the search was anchored on the user's position: bounding box, "
            "radius, and why it was applied. Never cached (see Pipeline)."
        ),
    )


class ApiRequest(BaseModel):
    method: str
    url: str
    headers: dict[str, str] = Field(default_factory=dict)
    body: dict[str, Any] | None = None
    query: dict[str, Any] | None = None


class GenerateResponse(BaseModel):
    query: str
    locale: str
    intent: str
    search_object: SearchObject
    api_request: ApiRequest
    cache: dict[str, Any] = Field(default_factory=lambda: {"hit": False})


class SearchResponse(BaseModel):
    query: str
    locale: str
    intent: str
    search_object: SearchObject
    api_request: ApiRequest
    api_response: Any | None = None
    cache: dict[str, Any] = Field(default_factory=lambda: {"hit": False})
