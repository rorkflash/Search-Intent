"""Post-processing helpers for generated request bodies."""

from __future__ import annotations

from typing import Any


def prune(value: Any, *, drop_null: bool, drop_empty_arrays: bool, drop_empty_objects: bool) -> Any:
    """Recursively remove null/empty values per api-map endpoint options."""
    if isinstance(value, dict):
        cleaned = {
            k: prune(
                v,
                drop_null=drop_null,
                drop_empty_arrays=drop_empty_arrays,
                drop_empty_objects=drop_empty_objects,
            )
            for k, v in value.items()
        }
        result = {}
        for k, v in cleaned.items():
            if drop_null and v is None:
                continue
            if drop_empty_arrays and isinstance(v, list) and not v:
                continue
            if drop_empty_objects and isinstance(v, dict) and not v:
                continue
            result[k] = v
        return result
    if isinstance(value, list):
        return [
            prune(
                v,
                drop_null=drop_null,
                drop_empty_arrays=drop_empty_arrays,
                drop_empty_objects=drop_empty_objects,
            )
            for v in value
        ]
    return value
