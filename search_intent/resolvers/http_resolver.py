"""HTTP resolver: calls an external service to resolve a value into IDs.

The endpoint URL is read from an environment variable (never hardcoded), the
query is templated with the value, and IDs are extracted via a JSONPath.

Target search endpoints are usually fuzzy: asking a movie catalog for
"Harry Potter" can also return films whose director or actor matched. An
optional ``match`` block turns such a search into a resolver by keeping only
the candidates whose name really corresponds to the extracted value, so a
phrase the extractor guessed wrong ("action movies") resolves to nothing
instead of to an unrelated ID.
"""

from __future__ import annotations

import os
import re
import unicodedata
from typing import Any

import httpx
from jsonpath_ng.ext import parse as jsonpath_parse

from .base import Resolver

_NON_ALNUM_RE = re.compile(r"[^0-9a-z]+")


def normalize_name(value: Any) -> str:
    """Casefold a name for comparison: no accents, no punctuation, one space.

    "Harry Potter and the Philosopher's Stone" and
    "harry potter and the philosophers stone" compare equal.
    """
    text = unicodedata.normalize("NFKD", str(value)).encode("ascii", "ignore").decode()
    return _NON_ALNUM_RE.sub(" ", text.lower()).strip()


def names_match(value: str, candidate: str, mode: str) -> bool:
    """Whether ``candidate`` is the thing ``value`` named.

    ``exact`` requires the same name. ``contains`` accepts containment either
    way, which is what titles need: the query may shorten the title ("Harry
    Potter" for a series) or spell it out in full.
    """
    left, right = normalize_name(value), normalize_name(candidate)
    if not left or not right:
        return False
    if mode == "exact":
        return left == right
    if mode == "contains":
        return left in right or right in left
    if mode == "prefix":
        return right.startswith(left) or left.startswith(right)
    raise ValueError(f"Unknown match mode {mode!r}")


class HttpResolver(Resolver):
    def __init__(self, entity_key: str, spec: dict[str, Any]) -> None:
        super().__init__(entity_key, spec)
        self.method: str = spec.get("method", "GET").upper()
        self.url: str | None = self._resolve_url(spec)
        self.query_template: dict[str, str] = spec.get("query", {})
        self.result_path = jsonpath_parse(spec.get("result_path", "$[*]"))
        self.timeout: float = float(spec.get("timeout_seconds", 5.0))

        match: dict[str, Any] = spec.get("match") or {}
        # With no match block, result_path selects the IDs themselves.
        self.match_field: str | None = match.get("field")
        self.match_mode: str = match.get("mode", "exact")
        self.id_field: str = match.get("id_field", "id")
        self.match_limit: int | None = match.get("limit")

    @staticmethod
    def _resolve_url(spec: dict[str, Any]) -> str | None:
        if "url_from_env" in spec:
            return os.environ.get(spec["url_from_env"])
        return spec.get("url")

    async def resolve(self, value: str) -> list[Any]:
        if not self.url:
            return []
        params = {k: v.replace("{{ value }}", value) for k, v in self.query_template.items()}
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.request(self.method, self.url, params=params)
            resp.raise_for_status()
            data = resp.json()
        candidates = [match.value for match in self.result_path.find(data)]
        if self.match_field is None:
            return candidates
        return self._filter_candidates(value, candidates)

    def _filter_candidates(self, value: str, candidates: list[Any]) -> list[Any]:
        ids: list[Any] = []
        for candidate in candidates:
            if not isinstance(candidate, dict):
                continue
            name = candidate.get(self.match_field)
            if name is None or not names_match(value, name, self.match_mode):
                continue
            found = candidate.get(self.id_field)
            if found is None or found in ids:
                continue
            ids.append(found)
            if self.match_limit is not None and len(ids) >= self.match_limit:
                break
        return ids
