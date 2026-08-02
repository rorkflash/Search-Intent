"""Shared FastAPI dependencies, resolved from app.state."""

from __future__ import annotations

from typing import Any

from fastapi import Depends, HTTPException, Request

from ..auth import AuthError
from ..core import Pipeline


def get_pipeline(request: Request) -> Pipeline:
    return request.app.state.pipeline


async def require_auth(request: Request) -> dict[str, Any]:
    guard = request.app.state.auth_guard
    try:
        return await guard(request)
    except AuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


PipelineDep = Depends(get_pipeline)
AuthDep = Depends(require_auth)
