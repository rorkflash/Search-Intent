"""Inbound authenticator interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class AuthError(Exception):
    """Raised when inbound authentication or authorization fails."""

    def __init__(self, detail: str, status_code: int = 401) -> None:
        super().__init__(detail)
        self.detail = detail
        self.status_code = status_code


class InboundAuthenticator(ABC):
    @abstractmethod
    def authenticate(self, token: str | None) -> dict[str, Any]:
        """Validate the token and return its claims, or raise AuthError."""
