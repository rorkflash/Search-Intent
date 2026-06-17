"""Extractor factory: selects the provider named in extractor.json."""

from __future__ import annotations

from typing import Any

from .base import ExtractionResult, Extractor
from .regex_extractor import RegexExtractor


def build_extractor(extractor_config: dict[str, Any]) -> Extractor:
    provider = extractor_config.get("extractor", {}).get("provider", "regex")
    if provider in ("gliner", "gliner2"):
        from .gliner2_extractor import Gliner2Extractor

        return Gliner2Extractor(extractor_config)
    if provider == "regex":
        return RegexExtractor(extractor_config)
    raise ValueError(f"Unknown extractor provider: {provider!r}")


__all__ = ["Extractor", "ExtractionResult", "RegexExtractor", "build_extractor"]
