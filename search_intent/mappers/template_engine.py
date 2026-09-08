"""Resolves ``{{ ... }}`` placeholders in api-map.json against a context.

Two placeholder styles are supported:
  - whole-value:  "{{ search_object.filters }}"  -> the actual object (not a string)
  - interpolated: "id-{{ search_object.intent }}" -> string substitution

Whole-value placeholders preserve type (dict/list/number), which is what API
bodies almost always need.

Fallbacks: ``{{ a | b }}`` evaluates paths left-to-right and returns the first
non-null / non-empty value (useful for ``q`` = extracted title OR raw query).
"""

from __future__ import annotations

import re
from typing import Any

_WHOLE_RE = re.compile(r"^\s*\{\{\s*(.+?)\s*\}\}\s*$")
_INLINE_RE = re.compile(r"\{\{\s*(.+?)\s*\}\}")
_PATH_RE = re.compile(r"^[\w.]+$")


def _lookup(path: str, context: dict[str, Any]) -> Any:
    value: Any = context
    for part in path.split("."):
        if isinstance(value, list):
            value = _index_list(value, part)
        elif isinstance(value, dict):
            value = value.get(part)
        else:
            value = getattr(value, part, None)
        if value is None:
            return None
    return value


def _lookup_with_fallback(expr: str, context: dict[str, Any]) -> Any:
    """Resolve ``path`` or ``path | other.path`` (first non-empty wins)."""
    for raw in expr.split("|"):
        path = raw.strip()
        if not path or not _PATH_RE.match(path):
            continue
        value = _lookup(path, context)
        if value is None:
            continue
        if value == "" or value == [] or value == {}:
            continue
        return value
    return None


def _index_list(value: list[Any], part: str) -> Any:
    """Support picking an element out of a list value in a template path.

    Extracted entities/resolved ids are always lists (a query can mention an
    entity more than once), but many target API fields are scalars. ``.first``
    / ``.last`` pick a single element; a plain integer indexes directly.
    """
    if part == "first":
        return value[0] if value else None
    if part == "last":
        return value[-1] if value else None
    if part.lstrip("-").isdigit():
        index = int(part)
        return value[index] if -len(value) <= index < len(value) else None
    return None


def render(template: Any, context: dict[str, Any]) -> Any:
    """Recursively render a template structure against ``context``."""
    if isinstance(template, str):
        whole = _WHOLE_RE.match(template)
        if whole:
            return _lookup_with_fallback(whole.group(1), context)
        return _INLINE_RE.sub(
            lambda m: str(_lookup_with_fallback(m.group(1), context) or ""), template
        )
    if isinstance(template, dict):
        return {k: render(v, context) for k, v in template.items()}
    if isinstance(template, list):
        return [render(v, context) for v in template]
    return template
