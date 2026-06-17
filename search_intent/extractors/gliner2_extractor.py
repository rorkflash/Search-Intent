"""Optional GLiNER2-based extractor.

Requires the ``gliner2`` package and a model (configured in extractor.json).
It is imported lazily so the service runs without the heavy ML dependency.
Install with: ``uv add gliner2`` (and a torch backend).
"""

from __future__ import annotations

from typing import Any

from .base import ExtractionResult, Extractor


class Gliner2Extractor(Extractor):
    def __init__(self, extractor_config: dict[str, Any]) -> None:
        super().__init__(extractor_config)
        try:
            from gliner2 import GLiNER2  # type: ignore
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise RuntimeError(
                "gliner2 is not installed. Install it or use the 'regex' extractor "
                "provider in extractor.json."
            ) from exc

        model_name = extractor_config.get("extractor", {}).get(
            "model", "fastino/gliner2-base-v1"
        )
        self._model = GLiNER2.from_pretrained(model_name)
        self._labels = list(self.entities.keys())

    def extract(self, query: str, locale: str = "en") -> ExtractionResult:  # pragma: no cover
        predictions = self._model.predict_entities(
            query, self._labels, threshold=self.entity_threshold
        )
        entities: dict[str, list[str]] = {}
        scores: list[float] = []
        for pred in predictions:
            label = pred["label"]
            entities.setdefault(label, []).append(pred["text"])
            scores.append(float(pred.get("score", 0.0)))

        confidence = sum(scores) / len(scores) if scores else 0.0
        return ExtractionResult(entities=entities, confidence=confidence)
