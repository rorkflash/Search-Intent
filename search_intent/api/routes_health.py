"""Health check endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Request

router = APIRouter(tags=["health"])


@router.get("/health")
async def health(request: Request) -> dict[str, str]:
    project = getattr(request.app.state, "project_name", "unknown")
    return {"status": "ok", "project": project}
