"""Query normalization: cheap, locale-agnostic cleanup before extraction."""

from __future__ import annotations

import re

_WS_RE = re.compile(r"\s+")


def normalize(query: str) -> str:
    """Trim, collapse whitespace. Casing is preserved for entity matching."""
    return _WS_RE.sub(" ", query).strip()
