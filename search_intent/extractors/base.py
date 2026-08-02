"""Entity extractor interface.

The core engine never hardcodes business labels; an extractor is given the
entity definitions from extractor.json and returns label -> values.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ExtractionResult:
    entities: dict[str, list[str]] = field(default_factory=dict)
    # Mean confidence across extracted entities, in [0, 1].
    confidence: float = 0.0


class Extractor(ABC):
    def __init__(self, extractor_config: dict[str, Any]) -> None:
        self.config = extractor_config
        self.entities: dict[str, Any] = extractor_config.get("entities", {})
        thresholds = extractor_config.get("extractor", {}).get("thresholds", {})
        self.entity_threshold: float = float(thresholds.get("entity", 0.35))

    @abstractmethod
    def extract(self, query: str, locale: str = "en") -> ExtractionResult:
        """Extract configured entities from ``query``."""
