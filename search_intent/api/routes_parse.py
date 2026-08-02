"""POST /v1/parse — intent + entity extraction only."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from ..core import Pipeline
from ..models import ParseResponse, QueryRequest
from .deps import AuthDep, PipelineDep

router = APIRouter(prefix="/v1", tags=["parse"])


@router.post("/parse", response_model=ParseResponse)
async def parse(
    body: QueryRequest,
    pipeline: Pipeline = PipelineDep,
    _claims: dict[str, Any] = AuthDep,
) -> ParseResponse:
    return pipeline.parse(body.query, body.locale)
