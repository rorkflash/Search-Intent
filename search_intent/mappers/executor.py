"""Executes a generated ApiRequest against the target API."""

from __future__ import annotations

from typing import Any

import httpx

from ..models import ApiRequest


class ApiExecutor:
    def __init__(self, timeout_seconds: float = 10.0) -> None:
        self._timeout = timeout_seconds

    async def execute(self, request: ApiRequest) -> Any:
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.request(
                request.method,
                request.url,
                headers=request.headers or None,
                json=request.body,
                params=request.query or None,
            )
            resp.raise_for_status()
            content_type = resp.headers.get("content-type", "")
            if "application/json" in content_type:
                return resp.json()
            return resp.text
