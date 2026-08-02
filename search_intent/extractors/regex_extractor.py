"""Zero-dependency fallback extractor.

Matches entities using the example vocabulary from extractor.json plus a few
built-in patterns (price expressions). It is intentionally simple: it lets the
service run end-to-end with no ML model. For production-quality extraction use
the GLiNER2 extractor.
"""

from __future__ import annotations

import re
from typing import Any

from .base import ExtractionResult, Extractor

# Price expressions: "under $100", "between 50 and 200", "$2500", "max 100".
_PRICE_RE = re.compile(
    r"(under|below|less than|max|up to|over|above|more than|min|from|between)?\s*"
    r"\$?\s*(\d+(?:[.,]\d+)?)\s*(?:(?:and|to|-)\s*\$?\s*(\d+(?:[.,]\d+)?))?",
    re.IGNORECASE,
)


class RegexExtractor(Extractor):
    def __init__(self, extractor_config: dict[str, Any]) -> None:
        super().__init__(extractor_config)
        # Pre-compile a whole-word matcher per entity from its examples.
        self._vocab: dict[str, re.Pattern[str]] = {}
        for label, spec in self.entities.items():
            examples = spec.get("examples", [])
            terms = sorted({e for e in examples if e}, key=len, reverse=True)
            if terms:
                joined = "|".join(re.escape(t) for t in terms)
                self._vocab[label] = re.compile(rf"\b({joined})\b", re.IGNORECASE)

    def extract(self, query: str, locale: str = "en") -> ExtractionResult:
        entities: dict[str, list[str]] = {}

        for label, pattern in self._vocab.items():
            if label == "price":
                continue
            found: list[str] = []
            for match in pattern.finditer(query):
                value = match.group(1)
                if value.lower() not in (v.lower() for v in found):
                    found.append(value)
            if found:
                entities[label] = found

        if "price" in self.entities:
            price = self._match_price(query)
            if price:
                entities["price"] = price

        # Crude but honest confidence: did we find anything at all?
        confidence = 0.8 if entities else 0.0
        return ExtractionResult(entities=entities, confidence=confidence)

    @staticmethod
    def _match_price(query: str) -> list[str]:
        match = _PRICE_RE.search(query)
        if not match or not match.group(2):
            return []
        return [match.group(0).strip()]
