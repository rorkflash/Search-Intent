"""Rule-based intent detection from intent-map.json.

Scores each intent by how many of its keywords appear in the query and picks
the best. Falls back to an intent with no keywords (the "global" intent) or the
first defined intent.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class IntentResult:
    intent: str
    objects: list[str]
    confidence: float


class IntentDetector:
    def __init__(self, intent_map: dict[str, Any]) -> None:
        self._intents: dict[str, Any] = intent_map.get("intents", {})
        # The fallback is an explicit keyword-less intent, else the first one.
        self._fallback = next(
            (name for name, spec in self._intents.items() if not spec.get("keywords")),
            next(iter(self._intents), "global_search"),
        )

    def detect(self, query: str) -> IntentResult:
        lowered = query.lower()
        best_name: str | None = None
        best_score = 0

        for name, spec in self._intents.items():
            keywords = spec.get("keywords", [])
            score = sum(1 for kw in keywords if kw.lower() in lowered)
            if score > best_score:
                best_score = score
                best_name = name

        if best_name is None:
            spec = self._intents.get(self._fallback, {})
            return IntentResult(
                intent=self._fallback,
                objects=list(spec.get("default_objects", [])),
                confidence=0.3,
            )

        spec = self._intents[best_name]
        keywords = spec.get("keywords", []) or [1]
        # Confidence scales with the fraction of keywords matched, capped at 0.95.
        confidence = min(0.95, 0.5 + 0.45 * (best_score / len(keywords)))
        return IntentResult(
            intent=best_name,
            objects=list(spec.get("default_objects", [])),
            confidence=round(confidence, 2),
        )
