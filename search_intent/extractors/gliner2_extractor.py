"""Optional GLiNER2-based extractor.

Requires the ``gliner2[local]`` package (it brings torch) and a model
(configured in extractor.json). It is imported lazily so the service runs
without the heavy ML dependency.

Both checkpoint families load through ``AutoExtractor``: GLiNER2 span models
(``fastino/gliner2-base-v1``) and GLiNER2.5 boundary models
(``fastino/gliner2.5-base-v1``).

What the model sees per label is the label name plus, when set, the entity's
``model_description``: one short line written for the model, e.g. "Movie
genre, such as comedy, horror or western". The plain ``description`` field is
for people and is not sent; benchmarks/extractor showed that long,
human-oriented descriptions hurt extraction.
"""

from __future__ import annotations

import logging
import os
import warnings
from functools import lru_cache
from typing import Any

from .base import ExtractionResult, Extractor

BUILTIN_MODEL = "fastino/gliner2-base-v1"


class _DropModelTypeNotice(logging.Filter):
    """GLiNER2 checkpoints declare ``model_type: gliner2`` but load through
    ExtractorConfig, so transformers warns about the mismatch on every load.
    The mismatch is by design in gliner2, so the notice is noise."""

    def filter(self, record: logging.LogRecord) -> bool:
        return "to instantiate a model of type" not in record.getMessage()


logging.getLogger("transformers.configuration_utils").addFilter(_DropModelTypeNotice())
# Transformers' DeBERTa module (the GLiNER2 encoder) decorates helpers with
# torch.jit.script at import time; recent torch flags that as deprecated.
# gliner2 already silences the Python 3.14 wording of this warning, not this one.
warnings.filterwarnings(
    "ignore", message=r"`torch\.jit\.script` is deprecated", category=FutureWarning
)


def model_name(extractor_config: dict[str, Any], default_model: str | None = None) -> str:
    """The model a collection runs: extractor.json's ``model``, else
    ``default_model`` (the GLINER2_MODEL env var), else BUILTIN_MODEL.

    scripts/prefetch_models.py uses this too, so the Docker image bakes in
    exactly the models the service will ask for.
    """
    return extractor_config.get("extractor", {}).get("model") or default_model or BUILTIN_MODEL


@lru_cache(maxsize=None)
def _load_model(name: str) -> Any:
    """Load each model once per process.

    The weights are read-only at inference time, so pipelines built from
    different configs (the sandbox holds one per collection) can share them.
    """
    try:
        from gliner2 import AutoExtractor  # type: ignore
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise RuntimeError(
            "gliner2 2.x is not installed. Install gliner2[local] or use the "
            "'regex' extractor provider in extractor.json."
        ) from exc
    return AutoExtractor.from_pretrained(_local_snapshot(name))


def _local_snapshot(name: str) -> str:
    """The cached snapshot folder of a Hub model, else ``name`` unchanged.

    Loading by Hub name asks the Hub for updates on every start, even when the
    weights are cached: slow, fails without network, and logs an HF_TOKEN
    notice. A cached model therefore loads from disk; an uncached one still
    downloads. To pick up a newer revision, delete it from MODEL_CACHE_DIR.
    """
    if os.path.isdir(name):
        return name
    from huggingface_hub import snapshot_download

    try:
        return snapshot_download(name, local_files_only=True)
    except FileNotFoundError:  # LocalEntryNotFoundError: not cached yet
        return name


class Gliner2Extractor(Extractor):
    def __init__(
        self, extractor_config: dict[str, Any], default_model: str | None = None
    ) -> None:
        super().__init__(extractor_config)
        self.model_name = model_name(extractor_config, default_model)
        self._model = _load_model(self.model_name)
        self._entity_types = self._build_entity_types()

    def _build_entity_types(self) -> list[str] | dict[str, str]:
        described = {
            label: spec["model_description"]
            for label, spec in self.entities.items()
            if spec.get("model_description")
        }
        if not described:
            return list(self.entities.keys())
        return {label: described.get(label, label) for label in self.entities}

    def extract(self, query: str, locale: str = "en") -> ExtractionResult:  # pragma: no cover
        result = self._model.extract_entities(
            query,
            self._entity_types,
            threshold=self.entity_threshold,
            include_confidence=True,
        )
        raw_entities = result.get("entities", {})
        entities: dict[str, list[str]] = {}
        scores: list[float] = []
        for label, items in raw_entities.items():
            for item in items:
                entities.setdefault(label, []).append(item["text"])
                scores.append(float(item.get("confidence", 0.0)))

        confidence = sum(scores) / len(scores) if scores else 0.0
        return ExtractionResult(entities=entities, confidence=confidence)
