"""JWT inbound authenticator (HS256 by default; secret/issuer/audience from env).

For production prefer RS256/ES256 with JWKS — wire a plugin for that.
"""

from __future__ import annotations

import os
from typing import Any

import jwt

from ..settings import Settings
from .base import AuthError, InboundAuthenticator


class JwtAuthenticator(InboundAuthenticator):
    def __init__(self, auth_config: dict[str, Any], settings: Settings) -> None:
        jwt_cfg = auth_config.get("jwt", {})
        self.algorithm: str = jwt_cfg.get("algorithm", "HS256")
        self.secret: str | None = self._from_env(jwt_cfg, "secret_from_env", settings.jwt_secret)
        self.issuer: str | None = self._from_env(jwt_cfg, "issuer_from_env", settings.jwt_issuer)
        self.audience: str | None = self._from_env(
            jwt_cfg, "audience_from_env", settings.jwt_audience
        )
        self.required_claims: list[str] = jwt_cfg.get("required_claims", [])

        authz = auth_config.get("authorization", {})
        self.authz_enabled: bool = bool(authz.get("enabled", False))
        self.required_permissions: list[str] = authz.get("required_permissions", [])

    @staticmethod
    def _from_env(cfg: dict[str, Any], key: str, fallback: str | None) -> str | None:
        if key in cfg:
            return os.environ.get(cfg[key], fallback)
        return fallback

    def authenticate(self, token: str | None) -> dict[str, Any]:
        if not token:
            raise AuthError("Missing bearer token")
        if not self.secret:
            raise AuthError("JWT secret is not configured", status_code=500)

        options = {"require": self.required_claims} if self.required_claims else {}
        try:
            claims = jwt.decode(
                token,
                self.secret,
                algorithms=[self.algorithm],
                audience=self.audience,
                issuer=self.issuer,
                options=options,
            )
        except jwt.PyJWTError as exc:
            raise AuthError(f"Invalid token: {exc}") from exc

        if self.authz_enabled and self.required_permissions:
            granted = set(claims.get("permissions", []))
            missing = [p for p in self.required_permissions if p not in granted]
            if missing:
                raise AuthError(
                    f"Missing required permissions: {missing}", status_code=403
                )
        return claims
