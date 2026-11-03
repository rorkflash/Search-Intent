"""Pre-download every NER model referenced by a bundled config profile.

Run at image build time. The extractor is constructed inside the FastAPI
lifespan, and uvicorn binds its socket only *after* the lifespan returns — so a
cold ~800MB HuggingFace download in there means the service refuses connections
for as long as the download takes, and forever if the host can't reach the Hub.
Baking the weights in turns startup into a local disk read.

A collection whose extractor.json names no model runs GLINER2_MODEL (else the
built-in default), so set GLINER2_MODEL at build time too: the Dockerfile
passes it through as a build arg.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from search_intent.extractors.gliner2_extractor import model_name


def referenced_models(config_root: Path, default_model: str | None = None) -> set[str]:
    """Every gliner model an extractor.json under ``config_root`` will load."""
    models: set[str] = set()
    for path in sorted(config_root.rglob("extractor.json")):
        config = json.loads(path.read_text(encoding="utf-8"))
        if config.get("extractor", {}).get("provider") in ("gliner", "gliner2"):
            models.add(model_name(config, default_model))
    return models


def main() -> int:
    config_root = Path(os.environ.get("SEARCH_INTENT_CONFIG_ROOT", "./config"))
    if not config_root.is_dir():
        print(f"Config root not found: {config_root}", file=sys.stderr)
        return 1

    models = referenced_models(config_root, os.environ.get("GLINER2_MODEL"))
    if not models:
        print(f"No gliner extractor configured under {config_root}; nothing to prefetch.")
        return 0

    # Imported here so the "nothing to prefetch" path stays dependency-free.
    from gliner2 import AutoExtractor

    for model in sorted(models):
        print(f"Prefetching {model} into HF_HOME={os.environ.get('HF_HOME', '<unset>')}")
        AutoExtractor.from_pretrained(model)
    return 0


if __name__ == "__main__":
    sys.exit(main())
