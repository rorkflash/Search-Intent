"""Loads the active project's JSON configuration from the config directory.

One running service = one active project config (see README design philosophy).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Config files and whether they are required to boot the service.
CONFIG_FILES: dict[str, bool] = {
    "project": True,
    "extractor": True,
    "intent-map": True,
    "search-map": True,
    "search-object-schema": False,
    "resolver-map": False,
    "api-map": True,
    "cache": False,
    "auth-inbound": False,
}


@dataclass
class ProjectConfig:
    """Parsed configuration for a single active project."""

    project: dict[str, Any]
    extractor: dict[str, Any]
    intent_map: dict[str, Any]
    search_map: dict[str, Any]
    api_map: dict[str, Any]
    search_object_schema: dict[str, Any] = field(default_factory=dict)
    resolver_map: dict[str, Any] = field(default_factory=dict)
    cache: dict[str, Any] = field(default_factory=dict)
    auth_inbound: dict[str, Any] = field(default_factory=dict)

    @property
    def name(self) -> str:
        return self.project.get("name", "unnamed-project")

    @property
    def default_locale(self) -> str:
        return self.project.get("default_locale", "en")


def _read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def load_config(config_dir: str | Path) -> ProjectConfig:
    """Read every config file from ``config_dir`` into a ProjectConfig.

    Raises FileNotFoundError if a required file is missing.
    """
    base = Path(config_dir)
    if not base.is_dir():
        raise FileNotFoundError(f"Config directory not found: {base}")

    loaded: dict[str, dict[str, Any]] = {}
    for stem, required in CONFIG_FILES.items():
        path = base / f"{stem}.json"
        if path.is_file():
            loaded[stem] = _read_json(path)
        elif required:
            raise FileNotFoundError(f"Required config file missing: {path}")
        else:
            loaded[stem] = {}

    return ProjectConfig(
        project=loaded["project"],
        extractor=loaded["extractor"],
        intent_map=loaded["intent-map"],
        search_map=loaded["search-map"],
        api_map=loaded["api-map"],
        search_object_schema=loaded["search-object-schema"],
        resolver_map=loaded["resolver-map"],
        cache=loaded["cache"],
        auth_inbound=loaded["auth-inbound"],
    )
