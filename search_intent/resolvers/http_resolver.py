"""HTTP resolver: calls an external service to resolve a value into IDs.

The endpoint URL is read from an environment variable (never hardcoded), the
query is templated with the value, and IDs are extracted via a JSONPath.
"""

from __future__ import annotations

import os
from typing import Any

import httpx
from jsonpath_ng.ext import parse as jsonpath_parse

from .base import Resolver


class HttpResolver(Resolver):
    def __init__(self, entity_key: str, spec: dict[str, Any]) -> None:
        super().__init__(entity_key, spec)
        self.method: str = spec.get("method", "GET").upper()
        self.url: str | None = self._resolve_url(spec)
        self.query_template: dict[str, str] = spec.get("query", {})
        self.result_path = jsonpath_parse(spec.get("result_path", "$[*]"))
        self.timeout: float = float(spec.get("timeout_seconds", 5.0))

    @staticmethod
    def _resolve_url(spec: dict[str, Any]) -> str | None:
        if "url_from_env" in spec:
            return os.environ.get(spec["url_from_env"])
        return spec.get("url")

    async def resolve(self, value: str) -> list[Any]:
        if not self.url:
            return []
        params = {k: v.replace("{{ value }}", value) for k, v in self.query_template.items()}
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.request(self.method, self.url, params=params)
            resp.raise_for_status()
            data = resp.json()
        return [match.value for match in self.result_path.find(data)]
