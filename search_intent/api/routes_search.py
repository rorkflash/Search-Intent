"""POST /v1/search — generate and (optionally) execute against the target API."""

from __future__ import annotations

from typing import Any

import httpx
from fastapi import APIRouter, HTTPException

from ..core import Pipeline
from ..models import QueryRequest, SearchResponse
from .deps import AuthDep, PipelineDep

router = APIRouter(prefix="/v1", tags=["search"])


@router.post("/search", response_model=SearchResponse)
async def search(
    body: QueryRequest,
    pipeline: Pipeline = PipelineDep,
    _claims: dict[str, Any] = AuthDep,
) -> SearchResponse:
    try:
        search_object, request, api_response, hit = await pipeline.search(
            body.query, body.locale, body.limit, body.offset
        )
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"Target API error: {exc}") from exc

    return SearchResponse(
        query=search_object.query,
        locale=search_object.locale,
        intent=search_object.intent,
        search_object=search_object,
        api_request=request,
        api_response=api_response,
        cache={"hit": hit},
    )
