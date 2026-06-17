"""Example inbound auth plugin.

Referenced by auth-inbound.json when using a custom plugin instead of the
built-in JWT authenticator. Subclass the base interface and implement
``authenticate``. This example simply delegates to the built-in HS256 verifier.
"""

from __future__ import annotations

from typing import Any

from search_intent.auth.jwt import JwtAuthenticator
from search_intent.plugins import BaseInboundAuth


class JwtInboundAuthPlugin(BaseInboundAuth):
    def __init__(self, auth_config: dict[str, Any], settings: Any) -> None:
        self._delegate = JwtAuthenticator(auth_config, settings)

    def authenticate(self, token: str | None) -> dict[str, Any]:
        return self._delegate.authenticate(token)
