"""Pre-download every NER model referenced by a bundled config profile.

Run at image build time. The extractor is constructed inside the FastAPI
lifespan, and uvicorn binds its socket only *after* the lifespan returns — so a
cold ~800MB HuggingFace download in there means the service refuses connections
for as long as the download takes, and forever if the host can't reach the Hub.
Baking the weights in turns startup into a local disk read.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

DEFAULT_MODEL = "fastino/gliner2-base-v1"


def referenced_models(config_root: Path) -> set[str]:
    """Every gliner model named by an extractor.json under ``config_root``."""
    models: set[str] = set()
    for path in sorted(config_root.rglob("extractor.json")):
        extractor = json.loads(path.read_text(encoding="utf-8")).get("extractor", {})
        if extractor.get("provider") in ("gliner", "gliner2"):
            models.add(extractor.get("model", DEFAULT_MODEL))
    return models


def main() -> int:
    config_root = Path(os.environ.get("SEARCH_INTENT_CONFIG_ROOT", "./config"))
    if not config_root.is_dir():
        print(f"Config root not found: {config_root}", file=sys.stderr)
        return 1

    models = referenced_models(config_root)
    if not models:
        print(f"No gliner extractor configured under {config_root}; nothing to prefetch.")
        return 0

    # Imported here so the "nothing to prefetch" path stays dependency-free.
    from gliner2 import GLiNER2

    for model in sorted(models):
        print(f"Prefetching {model} into HF_HOME={os.environ.get('HF_HOME', '<unset>')}")
        GLiNER2.from_pretrained(model)
    return 0


if __name__ == "__main__":
    sys.exit(main())
