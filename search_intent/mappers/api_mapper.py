"""Maps a SearchObject to a concrete target API request using api-map.json."""

from __future__ import annotations

import os
from typing import Any

from ..models import ApiRequest, SearchObject
from . import request_builder, template_engine


class ApiMapper:
    def __init__(self, api_map: dict[str, Any]) -> None:
        self._api: dict[str, Any] = api_map.get("api", {})
        self._endpoints: dict[str, Any] = api_map.get("endpoints", {})
        self._intent_endpoint_map: dict[str, str] = api_map.get("intent_endpoint_map", {})
        self.mode: str = self._api.get("mode", "generate_only")
        self._base_url = self._resolve_base_url()

    def _resolve_base_url(self) -> str:
        if "base_url_from_env" in self._api:
            return os.environ.get(self._api["base_url_from_env"], "")
        return self._api.get("base_url", "")

    def endpoint_for_intent(self, intent: str) -> str:
        if intent in self._intent_endpoint_map:
            return self._intent_endpoint_map[intent]
        # Fall back to the first defined endpoint.
        return next(iter(self._endpoints), "search")

    def build_request(self, search_object: SearchObject) -> ApiRequest:
        endpoint_name = self.endpoint_for_intent(search_object.intent)
        endpoint = self._endpoints.get(endpoint_name)
        if endpoint is None:
            raise ValueError(f"No endpoint definition for '{endpoint_name}'")

        context = {"search_object": search_object.model_dump()}
        headers = template_engine.render(endpoint.get("headers", {}), context)
        body = template_engine.render(endpoint.get("body"), context)
        query = template_engine.render(endpoint.get("query"), context)

        options = endpoint.get("options", {})
        if body is not None:
            body = request_builder.prune(
                body,
                drop_null=options.get("remove_null_values", False),
                drop_empty_arrays=options.get("remove_empty_arrays", False),
                drop_empty_objects=options.get("remove_empty_objects", False),
            )

        path = endpoint.get("path", "")
        url = f"{self._base_url.rstrip('/')}{path}" if self._base_url else path

        # Outbound auth (bearer/api-key) added as a header from env.
        self._apply_auth(headers)

        return ApiRequest(
            method=endpoint.get("method", "POST").upper(),
            url=url,
            headers=headers or {},
            body=body,
            query=query,
        )

    def _apply_auth(self, headers: dict[str, str]) -> None:
        auth = self._api.get("auth")
        if not auth:
            return
        atype = auth.get("type")
        if atype == "bearer_token" and "token_from_env" in auth:
            token = os.environ.get(auth["token_from_env"])
            if token:
                headers["Authorization"] = f"Bearer {token}"
        elif atype == "api_key" and "key_from_env" in auth:
            key = os.environ.get(auth["key_from_env"])
            if key:
                headers[auth.get("header", "X-API-Key")] = key
