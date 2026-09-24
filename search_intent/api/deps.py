"""Shared FastAPI dependencies, resolved from app.state."""

from __future__ import annotations

from typing import Any

from fastapi import Depends, HTTPException, Request

from ..auth import AuthError
from ..core import Pipeline
from ..models import QueryRequest, UserLocation


def get_pipeline(request: Request) -> Pipeline:
    return request.app.state.pipeline


async def require_auth(request: Request) -> dict[str, Any]:
    guard = request.app.state.auth_guard
    try:
        return await guard(request)
    except AuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


def user_location_from(request: Request, body: QueryRequest) -> UserLocation | None:
    """The searcher's position: the request body first, proxy headers second.

    The body is what a caller that asked the browser for geolocation sends.
    The header fallback picks up Cloudflare's visitor-location headers (or an
    X-User-Lat/X-User-Lng pair set by the gateway) so a caller that never
    touches the Geolocation API still gets a sensible anchor.
    """
    if body.user_location is not None:
        return body.user_location
    pipeline: Pipeline = request.app.state.pipeline
    return pipeline.geo_policy.location_from_headers(request.headers)


PipelineDep = Depends(get_pipeline)
AuthDep = Depends(require_auth)
