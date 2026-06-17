"""FastAPI dependency that enforces inbound auth per auth-inbound.json."""

from __future__ import annotations

from typing import Any

from fastapi import Request

from ..config import ProjectConfig
from ..settings import Settings
from .base import AuthError, InboundAuthenticator


def build_authenticator(
    config: ProjectConfig, settings: Settings
) -> InboundAuthenticator | None:
    """Return an authenticator, or None when inbound auth is disabled."""
    cfg = config.auth_inbound.get("inbound_auth", {})
    if not cfg.get("enabled", False):
        return None
    auth_type = cfg.get("type", "jwt")
    if auth_type == "jwt":
        from .jwt import JwtAuthenticator

        return JwtAuthenticator(cfg, settings)
    raise ValueError(f"Unsupported inbound auth type: {auth_type!r}")


def extract_token(request: Request, config: ProjectConfig) -> str | None:
    cfg = config.auth_inbound.get("inbound_auth", {})
    default_source = {"type": "header", "name": "Authorization", "scheme": "Bearer"}
    source = cfg.get("token_source", default_source)
    if source.get("type") == "header":
        raw = request.headers.get(source.get("name", "Authorization"))
        if not raw:
            return None
        scheme = source.get("scheme")
        if scheme and raw.startswith(f"{scheme} "):
            return raw[len(scheme) + 1 :]
        return raw
    return None


class AuthGuard:
    """Callable FastAPI dependency. No-op when authenticator is None."""

    def __init__(
        self, authenticator: InboundAuthenticator | None, config: ProjectConfig
    ) -> None:
        self._authenticator = authenticator
        self._config = config

    async def __call__(self, request: Request) -> dict[str, Any]:
        if self._authenticator is None:
            return {}
        token = extract_token(request, self._config)
        return self._authenticator.authenticate(token)


__all__ = ["AuthError", "AuthGuard", "build_authenticator", "extract_token"]
