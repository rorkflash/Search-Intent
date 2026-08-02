"""POST /v1/generate — full pipeline to a generated target API request."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from ..core import Pipeline
from ..models import GenerateResponse, QueryRequest
from .deps import AuthDep, PipelineDep

router = APIRouter(prefix="/v1", tags=["generate"])


@router.post("/generate", response_model=GenerateResponse)
async def generate(
    body: QueryRequest,
    pipeline: Pipeline = PipelineDep,
    _claims: dict[str, Any] = AuthDep,
) -> GenerateResponse:
    search_object, request, hit = await pipeline.generate(
        body.query, body.locale, body.limit, body.offset
    )
    return GenerateResponse(
        query=search_object.query,
        locale=search_object.locale,
        intent=search_object.intent,
        search_object=search_object,
        api_request=request,
        cache={"hit": hit},
    )
