"""Lightweight structural validation for a loaded ProjectConfig.

Catches the most common misconfigurations early with clear messages rather
than letting them surface as opaque errors deep in the pipeline.
"""

from __future__ import annotations

from .loader import ProjectConfig


class ConfigError(ValueError):
    """Raised when the active project config is structurally invalid."""


def validate_config(config: ProjectConfig) -> list[str]:
    """Return a list of warnings; raise ConfigError on fatal problems."""
    warnings: list[str] = []

    if not config.project.get("name"):
        raise ConfigError("project.json must define a 'name'")

    intents = config.intent_map.get("intents")
    if not isinstance(intents, dict) or not intents:
        raise ConfigError("intent-map.json must define a non-empty 'intents' object")

    objects = config.search_map.get("objects")
    if not isinstance(objects, dict) or not objects:
        raise ConfigError("search-map.json must define a non-empty 'objects' object")

    if "extractor" not in config.extractor:
        raise ConfigError("extractor.json must define an 'extractor' block")

    if not config.api_map.get("endpoints"):
        raise ConfigError("api-map.json must define at least one endpoint")

    # Non-fatal consistency checks.
    known_objects = set(objects)
    for intent_name, intent in intents.items():
        for obj in intent.get("default_objects", []):
            if obj not in known_objects:
                warnings.append(
                    f"intent '{intent_name}' references unknown object '{obj}'"
                )

    endpoints = set(config.api_map.get("endpoints", {}))
    for intent_name, endpoint in config.api_map.get("intent_endpoint_map", {}).items():
        if endpoint not in endpoints:
            warnings.append(
                f"intent_endpoint_map['{intent_name}'] -> unknown endpoint '{endpoint}'"
            )

    return warnings
