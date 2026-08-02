"""Resolves ``{{ ... }}`` placeholders in api-map.json against a context.

Two placeholder styles are supported:
  - whole-value:  "{{ search_object.filters }}"  -> the actual object (not a string)
  - interpolated: "id-{{ search_object.intent }}" -> string substitution

Whole-value placeholders preserve type (dict/list/number), which is what API
bodies almost always need.
"""

from __future__ import annotations

import re
from typing import Any

_WHOLE_RE = re.compile(r"^\s*\{\{\s*([\w.]+)\s*\}\}\s*$")
_INLINE_RE = re.compile(r"\{\{\s*([\w.]+)\s*\}\}")


def _lookup(path: str, context: dict[str, Any]) -> Any:
    value: Any = context
    for part in path.split("."):
        if isinstance(value, dict):
            value = value.get(part)
        else:
            value = getattr(value, part, None)
        if value is None:
            return None
    return value


def render(template: Any, context: dict[str, Any]) -> Any:
    """Recursively render a template structure against ``context``."""
    if isinstance(template, str):
        whole = _WHOLE_RE.match(template)
        if whole:
            return _lookup(whole.group(1), context)
        return _INLINE_RE.sub(
            lambda m: str(_lookup(m.group(1), context) or ""), template
        )
    if isinstance(template, dict):
        return {k: render(v, context) for k, v in template.items()}
    if isinstance(template, list):
        return [render(v, context) for v in template]
    return template
