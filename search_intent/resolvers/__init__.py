"""Resolver registry: builds resolvers from resolver-map.json."""

from __future__ import annotations

from typing import Any

from .base import Resolver
from .http_resolver import HttpResolver
from .static_resolver import StaticResolver


def build_resolvers(resolver_map: dict[str, Any]) -> dict[str, Resolver]:
    """Return entity_key -> Resolver for every entry in resolver-map.json."""
    resolvers: dict[str, Resolver] = {}
    for entity_key, spec in resolver_map.get("resolvers", {}).items():
        rtype = spec.get("type", "static")
        if rtype == "http":
            resolvers[entity_key] = HttpResolver(entity_key, spec)
        elif rtype == "static":
            resolvers[entity_key] = StaticResolver(entity_key, spec)
        else:
            raise ValueError(f"Unknown resolver type {rtype!r} for entity {entity_key!r}")
    return resolvers


__all__ = ["Resolver", "HttpResolver", "StaticResolver", "build_resolvers"]
